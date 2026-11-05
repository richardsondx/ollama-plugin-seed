import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from computer.adapter import DryRunAdapter  # noqa: E402
from cua.cdp import list_tabs  # noqa: E402
from plugins.loader import discover  # noqa: E402
from plugins.registry import Registry  # noqa: E402
from server.plugin_server import create_server  # noqa: E402


def request(port, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


class FoldManifestTest(unittest.TestCase):
    def test_folded_manifests_cover_every_old_cua_tool(self):
        plugins, errors = discover(os.path.join(ROOT, "plugins"))
        self.assertEqual(errors, {})
        self.assertNotIn("cua", plugins)
        browser = [t["name"] for t in plugins["browser"]["tools"]]
        computer = [t["name"] for t in plugins["computer"]["tools"]]
        for expected in ("list_tabs", "create_tab", "get_tab"):
            self.assertIn(expected, browser)
        for expected in ("get_state", "open_app", "click", "type_text"):
            self.assertIn(expected, computer)
        self.assertIn("webmcp.list_tools", browser)
        self.assertIn("webmcp.execute_tool", browser)
        self.assertIn("list_apps", computer)
        self.assertIn("get_app_state", computer)

    def test_dry_run_adapter_records_without_touching(self):
        adapter = DryRunAdapter()
        self.assertTrue(adapter.open_app("Google Chrome")["dry_run"])
        self.assertTrue(adapter.click("Google Chrome", x=100, y=200)["dry_run"])
        self.assertTrue(adapter.type_text("Google Chrome", "hello")["dry_run"])
        actions = [a["action"] for a in adapter.actions]
        self.assertEqual(actions, ["open_app", "click", "type_text"])

    def test_cdp_unreachable_is_error_not_a_tab(self):
        with self.assertRaises(RuntimeError) as ctx:
            list_tabs()
        self.assertIn("9222", str(ctx.exception))

    def test_old_state_file_listing_cua_surfaces_no_cua_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            with open(state, "w", encoding="utf-8") as f:
                json.dump({
                    "enabled": ["browser", "computer", "cua"],
                    "allowed_tools": {"cua.click": False},
                }, f)
            registry = Registry(os.path.join(ROOT, "plugins"), state)
            self.assertNotIn("cua", registry.enabled)
            self.assertNotIn("cua.click", registry.allowed_tools)
            names = [t["function"]["name"] for t in registry.enabled_tools()]
            self.assertFalse(any(n.startswith("cua.") for n in names))
            self.assertIn("browser.create_tab", names)
            self.assertIn("computer.open_app", names)


class FoldServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = create_server(0, os.path.join(cls.tmp.name, "state.json"))
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_browser_create_tab_dry_run_opens_nothing(self):
        request(self.port, "POST", "/api/plugins/browser/enable", {})
        code, data = request(self.port, "POST", "/api/tools/browser/create_tab/execute",
                             {"url": "https://google.com"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertIn("no tab was opened", data["result"]["note"])

    def test_browser_list_tabs_dry_run_lists_no_pretend_tabs(self):
        request(self.port, "POST", "/api/plugins/browser/enable", {})
        code, data = request(self.port, "POST", "/api/tools/browser/list_tabs/execute", {})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertEqual(data["result"]["tabs"], [])

    def test_computer_open_app_dry_run_records(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/open_app/execute",
                             {"app": "Google Chrome"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertTrue(data["result"]["dry_run"])

    def test_computer_click_dry_run_does_not_claim_real_click(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/click/execute",
                             {"app": "Google Chrome", "x": 100, "y": 200})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertTrue(data["result"]["dry_run"])
        self.assertNotIn("Real Mac", data.get("note", ""))

    def test_computer_get_state_dry_run(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/get_state/execute", {})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertTrue(data["result"]["dry_run"])
        self.assertEqual(data["result"]["tabs"], [])

    def test_computer_click_confirmation_gate_still_holds(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/click/execute",
                             {"app": "Google Chrome", "x": 1, "y": 2,
                              "action": "delete_data"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("confirmation_required"))

    def test_old_cua_route_is_refused_not_executed(self):
        request(self.port, "POST", "/api/plugins/browser/enable", {})
        code, data = request(self.port, "POST", "/api/tools/cua/create_tab/execute",
                             {"url": "https://google.com"})
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
