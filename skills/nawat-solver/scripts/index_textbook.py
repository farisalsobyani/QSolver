#!/usr/bin/env python3
"""Index a textbook PDF into the corpus.

Produces, under corpus/<book-id>/:
  source.pdf     — the PDF itself (copied in; tracked by Git LFS via corpus/.gitattributes)
  pages/pNNNN.txt — extracted text, one file per page (plain git; greppable)
  meta.json      — page count, display-page labels, OCR page list, title/edition/year
  fts.sqlite     — FTS5 (BM25) index over pages, used by search.py

and registers the book in corpus/library.json.

Pages with no text layer are OCR'd via Tesseract when available (pytesseract);
otherwise they are recorded in meta.json under "ocr_missing" so verification
knows to degrade gracefully (full-page evidence, no highlight).

The semantic map (corpus/<book-id>/map.md) is NOT written here — it is written
by Claude after indexing, by reading the book's structure. This script prints
a page-per-chapter hint (font-size-based heading candidates) to help.

Usage:
  index_textbook.py path/to/book.pdf --book-id sabiston-21e \
      --title "Sabiston Textbook of Surgery" --edition "21st Edition" --year 2022 \
      [--corpus corpus] [--no-copy]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from pathlib import Path

import pymupdf

from derive_folios import (derive as derive_page_folios, edge_candidates,
                           is_reflowed)


def extract_with_pdf_inspector(pdf_path: Path, page_count: int) -> tuple[list[str], list[int]] | None:
    """Preferred extractor: firecrawl/pdf-inspector — structured per-page
    markdown with multi-column reading order, heading levels, table detection,
    and principled OCR routing (incl. broken-encoding detection, which a
    text-length heuristic misses). Returns (texts, needs_ocr_indices), or
    None when the library is unavailable or fails (caller falls back to
    PyMuPDF)."""
    try:
        import pdf_inspector
    except ImportError:
        return None
    try:
        res = pdf_inspector.extract_pages_markdown(str(pdf_path))
    except Exception:
        return None
    texts = [''] * page_count
    needs_ocr: list[int] = []
    # Page-number indexing differs between pdf-inspector APIs (TextItem.page
    # is 1-indexed; extract_pages_markdown pages are 0-indexed). Detect from
    # the data instead of trusting either convention.
    numbers = [p.page for p in res.pages]
    offset = 0 if (numbers and min(numbers) == 0) else 1
    for page in res.pages:
        idx = page.page - offset
        if 0 <= idx < page_count:
            texts[idx] = (page.markdown or '').strip()
            if getattr(page, 'needs_ocr', False):
                needs_ocr.append(idx)
    return texts, needs_ocr


def extract_pages(doc: pymupdf.Document, book_dir: Path, pdf_path: Path) -> tuple[list[str], list[int], list[int], str]:
    """Extract text per page. pdf-inspector first (better reading order on
    two-column textbook layouts, markdown structure for the semantic map);
    PyMuPDF text extraction as fallback; Tesseract OCR for pages both flag
    as image-only. Returns (texts, ocr_pages, ocr_missing, extractor)."""
    pages_dir = book_dir / 'pages'
    pages_dir.mkdir(parents=True, exist_ok=True)
    ocr_pages: list[int] = []
    ocr_missing: list[int] = []

    try:
        import pytesseract  # noqa: F401
        have_tesseract = shutil.which('tesseract') is not None
    except ImportError:
        have_tesseract = False

    def ocr_page(i: int) -> str | None:
        if not have_tesseract:
            return None
        try:
            tp = doc[i].get_textpage_ocr(flags=0, full=True)
            return doc[i].get_text('text', textpage=tp).strip()
        except Exception:
            return None

    pi = extract_with_pdf_inspector(pdf_path, len(doc))
    if pi is not None:
        texts, flagged = pi
        extractor = 'pdf-inspector'
        retry = set(flagged) | {i for i, t in enumerate(texts) if len(t) < 20}
    else:
        texts = [doc[i].get_text('text').strip() for i in range(len(doc))]
        extractor = 'pymupdf'
        retry = {i for i, t in enumerate(texts) if len(t) < 20}

    for i in sorted(retry):
        # pdf-inspector flagged the page (or it came back empty): try the
        # PyMuPDF text layer before paying for OCR — the flag can also mean
        # "layout I could not handle", not only "scanned".
        alt = doc[i].get_text('text').strip()
        if len(alt) >= 20 and len(alt) > len(texts[i]):
            texts[i] = alt
            continue
        if len(texts[i]) >= 20:
            continue
        ocred = ocr_page(i)
        if ocred and len(ocred) >= 20:
            texts[i] = ocred
            ocr_pages.append(i)
        else:
            ocr_missing.append(i)

    for i, text in enumerate(texts):
        (pages_dir / f'p{i + 1:04d}.txt').write_text(text + '\n', encoding='utf-8')
    return texts, ocr_pages, ocr_missing, extractor


def build_fts(book_id: str, texts: list[str], labels: list[str], db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    # porter stemming so 'obstruction' also recalls 'obstructions'/'obstructive'.
    # The question-review skill's verifier searches this index for PARAPHRASED
    # passages, where stemming is what makes a reworded query land at all.
    con.execute('CREATE VIRTUAL TABLE pages USING fts5(book, page UNINDEXED, '
                "label UNINDEXED, text, tokenize='porter unicode61')")
    con.executemany(
        'INSERT INTO pages (book, page, label, text) VALUES (?, ?, ?, ?)',
        [(book_id, i + 1, labels[i], t) for i, t in enumerate(texts)],
    )
    con.commit()
    con.close()


def page_labels(doc: pymupdf.Document) -> list[str]:
    """The PDF's OWN embedded page labels, or the 1-based index when it has none.

    Only ASCRS of the six corpus books ships these. The index fallback is NOT a
    printed page number and must never be cited as one — see derive_folios.py,
    which recovers the real folio from the page text. Kept for compatibility;
    `meta.json:folios` is what citations use.
    """
    labels = []
    for i in range(len(doc)):
        try:
            lab = doc[i].get_label()
        except Exception:
            lab = ''
        labels.append(lab if lab else str(i + 1))
    return labels


def markdown_heading_hints(texts: list[str], limit: int = 300) -> list[dict]:
    """When pdf-inspector extracted the pages, its markdown headings are the
    best map skeleton: real heading levels in reading order, per page."""
    hints = []
    for i, text in enumerate(texts):
        for line in text.splitlines():
            m = re.match(r'^(#{1,4})\s+(.{4,120})$', line.strip())
            if m and re.search(r'[A-Za-z]{4,}', m.group(2)):
                hints.append({'page': i + 1, 'level': len(m.group(1)), 'text': m.group(2).strip()})
    if len(hints) > limit:  # keep the highest levels when a book floods H3/H4
        for max_level in (3, 2, 1):
            kept = [h for h in hints if h['level'] <= max_level]
            if len(kept) <= limit or max_level == 1:
                return kept[:limit]
    return hints


def heading_hints(doc: pymupdf.Document, limit: int = 200) -> list[dict]:
    """Fallback (PyMuPDF path): rough chapter-heading candidates by font
    size, to help Claude write the semantic map without reading blind."""
    hints = []
    for i, page in enumerate(doc):
        try:
            d = page.get_text('dict')
        except Exception:
            continue
        best = None
        for block in d.get('blocks', []):
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    txt = span.get('text', '').strip()
                    if 4 <= len(txt) <= 120 and span.get('size', 0) >= 16:
                        if best is None or span['size'] > best[0]:
                            best = (span['size'], txt)
        if best and re.search(r'[A-Za-z]{4,}', best[1]):
            hints.append({'page': i + 1, 'size': round(best[0], 1), 'text': best[1]})
    # keep the largest N so huge books don't flood the output
    hints.sort(key=lambda h: -h['size'])
    return sorted(hints[:limit], key=lambda h: h['page'])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('pdf', nargs='?', default=None,
                   help='source PDF path (not needed with --rebuild-fts)')
    p.add_argument('--book-id', required=True, help='corpus slug, e.g. sabiston-20e')
    p.add_argument('--title', default=None,
                   help="display title used in citations; MUST equal the app's canonical "
                        'string for this book (src/lib/referenceStandardize.ts)')
    p.add_argument('--edition', default='', help='e.g. "20th Edition"')
    p.add_argument('--year', default='', help='4-digit publication year')
    p.add_argument('--corpus', default='corpus')
    p.add_argument('--priority', type=int, default=100,
                   help='citation/retrieval priority; LOWER = preferred (1 = primary reference). '
                        'Editable later in corpus/library.json without re-indexing.')
    p.add_argument('--drive-id', default='',
                   help='Google Drive file id of the source PDF (drive-fetch storage model: '
                        'PDFs are gitignored; fetch_book.py re-downloads by this id)')
    p.add_argument('--no-copy', action='store_true', help='reference the PDF in place instead of copying')
    p.add_argument('--rebuild-fts', action='store_true',
                   help='rebuild fts.sqlite from the committed pages/*.txt (no PDF needed); '
                        'positional pdf argument is ignored')
    args = p.parse_args()

    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', args.book_id):
        p.error('--book-id must be a lowercase slug (a-z, 0-9, hyphens)')

    if args.rebuild_fts:
        book_dir = Path(args.corpus) / args.book_id
        meta = json.loads((book_dir / 'meta.json').read_text(encoding='utf-8'))
        texts = [(book_dir / 'pages' / f'p{i + 1:04d}.txt').read_text(encoding='utf-8').strip()
                 for i in range(meta['pages'])]
        build_fts(args.book_id, texts, meta['labels'], book_dir / 'fts.sqlite')
        print(json.dumps({'ok': True, 'rebuilt_fts': args.book_id, 'pages': meta['pages']}))
        return 0

    if not args.pdf or not args.title:
        p.error('pdf path and --title are required when indexing')

    src = Path(args.pdf)
    corpus = Path(args.corpus)
    book_dir = corpus / args.book_id
    book_dir.mkdir(parents=True, exist_ok=True)

    dest = book_dir / 'source.pdf'
    if not args.no_copy and src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
        pdf_path = dest
    else:
        pdf_path = src

    doc = pymupdf.open(pdf_path)
    labels = page_labels(doc)
    # Printed folios, for citations. Derived from PyMuPDF's own text rather than
    # from `texts`: pdf-inspector strips running headers, taking the folio with
    # them. Embedded labels, where a book has them, win outright.
    # Order matches derive_folios.run_book exactly; the two must not diverge.
    reflowed, margin_fraction = is_reflowed(doc)
    if reflowed:
        # A converted ebook has no page furniture at all, so the PDF page is the
        # only pagination it has — and therefore the thing a citation carries.
        folios: list[str | None] = [str(i + 1) for i in range(len(doc))]
        folio_confirmed = [True] * len(doc)
        folio_method = 'reflowed'
        folio_stats = {'confirmed': 0, 'interpolated': 0, 'unknown': 0, 'segments': 0,
                       'margin_text_fraction': round(margin_fraction, 4)}
    elif sum(1 for i, l in enumerate(labels) if l != str(i + 1)) > 0.5 * len(labels):
        folios = list(labels)
        folio_confirmed = [bool(l) for l in folios]
        folio_method = 'embedded'
        folio_stats = {'confirmed': len(labels), 'interpolated': 0, 'unknown': 0, 'segments': 0}
    else:
        derived, folio_confirmed, folio_stats = derive_page_folios(
            [edge_candidates(pg.get_text()) for pg in doc])
        folios = [str(f) if f is not None else None for f in derived]
        folio_method = 'derived' if folio_stats['confirmed'] else 'index'

    texts, ocr_pages, ocr_missing, extractor = extract_pages(doc, book_dir, pdf_path)
    build_fts(args.book_id, texts, labels, book_dir / 'fts.sqlite')

    meta = {
        'book_id': args.book_id,
        'title': args.title,
        'edition': args.edition,
        'year': args.year,
        'pages': len(doc),
        'labels': labels,                # the PDF's embedded labels, or the index
        'folios': folios,                # PRINTED page per PDF page — cite THIS
        'folio_confirmed': folio_confirmed,  # read off the page vs carried over
        'folio_method': folio_method,    # embedded | derived | reflowed | index
        'folio_stats': folio_stats,
        'ocr_pages': ocr_pages,          # OCR'd successfully at index time
        'ocr_missing': ocr_missing,      # no text layer AND no OCR available
        'extractor': extractor,          # pdf-inspector | pymupdf
        'drive_file_id': args.drive_id,  # fetch_book.py re-downloads by this
        'source': 'source.pdf' if not args.no_copy else str(src),
    }
    (book_dir / 'meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')

    # Register in the library.
    lib_path = corpus / 'library.json'
    library = json.loads(lib_path.read_text(encoding='utf-8')) if lib_path.exists() else {'books': {}}
    library['books'][args.book_id] = {
        'title': args.title, 'edition': args.edition, 'year': args.year,
        'pages': len(doc), 'map': (book_dir / 'map.md').exists(),
        'priority': args.priority,
    }
    lib_path.write_text(json.dumps(library, indent=2), encoding='utf-8')

    hints = markdown_heading_hints(texts) if extractor == 'pdf-inspector' else heading_hints(doc)
    doc.close()

    print(json.dumps({
        'ok': True, 'book_id': args.book_id, 'pages': len(texts),
        'extractor': extractor,
        'ocr_pages': len(ocr_pages), 'ocr_missing': len(ocr_missing),
        'next_step': f'write the semantic map at {book_dir}/map.md (chapter/section summaries with page ranges)',
        'heading_hints': hints,
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
