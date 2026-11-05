# Cua: generic browser and computer control

## What cua is

Cua is a plugin for generic control, built from scratch in this seed. It is modelled on the pattern ChatGPT uses for its Chrome and Computer plugins, where a single tool layer can open a tab, read tab state, open an app, click at coordinates, and type text. It is not a copy of OpenAI code, and it does not use any OpenAI package.

Cua has seven tools: get_state, list_tabs, create_tab, get_tab, open_app, click, and type_text.

## What cua is not

Cua is not WebMCP. WebMCP only exposes tools a page itself registered, for sites the user allowed, so it cannot open google.com or any site that registered nothing. Cua does not need a page to register anything, because it talks to Chrome itself through the Chrome debugging port, and to Mac apps through the accessibility adapter.

Cua is also not a finished computer-use product. It has no screenshot tool, no accessibility tree, and no visual element search in this version. Click needs screen coordinates x and y, and type_text types into the app you name, after activating it. If you do not know the coordinates, cua cannot guess them.

## How to enable it

Enable cua in the Plugins page, the same as browser and computer. A mention in chat, such as @cua, picks an enabled plugin for one turn only. It does not enable a plugin by itself.

## Dry-run first

By default the seed server runs in dry-run mode. In dry-run mode, cua returns dry_run true for every tool, and no app is opened, no tab is opened, no click happens, and no text is typed. That is the safe way to test prompts and tool names. A dry-run result is never a real result, and the server says so in the result.

## Real mode on Mac

Real mode needs all three of these, on macOS only:

1. Start the seed server with OLLAMA_COMPUTER_USE_REAL=1.
2. Grant Accessibility permission to the app running the seed server, in System Settings, Privacy and Security, Accessibility, then restart the server. The first real System Events call is what triggers the Mac prompt, which is why dry-run never prompts.
3. For tab state, launch Chrome with the debugging port, for example from Terminal: open -a "Google Chrome" --args --remote-debugging-port=9222. Then list_tabs and get_tab can read tabs at 127.0.0.1:9222.

Without the debugging port, list_tabs and get_tab return a plain error naming the port, never a pretend tab. Create_tab then falls back to opening Chrome with the URL, and the result says plainly that it used that fallback and that tab state is unavailable without the port.

## Opening google.com

In dry-run mode, or with WebMCP alone, opening google.com will not work, and cua will say so. In Mac mode, with real mode on and Accessibility granted, ask: @cua create a tab for https://google.com. That uses create_tab, through the debugging port if it is reachable, or by opening Chrome with the URL if it is not.

Click and type_text need coordinates and an app name, for example app Google Chrome, x and y as integers. Risky actions need confirmation first, under the computer policy. A click or type with sensitive data, or an action classified as handoff or always confirm, returns confirmation_required and does not run.

## What is not proven here

This plugin was built and tested in a Linux sandbox, with no Chrome and no macOS. Dry-run behaviour, the manifest, the debugging port error, and the confirmation gate are proven by tests. Real Mac behaviour, including open_app, click, type_text, and tab control through the debugging port, is not proven here. It needs the Mac steps above, and must be checked on a Mac before it is claimed to work there.
