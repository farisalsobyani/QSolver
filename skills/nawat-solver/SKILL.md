---
name: nawat-solver
description: >-
  Solve surgical/medical board-review MCQs against the repo's indexed textbook
  library and produce verified, evidence-backed answer packages — answer cards,
  app-compatible question_bank.csv, run_report.csv, one PDF per question with
  the cited textbook page highlighted in yellow. Use this skill whenever the
  user asks to solve, answer, process, or batch-process exam/board questions
  (from PDFs, images, spreadsheets, or pasted text), to index or add a textbook
  to the library, to verify citations against a textbook, or to export answered
  questions — even if they phrase it casually like "solve these", "run this
  batch", or "add this book". This replaces the old Supabase/OpenAI pipeline;
  never call external LLM APIs or Supabase for question processing.
---

# Nawat Solver

Claude-native re-implementation of the Nawat question pipeline. You (Claude)
perform every model role — extraction, retrieval, reasoning, critic,
self-consistency, writing. The scripts in `scripts/` handle everything
deterministic. The scripts make no network calls and the pipeline uses no
external LLM API and no Supabase — the one thing that does reach the network
is your own web search, in the guideline check at step 5.

All scripts run with `python3` from the repo root. `pymupdf` is required
(`pip install pymupdf` if missing). `pdf-inspector` is optional but
recommended before indexing a book (`pip install pdf-inspector`): indexing
prefers it for extraction (multi-column reading order, markdown heading
structure that feeds the semantic map, per-page OCR routing with
broken-encoding detection) and falls back to PyMuPDF without it.
`rapidfuzz` is also optional but recommended (`pip install rapidfuzz`):
fuzzy quote verification uses it for fast edit distance on real textbook
pages, with a pure-Python fallback when absent.
Verification/highlighting always uses PyMuPDF against the original PDF, so
the extractor choice never affects evidence rendering.

## The corpus ships EMPTY — the operator brings their own books

This is the public build of the skill, and it is the one thing that differs
most from the home repo. `corpus/` here carries only the retrieval aids —
`concept-index.md`, `aliases.md`, `library.json`, and a `map.md` per book. It
carries **no page text, no `fts.sqlite`, no PDFs, and no download links**:
those are six commercial textbooks, and shipping their text is not the
author's to do. Every book therefore starts *unavailable* and becomes
available only when this machine's operator indexes their own copy.

**Check what is actually available before promising a search.** A book is
usable when `corpus/<id>/pages/` and `corpus/<id>/fts.sqlite` both exist;
`library.json` lists what the aids were written for, not what is installed.
`search.py` reports what it can see — against an empty library it returns
`{"error": "no indexed books found"}` and exits 0, so treat that message, not
the exit status, as the signal. Run one search at the start of a run rather
than assuming the library is populated. If NOTHING is indexed, say so
plainly and stop — do not solve from memory and dress it in citations. A
question answered without an opened page is exactly what the verification
gates exist to prevent.

To install a book, the operator supplies the PDF and you index it (see
"Indexing" below). Match the edition in `library.json` — same edition means
the printed folios line up with the shipped `map.md` and `concept-index.md`,
so all the routing works immediately. A different edition still indexes fine,
but its page numbers no longer match the aids: re-derive the map for that
book, and say so rather than citing aid page numbers that point elsewhere.

`fetch_book.py` cannot help here — it reads a `drive_file_id` that this build
deliberately omits. It stays in the tree for operators who maintain their own
library with their own hosting; against this corpus it exits with that
message, which is correct, not a bug to route around.

## Resolving the corpus directory

The skill runs anywhere; only the library is directory-hosted. Resolve in
this order:
1. `./corpus` in the current working directory.
2. `$NAWAT_CORPUS` if set (absolute path to a corpus directory).
3. Otherwise the QSolver checkout this skill was installed from — its
   `corpus/` is the default library. Clone it once into a cache if it isn't
   already local:
   `git clone --depth 1 https://github.com/farisalsobyani/QSolver ~/.nawat-lib`
   (or `git -C ~/.nawat-lib pull` if it exists), then pass
   `--corpus ~/.nawat-lib/corpus` to every script. The repo is public — no
   credentials needed.
Run outputs go to `runs/<date>-<batch>/` under the CURRENT working
directory regardless of where the corpus lives.

