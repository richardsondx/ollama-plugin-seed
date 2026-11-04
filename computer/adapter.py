"""Computer Use adapter: dry-run by default, macOS best-effort second.

This is an open replacement, not a copy of @oai/sky. It does not
claim sky compatibility, and it does not bundle any proprietary
package. The dry-run adapter is the default, and it is what the
tests use: it records actions, returns a fake app state, and never
touches the operating system.

The macOS adapter is gated: it only runs on darwin, only when
OLLAMA_COMPUTER_USE_REAL=1 is set, and it uses AppleScript through
System Events, which requires Accessibility permission. If any of
those conditions is missing, it raises instead of silently falling
back to a different mechanism.
"""
import os
import platform
import subprocess


class DryRunAdapter:
    def __init__(self):
        self.actions = []

    def list_apps(self):
        return [
            {"id": "com.google.Chrome", "displayName": "Google Chrome", "isRunning": False},
            {"id": "com.apple.TextEdit", "displayName": "TextEdit", "isRunning": False},
        ]

    def get_app_state(self, app):
        return {
            "app": app,
            "screenshot": None,
            "text": "Dry-run app state for %s. No real app was touched." % app,
        }

    def click(self, app, element_index=None, x=None, y=None):
        self.actions.append({"action": "click", "app": app, "element_index": element_index, "x": x, "y": y})
        return {"ok": True, "dry_run": True}

    def type_text(self, app, text):
        self.actions.append({"action": "type_text", "app": app, "text": text})
        return {"ok": True, "dry_run": True}


class MacAdapter:
    def __init__(self):
        if platform.system() != "Darwin":
            raise RuntimeError("MacAdapter requires macOS")
        if os.environ.get("OLLAMA_COMPUTER_USE_REAL") != "1":
            raise RuntimeError("MacAdapter requires OLLAMA_COMPUTER_USE_REAL=1")

    def _osascript(self, script):
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("osascript failed: %s" % result.stderr.strip())
        return result.stdout.strip()

    def list_apps(self):
        out = self._osascript('tell application "System Events" to get name of every process')
        names = [n.strip() for n in out.split(",") if n.strip()]
        return [{"displayName": n, "isRunning": True} for n in names]

    def get_app_state(self, app):
        # Best-effort only: AppleScript does not give a full
        # accessibility tree in one call. The seed returns what it
        # can prove, and labels the rest as unavailable, rather
        # than inventing an element list.
        return {
            "app": app,
            "screenshot": None,
            "text": "macOS app state is limited in this seed. Use the Chrome plugin for browser work, and the dry-run adapter for tests.",
        }
