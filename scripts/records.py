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
