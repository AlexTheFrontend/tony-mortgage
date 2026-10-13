# Tony's View Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local static page that shows Tony Alexander's weekly borrower advice and economic tone (April 2022 - October 2026) on one timeline with the OCR, swap rates, mortgage rates and an advice score.

**Architecture:** Small Python scripts download the free Tony's View PDFs, extract their text, and check the per-issue JSON records that Claude Code helper agents write from a fixed rule sheet. A build script combines the records with two Reserve Bank xlsx files into `site/data.js`. A static page (`site/index.html` + Apache ECharts, saved locally) draws four stacked charts on one time axis.

**Tech Stack:** Python 3.11+ managed by `uv`, `pypdf`, `openpyxl`, `pytest`; plain HTML/CSS/JS with Apache ECharts 5.5.1 (vendored file).

**Spec:** `docs/superpowers/specs/2026-10-08-tonys-view-tracker-design.md`

## Global Constraints

- Python dependencies: `pypdf`, `openpyxl` (runtime) and `pytest` (dev) only. Run everything with `uv run` from the project root `/Users/sasha.fedorov/Projects/tonywebsite`.
- Use only free Tony's View PDFs: file names that start with `Tonys-View-`. Never use `Tview-Premium-*` PDFs (Tony's paid newsletter).
- PDFs and extracted text stay in `data/raw/` (git-ignored, never deployed).
- Download politely: User-Agent `tonywebsite-personal-tracker/0.1 (personal, non-commercial)`, 1 second between PDF downloads.
- Every quote in a record must be word for word from the issue text. `scripts/validate.py` enforces this.
- Borrower groups: `float`, `6m`, `1y`, `18m`, `2y`, `3y_plus`, `mix`, `none`. Permitted terms in months: 0, 6, 12, 18, 24, 36, 48, 60.
- Tone score: integer from -2 to +2.
- Advice score: sample loan $500,000, interest-only, no break fees, B20 monthly rates.
- The page must work from `file://` with no internet: no `fetch()`, no CDN at run time; data in `site/data.js`; ECharts in `site/vendor/echarts.min.js` (version 5.5.1).
- `uv run python -m scripts.build_data --no-quotes` must produce a page with no text from Tony's issues other than headlines.
- Reserve Bank series IDs: OCR `INM.DP1.N`, swap 1y `INM.DS01.NZZC`, swap 3y `INM.DS03.NZZC` (file `hb2-daily.xlsx`); B20 floating `MTGE.MBI.F`, 6m `MTGE.MBI.T07`, 1y `MTGE.MBI.T09`, 18m `INRL.MAL1.D18`, 2y `MTGE.MBI.T10`, 3y `MTGE.MBI.T11` (file `hb20.xlsx`).

## Review Focus

1. A PDF header with a wrong year (for example "25 January 2023" in a January 2024 issue) must not move the issue to the wrong year: the date closer to the upload date wins. Test in Task 1.
2. Real quotes from PDF text with broken words ("an d"), line breaks and curly quote marks must pass the quote check, and invented quotes must fail. Test in Task 4.
3. Running the download again must not download files that are already on disk, and must reject an HTML error page sent instead of a PDF. Test in Task 2.
4. A B20 month with no 18-month rate must use the mean of the 1-year and 2-year rates; any other missing rate must stop with a clear error. Test in Task 8.
5. A headline or quote that contains `<`, `&` or quote marks must show as plain text in the tooltip and the details panel, never as HTML. Manual check in Task 10.

## File Structure

```
pyproject.toml              uv project: dependencies and pytest settings
.gitignore                  ignores data/raw/, .venv/, caches
README.md                   how to run each step
scripts/__init__.py         makes scripts/ a package (empty)
scripts/issues.py           pure: dates from file names and PDF text, choose one PDF per date
scripts/fetch_issues.py     CLI: read the site's media list, download Tony's View PDFs
scripts/extract_text.py     CLI: PDF -> text, final issue dates -> data/raw/issues.json
scripts/records.py          pure: check one record against the rules
scripts/validate.py         CLI: check all (or some) records
scripts/rbnz.py             pure: read Reserve Bank xlsx series, find OCR changes
scripts/advice_score.py     pure: the "Was his advice good?" simulation
scripts/build_data.py       CLI: records + Reserve Bank data -> site/data.js
rules/extraction-rules.md   rule sheet for the helper agents
tests/test_*.py             pytest tests, one file per script module
data/raw/pdf/               downloaded PDFs + index.json        (git-ignored)
data/raw/text/              one text file per issue date         (git-ignored)
data/raw/issues.json        final list of issues                 (git-ignored)
data/raw/rbnz/              hb2-daily.xlsx, hb20.xlsx (owner downloads; git-ignored)
data/records/               one JSON record per issue (agents write these)
data/hand-check.md          result of the hand check of 10 records
site/index.html, style.css, app.js, vendor/echarts.min.js, data.js (generated)
```

Order: Tasks 1-6 make the records. Tasks 7-8 do not depend on Tasks 5-6 and can run while the agents work. Task 9 needs the two Reserve Bank files from the owner.

---

### Task 1: Project setup and issue dates

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `scripts/__init__.py`, `scripts/issues.py`
- Test: `tests/test_issues.py`

**Interfaces:**
- Consumes: nothing.
- Produces (in `scripts/issues.py`):
  - `MONTHS: dict[str, int]` (lower-case month name -> 1..12)
  - `@dataclass(frozen=True) class Pdf: file: str; url: str; uploaded: datetime`
  - `date_from_filename(name: str) -> date | None`
  - `date_from_text(text: str, head_chars: int = 600) -> date | None`
  - `resolve_date(file_date: date, header_date: date | None, uploaded: date) -> tuple[date, str | None]` (date, warning)
  - `tonys_view_pdfs(media: list[dict]) -> list[Pdf]` (media items have keys `date` ISO datetime and `source_url`)
  - `one_per_date(dated: list[tuple[date, Pdf]]) -> dict[date, Pdf]` (sorted by date, latest upload wins)

- [ ] **Step 1: Create the project files**

`pyproject.toml`:

```toml
[project]
name = "tonys-view-tracker"
version = "0.1.0"
description = "Charts of Tony Alexander's weekly borrower advice with the OCR and mortgage rates"
requires-python = ">=3.11"
dependencies = [
    "openpyxl>=3.1",
    "pypdf>=5.0",
]

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`.gitignore`:

```
data/raw/
.venv/
__pycache__/
.pytest_cache/
.DS_Store
```

`scripts/__init__.py`: an empty file.

Then run:

```bash
git init
uv sync
```

Expected: `uv sync` creates `.venv/` and `uv.lock` and installs openpyxl, pypdf and pytest.

- [ ] **Step 2: Write the failing tests**

`tests/test_issues.py`:

```python
from datetime import date, datetime

from scripts.issues import (
    Pdf,
    date_from_filename,
    date_from_text,
    one_per_date,
    resolve_date,
    tonys_view_pdfs,
)


def test_date_from_plain_filename():
    assert date_from_filename("Tonys-View-7-April-2022.pdf") == date(2022, 4, 7)


def test_date_from_filename_with_suffixes():
    assert date_from_filename("Tonys-View-2-July-2026-1.pdf") == date(2026, 7, 2)
    assert date_from_filename("Tonys-View-8-September-2022a.pdf") == date(2022, 9, 8)
    assert date_from_filename("Tonys-View-25-April-2024hik.pdf") == date(2024, 4, 25)


def test_premium_and_other_pdfs_have_no_issue_date():
    assert date_from_filename("Tview-Premium-2-February-2023.pdf") is None
    assert date_from_filename("TV-Spending-Plans-Survey-May-2022.pdf") is None


def test_impossible_date_is_not_an_issue():
    assert date_from_filename("Tonys-View-31-June-2023.pdf") is None


def test_date_from_header_text():
    text = "1\nInput to your Strategy\nISSN: 2703-2825  Thursday 7 April 2022\nSign up"
    assert date_from_text(text) == date(2022, 4, 7)
    assert date_from_text("ISSN: 2703-2825   13 June 2024") == date(2024, 6, 13)


def test_no_header_date_returns_none():
    assert date_from_text("No date here at all") is None


def test_resolve_date_same_dates_has_no_warning():
    d = date(2024, 6, 13)
    assert resolve_date(d, d, d) == (d, None)


def test_resolve_date_without_header_uses_file_name():
    d = date(2024, 6, 13)
    day, warning = resolve_date(d, None, d)
    assert day == d and "no date in the PDF header" in warning


def test_resolve_date_header_typo_in_year_uses_file_name():
    day, warning = resolve_date(date(2024, 1, 25), date(2023, 1, 25), date(2024, 1, 25))
    assert day == date(2024, 1, 25) and warning


def test_resolve_date_file_name_typo_uses_header():
    day, warning = resolve_date(date(2022, 6, 9), date(2022, 6, 23), date(2022, 6, 22))
    assert day == date(2022, 6, 23) and warning


def test_tonys_view_pdfs_skips_other_pdfs():
    media = [
        {"date": "2022-04-07T09:00:00", "source_url": "https://x/Tonys-View-7-April-2022.pdf"},
        {"date": "2023-02-02T09:00:00", "source_url": "https://x/Tview-Premium-2-February-2023.pdf"},
        {"date": "2022-05-01T09:00:00", "source_url": "https://x/TV-Spending-Plans-Survey-May-2022.pdf"},
    ]
    pdfs = tonys_view_pdfs(media)
    assert pdfs == [Pdf("Tonys-View-7-April-2022.pdf", "https://x/Tonys-View-7-April-2022.pdf",
                        datetime(2022, 4, 7, 9, 0))]


def test_one_per_date_keeps_latest_upload():
    a = Pdf("Tonys-View-9-June-2022-1.pdf", "u1", datetime(2022, 6, 9, 10))
    b = Pdf("Tonys-View-9-June-2022.pdf", "u2", datetime(2022, 6, 22, 10))
    c = Pdf("Tonys-View-7-April-2022.pdf", "u3", datetime(2022, 4, 7, 10))
    chosen = one_per_date([(date(2022, 6, 9), a), (date(2022, 6, 9), b), (date(2022, 4, 7), c)])
    assert list(chosen) == [date(2022, 4, 7), date(2022, 6, 9)]
    assert chosen[date(2022, 6, 9)].url == "u2"
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/test_issues.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.issues'`.

- [ ] **Step 4: Write the implementation**

`scripts/issues.py`:

