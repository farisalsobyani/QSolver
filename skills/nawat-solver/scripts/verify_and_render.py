#!/usr/bin/env python3
"""Verify a cited quote against the source PDF and render evidence.

Verification and evidence rendering are the same operation: the text search
that proves the quote exists on the page also yields its coordinates, so the
yellow highlight is free. A quote that cannot be located fails verification
and produces NO evidence — never a faked highlight.

Two match tiers:
  exact — pymupdf search_for (handles line wraps; case-insensitive)
  fuzzy — word-walk with bounded edit distance, ported from src/lib/pdf-render.ts
          (for OCR noise, ligatures, hyphenation splits)

Outputs (all optional, any combination):
  --png OUT.png        rasterized page with highlight (150 dpi default)
  --annotated-pdf OUT  single-page PDF: the real page + highlight annotation
                       + header strip citing book/edition/year/page
                       (export_pdf.py merges these into per-question PDFs)

Prints a JSON verdict:
  {"verified": true, "method": "exact", "book": "...", "page_label": "1418",
   "pdf_page": 1423, "rects": 2, "png": "...", "annotated_pdf": "..."}

Usage:
  verify_and_render.py --corpus corpus --book sabiston-21e --page 1418 \
      --quote "Defecography is the study of choice..." \
      [--png evidence/q3.png] [--annotated-pdf .tmp/q3-ev1.pdf] [--dpi 150]

--page takes the PRINTED page (the folio, as it appears on the page and in the
citation) and is resolved through meta.json:folios; use --pdf-page N
for a raw 1-based PDF index instead.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import pymupdf

YELLOW = (1.0, 0.9, 0.2)


# ---------------------------------------------------------------- text utils

def norm_word(w: str) -> str:
    w = unicodedata.normalize('NFKD', w)
    w = ''.join(c for c in w if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', w.lower())


try:
    # RapidFuzz (C++) when available: same semantics (score_cutoff exceeded
    # returns cutoff+1), 10-100x faster — matters when the fuzzy word-walk
    # scans real textbook pages plus --search-radius neighbors.
    from rapidfuzz.distance import Levenshtein as _Levenshtein

    def bounded_edit_distance(a: str, b: str, cap: int) -> int:
        return _Levenshtein.distance(a, b, score_cutoff=cap)
except ImportError:
    def bounded_edit_distance(a: str, b: str, cap: int) -> int:
        """Pure-Python fallback: Levenshtein with early exit past cap."""
        if abs(len(a) - len(b)) > cap:
            return cap + 1
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i] + [0] * len(b)
            best = cur[0]
            for j, cb in enumerate(b, 1):
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
                best = min(best, cur[j])
            if best > cap:
                return cap + 1
            prev = cur
        return prev[-1]


def words_roughly_match(page_word: str, quote_word: str) -> bool:
    """Port of wordsRoughlyMatch in pdf-render.ts."""
    if page_word == quote_word:
        return True
    if not page_word or not quote_word:
        return False
    min_len = min(len(page_word), len(quote_word))
    if min_len >= 5 and (page_word.startswith(quote_word) or quote_word.startswith(page_word)):
        return True
    max_len = max(len(page_word), len(quote_word))
    if max_len <= 4:
        max_dist = 0
    elif max_len <= 8:
        max_dist = 1
    else:
        max_dist = 2
    return bounded_edit_distance(page_word, quote_word, max_dist) <= max_dist


# ---------------------------------------------------------------- matching

def exact_rects(page: pymupdf.Page, quote: str) -> list[pymupdf.Rect]:
    rects = page.search_for(quote)
    if rects:
        return rects
    # Retry with whitespace collapsed (PDF extraction often differs in spacing)
    collapsed = re.sub(r'\s+', ' ', quote).strip()
    if collapsed != quote:
        rects = page.search_for(collapsed)
    return rects or []


def fuzzy_rects(page: pymupdf.Page, quote: str) -> tuple[list[pymupdf.Rect], float]:
    """Word-walk: slide over page words, greedily consuming quote words with
    tolerance for OCR noise and up to 2 interleaved junk words. Returns the
    matched words' rects and the coverage ratio of the best candidate."""
    quote_words = [norm_word(w) for w in quote.split()]
    quote_words = [w for w in quote_words if w]
    if len(quote_words) < 3:
        return [], 0.0

    raw = page.get_text('words')  # (x0, y0, x1, y1, word, block, line, word_no)
    # Some text layers join tokens with non-ASCII separators (thin space
    # U+2009, NBSP…) that get_text('words') does not split on, e.g. "P : F"
    # extracted as one token. Split those into sub-words sharing the rect.
    page_words = []
    for w in raw:
        rect = pymupdf.Rect(w[:4])
        for frag in w[4].split():
            nw = norm_word(frag)
            if nw:
                page_words.append((rect, nw))

    best: tuple[float, list[pymupdf.Rect]] = (0.0, [])
    n = len(page_words)
    for start in range(n):
        if not words_roughly_match(page_words[start][1], quote_words[0]):
            continue
        rects = [page_words[start][0]]
        qi, skips, matched = 1, 0, 1
        i = start + 1
        while i < n and qi < len(quote_words):
            if words_roughly_match(page_words[i][1], quote_words[qi]):
                rects.append(page_words[i][0])
                matched += 1
                qi += 1
                skips = 0
            else:
                # tolerate a skipped QUOTE word (extraction dropped it) …
                if qi + 1 < len(quote_words) and words_roughly_match(page_words[i][1], quote_words[qi + 1]):
                    rects.append(page_words[i][0])
                    matched += 1
                    qi += 2
                    skips = 0
                else:
                    # … or up to 2 junk PAGE words between matches
                    skips += 1
                    if skips > 2:
                        break
            i += 1
        coverage = matched / len(quote_words)
        if coverage > best[0]:
            best = (coverage, rects)
        if coverage >= 0.98:
            break
    return (best[1], best[0]) if best[0] >= 0.80 else ([], best[0])


