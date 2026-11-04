// Page script, MAIN world. WebMCP lives in the page world
// (document.modelContext), so this file is loaded as a declared
// MAIN world content script in manifest.json, not injected as an
// inline script. Inline injection is blocked by Content Security
// Policy on strict sites, while a declared content script is not
// subject to the page CSP. This script only reads tools the page
// itself registered. It never reads cookies, passwords, or storage.
async function ollamaDiscover() {
  try {
    if (!document.modelContext || !document.modelContext.getTools) {
      window.postMessage({ type: "OLLAMA_WEBMCP", tools: [], available: false }, location.origin);
      return;
    }
    var tools = await document.modelContext.getTools();
    window.postMessage({
      type: "OLLAMA_WEBMCP",
      available: true,
      tools: tools.map(function (t) {
        return { name: t.name, description: t.description, inputSchema: t.inputSchema, origin: t.origin };
      })
    }, location.origin);
  } catch (e) {
    window.postMessage({ type: "OLLAMA_WEBMCP", tools: [], available: false, error: String(e) }, location.origin);
  }
}

// postMessage creates a "message" event, not a custom event named
// after the message type, so execute and rediscover must be handled
// here. The old listener for "OLLAMA_WEBMCP_EXECUTE" as an event
// type never fired, which would have stalled every real page tool.
window.addEventListener("message", async function (event) {
  if (event.source !== window || event.origin !== location.origin || !event.data) return;
  if (event.data.type === "OLLAMA_WEBMCP_DISCOVER") {
    ollamaDiscover();
    return;
  }
  if (event.data.type !== "OLLAMA_WEBMCP_EXECUTE") return;
  var detail = event.data.detail || {};
  try {
    if (!document.modelContext || !document.modelContext.getTools) {
      window.postMessage({ type: "OLLAMA_WEBMCP_RESULT", id: detail.id, error: "WebMCP is not available on this page" }, location.origin);
      return;
    }
    var tools = await document.modelContext.getTools();
    var tool = tools.find(function (t) { return t.name === detail.name; });
    if (!tool) {
      window.postMessage({ type: "OLLAMA_WEBMCP_RESULT", id: detail.id, error: "tool not found" }, location.origin);
      return;
    }
    var result = await document.modelContext.executeTool(tool, detail.input || {});
    window.postMessage({ type: "OLLAMA_WEBMCP_RESULT", id: detail.id, result: result }, location.origin);
  } catch (e) {
    window.postMessage({ type: "OLLAMA_WEBMCP_RESULT", id: detail.id, error: String(e) }, location.origin);
  }
});

ollamaDiscover();
