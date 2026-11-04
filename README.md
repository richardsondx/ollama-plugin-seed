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

## Set it up with your agent: copy and paste this prompt

Copy everything in the block below, paste it into your agent, and let the agent do the setup. Change only the model name and the site you want to allow, if you need to.

```
Set up the Ollama Plugin Seed for me, end to end, and prove each step works before moving on.

Use this repo: https://github.com/richardsondx/ollama-plugin-seed
If it is already on this machine, use the local copy and do not re-clone it.

Steps, in order:
1. Check python3 is available, then run the tests: python3 -m unittest discover -s tests -v
   Stop and report the failure if any test fails. Do not weaken a test to make it pass.
2. Start the plugin server: python3 scripts/run_server.py
   It must serve on http://127.0.0.1:11435. Check http://127.0.0.1:11435/api/plugins lists 3 plugins: browser, computer, and skill-creator.
3. Enable the browser plugin, then check http://127.0.0.1:11435/api/tools returns its tools.
   Do not enable a plugin I did not name, and do not run a live computer action. Computer actions stay dry-run unless I explicitly approve a real one.
4. Set up the Chrome extension, with my help for the Chrome steps only:
   - Tell me, in exact steps, how to load the chrome-extension/ folder unpacked in Chrome, at chrome://extensions, with Developer mode on.
   - Wait for me to confirm it is loaded. Do not claim it is loaded before I confirm.
   - Then tell me how to allow one site in the extension popup, and wait for me to name that site. Only forward tools from sites I allow. Never read or share cookies, passwords, local storage, or page content.
   - Note: the extension only lists tools a page itself registered with WebMCP. It does not give generic control of a page that did not register tools.
5. Connect it to Ollama:
   - Check Ollama is running on its usual port 11434. If it is not running, tell me how to start it and stop there, do not install or change Ollama for me.
   - Use a tool-capable model. If I did not name one, ask me to pick one, and suggest one you can verify is installed.
   - Take the tool definitions from http://127.0.0.1:11435/api/tools, pass them in an Ollama /api/chat request, execute any returned tool calls through the plugin server, and return the results as tool messages. See docs/ollama-chat-flow.md in the repo.
6. Prove it with one real check: list the plugins, enable one, and show its tools. Then stop.

Rules for the whole setup:
- Do not push, deploy, post, send, pay, or delete anything, and do not change Ollama model runners.
- Do not copy OpenAI code, the ChatGPT extension, or any proprietary computer control package.
- If a step fails, stop at that step, show the exact error, and tell me what would unblock it. Do not skip the step and claim success.
- At the end, give me a short checklist: what works, what is still manual, and the exact URLs to open: the Plugins page at http://127.0.0.1:11435, and Ollama at http://127.0.0.1:11434.
```

If your agent asks which model to use, pick a tool-capable model you have installed, such as a Llama 3.1, Qwen 2.5 or 3, or Mistral class model. If your agent asks which site to allow in Chrome, name only a site you trust, and only after you have loaded the extension yourself.

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