```python
"""Find the Tony's View issues in the site's media list and give each one a date."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

MONTHS = {
    name: number
    for number, name in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"],
        start=1,
    )
}

# "Tonys-View-7-April-2022.pdf", also with "-1", "a" or "hik" before ".pdf".
# "Tview-Premium-..." (the paid newsletter) does not match.
_FILENAME = re.compile(r"^Tonys-View-(\d{1,2})-([A-Za-z]+)-(\d{4})[^/]*\.pdf$", re.IGNORECASE)
_HEADER_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b", re.IGNORECASE)


@dataclass(frozen=True)
class Pdf:
    file: str
    url: str
    uploaded: datetime


def _make_date(year: str, month_name: str, day: str) -> date | None:
    month = MONTHS.get(month_name.lower())
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def date_from_filename(name: str) -> date | None:
    m = _FILENAME.match(name)
    return _make_date(m.group(3), m.group(2), m.group(1)) if m else None


def date_from_text(text: str, head_chars: int = 600) -> date | None:
    """The first date in the top part of the issue, for example 'Thursday 7 April 2022'."""
    m = _HEADER_DATE.search(text[:head_chars])
    return _make_date(m.group(3), m.group(2), m.group(1)) if m else None


def resolve_date(file_date: date, header_date: date | None, uploaded: date) -> tuple[date, str | None]:
    """Choose the issue date. If the two dates differ, the one closer to the upload date wins."""
    if header_date is None:
        return file_date, f"{file_date}: no date in the PDF header, used the file name"
    if header_date == file_date:
        return file_date, None
    chosen = min((header_date, file_date), key=lambda d: abs((d - uploaded).days))
    return chosen, (f"{file_date}: PDF header says {header_date}, "
                    f"used {chosen} (closer to upload date {uploaded})")


def tonys_view_pdfs(media: list[dict]) -> list[Pdf]:
    pdfs = []
    for item in media:
        url = item["source_url"]
        name = url.rsplit("/", 1)[-1]
        if date_from_filename(name) is not None:
            pdfs.append(Pdf(name, url, datetime.fromisoformat(item["date"])))
    return sorted(pdfs, key=lambda p: p.uploaded)


def one_per_date(dated: list[tuple[date, Pdf]]) -> dict[date, Pdf]:
    """One PDF for each issue date: the latest upload wins."""
    latest: dict[date, Pdf] = {}
    for day, pdf in dated:
        if day not in latest or pdf.uploaded > latest[day].uploaded:
            latest[day] = pdf
    return {day: latest[day] for day in sorted(latest)}
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/test_issues.py -v`
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore scripts/__init__.py scripts/issues.py tests/test_issues.py docs/
git commit -m "feat: issue dates from Tony's View file names and PDF headers"
```

---

### Task 2: Download the PDFs

**Files:**
- Create: `scripts/fetch_issues.py`
- Test: `tests/test_fetch_issues.py`

**Interfaces:**
- Consumes: `Pdf`, `tonys_view_pdfs` from `scripts/issues.py`.
- Produces:
  - `fetch_media_list(get: Callable[[str], bytes]) -> list[dict]`
  - `download_missing(pdfs: list[Pdf], pdf_dir: Path, get: Callable[[str], bytes], pause: float = 1.0) -> int`
  - File `data/raw/pdf/index.json`: list of `{"file": str, "url": str, "uploaded": ISO datetime str}`.
  - Files `data/raw/pdf/<original file name>.pdf`.

- [ ] **Step 1: Write the failing tests**

`tests/test_fetch_issues.py`:

```python
import json
import urllib.error
from datetime import datetime

import pytest

from scripts.fetch_issues import download_missing, fetch_media_list
from scripts.issues import Pdf


def page_of(url: str) -> int:
    return int(url.rsplit("page=", 1)[1])


def test_fetch_media_list_reads_all_pages():
    pages = {1: [{"date": "d", "source_url": f"u{i}"} for i in range(100)],
             2: [{"date": "d", "source_url": "last"}]}
    calls = []

    def fake_get(url):
        calls.append(page_of(url))
        return json.dumps(pages[page_of(url)]).encode()

    assert len(fetch_media_list(fake_get)) == 101
    assert calls == [1, 2]


def test_fetch_media_list_stops_at_invalid_page_error():
    def fake_get(url):
        if page_of(url) == 1:
            return json.dumps([{"date": "d", "source_url": "u"}] * 100).encode()
        raise urllib.error.HTTPError(url, 400, "rest_post_invalid_page_number", None, None)

    assert len(fetch_media_list(fake_get)) == 100


def test_download_missing_skips_files_on_disk(tmp_path):
    (tmp_path / "Tonys-View-7-April-2022.pdf").write_bytes(b"%PDF old")
    pdfs = [Pdf("Tonys-View-7-April-2022.pdf", "u1", datetime(2022, 4, 7)),
            Pdf("Tonys-View-13-April-2022.pdf", "u2", datetime(2022, 4, 13))]
    fetched = []

    def fake_get(url):
        fetched.append(url)
        return b"%PDF new"

    assert download_missing(pdfs, tmp_path, fake_get, pause=0) == 1
    assert fetched == ["u2"]
    assert (tmp_path / "Tonys-View-7-April-2022.pdf").read_bytes() == b"%PDF old"


def test_download_missing_rejects_html_instead_of_pdf(tmp_path):
    pdfs = [Pdf("Tonys-View-7-April-2022.pdf", "u1", datetime(2022, 4, 7))]
    with pytest.raises(ValueError, match="did not return a PDF"):
        download_missing(pdfs, tmp_path, lambda url: b"<html>error</html>", pause=0)
    assert not (tmp_path / "Tonys-View-7-April-2022.pdf").exists()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_fetch_issues.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.fetch_issues'`.

- [ ] **Step 3: Write the implementation**

`scripts/fetch_issues.py`:

```python
"""Download every Tony's View PDF that is not yet on disk.

Run: uv run python -m scripts.fetch_issues
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from scripts.issues import Pdf, tonys_view_pdfs

MEDIA_URL = ("https://www.tonyalexander.nz/wp-json/wp/v2/media"
             "?mime_type=application/pdf&per_page=100&orderby=date&order=asc"
             "&_fields=date,source_url&page={page}")
PDF_DIR = Path("data/raw/pdf")
INDEX = PDF_DIR / "index.json"
USER_AGENT = "tonywebsite-personal-tracker/0.1 (personal, non-commercial)"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_media_list(get: Callable[[str], bytes] = _get) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        try:
            batch = json.loads(get(MEDIA_URL.format(page=page)))
        except urllib.error.HTTPError as error:
            if error.code == 400:  # WordPress: page number past the end
                return items
            raise
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


def download_missing(pdfs: list[Pdf], pdf_dir: Path, get: Callable[[str], bytes] = _get,
                     pause: float = 1.0) -> int:
    count = 0
    for pdf in pdfs:
        target = pdf_dir / pdf.file
        if target.exists():
            continue
        data = get(pdf.url)
        if not data.startswith(b"%PDF"):
            raise ValueError(f"{pdf.url} did not return a PDF")
        target.write_bytes(data)
        count += 1
        print("downloaded", pdf.file)
        time.sleep(pause)
    return count


def main() -> int:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = tonys_view_pdfs(fetch_media_list())
    count = download_missing(pdfs, PDF_DIR)
    INDEX.write_text(json.dumps(
        [{"file": p.file, "url": p.url, "uploaded": p.uploaded.isoformat()} for p in pdfs], indent=2))
    print(f"{len(pdfs)} Tony's View PDFs listed, {count} downloaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_fetch_issues.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the download**

Run: `uv run python -m scripts.fetch_issues`
Expected: about 4 minutes; the last line is `246 Tony's View PDFs listed, 246 downloaded` (the number can be a little higher if new issues came out). Run it again: `... 0 downloaded`.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_issues.py tests/test_fetch_issues.py
git commit -m "feat: download Tony's View PDFs from the site's media list"
```

---

### Task 3: Extract text and fix the issue dates

**Files:**
- Create: `scripts/extract_text.py`
- Test: `tests/test_extract_text.py`

**Interfaces:**
- Consumes: `Pdf`, `date_from_filename`, `date_from_text`, `resolve_date`, `one_per_date` from `scripts/issues.py`; `data/raw/pdf/index.json` from Task 2.
- Produces:
  - `pdf_to_text(path: Path) -> str`
  - `short_issues(issues: list[dict], min_chars: int = 2000) -> list[str]`
  - Files `data/raw/text/<YYYY-MM-DD>.txt`.
  - File `data/raw/issues.json`: list of `{"date": "YYYY-MM-DD", "pdf_url": str, "chars": int}`, sorted by date. Every later task uses this file as the list of issues.

- [ ] **Step 1: Write the failing test**

`tests/test_extract_text.py`:

```python
from scripts.extract_text import short_issues


def test_short_issues_lists_issues_with_little_text():
    issues = [{"date": "2022-04-07", "chars": 13641},
              {"date": "2022-04-13", "chars": 150},
              {"date": "2022-04-21", "chars": 0}]
    assert short_issues(issues) == ["2022-04-13", "2022-04-21"]
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run pytest tests/test_extract_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.extract_text'`.

- [ ] **Step 3: Write the implementation**

`scripts/extract_text.py`:

```python
"""Write the text of each issue to data/raw/text/ and the issue list to data/raw/issues.json.

Run: uv run python -m scripts.extract_text
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from scripts.issues import Pdf, date_from_filename, date_from_text, one_per_date, resolve_date

PDF_DIR = Path("data/raw/pdf")
TEXT_DIR = Path("data/raw/text")
ISSUES = Path("data/raw/issues.json")


def pdf_to_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def short_issues(issues: list[dict], min_chars: int = 2000) -> list[str]:
    """Issues with almost no text. A scanned PDF has no text for the agents to read."""
    return [i["date"] for i in issues if i["chars"] < min_chars]


def main() -> int:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    for old in TEXT_DIR.glob("*.txt"):
        old.unlink()
    index = json.loads((PDF_DIR / "index.json").read_text())
    pdfs = [Pdf(i["file"], i["url"], datetime.fromisoformat(i["uploaded"])) for i in index]

    dated, texts, failed = [], {}, []
    for pdf in pdfs:
        try:
            text = pdf_to_text(PDF_DIR / pdf.file)
        except Exception as error:  # a broken PDF must not stop the other issues
            print(f"ERROR {pdf.file}: {error}")
            failed.append(pdf.file)
            continue
        day, warning = resolve_date(date_from_filename(pdf.file), date_from_text(text), pdf.uploaded.date())
        if warning:
            print("WARNING", warning)
        dated.append((day, pdf))
        texts[pdf.file] = text

    chosen = one_per_date(dated)
    issues = []
    for day, pdf in chosen.items():
        text = texts[pdf.file]
        (TEXT_DIR / f"{day.isoformat()}.txt").write_text(text)
        issues.append({"date": day.isoformat(), "pdf_url": pdf.url, "chars": len(text)})
    ISSUES.write_text(json.dumps(issues, indent=2))

    print(f"{len(dated) - len(chosen)} duplicate PDFs dropped (latest upload kept)")
    short = short_issues(issues)
    if short:
        print("WARNING very little text, maybe a scanned PDF:", ", ".join(short))
    print(f"{len(issues)} issues written to {ISSUES}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run pytest tests/test_extract_text.py -v`
Expected: 1 passed.

- [ ] **Step 5: Run the extraction and read the warnings**

Run: `uv run python -m scripts.extract_text`
Expected: the last line is about `226 issues written to data/raw/issues.json`, with about 20 duplicates dropped and exit code 0.

Read every `WARNING` line. For each date warning, open the PDF and confirm that the chosen date is correct. If a choice is wrong, report it to the owner before you continue. Do not add special cases to the code without approval. If the "very little text" list is not empty, report those dates; the agents cannot read them.

- [ ] **Step 6: Commit**

```bash
git add scripts/extract_text.py tests/test_extract_text.py
git commit -m "feat: extract issue text and choose one PDF per issue date"
```

---

### Task 4: Record checker

**Files:**
- Create: `scripts/records.py`, `scripts/validate.py`
- Test: `tests/test_records.py`, `tests/test_validate.py`

**Interfaces:**
- Consumes: `data/raw/issues.json` and `data/raw/text/*.txt` from Task 3.
- Produces:
  - `scripts/records.py`: `GROUPS: set[str]`, `TERMS: set[int]`, `squash(text: str) -> str`, `quote_in_text(quote: str, text: str) -> bool`, `validate_record(rec: dict, text: str, expected_date: str, expected_url: str) -> list[str]`
  - `scripts/validate.py`: `check_all(issues: list[dict], records_dir: Path, text_dir: Path, only: set[str] | None = None) -> list[str]`; CLI `uv run python -m scripts.validate [--dates d1,d2,...]` prints `all records valid` and exits 0, or prints each problem and exits 1.

