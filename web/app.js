async function get(path) {
  const r = await fetch(path);
  return r.json();
}
async function post(path) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  return r.json();
}
function esc(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function iconFor(name) {
  const icons = {
    browser: '<svg viewBox="0 0 48 48" width="100%" height="100%"><circle cx="24" cy="24" r="20" fill="#fff"/><path d="M24 4 A20 20 0 0 1 41.3 34 L24 24 Z" fill="#EA4335"/><path d="M41.3 34 A20 20 0 0 1 6.7 34 L24 24 Z" fill="#FBBC05"/><path d="M6.7 34 A20 20 0 0 1 24 4 L24 24 Z" fill="#34A853"/><circle cx="24" cy="24" r="10" fill="#4285F4" stroke="#fff" stroke-width="3"/></svg>',
    computer: '<svg viewBox="0 0 48 48" width="100%" height="100%"><defs><linearGradient id="cu" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38bdf8"/><stop offset="0.5" stop-color="#a78bfa"/><stop offset="1" stop-color="#f472b6"/></linearGradient></defs><rect x="2" y="2" width="44" height="44" rx="11" fill="url(#cu)"/><rect x="9" y="11" width="30" height="20" rx="3" fill="#fff"/><circle cx="14" cy="16" r="2" fill="#f43f5e"/><circle cx="20" cy="16" r="2" fill="#f59e0b"/><circle cx="26" cy="16" r="2" fill="#22c55e"/><rect x="13" y="21" width="14" height="3" rx="1.5" fill="#c4b5fd"/><rect x="13" y="26" width="9" height="2" rx="1" fill="#e5e7eb"/><path d="M30 33l5 2-2 5 2 2-2 1-2-2-2 3z" fill="#111"/><rect x="20" y="33" width="8" height="3" rx="1.5" fill="#fff"/></svg>',
    "skill-creator": '<svg viewBox="0 0 48 48" width="100%" height="100%"><rect x="4" y="4" width="40" height="40" rx="8" fill="#e9d5ff"/><path d="M18 14h12v6a3 3 0 0 1 6 0v6h-6a3 3 0 0 1 0 6v6H18v-6a3 3 0 0 1-6 0v-6h6a3 3 0 0 1 0-6v-6z" fill="#7c3aed"/></svg>',
    handover: '<svg viewBox="0 0 48 48" width="100%" height="100%"><rect x="4" y="4" width="40" height="40" rx="10" fill="#dbeafe"/><path d="M12 24h22M28 16l8 8-8 8" stroke="#2563eb" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };
  return icons[name] || icons["skill-creator"];
}
function toolNames(p) {
  if (!p.tools) return [];
  return p.tools.map(function (t) { return typeof t === "string" ? t : t.name; });
}
function examplesFor(p) {
  if (p.name === "browser") return ["Browser: test my checkout flow on localhost", "Browser: list the tools on the page I allowed"];
  if (p.name === "computer") return ["Computer: open my calendar and find a good time for a focus block", "Computer: list the apps I can control"];
  if (p.name === "skill-creator") return ["Skill: validate a new skill folder before I share it", "Skill: check a SKILL.md frontmatter name matches its folder"];
  return ["Use " + p.name + " from Ollama, locally only"];
}
let allPlugins = [];
let currentView = "plugins";
let selected = null;
function setActiveNav(view) {
  currentView = view;
  document.getElementById("nav-plugins").classList.toggle("active", view === "plugins");
  document.getElementById("nav-skills").classList.toggle("active", view === "skills");
}
function renderInstalled() {
  const el = document.getElementById("installed-list");
  const installed = allPlugins.filter(function (p) { return p.enabled; });
  el.innerHTML = installed.length ? installed.map(function (p) {
    return '<div class="side-item' + (selected && selected.name === p.name ? " active" : "") + '" data-name="' + esc(p.name) + '"><span class="icon">' + iconFor(p.name) + "</span>" + esc(p.name) + "</div>";
  }).join("") : '<div class="side-item">No plugins enabled yet</div>';
  el.querySelectorAll(".side-item[data-name]").forEach(function (d) {
    d.onclick = function () { showDetail(d.dataset.name); };
  });
}
function cardHtml(p) {
  const action = p.enabled ? "Disable" : "Enable";
  return '<div class="card" data-name="' + esc(p.name) + '"><span class="icon">' + iconFor(p.name) + '</span><div><h3>' + esc(p.name) + '</h3><p>' + esc(p.description) + '</p></div><button class="plus" data-enable="' + esc(p.name) + '">' + (p.enabled ? "✓" : "+") + "</button></div>";
}
async function showPlugins() {
  setActiveNav("plugins");
  selected = null;
  const data = await get("/api/plugins");
  allPlugins = data.plugins || [];
  const q = (document.getElementById("search").value || "").toLowerCase();
  const list = allPlugins.filter(function (p) { return !q || p.name.toLowerCase().includes(q) || p.description.toLowerCase().includes(q); });
  const view = document.getElementById("view");
  view.innerHTML = '<h1>Plugins</h1><p class="sub">Connect plugins to let Ollama work across your tools, locally only.</p><div class="tabs"><button class="active">Public</button><button>Personal</button></div><div class="grid">' + list.map(cardHtml).join("") + "</div>";
  view.querySelectorAll(".card").forEach(function (c) {
    c.onclick = function (e) { if (e.target.closest("button")) return; showDetail(c.dataset.name); };
  });
  view.querySelectorAll("button.plus").forEach(function (b) {
    b.onclick = async function () {
      const p = allPlugins.find(function (x) { return x.name === b.dataset.enable; });
      await post("/api/plugins/" + p.name + "/" + (p.enabled ? "disable" : "enable"));
      showPlugins();
    };
  });
  renderInstalled();
}
function showDetail(name) {
  const p = allPlugins.find(function (x) { return x.name === name; });
  if (!p) return showPlugins();
  selected = p;
  setActiveNav("plugins");
  const tools = toolNames(p);
  const view = document.getElementById("view");
  view.innerHTML = '<div class="detail-crumb">Plugins &gt; ' + esc(p.name) + '</div>'
    + '<div class="detail-head"><span class="icon">' + iconFor(p.name) + "</span><div><h2>" + esc(p.name) + "</h2><p>" + esc(p.description) + "</p></div>"
    + '<button class="btn" onclick="showPlugins()">Manage</button>'
    + '<button class="btn black" id="toggle-btn">' + (p.enabled ? "Disable" : "Enable") + "</button></div>"
    + '<div class="banner">' + examplesFor(p).map(function (e) { return '<div class="pill">' + esc(e) + " →</div>"; }).join("") + "</div>"
    + '<p>' + esc(p.description) + " Tools are listed only when the plugin is enabled, and only for sites and apps you allowed.</p>"
    + '<div class="section"><h3>Skills 1</h3>' + (p.skills || [p.name]).map(function (s) { const sn = typeof s === "string" ? s : s.name; return '<div class="row"><span class="icon">' + iconFor(p.name) + "</span><div><strong>" + esc(sn) + "</strong><p>" + esc(p.description) + "</p></div><span>›</span></div>"; }).join("") + "</div>"
    + '<div class="section"><h3>Tools</h3>' + (tools.length ? tools.map(function (t) { return '<div class="row"><div><strong>' + esc(t) + "</strong></div></div>"; }).join("") : "<p>No tools listed.</p>") + "</div>"
    + '<div class="section"><h3>Information</h3><table class="info"><tr><td>Developer</td><td>Ollama plugin seed, local only</td></tr><tr><td>Category</td><td>Productivity</td></tr><tr><td>Version</td><td>' + esc(p.version || "0.1.0") + "</td></tr><tr><td>Status</td><td>" + (p.enabled ? "Enabled" : "Not enabled") + "</td></tr></table></div>";
  document.getElementById("toggle-btn").onclick = async function () {
    await post("/api/plugins/" + p.name + "/" + (p.enabled ? "disable" : "enable"));
    const data = await get("/api/plugins");
    allPlugins = data.plugins || [];
    showDetail(p.name);
    renderInstalled();
  };
  renderInstalled();
}
async function showSkills() {
  setActiveNav("skills");
  selected = null;
  const data = await get("/api/plugins/skills");
  allPlugins = allPlugins.length ? allPlugins : (await get("/api/plugins")).plugins || [];
  const skills = data.skills || [];
  const view = document.getElementById("view");
  view.innerHTML = '<h1>Skills</h1><p class="sub">Extend Ollama with task-specific skills.</p><div class="grid">' + skills.map(function (s) {
    const name = typeof s === "string" ? s : s.name;
    const plugin = typeof s === "object" ? s.plugin : "";
    const enabled = typeof s === "object" ? s.enabled : false;
    const desc = typeof s === "object" && s.description ? s.description : (plugin ? "Skill from " + plugin : "");
    return '<div class="card"><span class="icon">' + iconFor(plugin || name) + "</span><div><h3>/" + esc(name) + "</h3><p>" + esc(desc) + "</p></div><span>" + (enabled ? "✓" : "") + "</span></div>";
  }).join("") + "</div>";
  renderInstalled();
}
document.getElementById("nav-plugins").onclick = showPlugins;
document.getElementById("nav-skills").onclick = showSkills;
document.getElementById("search").oninput = function () { if (currentView === "plugins") showPlugins(); };
showPlugins();
