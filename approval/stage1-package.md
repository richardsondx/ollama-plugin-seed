# Stage 1 approval package: Ollama plugin seed, approved Nov 4, 2026

Package version: stage1-seed-fork-2026-11-04-01
Approval: Richardson tapped "Approve seed fork package" on Nov 4, 2026.

## Intent and audience
Build an open source seed for adding Codex-style plugin capability to Ollama, with a Chrome plugin using WebMCP and a Computer Use feature matching OpenAI's, so open source models can use them through Ollama. Audience: Richardson, and other people who want to add plugins and skills on this base.

## Deliverable
A local repo-ready folder at workspace/ollama-plugin-seed/, containing a working plugin loader and server, a Plugins admin page with Plugins, Skills, and Installed tabs, three builtin plugins, a Chrome extension, a Computer Use adapter, tests, and docs, including the upstream integration path for a real Ollama fork.

## Finish predicate
The seed passes only if all of these hold:
1. python3 -m unittest discover -s tests passes, 14 tests.
2. The live server lists 3 plugins, enables one, and returns its tools in Ollama chat tool shape.
3. A disabled plugin exposes no tools, and execution of a disabled or unlisted tool is refused.
4. A computer action classified as always_confirm returns confirmation_required and does not execute.
5. A skill folder that fails validation is reported as an error, not as a loaded skill.
6. No OpenAI code, ChatGPT extension code, or @oai/sky package is copied or claimed as compatible.
Predicate examples:
- Passing: a new plugin folder with a valid manifest and SKILL.md loads and lists, without changing core code.
- Failing: a plugin that claims browser control but only shows a static page, with no WebMCP tool discovery or DOM fallback, is not counted as a browser plugin.

## Constraints and assumptions
- Local work only in Stage 1. No fork on GitHub, no push, no deploy, no send, no delete.
- Server-served admin page is the Plugins host for the seed, not the desktop app page in app/, which is a later phase.
- OpenPresence reuse is pattern only: allowlist refusal, host allowlist, session handling. No OpenPresence browser code exists to copy.
- WebMCP is a proposed standard, not a finished standard, and only exposes tools a page registered.
- Computer Use is dry-run by default. Real macOS control is gated and best-effort in this seed.
- Assumption: Ollama upstream paths were mapped from a text fetch and secondary sources, and must be rechecked against a checkout before patching a real fork.

## Authority envelope
Autonomous scope: read and write files under workspace/ollama-plugin-seed/, run local Python tests and a local server on 127.0.0.1:11435.
Methods: local Python, local file writes, subagents for independent verification only.
Time and cost: local work, no paid tools, actual spend 0 dollars.
One-way-door gates, all requiring a separate approval: fork on GitHub, push, deploy, post, send, pay, delete.
Prohibited actions: fork, push, deploy, send, post, pay, delete, copy OpenAI code, claim @oai/sky compatibility, relax the predicate, convert a gap into a pass, expand the tool or target allowlist without reapproval.

## Plan and routing
Case A for the plugin system structure, because the skill format and WebMCP docs already exist. The seed is hand-built, not generated for an unproven field, and its first real task is the proof run in this package: the live server check and the test suite.
Stages: research, build loader and server, build extension and computer adapter, build docs, run tests and live server check, independent verifier, judge, proof report.
Depth max 2, serial execution by default, spawn count cap 4 for this run.

## Verification
Deterministic checks first: unit tests and live server curl checks. Generator and verifier separated. Judge in a fresh context with only the spec, the artifact, and the verifier report. Judge cannot convert a gap into a pass.

## Iteration and stopping
Stuck ladder: try the next route, change the method, or make an operational retry that leaves the deliverable and predicate unchanged, then report a dead end. Narrowing scope or changing a limit is an amendment, requiring a new predicate version and reapproval.

## Operations
Decision trail at proof/decision-trail.tsv. Artifact versions are file hashes recorded in the proof report. Cleanup: kill only what the run started, never the evidence. The test server was stopped after the live check, and its state file was removed.