- [ ] **Step 1: Write the failing tests for one record**

`tests/test_records.py`:

```python
import pytest

from scripts.records import quote_in_text, validate_record

TEXT = """Retailing outlook gets worse
the results continue to paint a bad an d deteriorating picture
If I were a borrower, what
would I do?
If I were borrowing at the moment, I would take a
mix of 6 and 12 month fixed rates.
The lowest 2 year rate is 6.19% this week."""

ADVICE = "I would take a mix of 6 and 12 month fixed rates"
TONE_QUOTE = "paint a bad and deteriorating picture"


def good(**changes):
    rec = {
        "date": "2024-06-13",
        "pdf_url": "https://x/a.pdf",
        "headline": "Retailing outlook gets worse",
        "borrower": {"group": "mix", "terms_months": [6, 12], "quote": ADVICE},
        "tone": {"score": -2, "reason": "Spending keeps falling.", "quote": TONE_QUOTE},
        "lender_min_rates": {"24": 6.19},
        "notes": "",
    }
    rec.update(changes)
    return rec


def check(rec):
    return validate_record(rec, TEXT, "2024-06-13", "https://x/a.pdf")


def has(errors, text):
    return any(text in e for e in errors)


def test_good_record_passes():
    assert check(good()) == []


def test_quote_survives_broken_words_line_breaks_and_curly_quotes():
    assert quote_in_text("paint a bad and deteriorating", TEXT)
    assert quote_in_text("Tony’s “view”", "Tony's\n\"view\"")


def test_invented_quote_fails():
    rec = good(borrower={"group": "1y", "terms_months": [12], "quote": "I would fix for one year"})
    assert has(check(rec), "borrower.quote is not in the issue text")


def test_empty_quote_fails():
    assert not quote_in_text("   ", TEXT)


@pytest.mark.parametrize("borrower, message", [
    ({"group": "5y", "terms_months": [60]}, "is not permitted"),
    ({"group": "mix", "terms_months": [12]}, "two or more terms"),
    ({"group": "float", "terms_months": [12]}, "must be empty"),
    ({"group": "1y", "terms_months": [24]}, "first term must be 12"),
    ({"group": "3y_plus", "terms_months": [24]}, "36 months or more"),
    ({"group": "1y", "terms_months": [13]}, "permitted terms"),
    ({"group": "1y", "terms_months": "12"}, "permitted terms"),
])
def test_bad_borrower_fails(borrower, message):
    borrower["quote"] = ADVICE
    assert has(check(good(borrower=borrower)), message)


def test_mix_with_floating_part_passes():
    assert check(good(borrower={"group": "mix", "terms_months": [0, 12], "quote": ADVICE})) == []


def test_none_group_needs_no_quote():
    assert check(good(borrower={"group": "none", "terms_months": [], "quote": ""})) == []


@pytest.mark.parametrize("score", [3, -3, 1.5, "1", True, None])
def test_bad_tone_score_fails(score):
    rec = good(tone={"score": score, "reason": "r", "quote": TONE_QUOTE})
    assert has(check(rec), "tone.score")


def test_empty_tone_reason_fails():
    assert has(check(good(tone={"score": 0, "reason": " ", "quote": TONE_QUOTE})), "tone.reason")


def test_wrong_date_and_url_fail():
    errors = check(good(date="2024-06-14", pdf_url="https://x/b.pdf"))
    assert has(errors, "date is") and has(errors, "pdf_url")


def test_invented_headline_fails():
    assert has(check(good(headline="Something else")), "headline")


def test_lender_rate_not_in_text_fails():
    assert has(check(good(lender_min_rates={"24": 5.99})), "lender_min_rates[24]")


def test_lender_rate_bad_term_fails():
    assert has(check(good(lender_min_rates={"30": 6.19})), "term '30'")


def test_lender_rates_null_passes():
    assert check(good(lender_min_rates=None)) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_records.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.records'`.

- [ ] **Step 3: Write `scripts/records.py`**

```python
"""Check one agent record against the rules in rules/extraction-rules.md."""
from __future__ import annotations

import re

GROUPS = {"float", "6m", "1y", "18m", "2y", "3y_plus", "mix", "none"}
TERMS = {0, 6, 12, 18, 24, 36, 48, 60}  # months; 0 is a floating part of a mix
GROUP_FIRST_TERM = {"6m": 6, "1y": 12, "18m": 18, "2y": 24}
_SAME_MARKS = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def squash(text: str) -> str:
    """Text without whitespace, in lower case, with plain quote marks.

    PDF text can break lines anywhere and even split words ("an d"),
    so all whitespace is removed before quotes are compared.
    """
    return re.sub(r"\s+", "", text.translate(_SAME_MARKS)).lower()


def quote_in_text(quote: str, text: str) -> bool:
    return bool(str(quote).strip()) and squash(str(quote)) in squash(text)


def _rate_in_text(rate: float, text: str) -> bool:
    flat = squash(text)
    return f"{rate:.2f}" in flat or f"{rate:g}" in flat


def validate_record(rec: dict, text: str, expected_date: str, expected_url: str) -> list[str]:
    errors: list[str] = []

    def err(message: str) -> None:
        errors.append(f"{expected_date}: {message}")

    if rec.get("date") != expected_date:
        err(f"date is {rec.get('date')!r}, expected {expected_date}")
    if rec.get("pdf_url") != expected_url:
        err("pdf_url does not match data/raw/issues.json")
    if not quote_in_text(rec.get("headline", ""), text):
        err("headline is empty or not in the issue text")

    borrower = rec.get("borrower") or {}
    group, terms = borrower.get("group"), borrower.get("terms_months")
    if group not in GROUPS:
        err(f"borrower.group {group!r} is not permitted")
    if not isinstance(terms, list) or any(type(t) is not int or t not in TERMS for t in terms):
        err(f"borrower.terms_months {terms!r} is not a list of permitted terms")
    else:
        first = terms[0] if terms else None
        if group in ("float", "none") and terms:
            err(f"borrower.terms_months must be empty for group {group}")
        if group == "mix" and len(set(terms)) < 2:
            err("borrower.group mix needs two or more terms")
        if group in GROUP_FIRST_TERM and first != GROUP_FIRST_TERM[group]:
            err(f"borrower.terms_months: first term must be {GROUP_FIRST_TERM[group]} for group {group}")
        if group == "3y_plus" and (first is None or first < 36):
            err("borrower.group 3y_plus needs a first term of 36 months or more")
    if group != "none" and not quote_in_text(borrower.get("quote", ""), text):
        err("borrower.quote is not in the issue text")

    tone = rec.get("tone") or {}
    score = tone.get("score")
    if type(score) is not int or not -2 <= score <= 2:
        err(f"tone.score {score!r} must be an integer from -2 to 2")
    if not str(tone.get("reason", "")).strip():
        err("tone.reason is empty")
    if not quote_in_text(tone.get("quote", ""), text):
        err("tone.quote is not in the issue text")

    rates = rec.get("lender_min_rates")
    if rates is not None:
        if not isinstance(rates, dict) or not rates:
            err("lender_min_rates must be null or a non-empty object")
        else:
            for term, rate in rates.items():
                if not (str(term).isdigit() and int(term) in TERMS - {0}):
                    err(f"lender_min_rates term {term!r} is not permitted")
                if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 < rate < 15:
                    err(f"lender_min_rates[{term}] {rate!r} is not a rate")
                elif not _rate_in_text(float(rate), text):
                    err(f"lender_min_rates[{term}] {rate} is not in the issue text")
    return errors
```

- [ ] **Step 4: Run the record tests to see them pass**

Run: `uv run pytest tests/test_records.py -v`
Expected: all passed (25 tests with the parametrized cases).

- [ ] **Step 5: Write the failing tests for the whole set**

`tests/test_validate.py`:

```python
import json

from scripts.validate import check_all

TEXT = "Headline one\nIf I were a borrower I would fix for one year.\nThe economy is weak."


def record(day):
    return {"date": day, "pdf_url": f"https://x/{day}.pdf", "headline": "Headline one",
            "borrower": {"group": "1y", "terms_months": [12], "quote": "I would fix for one year"},
            "tone": {"score": -1, "reason": "Weak.", "quote": "The economy is weak."},
            "lender_min_rates": None, "notes": ""}


def setup(tmp_path, days, records):
    records_dir, text_dir = tmp_path / "records", tmp_path / "text"
    records_dir.mkdir()
    text_dir.mkdir()
    for day in days:
        (text_dir / f"{day}.txt").write_text(TEXT)
    for day, content in records.items():
        (records_dir / f"{day}.json").write_text(content)
    issues = [{"date": d, "pdf_url": f"https://x/{d}.pdf"} for d in days]
    return issues, records_dir, text_dir


def test_all_good(tmp_path):
    issues, rd, td = setup(tmp_path, ["2022-04-07"], {"2022-04-07": json.dumps(record("2022-04-07"))})
    assert check_all(issues, rd, td) == []


def test_missing_extra_and_broken_records(tmp_path):
    issues, rd, td = setup(tmp_path, ["2022-04-07", "2022-04-13"],
                           {"2022-04-13": "{not json", "2099-01-01": json.dumps(record("2099-01-01"))})
    errors = check_all(issues, rd, td)
    assert "2022-04-07: record is missing" in errors
    assert any(e.startswith("2022-04-13: not valid JSON") for e in errors)
    assert "2099-01-01: record has no matching issue" in errors


def test_only_checks_the_given_dates(tmp_path):
    issues, rd, td = setup(tmp_path, ["2022-04-07", "2022-04-13"],
                           {"2022-04-07": json.dumps(record("2022-04-07"))})
    assert check_all(issues, rd, td, only={"2022-04-07"}) == []
```

- [ ] **Step 6: Run them to see them fail**

Run: `uv run pytest tests/test_validate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.validate'`.

- [ ] **Step 7: Write `scripts/validate.py`**

