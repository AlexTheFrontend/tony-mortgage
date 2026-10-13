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
