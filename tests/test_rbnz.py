from datetime import date, datetime

import openpyxl
import pytest

from scripts import rbnz


def make_xlsx(path, ids, rows):
    """A small file with the same layout as the Reserve Bank files."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append([None] + ["Group"] * len(ids))
    ws.append([None] + [f"name {i}" for i in ids])
    ws.append(["Notes"] + [None] * len(ids))
    ws.append(["Unit"] + ["%pa"] * len(ids))
    ws.append(["Series Id"] + ids)
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def test_read_series_finds_columns_by_id_and_skips_blanks(tmp_path):
    path = make_xlsx(tmp_path / "b2.xlsx", ["X.OTHER", rbnz.OCR, rbnz.SWAP_1Y], [
        [datetime(2022, 4, 7), 9.9, 1.0, 2.5],
        [datetime(2022, 4, 8), 9.9, 1.0, None],
        ["Source: RBNZ", None, None, None],
    ])
    out = rbnz.read_series(path, [rbnz.OCR, rbnz.SWAP_1Y])
    assert out[rbnz.OCR] == [(date(2022, 4, 7), 1.0), (date(2022, 4, 8), 1.0)]
    assert out[rbnz.SWAP_1Y] == [(date(2022, 4, 7), 2.5)]


def test_read_series_fails_for_unknown_id(tmp_path):
    path = make_xlsx(tmp_path / "b2.xlsx", [rbnz.OCR], [[datetime(2022, 4, 7), 1.0]])
    with pytest.raises(ValueError, match="series not found"):
        rbnz.read_series(path, ["NOT.THERE"])


def test_ocr_changes_start_with_the_rate_in_force():
    daily = [(date(2022, 2, 24), 1.0), (date(2022, 4, 6), 1.0), (date(2022, 4, 14), 1.5),
             (date(2022, 4, 15), 1.5), (date(2022, 5, 26), 2.0), (date(2023, 1, 5), 2.0)]
    assert rbnz.ocr_changes(daily, date(2022, 4, 7)) == [
        {"date": "2022-04-07", "rate": 1.0, "change": None},
        {"date": "2022-04-14", "rate": 1.5, "change": 0.5},
        {"date": "2022-05-26", "rate": 2.0, "change": 0.5},
    ]


def test_ocr_cut_is_negative():
    daily = [(date(2024, 8, 1), 5.5), (date(2024, 8, 15), 5.25)]
    assert rbnz.ocr_changes(daily, date(2024, 8, 1))[1] == {"date": "2024-08-15", "rate": 5.25, "change": -0.25}


def test_since_keeps_dates_from_start():
    series = [(date(2022, 4, 6), 2.7), (date(2022, 4, 7), 2.96)]
    assert rbnz.since(series, date(2022, 4, 7)) == [["2022-04-07", 2.96]]
