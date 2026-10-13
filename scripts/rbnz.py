"""Read series from Reserve Bank of New Zealand xlsx files (B2 daily, B20 monthly).

Layout of the "Data" sheet: header rows, one of them starts with "Series Id"
and holds the series IDs; each data row starts with a date in column A.
"""
from __future__ import annotations

import warnings
from datetime import date, datetime
from pathlib import Path

import openpyxl

OCR = "INM.DP1.N"
SWAP_1Y = "INM.DS01.NZZC"
SWAP_3Y = "INM.DS03.NZZC"
B20 = {
    "float": "MTGE.MBI.F",
    "6m": "MTGE.MBI.T07",
    "1y": "MTGE.MBI.T09",
    "18m": "INRL.MAL1.D18",
    "2y": "MTGE.MBI.T10",
    "3y": "MTGE.MBI.T11",
}

Series = list[tuple[date, float]]


def read_series(path: Path, series_ids: list[str]) -> dict[str, Series]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the files have no default style
        sheet = openpyxl.load_workbook(path, data_only=True)["Data"]
    columns: dict[str, int] | None = None
    out: dict[str, Series] = {sid: [] for sid in series_ids}
    for row in sheet.iter_rows(values_only=True):
        if row[0] == "Series Id":
            ids = list(row)
            missing = [sid for sid in series_ids if sid not in ids]
            if missing:
                raise ValueError(f"{path.name}: series not found: {missing}")
            columns = {sid: ids.index(sid) for sid in series_ids}
            continue
        if columns is None or not isinstance(row[0], datetime):
            continue
        for sid, col in columns.items():
            value = row[col]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[sid].append((row[0].date(), float(value)))
    if columns is None:
        raise ValueError(f"{path.name}: no 'Series Id' row")
    return out


def ocr_changes(daily: Series, start: date) -> list[dict]:
    """The OCR in force on `start`, then each later day the OCR changed."""
    out: list[dict] = []
    previous = None
    for day, rate in daily:
        if rate == previous:
            continue
        if day <= start:
            out = [{"date": start.isoformat(), "rate": rate, "change": None}]
        else:
            change = None if previous is None else round(rate - previous, 2)
            out.append({"date": day.isoformat(), "rate": rate, "change": change})
        previous = rate
    return out


def since(series: Series, start: date) -> list[list]:
    return [[day.isoformat(), value] for day, value in series if day >= start]
