# WebMCP, for the Chrome plugin

WebMCP is a proposed web standard, not a finished standard. Chrome docs describe it as a way for a page to declare structured tools for an agent, instead of the agent scraping the DOM to guess what a button or field means.

## Page side
- Imperative: document.modelContext.registerTool, with name, description, inputSchema, and an execute function. The execute function receives the input object, and an object with an AbortSignal as its second argument.
- Declarative: a form with toolname and tooldescription, and toolparamdescription on elements, becomes a tool. Removing toolname or tooldescription unregisters it.
- Discovery: document.modelContext.getTools, with an optional fromOrigins list for secure origins, and document.modelContext.executeTool for calling a tool.
- Gating: the tools permissions policy defaults to self, for top-level and same-origin contexts. Cross-origin iframes need allow="tools", and cross-origin discovery needs exposedTo on registration plus fromOrigins on discovery.
- Availability in the docs: origin trial from Chrome 149, plus local development with the chrome://flags/#enable-webmcp-testing flag.

## Extension side, in this seed
- The content script runs in an isolated world, so it injects a page script that runs in MAIN world to call document.modelContext.getTools.
- Results are relayed by postMessage to the content script, then to the background worker, then to the local plugin server, only for sites the user allowed in the popup.
- Execution goes back through the same path, to the page that registered the tool. The extension does not execute page tools itself.
- The extension never reads cookies, passwords, local storage, or session stores, and it never forwards page content.

## Limits, stated plainly
- WebMCP only exposes what a page registered. It does not give generic control of a page that did not opt in.
- Persistence across reloads or restarts is not stated in the fetched Chrome docs, so this seed does not assume it.
- A page registration cannot add a plugin, a destination, or a permission to the Ollama side.
