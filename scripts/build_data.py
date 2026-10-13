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

B2_FILE = Path("data/raw/rbnz/hb2-daily-close.xlsx")
B20_FILE = Path("data/raw/rbnz/hb20.xlsx")
OUT = Path("site/data.js")
LOAN = 500_000
RBNZ_URLS = [
    "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx",
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
