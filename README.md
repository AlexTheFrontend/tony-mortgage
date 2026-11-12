# Tony's View tracker

A private page that shows Tony Alexander's weekly borrower advice and economic
tone (from Tony's View, tonyalexander.nz) on one timeline with the OCR, swap
rates, mortgage rates and an advice score.

Design: `docs/superpowers/specs/2026-10-08-tonys-view-tracker-design.md`

## Run

1. `uv sync`
2. `uv run python -m scripts.fetch_issues` - download new Tony's View PDFs.
3. `uv run python -m scripts.extract_text` - text and issue list.
4. Write records for new issues with Claude Code helper agents and
   `rules/extraction-rules.md` (see the plan, Task 6).
5. `uv run python -m scripts.validate` - must print `all records valid`.
6. Download `hb2-daily-close.xlsx` and `hb20.xlsx` from the Reserve Bank in a
   browser into `data/raw/rbnz/` (the site blocks scripts).
7. `uv run python -m scripts.build_data` - writes `site/data.js` with Tony's
   quotes, for your own use. It prints a WARNING when the Reserve Bank data
   ends more than 6 weeks before the last issue.
8. Open `site/index.html`.

## Deploy

Deploy only the `public/` folder. It never holds Tony's quotes.

1. `uv run python -m scripts.build_data --public` - writes `public/`: a copy
   of `site/` with a `data.js` that has no quotes. `site/data.js` does not
   change.
2. `cd public && npx vercel --prod`. Or, in the Vercel project settings, set
   Root Directory to `public`, Framework Preset to "Other", and leave the
   build command empty.

Do not deploy `site/`: its `data.js` can hold quotes.

## Checks

1. `uv run pytest` - the Python tests.
2. `node tests/page/run.mjs` - 20 checks of the page in headless Edge or
   Chrome, with no network (Node 22 or later). Exit code 0 means all checks
   passed. Options:
   - Add `public` to check the deploy folder:
     `node tests/page/run.mjs public`.
   - Add a time zone to check the dates there:
     `node tests/page/run.mjs public America/Los_Angeles`.
   - Run the checks at least once in a time zone east of UTC, for example
     `Pacific/Auckland`. A date error that uses UTC shows only there.
   - Set `BROWSER` to the browser program if the runner cannot find it.
