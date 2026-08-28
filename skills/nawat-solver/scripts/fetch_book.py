#!/usr/bin/env python3
"""Fetch a book's source PDF from Google Drive into the corpus.

Storage model: source PDFs are NOT in git (a ~1 GB library exceeds GitHub's
free LFS quotas). Each book's meta.json records its drive_file_id; this
script downloads the PDF to corpus/<book>/source.pdf when a session needs it
— which is only for evidence rendering (verify_and_render.py) and indexing.
Retrieval and solving run entirely on the committed page text.

Requires the session's network policy to allow drive.google.com /
drive.usercontent.google.com, and the file to be link-accessible
("Anyone with the link — Viewer").

Usage:
  fetch_book.py sabiston-21e [--corpus corpus] [--force]
  fetch_book.py --all        # every registered book
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def fetch(book_id: str, corpus: Path, force: bool) -> bool:
    book_dir = corpus / book_id
    meta_path = book_dir / 'meta.json'
    if not meta_path.exists():
        print(f'{book_id}: no meta.json — is the book indexed?', file=sys.stderr)
        return False
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    dest = book_dir / meta.get('source', 'source.pdf')
    if dest.exists() and not force:
        print(f'{book_id}: already present ({dest.stat().st_size // 1_000_000} MB) — use --force to re-download')
        return True
    file_id = meta.get('drive_file_id')
    if not file_id:
        print(f'{book_id}: meta.json has no drive_file_id', file=sys.stderr)
        return False
    url = f'https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t'
    print(f'{book_id}: downloading…')
    r = subprocess.run(['curl', '-sSL', url, '-o', str(dest), '--max-time', '1800'])
    if r.returncode != 0:
        print(f'{book_id}: curl failed (network policy may block Drive domains)', file=sys.stderr)
        return False
    with dest.open('rb') as f:
        magic = f.read(5)
    if magic != b'%PDF-':
        dest.unlink(missing_ok=True)
        print(f'{book_id}: response was not a PDF (file not link-shared, or Drive interstitial page)', file=sys.stderr)
        return False
    print(f'{book_id}: ok ({dest.stat().st_size // 1_000_000} MB)')
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('book_id', nargs='?')
    p.add_argument('--all', action='store_true')
    p.add_argument('--corpus', default='corpus')
    p.add_argument('--force', action='store_true')
    args = p.parse_args()

    corpus = Path(args.corpus)
    if args.all:
        lib = json.loads((corpus / 'library.json').read_text(encoding='utf-8'))
        ids = list(lib.get('books', {}))
    elif args.book_id:
        ids = [args.book_id]
    else:
        p.error('give a book id or --all')
    ok = all([fetch(b, corpus, args.force) for b in ids])
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
