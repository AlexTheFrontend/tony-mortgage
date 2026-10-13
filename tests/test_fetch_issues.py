import json
import urllib.error
from datetime import datetime

import pytest

from scripts.fetch_issues import download_missing, fetch_media_list
from scripts.issues import Pdf


def page_of(url: str) -> int:
    return int(url.rsplit("page=", 1)[1])


def test_fetch_media_list_reads_all_pages():
    pages = {1: [{"date": "d", "source_url": f"u{i}"} for i in range(100)],
             2: [{"date": "d", "source_url": "last"}]}
    calls = []

    def fake_get(url):
        calls.append(page_of(url))
        return json.dumps(pages[page_of(url)]).encode()

    assert len(fetch_media_list(fake_get)) == 101
    assert calls == [1, 2]


def test_fetch_media_list_stops_at_invalid_page_error():
    def fake_get(url):
        if page_of(url) == 1:
            return json.dumps([{"date": "d", "source_url": "u"}] * 100).encode()
        raise urllib.error.HTTPError(url, 400, "rest_post_invalid_page_number", None, None)

    assert len(fetch_media_list(fake_get)) == 100


def test_download_missing_skips_files_on_disk(tmp_path):
    (tmp_path / "Tonys-View-7-April-2022.pdf").write_bytes(b"%PDF old")
    pdfs = [Pdf("Tonys-View-7-April-2022.pdf", "u1", datetime(2022, 4, 7)),
            Pdf("Tonys-View-13-April-2022.pdf", "u2", datetime(2022, 4, 13))]
    fetched = []

    def fake_get(url):
        fetched.append(url)
        return b"%PDF new"

    assert download_missing(pdfs, tmp_path, fake_get, pause=0) == 1
    assert fetched == ["u2"]
    assert (tmp_path / "Tonys-View-7-April-2022.pdf").read_bytes() == b"%PDF old"


def test_download_missing_rejects_html_instead_of_pdf(tmp_path):
    pdfs = [Pdf("Tonys-View-7-April-2022.pdf", "u1", datetime(2022, 4, 7))]
    with pytest.raises(ValueError, match="did not return a PDF"):
        download_missing(pdfs, tmp_path, lambda url: b"<html>error</html>", pause=0)
    assert not (tmp_path / "Tonys-View-7-April-2022.pdf").exists()
