"""Shared helpers for the nawat-solver export scripts.

THE ENTRY CONTRACT — entries/qNN.json, written by Claude as each question
finishes (it doubles as the batch resume checkpoint):

{
  "id": "q03",
  "source": "batch-07.pdf#3",
  "original": "verbatim original question text, incl. its choices",
  "reformatted": {
    "stem": "board-style vignette ending in the clinical question",
    "choices": [{"letter": "A", "text": "Colonoscopy"}, ...]   // canonical cleaned forms
  },
  "answer": "B",
  "solution": {
    "concept": "UWorld-style explanation body: 1-2 paragraphs of clinical prose following the arc definition/classification -> presentation-linked-to-mechanism -> evaluation/management sequence AS PROSE (never arrow chains), closing with the unlabeled trap sentence when gates found one; **markdown bold** on first mentions of entity/discriminators/tests",
    "why": "consultant-level reasoning for the correct answer",
    "approach": ["Nondestructive single injury → primary repair",     // optional: the paradigm as
                 "Multiple injuries <10 cm apart → segmental resection", // arrow rules — INTERNAL RECORD
                 "Destructive (>50% wall) → resection"],               // only; woven as prose into
                                                                       // concept, rendered NOWHERE
    "other_options": [{"letter": "A", "text": "Colonoscopy",
                       "why_wrong": "...",
                       "would_be_right": "the scenario in which this WOULD be correct"}, ...],
    "common_trap": {"letter": "C",
                    "text": "the trap sentence — ALSO woven verbatim as the closing sentence of concept; this field records it for telemetry"},
                                                                       // optional: only when the critic
                                                                       // raised medium/strong (or SC split)
    "take_home": "one high-yield pearl, phrased like UWorld's Educational objective"
  },
  "tags": {"subjects": ["..."], "systems": ["..."]},
  "references": [
    {"book_id": "sabiston-20e", "title": "Sabiston Textbook of Surgery. The Biological Basis of Modern Surgical Practice",
     "edition": "20th Edition", "year": "2017", "pages": ["1418"]}
    // title/edition/year are COPIED from corpus/<book>/meta.json, which is held
    // equal to the app's canonical citation strings (referenceStandardize.ts).
    // Never retype them: a near-miss title ("Sabiston Textbook of Surgery")
    // survives into the bank until someone runs the manual standardizer sweep.
    // book_id null/absent => general-knowledge citation (not in corpus, unverifiable)
  ],
  "passages": [
    {"book_id": "sabiston-20e", "page": "1418",     // PRINTED folio, not the PDF index
     "quote": "verbatim supporting sentence(s)",
     "paraphrase": "same fact in different words",
     "verified": true, "method": "exact" | "fuzzy",
     "png": "evidence/q3-sabiston-p1418.png",
     "annotated_pdf": ".tmp/q03-ev1.pdf"}
  ],
  "gates": {
    "answer_supported": true,
    "needs_review": false,
    "critic": {"strength": "none" | "weak" | "medium" | "strong",
               "alt": null, "reason": "", "resolved": true},
    "sc": null | {"votes": {"B": 2, "C": 1}, "final": "B", "unanimous": false},
    "distractors_refuted": true,
    "web_check": null | {"checked": true,          // current guidance vs the textbook answer
                         "agrees": false,          // false = guidance has moved on
                         "note": "one line stating BOTH positions",
                         "sources": ["https://…"]}
    // The textbook wins the letter — board exams track the books. A disagreement
    // is SURFACED, never applied: it caps confidence at MODERATE and rides in
    // run_report.csv so a human can decide. Mirrors the audit skill's
    // web-vs-textbook rule (question-review/reference/charter.md).
  },
  "duplicate_of": null | {"id": "batch-03#11", "score": 0.94},
  "negative_leadin": true      // optional: present only for EXCEPT/NOT questions
}

Citation format (locked): "Title, Edition, Year, Page N."  /  "Pages N, M."
"""

from __future__ import annotations

import json
from pathlib import Path


def load_entries(run_dir: Path) -> list[dict]:
    entries = []
    for f in sorted((run_dir / 'entries').glob('q*.json')):
        entries.append(json.loads(f.read_text(encoding='utf-8')))
    return entries


