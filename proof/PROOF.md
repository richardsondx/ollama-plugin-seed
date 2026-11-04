# Proof report: Ollama plugin seed, Nov 4, 2026

## Verdict
Judge: NARROW, not a clean PASS. The seed is usable as a base, with the gaps below recorded. A clean PASS would have converted those gaps into a pass, which the judge refused to do.

## What passed
- 14 tests, 13 behavioural, 1 wording check, run with python3 -m unittest discover -s tests, exit 0.
- Disabled plugins expose no tools, and unlisted tool execution is refused, by behavioural tests.
- Always-confirm computer actions return confirmation_required and do not execute, by behavioural tests.
- Invalid skill folders are reported as errors, not loaded.
- No OpenAI code, ChatGPT extension code, or @oai/sky code found in the files read by the verifier.
- Seed honestly states it is not a full Ollama fork.
- Live server check, by the generator, twice: 3 plugins listed (browser, computer, skill-creator), browser enabled, tools returned as browser.webmcp.list_tools and browser.webmcp.execute_tool. The verifier did not independently re-run this live check, so it is recorded as a generator check, not a verifier check.

## What failed, and was fixed in the same run
- First test run failed because a __pycache__ folder was counted as a plugin. The loader now skips __pycache__ and dot folders, and tests pass.
- Verifier found a DOM fallback contradiction in the browser skill, a missing background execute dispatch, and wildcard postMessage origins. All three were fixed locally, tests were re-run (14 passed), and extension JavaScript passed node --check. Those fixes were not independently re-verified by the verifier or judge, and that is recorded as a gap.

## Gaps that must be carried forward, from the judge
- No real Ollama patch applied; upstream integration is documentation only, and upstream PR ollama/ollama#13562 must be verified against a checkout.
- No desktop app Plugins page; the seed uses a server-served admin page on 127.0.0.1:11435, and the desktop app page is a later, Windows and macOS gated phase.
- No live Chrome test; extension JavaScript was read and syntax-checked, not run in Chrome.
- No live macOS control proven; real control is gated, best-effort, and requires Accessibility permission.
- No end-to-end Ollama chat test; that flow is documentation, not a test in the suite.
- Server-to-extension wiring for WebMCP execution is incomplete: the background dispatch handler exists, but the plugin server does not yet call it, and seed execution remains dry-run.
- Content script still matches all_urls for discovery, even though forwarding to the server is gated by allowed sites; that injection scope should be justified before release.
- No model runner, no llama/ or ml/ code, and no automatic skill loading into model context.
- Only 13 of the 14 passing tests are behavioural; the remaining test is a wording check, not functional proof.

## What was not done
- Nothing was forked on GitHub, pushed, deployed, posted, sent, paid, or deleted. The seed is local only at workspace/ollama-plugin-seed/, 37 files. A fork and push need a separate approval, with the exact repo name, visibility, file list, and commit message shown before any push runs.
- No live computer action was run. Computer Use in this seed is dry-run by default.
- No Chrome extension was installed or run in a live browser in this run.

## How to run it
```
python3 scripts/run_server.py
python3 -m unittest discover -s tests -v
```
Open http://127.0.0.1:11435 for the Plugins page, with Plugins, Skills, and Installed tabs.
