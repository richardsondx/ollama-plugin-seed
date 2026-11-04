# Adding a plugin

## Steps
1. Create a folder plugins/your-name/, with your-name in lowercase letters, digits, and hyphens, under 64 characters.
2. Write plugin.json with name, description, version, and tools. Each tool needs a name, a description, and a parameters object schema.
3. Write SKILL.md with frontmatter name and description matching the folder and manifest, plus a body that changes decisions, not generic advice.
4. Run: python3 scripts/validate_skill.py plugins/your-name
5. Restart the plugin server, open the Plugins page, and enable your plugin.
6. Check /api/tools to see your tool definitions, and test execution in dry-run first.

## Rules
- A skill is data, not code. Do not put executable code in SKILL.md.
- A tool not in plugin.json is refused, even if the skill mentions it.
- A disabled plugin exposes no tools.
- Keep discovery cheap: name and description must say what the plugin does and when it applies, without an exhaustive capability list.
- For retrying or externally mutating workflows, define a stopping condition proportional to the risk, and say it in the skill.
- Approval to complete a task does not expand scope or execution permissions. A plugin must not claim a permission its manifest does not list.

## Example, minimal
plugins/hello/plugin.json:
```json
{
  "name": "hello",
  "description": "Say hello, for testing the plugin loader.",
  "version": "0.1.0",
  "tools": [
    {"name": "say_hello", "description": "Return a greeting.", "parameters": {"type": "object", "properties": {}}}
  ]
}
```
plugins/hello/SKILL.md:
```markdown
---
name: hello
description: Say hello, for testing the plugin loader.
---

# Hello

Use this skill only when a greeting is explicitly requested.
```
