# Independent verifier report: Ollama plugin seed

Verifier context: Stage 1 package, README, architecture, upstream-integration, browser and computer skills, and Chrome extension manifest, content.js, and background.js. Tests were run locally. No edit, push, fork, or deploy by the verifier.

## Tests
- 14 tests ran, 14 passed, exit 0, matching the Stage 1 predicate count.
- 13 tests are behavioural: discovery, enable and disable, refusal, confirmation gating, and validation.
- One test, test_no_em_dash_in_skill_bodies, is a wording and style check, not functional proof, and should not be presented as functional behaviour proof.
- Scope limit: Python unit tests only were run by the verifier. The live server curl check was not independently re-run live by the verifier, though ServerTest names support it.

## Seed, not a full Ollama fork
- Honest. README says this seed is not a full copy of Ollama, and not a copy of OpenAI's ChatGPT extension or its @oai/sky package. Upstream-integration says fork steps are when approved separately, and the seed as its own repo is separate from a full fork.

## OpenAI code
- No, on the files read. No OpenAI code, ChatGPT extension code, or @oai/sky code appears. Computer Use uses the same confirmation categories as the user-supplied policy, presented as categories, not as copied code.

## Chrome extension
- Limited to page-registered WebMCP tools on user-allowed sites, with no DOM click, type, scroll, or screenshot control in content.js. Background.js gates forwarding by allowed site, and says it never forwards page content, cookies, or credentials.

## Computer Use
- Dry-run by default, with a confirmation gate, supported by test names and by the skill frontmatter.

## Gaps found, and what was fixed after verification
Fixed locally before the judge, within the approved envelope:
- Browser skill DOM fallback contradiction: the skill said to use DOM tools as a fallback, while README and architecture said there is no DOM fallback in the seed. The skill and plugin description were corrected to say there is no DOM fallback in this seed.
- Chrome execution loop: background.js had no handler to dispatch an execute message to a tab. A dispatch handler for execute-webmcp with a tab id was added, and JS syntax was checked with node --check.
- PostMessage origin: page script posts used "*" and content listeners checked source but not origin. Posts now use location.origin, and listeners check event.origin.

Gaps that remain, and must be recorded in the proof report:
- No real Ollama patch applied. Upstream-integration is documentation only, and upstream PR ollama/ollama#13562 must be verified against a checkout.
- No desktop app Plugins page. The seed uses a server-served admin page on 127.0.0.1:11435. The desktop app page is a later, Windows and macOS gated phase.
- No live Chrome test. Extension JavaScript was read and syntax-checked, not run in Chrome.
- No live macOS control proven. Real control is gated, best-effort, and requires Accessibility permission.
- No end-to-end Ollama chat flow tested. That flow is documentation, not a test in the suite.
- Server-to-extension wiring for WebMCP execution is not complete: the background dispatch handler exists, but the plugin server does not yet call it. Seed execution remains dry-run.
- Content script still matches all_urls for discovery, even though forwarding to the server is gated by allowed sites. That injection scope should be justified before release.
- No model runner, no llama/ or ml/ code, and no automatic skill loading into model context. Those are stated limits, not hidden gaps.