def merge_line_rects(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Merge word rects on the same visual line into spans, for clean highlights."""
    if not rects:
        return []
    lines: list[pymupdf.Rect] = []
    for r in sorted(rects, key=lambda r: (round(r.y0, 1), r.x0)):
        if lines and abs(lines[-1].y0 - r.y0) < 3.0:
            lines[-1] |= r
        else:
            lines.append(pymupdf.Rect(r))
    return lines


# ---------------------------------------------------------------- rendering

def render(args, doc: pymupdf.Document, meta: dict, pdf_index: int,
           rects: list[pymupdf.Rect], method: str) -> dict:
    page = doc[pdf_index]
    out: dict = {}
    if rects:
        annot = page.add_highlight_annot(rects)
        annot.set_colors(stroke=YELLOW)
        annot.update()

    if args.png:
        Path(args.png).parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(dpi=args.dpi).save(args.png)
        out['png'] = args.png

    if args.annotated_pdf:
        Path(args.annotated_pdf).parent.mkdir(parents=True, exist_ok=True)
        single = pymupdf.open()
        single.insert_pdf(doc, from_page=pdf_index, to_page=pdf_index)
        sp = single[0]
        # Header strip with the citation, drawn above the page content.
        cite_bits = [meta.get('title', ''), meta.get('edition', ''), meta.get('year', ''),
                     f"Page {args.page or pdf_index + 1}"]
        cite = ', '.join(b for b in cite_bits if b) + '.'
        strip_h = 24
        sp.set_mediabox(pymupdf.Rect(sp.rect.x0, sp.rect.y0 - strip_h, sp.rect.x1, sp.rect.y1))
        strip = pymupdf.Rect(sp.rect.x0, sp.rect.y0, sp.rect.x1, sp.rect.y0 + strip_h)
        sp.draw_rect(strip, color=None, fill=(0.137, 0.149, 0.184))
        sp.insert_textbox(strip + (10, 0, -10, 0), cite, fontsize=9,
                          fontname='helv', color=(1, 1, 1), align=0)
        single.save(args.annotated_pdf)
        single.close()
        out['annotated_pdf'] = args.annotated_pdf
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--corpus', default='corpus')
    p.add_argument('--book', required=True)
    p.add_argument('--page', default=None, help='display page label (as printed in the book)')
    p.add_argument('--pdf-page', type=int, default=None, help='1-based raw PDF page index')
    p.add_argument('--quote', required=True)
    p.add_argument('--png', default=None)
    p.add_argument('--annotated-pdf', default=None)
    p.add_argument('--dpi', type=int, default=150)
    p.add_argument('--search-radius', type=int, default=2,
                   help='also try +/- N neighboring pages when the quote is not on the cited page')
    args = p.parse_args()

    book_dir = Path(args.corpus) / args.book
    meta = json.loads((book_dir / 'meta.json').read_text(encoding='utf-8'))
    source = book_dir / meta.get('source', 'source.pdf')
    if not source.exists():
        print(json.dumps({'verified': False, 'error': 'source PDF not present in this session',
                          'fix': f'python3 .claude/skills/nawat-solver/scripts/fetch_book.py {args.book}'}))
        return 3
    doc = pymupdf.open(source)
    # Resolve a citation's printed page to a PDF index via meta.json:folios.
    # `labels` is only the PDF's embedded labels (or the bare index) and is a
    # last resort: for most books it equals the bare index, so trusting it
    # would open a page 20-45 sheets away from the one being cited.
    folios: list[str | None] = meta.get('folios') or []
    # A folio can appear twice: an UNNUMBERED page inside a run inherits its
    # neighbour's offset, and where the offset shifts across that page the
    # carried value duplicates the real folio next door (Sabiston 118/119 both
    # read "99"; only 119 is printed 99). Prefer the page the folio was READ
    # from, falling back to first-match for an index written before the flags.
    confirmed: list[bool] = meta.get('folio_confirmed') or []
    labels: list[str] = meta.get('labels', [])

    def folio_index(want: str) -> int | None:
        hits = [i for i, f in enumerate(folios) if f == want]
        if not hits:
            return None
        for i in hits:
            if i < len(confirmed) and confirmed[i]:
                return i
        return hits[0]


    if args.pdf_page is not None:
        base = args.pdf_page - 1
    elif args.page is not None:
        if (idx := folio_index(args.page)) is not None:
            base = idx
        elif args.page in labels:
            base = labels.index(args.page)
        else:
            print(json.dumps({
                'verified': False, 'book': args.book, 'page_label': args.page,
                'error': f'page {args.page} is not a known printed page for {args.book}',
                'fix': 'cite a folio reported by search.py, or pass --pdf-page N; '
                       'if this book has no folios, run derive_folios.py'}))
            return 3
    else:
        p.error('one of --page or --pdf-page is required')

    candidates = [base]
    for d in range(1, args.search_radius + 1):
        candidates += [base - d, base + d]
    candidates = [c for c in candidates if 0 <= c < len(doc)]

    verdict = {'verified': False, 'method': None, 'book': args.book,
               'page_label': args.page, 'pdf_page': None, 'rects': 0, 'coverage': 0.0}

    for idx in candidates:
        page = doc[idx]
        rects = exact_rects(page, args.quote)
        method = 'exact'
        coverage = 1.0
        if not rects:
            rects, coverage = fuzzy_rects(page, args.quote)
            method = 'fuzzy'
        if rects:
            rects = merge_line_rects(rects)
            verdict.update(verified=True, method=method, pdf_page=idx + 1,
                           page_label=(folios[idx] if idx < len(folios) and folios[idx]
                                       else (labels[idx] if idx < len(labels) else str(idx + 1))),
                           rects=len(rects), coverage=round(coverage, 3),
                           moved=(idx != base))
            verdict.update(render(args, doc, meta, idx, rects, method))
            break

    if not verdict['verified'] and args.png:
        # Failed verification: no highlight is ever rendered. A plain page
        # render is still useful context for review, but it is named to make
        # the failure impossible to miss.
        fail_png = re.sub(r'\.png$', '.UNVERIFIED.png', args.png)
        Path(fail_png).parent.mkdir(parents=True, exist_ok=True)
        doc[base].get_pixmap(dpi=args.dpi).save(fail_png)
        verdict['png'] = fail_png

    doc.close()
    print(json.dumps(verdict, ensure_ascii=False))
    return 0 if verdict['verified'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
