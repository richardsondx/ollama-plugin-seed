import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.plugin_server import create_server  # noqa: E402


def request(port, method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"error": raw}


class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = create_server(0, os.path.join(cls.tmp.name, "state.json"))
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        request(cls.port, "POST", "/api/plugins/browser/enable", {})
        request(cls.port, "POST", "/api/plugins/computer/enable", {})
        request(cls.port, "POST", "/api/webmcp/tools", {
            "site": "http://localhost:3000",
            "tools": [
                {"name": "local_echo", "description": "Return the text you gave, unchanged."},
                {"name": "local_time", "description": "Return the current local time."},
            ],
        })

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_list_tools_returns_registered_tools_not_dry_run(self):
        code, data = request(self.port, "POST", "/api/tools/browser/webmcp.list_tools/execute", {})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("ok"))
        self.assertNotIn("dry_run", data)
        names = [t["name"] for t in data["tools"]]
        self.assertIn("local_echo", names)
        self.assertIn("local_time", names)
        self.assertTrue(all(t["site"] == "http://localhost:3000" for t in data["tools"]))

    def test_execute_unregistered_site_and_tool_are_errors(self):
        code, data = request(self.port, "POST", "/api/tools/browser/webmcp.execute_tool/execute", {
            "site": "http://localhost:9999", "tool": "local_echo", "input": {},
        })
        self.assertEqual(code, 400)
        self.assertIn("error", data)
        code, data = request(self.port, "POST", "/api/tools/browser/webmcp.execute_tool/execute", {
            "site": "http://localhost:3000", "tool": "no_such_tool", "input": {},
        })
        self.assertEqual(code, 400)
        self.assertIn("error", data)

    def test_execute_queue_poll_post_result(self):
        holder = {}
        def call_execute():
            holder["code"], holder["data"] = request(
                self.port, "POST", "/api/tools/browser/webmcp.execute_tool/execute",
                {"site": "http://localhost:3000", "tool": "local_echo", "input": {"text": "hello"}},
                timeout=30)
        thread = threading.Thread(target=call_execute, daemon=True)
        thread.start()
        # Poll like the extension, with retries, then post a result.
        job = None
        for _ in range(50):
            code, data = request(self.port, "GET", "/api/webmcp/execute-queue")
            self.assertEqual(code, 200)
            if data.get("job"):
                job = data["job"]
                break
            threading.Event().wait(0.1)
        self.assertIsNotNone(job, "queue never returned the job")
        self.assertEqual(job["tool"], "local_echo")
        self.assertEqual(job["input"], {"text": "hello"})
        code, data = request(self.port, "GET", "/api/webmcp/execute-queue")
        self.assertIsNone(data.get("job"), "queue should pop the job once")
        code, data = request(self.port, "POST", "/api/webmcp/result", {
            "id": job["id"], "result": "hello",
        })
        self.assertEqual(code, 200)
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive(), "execute call did not return after a result")
        self.assertEqual(holder["code"], 200)
        self.assertTrue(holder["data"].get("ok"))
        self.assertEqual(holder["data"].get("result"), "hello")
        self.assertNotIn("dry_run", holder["data"])

    def test_execute_timeout_is_error_not_dry_run(self):
        os.environ["OLLAMA_WEBMCP_TIMEOUT"] = "0.5"
        try:
            code, data = request(self.port, "POST", "/api/tools/browser/webmcp.execute_tool/execute", {
                "site": "http://localhost:3000", "tool": "local_time", "input": {},
            }, timeout=10)
        finally:
            os.environ.pop("OLLAMA_WEBMCP_TIMEOUT", None)
        self.assertEqual(code, 200)
        self.assertFalse(data.get("ok"))
        self.assertIn("no extension result", data.get("error", ""))
        self.assertNotIn("dry_run", data)

    def test_result_for_unknown_job_is_error(self):
        code, data = request(self.port, "POST", "/api/webmcp/result", {
            "id": "deadbeefdeadbeef", "result": "x",
        })
        self.assertEqual(code, 404)

    def test_computer_still_dry_run(self):
        code, data = request(self.port, "POST", "/api/tools/computer/list_apps/execute", {})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))

    def test_unregistered_error_lists_registered_tools(self):
        code, data = request(self.port, "POST", "/api/tools/browser/webmcp.execute_tool/execute", {
            "site": "https://example.com", "tool": "made_up_tool", "input": {},
        })
        self.assertEqual(code, 400)
        self.assertIn("list_tools", data.get("error", ""))
        self.assertIn("did not register", data.get("error", ""))
        names = [(r["site"], r["tool"]) for r in data.get("registered", [])]
        self.assertIn(("http://localhost:3000", "local_echo"), names)
        self.assertIn(("http://localhost:3000", "local_time"), names)

    def test_computer_status_reports_dry_run_here(self):
        code, data = request(self.port, "GET", "/api/computer/status")
        self.assertEqual(code, 200)
        self.assertEqual(data.get("mode"), "dry_run")
        self.assertTrue(data.get("dry_run"))
        self.assertFalse(data.get("real_requested"))


if __name__ == "__main__":
    unittest.main()
