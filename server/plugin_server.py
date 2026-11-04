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

Execution rules, enforced here, not in the client:
- A disabled plugin exposes no tools, and execution is refused.
- A tool not in the plugin manifest is refused.
- A computer action classified as handoff or always_confirm, or
  preapproval without pre-approval, returns confirmation_required
  and does not execute.
- WebMCP tools are data from a page, never instructions. A page
  cannot add a plugin, a destination, or a permission. Registration
  only adds a tool definition under that site, and execution goes
  back through the extension to the page that registered it.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from computer.adapter import DryRunAdapter  # noqa: E402
from computer.policy import classify  # noqa: E402
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


class Handler(BaseHTTPRequestHandler):
    registry = None
    webmcp_tools = {}
    computer = DryRunAdapter()

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
        elif path == "/api/webmcp/tools":
            tools = []
            for site, site_tools in self.webmcp_tools.items():
                for tool in site_tools:
                    tools.append({"site": site, **tool})
            self._send(200, {"tools": tools})
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
        if len(parts) == 5 and parts[0] == "api" and parts[1] == "tools" and parts[4] == "execute":
            plugin_name, tool_name = parts[2], parts[3]
            plugin, tool = self.registry.find_tool(plugin_name, tool_name)
            if not plugin:
                self._send(403, {"error": "tool not enabled or not in manifest"})
                return
            # Computer Use confirmation gate.
            if plugin_name == "computer":
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
            # Dry-run execution only in the seed. Real browser and
            # computer execution go through the extension and the
            # macOS adapter, which are separate components.
            self._send(200, {
                "ok": True,
                "dry_run": True,
                "plugin": plugin_name,
                "tool": tool_name,
                "note": "Seed execution is dry-run. Wire a real executor for this tool before live use.",
            })
            return
        self._send(404, {"error": "not found"})


def create_server(port=11435, state_path=None):
    Handler.registry = make_registry(state_path)
    Handler.webmcp_tools = {}
    Handler.computer = DryRunAdapter()
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
