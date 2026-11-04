// Content script, isolated world. WebMCP lives in the page world
// (document.modelContext), so this script injects a page script that
// runs in MAIN world, then relays results back by postMessage.
// The page script only reads tools the page itself registered. It
// never reads cookies, passwords, or storage.
(function () {
  var script = document.createElement("script");
  script.textContent = "(" + function () {
    async function discover() {
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
    discover();
  } + ")();";
  (document.head || document.documentElement).appendChild(script);
  script.remove();

  window.addEventListener("message", function (event) {
    if (event.source !== window || event.origin !== location.origin || !event.data || event.data.type !== "OLLAMA_WEBMCP") return;
    chrome.runtime.sendMessage({
      type: "webmcp-discovered",
      site: location.origin,
      tools: event.data.tools || [],
      available: !!event.data.available
    });
  });
  window.addEventListener("message", function (event) {
    if (event.source !== window || event.origin !== location.origin || !event.data || event.data.type !== "OLLAMA_WEBMCP_RESULT") return;
    chrome.runtime.sendMessage({ type: "webmcp-result", id: event.data.id, result: event.data.result, error: event.data.error });
  });
  chrome.runtime.onMessage.addListener(function (msg) {
    if (msg && msg.type === "webmcp-execute") {
      window.postMessage({ type: "OLLAMA_WEBMCP_EXECUTE", detail: msg }, location.origin);
    }
  });
})();
