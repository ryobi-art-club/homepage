# AGENTS.md — cms/

Instructions for AI coding agents working on the CMS (this folder). The rules for the whole repository (hard rules, data contracts with the site build, wording, comments, working with the maintainer) are in the [root AGENTS.md](../AGENTS.md) and apply here too. Human-oriented documentation is the [root README.md](../README.md) (Japanese); section 8 describes the CMS.

## What this is

The admin screen (CMS) of the 凌美会 art club website: a Google Apps Script web app (`AppMain.js` serves `Ui.html`, which inlines the five screen scripts `UiCore.html`, `UiMedia.html`, `UiPreview.html`, `UiEditors.html`, `UiPublish.html` in that order, and `UiStyles.html`). Server files are grouped by a name prefix, since the Apps Script editor has no folders (README 8-1): `App…` (entry, config, shared utilities, login, error mail, Gemini client), `Content…` (content API, format, sheets, change history, proofreading, site build), `Media…` (image API, publish-time folder work, folders, storage, catalog). Functions called from the screen live in `ContentApi.js` / `MediaApi.js` (plus the feature files named in README 8-1). Helpers used by two or more groups go in `AppUtil.js`. All files share one global scope; put only declarations and constant values at the top level of a file (Apps Script loads files in no fixed order). The tests load every server `.js` (`tests/files.cjs`). It stores content in Google Sheets and images in Google Drive, and "公開する" starts the site build workflow of this repository.

## Commands (run in `cms/`)

```bash
node --test tests/*.cjs                       # unit tests (no Google access)
node tools/preview/build.cjs                  # local preview with sample data -> tools/preview/out/preview.html
npm install --prefix tools/preview            # once, for the screenshot runner
node tools/preview/shoot.cjs                  # drives every feature, saves screenshots, reports problems
```

`shoot.cjs` needs Chrome (and network for the SheetJS check). It prints: page overflow at several phone/tablet sizes, JavaScript errors, screen-script functions that never ran, and whether SheetJS loaded with SRI. It exits with code 1 when it finds a problem. `clasp push` (maintainer only) sends this folder to Apps Script.

## Hard rules

- The screen scripts (`UiCore.html` … `UiPublish.html`) are inlined by HtmlService. They must not contain the literal strings `https://`, `http://`, `//` (so no `//` comments; use `/* */`), `image/*`, or an SVG `xmlns`. Build URLs with `URL_PROTOCOL + '…'` and write `'image/' + '*'`. `tests/ui-script.test.cjs` checks this.
- Write to content sheets through `writeSheet_` (it sets the plain-text format `@` so values are not turned into formulas, dates or numbers).
- Some class names are assembled in code (e.g. `is-${placement}`, `'is-' + type`). Before removing CSS or functions as unused, search for the parts of the name and run the preview screenshots.
- Files in this folder that must not reach Apps Script (Node tools, docs, tests) go in `.claspignore`.
- Never put the web-app URL in any file (it is given to members directly).

## Conventions

