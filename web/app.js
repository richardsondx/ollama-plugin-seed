async function get(path) {
  const r = await fetch(path);
  return r.json();
}
async function post(path) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  return r.json();
}
function card(title, body, button) {
  const d = document.createElement("div");
  d.className = "card";
  d.innerHTML = "<h3>" + title + "</h3>" + body + (button || "");
  return d;
}
async function showPlugins() {
  const data = await get("/api/plugins");
  const view = document.getElementById("view");
  view.innerHTML = "";
  if (data.errors && Object.keys(data.errors).length) {
    view.appendChild(card("Plugins with errors", "<p>" + JSON.stringify(data.errors) + "</p>"));
  }
  data.plugins.forEach(function (p) {
    const btn = "<p><button class='action' data-name='" + p.name + "' data-action='" + (p.enabled ? "disable" : "enable") + "'>" + (p.enabled ? "Disable" : "Enable") + "</button></p>";
    view.appendChild(card(p.name + (p.enabled ? " - enabled" : ""), "<p>" + p.description + "</p><p><small>Version " + p.version + ". Tools: " + p.tools.join(", ") + "</small></p>", btn));
  });
  view.querySelectorAll("button.action").forEach(function (b) {
    b.onclick = async function () {
      await post("/api/plugins/" + b.dataset.name + "/" + b.dataset.action);
      showPlugins();
    };
  });
}
async function showSkills() {
  const data = await get("/api/plugins/skills");
  const view = document.getElementById("view");
  view.innerHTML = "";
  data.skills.forEach(function (s) {
    view.appendChild(card(s.name, "<p>" + s.description + "</p><p><small>Plugin: " + s.plugin + ". Enabled: " + s.enabled + "</small></p>"));
  });
}
async function showInstalled() {
  const data = await get("/api/plugins");
  const view = document.getElementById("view");
  view.innerHTML = "";
  data.plugins.filter(function (p) { return p.enabled; }).forEach(function (p) {
    view.appendChild(card(p.name, "<p>" + p.description + "</p><p><small>Tools: " + p.tools.join(", ") + "</small></p>"));
  });
  if (!data.plugins.some(function (p) { return p.enabled; })) {
    view.appendChild(card("Nothing installed yet", "<p>Enable a plugin on the Plugins tab.</p>"));
  }
}
function setActive(id) {
  document.querySelectorAll("nav button").forEach(function (b) { b.classList.remove("active"); });
  document.getElementById(id).classList.add("active");
}
document.getElementById("tab-plugins").onclick = function () { setActive("tab-plugins"); showPlugins(); };
document.getElementById("tab-skills").onclick = function () { setActive("tab-skills"); showSkills(); };
document.getElementById("tab-installed").onclick = function () { setActive("tab-installed"); showInstalled(); };
showPlugins();
