# AGENTS.md — homepage

Instructions for AI coding agents working in this repository. This file is in English and deliberately short: it holds the hard rules and tells you which document to read. The documentation itself is in Japanese under `docs/` (overview in `README.md`); read it there instead of expecting it to be restated here. [cms/AGENTS.md](cms/AGENTS.md) adds the rules for the CMS.

## What this is

The website of the 凌美会 art club, in two parts that are deployed separately:

- **Public site** (repository root): a static page built by `scripts/` from Google Sheets and Drive and published on GitHub Pages by `.github/workflows/deploy.yml`, which runs only on `workflow_dispatch` (the CMS "公開する" button or a manual run); pushing does not rebuild the site.
- **CMS** (`cms/`): a Google Apps Script web app that members use to edit and publish content; deployed with clasp from `cms/`.

## Read before you work

| Task | Read |
|---|---|
| Any code change | `docs/coding-rules.md` (rules for both parts), `docs/development.md` (setup, checks, pitfalls, deploy steps) |
| Public site code or looks | `docs/reference/site.md` |
| CMS code | `docs/reference/cms.md` and [cms/AGENTS.md](cms/AGENTS.md) |
| Sheet layout, saved content shape, update log | `docs/reference/data.md` (the contract between `cms/` and the site build) |
| Why something is built this way | `docs/decisions.md` |
| Operating procedures, troubleshooting | `docs/operations.md`, `docs/troubleshooting.md` |

## Commands

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate; .venv is ignored
pip install -r requirements.txt
python -m unittest discover tests     # public site + repository contents check; no Google access needed
(cd cms && node --test tests/*.cjs)   # CMS unit tests
git config core.hooksPath .githooks   # once per clone: runs the repository contents check before each commit
npm install --prefix tools/screenshot # once
node tools/screenshot/shoot.cjs      # builds the site from sample content and takes screenshots
node tools/screenshot/compare.cjs --save <dir outside the repo>   # before a change that should not alter looks
node tools/screenshot/compare.cjs <dir>                           # after it: pixel-by-pixel comparison
```

`.github/workflows/check.yml` runs both test suites on every push. A full local build of the site needs the service-account key; **do not look for or read it yourself**, ask the maintainer.

## Hard rules

- **Never** commit, push, run `clasp push`, change deployments, run the workflow, or send anything to an external service unless the maintainer explicitly asks in this conversation.
- **Never** read or print credentials (service-account JSON, `.clasprc.json`, private keys, anything in a user's key folder) and never print Script Property values.
- This repository is public. Never commit e-mail addresses (other than reserved example domains and the club's public contact address), the CMS web-app URL, keys, or spreadsheet exports. `tests/test_repository_contents.py` enforces this before each commit, on every push and before every build. Keep working files in `tmp/` (ignored) or outside the repository.
- `cms/` writes and the site build reads the same data (`_PublishedState`, `ChangeLog`). Change both sides together and update `docs/reference/data.md`; see it for the format-version rule and the mirrored wording table.
- Before removing CSS or functions as unused, search for class names assembled in code (e.g. `exhibition-{placement}-heading`, `image-count-{n}`) and compare screenshots.
- Preserve each file's line endings when editing with scripts (several files are CRLF in the working copy).

## Documentation rules

- Human documentation, code comments and all UI/site text are Japanese; only `AGENTS.md` files are English (`docs/coding-rules.md`, 「資料の言葉と置き場所」).
- Keep each document in its role (overview, procedure, troubleshooting, reference, decisions) and refer to other documents by file name and heading, never by section number.
- When setup, operation, the data shape or a design decision changes, update the matching file under `docs/`. There is no separate help page for members; members' questions are answered in `docs/troubleshooting.md`.

## Working with the maintainer

- Report in Japanese, in plain words; spell out abbreviations. Say what you verified and what you could not verify.
- The maintainer's checks are expensive (deploy + reload + one-time-code login, and publish/build waits): batch changes, ask only for checks whose result changes your next step, and check the real trigger and configuration before writing deploy steps (`docs/coding-rules.md`, 「管理者に確認をお願いするとき」).
- Show before/after screenshots for visible changes, and ask before decisions that are the maintainer's to make (wording members see, removing features, anything irreversible).
