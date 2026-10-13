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
