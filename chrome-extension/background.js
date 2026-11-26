// Background service worker for the Ollamapaca Chrome extension.
//
// Two jobs:
//
// 1. Browser control. The local plugin executor (127.0.0.1:11435)
//    queues browser actions (open a tab, navigate, read the page,
//    click, type, press a key, scroll). This worker long-polls for
//    them, runs them in your real Chrome with chrome.tabs,
//    chrome.scripting and chrome.debugger, and posts the result
//    back. No --remote-debugging-port is needed. You can switch this
//    off in the popup.
//
// 2. WebMCP. It forwards page-declared WebMCP tools to the executor
//    for sites you allowed, and runs them on request.
//
// It never reads cookies, saved passwords or storage, and it never
// returns the value of a password field.

const SERVER = "http://127.0.0.1:11435";
const VERSION = chrome.runtime.getManifest().version;
const POLL_WAIT_SECONDS = 15;

// ------------------------------------------------------------------
// settings

async function getSettings() {
  const data = await chrome.storage.local.get(["allowedSites", "browserControl"]);
  return {
    allowedSites: data.allowedSites || {},
    // Browser control is on unless the user switched it off.
    browserControl: data.browserControl !== false,
  };
}

function isLocalSite(site) {
  return !!site && (site === "http://localhost" || site.startsWith("http://localhost:") ||
    site === "http://127.0.0.1" || site.startsWith("http://127.0.0.1:"));
}

function isAllowed(allowed, site) {
  return !!allowed[site] || isLocalSite(site);
}

// ------------------------------------------------------------------
// WebMCP relay (unchanged behaviour)

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type === "webmcp-discovered" && sender.tab) {
    (async () => {
      const { allowedSites } = await getSettings();
      if (!isAllowed(allowedSites, msg.site)) return;
      await fetch(SERVER + "/api/webmcp/tools", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site: msg.site, tools: msg.tools }),
      }).catch(() => {});
    })();
  }
});

const pendingWebmcp = new Map();

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "webmcp-result" && msg.id) {
    const waiting = pendingWebmcp.get(msg.id);
    if (waiting) waiting({ result: msg.result, error: msg.error });
  }
});

async function runWebmcpJob(job) {
  const tabs = await chrome.tabs.query({});
  const tab = tabs.find((t) => {
    try { return t.url && new URL(t.url).origin === job.site; } catch (e) { return false; }
  });
  if (!tab) return { error: "no tab open for site " + job.site };
  const outcome = new Promise((resolve) => {
    const timer = setTimeout(() => {
      pendingWebmcp.delete(job.id);
      resolve({ error: "no result from page within 20 seconds" });
    }, 20000);
    pendingWebmcp.set(job.id, (o) => {
      clearTimeout(timer);
      pendingWebmcp.delete(job.id);
      resolve(o);
    });
  });
  try {
    await chrome.tabs.sendMessage(tab.id, { type: "webmcp-execute", id: job.id, name: job.tool, input: job.input || {} });
  } catch (e) {
    pendingWebmcp.delete(job.id);
    return { error: String(e) };
  }
  return outcome;
}

// ------------------------------------------------------------------
// tab helpers

function tabInfo(tab) {
  return { tab_id: tab.id, title: tab.title || "", url: tab.url || tab.pendingUrl || "", active: !!tab.active, window_id: tab.windowId };
}

function normalizeUrl(url) {
  const text = String(url || "").trim();
  if (!text) throw new Error("url is required");
  if (/^[a-z][a-z0-9+.-]*:/i.test(text)) return text;
  if (/^(localhost|127\.0\.0\.1)(:|\/|$)/i.test(text)) return "http://" + text;
  return "https://" + text;
}

function sameUrl(a, b) {
  const norm = (u) => String(u || "").toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/+$/, "");
  return !!a && !!b && norm(a) === norm(b);
}

