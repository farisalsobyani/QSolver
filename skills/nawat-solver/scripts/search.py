#!/usr/bin/env python3
"""BM25 keyword search over indexed textbook pages.

Complements the semantic map: the map routes by concept, this recalls by exact
term (drug names, eponyms, thresholds, numbers). Results are page-level; open
the page file (corpus/<book>/pages/pNNNN.txt) or neighbors for full context.

Usage:
  search.py "closed loop obstruction" [--book sabiston-20e] [--corpus corpus]
            [--limit 8] [--json]

Two different page numbers travel with every hit and they are NOT the same:
  folio — the number PRINTED on the page. This is the one that goes in a
          citation. It comes from meta.json:folios (see derive_folios.py).
  page  — the 1-based PDF page, i.e. which pNNNN.txt to open. Never cite it;
          it runs 20-45 pages ahead of the folio in most of these books.
A book whose folios could not be derived (Greenfield) reports folio `null` /
`p.?`. Cite such a page as an unnumbered reference or pick another source —
do NOT fall back to the PDF page and call it a printed page.

Output (text mode): one hit per line —  book p.FOLIO (pdf#N, score S): snippet
Output (--json): one JSON object per line with
book/page/folio/label/score/snippet.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from pathlib import Path


def default_corpus() -> str:
    """The corpus directory to use when --corpus is not given.

    $NAWAT_CORPUS lets an operator keep one library outside whatever directory
    they happen to be running from; ./corpus stays the default so a checkout
    with a corpus in it needs no setup at all.
    """
    return os.environ.get('NAWAT_CORPUS') or 'corpus'


def fts_query(raw: str) -> str:
    """Turn a free-text query into a safe FTS5 OR-query of quoted terms."""
    terms = re.findall(r'[A-Za-z0-9]+', raw)
    if not terms:
        return '""'
    return ' OR '.join(f'"{t}"' for t in terms)


def load_folios(corpus: Path, book_id: str) -> list[str | None]:
    """meta.json:folios — printed page per PDF page. Empty when never derived."""
    meta = corpus / book_id / 'meta.json'
    if not meta.exists():
        return []
    try:
        return json.loads(meta.read_text(encoding='utf-8')).get('folios') or []
    except (json.JSONDecodeError, ValueError):
        return []


def search_book(db: Path, query: str, limit: int) -> list[dict]:
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT book, page, label, snippet(pages, 3, '[', ']', ' … ', 18), bm25(pages) "
            'FROM pages WHERE pages MATCH ? ORDER BY bm25(pages) LIMIT ?',
            (fts_query(query), limit),
        ).fetchall()
    finally:
        con.close()
    return [
        {'book': r[0], 'page': r[1], 'label': r[2], 'snippet': re.sub(r'\s+', ' ', r[3]).strip(),
         'score': round(-r[4], 3)}  # bm25() returns lower-is-better; negate so higher is better
        for r in rows
    ]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('query')
    p.add_argument('--book', default=None, help='book id; searches every indexed book when omitted')
    p.add_argument('--corpus', default=default_corpus(),
                   help='corpus directory (default: $NAWAT_CORPUS, else ./corpus)')
    p.add_argument('--limit', type=int, default=8)
    p.add_argument('--json', action='store_true')
    args = p.parse_args()

    corpus = Path(args.corpus)
    dbs = ([corpus / args.book / 'fts.sqlite'] if args.book
           else sorted(corpus.glob('*/fts.sqlite')))
    dbs = [d for d in dbs if d.exists()]
    if not dbs:
        print(json.dumps({'error': 'no indexed books found', 'corpus': str(corpus)}))
        return 1

    # Book priorities from library.json (lower = preferred). Priority groups
    # results across books; BM25 scores rank within a book. Cross-book BM25
    # scores aren't strictly comparable anyway, so grouping is more honest
    # than pretending a global score sort means something.
    priorities: dict[str, int] = {}
    lib_path = corpus / 'library.json'
    if lib_path.exists():
        try:
            books = json.loads(lib_path.read_text(encoding='utf-8')).get('books', {})
            priorities = {bid: int(b.get('priority', 100)) for bid, b in books.items()}
        except (json.JSONDecodeError, ValueError):
            pass

    hits: list[dict] = []
    for db in dbs:
        hits.extend(search_book(db, args.query, args.limit))
    folios: dict[str, list[str | None]] = {}
    for h in hits:
        h['priority'] = priorities.get(h['book'], 100)
        book = h['book']
        if book not in folios:
            folios[book] = load_folios(corpus, book)
        table = folios[book]
        idx = h['page'] - 1
        h['folio'] = table[idx] if 0 <= idx < len(table) else None
    hits.sort(key=lambda h: (h['priority'], -h['score']))
    hits = hits[: args.limit]

    for h in hits:
        if args.json:
            print(json.dumps(h, ensure_ascii=False))
        else:
            folio = h['folio'] or '?'
            print(f"{h['book']} p.{folio} (pdf#{h['page']}, {h['score']}, "
                  f"prio {h['priority']}): {h['snippet']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
