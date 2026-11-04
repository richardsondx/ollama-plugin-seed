// Background service worker for the Ollama Chrome extension.
// It forwards page-discovered WebMCP tools to the local plugin
// server, only for sites the user allowed in the popup. It never
// forwards page content, cookies, or credentials. A page cannot
// add a plugin or a permission by registering a tool.
const SERVER = "http://127.0.0.1:11435";

async function allowedSites() {
  const data = await chrome.storage.local.get("allowedSites");
  return data.allowedSites || {};
}

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type === "webmcp-discovered" && sender.tab) {
    (async () => {
      const allowed = await allowedSites();
      if (!allowed[msg.site]) return;
      await fetch(SERVER + "/api/webmcp/tools", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site: msg.site, tools: msg.tools })
      }).catch(() => {});
    })();
  }
  if (msg.type === "webmcp-result") {
    chrome.storage.local.set({ ["webmcp-result-" + msg.id]: msg });
  }
});

// Execute dispatch: a caller that knows a tab id (for example the
// plugin server client, via the extension popup or a future bridge)
// can ask the background worker to forward an execute message to
// that tab's content script, which relays it to the page that
// registered the tool. This closes the loop the content script
// already listens for. It does not, by itself, wire the plugin
// server to the extension, which remains a documented gap.
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "execute-webmcp" && msg.tabId && msg.name) {
    chrome.tabs.sendMessage(msg.tabId, {
      type: "webmcp-execute",
      id: msg.id || "exec-1",
      name: msg.name,
      input: msg.input || {}
    });
    sendResponse({ dispatched: true });
  }
});