// The tab the agent is working in: the one it opened or used last,
// if it still exists, otherwise the active tab of the focused window.
let agentTabId = null;

async function targetTab(tabId) {
  if (tabId !== undefined && tabId !== null && tabId !== "") {
    const id = Number(tabId);
    try { return await chrome.tabs.get(id); } catch (e) { throw new Error("no tab with id " + tabId + ". Call list_tabs to see open tabs."); }
  }
  if (agentTabId !== null) {
    try { return await chrome.tabs.get(agentTabId); } catch (e) { agentTabId = null; }
  }
  let tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true, windowType: "normal" });
  if (!tabs.length) tabs = await chrome.tabs.query({ active: true });
  if (!tabs.length) throw new Error("no open tab. Use create_tab with a url first.");
  return tabs[0];
}

function waitForLoad(tabId, timeoutMs = 15000) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      chrome.tabs.onUpdated.removeListener(listener);
      clearTimeout(timer);
      // Give scripts a moment to render.
      setTimeout(resolve, 400);
    };
    const listener = (id, info) => {
      if (id === tabId && info.status === "complete") finish();
    };
    const timer = setTimeout(finish, timeoutMs);
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then((t) => { if (t.status === "complete") finish(); }).catch(finish);
  });
}

// After a click or key press, wait for a navigation if one starts.
async function settle(tabId) {
  await new Promise((r) => setTimeout(r, 500));
  try {
    const t = await chrome.tabs.get(tabId);
    if (t.status === "loading") await waitForLoad(tabId);
  } catch (e) { /* tab closed */ }
}

async function runInTab(tabId, func, args = []) {
  let results;
  try {
    results = await chrome.scripting.executeScript({ target: { tabId }, func, args, world: "ISOLATED" });
  } catch (e) {
    const msg = String(e && e.message || e);
    if (/cannot be scripted|Cannot access|chrome:\/\/|extensions gallery/i.test(msg)) {
      throw new Error("this page cannot be controlled by extensions (" + msg + "). Navigate to a normal web page first.");
    }
    throw new Error(msg);
  }
  const r = results && results[0];
  if (!r) throw new Error("the page did not return a result");
  if (r.result && r.result.__error) throw new Error(r.result.__error);
  return r.result;
}

// ------------------------------------------------------------------
// page functions, run inside the page (isolated world)

