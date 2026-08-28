# QSolver

A Claude Code skill that answers surgical/medical board-review MCQs against
textbooks **you** supply, and produces an evidence package for each one: an
answer card, an importable `question_bank.csv`, a telemetry report, and a PDF
per question with the cited textbook page highlighted in yellow.

The distinguishing property is that it will not quietly bluff. Every citation
is mechanically verified against the page it claims, a quote that fails
verification stays visibly failed, and each answer's confidence is *computed*
from what the pipeline actually managed to prove — not from how sure the model
felt.

## What's in the box

```
skills/nawat-solver/     the skill: SKILL.md, 3 reference prompts, 9 scripts
  vendor/question-review/  4 export-time style checkers (see "Vendored rules")
corpus/                  retrieval aids only — no textbook content
tools/sync_from_sawab.py drift check for the vendored checkers
```

**`corpus/` ships without any textbook text.** It contains the routing layer —
a `map.md` per book, a cross-book `concept-index.md`, an `aliases.md` of
abbreviations and eponyms, and `library.json` listing the six editions the aids
were written against:

| book | edition | priority |
|---|---|---|
| Schwartz's Principles of Surgery | 11th, 2019 | 1 |
| Sabiston Textbook of Surgery | 20th, 2017 | 2 |
| Current Surgical Therapy | 14th, 2023 | 3 |
| Fischer's Mastery of Surgery | 7th, 2019 | 4 |
| ASCRS Textbook of Colon and Rectal Surgery | 4th, 2022 | 5 |
| Greenfield's Surgery | 7th, 2023 | 6 |

Priority orders search results and breaks citation ties; it never suppresses a
book that is the only source or that contradicts a preferred one.

There is no page text, no search index, and no PDF here, and there won't be:
those are copyrighted works, and distributing them isn't mine to do. You bring
your own legally obtained copies.

## Setup

Requires Python 3.9+ and PyMuPDF.

```bash
git clone https://github.com/farisalsobyani/QSolver ~/.nawat-lib
pip install pymupdf rapidfuzz          # rapidfuzz optional, recommended
pip install pdf-inspector              # optional, better extraction quality
~/.nawat-lib/tools/install_skill.sh    # copies the skill into ~/.claude/skills/
```

Then index a book you own:

```bash
python3 ~/.claude/skills/nawat-solver/scripts/index_textbook.py ~/books/sabiston.pdf \
  --book-id sabiston-20e \
  --title "Sabiston Textbook of Surgery. The Biological Basis of Modern Surgical Practice" \
  --edition "20th Edition" --year 2017 \
  --corpus ~/.nawat-lib/corpus
```

Use the `book-id`, title, edition and year exactly as `corpus/library.json`
records them. **Match the edition** and the printed page numbers in the shipped
maps line up with your copy, so the routing works from the first question. A
different edition indexes fine but its folios won't match the aids — the skill
will tell you so rather than citing page numbers that point somewhere else.

You do not need all six books. One is enough to start; the skill checks what is
actually installed before it searches, and says so plainly when a topic's
preferred book is missing.

Ask Claude Code to "solve these questions" with a PDF, image, spreadsheet, or
pasted text, and the skill takes over from there.

## How an answer is produced

Per question: duplicate scan → retrieve and reason against the corpus (a 9-step
rubric) → an independent **critic** subagent that only tries to refute the
chosen letter → on a strong refutation, **three fresh solvers** vote → a web
check against current guidance → write the card → verify every quote against
the real page → checkpoint.

The textbook decides the letter, always; board exams track the books. When
current guidance disagrees, that is surfaced in one line with sources and caps
the question's confidence — it never silently rewrites the answer.

Confidence is derived, not self-reported: **LOW** if the answer is unsupported,
the three solvers had no majority, or a shown citation failed verification;
**MODERATE** for an unresolved dispute, a fuzzy-only quote match, or guidance
that has moved on; **HIGH** only when everything held.

## Vendored rules

Four checkers under `skills/nawat-solver/vendor/question-review/` enforce the
house style at export — choice length parity, parallel form, sentence case,
American spelling, abbreviation policy, sourcing of every precise number, and
one-entity-one-spelling. They are **copies**; the originals live in a private
repo that is their source of truth.

A copy is a second truth that drifts, so nothing here relies on remembering to
re-copy them: `tools/sync_from_sawab.py --check` hashes each vendored file
against what it was copied from and exits non-zero when they diverge — in
either direction, upstream change or local edit. Don't edit anything under
`vendor/`; fix the original and re-sync.

Two rules could not be vendored because they read a private application's
source. Their absence is stated in `SKILL.md` and the skill degrades loudly
rather than guessing: **lab reference ranges are unavailable**, so that toggle
stays off (a remembered normal range is an invented number, and it can silently
change which choice is correct), and the two-skill alignment check does not run
here.

## Contributing

The useful thing to contribute is a **map** — if you index a book and write a
good `corpus/<book>/map.md`, or improve one, send it. Everything derived from a
PDF is gitignored, so an accidental `git add -A` won't commit a textbook.

Note that indexing rewrites `corpus/library.json` with local page counts, which
will show as a local modification; `git checkout corpus/library.json` before
pulling if it gets in the way.

## License

The skill, scripts, maps and indexes here are the author's work. The textbooks
they point into are not, and are not distributed with them — the page numbers
in this repository are references, in the sense a bibliography is.
