async function currentSite() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs[0] || !tabs[0].url) return { site: "", tabId: null };
  try { return { site: new URL(tabs[0].url).origin, tabId: tabs[0].id }; } catch (e) { return { site: "", tabId: null }; }
}
function isLocalSite(site) {
  return site === "http://localhost" || site.startsWith("http://localhost:") ||
    site === "http://127.0.0.1" || site.startsWith("http://127.0.0.1:");
}
async function renderStatus() {
  const el = document.getElementById("status");
  try {
    const r = await fetch("http://127.0.0.1:11435/api/browser/status");
    const s = await r.json();
    el.className = "ok";
    el.textContent = s.connected ? "Connected to the local plugin executor on 127.0.0.1:11435." : "Executor is running, waiting for this extension to connect.";
  } catch (e) {
    el.className = "bad";
    el.textContent = "The local plugin executor is not running on 127.0.0.1:11435. Open Ollamapaca, or run python3 scripts/run_server.py in the ollama-plugin-seed folder.";
  }
}
async function render() {
  const data = await chrome.storage.local.get(["browserControl"]);
  const control = document.getElementById("control");
  control.checked = data.browserControl !== false;
  control.onchange = () => chrome.storage.local.set({ browserControl: control.checked });
  renderStatus();
  const { site, tabId } = await currentSite();
  document.getElementById("site").textContent = site ? (isLocalSite(site) ? "Allowed: " + site + " (local, automatic)" : "Site: " + site) : "No site available.";
  document.getElementById("allow").onclick = async () => {
    const d = await chrome.storage.local.get("allowedSites");
    const allowed = d.allowedSites || {};
    allowed[site] = true;
    await chrome.storage.local.set({ allowedSites: allowed });
    document.getElementById("site").textContent = "Allowed: " + site;
    if (tabId !== null) {
      try { await chrome.tabs.sendMessage(tabId, { type: "webmcp-rediscover" }); } catch (e) {}
    }
  };
  document.getElementById("deny").onclick = async () => {
    const d = await chrome.storage.local.get("allowedSites");
    const allowed = d.allowedSites || {};
    delete allowed[site];
    await chrome.storage.local.set({ allowedSites: allowed });
    document.getElementById("site").textContent = "Removed: " + site;
  };
}
render();
