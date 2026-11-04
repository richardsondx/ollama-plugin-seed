# Applying this seed to a real Ollama fork

Upstream: https://github.com/ollama/ollama, Go, MIT for its source, default branch main. Recheck file paths against a checkout before patching, because upstream moves.

## Patch points, in order
1. Add a plugins/ package to the fork, ported from plugins/loader.py and plugins/registry.py in this seed: loader, registry, manifest validation, enable and disable, and executor interface. Skills stay data, not code.
2. In server/routes.go, in GenerateRoutes, register plugin routes, for example GET /api/plugins, GET /api/plugins/skills, and POST /api/plugins/{name}/enable|disable, and wire enabled plugin tools into the ChatHandler path so they become api.Tool definitions for the model.
3. In api/types.go, add Plugin and Skill types only if plugin state must cross the API. ChatRequest.Tools itself does not need to change, because plugin tools already fit api.Tool.
4. In api/client.go, add client methods for the new plugin routes, only if clients need them.
5. In cmd/cmd.go, register a plugin command group, and add cmd/plugin.go with list, install, enable, and disable, following the existing Cobra pattern.
6. For the Plugins page, pick a host first. The seed uses a server-served admin page, which is cross-platform. The alternative is the app/ React SPA plus webview bindings, which is Windows and macOS gated and is the larger cost. Do not claim a web UI exists in upstream server/; it does not.
7. Add a tool executor, with a permission and confirmation policy. Ollama declares tools in /api/chat, but the client executes them today. A fork needs to decide where execution lives: in-process Go tools, local executables, or MCP servers over stdio or HTTP.

## Checks before reusing other work
- Verify the status of upstream PR ollama/ollama#13562, which proposes MCP support, against a checkout. A proposal is not evidence it is merged.
- Verify server/routes.go, server/images.go, and api/types.go against a checkout, not against secondary summaries.
- Do not touch llama/, ml/, mlx/, or runner code for a plugin seed.

## Fork steps, when approved separately
1. Fork ollama/ollama on GitHub, keeping it public to match upstream, or private if the owner chooses, with a note that upstream is MIT.
2. Clone the fork, copy this seed's plugins/, chrome-extension/, web/, and docs/ in, and apply the patch points above in a branch.
3. Run Ollama's own tests for the touched packages, plus this seed's tests, before any release.
4. Publish the seed as its own repo only if the owner wants a standalone base, separate from the full fork, and say so in the README so users do not confuse the two.