Indexed books and the duplicate-scan ledger accumulate in whichever corpus
directory is in use, and a cached clone is *this operator's* library, not a
shared one: `git pull` brings down aid updates, never their books or their
ledger. Tell them that when it matters — for instance before they assume a
`dup: false` means the question is new to anyone but them.

## The house-style rules come from the sawab bank, vendored here

Questions this skill writes are built to import into the **sawab** surgery bank
and to survive the audit its `question-review` skill later runs on them. Four of
that skill's checkers are vendored into `vendor/question-review/` so this build
can run the export checks with no sawab checkout present. They need nothing but
`python3` and their own two JSON files.

| what | vendored file | used for |
|---|---|---|
| choice house style + abbreviation policy | `scripts/check_choice_style.py`, `reference/abbreviations.json` | the export-time style check |
| American spelling, prose cells | `scripts/check_prose_style.py` | the export-time prose check |
| every precise number is sourced | `scripts/check_sourcing.py` | the export-time sourcing check |
| one entity, one spelling | `scripts/check_term_consistency.py`, `reference/term_exceptions.json` | in-batch term drift |

**The sawab repo remains the source of truth; these are copies.** A copy is a
second truth that drifts — every silent divergence in this project's history
(the uploaded copy three weeks behind, two folio writers disagreeing, a third
spelling table) was a rule living in two places with nothing comparing them.
What compares them here is `tools/sync_from_sawab.py` in the QSolver repo:
`--check` fails when a vendored file no longer matches the hash it was copied
from. **Never edit anything under `vendor/`** — a fix belongs in the sawab
original, and reaches here through a re-sync. If a checker's rule looks wrong
mid-run, report it; do not patch it locally.

Two things could NOT be vendored, because they read the sawab app's own source:

- **Lab reference ranges** (`src/lib/labValues.ts`, the NBME sheet). The
  reference-range toggle in `references/answer-format.md` therefore stays
  **OFF** in this build, whatever the user asks. A remembered range is an
  invented number, and a wrong normal range on a lab value silently changes
  which choice is correct. If the operator wants ranges, they must supply the
  sheet; say that rather than filling them in from memory.
- **The two-skill alignment check** (`check_skill_alignment.py`), which compares
  book titles against the app's canonical citation strings and this skill's tag
  lists against the bank's real categories. Without it, `library.json` titles and
  the tag lists in `references/answer-format.md` are unverified against the bank.
  They are correct as shipped; they are not *checked* here. Flag any citation
  string or tag you had to invent, rather than assuming it will match on import.

If a sawab checkout IS available, `$SAWAB_REPO` still enables both — say in the
handover which mode the run used. **Degrade loudly, never silently.**

## The two workflows

**A. Index a textbook** (once per book) — see "Indexing" below.
**B. Solve questions** (the main flow) — see "Solving" below.

---

## Indexing a textbook

