# AGENTS.md — homepage

Instructions for AI coding agents working in this repository. Human-oriented documentation is in [README.md](README.md) (Japanese). The system overview, accounts and operations are documented in the sibling repository `homepage-cms` (its README.md and AGENTS.md); read those first.

## What this is

The public website of the 凌美会 art club, built as one static page and published on GitHub Pages. `scripts/fetch_google_content.py` reads Google Sheets and Drive (read-only service account) into `build/runtime/`, and `scripts/build_site.py` renders `dist/` from that snapshot plus `src/site_static.json`. The GitHub Actions workflow runs only on `workflow_dispatch` (the CMS "公開する" button or a manual run); pushing does not rebuild the site.

## Commands

```bash
pip install -r requirements.txt
python -m py_compile scripts/build_site.py scripts/fetch_google_content.py
python -m unittest discover tests     # no Google access needed; the workflow runs it before every build
```

The content comes from `_PublishedState` as JSON (format version 2; its shape is defined in homepage-cms README section 8-4 and `CONTENT_FIELDS` in `Store.js`). Older formats are read only through `upgrade_content`. Change both repositories together when the shape changes.

A full local build needs the service-account key and the spreadsheet ID (README section 4). **Do not look for or read the key yourself**; ask the maintainer to run the fetch step. Rendering functions can be checked without Google access by importing `scripts/build_site.py` and calling them with small dicts.

## Hard rules

- **Never** commit, push, run the workflow, or send anything to an external service unless the maintainer explicitly asks in this conversation.
- **Never** read or print credentials (service-account JSON, keys). They must never be committed (`.gitignore` covers common names).
- Read sheet columns by header name and tolerate missing columns: the CMS and this site may be deployed in either order.
- Some class names are assembled in code (e.g. `exhibition-{placement}-heading` in `build_site.py`). Before removing CSS as unused, search for the parts of the name too, and check the page at desktop and phone widths.
- Images in `src/` are copied to `dist/` by explicit lines in `main()` of `build_site.py`; a new image needs a new copy line.
- `requirements.txt` pins major-version upper bounds on purpose; raise them only after a local build works.
- Preserve each file's line endings (several files are CRLF).

## Conventions

- HTML is built with Python f-strings; escape every value from the snapshot with `escape()`.
- The CMS has a preview pane that imitates this site (`homepage-cms/UiStyles.html`, "サイトプレビュー" section, and the preview renderers in `UiScript.html`). When you change how content looks here, mention that the CMS preview should be updated to match.
- Keep pages light: no embedded third-party widgets (maps are plain links to Google Maps search URLs).

## Working with the maintainer

- Report in Japanese, in plain words; say what you verified and what you could not.
- Show before/after for visible changes and get agreement before finalizing.
- Update `README.md` when setup, the static content fields or the page structure change.
