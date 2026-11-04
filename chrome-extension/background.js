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
});

// Pending jobs waiting for a page result, keyed by job id.
// A result resolves the waiting job, and only then is it posted
// to the server. Nothing else is forwarded.
const pendingJobs = new Map();

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type === "webmcp-result" && msg.id) {
    const waiting = pendingJobs.get(msg.id);
    if (waiting) {
      waiting.resolve({ result: msg.result, error: msg.error });
    } else {
      chrome.storage.local.set({ ["webmcp-result-" + msg.id]: msg });
    }
  }
});

// Execute dispatch: a caller that knows a tab id (for example the
// plugin server client, via the extension popup or a future bridge)
// can ask the background worker to forward an execute message to
// that tab's content script, which relays it to the page that
// registered the tool.
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

async function postJobResult(job, outcome) {
  await fetch(SERVER + "/api/webmcp/result", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: job.id, result: outcome.result, error: outcome.error })
  }).catch(() => {});
}

function waitForJobResult(job) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      pendingJobs.delete(job.id);
      resolve({ error: "no result from page within 20 seconds" });
    }, 20000);
    pendingJobs.set(job.id, {
      resolve: (outcome) => {
        clearTimeout(timer);
        pendingJobs.delete(job.id);
        resolve(outcome);
      }
    });
  });
}

async function executeJob(job) {
  const tabs = await chrome.tabs.query({});
  let tab = null;
  for (const candidate of tabs) {
    if (!candidate.url) continue;
    try {
      if (new URL(candidate.url).origin === job.site) { tab = candidate; break; }
    } catch (e) { continue; }
  }
  if (!tab) {
    await postJobResult(job, { error: "no tab open for site " + job.site });
    return;
  }
  const resultPromise = waitForJobResult(job);
  try {
    await chrome.tabs.sendMessage(tab.id, {
      type: "webmcp-execute",
      id: job.id,
      name: job.tool,
      input: job.input || {}
    });
  } catch (e) {
    pendingJobs.delete(job.id);
    await postJobResult(job, { error: String(e) });
    return;
  }
  const outcome = await resultPromise;
  await postJobResult(job, outcome);
}

let polling = false;
async function pollQueue() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch(SERVER + "/api/webmcp/execute-queue");
    if (!response.ok) return;
    const data = await response.json();
    if (data && data.job) {
      await executeJob(data.job);
    }
  } catch (e) {
    // Server not running yet, or not reachable. Next poll retries.
  } finally {
    polling = false;
  }
}

setInterval(pollQueue, 2000);
pollQueue();