def format_citation(ref: dict) -> str:
    """'Sabiston Textbook of Surgery. The Biological Basis of Modern Surgical Practice, 20th Edition, 2017, Page 1418.'"""
    pages = [str(p) for p in ref.get('pages', [])]
    page_part = None
    if pages:
        page_part = f'Page {pages[0]}' if len(pages) == 1 else f"Pages {', '.join(pages)}"
    bits = [ref.get('title', ''), ref.get('edition', ''), str(ref.get('year', '') or ''), page_part]
    return ', '.join(b for b in bits if b) + '.'


def format_inline_citation(entry: dict, passage: dict) -> str:
    """The parenthetical for a quote/paraphrase: single-page form of the same style."""
    ref = next((r for r in entry.get('references', [])
                if r.get('book_id') == passage.get('book_id')), None)
    if ref is None:
        ref = {'title': passage.get('book_id', 'Unknown source')}
    single = {**ref, 'pages': [passage.get('page', '?')]}
    return f'({format_citation(single)})'


def derive_confidence(entry: dict) -> str:
    """Gate-derived confidence — deterministic, never self-reported.
    First matching rule wins, top to bottom (LOW > MODERATE > HIGH)."""
    g = entry.get('gates', {})
    passages = entry.get('passages', [])
    critic = g.get('critic') or {}
    sc = g.get('sc')

    # LOW
    if g.get('answer_supported') is False:
        return 'LOW'
    if sc and not sc.get('final'):
        return 'LOW'  # no majority
    if any(p.get('verified') is False for p in passages):
        return 'LOW'

    # MODERATE
    if critic.get('strength') == 'medium' and not critic.get('resolved', False):
        return 'MODERATE'
    if sc and not sc.get('unanimous', False):
        return 'MODERATE'  # split vote (e.g. 2-1)
    if any(p.get('verified') and p.get('method') == 'fuzzy' and _page_is_ocr(p)
           for p in passages):
        return 'MODERATE'
    if g.get('distractors_refuted') is False:
        return 'MODERATE'
    web = g.get('web_check') or {}
    if web.get('checked') and web.get('agrees') is False:
        return 'MODERATE'  # current guidance disagrees with the cited textbook

    return 'HIGH'


def _page_is_ocr(passage: dict) -> bool:
    """Fuzzy verification only caps confidence when the page's text layer is
    OCR-derived (or absent) — on native-text pages, fuzzy matches are routine
    extraction artifacts (ligatures, line breaks), not weaker evidence.
    Looks the page up in the book's meta.json; unknown => treat as OCR
    (conservative)."""
    import json as _json
    book, page = passage.get('book_id'), str(passage.get('page', ''))
    if not book:
        return True
    try:
        meta = _json.loads(Path('corpus').joinpath(book, 'meta.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return True
    labels = meta.get('labels', [])
    idx = labels.index(page) if page in labels else (int(page) - 1 if page.isdigit() else -1)
    return idx in set(meta.get('ocr_pages', [])) | set(meta.get('ocr_missing', []))


def strip_markdown(text: str) -> str:
    """Drop markdown emphasis markers for plain-text outputs (the CSV).
    Mirrors the app's cleanMarkdown: bold/italic/code markers removed,
    content kept."""
    import re
    t = text or ''
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)
    t = re.sub(r'(?<!\w)\*(?!\s)(.*?)(?<!\s)\*(?!\w)', r'\1', t)
    return t.replace('`', '')


def md_to_html_bold(text: str) -> str:
    """Convert **bold** markers to <b> for the PDF card (input already HTML-escaped)."""
    import re
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text or '')


def as_sentence(text: str) -> str:
    """Normalize free text into one clean sentence: capitalized, one period."""
    t = (text or '').strip().rstrip('.')
    if not t:
        return ''
    return t[0].upper() + t[1:] + '.'


def trap_sentence(sol: dict) -> str:
    """The common trap as an unlabeled standalone sentence ('' when no trap)."""
    trap = sol.get('common_trap')
    if not trap:
        return ''
    return as_sentence(trap.get('text', ''))


def choices_by_letter(entry: dict) -> dict[str, str]:
    return {c['letter']: c['text'] for c in entry.get('reformatted', {}).get('choices', [])}


def sc_vote_str(entry: dict) -> str:
    sc = entry.get('gates', {}).get('sc')
    if not sc:
        return ''
    votes = sc.get('votes', {})
    ordered = sorted(votes.items(), key=lambda kv: -kv[1])
    return f"{sc.get('final', '?')} {'-'.join(str(v) for _, v in ordered)}"
