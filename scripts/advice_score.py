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


def month_range(first: str, last: str) -> list[str]:
    """Every month from `first` to `last` (YYYY-MM), both included."""
    year, month = int(first[:4]), int(first[5:7])
    out = []
    while f"{year:04d}-{month:02d}" <= last:
        out.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def score(records: list[dict], b20: dict[str, list[tuple[date, float]]], loan: float) -> dict:
    rates = {key: {day.strftime("%Y-%m"): value for day, value in series} for key, series in b20.items()}
    first = min(r["date"] for r in records)[:7]
    last = max(m for series in rates.values() for m in series)
    months = month_range(first, last)  # every month, so a gap in B20 stops in rate_for
    return {
        "loan": loan,
        "months": months,
        "tony": run_strategy(months, latest_advice(records), rates, loan),
        "fix_1y": run_strategy(months, lambda m: [12], rates, loan),
        "float": run_strategy(months, lambda m: [0], rates, loan),
    }
