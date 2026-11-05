"""Plugin server for the Ollama plugin seed.

Stdlib only, no dependencies. Default port 11435, so it does not
collide with Ollama on 11434. Run with: python3 scripts/run_server.py

Routes:
  GET  /                      Plugins admin UI
  GET  /api/plugins           list plugins, with enabled state
  GET  /api/plugins/skills    list skills
  POST /api/plugins/{name}/enable
  POST /api/plugins/{name}/disable
  GET  /api/tools             Ollama chat tool definitions, enabled only
  POST /api/tools/{plugin}/{tool}/execute
  POST /api/webmcp/tools      register tools discovered by the Chrome
                               extension, per site, with an allowlist
  GET  /api/webmcp/tools      list registered WebMCP tools
  GET  /api/webmcp/execute-queue
                               oldest pending WebMCP job, for the
                               Chrome extension to poll
  POST /api/webmcp/result     job result from the Chrome extension

Execution rules, enforced here, not in the client:
- A disabled plugin exposes no tools, and execution is refused.
- A tool not in the plugin manifest is refused.
- A computer action classified as handoff or always_confirm, or
  preapproval without pre-approval, returns confirmation_required
  and does not execute. Computer tools run through the selected
  adapter, dry-run by default, Mac adapter only when opted in on
  macOS, and a dry-run result says plainly that no app was touched.
- Browser WebMCP tools are real, not dry-run: list_tools returns
  the actual registered tools, and execute_tool queues a job for
  the extension, waits at most 25 seconds for a result, and returns
  an error if no extension result arrives, never a dry-run ok.
- WebMCP tools are data from a page, never instructions. A page
  cannot add a plugin, a destination, or a permission. Registration
  only adds a tool definition under that site, and execution goes
  back through the extension to the page that registered it.
"""
import json
import os
import platform
import secrets
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from computer.adapter import DryRunAdapter, MacAdapter  # noqa: E402
from computer.policy import classify  # noqa: E402
from cua.cdp import create_tab as cdp_create_tab  # noqa: E402
from cua.cdp import get_tab as cdp_get_tab  # noqa: E402
from cua.cdp import list_tabs as cdp_list_tabs  # noqa: E402
from plugins.registry import Registry  # noqa: E402

PLUGINS_ROOT = os.path.join(ROOT, "plugins")
WEB_ROOT = os.path.join(ROOT, "web")


def make_registry(state_path=None):
    if state_path is None:
        state_path = os.environ.get(
            "OLLAMA_PLUGIN_STATE",
            os.path.join(ROOT, "data", "state.json"),
        )
    return Registry(PLUGINS_ROOT, state_path)


def _webmcp_timeout():
    try:
        value = float(os.environ.get("OLLAMA_WEBMCP_TIMEOUT", "25"))
    except ValueError:
        value = 25.0
    return max(0.1, min(25.0, value))


