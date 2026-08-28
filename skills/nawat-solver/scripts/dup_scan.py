#!/usr/bin/env python3
"""Duplicate detection for incoming MCQs against the answer ledger.

Faithful port of src/lib/question-similarity.ts: two Sørensen–Dice signals
(stem token overlap, normalized choice-set overlap) combined under the same
strictness presets. A question that matches a ledger entry is skipped by the
pipeline and linked to the earlier answer in run_report.csv.

Ledger format (corpus/ledger.jsonl, one JSON object per line):
  {"id": "batch-03#11", "stem": "...", "choices": ["...", ...],
   "answer": "B", "run": "runs/2026-08-01-batch-03", "ts": "..."}

Usage:
  # Check one question (stem on stdin or --stem, choices via --choice, repeatable)
  dup_scan.py check --ledger corpus/ledger.jsonl --stem "..." \
      --choice "colonoscopy" --choice "defecography" [--strictness balanced]
  # Append an answered question to the ledger
  dup_scan.py add --ledger corpus/ledger.jsonl --id batch-07#3 --stem "..." \
      --choice "..." --answer B --run runs/2026-08-12-batch-07

check prints a JSON verdict:
  {"dup": true, "match": {...ledger entry...}, "stemScore": 0.91,
   "choiceScore": 1.0, "score": 0.955}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Generic question scaffolding with no discriminating signal — same list as
# question-similarity.ts so the two implementations score identically.
STOP = {
    'the', 'a', 'an', 'of', 'to', 'in', 'is', 'are', 'was', 'were', 'be', 'been',
    'and', 'or', 'with', 'for', 'on', 'at', 'by', 'from', 'as', 'that', 'this',
    'which', 'what', 'who', 'whom', 'his', 'her', 'their', 'has', 'had', 'have',
    'patient', 'patients', 'year', 'years', 'old', 'man', 'woman', 'male', 'female',
    'boy', 'girl', 'presents', 'presented', 'presenting', 'history', 'following',
    'most', 'likely', 'best', 'next', 'step', 'management', 'diagnosis', 'cause',
}

PRESETS = {
    'conservative': {'stemOnly': 0.90, 'choiceStrong': 0.85, 'choiceStrongStem': 0.55, 'combined': 0.82},
    'balanced':     {'stemOnly': 0.82, 'choiceStrong': 0.70, 'choiceStrongStem': 0.40, 'combined': 0.72},
    'aggressive':   {'stemOnly': 0.72, 'choiceStrong': 0.60, 'choiceStrongStem': 0.25, 'combined': 0.60},
}


def normalize(s: str) -> str:
    s = (s or '').lower()
    s = re.sub(r'<!--[\s\S]*?-->', ' ', s)     # html comments / meta markers
    s = re.sub(r'\[(?:tid|ref):[^\]]+\]', ' ', s)  # citation ids (tid legacy, ref current)
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def token_set(s: str) -> set[str]:
    return {w for w in normalize(s).split(' ') if len(w) > 1 and w not in STOP}


def dice(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return (2 * inter) / (len(a) + len(b))


def choice_set(choices: list[str]) -> set[str]:
    out = set()
    for c in choices:
        n = normalize(c)
        if len(n) > 2:
            out.add(n)
    return out


def is_duplicate(a_stem: str, a_choices: list[str], b_stem: str, b_choices: list[str],
                 strictness: str = 'balanced') -> dict:
    t = PRESETS[strictness]
    stem_score = dice(token_set(a_stem), token_set(b_stem))
    ca, cb = choice_set(a_choices), choice_set(b_choices)
    choice_score = dice(ca, cb) if ca and cb else 0.0
    have_choices = bool(ca) and bool(cb)
    score = 0.5 * stem_score + 0.5 * choice_score if have_choices else stem_score

    dup = False
    if stem_score >= t['stemOnly']:
        dup = True
    elif have_choices and choice_score >= t['choiceStrong'] and stem_score >= t['choiceStrongStem']:
        dup = True
    elif score >= t['combined']:
        dup = True

    return {'dup': dup, 'stemScore': round(stem_score, 4),
            'choiceScore': round(choice_score, 4), 'score': round(score, 4)}


def load_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def cmd_check(args) -> int:
    stem = args.stem if args.stem is not None else sys.stdin.read()
    choices = args.choice or []
    best = None
    for entry in load_ledger(Path(args.ledger)):
        verdict = is_duplicate(stem, choices, entry.get('stem', ''),
                               entry.get('choices', []), args.strictness)
        if best is None or verdict['score'] > best[0]['score']:
            best = (verdict, entry)
        if verdict['dup']:
            print(json.dumps({**verdict, 'match': entry}, ensure_ascii=False))
            return 0
    out = {'dup': False}
    if best:
        out.update(best[0])
        out['closest'] = best[1].get('id')
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_add(args) -> int:
    entry = {'id': args.id, 'stem': args.stem, 'choices': args.choice or [],
             'answer': args.answer, 'run': args.run}
    path = Path(args.ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(json.dumps({'added': args.id}))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    c = sub.add_parser('check', help='check one question against the ledger')
    c.add_argument('--ledger', required=True)
    c.add_argument('--stem', default=None, help='question stem (reads stdin if omitted)')
    c.add_argument('--choice', action='append', help='answer choice text (repeat per choice)')
    c.add_argument('--strictness', choices=list(PRESETS), default='balanced')
    c.set_defaults(fn=cmd_check)

    a = sub.add_parser('add', help='append an answered question to the ledger')
    a.add_argument('--ledger', required=True)
    a.add_argument('--id', required=True)
    a.add_argument('--stem', required=True)
    a.add_argument('--choice', action='append')
    a.add_argument('--answer', default='')
    a.add_argument('--run', default='')
    a.set_defaults(fn=cmd_add)

    args = p.parse_args()
    return args.fn(args)


if __name__ == '__main__':
    raise SystemExit(main())