```python
"""Check the records in data/records/ against data/raw/issues.json.

Run: uv run python -m scripts.validate                 (all records)
     uv run python -m scripts.validate --dates d1,d2   (only these dates)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.records import validate_record

ISSUES = Path("data/raw/issues.json")
TEXT_DIR = Path("data/raw/text")
RECORDS = Path("data/records")


def check_all(issues: list[dict], records_dir: Path, text_dir: Path,
              only: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    expected = {i["date"]: i for i in issues if only is None or i["date"] in only}
    if only is None:
        extra = {p.stem for p in records_dir.glob("*.json")} - expected.keys()
        errors += [f"{day}: record has no matching issue" for day in sorted(extra)]
    for day, issue in sorted(expected.items()):
        path = records_dir / f"{day}.json"
        if not path.exists():
            errors.append(f"{day}: record is missing")
            continue
        try:
            rec = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            errors.append(f"{day}: not valid JSON ({error})")
            continue
        text = (text_dir / f"{day}.txt").read_text()
        errors += validate_record(rec, text, day, issue["pdf_url"])
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the records in data/records/.")
    parser.add_argument("--dates", help="comma-separated issue dates to check (default: all)")
    args = parser.parse_args(argv)
    issues = json.loads(ISSUES.read_text())
    only = set(args.dates.split(",")) if args.dates else None
    if only:
        unknown = only - {i["date"] for i in issues}
        if unknown:
            print("unknown dates:", ", ".join(sorted(unknown)))
            return 1
    errors = check_all(issues, RECORDS, TEXT_DIR, only)
    for error in errors:
        print(error)
    print(f"{len(errors)} problems" if errors else "all records valid")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Run all tests to see them pass**

Run: `uv run pytest -v`
Expected: all passed.

- [ ] **Step 9: Commit**

```bash
git add scripts/records.py scripts/validate.py tests/test_records.py tests/test_validate.py
git commit -m "feat: check agent records, including word-for-word quotes"
```

---

### Task 5: Rule sheet and pilot run

**Files:**
- Create: `rules/extraction-rules.md`, `data/records/<6 pilot dates>.json` (written by one agent)

**Interfaces:**
- Consumes: `data/raw/issues.json`, `data/raw/text/*.txt` (Task 3); `scripts.validate` CLI (Task 4).
- Produces: the rule sheet that every agent in Task 6 follows; 6 valid pilot records.

- [ ] **Step 1: Write the rule sheet**

`rules/extraction-rules.md`:

````markdown
# Rule sheet: one record for one Tony's View issue

You read the text of one weekly "Tony's View" issue by Tony Alexander and write
one JSON record. Use only the text of that issue. Do not use your own knowledge
of the economy, and do not use other issues.

## Input

- `data/raw/text/<date>.txt` - the text of the issue. It comes from a PDF, so
  lines and even words can break in odd places ("an d").
- `data/raw/issues.json` - the `pdf_url` for each date.

## Output

Write `data/records/<date>.json` with exactly these fields:

```json
{
  "date": "2024-06-13",
  "pdf_url": "https://www.tonyalexander.nz/wp-content/uploads/Tonys-View-13-June-2024.pdf",
  "headline": "Retailing outlook gets worse",
  "borrower": {
    "group": "mix",
    "terms_months": [6, 12],
    "quote": "If I were borrowing at the moment, I would take a mix of 6 and 12 month fixed rates"
  },
  "tone": {
    "score": -2,
    "reason": "Spending plans and the housing market keep getting weaker.",
    "quote": "the results continue to paint a bad and deteriorating picture"
  },
  "lender_min_rates": null,
  "notes": ""
}
```

## Fields

### date, pdf_url

Copy them from `data/raw/issues.json`.

### headline

The title of the first article, word for word. It is the first line of text
after "Sign up for free at www.tonyalexander.nz".

### borrower

1. Find the section "If I were a borrower, what would I do?". It is usually in
   the second half of the issue.
2. Read the whole section. Most of it is commentary about interest rates. The
   advice is usually one or two sentences, for example "If I were borrowing at
   the moment, I would fix for one year."
3. Choose the group:

| group | Use when Tony says he would ... |
|---|---|
| `float` | stay on a floating rate |
| `6m` | fix for 6 months |
| `1y` | fix for 1 year (12 months) |
| `18m` | fix for 18 months |
| `2y` | fix for 2 years |
| `3y_plus` | fix for 3 years or longer |
| `mix` | split the loan across two or more terms |
| `none` | (the issue has no borrower section, or the section gives no advice) |

4. `terms_months`: every term that Tony names in the advice, in months, in the
   order he names them. Permitted values: 0 (a floating part), 6, 12, 18, 24,
   36, 48, 60. Use `[]` for `float` and `none`.
5. `quote`: the advice sentence, word for word, at most 300 characters. You can
   join words that are broken across lines. Use `""` for `none`.

Rules for hard cases:

- One choice with an alternative ("one year, or perhaps 18 months"): the group
  is the first term. `terms_months` lists both: `[12, 18]`.
- A split ("a mix of 6 and 12 month fixed rates", "spread across 1, 2 and 3
  years"): `mix`, with all terms: `[6, 12]`.
- Part floating, part fixed: `mix`, with 0 for the floating part: `[0, 12]`.
- Terms in words: "six months" = 6, "one year" = 12, "eighteen months" = 18,
  "two years" = 24, "three years" = 36.
- "My view is unchanged" without a term: `none`, and write
  "advice unchanged, term not stated" in `notes`.
- Do not copy advice from an earlier issue.

### tone

Read the whole issue. Score Tony's overall view of the New Zealand economy:
where it is now and where it goes in the next few months. Do not score world
markets.

| score | Meaning |
|---|---|
| -2 | Recession, a sharp fall, or a very bad outlook |
| -1 | Weak or getting weaker; mostly negative |
| 0 | Mixed or flat |
| +1 | Getting better; mostly positive |
| +2 | Strong growth or a clear boom |

- `score`: an integer (`-2`, `-1`, `0`, `1`, `2`), not a string.
- `reason`: one sentence in your own words, at most 20 words.
- `quote`: one sentence from the issue, word for word, that best supports the
  score.

### lender_min_rates

Only when the issue has Tony's table or list of the current lowest (minimum)
fixed mortgage rates that lenders charge. Record the term in months (as a
string key) and the rate (as a number), for example `{"24": 6.19, "36": 6.25}`.
Do not record forecasts, averages, swap rates, or one bank's rate that he
mentions in passing. In all other issues: `null`.

### notes

`""`, or one short sentence about something unusual, for example "No borrower
section this week".

## Check your work

Run:

```bash
uv run python -m scripts.validate --dates <your dates, comma-separated>
```

Fix every problem it reports, then run it again until it prints
`all records valid`. The most common problem is a quote that is not word for
word. Copy the quote from the text file again.
````

- [ ] **Step 2: Choose 6 pilot issues across the years**

Run:

```bash
uv run python - <<'EOF'
import json
from datetime import date
dates = [i["date"] for i in json.load(open("data/raw/issues.json"))]
def nearest(target):
    return min(dates, key=lambda d: abs((date.fromisoformat(d) - date.fromisoformat(target)).days))
print(",".join(sorted({dates[0], nearest("2022-11-24"), nearest("2023-08-01"),
                       nearest("2024-06-13"), nearest("2025-08-01"), dates[-1]})))
EOF
```

Expected: 6 comma-separated dates, starting with `2022-04-07`.

- [ ] **Step 3: Run one pilot agent**

Use the Agent tool: `subagent_type: "general-purpose"`, `model: "sonnet"`, with this prompt (put the 6 dates in both places):

```
You are extracting data from Tony Alexander's weekly "Tony's View" issues.
Working directory: /Users/sasha.fedorov/Projects/tonywebsite

1. Read rules/extraction-rules.md completely. Follow it exactly.
2. For each date below, read data/raw/text/<date>.txt and the pdf_url in
   data/raw/issues.json, then write data/records/<date>.json.
   Dates: <DATES>
3. Run: uv run python -m scripts.validate --dates <DATES>
   Fix every problem it reports. Run it again until it prints "all records valid".
4. Do not change any file except data/records/<date>.json for your dates.

Reply in at most 150 words: how many records you wrote, and each date where
you were not sure (the date and one line about why).
```

Expected: the agent reports 6 records and `all records valid`.

- [ ] **Step 4: Check the pilot records yourself**

For each pilot date, read `data/records/<date>.json` and the borrower section and the first article in `data/raw/text/<date>.txt`. Check:
1. The group and terms match the advice sentence.
2. The tone score is within 1 point of your own reading.
3. The headline is the first article title.

If a rule was unclear (the agent reported doubt, or a record is wrong), make the rule sheet clearer, delete the 6 pilot records, and repeat Step 3. Then run `uv run python -m scripts.validate --dates <DATES>` yourself.
Expected: `all records valid`, and all 6 records are correct.

- [ ] **Step 5: Commit**

```bash
git add rules/extraction-rules.md data/records/
git commit -m "feat: rule sheet for reading issues, with 6 pilot records"
```

---

### Task 6: Read all issues with helper agents, then hand-check

**Files:**
- Create: `data/records/<date>.json` for every issue, `data/hand-check.md`

**Interfaces:**
- Consumes: the rule sheet and pilot records (Task 5), `scripts.validate` (Task 4).
- Produces: one valid record for every date in `data/raw/issues.json`.

- [ ] **Step 1: Split the remaining dates into batches of 25**

Run:

```bash
uv run python - <<'EOF'
import json, pathlib
dates = [i["date"] for i in json.load(open("data/raw/issues.json"))
         if not pathlib.Path(f"data/records/{i['date']}.json").exists()]
for n in range(0, len(dates), 25):
    print(",".join(dates[n:n + 25]))
EOF
```

Expected: about 9 lines, each with up to 25 dates.

- [ ] **Step 2: Run one agent for each batch, all at the same time**

In one message, start one Agent call for each line from Step 1: `subagent_type: "general-purpose"`, `model: "sonnet"`, with the prompt from Task 5 Step 3 and that line as `<DATES>`. Each agent writes only its own files.

Expected: each agent reports `all records valid` for its batch. Collect every date that an agent was not sure about.

- [ ] **Step 3: Check the whole set**

Run: `uv run python -m scripts.validate`
Expected: `all records valid`. If there are problems, start one agent with the Task 5 prompt for only the dates that have problems, then run the check again.

- [ ] **Step 4: Review the dates the agents were not sure about**

For each of those dates, read the record and the text, and correct the record by hand if it is wrong. Then run `uv run python -m scripts.validate` again.
Expected: `all records valid`.

- [ ] **Step 5: Hand-check 10 random records**

Choose them:

```bash
uv run python - <<'EOF'
import json, random
dates = [i["date"] for i in json.load(open("data/raw/issues.json"))]
print(",".join(sorted(random.Random(2026).sample(dates, 10))))
EOF
```

For each date, read the borrower section and the whole issue text, and decide your own group and tone score before you look at the record. Write the result to `data/hand-check.md`:

```markdown
# Hand check of 10 random records

| Date | Record group | My group | Record tone | My tone | Pass |
|---|---|---|---|---|---|
| 2023-03-02 | 1y | 1y | -1 | -1 | yes |
```

A record passes if the group is the same and the tone is within 1 point.
Expected: at least 9 of 10 pass. If fewer pass, make the rule sheet clearer for the kind of mistake you found, delete all records except the pilot records, and repeat this task from Step 1.

- [ ] **Step 6: Commit**

```bash
git add data/records/ data/hand-check.md
git commit -m "feat: records for all Tony's View issues, with hand check"
```

---

### Task 7: Reserve Bank reader

**Files:**
- Create: `scripts/rbnz.py`
- Test: `tests/test_rbnz.py`

**Interfaces:**
- Consumes: nothing (tests make their own small xlsx files).
- Produces (in `scripts/rbnz.py`):
  - Constants `OCR`, `SWAP_1Y`, `SWAP_3Y` (str) and `B20: dict[str, str]` with keys `"float"`, `"6m"`, `"1y"`, `"18m"`, `"2y"`, `"3y"` -> series ID.
  - `Series = list[tuple[date, float]]`
  - `read_series(path: Path, series_ids: list[str]) -> dict[str, Series]`
  - `ocr_changes(daily: Series, start: date) -> list[dict]`: items `{"date": "YYYY-MM-DD", "rate": float, "change": float | None}`; the first item is the OCR in force on `start` with `change: None`.
  - `since(series: Series, start: date) -> list[list]`: `[["YYYY-MM-DD", value], ...]` for dates on or after `start`.

- [ ] **Step 1: Write the failing tests**

`tests/test_rbnz.py`:

```python
from datetime import date, datetime

import openpyxl
import pytest

from scripts import rbnz


def make_xlsx(path, ids, rows):
    """A small file with the same layout as the Reserve Bank files."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append([None] + ["Group"] * len(ids))
    ws.append([None] + [f"name {i}" for i in ids])
    ws.append(["Notes"] + [None] * len(ids))
    ws.append(["Unit"] + ["%pa"] * len(ids))
    ws.append(["Series Id"] + ids)
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def test_read_series_finds_columns_by_id_and_skips_blanks(tmp_path):
    path = make_xlsx(tmp_path / "b2.xlsx", ["X.OTHER", rbnz.OCR, rbnz.SWAP_1Y], [
        [datetime(2022, 4, 7), 9.9, 1.0, 2.5],
        [datetime(2022, 4, 8), 9.9, 1.0, None],
        ["Source: RBNZ", None, None, None],
    ])
    out = rbnz.read_series(path, [rbnz.OCR, rbnz.SWAP_1Y])
    assert out[rbnz.OCR] == [(date(2022, 4, 7), 1.0), (date(2022, 4, 8), 1.0)]
    assert out[rbnz.SWAP_1Y] == [(date(2022, 4, 7), 2.5)]


def test_read_series_fails_for_unknown_id(tmp_path):
    path = make_xlsx(tmp_path / "b2.xlsx", [rbnz.OCR], [[datetime(2022, 4, 7), 1.0]])
    with pytest.raises(ValueError, match="series not found"):
        rbnz.read_series(path, ["NOT.THERE"])


def test_ocr_changes_start_with_the_rate_in_force():
    daily = [(date(2022, 2, 24), 1.0), (date(2022, 4, 6), 1.0), (date(2022, 4, 14), 1.5),
             (date(2022, 4, 15), 1.5), (date(2022, 5, 26), 2.0), (date(2023, 1, 5), 2.0)]
    assert rbnz.ocr_changes(daily, date(2022, 4, 7)) == [
        {"date": "2022-04-07", "rate": 1.0, "change": None},
        {"date": "2022-04-14", "rate": 1.5, "change": 0.5},
        {"date": "2022-05-26", "rate": 2.0, "change": 0.5},
    ]


def test_ocr_cut_is_negative():
    daily = [(date(2024, 8, 1), 5.5), (date(2024, 8, 15), 5.25)]
    assert rbnz.ocr_changes(daily, date(2024, 8, 1))[1] == {"date": "2024-08-15", "rate": 5.25, "change": -0.25}


def test_since_keeps_dates_from_start():
    series = [(date(2022, 4, 6), 2.7), (date(2022, 4, 7), 2.96)]
    assert rbnz.since(series, date(2022, 4, 7)) == [["2022-04-07", 2.96]]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_rbnz.py -v`
Expected: FAIL with `ImportError: cannot import name 'rbnz' from 'scripts'`.

- [ ] **Step 3: Write the implementation**

`scripts/rbnz.py`:

```python
"""Read series from Reserve Bank of New Zealand xlsx files (B2 daily, B20 monthly).

Layout of the "Data" sheet: header rows, one of them starts with "Series Id"
and holds the series IDs; each data row starts with a date in column A.
"""
from __future__ import annotations

import warnings
from datetime import date, datetime
from pathlib import Path

import openpyxl

OCR = "INM.DP1.N"
SWAP_1Y = "INM.DS01.NZZC"
SWAP_3Y = "INM.DS03.NZZC"
B20 = {
    "float": "MTGE.MBI.F",
    "6m": "MTGE.MBI.T07",
    "1y": "MTGE.MBI.T09",
    "18m": "INRL.MAL1.D18",
    "2y": "MTGE.MBI.T10",
    "3y": "MTGE.MBI.T11",
}

Series = list[tuple[date, float]]


def read_series(path: Path, series_ids: list[str]) -> dict[str, Series]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the files have no default style
        sheet = openpyxl.load_workbook(path, data_only=True)["Data"]
    columns: dict[str, int] | None = None
    out: dict[str, Series] = {sid: [] for sid in series_ids}
    for row in sheet.iter_rows(values_only=True):
        if row[0] == "Series Id":
            ids = list(row)
            missing = [sid for sid in series_ids if sid not in ids]
            if missing:
                raise ValueError(f"{path.name}: series not found: {missing}")
            columns = {sid: ids.index(sid) for sid in series_ids}
            continue
        if columns is None or not isinstance(row[0], datetime):
            continue
        for sid, col in columns.items():
            value = row[col]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[sid].append((row[0].date(), float(value)))
    if columns is None:
        raise ValueError(f"{path.name}: no 'Series Id' row")
    return out


def ocr_changes(daily: Series, start: date) -> list[dict]:
    """The OCR in force on `start`, then each later day the OCR changed."""
    out: list[dict] = []
    previous = None
    for day, rate in daily:
        if rate == previous:
            continue
        if day <= start:
            out = [{"date": start.isoformat(), "rate": rate, "change": None}]
        else:
            change = None if previous is None else round(rate - previous, 2)
            out.append({"date": day.isoformat(), "rate": rate, "change": change})
        previous = rate
    return out


def since(series: Series, start: date) -> list[list]:
    return [[day.isoformat(), value] for day, value in series if day >= start]
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_rbnz.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/rbnz.py tests/test_rbnz.py
git commit -m "feat: read OCR, swap and mortgage rate series from Reserve Bank files"
```

---

### Task 8: Advice score

**Files:**
- Create: `scripts/advice_score.py`
- Test: `tests/test_advice_score.py`

**Interfaces:**
- Consumes: record shape from Task 4 (`date`, `borrower.group`, `borrower.terms_months`); B20 keys from Task 7 (`"float"`, `"6m"`, `"1y"`, `"18m"`, `"2y"`, `"3y"`).
- Produces (in `scripts/advice_score.py`):
  - `advice_terms(group: str, terms: list[int]) -> list[int] | None`
  - `rate_for(rates: dict[str, dict[str, float]], term: int, month: str) -> float` (`month` is `"YYYY-MM"`)
  - `run_strategy(months: list[str], terms_for: Callable[[str], list[int]], rates: dict[str, dict[str, float]], loan: float) -> list[float]` (total interest at the end of each month)
  - `latest_advice(records: list[dict]) -> Callable[[str], list[int]]`
  - `score(records: list[dict], b20: dict[str, list[tuple[date, float]]], loan: float) -> dict` with keys `loan`, `months` (`"YYYY-MM"` list), `tony`, `fix_1y`, `float` (lists of totals, same length as `months`).

- [ ] **Step 1: Write the failing tests**

`tests/test_advice_score.py`:

```python
from datetime import date

import pytest

from scripts.advice_score import advice_terms, latest_advice, rate_for, run_strategy, score

M = ["2022-04", "2022-05", "2022-06"]


def flat(rate_by_key, months):
    return {key: {m: rate for m in months} for key, rate in rate_by_key.items()}


def rec(day, group, terms):
    return {"date": day, "borrower": {"group": group, "terms_months": terms}}


def test_always_fix_1y_pays_the_1y_rate():
    rates = flat({"1y": 12.0, "float": 6.0}, M)
    assert run_strategy(M, lambda m: [12], rates, 100_000) == [1000.0, 2000.0, 3000.0]


def test_always_float_pays_the_floating_rate():
    rates = flat({"1y": 12.0, "float": 6.0}, M)
    assert run_strategy(M, lambda m: [0], rates, 100_000) == [500.0, 1000.0, 1500.0]


def test_floating_part_is_fixed_when_advice_changes():
    rates = flat({"1y": 12.0, "float": 6.0}, M)
    advice = {"2022-04": [0], "2022-05": [12], "2022-06": [12]}
    assert run_strategy(M, advice.get, rates, 100_000) == [500.0, 1500.0, 2500.0]


def test_fixed_part_keeps_its_rate_until_the_term_ends():
    months = [f"2022-{m:02d}" for m in range(1, 9)]
    rates = {"6m": {m: (12.0 if m < "2022-07" else 6.0) for m in months}}
    totals = run_strategy(months, lambda m: [6], rates, 100_000)
    assert totals == [1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0, 6500.0, 7000.0]


def test_mix_splits_the_loan_evenly():
    rates = flat({"6m": 12.0, "1y": 6.0}, M[:1])
    assert run_strategy(M[:1], lambda m: [6, 12], rates, 100_000) == [750.0]


def test_advice_terms():
    assert advice_terms("none", []) is None
    assert advice_terms("float", []) == [0]
    assert advice_terms("1y", [12, 18]) == [12]
    assert advice_terms("3y_plus", [60]) == [36]
    assert advice_terms("mix", [12, 6, 60, 0]) == [0, 6, 12, 36]


def test_missing_18m_rate_uses_mean_of_1y_and_2y():
    rates = {"1y": {"2022-04": 5.0}, "2y": {"2022-04": 6.0}}
    assert rate_for(rates, 18, "2022-04") == 5.5


def test_other_missing_rate_is_an_error():
    with pytest.raises(ValueError, match="no 2y rate for 2022-04"):
        rate_for({"1y": {"2022-04": 5.0}}, 24, "2022-04")


def test_latest_advice_keeps_earlier_advice_for_none_and_starts_with_1y():
    terms_for = latest_advice([rec("2022-05-05", "float", []), rec("2022-06-02", "none", [])])
    assert terms_for("2022-04") == [12]
    assert terms_for("2022-05") == [0]
    assert terms_for("2022-06") == [0]


def test_score_runs_three_strategies_from_the_first_issue_month():
    b20 = {
        "1y": [(date(2022, 3, 31), 9.0), (date(2022, 4, 30), 12.0), (date(2022, 5, 31), 12.0)],
        "float": [(date(2022, 3, 31), 9.0), (date(2022, 4, 30), 6.0), (date(2022, 5, 31), 6.0)],
    }
    result = score([rec("2022-04-07", "float", [])], b20, 100_000)
    assert result["months"] == ["2022-04", "2022-05"]
    assert result["tony"] == [500.0, 1000.0]
    assert result["fix_1y"] == [1000.0, 2000.0]
    assert result["float"] == [500.0, 1000.0]
    assert result["loan"] == 100_000
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_advice_score.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.advice_score'`.

- [ ] **Step 3: Write the implementation**

`scripts/advice_score.py`:

```python
"""The "Was his advice good?" score (spec section 8).

An interest-only loan. Each time a fixed part ends, it is split evenly across
the terms in Tony's latest advice and fixed at that month's B20 rate.
A floating part (term 0) is checked again every month.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

RATE_KEY = {0: "float", 6: "6m", 12: "1y", 18: "18m", 24: "2y", 36: "3y"}
LONGEST = 36  # a longer term is fixed for 3 years at the 3-year rate
DEFAULT_TERMS = [12]  # before the first advice


@dataclass
class Part:
    amount: float
    rate: float  # percent per year
    left: int  # months until the fixed rate ends; 0 = due now (always 0 for floating)


def advice_terms(group: str, terms: list[int]) -> list[int] | None:
    """The terms that one record tells a borrower to fix for. None means no advice."""
    if group == "none":
        return None
    if group == "float":
        return [0]
    if group == "3y_plus":
        return [LONGEST]
    if group == "mix":
        return sorted({min(t, LONGEST) for t in terms})
    return [min(terms[0], LONGEST)]


def rate_for(rates: dict[str, dict[str, float]], term: int, month: str) -> float:
    key = RATE_KEY[term]
    value = rates.get(key, {}).get(month)
    if value is not None:
        return value
    if term == 18:
        return (rate_for(rates, 12, month) + rate_for(rates, 24, month)) / 2
    raise ValueError(f"B20 has no {key} rate for {month}")


def run_strategy(months: list[str], terms_for: Callable[[str], list[int]],
                 rates: dict[str, dict[str, float]], loan: float) -> list[float]:
    """Total interest paid up to the end of each month."""
    parts: list[Part] = []
    total = 0.0
    totals = []
    for month in months:
        due = loan if not parts else sum(p.amount for p in parts if p.left == 0)
        parts = [p for p in parts if p.left > 0]
        if due:
            wanted = terms_for(month)
            for term in wanted:
                parts.append(Part(due / len(wanted), rate_for(rates, term, month), term))
        for part in parts:
            total += part.amount * part.rate / 100 / 12
            part.left = max(part.left - 1, 0)
        totals.append(round(total, 2))
    return totals


def latest_advice(records: list[dict]) -> Callable[[str], list[int]]:
    """For a month: the advice of the last issue in or before that month.

    Advice "none" keeps the earlier advice. Before any advice: fix for 1 year.
    """
    timeline: list[tuple[str, list[int]]] = []
    current = DEFAULT_TERMS
    for record in sorted(records, key=lambda r: r["date"]):
        terms = advice_terms(record["borrower"]["group"], record["borrower"]["terms_months"])
        if terms is not None:
            current = terms
        timeline.append((record["date"][:7], current))

    def terms_for(month: str) -> list[int]:
        found = DEFAULT_TERMS
        for issue_month, terms in timeline:
            if issue_month > month:
                break
            found = terms
        return found

    return terms_for


def score(records: list[dict], b20: dict[str, list[tuple[date, float]]], loan: float) -> dict:
    rates = {key: {day.strftime("%Y-%m"): value for day, value in series} for key, series in b20.items()}
    first = min(r["date"] for r in records)[:7]
    months = sorted(m for m in rates["1y"] if m >= first)
    return {
        "loan": loan,
        "months": months,
        "tony": run_strategy(months, latest_advice(records), rates, loan),
        "fix_1y": run_strategy(months, lambda m: [12], rates, loan),
        "float": run_strategy(months, lambda m: [0], rates, loan),
    }
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_advice_score.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/advice_score.py tests/test_advice_score.py
git commit -m "feat: advice score compares Tony's advice with fixing 1 year and floating"
```

---

### Task 9: Build the data file

**Files:**
- Create: `scripts/build_data.py`
- Test: `tests/test_build_data.py`
- Generated: `site/data.js`

**Interfaces:**
- Consumes: `scripts.rbnz` (Task 7), `scripts.advice_score.score` (Task 8), `scripts.validate.check_all` (Task 4), records (Task 6).
- Produces:
  - `strip_quotes(records: list[dict]) -> list[dict]` (a copy without `borrower.quote` and `tone.quote`)
  - `build_payload(records: list[dict], b2: dict[str, Series], b20: dict[str, Series], include_quotes: bool) -> dict`
  - `to_js(payload: dict) -> str`
  - `site/data.js`: `window.TONY_DATA = {...};` with keys:
    - `quotes`: bool
    - `issues`: list of records sorted by date
    - `ocr`: list of `{date, rate, change}` (Task 7 `ocr_changes`)
    - `ocr_last`: `{date, rate}` (the last day in the B2 file)
    - `swap`: `{"y1": [[date, value], ...], "y3": [...]}`
    - `mortgage`: `{"1y": [[date, value], ...], "2y": [...], "3y": [...]}` (month-end dates)
    - `score`: output of `advice_score.score`

- [ ] **Step 1: Write the failing tests**

`tests/test_build_data.py`:

```python
import json
from datetime import date

from scripts import rbnz
from scripts.build_data import build_payload, to_js

QUOTE = "I would fix 1 year"


def records():
    return [{"date": "2022-04-07", "pdf_url": "u1", "headline": "H1",
             "borrower": {"group": "1y", "terms_months": [12], "quote": QUOTE},
             "tone": {"score": -1, "reason": "Weak.", "quote": "weak outlook"},
             "lender_min_rates": None, "notes": ""}]


def series():
    b2 = {rbnz.OCR: [(date(2022, 2, 24), 1.0), (date(2022, 4, 14), 1.5)],
          rbnz.SWAP_1Y: [(date(2022, 4, 6), 2.7), (date(2022, 4, 7), 2.96)],
          rbnz.SWAP_3Y: [(date(2022, 4, 7), 3.66)]}
    b20 = {key: [(date(2022, 4, 30), 4.0), (date(2022, 5, 31), 4.5)] for key in rbnz.B20}
    return b2, b20


def test_payload_holds_every_chart_input():
    b2, b20 = series()
    p = build_payload(records(), b2, b20, include_quotes=True)
    assert p["ocr"] == [{"date": "2022-04-07", "rate": 1.0, "change": None},
                        {"date": "2022-04-14", "rate": 1.5, "change": 0.5}]
    assert p["ocr_last"] == {"date": "2022-04-14", "rate": 1.5}
    assert p["swap"] == {"y1": [["2022-04-07", 2.96]], "y3": [["2022-04-07", 3.66]]}
    assert p["mortgage"]["2y"] == [["2022-04-30", 4.0], ["2022-05-31", 4.5]]
    assert p["score"]["months"] == ["2022-04", "2022-05"]
    assert p["issues"][0]["borrower"]["quote"] == QUOTE
    assert p["quotes"] is True


def test_no_quotes_removes_every_quote_but_keeps_the_reason():
    b2, b20 = series()
    p = build_payload(records(), b2, b20, include_quotes=False)
    issue = p["issues"][0]
    assert "quote" not in issue["borrower"] and "quote" not in issue["tone"]
    assert issue["tone"]["reason"] == "Weak."
    assert p["quotes"] is False
    assert QUOTE not in to_js(p)


def test_no_quotes_does_not_change_the_input_records():
    recs = records()
    b2, b20 = series()
    build_payload(recs, b2, b20, include_quotes=False)
    assert recs[0]["borrower"]["quote"] == QUOTE


def test_to_js_is_a_script_that_holds_json():
    js = to_js({"a": "Tony’s \"view\" <b>"})
    prefix = "window.TONY_DATA = "
    assert js.startswith(prefix) and js.endswith(";\n")
    assert json.loads(js[len(prefix):-2]) == {"a": "Tony’s \"view\" <b>"}
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_build_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_data'`.

- [ ] **Step 3: Write the implementation**

`scripts/build_data.py`:

```python
"""Combine the records and the Reserve Bank files into site/data.js.

Run: uv run python -m scripts.build_data              (with Tony's quotes)
     uv run python -m scripts.build_data --no-quotes  (for a public site)
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date
from pathlib import Path

from scripts import rbnz
from scripts.advice_score import score
from scripts.validate import ISSUES, RECORDS, TEXT_DIR, check_all

B2_FILE = Path("data/raw/rbnz/hb2-daily.xlsx")
B20_FILE = Path("data/raw/rbnz/hb20.xlsx")
OUT = Path("site/data.js")
LOAN = 500_000
RBNZ_URLS = [
    "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx",
    "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b20/hb20.xlsx",
]


def strip_quotes(records: list[dict]) -> list[dict]:
    out = copy.deepcopy(records)
    for record in out:
        record["borrower"].pop("quote", None)
        record["tone"].pop("quote", None)
    return out


def build_payload(records: list[dict], b2: dict, b20: dict, include_quotes: bool) -> dict:
    records = sorted(records, key=lambda r: r["date"])
    start = date.fromisoformat(records[0]["date"])
    ocr = b2[rbnz.OCR]
    return {
        "quotes": include_quotes,
        "issues": copy.deepcopy(records) if include_quotes else strip_quotes(records),
        "ocr": rbnz.ocr_changes(ocr, start),
        "ocr_last": {"date": ocr[-1][0].isoformat(), "rate": ocr[-1][1]},
        "swap": {"y1": rbnz.since(b2[rbnz.SWAP_1Y], start), "y3": rbnz.since(b2[rbnz.SWAP_3Y], start)},
        "mortgage": {key: rbnz.since(b20[key], start) for key in ("1y", "2y", "3y")},
        "score": score(records, b20, LOAN),
    }


def to_js(payload: dict) -> str:
    return "window.TONY_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build site/data.js.")
    parser.add_argument("--no-quotes", action="store_true", help="leave out all quotes from Tony's issues")
    args = parser.parse_args(argv)

    missing = [str(p) for p in (B2_FILE, B20_FILE) if not p.exists()]
    if missing:
        print("Missing Reserve Bank files:", ", ".join(missing))
        print("Download them in a browser (the site blocks scripts) into data/raw/rbnz/:")
        for url in RBNZ_URLS:
            print("  " + url)
        return 2

    errors = check_all(json.loads(ISSUES.read_text()), RECORDS, TEXT_DIR)
    if errors:
        print(f"{len(errors)} record problems. Run: uv run python -m scripts.validate")
        return 1

    records = [json.loads(p.read_text()) for p in sorted(RECORDS.glob("*.json"))]
    b2 = rbnz.read_series(B2_FILE, [rbnz.OCR, rbnz.SWAP_1Y, rbnz.SWAP_3Y])
    by_id = rbnz.read_series(B20_FILE, list(rbnz.B20.values()))
    b20 = {key: by_id[sid] for key, sid in rbnz.B20.items()}

    payload = build_payload(records, b2, b20, include_quotes=not args.no_quotes)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(to_js(payload))
    print(f"wrote {OUT}: {len(records)} issues, quotes {'off' if args.no_quotes else 'on'}, "
          f"OCR to {payload['ocr_last']['date']}, B20 to {payload['score']['months'][-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest -v`
Expected: all passed.

- [ ] **Step 5: Get the Reserve Bank files**

Run: `ls data/raw/rbnz/`
Expected: `hb2-daily.xlsx  hb20.xlsx`. If a file is missing, ask the owner to download it in a browser (URLs in `RBNZ_URLS`) into `data/raw/rbnz/`, and wait. Do not use another source without the owner's approval.

- [ ] **Step 6: Build and check the OCR changes**

Run:

```bash
uv run python -m scripts.build_data
uv run python - <<'EOF'
import json
d = json.loads(open("site/data.js").read()[len("window.TONY_DATA = "):-2])
for o in d["ocr"]:
    print(o)
print("last", d["ocr_last"])
EOF
```

Expected: the build line ends with `OCR to 2026-...` (a date in the last few weeks) and `B20 to 2026-...`. The OCR list starts with `{'date': '2022-04-07', 'rate': 1.0, 'change': None}` and includes `{'date': '2022-11-24', 'rate': 4.25, 'change': 0.75}` and `{'date': '2024-08-15', 'rate': 5.25, 'change': -0.25}`.

- [ ] **Step 7: Commit**

```bash
git add scripts/build_data.py tests/test_build_data.py site/data.js
git commit -m "feat: build site data from records and Reserve Bank files"
```

---

### Task 10: The page

**Files:**
- Create: `site/index.html`, `site/style.css`, `site/app.js`, `site/vendor/echarts.min.js`

**Interfaces:**
- Consumes: `window.TONY_DATA` from `site/data.js` (shape in Task 9).
- Produces: the finished page.

- [ ] **Step 1: Load the dataviz skill**

Use the Skill tool with `dataviz`. Keep the structure below. You can change the colour tokens in `style.css` and the mark sizes in `app.js` to follow the skill. Do not change the data shape or the chart order.

- [ ] **Step 2: Save ECharts locally**

```bash
mkdir -p site/vendor
curl -sL -o site/vendor/echarts.min.js https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js
head -c 120 site/vendor/echarts.min.js; echo; wc -c site/vendor/echarts.min.js
```

Expected: the file starts with a licence comment and is about 1 MB.

- [ ] **Step 3: Write `site/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tony's View Tracker</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>Tony's View tracker</h1>
    <p class="sub">Tony Alexander's weekly borrower advice and economic tone, with the OCR, swap rates and mortgage rates. <span id="range"></span></p>
  </header>
  <section id="summary" class="tiles" aria-label="Latest values"></section>
  <div id="advice-legend" class="legend" aria-label="Advice colours"></div>
  <main>
    <div id="chart" role="img" aria-label="Stacked charts: rates, borrower advice, economic tone and advice score over time"></div>
    <aside id="details" hidden>
      <button id="close" type="button" aria-label="Close details">×</button>
      <h2 id="d-headline"></h2>
      <p class="meta"><span id="d-date"></span> · <a id="d-pdf" target="_blank" rel="noopener">Open the PDF</a></p>
      <h3>If I were a borrower</h3>
      <p id="d-advice"></p>
      <blockquote id="d-advice-quote"></blockquote>
      <h3>Economy tone</h3>
      <p id="d-tone"></p>
      <blockquote id="d-tone-quote"></blockquote>
    </aside>
  </main>
  <footer>
    <label>Loan for the advice score: $<input id="loan" type="number" min="10000" step="10000" value="500000"></label>
    <p class="note">Mortgage rates are Reserve Bank monthly averages of advertised (carded) rates, not special rates. The advice score assumes an interest-only loan with no break fees. Tone scores and advice groups were read from each issue by an AI; click a week to see the source. Sources: tonyalexander.nz, Reserve Bank of New Zealand (B2, B20).</p>
  </footer>
  <script src="vendor/echarts.min.js"></script>
  <script src="data.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Write `site/style.css`**

```css
:root {
  color-scheme: light dark;
  --bg: #ffffff; --fg: #1d2330; --muted: #5d6675; --grid: #e3e6eb; --panel: #f6f7f9;
  --ocr: #1d2330; --m1: #2563eb; --m2: #7c3aed; --m3: #c2410c; --table: #0f766e;
  --pos: #2e8b57; --neg: #c0392b; --tony: #2563eb; --fix1: #7c3aed; --float: #c2410c;
  --g-float: #fcd34d; --g-6m: #bfdbfe; --g-1y: #60a5fa; --g-18m: #2563eb; --g-2y: #1e40af;
  --g-3y_plus: #172554; --g-mix: #c084fc; --g-none: #d1d5db;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151b; --fg: #e6e8ec; --muted: #9aa3b2; --grid: #2a2f39; --panel: #1a1e26;
    --ocr: #e6e8ec; --m1: #6ea8ff; --m2: #b18cff; --m3: #ff8a4c; --table: #2dd4bf;
    --pos: #4cc38a; --neg: #ff6b5e; --tony: #6ea8ff; --fix1: #b18cff; --float: #ff8a4c;
    --g-float: #b45309; --g-6m: #1e3a8a; --g-1y: #1d4ed8; --g-18m: #3b82f6; --g-2y: #93c5fd;
    --g-3y_plus: #dbeafe; --g-mix: #a855f7; --g-none: #3f4653;
  }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--fg);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
header h1 { margin: 0 0 4px; font-size: 22px; }
.sub, .note, .meta { color: var(--muted); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }
.tile { background: var(--panel); border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; }
.tile .label, .tile .note { font-size: 12px; color: var(--muted); }
.tile .value { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; color: var(--muted); margin: 0 0 8px; }
.legend i { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
#chart { width: 100%; height: 880px; }
#details { position: fixed; top: 16px; right: 16px; bottom: 16px; width: min(420px, calc(100vw - 32px));
  overflow: auto; background: var(--panel); border: 1px solid var(--grid); border-radius: 10px;
  padding: 16px 18px; box-shadow: 0 8px 30px rgb(0 0 0 / 0.2); }
#details h2 { font-size: 18px; margin: 0 28px 4px 0; }
#details h3 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin: 18px 0 4px; }
#details blockquote { margin: 6px 0 0; padding-left: 10px; border-left: 3px solid var(--grid); font-style: italic; }
#close { position: absolute; top: 8px; right: 10px; border: 0; background: none; color: var(--fg); font-size: 22px; cursor: pointer; }
footer { margin-top: 12px; font-size: 13px; }
footer input { width: 120px; font: inherit; }
a { color: var(--m1); }
.hint { color: var(--muted); font-size: 11px; }
```

- [ ] **Step 5: Write `site/app.js`**

```js
/* Tony's View tracker: draws the stacked charts from window.TONY_DATA (site/data.js). */
(function () {
  "use strict";

  const D = window.TONY_DATA;
  if (!D || !window.echarts) {
    document.getElementById("chart").textContent =
      "Data or chart library missing. Run: uv run python -m scripts.build_data";
    return;
  }

  const GROUPS = ["float", "6m", "1y", "18m", "2y", "3y_plus", "mix", "none"];
  const GROUP_LABEL = {
    float: "Float", "6m": "6 months", "1y": "1 year", "18m": "18 months",
    "2y": "2 years", "3y_plus": "3+ years", mix: "Mix", none: "No advice",
  };
  const TERM_LABEL = { 0: "float", 6: "6m", 12: "1y", 18: "18m", 24: "2y", 36: "3y", 48: "4y", 60: "5y" };
  const DAY_MS = 86400000;
  // Pixel layout of the stacked charts. The chart box is 880px high (style.css).
  const GRID = [
    { top: 72, height: 270 },  // rates
    { top: 376, height: 34 },  // advice strip
    { top: 446, height: 150 }, // tone
    { top: 640, height: 170 }, // advice score
  ];
  const SLIDER_TOP = 840;

  const issues = D.issues;
  const lastIssue = issues[issues.length - 1];
  const endDate = isoDay(Math.max(Date.parse(lastIssue.date) + 7 * DAY_MS, Date.parse(D.ocr_last.date)));
  const toneAvg = rolling(issues.map((r) => r.tone.score), 8);
  const adviceCells = issues.map((r, i) => ({
    group: r.borrower.group,
    value: [r.date, i + 1 < issues.length ? issues[i + 1].date : endDate, 0],
  }));
  let C = {}; // colours, read from the CSS tokens on each draw
  let chart = null;

  function isoDay(ms) { return new Date(ms).toISOString().slice(0, 10); }
  function pct(n) { return n.toFixed(2) + "%"; }
  function money(n) { return "$" + Math.round(n).toLocaleString("en-NZ"); }
  function signed(n, digits) { return (n > 0 ? "+" : "") + n.toFixed(digits); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function adviceLabel(b) {
    if (b.group === "mix") return "Mix: " + b.terms_months.map((t) => TERM_LABEL[t] || t + "m").join(" + ");
    return GROUP_LABEL[b.group];
  }
  function rolling(values, n) {
    return values.map((_, i) => {
      const part = values.slice(Math.max(0, i - n + 1), i + 1);
      return part.reduce((a, b) => a + b, 0) / part.length;
    });
  }
  // The last item of a date-sorted list with a date on or before `day` (YYYY-MM-DD).
  function lastOnOrBefore(list, day, dateOf) {
    let found = null;
    for (const item of list) {
      if (dateOf(item) > day) break;
      found = item;
    }
    return found;
  }
  function readColours() {
    const style = getComputedStyle(document.documentElement);
    const names = ["fg", "muted", "grid", "panel", "ocr", "m1", "m2", "m3", "table", "pos", "neg",
      "tony", "fix1", "float"].concat(GROUPS.map((g) => "g-" + g));
    const out = {};
    for (const n of names) out[n] = style.getPropertyValue("--" + n).trim();
    return out;
  }
  function scoreSeries(loan) {
    const k = loan / D.score.loan;
    const line = (key) => D.score.months.map((m, i) => [m + "-15", Math.round(D.score[key][i] * k)]);
    return { tony: line("tony"), fix_1y: line("fix_1y"), float: line("float") };
  }

  function renderAdvice(params, api) {
    const start = api.coord([api.value(0), 0]);
    const end = api.coord([api.value(1), 0]);
    const height = api.size([0, 1])[1] * 0.9;
    const rect = echarts.graphic.clipRectByRect(
      { x: start[0], y: start[1] - height / 2, width: Math.max(end[0] - start[0] - 1, 1), height },
      { x: params.coordSys.x, y: params.coordSys.y, width: params.coordSys.width, height: params.coordSys.height });
    return rect && { type: "rect", shape: rect, style: { fill: C["g-" + adviceCells[params.dataIndex].group] } };
  }

  function rateLine(name, data, colour, type) {
    return { name, type: "line", xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, sampling: "lttb", data,
      lineStyle: { width: type === "dotted" ? 1.5 : 2, type, color: colour }, itemStyle: { color: colour } };
  }
  function scoreLine(id, name, data, colour) {
    return { id, name, type: "line", xAxisIndex: 3, yAxisIndex: 3, showSymbol: false, data,
      lineStyle: { width: 2, color: colour }, itemStyle: { color: colour } };
  }

  function tooltipHtml(t) {
    const day = isoDay(t);
    const rows = [`<b>${day}</b>`];
    const issue = lastOnOrBefore(issues, day, (r) => r.date);
    if (issue) {
      rows.push(`Issue ${issue.date}: <i>${esc(issue.headline)}</i>`);
      rows.push(`Advice: ${esc(adviceLabel(issue.borrower))}`);
      rows.push(`Tone: ${signed(issue.tone.score, 0)}`);
    }
    const ocr = lastOnOrBefore(D.ocr, day, (o) => o.date);
    if (ocr) rows.push(`OCR: ${pct(ocr.rate)}`);
    const mortgage = ["1y", "2y", "3y"]
      .map((k) => [k, lastOnOrBefore(D.mortgage[k], day, (p) => p[0])])
      .filter(([, p]) => p)
      .map(([k, p]) => `${k} ${pct(p[1])}`);
    if (mortgage.length) rows.push(`Mortgage (average advertised): ${mortgage.join(", ")}`);
    const s1 = lastOnOrBefore(D.swap.y1, day, (p) => p[0]);
    const s3 = lastOnOrBefore(D.swap.y3, day, (p) => p[0]);
    if (s1 && s3) rows.push(`Swap: 1y ${pct(s1[1])}, 3y ${pct(s3[1])}`);
    if (issue && issue.lender_min_rates) {
      rows.push("Tony's lowest lender rates: " + Object.entries(issue.lender_min_rates)
        .map(([term, rate]) => `${TERM_LABEL[term] || term + "m"} ${pct(rate)}`).join(", "));
    }
    rows.push('<span class="hint">Click for details</span>');
    return rows.join("<br>");
  }

  function buildOption(loan) {
    const s = scoreSeries(loan);
    const timeAxis = (i) => ({
      type: "time", gridIndex: i, min: issues[0].date, max: endDate,
      axisLine: { lineStyle: { color: C.grid } }, splitLine: { show: false },
      axisTick: { show: i === 0 || i === 3 },
      axisLabel: { show: i === 0 || i === 3, color: C.muted, hideOverlap: true },
    });
    const valueAxis = (i, extra) => Object.assign({
      type: "value", gridIndex: i, axisLabel: { color: C.muted }, splitLine: { lineStyle: { color: C.grid } },
    }, extra);
    const tableRates = [];
    for (const r of issues) {
      for (const [, rate] of Object.entries(r.lender_min_rates || {})) tableRates.push([r.date, rate]);
    }
    const titles = [
      ["Rates (% per year)", 4],
      ["If I were a borrower", GRID[1].top - 26],
      ["Economy tone, -2 to +2 (bars) and 8-week average (line)", GRID[2].top - 26],
      ["Advice score: total interest paid", GRID[3].top - 26],
    ];
    return {
      backgroundColor: "transparent",
      animation: false,
      textStyle: { color: C.fg, fontFamily: "inherit" },
      title: titles.map(([text, top]) => ({ text, left: 8, top, textStyle: { fontSize: 13, fontWeight: 600, color: C.fg } })),
      legend: [
        { type: "scroll", top: 28, left: 8, right: 8, textStyle: { color: C.muted },
          data: ["OCR", "OCR change", "Mortgage 1y", "Mortgage 2y", "Mortgage 3y", "Swap 1y", "Swap 3y", "Tony's lowest lender rates"] },
        { top: GRID[3].top - 26, right: 8, textStyle: { color: C.muted },
          data: ["Tony's advice", "Always fix 1 year", "Always float"] },
      ],
      grid: GRID.map((g) => ({ left: 52, right: 20, top: g.top, height: g.height })),
      xAxis: GRID.map((_, i) => timeAxis(i)),
      yAxis: [
        valueAxis(0, { min: 0 }),
        { type: "category", gridIndex: 1, data: ["Advice"], show: false },
        valueAxis(2, { min: -2, max: 2, interval: 1 }),
        valueAxis(3, { min: 0, axisLabel: { color: C.muted, formatter: (v) => "$" + Math.round(v / 1000) + "k" } }),
      ],
      axisPointer: { link: [{ xAxisIndex: "all" }], lineStyle: { color: C.muted } },
      tooltip: {
        trigger: "axis", confine: true, axisPointer: { type: "line" },
        backgroundColor: C.panel, borderColor: C.grid, textStyle: { color: C.fg },
        formatter: (params) => tooltipHtml(params[0].axisValue),
      },
      dataZoom: [
        { type: "slider", xAxisIndex: [0, 1, 2, 3], top: SLIDER_TOP, height: 22,
          labelFormatter: (v) => isoDay(v).slice(0, 7) },
        { type: "inside", xAxisIndex: [0, 1, 2, 3], zoomOnMouseWheel: "shift" },
      ],
      series: [
        { name: "OCR", type: "line", step: "end", xAxisIndex: 0, yAxisIndex: 0, showSymbol: false,
          lineStyle: { width: 2.5, color: C.ocr }, itemStyle: { color: C.ocr },
          data: D.ocr.map((o) => [o.date, o.rate]).concat([[D.ocr_last.date, D.ocr_last.rate]]) },
        { name: "OCR change", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, symbol: "triangle", symbolSize: 9,
          itemStyle: { color: C.ocr }, label: { show: true, fontSize: 10, color: C.fg },
          data: D.ocr.filter((o) => o.change !== null).map((o) => ({
            value: [o.date, o.rate], symbolRotate: o.change < 0 ? 180 : 0,
            label: { formatter: signed(o.change, 2), position: o.change < 0 ? "bottom" : "top" },
          })) },
        rateLine("Mortgage 1y", D.mortgage["1y"], C.m1, "solid"),
        rateLine("Mortgage 2y", D.mortgage["2y"], C.m2, "solid"),
        rateLine("Mortgage 3y", D.mortgage["3y"], C.m3, "solid"),
        rateLine("Swap 1y", D.swap.y1, C.m1, "dotted"),
        rateLine("Swap 3y", D.swap.y3, C.m3, "dotted"),
        { name: "Tony's lowest lender rates", type: "scatter", xAxisIndex: 0, yAxisIndex: 0,
          symbol: "diamond", symbolSize: 7, itemStyle: { color: C.table }, data: tableRates },
        { name: "Advice", type: "custom", xAxisIndex: 1, yAxisIndex: 1, renderItem: renderAdvice,
          encode: { x: [0, 1], y: 2 }, data: adviceCells.map((c) => c.value) },
        { name: "Tone", type: "bar", xAxisIndex: 2, yAxisIndex: 2, barMaxWidth: 6,
          data: issues.map((r) => ({ value: [r.date, r.tone.score],
            itemStyle: { color: r.tone.score >= 0 ? C.pos : C.neg } })) },
        { name: "Tone 8-week average", type: "line", xAxisIndex: 2, yAxisIndex: 2, showSymbol: false, smooth: true,
          lineStyle: { width: 2, color: C.fg }, itemStyle: { color: C.fg },
          data: issues.map((r, i) => [r.date, Math.round(toneAvg[i] * 100) / 100]) },
        scoreLine("tony", "Tony's advice", s.tony, C.tony),
        scoreLine("fix_1y", "Always fix 1 year", s.fix_1y, C.fix1),
        scoreLine("float", "Always float", s.float, C.float),
      ],
    };
  }

  function setQuote(el, text) { el.textContent = text || ""; el.hidden = !text; }
  function showDetails(issue) {
    const $ = (id) => document.getElementById(id);
    $("d-headline").textContent = issue.headline;
    $("d-date").textContent = issue.date;
    $("d-pdf").href = /^https:\/\//.test(issue.pdf_url) ? issue.pdf_url : "#";
    $("d-advice").textContent = adviceLabel(issue.borrower);
    setQuote($("d-advice-quote"), issue.borrower.quote);
    $("d-tone").textContent = signed(issue.tone.score, 0) + " - " + issue.tone.reason;
    setQuote($("d-tone-quote"), issue.tone.quote);
    $("details").hidden = false;
  }

  function renderSummary(loan) {
    const s = scoreSeries(loan);
    const last = (a) => a[a.length - 1][1];
    const diff = last(s.tony) - last(s.fix_1y);
    const tiles = [
      ["OCR", pct(D.ocr_last.rate), "as at " + D.ocr_last.date],
      ["Tony's latest advice", adviceLabel(lastIssue.borrower), "issue " + lastIssue.date],
      ["Latest tone", signed(lastIssue.tone.score, 0), "8-week average " + signed(toneAvg[toneAvg.length - 1], 1)],
      ["Advice score", money(Math.abs(diff)) + (diff <= 0 ? " less" : " more"),
        "interest than always fixing 1 year, on a " + money(loan) + " loan"],
    ];
    document.getElementById("summary").replaceChildren(...tiles.map(([label, value, note]) => {
      const tile = document.createElement("div");
      tile.className = "tile";
      for (const [cls, text] of [["label", label], ["value", value], ["note", note]]) {
        const span = document.createElement("span");
        span.className = cls;
        span.textContent = text;
        tile.append(span);
      }
      return tile;
    }));
  }

  function renderLegend() {
    document.getElementById("advice-legend").replaceChildren(...GROUPS.map((g) => {
      const key = document.createElement("span");
      const swatch = document.createElement("i");
      swatch.style.background = C["g-" + g];
      key.append(swatch, document.createTextNode(GROUP_LABEL[g]));
      return key;
    }));
  }

  function currentLoan() {
    const value = Number(document.getElementById("loan").value);
    return value > 0 ? value : D.score.loan;
  }

  function draw() {
    C = readColours();
    if (chart) chart.dispose();
    chart = echarts.init(document.getElementById("chart"));
    chart.setOption(buildOption(currentLoan()));
    chart.getZr().on("click", (e) => {
      if (e.offsetY >= SLIDER_TOP) return;
      const [t] = chart.convertFromPixel({ gridIndex: 0 }, [e.offsetX, e.offsetY]);
      if (!Number.isFinite(t)) return;
      const issue = lastOnOrBefore(issues, isoDay(t), (r) => r.date);
      if (issue) showDetails(issue);
    });
    renderSummary(currentLoan());
    renderLegend();
  }

  document.getElementById("range").textContent =
    `${issues.length} issues, ${issues[0].date} to ${lastIssue.date}` + (D.quotes ? "" : " (quotes off)");
  document.getElementById("loan").addEventListener("change", () => {
    const s = scoreSeries(currentLoan());
    chart.setOption({ series: [{ id: "tony", data: s.tony }, { id: "fix_1y", data: s.fix_1y }, { id: "float", data: s.float }] });
    renderSummary(currentLoan());
  });
  document.getElementById("close").addEventListener("click", () => { document.getElementById("details").hidden = true; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") document.getElementById("details").hidden = true; });
  window.addEventListener("resize", () => chart && chart.resize());
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  draw();
})();
```

- [ ] **Step 6: Check the page in a browser**

Run: `open site/index.html` (or use the Chrome tools if they are available, and take a screenshot).
Check each item and fix what fails:
1. The summary row shows the OCR, the latest advice, the latest tone and the advice score.
2. The rates chart shows the OCR step line with ▲/▼ labels, three mortgage lines, two dotted swap lines, and diamonds only where Tony gave his table.
3. The advice strip has one coloured cell per week, and the colour legend above the chart matches it.
4. Hover shows one vertical line through all four charts and a tooltip with the values.
5. A click on a week opens the details panel with the headline, the advice, the quotes and a working PDF link. Escape closes it.
6. The slider zooms all four charts together.
7. A change of the loan amount changes the score chart and the score tile.
8. Switch macOS to dark mode: the page redraws in dark colours.
9. The browser console has no errors.
10. Review Focus 5: in `site/data.js`, change the first issue's headline to `<b>Test</b> & "quotes"`, reload, and confirm that the tooltip and the details panel show those characters as plain text. Then run `uv run python -m scripts.build_data` to restore the file.

Expected: all 10 items pass.

- [ ] **Step 7: Commit**

```bash
git add site/index.html site/style.css site/app.js site/vendor/echarts.min.js
git commit -m "feat: stacked timeline page for advice, tone, rates and advice score"
```

---

### Task 11: Final checks and README

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: a verified build and a short guide to rerun it.

- [ ] **Step 1: Write `README.md`**

```markdown
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
6. Download `hb2-daily.xlsx` and `hb20.xlsx` from the Reserve Bank in a
   browser into `data/raw/rbnz/` (the site blocks scripts).
7. `uv run python -m scripts.build_data` - writes `site/data.js`.
   Use `--no-quotes` before you publish the site anywhere.
8. Open `site/index.html`.

Tests: `uv run pytest`
```

- [ ] **Step 2: Run every check**

```bash
uv run pytest -v
uv run python -m scripts.validate
uv run python -m scripts.build_data --no-quotes
uv run python - <<'EOF'
import glob, json
d = json.loads(open("site/data.js").read()[len("window.TONY_DATA = "):-2])

def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)

page_text = "\n".join(strings(d))
quotes = []
for path in glob.glob("data/records/*.json"):
    r = json.load(open(path))
    quotes += [q for q in (r["borrower"].get("quote"), r["tone"].get("quote")) if q]
leaks = [q for q in quotes if q in page_text]
print("issues", len(d["issues"]), "| quotes flag", d["quotes"], "| leaked quotes", len(leaks))
EOF
uv run python -m scripts.build_data
```

Expected:
1. All tests pass.
2. `all records valid`.
3. The `--no-quotes` check prints `issues 226 | quotes flag False | leaked quotes 0` (the issue count can be a little higher if new issues came out).
4. The last build restores the local page with quotes (`quotes on`).

- [ ] **Step 3: Check the success criteria in the spec (section 12)**

1. Every issue has a valid record (Step 2, item 2).
2. The OCR line matches the Reserve Bank file at every change (Task 9 Step 6 list).
3. The hand check passed (`data/hand-check.md`, at least 9 of 10).
4. The page works from the file system with no internet (Task 10 Step 6; also turn off Wi-Fi and reload once).
5. The `--no-quotes` build has no quotes (Step 2, item 3).

- [ ] **Step 4: Commit**

```bash
git add README.md site/data.js
git commit -m "docs: README with the steps to rebuild the tracker"
```
