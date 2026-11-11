"""Combine the records and the Reserve Bank files into site/data.js.

Run: uv run python -m scripts.build_data              (with Tony's quotes)
     uv run python -m scripts.build_data --no-quotes  (site/data.js with no quotes)
     uv run python -m scripts.build_data --public     (public/: the site to deploy, never with quotes)
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

from scripts import rbnz
from scripts.advice_score import score, score_by_start
from scripts.validate import ISSUES, RECORDS, TEXT_DIR, check_all

B2_FILE = Path("data/raw/rbnz/hb2-daily-close.xlsx")
B20_FILE = Path("data/raw/rbnz/hb20.xlsx")
SITE = Path("site")
OUT = SITE / "data.js"
PUBLIC = Path("public")
SKIP_FROM_SITE = ("data.js", ".vercel", ".DS_Store")  # data.js is written new; .vercel is a local link
KEEP_IN_PUBLIC = {".vercel"}  # the Vercel link of public/, from `npx vercel` in that folder
LOAN = 500_000
STALE_DAYS = 42  # warn when Reserve Bank data ends this long before the last issue
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
        "by_start": score_by_start(records, b20, LOAN),
    }


def stale_warnings(payload: dict, max_days: int = STALE_DAYS) -> list[str]:
    """Warnings when the Reserve Bank data ends long before the last issue.

    The Reserve Bank can stop updating a file: hb2-daily.xlsx froze in August 2025.
    """
    last_issue = date.fromisoformat(payload["issues"][-1]["date"])
    out = []
    ocr_last = date.fromisoformat(payload["ocr_last"]["date"])
    if (last_issue - ocr_last).days > max_days:
        out.append(f"OCR and swap data end {ocr_last}, {(last_issue - ocr_last).days} days before the last issue. "
                   f"Download {B2_FILE.name} again; if it is still old, the Reserve Bank may have renamed the file.")
    month = payload["score"]["months"][-1]
    year, mon = int(month[:4]), int(month[5:7])
    month_end = date(year + mon // 12, mon % 12 + 1, 1) - timedelta(days=1)
    if (last_issue - month_end).days > max_days:
        out.append(f"Mortgage data ends {month}, {(last_issue - month_end).days} days before the last issue. "
                   f"Download {B20_FILE.name} again; if it is still old, the Reserve Bank may have renamed the file.")
    return out


def to_js(payload: dict) -> str:
    return "window.TONY_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"


def write_public(payload: dict, site_dir: Path = SITE, public_dir: Path = PUBLIC) -> None:
    """Make public_dir a copy of the site with this payload as data.js.

    Refuses a payload with any of Tony's quotes, so the deploy folder never holds them.
    """
    if payload["quotes"] or any("quote" in r["borrower"] or "quote" in r["tone"] for r in payload["issues"]):
        raise ValueError("the public build must not hold Tony's quotes")
    public_dir.mkdir(exist_ok=True)
    for old in public_dir.iterdir():
        if old.name in KEEP_IN_PUBLIC:
            continue
        if old.is_dir() and not old.is_symlink():
            shutil.rmtree(old)
        else:
            old.unlink()
    shutil.copytree(site_dir, public_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*SKIP_FROM_SITE))
    (public_dir / "data.js").write_text(to_js(payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build site/data.js, or public/ for the web.")
    parser.add_argument("--no-quotes", action="store_true", help="leave out all quotes from Tony's issues")
    parser.add_argument("--public", action="store_true",
                        help="write public/ (the site with no quotes) to deploy; site/data.js does not change")
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

    payload = build_payload(records, b2, b20, include_quotes=not (args.no_quotes or args.public))
    if args.public:
        write_public(payload)
        target = f"{PUBLIC}/"
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(to_js(payload))
        target = str(OUT)
    print(f"wrote {target}: {len(records)} issues, quotes {'on' if payload['quotes'] else 'off'}, "
          f"OCR to {payload['ocr_last']['date']}, B20 to {payload['score']['months'][-1]}")
    for warning in stale_warnings(payload):
        print("WARNING:", warning)
    return 0


if __name__ == "__main__":
    sys.exit(main())
