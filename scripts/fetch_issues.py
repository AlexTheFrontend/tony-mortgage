"""Download every Tony's View PDF that is not yet on disk.

Run: uv run python -m scripts.fetch_issues
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from scripts.issues import Pdf, tonys_view_pdfs

MEDIA_URL = ("https://www.tonyalexander.nz/wp-json/wp/v2/media"
             "?mime_type=application/pdf&per_page=100&orderby=date&order=asc"
             "&_fields=date,source_url&page={page}")
PDF_DIR = Path("data/raw/pdf")
INDEX = PDF_DIR / "index.json"
USER_AGENT = "tonywebsite-personal-tracker/0.1 (personal, non-commercial)"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_media_list(get: Callable[[str], bytes] = _get) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        try:
            batch = json.loads(get(MEDIA_URL.format(page=page)))
        except urllib.error.HTTPError as error:
            if error.code == 400:  # WordPress: page number past the end
                return items
            raise
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


def download_missing(pdfs: list[Pdf], pdf_dir: Path, get: Callable[[str], bytes] = _get,
                     pause: float = 1.0) -> int:
    count = 0
    for pdf in pdfs:
        target = pdf_dir / pdf.file
        if target.exists():
            continue
        data = get(pdf.url)
        if not data.startswith(b"%PDF"):
            raise ValueError(f"{pdf.url} did not return a PDF")
        target.write_bytes(data)
        count += 1
        print("downloaded", pdf.file)
        time.sleep(pause)
    return count


def main() -> int:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = tonys_view_pdfs(fetch_media_list())
    count = download_missing(pdfs, PDF_DIR)
    INDEX.write_text(json.dumps(
        [{"file": p.file, "url": p.url, "uploaded": p.uploaded.isoformat()} for p in pdfs], indent=2))
    print(f"{len(pdfs)} Tony's View PDFs listed, {count} downloaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
