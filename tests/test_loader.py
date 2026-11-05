import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from plugins.loader import discover, load_plugin, PluginError  # noqa: E402
from plugins.registry import Registry  # noqa: E402


class LoaderTest(unittest.TestCase):
    def test_discover_four_plugins(self):
        plugins, errors = discover(os.path.join(ROOT, "plugins"))
        self.assertEqual(errors, {})
        self.assertEqual(sorted(plugins), ["browser", "computer", "cua", "skill-creator"])
        self.assertTrue(plugins["browser"]["tools"])

    def test_registry_enable_disable_and_tools(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            reg = Registry(os.path.join(ROOT, "plugins"), state)
            self.assertEqual(reg.enabled_tools(), [])
            self.assertTrue(reg.enable("browser"))
            self.assertFalse(reg.enable("nope"))
            tools = reg.enabled_tools()
            self.assertTrue(any(t["function"]["name"] == "browser.webmcp.list_tools" for t in tools))
            plugin, tool = reg.find_tool("browser", "webmcp.list_tools")
            self.assertIsNotNone(plugin)
            plugin, tool = reg.find_tool("computer", "list_apps")
            self.assertIsNone(plugin)
            self.assertTrue(reg.disable("browser"))
            self.assertEqual(reg.enabled_tools(), [])

    def test_bad_plugin_is_error_not_crash(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad-name!")
            os.makedirs(bad)
            with open(os.path.join(bad, "plugin.json"), "w") as f:
                f.write('{"name": "bad-name!", "description": "x", "tools": []}')
            with open(os.path.join(bad, "SKILL.md"), "w") as f:
                f.write("---\nname: bad-name!\ndescription: x\n---\nBody.\n")
            plugins, errors = discover(tmp)
            self.assertEqual(plugins, {})
            self.assertIn("bad-name!", errors)


if __name__ == "__main__":
    unittest.main()