- **Errors**: every catch site calls `showError(error, '操作名', target)` (`target` is `''`, `'auth'` or `'media'`). The one-line summary shows only what to do next (or the message itself); the operation name appears in the detail card and the history (`errorSummary`). Classification and hints live in `ERROR_RULES`. Messages tell the member what to do next, in plain Japanese.
- **Login**: do not reveal whether an address is on the allowlist. Unregistered addresses get the same answers, limits and timing as members (a code is created but not mailed; `pickOtpMailTime_`). Keep it that way when changing `AppAuth.js` (README 8-2).
- **Styles**: use the tokens at the top of `UiStyles.html` (`--space-*`, `--radius-*`, `--fs-*`, colours), chosen by role, not by the nearest value: status colours come as `--green-*` / `--danger-*` / `--yellow-*` with `-bg`, `-line`, `-text`. Write a raw colour only for a one-off effect; add a token when a new role appears (README 11-6). Text follows the Digital Agency guideline for Japanese: 16px for body and UI, never below 14px. Touch targets are at least 44px on phones. No decorative gradients, blur or large shadows. The "サイトプレビュー" section of `UiStyles.html` mirrors the public site (`../src/stylesheet.css`) and uses its values.
- **Images**: render Drive images with `mediaImageHtml(file)` and call `hydrateThumbnails(container)` after inserting HTML. Images in link-shared folders (`file.public`) load straight from Drive; private ones are fetched through `getMediaThumbnails` (the browser cannot read private Drive files, the server runs as the owner). Never put a private image's Drive URL in an `<img>`.
- **Content state**: `appState.state` is the only place content lives on the screen. Editor fields carry `data-field` inside an `<article data-editor="kind" data-index="n">` and write to the state on input (`onEditorInput` → `setEditorField`); never read content back from the DOM. Saving, publishing, previews and proofreading all start from `buildPayload()` / `buildPayloadList(kind)`, the one place that trims, normalises and sorts.
- **HTML**: build markup with the `html` tagged template (values are escaped; nested `html` results and arrays are inserted as is; `null`/`undefined`/`false` insert nothing; newlines plus indentation in the literal parts are removed). Wrap only fixed markup from the code in `trustedHtml(…)`. Use `jsString(value)` for values inside `onclick="…('…')"`. Do not call `escapeHtml` directly or join HTML strings.
- **Previews**: the right-hand previews are built only after the member presses 「プレビューを表示」 (`openPreview`, `ensurePreviewOpen`). Do not make tab switches or typing call the server while a preview is closed. They imitate the site's `scripts/sitebuild/sections.py` (mapping in README 12-6).
- **Explanations**: do not add always-visible notes. Put occasional explanations behind a `?` button (`data-help` box + `${HELP_BUTTON}` + `.help-text`).
- **Naming** (README 8-1, 11-3): server functions callable from the screen have no `_`, all others end with `_`; constants are UPPER_CASE without `_` at the end; screen-script `on…` names are only for change/keydown/input handlers, button actions start with a verb. Verbs keep one meaning each: `read` (sheet, or form/file on the screen), `get` (Drive, settings, cache), `build`, `parse`, `normalize`, `require` (throws), `ensure` (creates if missing), `render`, `refresh`. Stored data uses camelCase (`mediaFolderId`); internal names for 取り組み事例 are `request` / `requestCases` / `caseId`.
- **One place for one job**: reuse the shared helpers (`requireOneOf_`, `askGeminiForJson_`, `sendAdminMail_`, `refreshPreview`, `toggleItemPublished` / `removeItem`, `commitEditorChange`, `movedInList`, `commitMediaChange`, `readFile`) instead of writing the same steps again.
- **Publishing safety**: never delete anything midway through a publish; delete only after success, and keep every step safe to retry.
- **Preview mock**: `tools/preview/mock-backend.js` mirrors the server functions' return values and messages. When you add or change a server function the UI calls, update the mock, and add steps to `shoot.cjs` so the new UI code runs (the "never ran" list must stay empty).

## How to verify a change

1. `node --test tests/*.cjs`
2. For anything visible: `node tools/preview/build.cjs` then `node tools/preview/shoot.cjs`, and look at the relevant screenshots in `tools/preview/out/shots/` (desktop and mobile). Phone sizes are emulated as real phones (viewport meta honoured).
3. For changes that should not alter looks or behaviour (refactoring): before the change run `shoot.cjs` and `node tools/preview/compare.cjs --save <dir outside the repo>`; after it run `build.cjs`, `shoot.cjs` and `node tools/preview/compare.cjs <dir>`. It compares every screenshot pixel by pixel and the calls the screen sent to the server (key order ignored). Shots are deterministic (fixed clock and random numbers, no animation, status queue drained).
4. Server-side code cannot be run locally; cover it with tests in `tests/` (they load the `.js` files into a `vm` context with stubbed Google services).
