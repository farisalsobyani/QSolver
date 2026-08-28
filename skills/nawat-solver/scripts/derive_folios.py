#!/usr/bin/env python3
"""Derive each page's PRINTED folio (the number as it appears in the book) and
record it in the corpus meta.json.

Why this exists: `index_textbook.py:page_labels()` asks PyMuPDF for embedded
page labels and falls back to the 1-based PDF index when a book has none. Only
ASCRS ships real labels, so for the other five books the "label" was the PDF
index wearing a printed-page name — and citations built from it ran 20-45 pages
high (Sabiston PDF p.1000 is printed p.977; CST PDF p.800 is printed p.758).

The folio is not in the extracted corpus text: pdf-inspector filters page
numbers out and offers no option to keep them. So it MUST be read from the PDF's
own text layer (PyMuPDF), where the folio survives as a bare number on the first
or last line of the page.

That makes the text source load-bearing. --pdf is always safe. --from-sqlite is
safe ONLY for an index built from the PDFs (build_textbook_index.py --books-dir);
point it at one built with --from-corpus and you are reading folio-stripped
markdown, which yields a handful of spurious matches, a long interpolated run
from them, and folios that are quietly WRONG. The confirmation-rate guard below
refuses to write in that case.

The offset is piecewise constant, not constant — front matter, inserted plates
and section breaks shift it (Sabiston drifts -23 -> -26 across the book), so a
single global correction is wrong. This walks the book, confirms the running
offset against each page's own printed number, and only switches when a new
offset holds for several consecutive pages.

Usage:
  derive_folios.py --book-id sabiston-20e --pdf "/path/Sabiston.pdf" [--corpus DIR]
  derive_folios.py --book-id sabiston-20e --from-sqlite DB --sqlite-key sabiston
  derive_folios.py --all --from-sqlite DB          # every book the DB carries
  derive_folios.py --book-id ... --check           # report only, write nothing

NOT every book is a print facsimile. A REFLOWED ebook (Greenfield: 6293 US-Letter
pages, 0 of 300 sampled pages carrying ANY text in the outer margins, against
98/100 for Sabiston) has no printed folio anywhere, because it was never printed
that way — its page breaks are conversion artifacts. There is nothing for OCR to
recover. For such a book the PDF page IS the only pagination that exists, so it
is also the correct thing to cite: folios are set equal to the PDF page and the
method recorded as "reflowed". The sawab bank already cites Greenfield this way —
475 of its 489 Greenfield citations carry a page, and all 475 fall inside this
file's 1-6293 — so treating those pages as uncitable would break real citations.

Writes into corpus/<book-id>/meta.json:
  folios        list[str|null] parallel to pages; null = undeterminable
  folio_method  "embedded"  the PDF's own page labels (ASCRS)
                "derived"   read off the printed page (the four print facsimiles)
                "reflowed"  no page furniture exists; folio == PDF page, citable
                "index"     furniture expected but none found — do NOT cite pages
  folio_stats   {confirmed, interpolated, unknown, segments}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

from _common import find_corpus

BARE_NUM = re.compile(r'^(\d{1,4})$')
EDGE_LINES = 2      # folios sit on the first or last line of a page
LOOKAHEAD = 12      # how far to look when testing a candidate new offset
MIN_RUN = 4         # consecutive agreeing pages required to switch offset
MIN_CONFIRMED_FRACTION = 0.5   # below this (but above zero) the read is suspect
MARGIN_BAND = 0.09             # outer fraction of page height that holds furniture
REFLOW_SAMPLE = 300            # pages sampled when asking "is this a reflow?"
REFLOW_MAX_MARGIN_FRACTION = 0.02


def edge_candidates(text: str) -> set[int]:
    """Bare integers on the first/last few non-empty lines — folio candidates."""
    lines = [l.strip() for l in (text or '').split('\n') if l.strip()]
    if not lines:
        return set()
    edges = lines[:EDGE_LINES] + lines[-EDGE_LINES:]
    return {int(m.group(1)) for l in edges if (m := BARE_NUM.match(l))}


def derive(cands: list[set[int]]) -> tuple[list[int | None], list[bool], dict]:
    """Walk the book confirming a running offset; switch only on a sustained run.

    Returns (folios, confirmed_flags, stats). A page whose own folio is printed
    and agrees with the running offset is 'confirmed'; a page with no printed
    folio inherits the offset and is 'interpolated'; pages before the first
    confirmation are None.

    The confirmed flags matter downstream. An UNNUMBERED page inside a run (a
    plate, a section divider) inherits the offset that was current before it,
    and when the offset shifts across that very page the inherited value
    collides with the real folio of its neighbour: Sabiston PDF 118 is
    unnumbered, the offset moves -19 -> -20 over it, and both 118 and 119 come
    out as "99". Only 119 is the printed page 99. Resolving a citation must
    therefore prefer a page whose folio was actually READ off it.
    """
    n = len(cands)
    folios: list[int | None] = [None] * n
    is_confirmed: list[bool] = [False] * n
    offset: int | None = None
    confirmed = interpolated = segments = 0

    for p in range(n):
        page_no = p + 1
        if offset is not None and (page_no + offset) in cands[p]:
            folios[p] = page_no + offset
            is_confirmed[p] = True
            confirmed += 1
            continue
        # Either no offset yet, or this page disagrees. Test each candidate:
        # adopt it only if the same offset is printed on several nearby pages.
        switched = False
        for c in sorted(cands[p]):
            o = c - page_no
            if o == offset:
                continue
            agree = sum(1 for q in range(p, min(n, p + LOOKAHEAD))
                        if (q + 1 + o) in cands[q])
            if agree >= MIN_RUN:
                offset = o
                folios[p] = c
                is_confirmed[p] = True
                confirmed += 1
                segments += 1
                switched = True
                break
        if switched:
            continue
        if offset is not None:
            # No printed folio here (figure page, plate, blank) — carry the run.
            folios[p] = page_no + offset
            interpolated += 1

    return folios, is_confirmed, {'confirmed': confirmed, 'interpolated': interpolated,
                                  'unknown': sum(1 for f in folios if f is None),
                                  'segments': segments}


def pages_from_sqlite(db: Path, key: str) -> list[str]:
    con = sqlite3.connect(db)
    rows = con.execute('SELECT page, text FROM pages WHERE book=? ORDER BY page',
                       (key,)).fetchall()
    con.close()
    return [t or '' for _, t in rows]


def is_reflowed(doc) -> tuple[bool, float]:
    """True when the book has no page furniture at all — a converted ebook.

    Sampled geometrically rather than by parsing text: the folio and running head
    live in the outer margin band, so a book that prints them has text there on
    nearly every page. One that never does was never paginated for print.
    """
    n = doc.page_count
    step = max(1, n // REFLOW_SAMPLE)
    sampled = with_margin = 0
    for i in range(0, n, step):
        page = doc[i]
        h = page.rect.height
        if h <= 0:
            continue
        sampled += 1
        for w in page.get_text("words"):
            if w[3] < h * MARGIN_BAND or w[1] > h * (1 - MARGIN_BAND):
                with_margin += 1
                break
    frac = with_margin / sampled if sampled else 1.0
    return frac <= REFLOW_MAX_MARGIN_FRACTION, frac


def pages_from_pdf(pdf: Path) -> tuple[list[str], list[str | None], tuple[bool, float]]:
    import pymupdf  # noqa: PLC0415  (optional dep, only this path needs it)
    doc = pymupdf.open(pdf)
    reflow = is_reflowed(doc)
    texts, labels = [], []
    for pg in doc:
        texts.append(pg.get_text())
        try:
            lab = pg.get_label()
        except Exception:
            lab = ''
        labels.append(lab or None)
    doc.close()
    return texts, labels, reflow


def run_book(book_id: str, texts: list[str], embedded: list[str | None] | None,
             corpus: Path, check: bool, force: bool = False,
             reflow: tuple[bool, float] | None = None) -> int:
    meta_path = corpus / book_id / 'meta.json'
    if not meta_path.exists():
        print(f'  ! {meta_path} not found', file=sys.stderr)
        return 1
    meta = json.loads(meta_path.read_text(encoding='utf-8'))

    # A book that ships real embedded page labels (ASCRS is the only one of the
    # six) already has them in meta.json:labels — indexing stored them there.
    # Those are authoritative, including the roman-numeral front matter, so
    # prefer them and skip derivation. `labels` equal to the 1-based index is
    # index_textbook.py's fallback, i.e. no labels at all.
    if embedded is None:
        stored = meta.get('labels') or []
        if sum(1 for i, l in enumerate(stored) if l != str(i + 1)) > 0.5 * len(stored):
            embedded = stored

    if reflow and reflow[0]:
        # No page furniture anywhere: the PDF page is the only pagination this
        # book has, so it is also what a citation must carry.
        n_pages = meta.get('pages', len(texts))
        folios = [str(i + 1) for i in range(n_pages)]
        is_confirmed = [True] * n_pages   # the PDF page IS the pagination
        method = 'reflowed'
        stats = {'confirmed': 0, 'interpolated': 0, 'unknown': 0, 'segments': 0,
                 'margin_text_fraction': round(reflow[1], 4)}
    elif embedded and sum(1 for l in embedded if l) > 0.5 * len(embedded):
        folios = [l for l in embedded]
        is_confirmed = [bool(l) for l in folios]   # the PDF's own page labels
        method, stats = 'embedded', {'confirmed': sum(1 for f in folios if f),
                                     'interpolated': 0,
                                     'unknown': sum(1 for f in folios if not f),
                                     'segments': 0}
    else:
        derived, is_confirmed, stats = derive([edge_candidates(t) for t in texts])
        folios = [str(f) if f is not None else None for f in derived]
        method = 'derived' if stats['confirmed'] else 'index'

    n = len(folios)
    pct = 100 * stats['confirmed'] / n if n else 0
    sample = ', '.join(f'pdf {p}->{folios[p - 1]}' for p in (1000, 1500) if p <= n)
    print(f'  {book_id:32s} {method:9s} confirmed {stats["confirmed"]:5d}/{n} '
          f'({pct:.0f}%) interp {stats["interpolated"]:5d} unknown {stats["unknown"]:4d} '
          f'segments {stats["segments"]:3d}  {sample}')

    if check:
        return 0

    # Refuse to overwrite good folios with a bad read. A book with NO folios at
    # all (Greenfield) legitimately confirms zero and records honest nulls; the
    # dangerous shape is a FEW confirmations carrying a long interpolated run,
    # which is what reading folio-stripped text looks like.
    if method != 'reflowed' and 0 < stats['confirmed'] < MIN_CONFIRMED_FRACTION * n and not force:
        print(f'  ! {book_id}: only {stats["confirmed"]}/{n} pages carry a printed '
              f'folio, and {stats["interpolated"]} were interpolated from them — '
              f'refusing to write.\n'
              f'    This is what reading folio-STRIPPED text looks like. Derive from '
              f'the PDF (--pdf) or from a PDF-built index, not from one built with '
              f'build_textbook_index.py --from-corpus.\n'
              f'    Pass --force if you are certain this book really is this sparse.',
              file=sys.stderr)
        return 1

    if len(folios) != meta.get('pages', len(folios)):
        print(f'  ! page count mismatch: meta says {meta.get("pages")}, got {len(folios)}',
              file=sys.stderr)
        return 1
    meta['folios'] = folios
    # True where the folio was READ from that page (or is the pagination itself);
    # False where it was carried over from a neighbour. A carried value can
    # collide with a real one across an unnumbered page, so resolution prefers
    # a confirmed page — see derive().
    meta['folio_confirmed'] = is_confirmed
    meta['folio_method'] = method
    meta['folio_stats'] = stats
    # indent=2 to match what index_textbook.py writes — these files are committed.
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--book-id')
    ap.add_argument('--pdf')
    ap.add_argument('--from-sqlite', help='a prebuilt page-text index to read instead of the PDF')
    ap.add_argument('--sqlite-key', help='book key inside that index (default: --book-id)')
    ap.add_argument('--all', action='store_true', help='every book in --from-sqlite')
    ap.add_argument('--map', action='append', default=[],
                    help='sqlite-key=book-id, repeatable, for --all')
    ap.add_argument('--corpus', default=find_corpus(),
                   help='corpus directory (default: found automatically - $NAWAT_CORPUS, ./corpus, or the one beside the skill)')
    ap.add_argument('--check', action='store_true', help='report only; write nothing')
    ap.add_argument('--force', action='store_true',
                    help='write even when the confirmation rate looks like a bad read')
    args = ap.parse_args()

    corpus = Path(args.corpus).expanduser()
    mapping = dict(m.split('=', 1) for m in args.map)
    rc = 0

    if args.all:
        if not args.from_sqlite:
            ap.error('--all requires --from-sqlite')
        con = sqlite3.connect(args.from_sqlite)
        keys = [r[0] for r in con.execute('SELECT key FROM books ORDER BY key')]
        con.close()
        print(f'deriving folios for {len(keys)} books from {args.from_sqlite}')
        for key in keys:
            book_id = mapping.get(key, key)
            rc |= run_book(book_id, pages_from_sqlite(Path(args.from_sqlite), key),
                           None, corpus, args.check, args.force)
        return rc

    if not args.book_id:
        ap.error('--book-id is required (or use --all)')
    if args.from_sqlite:
        texts = pages_from_sqlite(Path(args.from_sqlite), args.sqlite_key or args.book_id)
        embedded = None
        reflow = None
    elif args.pdf:
        texts, embedded, reflow = pages_from_pdf(Path(args.pdf).expanduser())
    else:
        ap.error('one of --pdf or --from-sqlite is required')
    return run_book(args.book_id, texts, embedded, corpus, args.check, args.force, reflow)


if __name__ == '__main__':
    raise SystemExit(main())
