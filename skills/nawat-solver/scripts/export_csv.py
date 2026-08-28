#!/usr/bin/env python3
"""Export a run's entries to question_bank.csv, run_report.csv, and answers.md.

question_bank.csv is byte-compatible with the app's Nawat_QuestionBank.csv
(src/lib/export-csv.ts): the exact same 19 headers, RFC-4180 quoting, CRLF
line endings, and a UTF-8 BOM so Excel detects the encoding. Duplicates are
NOT rows here (they aren't new questions); they appear only in run_report.csv.

THE HEADER NAMES ARE DELIBERATE — do not "fix" them to match the sawab bank.
`Subjects`/`Systems`/`Paraphrased Passages` are what this file has always used
and what the Nawat app's own export emits. On the sawab side that means:
  BulkImport (creating new questions) accepts all three as aliases — this file
    imports cleanly, which is the one job it has.
  CsvSync (round-trip EDITING of existing questions) accepts only the singular
    `Subject`/`System`; it does take `Paraphrased Passages` for cited passages.
So a file from here CREATES questions but cannot UPDATE them. That is correct:
updates are the question-review skill's job and travel on its 15-column v2 CSV,
which is column-restricted on purpose. Renaming these headers would buy an
update path this file should not have, at the cost of the app compatibility it
does need.

run_report.csv carries the pipeline telemetry the app format has no place
for: confidence, critic verdict, SC vote, verification status, file links.

Usage:
  export_csv.py runs/2026-08-12-batch-07
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

from _common import (choices_by_letter, derive_confidence, format_citation,
                     format_inline_citation, load_entries, sc_vote_str,
                     strip_markdown)

QB_HEADERS = ['ID', 'Original Question', 'Reformatted Question',
              'Choice A', 'Choice B', 'Choice C', 'Choice D', 'Choice E',
              'Correct Answer', 'Concept', 'Why', 'Reasons Wrong Answers Are Wrong',
              'Take-Home Message', 'References', 'Supporting Passage',
              'Paraphrased Passages', 'Subjects', 'Systems', 'Needs Review']

RR_HEADERS = ['q', 'source', 'answer', 'confidence', 'critic', 'sc_vote',
              'answer_supported', 'needs_review', 'web_check', 'citations',
              'pdf', 'evidence', 'duplicate_of']


def write_csv(path: Path, rows: list[list[str]]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator='\r\n')
    w.writerows(rows)
    path.write_text('﻿' + buf.getvalue(), encoding='utf-8')


def wrong_line(o: dict) -> str:
    """One line per distractor, in the bank's house shape: '<Letter>: <choice>: <why>'.

    QuestionCard renders this field by splitting on single newlines and matching
    `^([A-Ea-e]):\\s*([^:]+):(.*)$`, bolding the letter + whatever precedes the
    SECOND colon as the option label. Without the choice text in that slot, a
    'Would be correct if:' clause supplies the second colon and the whole
    rationale renders bold as if it were the option. Emitting the choice text
    keeps the label short and correct, and matches what the audit skill's field
    spec expects of this column.
    """
    label = (o.get('text') or '').replace(':', ' -').strip()
    head = f"{o['letter']}: {label}: " if label else f"{o['letter']}: "
    line = head + o.get('why_wrong', '')
    if o.get('would_be_right'):
        line += f" Would be correct if: {o['would_be_right']}"
    return line


def question_bank_row(entry: dict, row_id: int) -> list[str]:
    ch = choices_by_letter(entry)
    sol = entry.get('solution', {})
    wrong = '\n'.join(wrong_line(o) for o in sol.get('other_options', [])
                      if o.get('letter') != entry.get('answer'))
    refs = '\n'.join(format_citation(r) for r in entry.get('references', []))
    # Passages are separated by a BLANK line, not a single newline: the app
    # splits cited_passages on /\n\s*\n/ to give each passage its own bubble and
    # falls back to one bubble for the whole cell when it finds no blank breaks.
    passages = '\n\n'.join(f"(p. {p.get('page', '?')}) \"{p.get('quote', '')}\""
                           for p in entry.get('passages', []) if p.get('quote'))
    paraphrased = '\n\n'.join(
        f"\"{p.get('paraphrase', '')}\" {format_inline_citation(entry, p)}"
        for p in entry.get('passages', []) if p.get('paraphrase'))
    tags = entry.get('tags', {})
    row = [
        str(row_id),
        entry.get('original', ''),
        entry.get('reformatted', {}).get('stem', ''),
        ch.get('A', ''), ch.get('B', ''), ch.get('C', ''), ch.get('D', ''), ch.get('E', ''),
        entry.get('answer', ''),
        # UWorld model: the Concept column is the explanation prose alone —
        # the approach is woven into it as sentences by the writer, and the
        # arrow-rule box is a figure that lives only in PDF/answers.md.
        sol.get('concept', ''),
        sol.get('why', ''),
        wrong,
        sol.get('take_home', ''),
        refs,
        passages,
        paraphrased,
        ', '.join(tags.get('subjects', [])),
        ', '.join(tags.get('systems', [])),
        'Yes' if entry.get('gates', {}).get('needs_review') else '',
    ]
    # The CSV is plain text — markdown emphasis (UWorld-style **bold**) is
    # stripped here, mirroring the app's cleanMarkdown.
    return [strip_markdown(cell) for cell in row]


def run_report_row(entry: dict) -> list[str]:
    dup = entry.get('duplicate_of')
    if dup:
        return [entry.get('id', ''), entry.get('source', ''), '', '', '', '', '', '',
                '', '', '', '', f"{dup.get('id', '?')} ({dup.get('score', '?')})"]
    g = entry.get('gates', {})
    critic = g.get('critic') or {}
    critic_str = critic.get('strength', '')
    if critic_str == 'strong' and g.get('sc'):
        critic_str = 'strong→SC'
    cites = '; '.join(
        f"{p.get('book_id', '?')} p.{p.get('page', '?')} {'✓' if p.get('verified') else '✗'}"
        for p in entry.get('passages', []))
    pngs = '; '.join(p.get('png', '') for p in entry.get('passages', []) if p.get('png'))
    # Guideline drift, surfaced not applied: 'disagrees' means current guidance
    # has moved past the cited textbook. The letter still follows the book.
    web = g.get('web_check') or {}
    if not web.get('checked'):
        web_str = 'not checked'
    elif web.get('agrees') is False:
        web_str = f"disagrees: {web.get('note', '')}".strip()
    else:
        web_str = 'agrees'
    return [
        entry.get('id', ''), entry.get('source', ''), entry.get('answer', ''),
        entry.get('confidence') or derive_confidence(entry),
        critic_str, sc_vote_str(entry),
        str(g.get('answer_supported', '')).lower(),
        str(g.get('needs_review', '')).lower(),
        web_str,
        cites or '(none found)',
        f"pdfs/{entry.get('id', '')}.pdf",
        pngs, '',
    ]


def answers_md(entries: list[dict]) -> str:
    out = []
    for i, e in enumerate(entries, 1):
        if e.get('duplicate_of'):
            dup = e['duplicate_of']
            out.append(f"## Question {i} — {e.get('source', '')}\n\n"
                       f"*Skipped: duplicate of {dup.get('id')} (score {dup.get('score')}).*\n")
            continue
        ch = e.get('reformatted', {}).get('choices', [])
        sol = e.get('solution', {})
        conf = e.get('confidence') or derive_confidence(e)
        g = e.get('gates', {})
        critic = (g.get('critic') or {}).get('strength', '—')
        lines = [f"## Question {i} — {e.get('source', '')}", '',
                 '### Original', '', e.get('original', ''), '',
                 '### Reformatted', '', e.get('reformatted', {}).get('stem', ''), '']
        lines += [f"{c['letter']}) {c['text']}" for c in ch]
        answer_text = choices_by_letter(e).get(e.get('answer', ''), '')
        lines += ['', '### Solution', '',
                  f"✅ **Answer**: {e.get('answer', '?')} — {answer_text}", '']
        if sol.get('concept'):
            lines += [sol['concept'], '']
        lines += [f"**Why:** {sol.get('why', '')}", '']
        others = [o for o in sol.get('other_options', []) if o.get('letter') != e.get('answer')]
        if others:
            lines.append('**Other options:**')
            for o in others:
                item = f"- {o['letter']}) **{o.get('text', '')}** — {o.get('why_wrong', '')}"
                if o.get('would_be_right'):
                    item += f" *Would be correct if:* {o['would_be_right']}"
                lines.append(item)
            lines.append('')
        if sol.get('take_home'):
            lines += [f"📌 **Take-home:** {sol['take_home']}", '']
        tags = e.get('tags', {})
        if tags.get('subjects') or tags.get('systems'):
            lines += ['### Tags', '',
                      f"Subjects: {', '.join(tags.get('subjects', []))} · "
                      f"Systems: {', '.join(tags.get('systems', []))}", '']
        if e.get('references'):
            lines += ['### References', '']
            lines += [format_citation(r) for r in e['references']]
            lines.append('')
        verified_ps = [p for p in e.get('passages', []) if p.get('quote')]
        if verified_ps:
            lines += ['### Supporting Passage', '']
            for p in verified_ps:
                mark = '✓' if p.get('verified') else '✗ UNVERIFIED'
                lines.append(f"> (p. {p.get('page', '?')}) \"{p.get('quote', '')}\"  [{mark}]")
                if p.get('png'):
                    lines.append(f">\n> 🖼 `{p['png']}`")
                lines.append('')
            lines += ['### Paraphrased Passage', '']
            for p in verified_ps:
                if p.get('paraphrase'):
                    lines.append(f"\"{p['paraphrase']}\" {format_inline_citation(e, p)}")
            lines.append('')
        lines += [f"**Confidence: {conf}** · critic: {critic} · "
                  f"SC: {sc_vote_str(e) or 'not triggered'} · "
                  f"answerSupported: {g.get('answer_supported', '?')} · "
                  f"needsReview: {g.get('needs_review', '?')}", '', '---', '']
        out.append('\n'.join(lines))
    return '\n'.join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('run_dir')
    p.add_argument('--out', default=None,
                   help='output directory (default: the run directory)')
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    entries = load_entries(run_dir)
    if not entries:
        print(f'no entries found under {run_dir}/entries/')
        return 1

    out_dir = Path(args.out) if args.out else run_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    solved = [e for e in entries if not e.get('duplicate_of')]
    qb_rows = [QB_HEADERS] + [question_bank_row(e, i + 1) for i, e in enumerate(solved)]
    write_csv(out_dir / 'question_bank.csv', qb_rows)

    rr_rows = [RR_HEADERS] + [run_report_row(e) for e in entries]
    write_csv(out_dir / 'run_report.csv', rr_rows)

    (out_dir / 'answers.md').write_text(answers_md(entries), encoding='utf-8')

    print(f'wrote {out_dir}/question_bank.csv ({len(solved)} questions), '
          f'run_report.csv ({len(entries)} rows), answers.md')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
