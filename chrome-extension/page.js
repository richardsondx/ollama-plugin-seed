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

window.addEventListener("OLLAMA_WEBMCP_EXECUTE", async function (event) {
  try {
    if (!document.modelContext || !document.modelContext.getTools) {
      window.postMessage({ type: "OLLAMA_WEBMCP_RESULT", id: event.detail.id, error: "WebMCP is not available on this page" }, location.origin);
      return;
    }
    var tools = await document.modelContext.getTools();
    var tool = tools.find(function (t) { return t.name === event.detail.name; });
    if (!tool) {
      window.postMessage({ type: "OLLAMA_WEBMCP_RESULT", id: event.detail.id, error: "tool not found" }, location.origin);
      return;
    }
    var result = await document.modelContext.executeTool(tool, event.detail.input || {});
    window.postMessage({ type: "OLLAMA_WEBMCP_RESULT", id: event.detail.id, result: result }, location.origin);
  } catch (e) {
    window.postMessage({ type: "OLLAMA_WEBMCP_RESULT", id: event.detail.id, error: String(e) }, location.origin);
  }
});

ollamaDiscover();
