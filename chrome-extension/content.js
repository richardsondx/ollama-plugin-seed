// Content script, isolated world, relay only. WebMCP lives in the
// page world (document.modelContext), which is handled by page.js,
// a declared MAIN world content script. This file does not inject
// any script, inline or otherwise, because inline injection is
// blocked by Content Security Policy on strict sites. It only
// relays window messages from page.js to the background worker,
// and execute messages from the background back to page.js.
// It never reads cookies, passwords, or storage.
(function () {
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
    if (msg && msg.type === "webmcp-rediscover") {
      window.postMessage({ type: "OLLAMA_WEBMCP_DISCOVER" }, location.origin);
    }
  });
})();
