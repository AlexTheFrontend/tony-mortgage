from datetime import date, datetime

from scripts.issues import (
    Pdf,
    date_from_filename,
    date_from_text,
    one_per_date,
    resolve_date,
    tonys_view_pdfs,
)


def test_date_from_plain_filename():
    assert date_from_filename("Tonys-View-7-April-2022.pdf") == date(2022, 4, 7)


def test_date_from_filename_with_suffixes():
    assert date_from_filename("Tonys-View-2-July-2026-1.pdf") == date(2026, 7, 2)
    assert date_from_filename("Tonys-View-8-September-2022a.pdf") == date(2022, 9, 8)
    assert date_from_filename("Tonys-View-25-April-2024hik.pdf") == date(2024, 4, 25)


def test_premium_and_other_pdfs_have_no_issue_date():
    assert date_from_filename("Tview-Premium-2-February-2023.pdf") is None
    assert date_from_filename("TV-Spending-Plans-Survey-May-2022.pdf") is None


def test_impossible_date_is_not_an_issue():
    assert date_from_filename("Tonys-View-31-June-2023.pdf") is None


def test_date_from_header_text():
    text = "1\nInput to your Strategy\nISSN: 2703-2825  Thursday 7 April 2022\nSign up"
    assert date_from_text(text) == date(2022, 4, 7)
    assert date_from_text("ISSN: 2703-2825   13 June 2024") == date(2024, 6, 13)


def test_no_header_date_returns_none():
    assert date_from_text("No date here at all") is None


def test_resolve_date_same_dates_has_no_warning():
    d = date(2024, 6, 13)
    assert resolve_date(d, d, d) == (d, None)


def test_resolve_date_without_header_uses_file_name():
    d = date(2024, 6, 13)
    day, warning = resolve_date(d, None, d)
    assert day == d and "no date in the PDF header" in warning


def test_resolve_date_header_typo_in_year_uses_file_name():
    day, warning = resolve_date(date(2024, 1, 25), date(2023, 1, 25), date(2024, 1, 25))
    assert day == date(2024, 1, 25) and warning


def test_resolve_date_file_name_typo_uses_header():
    day, warning = resolve_date(date(2022, 6, 9), date(2022, 6, 23), date(2022, 6, 22))
    assert day == date(2022, 6, 23) and warning


def test_tonys_view_pdfs_skips_other_pdfs():
    media = [
        {"date": "2022-04-07T09:00:00", "source_url": "https://x/Tonys-View-7-April-2022.pdf"},
        {"date": "2023-02-02T09:00:00", "source_url": "https://x/Tview-Premium-2-February-2023.pdf"},
        {"date": "2022-05-01T09:00:00", "source_url": "https://x/TV-Spending-Plans-Survey-May-2022.pdf"},
    ]
    pdfs = tonys_view_pdfs(media)
    assert pdfs == [Pdf("Tonys-View-7-April-2022.pdf", "https://x/Tonys-View-7-April-2022.pdf",
                        datetime(2022, 4, 7, 9, 0))]


def test_one_per_date_keeps_latest_upload():
    a = Pdf("Tonys-View-9-June-2022-1.pdf", "u1", datetime(2022, 6, 9, 10))
    b = Pdf("Tonys-View-9-June-2022.pdf", "u2", datetime(2022, 6, 22, 10))
    c = Pdf("Tonys-View-7-April-2022.pdf", "u3", datetime(2022, 4, 7, 10))
    chosen = one_per_date([(date(2022, 6, 9), a), (date(2022, 6, 9), b), (date(2022, 4, 7), c)])
    assert list(chosen) == [date(2022, 4, 7), date(2022, 6, 9)]
    assert chosen[date(2022, 6, 9)].url == "u2"
