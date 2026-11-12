# AGENTS.md — cms/

Rules for AI coding agents working on the CMS (this folder). The [root AGENTS.md](../AGENTS.md) applies too. Read `../docs/reference/cms.md` (how the CMS works) and `../docs/coding-rules.md` (rules for both parts) before changing code; this file only adds the CMS-specific hard rules and commands.

## Commands (run in `cms/`)

```bash
node --test tests/*.cjs              # unit tests (no Google access)
node tools/preview/build.cjs         # local preview with sample data -> tools/preview/out/preview.html
npm install --prefix tools/preview   # once, for the screenshot runner
node tools/preview/shoot.cjs         # drives every feature, saves screenshots, reports problems
node tools/preview/compare.cjs --save <dir outside the repo>   # before a change that should not alter looks or behaviour
node tools/preview/compare.cjs <dir>                           # after it: screenshots pixel by pixel + calls sent to the server
```

`shoot.cjs` needs Chrome. It reports page overflow, JavaScript errors, screen-script functions that never ran, and whether SheetJS loaded with SRI; the "never ran" list must stay empty, so add shoot steps (and mock responses in `tools/preview/mock-backend.js`) when you add UI code or change a server function the UI calls.

## Hard rules

- Screen scripts (`UiCore.html` … `UiPublish.html`) are inlined by HtmlService: never write the literal strings `https://`, `http://`, `//` (use `/* */` comments), `image/*`, or an SVG `xmlns`. `tests/ui-script.test.cjs` checks this.
- All server files share one global scope and load in no fixed order: put only declarations and constant values at the top level of a file.
- Write to content sheets only through `writeSheet_` (plain-text format, so values are not turned into formulas, dates or numbers).
- Screen code keeps content only in `appState.state` and builds what it sends with `buildPayload()`; build HTML only with the `html` tagged template. Details: `../docs/coding-rules.md`.
- Login must not reveal whether an address is on the allowlist (same answers, limits and timing for unregistered addresses). Keep this when changing `AppAuth.js`; see `../docs/reference/cms.md`.
- Never put the web-app URL in any file. Files in this folder that must not reach Apps Script (tools, tests, docs) go in `.claspignore`.
