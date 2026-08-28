#!/usr/bin/env python3
"""Build per-question PDFs: answer card + references + native highlighted pages.

For each entry, produces pdfs/<id>.pdf laid out as:
  p.1   answer card (original, reformatted vignette + choices, solution,
        take-home, confidence/verification line)
  p.2   references: every citation with its verbatim quote, paraphrase,
        and verified ✓/✗ status
  p.3+  one page per VERIFIED citation — the actual textbook page copied out
        of the source PDF with the yellow highlight annotation applied
        (produced by verify_and_render.py --annotated-pdf). Vector-crisp,
        searchable, citing header strip on top. A failed citation gets NO
        evidence page — the ✗ on p.2 is its record.

--combined additionally concatenates every per-question PDF into batch.pdf.

Usage:
  export_pdf.py runs/2026-08-12-batch-07 [--combined]
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import pymupdf

from _common import (choices_by_letter, derive_confidence, format_citation,
                     format_inline_citation, load_entries, md_to_html_bold,
                     sc_vote_str)

PAGE = pymupdf.paper_rect('a4')
MARGIN = 46

CSS = """
* { font-family: sans-serif; color: #1c2130; }
body { font-size: 10px; line-height: 1.5; }
h1 { font-size: 15px; margin: 0 0 2px 0; }
h2 { font-size: 11px; color: #8a6d00; text-transform: uppercase;
     letter-spacing: 1px; margin: 14px 0 3px 0; }
p { margin: 0 0 6px 0; }
.small { font-size: 8.5px; color: #5a6070; }
.mono { font-family: monospace; font-size: 8.5px; }
blockquote { background: #fff3b0; padding: 6px 10px; margin: 4px 0;
             font-style: italic; }
.verify { background: #eef7ee; padding: 6px 10px; font-size: 8.5px; }
.unverified { background: #fde8e8; padding: 6px 10px; font-size: 8.5px; }
li { margin-bottom: 3px; }
"""


def esc(s: str) -> str:
    return html.escape(s or '')


def card_html(e: dict) -> str:
    ch = e.get('reformatted', {}).get('choices', [])
    sol = e.get('solution', {})
    g = e.get('gates', {})
    conf = e.get('confidence') or derive_confidence(e)
    answer_text = choices_by_letter(e).get(e.get('answer', ''), '')
    tags = e.get('tags', {})
    others = [o for o in sol.get('other_options', []) if o.get('letter') != e.get('answer')]

    parts = [f"<h1>Question {esc(e.get('id', ''))}</h1>",
             f"<p class='small'>{esc(e.get('source', ''))} · "
             f"{esc(' · '.join(tags.get('subjects', []) + tags.get('systems', [])))}</p>",
             "<h2>Original</h2>",
             f"<p class='mono'>{esc(e.get('original', ''))}</p>",
             "<h2>Reformatted</h2>",
             f"<p>{esc(e.get('reformatted', {}).get('stem', ''))}</p>",
             '<p>' + '<br/>'.join(f"{esc(c['letter'])}) {esc(c['text'])}" for c in ch) + '</p>',
             "<h2>Solution</h2>",
             f"<p><b>✅ Answer: {esc(e.get('answer', '?'))} — {esc(answer_text)}</b></p>"]
    if sol.get('concept'):
        parts.append(f"<p>{md_to_html_bold(esc(sol['concept']))}</p>")
    parts.append(f"<p><b>Why:</b> {esc(sol.get('why', ''))}</p>")
    if others:
        items = []
        for o in others:
            item = f"{esc(o['letter'])}) <b>{esc(o.get('text', ''))}</b> — {esc(o.get('why_wrong', ''))}"
            if o.get('would_be_right'):
                item += f" <i>Would be correct if:</i> {esc(o['would_be_right'])}"
            items.append(f'<li>{item}</li>')
        parts.append('<p><b>Other options:</b></p><ul>' + ''.join(items) + '</ul>')
    if sol.get('take_home'):
        parts.append(f"<p><b>📌 Take-home:</b> {esc(sol['take_home'])}</p>")
    critic = (g.get('critic') or {}).get('strength', '—')
    parts.append(
        f"<p class='verify'><b>Confidence: {conf}</b> · critic: {esc(critic)} · "
        f"SC: {esc(sc_vote_str(e) or 'not triggered')} · "
        f"answerSupported: {g.get('answer_supported', '?')} · "
        f"needsReview: {g.get('needs_review', '?')}</p>")
    return f'<body>{"".join(parts)}</body>'


def references_html(e: dict) -> str:
    parts = ["<h1>References &amp; Supporting Passages</h1>"]
    refs = e.get('references', [])
    if refs:
        parts.append('<h2>References</h2><p>' +
                     '<br/>'.join(esc(format_citation(r)) for r in refs) + '</p>')
    for p in e.get('passages', []):
        ok = p.get('verified')
        mark = '✓ verified' + (f" ({p.get('method')})" if p.get('method') else '') if ok else '✗ NOT FOUND IN SOURCE'
        parts.append(f"<h2>{esc(p.get('book_id', '?'))}, p. {esc(str(p.get('page', '?')))} — {mark}</h2>")
        if p.get('quote'):
            parts.append(f"<blockquote>(p. {esc(str(p.get('page', '?')))}) "
                         f"&quot;{esc(p['quote'])}&quot;</blockquote>")
        if p.get('paraphrase'):
            parts.append(f"<p>&quot;{esc(p['paraphrase'])}&quot; "
                         f"{esc(format_inline_citation(e, p))}</p>")
        if not ok:
            parts.append("<p class='unverified'>This citation could not be mechanically verified "
                         "against the source PDF — no evidence page is included for it.</p>")
    if len(parts) == 1:
        parts.append('<p>No textbook references for this question.</p>')
    return f'<body>{"".join(parts)}</body>'


def html_pages(doc: pymupdf.Document, content: str) -> None:
    """Lay out HTML across as many A4 pages as needed and append them to doc."""
    import io

    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    story = pymupdf.Story(html=content, user_css=CSS)
    where = pymupdf.Rect(PAGE.x0 + MARGIN, PAGE.y0 + MARGIN, PAGE.x1 - MARGIN, PAGE.y1 - MARGIN)
    more = 1
    while more:
        dev = writer.begin_page(PAGE)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    rendered = pymupdf.open('pdf', buf.getvalue())
    doc.insert_pdf(rendered)
    rendered.close()


def build_question_pdf(e: dict, run_dir: Path, out_path: Path) -> dict:
    doc = pymupdf.open()
    html_pages(doc, card_html(e))
    html_pages(doc, references_html(e))
    evidence_added = 0
    for p in e.get('passages', []):
        if not p.get('verified') or not p.get('annotated_pdf'):
            continue
        ev_path = run_dir / p['annotated_pdf'] if not Path(p['annotated_pdf']).is_absolute() \
            else Path(p['annotated_pdf'])
        if ev_path.exists():
            ev = pymupdf.open(ev_path)
            doc.insert_pdf(ev)
            ev.close()
            evidence_added += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path, garbage=3, deflate=True)
    pages = len(doc)
    doc.close()
    return {'pdf': str(out_path), 'pages': pages, 'evidence_pages': evidence_added}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('run_dir')
    p.add_argument('--combined', action='store_true', help='also write batch.pdf')
    p.add_argument('--out', default=None,
                   help='output directory for pdfs/ and batch.pdf (default: the run directory)')
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    entries = [e for e in load_entries(run_dir) if not e.get('duplicate_of')]
    if not entries:
        print(f'no solved entries under {run_dir}/entries/')
        return 1

    out_dir = Path(args.out) if args.out else run_dir

    results = []
    for e in entries:
        out = build_question_pdf(e, run_dir, out_dir / 'pdfs' / f"{e.get('id', 'q')}.pdf")
        results.append(out)
        print(f"{out['pdf']}: {out['pages']} pages ({out['evidence_pages']} evidence)")

    if args.combined:
        combined = pymupdf.open()
        for r in results:
            part = pymupdf.open(r['pdf'])
            combined.insert_pdf(part)
            part.close()
        combined.save(out_dir / 'batch.pdf', garbage=3, deflate=True)
        combined.close()
        print(f"{out_dir}/batch.pdf: all {len(results)} questions")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
