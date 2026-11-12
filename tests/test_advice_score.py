from datetime import date

import pytest

from scripts.advice_score import advice_terms, latest_advice, rate_for, run_strategy, score, score_by_start

M = ["2022-04", "2022-05", "2022-06"]


def flat(rate_by_key, months):
    return {key: {m: rate for m in months} for key, rate in rate_by_key.items()}


def rec(day, group, terms):
    return {"date": day, "borrower": {"group": group, "terms_months": terms}}


def test_always_fix_1y_pays_the_1y_rate():
    rates = flat({"1y": 12.0, "float": 6.0}, M)
    assert run_strategy(M, lambda m: [12], rates, 100_000) == [1000.0, 2000.0, 3000.0]


def test_always_float_pays_the_floating_rate():
    rates = flat({"1y": 12.0, "float": 6.0}, M)
    assert run_strategy(M, lambda m: [0], rates, 100_000) == [500.0, 1000.0, 1500.0]


def test_floating_part_is_fixed_when_advice_changes():
    rates = flat({"1y": 12.0, "float": 6.0}, M)
    advice = {"2022-04": [0], "2022-05": [12], "2022-06": [12]}
    assert run_strategy(M, advice.get, rates, 100_000) == [500.0, 1500.0, 2500.0]


def test_fixed_part_keeps_its_rate_until_the_term_ends():
    months = [f"2022-{m:02d}" for m in range(1, 9)]
    rates = {"6m": {m: (12.0 if m < "2022-07" else 6.0) for m in months}}
    totals = run_strategy(months, lambda m: [6], rates, 100_000)
    assert totals == [1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0, 6500.0, 7000.0]


def test_mix_splits_the_loan_evenly():
    rates = flat({"6m": 12.0, "1y": 6.0}, M[:1])
    assert run_strategy(M[:1], lambda m: [6, 12], rates, 100_000) == [750.0]


def test_advice_terms():
    assert advice_terms("none", []) is None
    assert advice_terms("float", []) == [0]
    assert advice_terms("1y", [12, 18]) == [12]
    assert advice_terms("3y_plus", [60]) == [36]
    assert advice_terms("mix", [12, 6, 60, 0]) == [0, 6, 12, 36]


def test_missing_18m_rate_uses_mean_of_1y_and_2y():
    rates = {"1y": {"2022-04": 5.0}, "2y": {"2022-04": 6.0}}
    assert rate_for(rates, 18, "2022-04") == 5.5


def test_other_missing_rate_is_an_error():
    with pytest.raises(ValueError, match="no 2y rate for 2022-04"):
        rate_for({"1y": {"2022-04": 5.0}}, 24, "2022-04")


def test_latest_advice_keeps_earlier_advice_for_none_and_starts_with_1y():
    terms_for = latest_advice([rec("2022-05-05", "float", []), rec("2022-06-02", "none", [])])
    assert terms_for("2022-04") == [12]
    assert terms_for("2022-05") == [0]
    assert terms_for("2022-06") == [0]


def test_score_runs_three_strategies_from_the_first_issue_month():
    b20 = {
        "1y": [(date(2022, 3, 31), 9.0), (date(2022, 4, 30), 12.0), (date(2022, 5, 31), 12.0)],
        "float": [(date(2022, 3, 31), 9.0), (date(2022, 4, 30), 6.0), (date(2022, 5, 31), 6.0)],
    }
    result = score([rec("2022-04-07", "float", [])], b20, 100_000)
    assert result["months"] == ["2022-04", "2022-05"]
    assert result["tony"] == [500.0, 1000.0]
    assert result["fix_1y"] == [1000.0, 2000.0]
    assert result["float"] == [500.0, 1000.0]
    assert result["loan"] == 100_000



def gap_b20():
    # B20 has June, but no 1y rate for May.
    return {
        "1y": [(date(2022, 4, 30), 12.0), (date(2022, 6, 30), 12.0)],
        "float": [(date(2022, 4, 30), 6.0), (date(2022, 5, 31), 6.0), (date(2022, 6, 30), 6.0)],
    }


def test_score_counts_a_month_with_no_1y_rate():
    result = score([rec("2022-04-07", "1y", [12])], gap_b20(), 100_000)
    assert result["months"] == ["2022-04", "2022-05", "2022-06"]
    assert result["fix_1y"] == [1000.0, 2000.0, 3000.0]


def test_score_stops_when_a_needed_1y_rate_is_missing():
    records = [rec("2022-04-07", "float", []), rec("2022-05-05", "1y", [12])]
    with pytest.raises(ValueError, match="no 1y rate for 2022-05"):
        score(records, gap_b20(), 100_000)


def three_months_b20():
    rates = {"float": 6.0, "6m": 8.0, "1y": 12.0, "18m": 9.0, "2y": 10.0, "3y": 7.2}
    ends = [date(2022, 4, 30), date(2022, 5, 31), date(2022, 6, 30)]
    return {key: [(day, rate) for day in ends] for key, rate in rates.items()}


def test_score_by_start_gives_totals_from_each_start_month_to_the_end():
    rows = score_by_start([rec("2022-04-07", "float", [])], three_months_b20(), 100_000)
    assert [(r["start"], r["months"]) for r in rows] == [("2022-04", 3), ("2022-05", 2), ("2022-06", 1)]
    assert set(rows[0]["totals"]) == {"tony", "float", "6m", "1y", "18m", "2y", "3y"}
    assert rows[0]["totals"]["float"] == 1500.0
    assert rows[0]["totals"]["1y"] == 3000.0
    assert rows[0]["totals"]["3y"] == 1800.0
    assert rows[2]["totals"]["1y"] == 1000.0


def test_score_by_start_uses_the_advice_in_force_at_the_start():
    # The April issue says float; a June start must float too, not use the 1-year default.
    rows = score_by_start([rec("2022-04-07", "float", [])], three_months_b20(), 100_000)
    assert rows[2]["totals"]["tony"] == 500.0
