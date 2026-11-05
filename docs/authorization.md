# Authorization settings

Authorization settings is one place in Ollamapaca to grant, see, and
revoke tool, app, and site permissions. It lives on the Plugins page,
in the Authorization section, and it talks to the seed server on
127.0.0.1:11435 for computer status, allowed apps, allowed tools, and
allowed sites. If the seed server is not running, that section says
so plainly, and the plugin list, enable, disable, and chat still work.

## What it controls

- Computer access: whether the seed is in dry-run or real Mac mode,
  and whether real mode was requested. The Request computer access
  button tries a harmless System Events listing. If that succeeds,
  access appears granted. If it fails, the section shows the
  System Settings step and asks you to recheck after granting.
- Allowed apps: apps that computer app actions may open,
  click, or type into. Empty means no app restriction yet. Adding
  one app turns the restriction on, and any other app is refused
  with a plain error.
- Allowed tools: each tool for browser and computer, on or
  off. A tool set to off is refused with a 403 even if its plugin
  is enabled. A tool with no setting is allowed, as today.
- Allowed sites: sites with registered WebMCP tools, as seen by
  the seed. Localhost and 127.0.0.1 are auto-allowed in local mode.

## What it does not control

- macOS Accessibility itself is granted in System Settings, Privacy
  and Security, Accessibility, to the app running the seed server.
  Ollamapaca can only request and recheck it, not grant it itself.
  Granting in System Settings, then restarting the seed, then
  rechecking, is the only route.
- Risky actions still need confirmation in chat. Authorization
  settings must not bypass the confirmation gate, and it does not
  turn a handoff or always confirm action into an automatic allow.
- The Chrome popup is still the place that adds a remote site,
  because site permission lives in Chrome storage, not on the
  seed server. The Authorization section only lists sites that
  have already registered tools.

## How to grant computer access on Mac, step by step

1. Pull the fork and the seed after this change is pushed.
2. Enable browser and computer in the Plugins page.
3. Start the seed server on macOS with
   OLLAMA_COMPUTER_USE_REAL=1.
4. Open Authorization in the Plugins page and click Request
   computer access.
5. If macOS asks, or if the result says access is not granted,
   open System Settings, Privacy and Security, Accessibility,
   grant the app running the seed server, restart the seed.
6. Click Recheck in Authorization. It should show real mode,
   not dry-run.
7. Add Google Chrome to allowed apps, if you want the app
   restriction on, then ask, with a tool-capable model,
   @browser create a tab for https://google.com, and
   @computer open Chrome to open an app.

## Why fork enable and seed enable both matter

Enabling a plugin in the fork app enables it on the fork server
on 11434, which is what lists tools for chat. Enabling it on the
seed server on 11435 is a separate step, and execution is refused
with a 403 if the seed has not enabled it. They are not synced
yet, and this document does not claim they are. Until they are
synced, check both: the fork Plugins page for listing, and the
seed authorization endpoint for execution. The Authorization
section shows seed enabled plugins, so you can spot a mismatch.

## Limits, stated plainly

This sandbox is Linux. Accessibility, real Mac control, Chrome
tab control, and the macOS permission prompt cannot be proven
here. All of that is unproven on Mac until the steps above are
run on a Mac, with a screenshot of the Authorization section
showing real mode and a granted result.
