"""Download test book fixtures from Project Gutenberg."""

import urllib.request
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent

BOOKS = {
    "sample_epub/art_of_war.epub": "https://www.gutenberg.org/ebooks/132.epub3.images",
    "sample_epub/meditations.epub": "https://www.gutenberg.org/ebooks/2680.epub3.images",
    "sample_pdf/the_republic.pdf": "https://www.gutenberg.org/files/1497/1497-pdf.pdf",
    "sample_mobi/art_of_war.mobi": "https://www.gutenberg.org/ebooks/132.kf8.images",
}


def download_fixtures():
    for rel_path, url in BOOKS.items():
        dest = FIXTURES_DIR / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            print(f"  Already exists: {rel_path}")
            continue
        print(f"  Downloading: {rel_path} from {url}")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"  Saved: {dest} ({dest.stat().st_size / 1024:.0f} KB)")
        except Exception as e:
            print(f"  FAILED: {e}")


if __name__ == "__main__":
    print("Downloading test fixtures from Project Gutenberg...")
    download_fixtures()
    print("Done.")
