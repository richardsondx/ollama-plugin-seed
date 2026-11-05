"""Plugin registry: enable, disable, and tool listing.

State is a small JSON file, separate from the plugin folders, so
enabling a plugin never edits the plugin itself. The registry
enforces the allowlist from the OpenPresence pattern: a tool that
is not listed in the plugin manifest is refused before execution,
and a disabled plugin exposes no tools.
"""
import json
import os

from plugins.loader import discover


class Registry:
    def __init__(self, plugins_root, state_path=None):
        self.plugins_root = plugins_root
        self.state_path = state_path
        self.plugins, self.errors = discover(plugins_root)
        self.enabled = set()
        # Authorization allowlists. Old state files contain only
        # "enabled" and must still load, so both lists default empty.
        # Empty allowed_apps means no app restriction yet, not a
        # block on everything. A tool is allowed unless it is
        # explicitly set to false in allowed_tools.
        self.allowed_apps = set()
        self.allowed_tools = {}
        if state_path and os.path.exists(state_path):
            try:
                with open(state_path, encoding="utf-8") as f:
                    data = json.load(f)
                for name in data.get("enabled", []):
                    if name in self.plugins:
                        self.enabled.add(name)
                for name in data.get("allowed_apps", []) or []:
                    if isinstance(name, str) and name:
                        self.allowed_apps.add(name)
                raw_tools = data.get("allowed_tools", {}) or {}
                if isinstance(raw_tools, dict):
                    for key, value in raw_tools.items():
                        if isinstance(key, str) and isinstance(value, bool):
                            # Drop settings for plugins that no longer
                            # exist, so a removed plugin such as cua
                            # can never keep offering tools through
                            # an old state file. Enabled names above
                            # are filtered the same way.
                            if key.split(".", 1)[0] in self.plugins:
                                self.allowed_tools[key] = value
            except (json.JSONDecodeError, OSError):
                self.enabled = set()
                self.allowed_apps = set()
                self.allowed_tools = {}

    def save(self):
        if not self.state_path:
            return
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({
                "enabled": sorted(self.enabled),
                "allowed_apps": sorted(self.allowed_apps),
                "allowed_tools": dict(sorted(self.allowed_tools.items())),
            }, f, indent=2)

    def set_allowed_app(self, app, allowed):
        if allowed:
            self.allowed_apps.add(app)
        else:
            self.allowed_apps.discard(app)
        self.save()

    def is_app_allowed(self, app):
        if not self.allowed_apps:
            return True
        return app in self.allowed_apps

    def set_allowed_tool(self, plugin_name, tool_name, allowed):
        self.allowed_tools["%s.%s" % (plugin_name, tool_name)] = bool(allowed)
        self.save()

    def is_tool_allowed(self, plugin_name, tool_name):
        return self.allowed_tools.get(
            "%s.%s" % (plugin_name, tool_name), True)

    def list_plugins(self):
        out = []
        for name in sorted(self.plugins):
            plugin = self.plugins[name]
            out.append({
                "name": name,
                "description": plugin["description"],
                "version": plugin.get("version", "0.1.0"),
                "enabled": name in self.enabled,
                "skills": [name],
                "tools": [t["name"] for t in plugin.get("tools", [])],
            })
        return out

    def list_skills(self):
        out = []
        for name in sorted(self.plugins):
            plugin = self.plugins[name]
            out.append({
                "name": name,
                "description": plugin["skill"]["description"],
                "plugin": name,
                "enabled": name in self.enabled,
            })
        return out

    def enable(self, name):
        if name not in self.plugins:
            return False
        self.enabled.add(name)
        self.save()
        return True

    def disable(self, name):
        if name not in self.plugins:
            return False
        self.enabled.discard(name)
        self.save()
        return True

    def enabled_tools(self):
        """Ollama chat tool definitions for enabled plugins only."""
        tools = []
        for name in sorted(self.enabled):
            plugin = self.plugins[name]
            for tool in plugin.get("tools", []):
                tools.append({
                    "plugin": name,
                    "type": "function",
                    "function": {
                        "name": "%s.%s" % (name, tool["name"]),
                        "description": tool["description"],
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    },
                })
        return tools

    def find_tool(self, plugin_name, tool_name):
        """Return (plugin, tool) only if the plugin is enabled and the
        tool is in its manifest. Otherwise return (None, None)."""
        if plugin_name not in self.enabled:
            return None, None
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return None, None
        for tool in plugin.get("tools", []):
            if tool["name"] == tool_name:
                return plugin, tool
        return None, None
