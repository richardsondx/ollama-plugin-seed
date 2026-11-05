import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

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


class ServerTest(unittest.TestCase):
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

    def test_plugins_list_and_enable(self):
        code, data = request(self.port, "GET", "/api/plugins")
        self.assertEqual(code, 200)
        self.assertEqual(len(data["plugins"]), 3)
        code, data = request(self.port, "POST", "/api/plugins/browser/enable", {})
        self.assertEqual(code, 200)
        self.assertTrue(data["enabled"])
        code, data = request(self.port, "GET", "/api/tools")
        self.assertTrue(any(t["function"]["name"] == "browser.webmcp.list_tools" for t in data["tools"]))
        code, data = request(self.port, "POST", "/api/plugins/browser/disable", {})
        self.assertFalse(data["enabled"])

    def test_disabled_tool_refused(self):
        code, data = request(self.port, "POST", "/api/tools/computer/list_apps/execute", {})
        self.assertEqual(code, 403)

    def test_computer_confirmation_gate(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/click/execute", {"action": "delete_data"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("confirmation_required"))
        self.assertEqual(data["policy"], "always_confirm")
        request(self.port, "POST", "/api/plugins/computer/disable", {})

    def test_computer_runs_through_adapter_and_says_dry_run(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/list_apps/execute", {})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertTrue(data.get("result"))
        code, data = request(self.port, "POST", "/api/tools/computer/click/execute", {"app": "Chrome"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        code, data = request(self.port, "POST", "/api/tools/computer/get_app_state/execute", {})
        self.assertEqual(code, 400)
        request(self.port, "POST", "/api/plugins/computer/disable", {})

    def test_webmcp_register_and_list(self):
        code, data = request(self.port, "POST", "/api/webmcp/tools", {
            "site": "https://example.com",
            "tools": [{"name": "search", "description": "Search the example site."}],
        })
        self.assertEqual(code, 200)
        self.assertEqual(data["tools_registered"], 1)
        code, data = request(self.port, "GET", "/api/webmcp/tools")
        self.assertTrue(any(t["name"] == "search" for t in data["tools"]))


if __name__ == "__main__":
    unittest.main()