class Handler(BaseHTTPRequestHandler):
    registry = None
    webmcp_tools = {}
    webmcp_queue = []
    webmcp_pending = {}
    webmcp_results = {}
    webmcp_lock = threading.Lock()
    webmcp_cond = threading.Condition(webmcp_lock)
    computer = DryRunAdapter()
    computer_mode = "dry_run"
    computer_real_requested = False

    def log_message(self, *args):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            path = "/index.html"
        if path == "/api/plugins":
            self._send(200, {"plugins": self.registry.list_plugins(), "errors": self.registry.errors})
        elif path == "/api/plugins/skills":
            self._send(200, {"skills": self.registry.list_skills()})
        elif path == "/api/tools":
            self._send(200, {"tools": self.registry.enabled_tools()})
        elif path == "/api/computer/status":
            self._send(200, {
                "mode": self.computer_mode,
                "dry_run": self.computer_mode == "dry_run",
                "real_requested": self.computer_real_requested,
            })
        elif path == "/api/authorization":
            self._send(200, {
                "computer": {
                    "mode": self.computer_mode,
                    "dry_run": self.computer_mode == "dry_run",
                    "real_requested": self.computer_real_requested,
                },
                "enabled_plugins": sorted(self.registry.enabled),
                "allowed_apps": sorted(self.registry.allowed_apps),
                "app_restriction_active": bool(self.registry.allowed_apps),
                "allowed_tools": dict(sorted(self.registry.allowed_tools.items())),
                "disallowed_tools": sorted(
                    key for key, value in self.registry.allowed_tools.items()
                    if value is False),
                "sites": sorted(self.webmcp_tools.keys()),
                "localhost_auto_allowed": True,
                "notes": [
                    "Allowed sites here are only sites with registered WebMCP tools. The Chrome popup is still the place that adds a remote site, because site permission lives in Chrome storage, not on this server. Localhost and 127.0.0.1 are auto-allowed in local mode.",
                    "Empty allowed apps means no app restriction yet. Add an app to turn the restriction on.",
                    "A tool is allowed unless it is explicitly set to false here.",
                    "Authorization settings do not bypass the confirmation gate for risky actions.",
                ],
            })
        elif path == "/api/webmcp/tools":
            tools = []
            for site, site_tools in self.webmcp_tools.items():
                for tool in site_tools:
                    tools.append({"site": site, **tool})
            self._send(200, {"tools": tools})
        elif path == "/api/webmcp/execute-queue":
            job = None
            with self.webmcp_lock:
                while self.webmcp_queue:
                    candidate = self.webmcp_queue.pop(0)
                    if candidate["site"] in self.webmcp_tools:
                        job = candidate
                        break
            self._send(200, {"job": job})
        elif path.startswith("/ui/") or path == "/index.html":
            rel = path.lstrip("/")
            if rel == "index.html":
                rel = "index.html"
            else:
                rel = rel[3:]
            full = os.path.join(WEB_ROOT, rel)
            if not os.path.isfile(full) or not full.startswith(WEB_ROOT):
                self._send(404, {"error": "not found"})
                return
            with open(full, "rb") as f:
                body = f.read()
            ctype = "text/html" if full.endswith(".html") else "text/javascript"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_json()
        parts = [p for p in path.split("/") if p]
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "plugins" and parts[3] in ("enable", "disable"):
            name = parts[2]
            ok = self.registry.enable(name) if parts[3] == "enable" else self.registry.disable(name)
            if not ok:
                self._send(404, {"error": "unknown plugin: %s" % name})
            else:
                self._send(200, {"name": name, "enabled": name in self.registry.enabled})
            return
        if path == "/api/authorization/request-computer-access":
            if self.computer_mode != "mac":
                self._send(200, {
                    "granted": False,
                    "mode": self.computer_mode,
                    "dry_run": self.computer_mode == "dry_run",
                    "real_requested": self.computer_real_requested,
                    "reason": "Real mode is off. Start the seed server on macOS with OLLAMA_COMPUTER_USE_REAL=1, then request access again. Dry-run never counts as granted.",
                    "instructions": "On macOS, start the seed with OLLAMA_COMPUTER_USE_REAL=1, then request access again. If macOS asks, grant Accessibility in System Settings, Privacy and Security, Accessibility, to the app running the seed server, restart the seed, then recheck.",
                })
                return
            try:
                self.computer.list_apps()
                self._send(200, {
                    "granted": True,
                    "mode": self.computer_mode,
                    "reason": "A System Events listing succeeded, which means Accessibility appears to be granted to the app running the seed server.",
                })
            except Exception as exc:
                self._send(200, {
                    "granted": False,
                    "mode": self.computer_mode,
                    "reason": str(exc),
                    "instructions": "Grant Accessibility in System Settings, Privacy and Security, Accessibility, to the app running the seed server, restart the seed, then recheck. Ollamapaca can request and recheck this permission, it cannot grant it itself.",
                })
            return
        if path == "/api/authorization/allowed-apps":
            app = body.get("app", "")
            allowed = body.get("allowed")
            if not isinstance(app, str) or not app or not isinstance(allowed, bool):
                self._send(400, {"error": "app as a string and allowed as true or false are required"})
                return
            self.registry.set_allowed_app(app, allowed)
            self._send(200, {
                "app": app,
                "allowed": allowed,
                "allowed_apps": sorted(self.registry.allowed_apps),
                "app_restriction_active": bool(self.registry.allowed_apps),
                "note": "Empty allowed apps means no app restriction yet. Adding an app turns the restriction on.",
            })
            return
        if path == "/api/authorization/allowed-tools":
            plugin_name = body.get("plugin", "")
            tool_name = body.get("tool", "")
            allowed = body.get("allowed")
            if not isinstance(allowed, bool):
                self._send(400, {"error": "plugin, tool, and allowed as true or false are required"})
                return
            # find_tool requires the plugin to be enabled, so check the
            # manifest directly here, otherwise a tool could never be
            # disallowed before the plugin is enabled.
            manifest = self.registry.plugins.get(plugin_name) if isinstance(plugin_name, str) else None
            if not manifest or not any(t["name"] == tool_name for t in manifest.get("tools", [])):
                self._send(404, {"error": "unknown plugin or tool: %s.%s" % (plugin_name, tool_name)})
                return
            self.registry.set_allowed_tool(plugin_name, tool_name, allowed)
            self._send(200, {
                "plugin": plugin_name,
                "tool": tool_name,
                "allowed": allowed,
                "disallowed_tools": sorted(
                    key for key, value in self.registry.allowed_tools.items()
                    if value is False),
            })
            return
        if path == "/api/webmcp/tools":
            site = body.get("site", "")
            tools = body.get("tools", [])
            if not site or not isinstance(tools, list):
                self._send(400, {"error": "site and tools list are required"})
                return
            clean = []
            for tool in tools:
                if tool.get("name") and tool.get("description"):
                    clean.append({
                        "name": tool["name"],
                        "description": tool["description"],
                        "inputSchema": tool.get("inputSchema", {"type": "object", "properties": {}}),
                    })
            self.webmcp_tools[site] = clean
            self._send(200, {"site": site, "tools_registered": len(clean)})
            return
        if path == "/api/webmcp/result":
            job_id = body.get("id", "")
            with self.webmcp_lock:
                job = self.webmcp_pending.get(job_id)
                if not job:
                    self._send(404, {"error": "unknown job: %s" % job_id})
                    return
                if job["site"] not in self.webmcp_tools:
                    del self.webmcp_pending[job_id]
                    self._send(400, {"error": "site is no longer registered"})
                    return
                self.webmcp_results[job_id] = {
                    "result": body.get("result"),
                    "error": body.get("error"),
                }
                self.webmcp_cond.notify_all()
            self._send(200, {"ok": True, "id": job_id})
            return
        if len(parts) == 5 and parts[0] == "api" and parts[1] == "tools" and parts[4] == "execute":
            plugin_name, tool_name = parts[2], parts[3]
            plugin, tool = self.registry.find_tool(plugin_name, tool_name)
            if not plugin:
                self._send(403, {"error": "tool not enabled or not in manifest"})
                return
            # Authorization enforcement, before any execution and
            # before the confirmation gate. An explicitly disallowed
            # tool is refused even if its plugin is enabled. An app
            # restriction, when set, refuses cua and computer app
            # actions for apps not on the list. This never bypasses
            # the confirmation gate below.
            if not self.registry.is_tool_allowed(plugin_name, tool_name):
                self._send(403, {
                    "error": "tool is disallowed in Authorization settings: %s.%s" % (plugin_name, tool_name),
                })
                return
            if plugin_name in ("computer", "cua") and tool_name in ("click", "type_text", "open_app"):
                app = body.get("app", "")
                if not self.registry.is_app_allowed(app):
                    self._send(403, {
                        "error": "app is not allowed in Authorization settings: %s. Add it to allowed apps first." % app,
                    })
                    return
            # Computer Use confirmation gate. Computer tools are
            # dry-run unless the server was started on macOS with
            # OLLAMA_COMPUTER_USE_REAL=1, which selects MacAdapter.
            if plugin_name in ("computer", "cua"):
                action = body.get("action", tool_name)
                outcome = classify(action, sensitive_data=bool(body.get("sensitive_data")), preapproved=bool(body.get("preapproved")))
                if outcome in ("handoff", "always_confirm", "preapproval_or_confirm"):
                    self._send(200, {
                        "confirmation_required": True,
                        "policy": outcome,
                        "action": action,
                        "message": "This computer action needs confirmation before it runs, or a handoff to the user.",
                    })
                    return
            # Browser WebMCP: real execution through the extension.
            if plugin_name == "browser" and tool_name == "webmcp.list_tools":
                tools = []
                for site, site_tools in self.webmcp_tools.items():
                    for tool in site_tools:
                        tools.append({"site": site, **tool})
                self._send(200, {
                    "ok": True,
                    "plugin": plugin_name,
                    "tool": tool_name,
                    "tools": tools,
                })
                return
            if plugin_name == "browser" and tool_name == "webmcp.execute_tool":
                site = body.get("site", "")
                tool_requested = body.get("tool", "")
                registered = self.webmcp_tools.get(site, [])
                if not site or not any(t["name"] == tool_requested for t in registered):
                    known = []
                    for known_site, known_tools in self.webmcp_tools.items():
                        for known_tool in known_tools:
                            known.append({"site": known_site, "tool": known_tool["name"]})
                    self._send(400, {
                        "error": (
                            "Site or tool is not registered: %s %s. "
                            "Call webmcp.list_tools first and only call a tool that "
                            "list_tools returned, with its exact site origin. "
                            "A site that did not register WebMCP tools cannot be "
                            "controlled this way, and a tool list_tools did not "
                            "return does not exist, even if it sounds plausible."
                            % (site, tool_requested)
                        ),
                        "registered": known,
                    })
                    return
                job_id = secrets.token_hex(8)
                job = {
                    "id": job_id,
                    "site": site,
                    "tool": tool_requested,
                    "input": body.get("input") or {},
                }
                timeout = _webmcp_timeout()
                with self.webmcp_cond:
                    self.webmcp_pending[job_id] = job
                    self.webmcp_queue.append(job)
                    self.webmcp_cond.notify_all()
                    result = self.webmcp_cond.wait_for(
                        lambda: job_id in self.webmcp_results, timeout=timeout)
                    outcome = self.webmcp_results.pop(job_id, None)
                    self.webmcp_pending.pop(job_id, None)
                if not result or outcome is None:
                    self._send(200, {
                        "ok": False,
                        "plugin": plugin_name,
                        "tool": tool_name,
                        "error": "no extension result within %s seconds" % timeout,
                    })
                    return
                if outcome.get("error"):
                    self._send(200, {
                        "ok": False,
                        "plugin": plugin_name,
                        "tool": tool_name,
                        "error": outcome["error"],
                    })
                    return
                self._send(200, {
                    "ok": True,
                    "plugin": plugin_name,
                    "tool": tool_name,
                    "site": site,
                    "result": outcome.get("result"),
                })
                return
            # Computer tools run through the selected adapter, after
            # the confirmation gate above. Dry-run is the default, and
            # its result says dry-run plainly, never that an app was
            # opened or touched. In Mac mode the adapter is MacAdapter,
            # and a tool it does not implement returns an error, never
            # a pretend success.
            if plugin_name == "computer":
                adapter = self.computer
                dry_run = self.computer_mode == "dry_run"
                try:
                    if tool_name == "list_apps":
                        result = adapter.list_apps()
                    elif tool_name == "get_app_state":
                        app = body.get("app", "")
                        if not app:
                            self._send(400, {"error": "app is required for get_app_state"})
                            return
                        result = adapter.get_app_state(app)
                    elif tool_name == "click":
                        if dry_run:
                            result = adapter.click(
                                body.get("app", ""),
                                element_index=body.get("element_index"),
                                x=body.get("x"),
                                y=body.get("y"),
                            )
                        else:
                            self._send(200, {
                                "ok": False,
                                "plugin": plugin_name,
                                "tool": tool_name,
                                "error": "Mac adapter does not implement click yet, no click was performed.",
                            })
                            return
                    elif tool_name == "type_text":
                        if dry_run:
                            result = adapter.type_text(body.get("app", ""), body.get("text", ""))
                        else:
                            self._send(200, {
                                "ok": False,
                                "plugin": plugin_name,
                                "tool": tool_name,
                                "error": "Mac adapter does not implement type_text yet, no text was typed.",
                            })
                            return
                    else:
                        self._send(403, {"error": "tool not enabled or not in manifest"})
                        return
                except Exception as exc:
                    self._send(200, {
                        "ok": False,
                        "plugin": plugin_name,
                        "tool": tool_name,
                        "error": str(exc),
                    })
                    return
                self._send(200, {
                    "ok": True,
                    "dry_run": dry_run,
                    "plugin": plugin_name,
                    "tool": tool_name,
                    "result": result,
                    "note": "Dry-run: no app was touched." if dry_run else "Real Mac adapter result.",
                })
                return
            # Cua: generic browser and computer control, built from
            # scratch, not WebMCP page tools and not OpenAI code.
            # It routes through the selected adapter, after the
            # confirmation gate above, exactly like computer. Dry-run
            # never touches an app or opens a tab, and says so.
            # In Mac mode, tab tools use the Chrome debugging port,
            # and create_tab falls back to opening Chrome with the
            # URL if that port is unreachable, stating the route.
            if plugin_name == "cua":
                adapter = self.computer
                dry_run = self.computer_mode == "dry_run"
                try:
                    if tool_name == "get_state":
                        try:
                            tabs = cdp_list_tabs()
                            tabs_note = "Chrome tabs from the debugging port."
                        except Exception as exc:
                            tabs = []
                            tabs_note = str(exc)
                        try:
                            apps = adapter.list_apps()
                        except Exception as exc:
                            apps = []
                            tabs_note += " Apps listing failed: %s" % exc
                        result = {
                            "mode": self.computer_mode,
                            "dry_run": dry_run,
                            "apps": apps,
                            "tabs": tabs,
                            "tabs_note": tabs_note,
                        }
                    elif tool_name == "list_tabs":
                        if dry_run:
                            result = {
                                "dry_run": True,
                                "tabs": [],
                                "note": "Dry-run: no Chrome was contacted, no tab was listed.",
                            }
                        else:
                            result = {"tabs": cdp_list_tabs()}
                    elif tool_name == "create_tab":
                        url = body.get("url", "")
                        if not url:
                            self._send(400, {"error": "url is required for create_tab"})
                            return
                        if dry_run:
                            result = {
                                "dry_run": True,
                                "url": url,
                                "note": "Dry-run: no tab was opened, no app was touched.",
                            }
                        else:
                            try:
                                tab = cdp_create_tab(url)
                                result = {"route": "chrome debugging port", "tab": tab}
                            except Exception:
                                if platform.system() != "Darwin":
                                    raise
                                proc = subprocess.run(
                                    ["open", "-a", "Google Chrome", url],
                                    capture_output=True, text=True, timeout=30, check=False,
                                )
                                if proc.returncode != 0:
                                    raise RuntimeError("open failed: %s" % proc.stderr.strip())
                                result = {
                                    "route": "open -a Google Chrome, debugging port unreachable",
                                    "url": url,
                                    "note": "Tab was opened by opening Chrome, tab state is unavailable without the debugging port at 127.0.0.1:9222.",
                                }
                    elif tool_name == "get_tab":
                        if dry_run:
                            result = {
                                "dry_run": True,
                                "note": "Dry-run: no Chrome was contacted, no tab was fetched.",
                            }
                        else:
                            result = {"tab": cdp_get_tab(
                                tab_id=body.get("tab_id"), url=body.get("url"))}
                    elif tool_name == "open_app":
                        app = body.get("app", "")
                        if not app:
                            self._send(400, {"error": "app is required for open_app"})
                            return
                        result = adapter.open_app(app)
                    elif tool_name == "click":
                        result = adapter.click(
                            body.get("app", ""),
                            element_index=body.get("element_index"),
                            x=body.get("x"),
                            y=body.get("y"),
                        )
                    elif tool_name == "type_text":
                        result = adapter.type_text(body.get("app", ""), body.get("text", ""))
                    else:
                        self._send(403, {"error": "tool not enabled or not in manifest"})
                        return
                except Exception as exc:
                    self._send(200, {
                        "ok": False,
                        "plugin": plugin_name,
                        "tool": tool_name,
                        "error": str(exc),
                    })
                    return
                self._send(200, {
                    "ok": True,
                    "dry_run": dry_run,
                    "plugin": plugin_name,
                    "tool": tool_name,
                    "result": result,
                    "note": "Dry-run: no app was touched." if dry_run else "Real adapter result.",
                })
                return
            # Dry-run execution only in the seed for other tools.
            self._send(200, {
                "ok": True,
                "dry_run": True,
                "plugin": plugin_name,
                "tool": tool_name,
                "note": "Seed execution is dry-run. Wire a real executor for this tool before live use.",
            })
            return
        self._send(404, {"error": "not found"})


def select_computer_adapter():
    # Real Mac control is opt in only. Dry-run is the default, and
    # it is also what runs on any non-Mac machine, even if real
    # mode was requested, because MacAdapter itself requires Darwin.
    requested = os.environ.get("OLLAMA_COMPUTER_USE_REAL") == "1"
    if platform.system() == "Darwin" and requested:
        return MacAdapter(), "mac", requested
    return DryRunAdapter(), "dry_run", requested


def create_server(port=11435, state_path=None):
    Handler.registry = make_registry(state_path)
    Handler.webmcp_tools = {}
    Handler.webmcp_queue = []
    Handler.webmcp_pending = {}
    Handler.webmcp_results = {}
    adapter, mode, requested = select_computer_adapter()
    Handler.computer = adapter
    Handler.computer_mode = mode
    Handler.computer_real_requested = requested
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    port = int(os.environ.get("OLLAMA_PLUGIN_PORT", "11435"))
    server = create_server(port)
    print("Ollama plugin seed server on http://127.0.0.1:%d" % port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
