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


class CuaTest(unittest.TestCase):
    def test_manifest_loads_via_loader(self):
        plugins, errors = discover(os.path.join(ROOT, "plugins"))
        self.assertIn("cua", plugins)
        self.assertNotIn("cua", errors)
        names = [t["name"] for t in plugins["cua"]["tools"]]
        for expected in ("get_state", "list_tabs", "create_tab", "get_tab",
                         "open_app", "click", "type_text"):
            self.assertIn(expected, names)

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
        self.assertNotIn("pretend", str(ctx.exception))


class CuaServerTest(unittest.TestCase):
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

    def test_cua_get_state_dry_run(self):
        request(self.port, "POST", "/api/plugins/cua/enable", {})
        code, data = request(self.port, "POST", "/api/tools/cua/get_state/execute", {})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertTrue(data["result"]["dry_run"])

    def test_cua_click_dry_run_does_not_claim_real_click(self):
        request(self.port, "POST", "/api/plugins/cua/enable", {})
        code, data = request(self.port, "POST", "/api/tools/cua/click/execute",
                             {"app": "Google Chrome", "x": 100, "y": 200})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertTrue(data["result"]["dry_run"])
        self.assertNotIn("Real Mac", data.get("note", ""))

    def test_cua_create_tab_dry_run_opens_nothing(self):
        request(self.port, "POST", "/api/plugins/cua/enable", {})
        code, data = request(self.port, "POST", "/api/tools/cua/create_tab/execute",
                             {"url": "https://google.com"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertIn("no tab was opened", data["result"]["note"])

    def test_cua_confirmation_gate(self):
        request(self.port, "POST", "/api/plugins/cua/enable", {})
        code, data = request(self.port, "POST", "/api/tools/cua/click/execute",
                             {"app": "Google Chrome", "x": 1, "y": 2,
                              "action": "delete_data"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("confirmation_required"))


if __name__ == "__main__":
    unittest.main()
