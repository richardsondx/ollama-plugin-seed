"""Chrome DevTools Protocol helper, standard library only.

This module talks to a Chrome instance the user launched with
remote debugging on, at http://127.0.0.1:9222. It does not launch
Chrome by itself, and it does not read cookies, passwords, or
storage. It lists tabs and creates a tab, nothing more.

If the debugging port is unreachable, every function raises a
plain error naming the port. Callers must surface that error, and
must never invent a tab id, title, or URL in its place.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

CDP_BASE = "http://127.0.0.1:9222"


def _get(path, timeout=5):
    try:
        with urllib.request.urlopen(CDP_BASE + path, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RuntimeError(
            "Chrome debugging port is unreachable at %s. "
            "Launch Chrome with --remote-debugging-port=9222 and try again. "
            "Details: %s" % (CDP_BASE, exc)
        )


def list_tabs():
    data = _get("/json/list")
    tabs = []
    for entry in data:
        if entry.get("type") not in ("page", None):
            continue
        tabs.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "url": entry.get("url"),
            "type": entry.get("type", "page"),
        })
    return tabs


def create_tab(url):
    if not url:
        raise ValueError("url is required to create a tab")
    query = urllib.parse.urlencode({"url": url})
    try:
        req = urllib.request.Request(
            "%s/json/new?%s" % (CDP_BASE, query), method="PUT")
        with urllib.request.urlopen(req, timeout=10) as resp:
            entry = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RuntimeError(
            "Chrome debugging port is unreachable at %s. "
            "Launch Chrome with --remote-debugging-port=9222 and try again. "
            "Details: %s" % (CDP_BASE, exc)
        )
    return {
        "id": entry.get("id"),
        "title": entry.get("title"),
        "url": entry.get("url"),
        "type": entry.get("type", "page"),
    }


def get_tab(tab_id=None, url=None):
    tabs = list_tabs()
    for tab in tabs:
        if tab_id and tab.get("id") == tab_id:
            return tab
        if url and tab.get("url") and url in tab["url"]:
            return tab
    raise RuntimeError("No Chrome tab matched id %r or url %r." % (tab_id, url))
