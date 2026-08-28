#!/usr/bin/env python3
"""Point this at your textbook PDFs; it indexes the ones the library knows.

  tools/add_book.py ~/Books                 # a directory, searched recursively
  tools/add_book.py ~/Books/sabiston.pdf    # or individual files
  tools/add_book.py ~/Books --yes           # skip the confirmation

The problem this solves: index_textbook.py needs a --book-id, --title,
--edition and --year that match corpus/library.json EXACTLY, because those
strings are copied verbatim into every citation the skill writes and the page
numbers in the shipped maps only line up for the right edition. Retyping them
per book is tedious and a near-miss is silent. So this script identifies each
PDF and supplies them for you.

IDENTIFICATION is mostly by page count, which library.json records per book.
It is a sharp signal: it tells apart not just the six books but their editions,
so a 21st-edition Sabiston is caught rather than indexed under the 20th's maps.
The filename is used as a weaker second opinion, and a disagreement between the
two is reported rather than guessed at.

PDFs are referenced where they are, not copied into the corpus (the six books
are ~2.3 GB together). Evidence rendering opens the original path, so moving a
PDF later breaks its highlights until you re-run this; nothing else degrades.
Pass --copy to take a corpus-local copy instead.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INDEXER = REPO / 'skills' / 'nawat-solver' / 'scripts' / 'index_textbook.py'

# Filename hints — the weak signal, checked against the page count's verdict.
HINTS = {
    'sabiston-20e': ('sabiston',),
    'schwartz-11e': ('schwartz',),
    'current-surgical-therapy-14e': ('current', 'cameron'),
    'fischer-mastery-7e': ('fischer', 'mastery'),
    'ascrs-colon-rectal-4e': ('ascrs', 'colon', 'rectal'),
    'mulholland-greenfield-7e': ('greenfield', 'mulholland'),
}

# A book's page count identifies it, but a PDF can carry a few cover/scan pages
# the reference copy lacked. Allow a little slack, and treat an exact hit as
# stronger than a near one.
SLACK = 6

# Measured: 1,699 pages in 5m56s (~0.21 s/page) on the PyMuPDF path with
# pdf-inspector absent, which is what most people will be running. Used only to
# set expectations before a long job — the big books are not quick.
SECONDS_PER_PAGE = 0.21


def eta(pages: int) -> str:
    mins = round(pages * SECONDS_PER_PAGE / 60)
    return f'~{mins} min' if mins >= 1 else 'under a minute'


def page_count(pdf: Path) -> int | None:
    try:
        import pymupdf
    except ImportError:
        sys.exit('pymupdf is required: pip install pymupdf')
    try:
        with pymupdf.open(pdf) as doc:
            return len(doc)
    except Exception as exc:                      # noqa: BLE001 - report, skip
        print(f'  ! {pdf.name}: cannot open ({exc})')
        return None


def identify(pdf: Path, pages: int, library: dict) -> tuple[str | None, str]:
    """Return (book_id, human explanation of how sure we are)."""
    by_pages = [(bid, abs(pages - b['pages'])) for bid, b in library.items()
                if abs(pages - b['pages']) <= SLACK]
    by_pages.sort(key=lambda x: x[1])

    name = pdf.name.lower()
    by_name = [bid for bid, hints in HINTS.items() if any(h in name for h in hints)]

    if by_pages:
        bid, delta = by_pages[0]
        exact = 'exact page match' if delta == 0 else f'page count off by {delta}'
        if by_name and bid not in by_name:
            other = library[by_name[0]]
            return None, (f'CONFLICT: {exact} says {bid}, but the filename says '
                          f'{by_name[0]} ({other["title"]}). Index it by hand.')
        return bid, exact
    if len(by_name) == 1:
        bid = by_name[0]
        want = library[bid]['pages']
        return None, (f'filename looks like {bid}, but it has {pages} pages and '
                      f'that edition has {want}. Probably a different edition: '
                      f'the shipped map.md page numbers would not match, so '
                      f'index it by hand with its own title/edition/year.')
    return None, f'{pages} pages — not one of the six books in library.json'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='+', help='PDF files, or directories to search')
    ap.add_argument('--corpus', default=os.environ.get('NAWAT_CORPUS') or str(REPO / 'corpus'),
                    help='corpus directory (default: $NAWAT_CORPUS, else this checkout)')
    ap.add_argument('--copy', action='store_true',
                    help='copy each PDF into the corpus instead of referencing it in place')
    ap.add_argument('--yes', action='store_true', help='index without confirming')
    args = ap.parse_args()

    corpus = Path(args.corpus).expanduser().resolve()
    lib_path = corpus / 'library.json'
    if not lib_path.exists():
        sys.exit(f'no library.json under {corpus} — is --corpus right?')
    library = json.loads(lib_path.read_text(encoding='utf-8'))['books']

    pdfs: list[Path] = []
    for raw in args.paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            pdfs += sorted(q for q in p.rglob('*.pdf') if not q.name.startswith('.'))
        elif p.is_file():
            pdfs.append(p)
        else:
            print(f'  ! {raw}: not found')
    if not pdfs:
        sys.exit('no PDFs found')

    print(f'{len(pdfs)} PDF(s); corpus {corpus}\n')
    plan, skipped = [], []
    for pdf in pdfs:
        pages = page_count(pdf)
        if pages is None:
            continue
        bid, why = identify(pdf, pages, library)
        installed = (corpus / bid / 'fts.sqlite').exists() if bid else False
        if bid and installed:
            skipped.append((pdf, f'{bid} is already indexed — delete '
                                 f'{corpus / bid} to redo it'))
        elif bid:
            plan.append((pdf, bid, why))
            print(f'  + {pdf.name}\n      -> {bid}  ({why})')
        else:
            skipped.append((pdf, why))

    for pdf, why in skipped:
        print(f'  - {pdf.name}\n      {why}')

    if not plan:
        print('\nnothing to index')
        return 1
    total = sum(library[bid]['pages'] for _, bid, _ in plan)
    if not args.yes:
        print(f'\nindex {len(plan)} book(s), {total:,} pages, {eta(total)} total? [y/N] ',
              end='', flush=True)
        if input().strip().lower() not in ('y', 'yes'):
            print('nothing done')
            return 1

    failed = []
    for i, (pdf, bid, _) in enumerate(plan, 1):
        b = library[bid]
        print(f'\n[{i}/{len(plan)}] {bid} — {b["pages"]} pages, {eta(b["pages"])}')
        cmd = [sys.executable, str(INDEXER), str(pdf.resolve()),
               '--book-id', bid, '--title', b['title'],
               '--edition', b['edition'], '--year', str(b['year']),
               '--corpus', str(corpus)]
        if not args.copy:
            cmd.append('--no-copy')
        if subprocess.run(cmd).returncode != 0:
            failed.append(bid)
            print(f'  ! {bid} failed — see the output above')

    ready = [bid for bid in library if (corpus / bid / 'fts.sqlite').exists()]
    print(f'\n{len(ready)} of {len(library)} books indexed: {", ".join(ready) or "none"}')
    if failed:
        print(f'failed: {", ".join(failed)}')
    print('\nThe maps shipped with this repo already cover these books, so the '
          'skill can route immediately. Ask Claude Code to solve a question.')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
