# Ollama Plugin Seed

An open source seed for adding Codex-style plugin capability to Ollama, with a Chrome plugin using WebMCP and a Computer Use feature matching OpenAI's, for use with open source models.

This seed is not a full copy of Ollama, and it is not a copy of OpenAI's ChatGPT extension or its @oai/sky package. It is a small, working base that other people can use to add plugins and skills to Ollama, and a documented path to apply it to a real Ollama fork.

## What it does
- Loads plugins from folders, each with a plugin.json manifest and a SKILL.md skill, validated on load
- Serves a Plugins admin page at http://127.0.0.1:11435, with tabs for Plugins, Skills, and Installed, and enable and disable controls
- Exposes enabled plugin tools in Ollama chat tool shape, so they can be passed to Ollama /api/chat as tool definitions
- Discovers page-declared WebMCP tools through a Chrome extension, only for sites the user allowed, and registers them with the local plugin server
- Provides a Computer Use adapter that is dry-run by default, with a confirmation policy for risky actions, and a gated macOS adapter for real use

## Quick start
```
python3 scripts/run_server.py
```
Open http://127.0.0.1:11435, enable the browser plugin, and check:
```
curl http://127.0.0.1:11435/api/plugins
curl http://127.0.0.1:11435/api/tools
```
Run tests:
```
python3 -m unittest discover -s tests -v
```
Load the Chrome extension unpacked from chrome-extension/, allow a site in the popup, and visit a page that registers WebMCP tools. The extension only forwards tools from allowed sites, and it never forwards cookies, passwords, or page content.

To use plugin tools with Ollama, run Ollama on its usual port 11434, take the tool definitions from /api/tools on this server, pass them in a /api/chat request, execute the returned tool calls through this server, and return the results as tool messages. See docs/ollama-chat-flow.md.

## What it does not do
- It does not copy OpenAI code, the ChatGPT browser extension, or @oai/sky. Computer Use here is an open adapter with the same confirmation categories, not the same implementation.
- It does not give generic control of arbitrary pages. WebMCP only exposes tools a page registered. Arbitrary sites need a separate DOM and tab layer, which is not in this seed.
- It does not run computer actions live by default. Seed execution is dry-run, and computer actions that need confirmation return confirmation_required instead of running.
- It does not include Ollama's model runners. Do not touch llama/ or ml/ code when applying this seed to a real fork.

## Adding a plugin
See docs/adding-a-plugin.md. In short: create plugins/your-name/ with plugin.json and SKILL.md, run scripts/validate_skill.py on it, restart the server, and enable it in the Plugins page. A plugin that fails validation is listed under errors and does not hide the other plugins.

## Applying this to a real Ollama fork
See docs/upstream-integration.md for the exact patch points in ollama/ollama: a new plugins/ package, routes in server/routes.go, tool types in api/types.go, a CLI group in cmd/, and the Plugins page host decision. The seed's server-served admin page is the cross-platform choice. The desktop app page in app/ is a later, platform-gated phase.

## Licence
MIT, for this seed's code. Ollama's own source is also MIT, but model weights and bundled native dependencies carry separate licences, so MIT for source does not licence every model a user pulls.
