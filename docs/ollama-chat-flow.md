# Using plugin tools with Ollama chat

Ollama already declares tools in /api/chat, but the client executes them. This seed fits that flow, it does not replace it.

1. Start Ollama on port 11434, and start this plugin server on port 11435.
2. Enable a plugin in the Plugins page, or with POST /api/plugins/{name}/enable.
3. Get tool definitions from GET /api/tools on the plugin server.
4. Send a /api/chat request to Ollama with those tools in the tools array, and a tool-capable model.
5. When Ollama returns tool_calls, execute each call through this plugin server, at POST /api/tools/{plugin}/{tool}/execute, with the call arguments.
6. If the server returns confirmation_required, stop and confirm with the user before proceeding. Do not retry the same call without that confirmation.
7. Return each result to Ollama as a message with role tool, then call /api/chat again for the model's next step.

For the OpenAI-compatible surface, the same tool definitions can be translated for /v1/chat/completions, as a second phase. That translation is not in this seed.
