"""Find the Tony's View issues in the site's media list and give each one a date."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

MONTHS = {
    name: number
    for number, name in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"],
        start=1,
    )
}

# "Tonys-View-7-April-2022.pdf", also with "-1", "a" or "hik" before ".pdf".
# "Tview-Premium-..." (the paid newsletter) does not match.
_FILENAME = re.compile(r"^Tonys-View-(\d{1,2})-([A-Za-z]+)-(\d{4})[^/]*\.pdf$", re.IGNORECASE)
_HEADER_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b", re.IGNORECASE)


@dataclass(frozen=True)
class Pdf:
    file: str
    url: str
    uploaded: datetime


def _make_date(year: str, month_name: str, day: str) -> date | None:
    month = MONTHS.get(month_name.lower())
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def date_from_filename(name: str) -> date | None:
    m = _FILENAME.match(name)
    return _make_date(m.group(3), m.group(2), m.group(1)) if m else None


def date_from_text(text: str, head_chars: int = 600) -> date | None:
    """The first date in the top part of the issue, for example 'Thursday 7 April 2022'."""
    m = _HEADER_DATE.search(text[:head_chars])
    return _make_date(m.group(3), m.group(2), m.group(1)) if m else None


def resolve_date(file_date: date, header_date: date | None, uploaded: date) -> tuple[date, str | None]:
    """Choose the issue date. If the two dates differ, the one closer to the upload date wins."""
    if header_date is None:
        return file_date, f"{file_date}: no date in the PDF header, used the file name"
    if header_date == file_date:
        return file_date, None
    chosen = min((header_date, file_date), key=lambda d: abs((d - uploaded).days))
    return chosen, (f"{file_date}: PDF header says {header_date}, "
                    f"used {chosen} (closer to upload date {uploaded})")


def tonys_view_pdfs(media: list[dict]) -> list[Pdf]:
    pdfs = []
    for item in media:
        url = item["source_url"]
        name = url.rsplit("/", 1)[-1]
        if date_from_filename(name) is not None:
            pdfs.append(Pdf(name, url, datetime.fromisoformat(item["date"])))
    return sorted(pdfs, key=lambda p: p.uploaded)


def one_per_date(dated: list[tuple[date, Pdf]]) -> dict[date, Pdf]:
    """One PDF for each issue date: the latest upload wins."""
    latest: dict[date, Pdf] = {}
    for day, pdf in dated:
        if day not in latest or pdf.uploaded > latest[day].uploaded:
            latest[day] = pdf
    return {day: latest[day] for day in sorted(latest)}
