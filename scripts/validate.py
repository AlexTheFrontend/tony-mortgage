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
