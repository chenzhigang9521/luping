"""
Fetch a Noto Sans TTF for bundling into the app.
This script attempts to download a Noto Sans regular TTF into `resources/fonts/`.
It does NOT modify the repository otherwise. Use this in CI/build steps when you
want a reproducible, embeddable open-source font.

License note: Noto fonts are open-source (Apache 2.0 / SIL) — verify license for
specific font files before redistributing in your product.
"""
import os
import sys
from pathlib import Path

URLS = [
    # Raw file in github repo (preferred)
    'https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf',
    # Alternate path if repo layout differs
    'https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf',
]

DEST_DIR = Path(__file__).resolve().parent.parent / 'resources' / 'fonts'
DEST_DIR.mkdir(parents=True, exist_ok=True)
OUT = DEST_DIR / 'NotoSans-Regular.ttf'


def download(url, dest):
    try:
        import urllib.request
        print(f'Downloading {url} -> {dest}')
        with urllib.request.urlopen(url, timeout=30) as r:
            data = r.read()
            if len(data) < 1000:
                print('Downloaded file too small, aborting')
                return False
            with open(dest, 'wb') as f:
                f.write(data)
        print('Download complete')
        return True
    except Exception as e:
        print('Download failed:', e)
        return False


def main():
    if OUT.exists():
        print('Font already exists:', OUT)
        sys.exit(0)

    for url in URLS:
        ok = download(url, OUT)
        if ok:
            sys.exit(0)

    print('All download attempts failed. Please download a suitable TTF and place it in:', DEST_DIR)
    sys.exit(2)

if __name__ == '__main__':
    main()
