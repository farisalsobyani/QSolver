# --- VENDORED COPY - DO NOT EDIT ------------------------------------
# source : .claude/skills/question-review/scripts/check_prose_style.py   (sawab repo - the source of truth)
# sha256 : 3c874838d6a93d0e57a265666a2735b88004a18892e938ee4377551e054f50d8
# synced : 2026-08-28 by tools/sync_from_sawab.py
# Edit the sawab original, not this file. `sync_from_sawab.py --check`
# fails when the two have drifted apart.
# --------------------------------------------------------------------

#!/usr/bin/env python3
"""American spelling across the PROSE cells, not just the choices.

check_choice_style.py enforces the bank's American-English rule on the choice
set. It stops there, because its other five rules are properties of a choice
SET. But spelling is not a choice property — it is a bank-wide convention, and
the prose cells are just as student-facing as the options. A paraphrase reading
"return to theatre" ships to every student who opens that explanation, and until
now nothing looked at it.

Cells checked (the ones the site renders as prose):
  Reformatted Question · Concept · Why · Reasons Wrong Answers Are Wrong ·
  Take-Home Message · Cited Passages

References is deliberately NOT checked: it is a formulaic citation string whose
only free text is the book title, so a "British spelling" there is a publisher's
name, not the bank's prose.

SPELLING ONLY, and that is a decision rather than a gap. The abbreviation ruling
in reference/abbreviations.json governs CHOICES ONLY: prose may abbreviate freely
after first mention, as UWorld explanations do, and expanding every occurrence
would bloat the teaching. Length parity, parallel form, sentence case and stem
echo are all properties of a choice SET and have no prose analogue. Spelling is
the only rule that transfers, which is why it is the only one here.

Usage:
  check_prose_style.py --all EXPORT.csv          # sweep the bank
  check_prose_style.py --csv V2.csv              # check a built v2 CSV
  check_prose_style.py RESULTS.json              # check the auditor's `after` cells
  check_prose_style.py --all EXPORT.csv --edits fixes.json

`--edits` writes the fixes in apply_abbrev_decisions.py's `--extra-edits` shape
({"<qid>|<field>": {"from": …, "to": …}}), so a spelling sweep applies through
the same applier and the same 15-column v2 CSV as every other sweep — no new
apply path. The substring form is used rather than whole-cell, so the applier
fails loudly if the cell moved under it.

Matched capitalisation is preserved ("Haemostasis" -> "Hemostasis"), which is
what makes the emitted edits safe to apply blind: a cell holding both
"Oesophagectomy" and "oesophageal" yields two edits, not one that would
lowercase a sentence opening.

Exits non-zero if any cell is flagged. Heuristic by design — a hit means "look
at this one".
"""
import argparse
import csv
import json
import pathlib
import sys

from qr_common import british_hits, correct_text, csv_cell, norm

csv.field_size_limit(10 ** 9)

# CSV column -> the findings-schema field name used in RESULTS.json / decisions.
PROSE_FIELDS = {
    "Reformatted Question": "stem",
    "Concept": "concept",
    "Why": "why",
    "Reasons Wrong Answers Are Wrong": "reasons_wrong",
    "Take-Home Message": "take_home",
    "Cited Passages": "cited_passages",
}
FIELD_TO_COL = {v: k for k, v in PROSE_FIELDS.items()}


def scan_cell(text):
    """[(found, american)] for one cell, deduped, capitalisation preserved."""
    return british_hits(text or "")


def scan_rows(rows, cells=None):
    """[(qid, col, [(found, fixed), …])] over every prose cell of every row.

    `cells`, when given, is filled with {(qid, col): text} for the flagged cells
    so --edits can rebuild a whole corrected cell without re-reading the CSV.
    """
    out = []
    for r in rows:
        qid = norm(r.get("ID"))
        for col in PROSE_FIELDS:
            text = csv_cell(r, col)
            hits = scan_cell(text)
            if hits:
                out.append((qid, col, hits))
                if cells is not None:
                    cells[(qid, col)] = text
    return out


def from_results(path, cells=None):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out = []
    for q in data.get("results", []):
        for f in q.get("findings", []):
            if (f.get("verify") or {}).get("verdict") == "refuted":
                continue
            col = FIELD_TO_COL.get(f.get("field"))
            after = norm(f.get("after"))
            if not col or not after:
                continue
            hits = scan_cell(after)
            if hits:
                qid = q.get("question_id", "")[:8]
                out.append((qid, col, hits))
                if cells is not None:
                    cells[(qid, col)] = after
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?", help="RESULTS.json from an audit run")
    ap.add_argument("--all", dest="export", help="a full admin EXPORT.csv")
    ap.add_argument("--csv", help="a built v2 CSV")
    ap.add_argument("--edits", help="write --extra-edits-shaped fixes to this path")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    src = args.export or args.csv
    if not src and not args.results:
        ap.error("pass --all EXPORT.csv, --csv V2.csv, or RESULTS.json")

    cells = {}
    if src:
        with open(src, newline="", encoding="utf-8-sig") as fh:
            findings = scan_rows(list(csv.DictReader(fh)), cells)
        checked = f"{src}"
    else:
        findings = from_results(args.results, cells)
        checked = f"{args.results}"

    by_field, by_word = {}, {}
    for _, col, hits in findings:
        by_field[col] = by_field.get(col, 0) + 1
        for found, _fixed in hits:
            by_word[found.lower()] = by_word.get(found.lower(), 0) + 1

    print(json.dumps({
        "source": checked,
        "cells_flagged": len(findings),
        "questions_flagged": len({q for q, _, _ in findings}),
        "by_field": dict(sorted(by_field.items(), key=lambda kv: -kv[1])),
        "by_spelling": dict(sorted(by_word.items(), key=lambda kv: -kv[1])),
    }, indent=1, ensure_ascii=False))

    for qid, col, hits in findings[: args.limit]:
        for found, fixed in hits:
            print(f"  {qid}  {col}: British spelling {found!r} — use {fixed!r}")
    if len(findings) > args.limit:
        print(f"  … {len(findings) - args.limit} more flagged cell(s)")

    if args.edits:
        # A substring edit is emitted only when it is PROVABLY equivalent to the
        # word-safe correction. It is not always: a cell holding both "oedema"
        # and "angioedema" flags the first correctly, but the applier's
        # str.replace would also turn the second into "angiedema". Where the two
        # disagree — or where one cell carries several spellings — the whole
        # corrected cell is emitted instead, which the applier also accepts.
        edits, whole = {}, 0
        for qid, col, hits in findings:
            cell = cells.get((qid, col), "")
            fixed_cell = correct_text(cell)
            naive = cell
            for found, fixed in hits:
                naive = naive.replace(found, fixed)
            key = f"{qid}|{PROSE_FIELDS[col]}"
            if len(hits) == 1 and naive == fixed_cell:
                edits[key] = {"from": hits[0][0], "to": hits[0][1]}
            else:
                edits[key] = fixed_cell
                whole += 1
        pathlib.Path(args.edits).write_text(json.dumps(edits, indent=1, ensure_ascii=False),
                                            encoding="utf-8")
        print(f"\nwrote {len(edits)} edit(s) -> {args.edits} "
              f"({len(edits) - whole} substring, {whole} whole-cell)")

    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
