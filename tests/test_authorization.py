import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

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


class AuthorizationRegistryTest(unittest.TestCase):
    def test_old_state_file_with_only_enabled_still_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            with open(state, "w", encoding="utf-8") as f:
                json.dump({"enabled": ["browser"]}, f)
            registry = Registry(os.path.join(ROOT, "plugins"), state)
            self.assertIn("browser", registry.enabled)
            self.assertEqual(registry.allowed_apps, set())
            self.assertEqual(registry.allowed_tools, {})

    def test_allowed_apps_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            registry = Registry(os.path.join(ROOT, "plugins"), state)
            self.assertTrue(registry.is_app_allowed("Google Chrome"))
            registry.set_allowed_app("Google Chrome", True)
            self.assertTrue(registry.is_app_allowed("Google Chrome"))
            self.assertFalse(registry.is_app_allowed("TextEdit"))
            reloaded = Registry(os.path.join(ROOT, "plugins"), state)
            self.assertIn("Google Chrome", reloaded.allowed_apps)
            self.assertFalse(reloaded.is_app_allowed("TextEdit"))
            registry.set_allowed_app("Google Chrome", False)
            self.assertTrue(registry.is_app_allowed("TextEdit"))


class AuthorizationServerTest(unittest.TestCase):
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

    def test_authorization_get_returns_mode_and_lists(self):
        code, data = request(self.port, "GET", "/api/authorization")
        self.assertEqual(code, 200)
        self.assertEqual(data["computer"]["mode"], "dry_run")
        self.assertTrue(data["computer"]["dry_run"])
        self.assertTrue(data["localhost_auto_allowed"])
        self.assertIn("sites", data)
        self.assertIn("allowed_apps", data)

    def test_request_computer_access_on_linux_is_not_granted(self):
        code, data = request(self.port, "POST", "/api/authorization/request-computer-access", {})
        self.assertEqual(code, 200)
        self.assertFalse(data["granted"])
        self.assertIn("dry-run", (data.get("reason", "") + data.get("instructions", "")).lower())

    def test_allowed_tools_disallow_returns_403(self):
        request(self.port, "POST", "/api/plugins/cua/enable", {})
        code, data = request(
            self.port, "POST", "/api/authorization/allowed-tools",
            {"plugin": "cua", "tool": "click", "allowed": False})
        self.assertEqual(code, 200)
        self.assertIn("cua.click", data["disallowed_tools"])
        code, data = request(
            self.port, "POST", "/api/tools/cua/click/execute",
            {"app": "Google Chrome", "x": 10, "y": 10})
        self.assertEqual(code, 403)
        self.assertIn("disallowed", data["error"])
        request(
            self.port, "POST", "/api/authorization/allowed-tools",
            {"plugin": "cua", "tool": "click", "allowed": True})

    def test_allowed_apps_restriction_refuses_other_apps(self):
        request(self.port, "POST", "/api/plugins/cua/enable", {})
        request(
            self.port, "POST", "/api/authorization/allowed-apps",
            {"app": "Google Chrome", "allowed": True})
        code, data = request(
            self.port, "POST", "/api/tools/cua/click/execute",
            {"app": "TextEdit", "x": 10, "y": 10})
        self.assertEqual(code, 403)
        self.assertIn("not allowed", data["error"])
        request(
            self.port, "POST", "/api/authorization/allowed-apps",
            {"app": "Google Chrome", "allowed": False})


if __name__ == "__main__":
    unittest.main()
