import json
from datetime import date

import pytest

from scripts import rbnz
from scripts.build_data import build_payload, stale_warnings, to_js, write_public

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


def test_payload_has_totals_for_each_start_month():
    b2, b20 = series()
    p = build_payload(records(), b2, b20, include_quotes=True)
    assert [row["start"] for row in p["by_start"]] == ["2022-04", "2022-05"]
    assert p["by_start"][0]["totals"]["1y"] == p["score"]["fix_1y"][-1]


def payload_dates(last_issue, ocr_last, last_b20_month):
    return {"issues": [{"date": last_issue}], "ocr_last": {"date": ocr_last, "rate": 2.75},
            "score": {"months": [last_b20_month]}}


def test_no_warning_when_the_reserve_bank_data_is_recent():
    assert stale_warnings(payload_dates("2026-10-08", "2026-10-12", "2026-09")) == []


def test_warns_when_the_ocr_data_ends_long_before_the_last_issue():
    # The frozen hb2-daily.xlsx case: OCR data stopped in August 2025.
    warnings = stale_warnings(payload_dates("2026-10-08", "2025-08-22", "2026-09"))
    assert len(warnings) == 1
    assert "2025-08-22" in warnings[0] and "hb2-daily-close.xlsx" in warnings[0]


def test_warns_when_the_mortgage_data_ends_long_before_the_last_issue():
    # B20 to July 2026 ends 2026-07-31, 69 days before the last issue.
    warnings = stale_warnings(payload_dates("2026-10-08", "2026-10-12", "2026-07"))
    assert len(warnings) == 1
    assert "2026-07" in warnings[0] and "hb20.xlsx" in warnings[0]


def site_tree(tmp_path):
    site = tmp_path / "site"
    (site / "vendor").mkdir(parents=True)
    (site / "index.html").write_text("<html>")
    (site / "vendor" / "echarts.min.js").write_text("echarts")
    (site / "data.js").write_text(f"window.TONY_DATA = {{\"quote\":\"{QUOTE}\"}};")  # a local build with quotes
    (site / ".DS_Store").write_text("finder")
    (site / ".vercel").mkdir()
    (site / ".vercel" / "project.json").write_text("site link")
    return site


def no_quote_payload():
    b2, b20 = series()
    return build_payload(records(), b2, b20, include_quotes=False)


def test_public_build_copies_the_site_with_a_new_data_file(tmp_path):
    public = tmp_path / "public"
    write_public(no_quote_payload(), site_tree(tmp_path), public)
    files = sorted(p.relative_to(public).as_posix() for p in public.rglob("*"))
    assert files == ["data.js", "index.html", "vendor", "vendor/echarts.min.js"]
    assert (public / "data.js").read_text() == to_js(no_quote_payload())
    assert QUOTE not in (public / "data.js").read_text()


def test_public_build_keeps_the_vercel_link_and_removes_old_files(tmp_path):
    public = tmp_path / "public"
    (public / ".vercel").mkdir(parents=True)
    (public / ".vercel" / "project.json").write_text("public link")
    (public / "old.html").write_text("old")
    (public / "old-dir").mkdir()
    (public / "old-dir" / "old.js").write_text("old")
    write_public(no_quote_payload(), site_tree(tmp_path), public)
    assert (public / ".vercel" / "project.json").read_text() == "public link"
    assert not (public / "old.html").exists() and not (public / "old-dir").exists()


def test_public_build_refuses_a_payload_with_quotes(tmp_path):
    b2, b20 = series()
    with pytest.raises(ValueError, match="quotes"):
        write_public(build_payload(records(), b2, b20, include_quotes=True), site_tree(tmp_path), tmp_path / "public")
    assert not (tmp_path / "public").exists()


def test_public_build_refuses_a_quote_left_in_one_record(tmp_path):
    payload = no_quote_payload()
    payload["issues"][0]["tone"]["quote"] = "weak outlook"
    with pytest.raises(ValueError, match="quotes"):
        write_public(payload, site_tree(tmp_path), tmp_path / "public")
    assert not (tmp_path / "public").exists()
