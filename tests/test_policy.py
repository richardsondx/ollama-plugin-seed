import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from computer.policy import classify  # noqa: E402
from computer.adapter import DryRunAdapter  # noqa: E402


class PolicyTest(unittest.TestCase):
    def test_handoff(self):
        self.assertEqual(classify("change_password_submit"), "handoff")
        self.assertEqual(classify("bypass_paywall"), "handoff")

    def test_always_confirm(self):
        self.assertEqual(classify("delete_data"), "always_confirm")
        self.assertEqual(classify("financial_transaction"), "always_confirm")
        self.assertEqual(classify("install_browser_extension"), "always_confirm")

    def test_preapproval(self):
        self.assertEqual(classify("login"), "preapproval_or_confirm")
        self.assertEqual(classify("login", preapproved=True), "no_confirmation")
        self.assertEqual(classify("upload_file", sensitive_data=True), "preapproval_or_confirm")

    def test_no_confirmation(self):
        self.assertEqual(classify("get_app_state"), "no_confirmation")
        self.assertEqual(classify("download_file"), "no_confirmation")

    def test_dry_run_never_touches_os(self):
        adapter = DryRunAdapter()
        state = adapter.get_app_state("Google Chrome")
        self.assertIn("Dry-run", state["text"])
        self.assertEqual(adapter.actions, [])
        adapter.click("Google Chrome", element_index=1)
        self.assertEqual(len(adapter.actions), 1)


if __name__ == "__main__":
    unittest.main()