function pageSnapshot(maxElements, maxText) {
  const SELECTOR = [
    "a[href]", "button", "input:not([type=hidden])", "textarea", "select", "summary",
    "[role=button]", "[role=link]", "[role=checkbox]", "[role=radio]", "[role=tab]",
    "[role=menuitem]", "[role=option]", "[role=switch]", "[role=combobox]",
    "[role=textbox]", "[role=searchbox]", "[contenteditable='']", "[contenteditable=true]",
    "[onclick]",
  ].join(",");
  const clean = (s, n) => String(s || "").replace(/\s+/g, " ").trim().slice(0, n);
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const st = getComputedStyle(el);
    return st.visibility !== "hidden" && st.display !== "none" && Number(st.opacity) > 0.05;
  };
  const labelOf = (el) => {
    const aria = el.getAttribute("aria-label");
    if (aria) return aria;
    const by = el.getAttribute("aria-labelledby");
    if (by) {
      const t = by.split(/\s+/).map((id) => document.getElementById(id)).filter(Boolean).map((n) => n.innerText).join(" ");
      if (t.trim()) return t;
    }
    if (el.labels && el.labels.length) return Array.from(el.labels).map((l) => l.innerText).join(" ");
    if (el.placeholder) return el.placeholder;
    const text = el.innerText || el.textContent;
    if (text && text.trim()) return text;
    return el.getAttribute("title") || el.getAttribute("alt") || el.getAttribute("name") ||
      (el.querySelector && el.querySelector("img[alt]") ? el.querySelector("img[alt]").alt : "") || "";
  };
  const roleOf = (el) => {
    const role = el.getAttribute("role");
    if (role) return role;
    const tag = el.tagName.toLowerCase();
    if (tag === "a") return "link";
    if (tag === "input") {
      const t = (el.type || "text").toLowerCase();
      if (["button", "submit", "reset", "image"].includes(t)) return "button";
      if (t === "checkbox" || t === "radio") return t;
      return "input";
    }
    if (tag === "select") return "select";
    if (tag === "textarea") return "textarea";
    if (el.isContentEditable) return "editable";
    return tag;
  };
  if (typeof window.__opacaNext !== "number") window.__opacaNext = 1;
  const all = Array.from(document.querySelectorAll(SELECTOR)).filter(visible);
  const vh = window.innerHeight;
  const inView = (el) => { const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < vh; };
  // Elements on screen first, then the rest of the page.
  all.sort((a, b) => (inView(b) ? 1 : 0) - (inView(a) ? 1 : 0));
  const lines = [];
  for (const el of all.slice(0, maxElements)) {
    let ref = el.getAttribute("data-opaca-ref");
    if (!ref) {
      ref = String(window.__opacaNext++);
      el.setAttribute("data-opaca-ref", ref);
    }
    const role = roleOf(el);
    let line = "[" + ref + "] " + role;
    const name = clean(labelOf(el), 80);
    if (name) line += ' "' + name + '"';
    const tag = el.tagName.toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") {
      const type = (el.type || "").toLowerCase();
      if (tag === "input" && type && !["text", "button", "submit"].includes(type)) line += " type=" + type;
      if (type === "checkbox" || type === "radio") line += el.checked ? " checked" : " unchecked";
      else if (type !== "password" && el.value) line += ' value="' + clean(el.value, 60) + '"';
    }
    if (tag === "a") {
      const href = el.getAttribute("href") || "";
      if (href && !href.startsWith("javascript:")) line += " -> " + clean(href, 80);
    }
    if (el.disabled) line += " disabled";
    if (!inView(el)) line += " (offscreen)";
    lines.push(line);
  }
  const text = clean(document.body ? document.body.innerText : "", maxText);
  return {
    title: document.title,
    url: location.href,
    elements: lines,
    elementCount: all.length,
    text,
    scroll: { y: Math.round(scrollY), height: Math.round(document.documentElement.scrollHeight), viewport: vh },
  };
}

function pageLocate(ref, text) {
  const clean = (s) => String(s || "").replace(/\s+/g, " ").trim().toLowerCase();
  let el = null;
  if (ref !== undefined && ref !== null && ref !== "") {
    el = document.querySelector('[data-opaca-ref="' + String(ref).replace(/[^0-9]/g, "") + '"]');
    if (!el) return { __error: "no element with ref " + ref + " on this page. Call read_page again to get fresh refs." };
  } else if (text) {
    const want = clean(text);
    const cands = Array.from(document.querySelectorAll("a,button,input,textarea,select,summary,label,[role],[onclick],[contenteditable]"));
    el = cands.find((c) => clean(c.innerText || c.value || c.getAttribute("aria-label") || c.placeholder) === want) ||
      cands.find((c) => clean(c.innerText || c.value || c.getAttribute("aria-label") || c.placeholder).includes(want));
    if (!el) return { __error: 'no clickable element with text "' + text + '". Call read_page to see the elements.' };
  } else {
    return { __error: "give a ref from read_page (or the element's text)" };
  }
  el.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
  const r = el.getBoundingClientRect();
  const name = String(el.innerText || el.value || el.getAttribute("aria-label") || el.placeholder || el.tagName).replace(/\s+/g, " ").trim().slice(0, 60);
  return { x: r.left + r.width / 2, y: r.top + r.height / 2, name, tag: el.tagName.toLowerCase() };
}

