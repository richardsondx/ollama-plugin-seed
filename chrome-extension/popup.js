async function currentSite() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs[0] || !tabs[0].url) return "";
  try { return new URL(tabs[0].url).origin; } catch (e) { return ""; }
}
async function render() {
  const site = await currentSite();
  document.getElementById("site").textContent = site ? "Site: " + site : "No site available.";
  document.getElementById("allow").onclick = async () => {
    const data = await chrome.storage.local.get("allowedSites");
    const allowed = data.allowedSites || {};
    allowed[site] = true;
    await chrome.storage.local.set({ allowedSites: allowed });
    document.getElementById("site").textContent = "Allowed: " + site;
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
