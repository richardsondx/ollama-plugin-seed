async function currentSite() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs[0] || !tabs[0].url) return { site: "", tabId: null };
  try { return { site: new URL(tabs[0].url).origin, tabId: tabs[0].id }; } catch (e) { return { site: "", tabId: null }; }
}
function isLocalSite(site) {
  return site === "http://localhost" || site.startsWith("http://localhost:") ||
    site === "http://127.0.0.1" || site.startsWith("http://127.0.0.1:");
}
async function render() {
  const { site, tabId } = await currentSite();
  const localNote = document.getElementById("localnote");
  if (isLocalSite(site) && localNote) localNote.style.display = "block";
  document.getElementById("site").textContent = site ? (isLocalSite(site) ? "Allowed: " + site + " (local, automatic)" : "Site: " + site) : "No site available.";
  document.getElementById("allow").onclick = async () => {
    const data = await chrome.storage.local.get("allowedSites");
    const allowed = data.allowedSites || {};
    allowed[site] = true;
    await chrome.storage.local.set({ allowedSites: allowed });
    document.getElementById("site").textContent = "Allowed: " + site;
    // Re-discover tools on the tab now, so allowing does not need a page reload.
    if (tabId !== null) {
      try { await chrome.tabs.sendMessage(tabId, { type: "webmcp-rediscover" }); } catch (e) {}
    }
  };
  document.getElementById("deny").onclick = async () => {
    const data = await chrome.storage.local.get("allowedSites");
    const allowed = data.allowedSites || {};
    delete allowed[site];
    await chrome.storage.local.set({ allowedSites: allowed });
    document.getElementById("site").textContent = "Removed: " + site;
  };
}
render();