function pageClickFallback(ref, text) {
  const clean = (s) => String(s || "").replace(/\s+/g, " ").trim().toLowerCase();
  let el = ref ? document.querySelector('[data-opaca-ref="' + String(ref).replace(/[^0-9]/g, "") + '"]') : null;
  if (!el && text) {
    const want = clean(text);
    el = Array.from(document.querySelectorAll("a,button,input,[role],[onclick]")).find((c) => clean(c.innerText || c.value || c.getAttribute("aria-label")).includes(want));
  }
  if (!el) return { __error: "element not found" };
  el.click();
  return { ok: true };
}

function pageFocus(ref, clear) {
  let el = null;
  if (ref !== undefined && ref !== null && ref !== "") {
    el = document.querySelector('[data-opaca-ref="' + String(ref).replace(/[^0-9]/g, "") + '"]');
    if (!el) return { __error: "no element with ref " + ref + ". Call read_page again to get fresh refs." };
  } else {
    // No ref: use the focused field, or the first visible search or
    // text box, which is what "type into the search box" means.
    const editable = (n) => n && (n.isContentEditable || /^(INPUT|TEXTAREA)$/.test(n.tagName));
    const shown = (n) => { const r = n.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    el = editable(document.activeElement) ? document.activeElement : null;
    if (!el) {
      el = Array.from(document.querySelectorAll("input[type=search],input[name=q],input[name=search],input[role=searchbox],input[role=combobox],input:not([type]),input[type=text],textarea")).find(shown) || null;
    }
    if (!el) return { __error: "no text field found. Call read_page and pass the ref of the field." };
    if (!el.getAttribute("data-opaca-ref")) {
      if (typeof window.__opacaNext !== "number") window.__opacaNext = 1;
      el.setAttribute("data-opaca-ref", String(window.__opacaNext++));
    }
  }
  el.scrollIntoView({ block: "center", behavior: "instant" });
  el.focus();
  if (clear) {
    if ("value" in el && typeof el.select === "function") {
      try { el.select(); } catch (e) { /* not selectable */ }
    } else if (el.isContentEditable) {
      const range = document.createRange();
      range.selectNodeContents(el);
      const sel = getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    }
  }
  return { focused: document.activeElement === el, tag: el.tagName.toLowerCase(), ref: el.getAttribute("data-opaca-ref") };
}

function pageSetValueFallback(ref, text, clear) {
  const el = document.querySelector('[data-opaca-ref="' + String(ref).replace(/[^0-9]/g, "") + '"]');
  if (!el) return { __error: "element not found" };
  el.focus();
  if (el.isContentEditable) {
    if (clear) el.textContent = "";
    document.execCommand("insertText", false, text);
    return { ok: true };
  }
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  setter.call(el, (clear ? "" : el.value) + text);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return { ok: true };
}

function pageScroll(direction, amount) {
  const h = window.innerHeight * (amount || 0.8);
  const map = { down: [0, h], up: [0, -h], right: [h, 0], left: [-h, 0] };
  if (direction === "top") window.scrollTo(0, 0);
  else if (direction === "bottom") window.scrollTo(0, document.documentElement.scrollHeight);
  else window.scrollBy(...(map[direction] || map.down));
  return { y: Math.round(scrollY), height: Math.round(document.documentElement.scrollHeight) };
}

function pageText(maxText) {
  return { title: document.title, url: location.href, text: String(document.body ? document.body.innerText : "").replace(/\n{3,}/g, "\n\n").trim().slice(0, maxText) };
}

// ------------------------------------------------------------------
// trusted input through chrome.debugger

const attached = new Set();
const detachTimers = new Map();

chrome.debugger.onDetach.addListener((source) => {
  if (source.tabId !== undefined) attached.delete(source.tabId);
});

async function withDebugger(tabId, fn) {
  if (!attached.has(tabId)) {
    await chrome.debugger.attach({ tabId }, "1.3");
    attached.add(tabId);
  }
  clearTimeout(detachTimers.get(tabId));
  try {
    return await fn((method, params) => chrome.debugger.sendCommand({ tabId }, method, params || {}));
  } finally {
    // Detach after a quiet period, so the "is debugging this browser"
    // bar goes away when the agent is done.
    detachTimers.set(tabId, setTimeout(() => {
      attached.delete(tabId);
      chrome.debugger.detach({ tabId }).catch(() => {});
    }, 20000));
  }
}

const KEYS = {
  Enter: { code: "Enter", keyCode: 13, text: "\r" },
  Tab: { code: "Tab", keyCode: 9 },
  Escape: { code: "Escape", keyCode: 27 },
  Backspace: { code: "Backspace", keyCode: 8 },
  Delete: { code: "Delete", keyCode: 46 },
  Space: { key: " ", code: "Space", keyCode: 32, text: " " },
  ArrowUp: { code: "ArrowUp", keyCode: 38 },
  ArrowDown: { code: "ArrowDown", keyCode: 40 },
  ArrowLeft: { code: "ArrowLeft", keyCode: 37 },
  ArrowRight: { code: "ArrowRight", keyCode: 39 },
  PageUp: { code: "PageUp", keyCode: 33 },
  PageDown: { code: "PageDown", keyCode: 34 },
  Home: { code: "Home", keyCode: 36 },
  End: { code: "End", keyCode: 35 },
};

async function pressKey(tabId, key) {
  const def = KEYS[key];
  if (!def) throw new Error("unsupported key " + key + ". Use one of: " + Object.keys(KEYS).join(", "));
  const base = { key: def.key || key, code: def.code, windowsVirtualKeyCode: def.keyCode, nativeVirtualKeyCode: def.keyCode };
  await withDebugger(tabId, async (send) => {
    await send("Input.dispatchKeyEvent", { type: def.text ? "keyDown" : "rawKeyDown", ...base, text: def.text, unmodifiedText: def.text });
    await send("Input.dispatchKeyEvent", { type: "keyUp", ...base });
  });
}

async function clickAt(tabId, x, y) {
  await withDebugger(tabId, async (send) => {
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
    await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  });
}

// ------------------------------------------------------------------
// actions

const SNAPSHOT_ELEMENTS = 50;
const SNAPSHOT_TEXT = 1500;

function formatSnapshot(tab, snap, header) {
  const lines = [];
  if (header) lines.push(header, "");
  lines.push("Tab " + tab.id + ": " + (snap.title || "(no title)"));
  lines.push("URL: " + snap.url);
  lines.push("");
  if (snap.elements.length) {
    lines.push("Interactive elements (use the number in [ ] as ref for click and type):");
    lines.push(...snap.elements);
    if (snap.elementCount > snap.elements.length) lines.push("... " + (snap.elementCount - snap.elements.length) + " more, scroll to see them");
  } else {
    lines.push("No interactive elements found.");
  }
  lines.push("", "Page text:", snap.text || "(empty)");
  return lines.join("\n");
}

async function snapshotResult(tab, header) {
  const fresh = await chrome.tabs.get(tab.id);
  const snap = await runInTab(tab.id, pageSnapshot, [SNAPSHOT_ELEMENTS, SNAPSHOT_TEXT]);
  return { ...tabInfo(fresh), text: formatSnapshot(fresh, snap, header) };
}

const actions = {
  async list_tabs() {
    const tabs = await chrome.tabs.query({ windowType: "normal" });
    const list = tabs.map(tabInfo);
    const text = list.map((t) => "Tab " + t.tab_id + (t.active ? " (active)" : "") + ": " + t.title + " - " + t.url).join("\n");
    return { tabs: list, text: text || "No tabs open." };
  },

  async create_tab(args) {
    const url = normalizeUrl(args.url);
    const tabs = await chrome.tabs.query({});
    const existing = tabs.find((t) => sameUrl(t.url, url));
    let tab;
    let header;
    if (existing) {
      tab = await chrome.tabs.update(existing.id, { active: true });
      await chrome.windows.update(existing.windowId, { focused: true });
      header = "A tab with this URL was already open, switched to it.";
    } else {
      tab = await chrome.tabs.create({ url, active: true });
      await waitForLoad(tab.id);
      header = "Opened " + url + " in a new tab.";
    }
    agentTabId = tab.id;
    return snapshotResult(tab, header);
  },

  async navigate(args) {
    const url = normalizeUrl(args.url);
    const tab = await targetTab(args.tab_id);
    await chrome.tabs.update(tab.id, { url, active: true });
    await waitForLoad(tab.id);
    agentTabId = tab.id;
    return snapshotResult(tab, "Navigated to " + url + ".");
  },

  async go_back(args) {
    const tab = await targetTab(args.tab_id);
    await chrome.tabs.goBack(tab.id);
    await settle(tab.id);
    return snapshotResult(tab, "Went back.");
  },

  async switch_tab(args) {
    const tab = await targetTab(args.tab_id);
    await chrome.tabs.update(tab.id, { active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
    agentTabId = tab.id;
    return snapshotResult(tab, "Switched to tab " + tab.id + ".");
  },

  async close_tab(args) {
    const tab = await targetTab(args.tab_id);
    await chrome.tabs.remove(tab.id);
    if (agentTabId === tab.id) agentTabId = null;
    return { tab_id: tab.id, text: "Closed tab " + tab.id + " (" + (tab.title || tab.url) + ")." };
  },

  async get_tab(args) {
    if (args.url && !args.tab_id) {
      const tabs = await chrome.tabs.query({});
      const t = tabs.find((x) => (x.url || "").includes(args.url));
      if (!t) throw new Error("no tab matches " + args.url);
      return { tab: tabInfo(t), text: "Tab " + t.id + ": " + t.title + " - " + t.url };
    }
    const tab = await targetTab(args.tab_id);
    return { tab: tabInfo(tab), text: "Tab " + tab.id + ": " + tab.title + " - " + tab.url };
  },

  async read_page(args) {
    const tab = await targetTab(args.tab_id);
    agentTabId = tab.id;
    return snapshotResult(tab);
  },

  async get_text(args) {
    const tab = await targetTab(args.tab_id);
    const r = await runInTab(tab.id, pageText, [Math.min(Number(args.max_chars) || 12000, 40000)]);
    return { ...tabInfo(tab), text: "Tab " + tab.id + ": " + r.title + "\nURL: " + r.url + "\n\n" + r.text };
  },

  async click(args) {
    const tab = await targetTab(args.tab_id);
    agentTabId = tab.id;
    const loc = await runInTab(tab.id, pageLocate, [args.ref ?? null, args.text ?? null]);
    let how = "trusted click";
    try {
      await clickAt(tab.id, loc.x, loc.y);
    } catch (e) {
      // DevTools open on the tab, or a page that refuses debugging.
      await runInTab(tab.id, pageClickFallback, [args.ref ?? null, args.text ?? null]);
      how = "script click";
    }
    await settle(tab.id);
    return snapshotResult(tab, "Clicked " + loc.tag + ' "' + loc.name + '" (' + how + ").");
  },

  async type(args) {
    const tab = await targetTab(args.tab_id);
    agentTabId = tab.id;
    const text = String(args.text ?? "");
    const clear = args.clear !== false;
    const focus = await runInTab(tab.id, pageFocus, [args.ref ?? null, clear]);
    args.ref = focus.ref;
    try {
      await withDebugger(tab.id, async (send) => {
        if (clear) await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Backspace", code: "Backspace", windowsVirtualKeyCode: 8 }).then(() => send("Input.dispatchKeyEvent", { type: "keyUp", key: "Backspace", code: "Backspace", windowsVirtualKeyCode: 8 }));
        if (text) await send("Input.insertText", { text });
      });
    } catch (e) {
      await runInTab(tab.id, pageSetValueFallback, [args.ref, text, clear]);
    }
    let header = 'Typed "' + text + '" into [' + args.ref + "].";
    if (args.submit) {
      await pressKey(tab.id, "Enter");
      await settle(tab.id);
      header += " Pressed Enter.";
    }
    return snapshotResult(tab, header);
  },

  async press_key(args) {
    const tab = await targetTab(args.tab_id);
    agentTabId = tab.id;
    const key = String(args.key || "");
    await pressKey(tab.id, key);
    await settle(tab.id);
    return snapshotResult(tab, "Pressed " + key + " once.");
  },

  async scroll(args) {
    const tab = await targetTab(args.tab_id);
    agentTabId = tab.id;
    await runInTab(tab.id, pageScroll, [String(args.direction || "down"), Number(args.amount) || 0.8]);
    await new Promise((r) => setTimeout(r, 300));
    return snapshotResult(tab, "Scrolled " + (args.direction || "down") + ".");
  },
};

async function runBrowserJob(job) {
  const { browserControl } = await getSettings();
  if (!browserControl) {
    return { error: "Browser control is switched off in the Ollamapaca Chrome extension popup." };
  }
  const fn = actions[job.action];
  if (!fn) return { error: "unknown browser action: " + job.action };
  try {
    return { result: await fn(job.args || {}) };
  } catch (e) {
    return { error: String(e && e.message || e) };
  }
}

// ------------------------------------------------------------------
// long-poll loop

let loopRunning = false;
// When the loop last made progress. A loop that has not moved for a
// while is stuck on a request that will never finish (after the Mac
// sleeps or the network changes), so a new loop replaces it.
let lastLoopTick = 0;
let loopGeneration = 0;
const STUCK_AFTER_MS = (POLL_WAIT_SECONDS + 30) * 1000;

// fetchWithTimeout aborts a request that hangs, so one dead
// connection can never stop the extension from polling again.
async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function postResult(path, body) {
  await fetchWithTimeout(SERVER + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => {});
}

async function pollOnce() {
  const { browserControl } = await getSettings();
  const url = SERVER + "/api/browser/next?wait=" + POLL_WAIT_SECONDS + "&version=" + encodeURIComponent(VERSION) + "&control=" + (browserControl ? "1" : "0");
  const response = await fetchWithTimeout(url, {}, (POLL_WAIT_SECONDS + 10) * 1000);
  if (!response.ok) throw new Error("status " + response.status);
  const data = await response.json();
  const job = data && data.job;
  if (!job) return;
  if (job.kind === "webmcp") {
    const outcome = await runWebmcpJob(job);
    await postResult("/api/webmcp/result", { id: job.id, result: outcome.result, error: outcome.error });
  } else {
    const outcome = await runBrowserJob(job);
    await postResult("/api/browser/result", { id: job.id, result: outcome.result, error: outcome.error });
  }
}

async function pollLoop() {
  if (loopRunning && Date.now() - lastLoopTick < STUCK_AFTER_MS) return;
  // Either no loop is running, or the running one is stuck. Start a
  // new one; the old one notices its generation changed and exits.
  const generation = ++loopGeneration;
  loopRunning = true;
  lastLoopTick = Date.now();
  try {
    while (generation === loopGeneration) {
      // An extension API call resets the service worker idle timer,
      // so Chrome keeps this worker alive while the loop runs.
      await chrome.runtime.getPlatformInfo();
      lastLoopTick = Date.now();
      try {
        await pollOnce();
      } catch (e) {
        // Executor not running yet, or the request timed out.
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
  } finally {
    if (generation === loopGeneration) loopRunning = false;
  }
}

// Restart the loop whenever Chrome wakes the worker.
chrome.alarms.create("ollamapaca-keepalive", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => pollLoop());
chrome.runtime.onStartup.addListener(() => pollLoop());
chrome.runtime.onInstalled.addListener(() => pollLoop());
pollLoop();
