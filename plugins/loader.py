"""Plugin loader for the Ollama plugin seed.

A plugin is a folder with:
  plugin.json  manifest, with name, description, version, tools, allowlist
  SKILL.md     Codex-style skill, frontmatter name and description

A skill is data, not code. The loader validates the manifest and the
skill frontmatter, and refuses a plugin whose name, tool list, or
skill does not match. It never executes plugin code on load.

Tools are expressed in the same shape Ollama already uses for chat
tools: name, description, and a JSON Schema parameters object. That
means enabled plugin tools can be passed to Ollama /api/chat as
api.Tool definitions without changing Ollama's tool type.
"""
import json
import os
import re

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class PluginError(ValueError):
    pass


def parse_frontmatter(text):
    """Return (frontmatter dict, body). Frontmatter is YAML-like, but
    this seed parses only the simple key: value lines it needs, so it
    has no YAML dependency. Complex values are not supported."""
    if not text.startswith("---\n"):
        raise PluginError("SKILL.md does not start with frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise PluginError("SKILL.md frontmatter is not closed")
    raw = text[4:end]
    data = {}
    for line in raw.splitlines():
        if ":" not in line or line.startswith(" ") or line.startswith("\t"):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, text[end + 4:].lstrip("\n")


def load_plugin(path):
    manifest_path = os.path.join(path, "plugin.json")
    skill_path = os.path.join(path, "SKILL.md")
    if not os.path.exists(manifest_path):
        raise PluginError("missing plugin.json in %s" % path)
    if not os.path.exists(skill_path):
        raise PluginError("missing SKILL.md in %s" % path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    name = manifest.get("name", "")
    if not NAME_RE.match(name):
        raise PluginError("invalid plugin name: %r" % name)
    if os.path.basename(os.path.normpath(path)) != name:
        raise PluginError("folder name does not match plugin name: %s" % name)
    if not manifest.get("description"):
        raise PluginError("plugin %s has no description" % name)
    tools = manifest.get("tools", [])
    if not isinstance(tools, list):
        raise PluginError("plugin %s tools must be a list" % name)
    for tool in tools:
        if not tool.get("name") or not tool.get("description"):
            raise PluginError("plugin %s has a tool without name or description" % name)
        params = tool.get("parameters", {})
        if not isinstance(params, dict) or params.get("type") != "object":
            raise PluginError("tool %s parameters must be an object schema" % tool.get("name"))
    with open(skill_path, encoding="utf-8") as f:
        frontmatter, _body = parse_frontmatter(f.read())
    if frontmatter.get("name") != name:
        raise PluginError("SKILL.md name does not match plugin name in %s" % name)
    if not frontmatter.get("description"):
        raise PluginError("SKILL.md for %s has no description" % name)
    manifest["path"] = path
    manifest["skill"] = frontmatter
    return manifest


def discover(root):
    """Return (plugins dict, errors dict). Errors are recorded, not
    raised, so one bad plugin cannot hide the rest of the list."""
    plugins = {}
    errors = {}
    if not os.path.isdir(root):
        return plugins, {"root": "plugins directory not found: %s" % root}
    for entry in sorted(os.listdir(root)):
        path = os.path.join(root, entry)
        if entry.startswith(".") or entry == "__pycache__":
            continue
        if not os.path.isdir(path):
            continue
        try:
            plugin = load_plugin(path)
            plugins[plugin["name"]] = plugin
        except (PluginError, json.JSONDecodeError, OSError) as exc:
            errors[entry] = str(exc)
    return plugins, errors
