# Cua is now internal, not a plugin

Cua was the internal engine for generic browser and computer control, built from scratch in this seed. It is modelled on the pattern ChatGPT uses for its Chrome and Computer plugins, where one tool layer can open a tab, read tab state, open an app, click at coordinates, and type text. It is not a copy of OpenAI code, and it does not use any OpenAI package.

That engine is still here, in cua/cdp.py for Chrome tabs and in computer/adapter.py for Mac apps. What changed is the surface: there is no cua plugin to enable, and no @cua to type. Use @browser for tabs and @computer for apps.

## Where each tool now lives

- @browser, list_tabs: Chrome tabs through the debugging port at 127.0.0.1:9222.
- @browser, create_tab: open a Chrome tab with a URL, through the debugging port first, or by opening Chrome with the URL on macOS if the port is unreachable, with the route stated in the result.
- @browser, get_tab: one Chrome tab by tab id or URL substring, through the debugging port.
- @browser, webmcp.list_tools and webmcp.execute_tool: unchanged, page tools a site registered, through the Chrome extension. These are different from tab tools. A page tool only runs what a page registered. A tab tool opens a tab directly.
- @computer, list_apps and get_app_state: apps and app state, as before.
- @computer, get_state: mode, running apps, and Chrome tabs if the debugging port answers, else tabs unavailable with the port instruction.
- @computer, open_app: open a Mac app by name.
- @computer, click: click at screen coordinates x and y in a Mac app.
- @computer, type_text: type text into a Mac app, never logged.

## How to use it

Enable browser and computer in the Plugins page. A mention in chat, such as @browser or @computer, picks an enabled plugin for one turn only. It does not enable a plugin by itself. Do not enable cua, there is nothing to enable under that name any more, and an old state file that still lists cua is ignored, it offers no tools.

## Dry-run first

By default the seed server runs in dry-run mode. In dry-run mode, tab and app tools return dry_run true, and no tab is opened, no app is opened, no click happens, and no text is typed. That is the safe way to test prompts and tool names. A dry-run result is never a real result, and the server says so in the result.

## Real mode on Mac

Real mode needs all three of these, on macOS only:

1. Start the seed server with OLLAMA_COMPUTER_USE_REAL=1.
2. Grant Accessibility permission to the app running the seed server, in System Settings, Privacy and Security, Accessibility, then restart the server. The first real System Events call is what triggers the Mac prompt, which is why dry-run never prompts.
3. For tab state, launch Chrome with the debugging port, for example from Terminal: open -a "Google Chrome" --args --remote-debugging-port=9222. Then list_tabs and get_tab can read tabs at 127.0.0.1:9222.

Without the debugging port, list_tabs and get_tab return a plain error naming the port, never a pretend tab. Create_tab then falls back to opening Chrome with the URL, and the result says plainly that it used that fallback and that tab state is unavailable without the port.

## Opening google.com

In dry-run mode, or with WebMCP alone, opening google.com will not work, and the browser plugin will say so. In Mac mode, with real mode on and Accessibility granted, ask: @browser create a tab for https://google.com. That uses create_tab, through the debugging port if it is reachable, or by opening Chrome with the URL if it is not. To open an app instead, ask: @computer open Chrome.

Click and type_text need coordinates and an app name, for example app Google Chrome, x and y as integers. Risky actions need confirmation first, under the computer policy. A click or type with sensitive data, or an action classified as handoff or always confirm, returns confirmation_required and does not run.

## Transcript, step 1

A browser or computer turn is shown as a collapsible summary, not as a tool log. Step names, in order:

- computer.open_app: Open app name
- browser.create_tab: Open URL in a new tab
- computer.type_text: Type in app name (typed text is never shown in a step name)
- computer.press_key: Press key in app name
- computer.get_app_state and computer.get_state: Check app name, or Check computer
- browser.get_tab: Check tab
- browser.list_tabs: Check tabs
- computer.list_apps: List apps
- computer.click: Click in app name
- browser.webmcp.list_tools: List page tools
- browser.webmcp.execute_tool: Run page tool name

The summary header shows "Working" while the turn is streaming, and "Worked for Xs" once streaming ends, where X is the real elapsed time measured in the browser from when the user message was sent in that session to when the final answer arrived. Turns loaded from history, where no start time was observed, show the steps with no timer, rather than a made-up time. Raw tool names, argument JSON, and result JSON are hidden behind each step's Details toggle.

Intent and final answer are model behaviour, driven by the plugin descriptions: before the first tool call, the model should state in one plain sentence what it is about to do, and after a successful open, answer in one sentence naming the app, the site, and the URL as a link, and stop. If a model does not follow that wording, the step names and timer still work, but the intent sentence will not appear. That is a model behaviour gap, not a UI bug.

What is not in step 1: a live window thumbnail. That needs screen capture in step 2, with Screen Recording permission on Mac and image tool results in chat, and it is not built here. This summary never claims to show a live window.

## What is not proven here

This change was built and tested in a Linux sandbox, with no Chrome and no macOS. Dry-run behaviour, the manifests, the debugging port error, and the confirmation gate are proven by tests. Real Mac behaviour, including open_app, click, type_text, and tab control through the debugging port, is not proven here. It needs the Mac steps above, and must be checked on a Mac before it is claimed to work there.
