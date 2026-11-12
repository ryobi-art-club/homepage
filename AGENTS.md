# AGENTS.md — homepage

Instructions for AI coding agents working in this repository. Human-oriented documentation is in [README.md](README.md) (Japanese); read sections 1, 6 and 11 before changing code, plus section 8 for the CMS and section 12 for the public site. This file covers the whole repository and the public site; [cms/AGENTS.md](cms/AGENTS.md) adds the rules for the CMS.

## What this is

The website of the 凌美会 art club, in two parts:

- **Public site** (repository root): one static page published on GitHub Pages. `scripts/fetch_google_content.py` reads Google Sheets and Drive (read-only service account) into `build/runtime/`, and `scripts/build_site.py` renders `dist/` from that snapshot plus `src/site_static.json` (HTML in `scripts/sitebuild/`). The build workflow (`.github/workflows/deploy.yml`) runs only on `workflow_dispatch` (the CMS "公開する" button or a manual run); pushing does not rebuild the site.
- **CMS** (`cms/`): the admin screen members use to edit and publish content, a Google Apps Script web app deployed with clasp from `cms/`.

The two parts are deployed separately (GAS versions vs. GitHub Pages), even though they live in one repository. Users are club members, not engineers; all UI and site text is Japanese.

## Commands

```bash
pip install -r requirements.txt
python -m unittest discover tests     # public site + repository contents check; no Google access needed
(cd cms && node --test tests/*.cjs)   # CMS unit tests
git config core.hooksPath .githooks   # once per clone: runs the repository contents check before each commit
npm install --prefix tools/screenshot # once
node tools/screenshot/shoot.cjs      # builds the site from tools/screenshot/sample-content.json and takes screenshots
node tools/screenshot/compare.cjs --save <dir outside the repo>   # before a change that should not alter looks
node tools/screenshot/compare.cjs <dir>                           # after it: pixel-by-pixel comparison
```

`.github/workflows/check.yml` runs both test suites on every push. A full local build of the site needs the service-account key and the spreadsheet ID (README 12-4). **Do not look for or read the key yourself**; ask the maintainer to run the fetch step. Site rendering functions can be checked without Google access by importing them and calling them with small dicts, or with the sample-content screenshots.

## Hard rules

- **Never** commit, push, run `clasp push`, change deployments, run the workflow, or send anything to an external service unless the maintainer explicitly asks in this conversation.
- **Never** read or print credentials (service-account JSON, `.clasprc.json`, private keys, anything in a user's key folder) and never print Script Property values. If a task needs them, ask the maintainer to run that step.
- This repository is public. Never commit e-mail addresses (other than reserved example domains and the club's public contact address), the CMS web-app URL, keys, or spreadsheet exports. `tests/test_repository_contents.py` enforces this in `.githooks/pre-commit`, on every push and before every build. Keep working files in `tmp/` (ignored) or outside the repository.
- **Data contracts between `cms/` and the site build**:
  - The content saved in `_PublishedState` and `_Drafts` has the shape `CONTENT_FIELDS` in `cms/ContentModel.js` (`formatVersion` 2, README 8-4), read by `scripts/fetch_google_content.py`. Content of another format version is refused on both sides (`requireContentFormat_`, `read_published_content`). To change the format, raise the version and convert older versions in those two places only; remove the conversion once a publish has rewritten the stored content.
  - `ChangeLog` holds one change per row (`timestamp`, `kind`, `item_id`, `note`, `actor_name`), no titles. The wording table `CHANGE_LOG_ITEM_LISTS` in `cms/ContentHistory.js` is mirrored by `CHANGE_LOG_TEXT` in `scripts/sitebuild/sections.py`; change both together.
  - Read sheet columns by header name and tolerate missing columns. Normally the CMS and the site may be deployed in either order; when a change fixes an order, write it down in the README.
- One value, one name: do not store values that other values determine, and do not add second names for an existing value. When two places hold the same fact, keep (1) the one that cannot become contradictory, then (2) the source value, then (3) the most-used name that fits the naming rules (README 11-2).
- Preserve each file's line endings when editing with scripts (several files are CRLF in the working copy).

## Public site conventions

- **HTML**: build markup with `html(template, **values)` from `scripts/sitebuild/html.py`: values are escaped, `Markup` results and lists of them are inserted as is, `None`/`False` insert nothing, newlines plus indentation in the template are removed. Wrap only fixed markup from the code in `Markup(…)`. Do not build HTML with f-strings and `escape()`. The package is `sitebuild`, not `site` (that name is a Python standard module).
- **Styles**: pick colours and sizes from the tokens at the top of `src/stylesheet.css` by role (text: `--text-body` / `--text-soft` / `--text-muted`; lines: `--divider` / `--line-strong` / `--underline`; surfaces: `--glass` / `--glass-strong`). Write a raw value only for a one-off effect (hero shade, grid overlay, logo glow). No inline `style=` for looks in the generated HTML, except values computed per item (`--ratio`, `--rows`, carousel ratios).
- The CMS preview pane imitates this site (the "サイトプレビュー" section of `cms/UiStyles.html` and the renderers in `cms/UiPreview.html`; the function mapping is in README 12-6). When you change how content looks on the site, update the CMS preview too.
- Some class names are assembled in code (e.g. `exhibition-{placement}-heading` and `image-count-{n}` in `sitebuild/sections.py`). Before removing CSS as unused, search for the parts of the name too, and compare screenshots.
- Images in `src/` are copied to `dist/` by name (`STATIC_FILES` in `build_site.py`); a new image needs its name added there.
- Keep pages light: no embedded third-party widgets (maps are plain links to Google Maps search URLs).
- `requirements.txt` pins major-version upper bounds on purpose; raise them only after a local build works.
- **Wording**: the public site uses the wording most natural to visitors; the CMS uses clear, concise wording. Keep the per-place wording (取り組み事例 / 過去の取り組み事例 / 取り組み「…」); do not unify it to 実績 (it reads as boasting).
- **Comments**: Japanese, and only for what the code cannot say (a reason, an agreement between the CMS and the site, a past incident). Prefer clearer names and structure over a comment. Consistency with how the rest of the code does the same thing comes first.

## How to verify a change

1. Run both test suites (Commands above).
2. For changes that should not alter the page or the CMS screens, compare screenshots before and after: `tools/screenshot/compare.cjs` for the site, `cms/tools/preview/compare.cjs` for the CMS (see cms/AGENTS.md).
3. For changes to the data read from the sheets, also compare the site built from real data (ask the maintainer for an Excel export of the spreadsheet; keep it outside the repository).

## Working with the maintainer

- Report in Japanese, in plain words; spell out abbreviations. Say what you verified and what you could not verify.
- The maintainer's checks are expensive (deploy + reload + one-time-code login, and publish/build waits). Batch changes into few deploys, and ask only for checks whose result changes what you do next. Before writing deploy steps, check the real trigger and configuration (e.g. the site workflow runs only on `workflow_dispatch`).
- For visible changes, show before/after screenshots and get agreement before finalizing.
- Ask before decisions that are the maintainer's to make (wording visible to members, removing features, anything irreversible).
- Update `README.md` when setup, operation, the static content fields, the page structure or design decisions change. There is no separate help page for members; members' common questions and their answers are in README section 7.
