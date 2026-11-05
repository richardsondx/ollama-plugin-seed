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
from server.plugin_server import (  # noqa: E402
    FALLBACK_OPEN_TTL_SECONDS,
    _norm_url,
    _urls_match,
    create_server,
)


def request(port, method, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
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


class ControlTest(unittest.TestCase):
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

    def test_press_key_dry_run_records(self):
        adapter = DryRunAdapter()
        result = adapter.press_key("Safari", "Enter")
        self.assertTrue(result["dry_run"])
        self.assertEqual(adapter.actions[-1], {"action": "press_key", "app": "Safari", "key": "Enter"})

    def test_press_key_via_server_dry_run(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/press_key/execute",
                             {"app": "Safari", "key": "Enter"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        request(self.port, "POST", "/api/plugins/computer/disable", {})

    def test_press_key_enter_dry_run_returns_state_and_press_once_note(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/press_key/execute",
                             {"app": "Safari", "key": "Enter"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        result = data.get("result", {})
        self.assertIn("state", result)
        self.assertIn("Dry-run", result["state"].get("text", ""))
        self.assertIn("state_note", result)
        self.assertIn("once", result["state_note"])
        self.assertIn("Do not press Enter again", result["state_note"])
        self.assertIn("no page load was checked", result["state_note"])
        self.assertIn("Do not press Enter again", data.get("note", ""))
        request(self.port, "POST", "/api/plugins/computer/disable", {})

    def test_press_key_non_enter_dry_run_returns_state_note(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/press_key/execute",
                             {"app": "Safari", "key": "Tab"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("dry_run"))
        self.assertIn("state", data.get("result", {}))
        self.assertIn("once", data.get("result", {}).get("state_note", ""))
        self.assertIn("no page load was checked", data.get("result", {}).get("state_note", ""))
        request(self.port, "POST", "/api/plugins/computer/disable", {})

    def test_press_key_unknown_key_is_an_error_not_a_success(self):
        request(self.port, "POST", "/api/plugins/computer/enable", {})
        code, data = request(self.port, "POST", "/api/tools/computer/press_key/execute",
                             {"app": "Safari"})
        self.assertEqual(code, 400)
        code, data = request(self.port, "POST", "/api/tools/computer/press_key/execute",
                             {"app": "Safari", "key": "F13"})
        self.assertEqual(code, 400)
        self.assertIn("Enter", data.get("error", ""))
        request(self.port, "POST", "/api/plugins/computer/disable", {})

    def test_create_tab_dry_run_twice_touches_nothing(self):
        request(self.port, "POST", "/api/plugins/browser/enable", {})
        for _ in range(2):
            code, data = request(self.port, "POST", "/api/tools/browser/create_tab/execute",
                                 {"url": "https://google.com"})
            self.assertEqual(code, 200)
            self.assertTrue(data.get("dry_run"))
            self.assertIn("no tab was opened", data.get("result", {}).get("note", ""))
        request(self.port, "POST", "/api/plugins/browser/disable", {})

    def test_url_matching_for_dedup(self):
        self.assertEqual(_norm_url("https://www.google.com/"), "google.com")
        self.assertTrue(_urls_match("google.com", "https://www.google.com/"))
        self.assertTrue(_urls_match("https://google.com", "google.com/search"))
        self.assertFalse(_urls_match("google.com", "https://yahoo.com/"))
        self.assertTrue(FALLBACK_OPEN_TTL_SECONDS >= 300)

    def test_fallback_open_dict_holds_previous_result(self):
        # The fallback dict itself is the dedup store: a second
        # lookup for the same normalised URL within the TTL must
        # find the first result, so the server does not open again.
        from server.plugin_server import Handler
        import time
        key = _norm_url("https://google.com")
        result = {"route": "open -a Google Chrome, debugging port unreachable",
                  "url": "https://google.com"}
        Handler.fallback_opens[key] = (time.time(), result)
        prev = Handler.fallback_opens.get(key)
        self.assertIsNotNone(prev)
        self.assertLess(time.time() - prev[0], FALLBACK_OPEN_TTL_SECONDS)
        self.assertEqual(prev[1]["url"], "https://google.com")
        Handler.fallback_opens.pop(key, None)

    def test_non_object_body_returns_plain_400(self):
        code, data = request(self.port, "POST", "/api/tools/computer/list_apps/execute",
                             raw=b"[1, 2, 3]")
        self.assertEqual(code, 400)
        self.assertIn("JSON object", data.get("error", ""))

    def test_tool_descriptions_carry_the_new_guidance(self):
        with open(os.path.join(ROOT, "plugins", "computer", "plugin.json")) as f:
            computer = json.load(f)
        by_name = {t["name"]: t["description"] for t in computer["tools"]}
        self.assertIn("press_key", by_name)
        self.assertIn("press_key", by_name["type_text"])
        self.assertIn("Enter", by_name["type_text"])
        self.assertIn("once", by_name["press_key"])
        self.assertIn("Do not press Enter again", by_name["press_key"])
        self.assertIn("Do not press Enter again", by_name["type_text"])
        self.assertIn("Do not guess coordinates", by_name["click"])
        self.assertIn("100, 100", by_name["click"])
        with open(os.path.join(ROOT, "plugins", "browser", "plugin.json")) as f:
            browser = json.load(f)
        browser_by_name = {t["name"]: t["description"] for t in browser["tools"]}
        self.assertIn("do not call create_tab again", browser_by_name["create_tab"])
        self.assertIn("Do not poll", browser_by_name["get_tab"])


if __name__ == "__main__":
    unittest.main()
