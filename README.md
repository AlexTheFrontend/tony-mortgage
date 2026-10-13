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
7. `uv run python -m scripts.build_data` - writes `site/data.js`.
   Use `--no-quotes` before you publish the site anywhere.
8. Open `site/index.html`.

Tests: `uv run pytest`
