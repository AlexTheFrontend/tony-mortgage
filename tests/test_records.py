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
