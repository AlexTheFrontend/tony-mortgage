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
