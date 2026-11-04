# Architecture

## Layers, in order
1. Plugin folders, data only: plugin.json plus SKILL.md, validated on load.
2. Loader and registry: discovery, validation, enable and disable, and tool listing. A disabled plugin exposes no tools.
3. Plugin server: HTTP routes on port 11435, separate from Ollama on 11434, serving the admin UI and the tool API.
4. Chrome extension: discovers WebMCP tools in the page world, forwards them only for user-allowed sites, and executes them back in the page that registered them.
5. Computer adapter: dry-run by default, macOS gated by platform and by OLLAMA_COMPUTER_USE_REAL=1, with a confirmation policy in front of every computer action.
6. Ollama chat flow: the model returns tool calls, the client executes them through this server, and returns tool messages to Ollama. Ollama itself does not execute plugin code in this seed.

## Trust boundaries
- A plugin manifest is the allowlist. A tool not in the manifest is refused before execution, following the OpenPresence pattern of client-side refusal before a network call.
- Page content is data, never instructions. A WebMCP tool registration cannot add a plugin, a destination, or a permission.
- Third-party content is never permission for a computer action. Confirmations must explain the risk and the mechanism, and, for data transmission, what data goes where.
- No raw credentials are stored in plugin code. The plugin server runs on 127.0.0.1 only, and the extension talks to it on localhost only.

## What is not in the seed, on purpose
- No model runner, no llama.cpp binding, no MLX runner.
- No generic DOM clicker for arbitrary sites.
- No @oai/sky compatibility, no ChatGPT extension code, no OpenAI package.
- No automatic skill loading into model context. Skills are listed and enabled explicitly, and their bodies are read only when the skill applies.