1. `python3 .claude/skills/nawat-solver/scripts/index_textbook.py <pdf> \
    --book-id <slug> --title "<Display Title>" --edition "20th Edition" --year 2017`
   The title/edition/year are copied VERBATIM into every citation this skill
   writes, so they must be the form the destination bank expects. For the six
   books in `library.json`, use its strings exactly — they are the sawab bank's
   canonical citation strings, and retyping a near-miss ("Sabiston Textbook of
   Surgery" for the full subtitled form) survives into the bank unnoticed. For a
   book not in `library.json`, there is no canonical string to copy: pick a
   consistent one, and tell the operator it is yours, not the bank's.
   Extracts per-page text to `corpus/<slug>/pages/`, builds the BM25 index,
   derives each page's printed folio into `meta.json:folios`, and registers the
   book in `corpus/library.json`. OCR-less scanned pages are listed in
   `meta.json:ocr_missing` — warn the user if that list is large.
   Check `meta.json:folio_method` afterwards. `embedded` (the PDF's own labels),
   `derived` (read off the printed page) and `reflowed` (a converted ebook with
   no page furniture at all, where the PDF page is the only pagination and is
   therefore what a citation carries) are all citable. Only `index` is not — it
   means furniture was expected but none was found, so citations for that book
   must carry no page rather than a PDF page. Re-run standalone with
   `derive_folios.py` if needed; reflow detection needs `--pdf`.
2. **Write the semantic map** at `corpus/<slug>/map.md`. Use the script's
   `heading_hints` output plus your own reading of the pages to produce
   per-chapter/section summaries with page ranges:
   ```
   ## Ch. 42 — Acute Appendicitis (pp. 1296–1311)
   Epidemiology, fecalith obstruction (1296–98) · presentation & migration
   of pain, Alvarado (1299–1302) · imaging criteria (1303–05) · management:
   appendectomy vs antibiotic-first, appendicolith criterion (1306–09) · …
   ```
   Keep one line per section; the map must be small enough to read whole.
3. **Update the retrieval aids**: add the new book's topics to
   `corpus/concept-index.md` (merge its map.md lines into the existing topic
   rows, priority order), and append any new abbreviations/eponyms it surfaced
   to `corpus/aliases.md`. Page numbers in both aids are **printed folios**,
   the same numbers `search.py` prints as `p.NNNN` — never PDF pages.
4. An indexed book stays LOCAL. `.gitignore` excludes `pages/`, `meta.json`,
   `fts.sqlite` and every PDF, so a book the operator indexes is theirs and is
   never committed back — that is deliberate, not an oversight to fix, and you
   should not add those paths to a commit even if asked to "save the library".
   What IS versioned is the aids: `map.md`, `concept-index.md`, `aliases.md`,
   `library.json`. If indexing a NEW book produced a good map, that map is the
   part worth contributing upstream; offer it, and send nothing else.
   `index_textbook.py --book-id <id> --rebuild-fts --corpus <dir>` rebuilds a
   search index from page text already on disk (seconds, no PDF needed) — the
   command to reach for when `pages/` exists but `fts.sqlite` does not.

## Solving questions

### Intake
- Read the input natively (PDF pages, images, spreadsheet, pasted text).
  Split multi-question inputs; for each question capture the VERBATIM
  original (stem + choices as written).
- Duplicate scan each question BEFORE solving:
  `scripts/dup_scan.py check --ledger corpus/ledger.jsonl --stem "..." --choice "..." ...`
  A `dup: true` result → write a stub entry with `duplicate_of` and skip
  solving. Never spend solving effort on a duplicate.
- Create the run dir: `runs/<YYYY-MM-DD>-<batch-name>/` with `entries/`.
  **Resume rule**: if `entries/qNN.json` already exists for a question, skip
  it — that file is the checkpoint.

### Per-question pipeline
Read `references/reasoning.md` before the first question and follow its
9-step rubric. The flow per question:

1. **Retrieve + reason (fused).** Before the first search, read
   `corpus/aliases.md` (once per run): expand abbreviations/eponyms in the stem
   and translate UK→US spellings — search both surface forms when they differ.
   Route with `corpus/concept-index.md` (topic → every book's pages, priority
   order) and `corpus/<book>/map.md`; use `scripts/search.py "<terms>"` for
   exact-term recall; open `corpus/<book>/pages/pNNNN.txt` (and neighbors) for
   full context — `pNNNN` is the PDF page (`pdf#N` in a search hit), while the
   number you CITE is the printed folio (`p.NNNN` in that same hit, and what the
   concept index and map.md list); they differ in the four print facsimiles.
   Retrieval is agentic: whenever reasoning hinges on a fact you haven't seen,
   go look. When citing, use the concept index to check the second book's
   coverage of the topic — complementary support and contradictions are one
   lookup away, so actually look.
   **Book priority** (`priority` in `corpus/library.json`; lower = preferred;
   search.py already orders hits by it): consult higher-priority books first,
   and when two books support the answer at the SAME decision level, cite the
   higher-priority one. Priority breaks ties — it never suppresses evidence:
   a lower-priority book is still cited when it is the only source, adds
   decision-relevant content, or contradicts the preferred book (surface the
   contradiction honestly). **Complementary support** — each book contributes
   a different part of the answer (eg, one states the criterion, the other
   the threshold or the confirmatory test) — means cite BOTH: one verified
   supporting passage per book (each with its own evidence page), references
   listed in priority order, and the Concept prose synthesizes them into one
   narrative — never two parallel summaries. Redundant support (same fact,
   same decision level) is the only case where priority drops a citation.
   The user can override per run ("use only Schwartz", "prefer Sabiston
   today") — a run instruction beats library.json.
   Work the rubric: intent → disqualifiers → pathology scope with decision
   criteria → canonical choices → per-choice analysis → answer → self-check.
2. **Escalation** (max 1 retry): if `answerSupported` came out false, re-search
   with different terms / adjacent chapters once, then re-reason. Still
   unsupported → keep the best letter, `needs_review: true`.
3. **Critic** — spawn an independent subagent with `references/critic.md`, the
   stem, choices, your letter, a one-line reasoning summary, and your cited
   pages. Do NOT show it your full reasoning. Apply its verdict:
   none/weak → proceed; medium → record (caps confidence) unless one
   re-reason pass resolves it; strong → self-consistency.
4. **Self-consistency** (only on strong dispute) — 3 fresh subagents, each
   solving from scratch with `references/reasoning.md` and corpus access,
   blind to prior work. Majority letter wins; no majority → needs_review.
   SC's verdict is FINAL — never re-run the critic on it.
   **Loop-safety invariants**: ≤2 escalation rounds; critic ≤1× per round;
   no critic↔SC ping-pong; a human reviewer hint outranks everything (skip
   critic AND SC when the user has already told you the answer).
5. **Guideline check (web)** — once the letter is settled, search the web for
   current guidance on the single decision the question turns on, and record
   `gates.web_check`. **The textbook wins the letter**: board exams track the
   books, so a disagreement NEVER changes the answer, the choices, or the
   teaching. It is surfaced — one line stating both positions, with sources —
   caps confidence at MODERATE, and shows in `run_report.csv` so a human can
   decide whether the question is still fair to ask. This mirrors the audit
   skill's web-vs-textbook rule (`question-review/reference/charter.md`), which
   would otherwise be the first place the drift surfaces, long after import.
   Skip it only if the user turns it off for the run; then leave
   `web_check: null`, which reports as `not checked` rather than as agreement.
6. **Write the card** — read `references/answer-format.md`; write vignette,
   solution, tags, references, passages into the entry JSON (schema documented
   in `scripts/_common.py`).
7. **Verify + render evidence** — for every quoted passage:
   ```
   scripts/verify_and_render.py --corpus corpus --book <id> --page <label> \
     --quote "<verbatim quote>" --png runs/<run>/evidence/<qid>-<book>-p<label>.png \
     --annotated-pdf runs/<run>/.tmp/<qid>-ev<n>.pdf
   ```
   Record the verdict (verified/method) in the passage object. A failed quote
   keeps `verified: false` — NEVER trim or swap a quote just to pass; re-check
   the source and fix only if it genuinely says it elsewhere.
8. **Checkpoint** — write `entries/qNN.json` (this is the resume point), then
   append to the ledger:
   `scripts/dup_scan.py add --ledger corpus/ledger.jsonl --id <src-id> --stem "..." ...`

### Batch mode
Fan out one subagent per question (bounded concurrency, ~4–6 at a time), each
running the per-question pipeline above and writing its own entry file. The
orchestrating session only aggregates. Subagent model tiering is a config
knob: critic and SC subagents may run on a cheaper tier (e.g. Sonnet) when the
user wants cost control; main reasoning stays on the session model.

### Export
```
python3 .claude/skills/nawat-solver/scripts/export_csv.py runs/<run> [--out DIR]
python3 .claude/skills/nawat-solver/scripts/export_pdf.py runs/<run> [--combined] [--out DIR]
```
`--out DIR` redirects the exports (CSVs/answers.md, and pdfs/ + batch.pdf) to
a chosen folder; default is the run directory itself.
Produces `question_bank.csv` (exact 19-column match with the app's
Nawat_QuestionBank.csv), `run_report.csv` (telemetry incl. confidence),
`answers.md`, and `pdfs/<qid>.pdf` (card + references + native highlighted
source pages).

**Then run the choice house-style check before handing anything over:**
```
QR="$(dirname "$0")/vendor/question-review/scripts"   # or the skill dir's vendor/
python3 "$QR/check_choice_style.py" --all runs/<run>/question_bank.csv
```
It reads this exact CSV shape unmodified. It judges the whole choice set against
the stem — length parity, parallel form, sentence case, American spelling, stem
echo, abbreviation policy — and escalates an outlier that turns out to be the
**key** to `GIVEAWAY`, the case where format alone reveals the answer. Fix what
it flags and re-export; a `GIVEAWAY` is not a polish note, it is a question a
student can get right without knowing the medicine. Report the remaining count
to the user rather than shipping it silently. See `references/reasoning.md`
step 4 → *House style* for the rules and the allowed fix directions.

**Two more checkers from the same skill read this CSV unmodified:**
```
python3 "$QR/check_sourcing.py"          --all runs/<run>/question_bank.csv
python3 "$QR/check_term_consistency.py"  --all runs/<run>/question_bank.csv
python3 "$QR/check_prose_style.py"       --all runs/<run>/question_bank.csv
```
- **check_sourcing** sorts every unit-bearing figure in Concept / Why / Reasons
  Wrong / Take-Home into *sourced* (in this question's own passages), *echoed*
  (in the stem or a choice) or **unsourced**. (Its `--verify` flag is NOT
  available in this build — it shells out to the audit skill's own textbook
  index, which is not vendored. The tiering above works without it; only the
  automatic re-search of an unsourced figure is missing, so check those by
  hand against the corpus.) Fix the unsourced ones — cite them
  or make them qualitative (`references/answer-format.md` → *Every precise number
  in an explanation must be sourced*).
- **check_prose_style** applies the bank's American-English rule to the PROSE
  cells — stem, concept, why, reasons wrong, take-home, cited passages — which
  `check_choice_style` never looks at. This is the one house-style rule that is
  not a property of the choice set, and the one most easily missed while writing:
  a paraphrase reading "return to theatre" reaches a student exactly as a choice
  does. `--edits OUT.json` writes the corrections if you want them applied
  mechanically rather than by hand.
- **check_term_consistency** groups one entity written several ways
  (`Angioembolization` / `Angioembolisation`) and proposes a canonical form. On a
  run's CSV it catches drift **inside the batch**, which is what you can fix
  here. Drift against the rest of the bank needs a fresh bank export and is the
  audit skill's `sweep` job — don't try to reproduce it from a batch.

**Deliverables** (after the checks above pass, not before): send the user
exactly one `pdfs/<qid>.pdf` per question plus the combined `question_bank.csv`
for the batch — nothing else by default. `run_report.csv` and `answers.md` stay
in the run dir (the run report is how a human knows which answers to
double-check, so summarize its needs_review / LOW-confidence counts — and any
`web_check: disagrees` rows — in your closing message, and offer it on request).
Skip `--combined` batch.pdf unless asked. Clean up `.tmp/` afterward.

## Confidence (derived, never self-reported)
Computed by `_common.derive_confidence` from the gates — do not overwrite it
with your own feeling:
- **LOW** — answer unsupported, or SC had no majority, or a shown citation
  failed verification.
- **MODERATE** — unresolved medium critic dispute, split SC vote, fuzzy-only
  citation match, an unrefuted distractor, or current guidance disagreeing with
  the cited textbook.
- **HIGH** — everything held.

## Honesty rules (load-bearing — carried from the original pipeline)
- `answerSupported` is a review signal, never a refusal switch: always emit
  your best letter.
- Report gate outcomes exactly as they happened; the run report exists so a
  human knows which answers to double-check.
- Citations only to pages you actually opened. A citation that fails
  mechanical verification stays visibly failed (✗) in every output.
- Failed verification never silently produces evidence: no highlight, no
  evidence page, `.UNVERIFIED.png` naming for the fallback render.

## Script reference
| Script | Purpose |
|---|---|
| `index_textbook.py` | PDF → pages/, meta.json, fts.sqlite, library.json |
| `search.py` | BM25 page search (`--json` for machine output); reports the printed folio |
| `derive_folios.py` | recover each page's PRINTED folio → `meta.json:folios` |
| `verify_and_render.py` | quote → verify + yellow highlight + PNG + annotated single-page PDF |
| `dup_scan.py` | `check` incoming question vs ledger; `add` answered question |
| `export_csv.py` | entries → question_bank.csv + run_report.csv + answers.md |
| `export_pdf.py` | entries → pdfs/<qid>.pdf (+ batch.pdf with --combined) |

Entry JSON schema: documented at the top of `scripts/_common.py`.
