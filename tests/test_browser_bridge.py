"""Browser control through the Chrome extension bridge.

A thread plays the extension: it long-polls /api/browser/next and
posts results to /api/browser/result, the same protocol the real
extension's background worker uses.
"""
import os
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.plugin_server import create_server  # noqa: E402
from test_webmcp_bridge import request  # noqa: E402


class FakeExtension(threading.Thread):
    def __init__(self, port):
        super().__init__(daemon=True)
        self.port = port
        self.stop = False
        self.seen = []

    def run(self):
        while not self.stop:
            code, data = request(self.port, "GET", "/api/browser/next?wait=1&version=test&control=1")
            job = data.get("job")
            if not job:
                continue
            self.seen.append(job)
            if job["kind"] != "browser":
                continue
            if job["action"] == "click" and job["args"].get("ref") == 999:
                request(self.port, "POST", "/api/browser/result", {"id": job["id"], "error": "no element with ref 999"})
            else:
                request(self.port, "POST", "/api/browser/result", {
                    "id": job["id"],
                    "result": {"tab_id": 7, "text": "Tab 7: Example\nURL: https://example.com/\n\n[1] link \"More\""},
                })


class BrowserBridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = create_server(0, os.path.join(self.tmp.name, "state.json"))
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        request(self.port, "POST", "/api/plugins/browser/enable", {})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_status_reports_extension(self):
        code, data = request(self.port, "GET", "/api/browser/status")
        self.assertEqual(code, 200)
        self.assertFalse(data["connected"])
        ext = FakeExtension(self.port)
        ext.start()
        time.sleep(0.3)
        code, data = request(self.port, "GET", "/api/browser/status")
        self.assertTrue(data["connected"])
        ext.stop = True

    def test_actions_run_through_extension(self):
        ext = FakeExtension(self.port)
        ext.start()
        time.sleep(0.3)
        code, data = request(self.port, "POST", "/api/tools/browser/create_tab/execute", {"url": "example.com"})
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"], data)
        self.assertEqual(data["route"], "chrome extension")
        self.assertIn("[1] link", data["result"]["text"])
        code, data = request(self.port, "POST", "/api/tools/browser/click/execute", {"ref": 1})
        self.assertTrue(data["ok"])
        jobs = [(j["action"], j["args"]) for j in ext.seen]
        self.assertEqual(jobs[0], ("create_tab", {"url": "example.com"}))
        self.assertEqual(jobs[1], ("click", {"ref": 1}))
        ext.stop = True

    def test_extension_error_is_not_success(self):
        ext = FakeExtension(self.port)
        ext.start()
        time.sleep(0.3)
        code, data = request(self.port, "POST", "/api/tools/browser/click/execute", {"ref": 999})
        self.assertFalse(data["ok"])
        self.assertIn("999", data["error"])
        ext.stop = True

    def test_no_extension_gives_setup_error(self):
        code, data = request(self.port, "POST", "/api/tools/browser/read_page/execute", {})
        self.assertEqual(code, 200)
        self.assertFalse(data["ok"])
        self.assertIn("chrome://extensions", data["error"])


if __name__ == "__main__":
    unittest.main()
