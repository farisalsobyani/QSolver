# Stage 2 — Answer card format

Adapted from Nawat's `STAGE2_SYSTEM_PROMPT`. The card is the user-facing
product: a premium board-review learning card (ABSITE / Saudi Board / FRCS /
SCORE / SESAP level). Stage 2 writes prose into the entry JSON fields
(`reformatted`, `solution`, `tags`); export scripts render it to answers.md,
CSVs, and the per-question PDF.

## Voice — consultant at the bedside, never an answer key

- Avoid: "The answer is…", "The correct answer is…", "This option is wrong
  because…", "The question asks…".
- Prefer: "The most important finding is…", "The deciding factor is…",
  "Management changes once…", "In this setting…", "This presentation
  supports…".
- Prose NEVER describes sources: no "the passage states", "according to the
  textbook", "the reference shows". All sourcing lives in the References /
  Supporting Passage sections; the teaching reads as direct clinical
  knowledge.
- Every explanation is fully standalone — never reference other questions.
- Be extremely concise in the Solution: no filler, no padding.

## Reformatted vignette — board style, ~3–5 sentences

Written like an experienced surgical educator: natural sequencing of history →
examination → investigations → decision point, ending with a direct clinical
question ("What is the most appropriate next step?"). Not a grammar pass —
if it reads like converted lecture notes, rewrite it.

**Preservation rules (never optional):**
1. **Vitals, labs, imaging** — include EVERY value from the original, in clean
   clinical notation ("BP 118/76 mmHg, HR 102 bpm, Temp 38.4°C"; "WBC
   14,200/μL"; "CT abdomen: grade III splenic laceration with active
   extravasation"). Formatting may change; values never.
2. **Demographics** — preserved exactly (age, sex, parity, BMI, occupation,
   relevant social/family history).
3. **Question purpose is sacred** — never change the action verb, the decision
   at stake, the setting/time-frame/qualifiers ("hemodynamically stable",
   "after failed conservative management"), or the specific pathology.
   "Confirmatory test" stays confirmatory; "next best step" stays next best
   step. This includes negative lead-ins: an "all of the following EXCEPT" /
   "which is NOT" question is kept negative — never converted to a positive
   form (that would silently change which choice is correct). Render the
   negation in capitals ("EXCEPT", "NOT") so it cannot be misread, and set
   `"negative_leadin": true` on the entry so runs can count them.
4. **Zero answer hints** — completely neutral wording, ordering, and emphasis.
   Write as if you don't know the correct answer.
5. **Self-contained** — the vignette is an original case, not commentary on a
   source. Never "the question", "as provided", "no other values are given".
6. **Qualitative findings get representative values** — "febrile" → "Temp
   38.7°C"; "tachycardic" → "HR 118 bpm"; "leukocytosis" → "WBC 16,400/μL".
   A finding missing from the source may be added ONLY if decision-relevant
   and answer-neutral; otherwise omit silently. NEVER write meta-commentary
   about absent findings ("otherwise unremarkable labs", "no other vitals
   provided").
   The test for any addition: could it favor, disfavor, suggest, exclude, or
   change difficulty for any choice? If yes, omit. When in doubt, omit.
7. **Reference ranges (per-run toggle, OFF by default)** — when the user asks
   for board-style reference ranges, append the normal range in parentheses to
   each lab value: "WBC 16,400/μL (4,500–11,000/mm³)". Ranges are
   diagnostically neutral by definition (they state what normal is, not what
   this patient has) and are applied uniformly to every lab in the vignette —
   never selectively, which would itself hint. Do not add ranges unless the run
   was asked to include them.

   **A range is COPIED, never recalled.** The student can open the in-quiz Lab
   Values panel while answering; a stem that disagrees with that panel is worse
   than a stem with no ranges at all. So the only permitted source is the app's
   own sheet:
   ```
   python3 "$SAWAB_REPO/.claude/skills/question-review/scripts/lab_ranges.py" "calcium"
   ```
   Copy the `conv` string **verbatim**, including its en dashes, and write the
   sheet's `label` verbatim as the analyte name (`WBC` → `Leukocyte count
   (WBC)`). Only a `match: "exact"` row may be copied — `lactate` partial-matches
   *Lactate dehydrogenase*, a different analyte whose range would be flatly
   wrong. For a sex- or state-qualified row, take the one matching this patient
   and carry the qualifier: `41%–53% (male)`.

   An analyte the sheet does not carry (lactate, CRP, INR, CA 19-9, CEA,
   ammonia, drain amylase…) simply gets **no range**. Writing one from memory is
   the invented number the audit charter forbids, and it is the specific way
   this toggle used to go wrong. Vital signs get no ranges either — the sheet
   has none. **No `$SAWAB_REPO`, no ranges**: leave the toggle off and say why.

### Values stay IN the prose — for now, and deliberately

Vitals, labs and imaging findings are written **inline, in the sentences**, in
clean clinical notation ("BP 118/76 mmHg, HR 102 bpm, Temp 38.4 °C"; "CT
abdomen: grade III splenic laceration with active extravasation"). Do not pull
them into tables or labelled blocks.

This is worth stating explicitly because the audit skill's field spec describes
the *opposite* layout — a UWorld-style stem with `**Vital Signs**` /
`**Laboratory Results**` tables after the lead-in and `(see … below)` pointers
from the prose. That layout is the agreed destination, but it is **staged, not
live**: `QuestionCard.tsx` renders the stem as plain text in a
`whitespace-pre-line` div, so a GFM table would show students literal pipe
characters. `react-markdown` is in the app's dependencies but is wired only into
the CMS `Page.tsx`, and `remark-gfm` — which is what actually renders tables —
is not installed at all.

Three things must ship before either skill switches: `remark-gfm` added, a
markdown renderer wired into `QuestionCard`'s stem, and in-stem highlighting
kept working (highlights are anchored by character offsets into the raw stem —
see `highlightText.tsx` — so the renderer has to preserve offsets per block).
Until then, inline is correct here and the audit skill holds its
`stem-restructure` edits. When it ships, both flip together.

## Sections of the card (entry JSON → rendered output)

- **Concept (UWorld-style teaching block)** — `solution.concept` is written
  the way UWorld writes an explanation body: 1–2 short paragraphs of flowing
  clinical prose that stand alone as a mini-review. Follow UWorld's arc, in
  order:
  (a) **definition/classification** — name the entity in bold with its causes
      or classes ("**Obstructed defecation syndrome** is … caused by either
      **structural** abnormalities (**rectocele**, **internal rectal
      intussusception**) or **functional** disorders (**dyssynergic
      defecation**).");
  (b) **typical presentation, linked to mechanism** — "Patients typically
      report …" and why those findings point where they point;
  (c) **the evaluation/management sequence AS PROSE** — "Evaluation excludes
      mucosal disease when alarm features (eg, bleeding, weight loss) are
      present; **defecography**, which images evacuation in real time, is the
      **confirmatory study** for structural causes, whereas **anorectal
      manometry** is reserved for suspected dyssynergia." NEVER write arrow
      chains (x → y) inside the prose — arrows belong to the Approach box,
      exactly as UWorld keeps algorithms in table figures, never in
      paragraphs;
  (d) when the verification gates identified a trap, the block CLOSES with
      the unlabeled trap sentence (rules below).
  UWorld idiom throughout: present tense, impersonal ("Patients typically
  report…"), UWorld-style parentheticals ("(eg, vaginal splinting)",
  "(ie, …)" — no periods inside eg/ie), and disciplined bolding — first
  mentions of the entity, the key discriminators, and test/treatment names
  only, not every noun. A reader skimming just the bold words should retain
  the testable core. No headers, no bullets — sentences only. Exports handle
  bold per format (rendered in PDF/answers.md, stripped for the CSV).
  Relatedly, `take_home` is phrased like UWorld's "Educational objective":
  one or two sentences stating what the learner should now recognize or do.

- **Original** — verbatim, always present, never skipped.
- **Reformatted** — the vignette, then the four canonical choices A–D
  (canonical forms from Stage 1, reused identically everywhere).
- **Solution** — in this order:
  1. `✅ Answer: <letter> — <canonical choice text>`
  2. **Concept** — the UWorld-style teaching block described above: the
     general principle before the case-specific reasoning, exactly as UWorld
     opens its explanations.
  3. **Why** — the deciding features and reasoning for THIS case.
  4. **Other options** — each wrong letter gets TWO parts: why it's wrong
     HERE, then *"Would be correct if:"* — the specific scenario in which that
     option would be the right answer ("Anorectal manometry would be correct
     if the stem described paradoxical puborectalis contraction on attempted
     defecation"). This turns every distractor into a second teaching point.
     If an option is simply never correct for this presentation, say what it
     is actually used for instead of inventing a scenario.
  5. **The trap sentence** — not a separate section: it is the CLOSING
     SENTENCE of the Concept block, and it exists ONLY when the verification
     gates identified a trap (the critic raised a medium/strong dispute for a
     specific letter, or the self-consistency vote split). That letter is the
     mechanically-identified tempting answer. Write ONE complete sentence
     with no label or title — the sentence itself names the tempting option,
     why it tempts, and the stem detail that rules it out: "Manometry is the
     tempting alternative here because it is the classic anorectal function
     test, but it assesses sphincter coordination and cannot demonstrate the
     structural abnormality this presentation suggests." Record the letter
     and sentence in `solution.common_trap` for telemetry. Never fabricate a
     trap when the gates were clean — the absence of a trap sentence is
     itself a signal the question was unambiguous.
  6. **📌 Take-home** — one high-yield pearl, phrased like UWorld's
     "Educational objective".

  Note on the management paradigm: it appears ONLY woven as prose inside the
  Concept block (arc step (c)) — there is NO separately rendered Approach
  section or box anywhere. Still populate `solution.approach` with the arrow
  rules as an internal structured record (useful for analysis and future
  flashcard export); no renderer displays it.
- **Tags** — Subjects and Systems from the app's allowed lists (see below).
- **References / Supporting Passage / Paraphrased Passage** — see citation
  format.

## American spelling in the prose too — and abbreviations are NOT the same

The bank is written in American English, and that rule does not stop at the
choices. It binds every prose cell you write here: the vignette, `concept`,
`why`, each `why_wrong` / `would_be_right`, `take_home`, and every `paraphrase`.
A paraphrase reading "emergent return to **theatre**" reaches a student exactly
as a choice does. Write `esophagus`, `hemorrhage`, `tumor`, `edema`, `ischemia`,
`maneuver`, `anesthetic`, `operating room`, `randomized`, `characterization`.

Three things that are already correct and must NOT be "fixed": **embolism**
(only *embolise/embolisation* are British), **gastroesophageal** and
**angioedema** (the `o` belongs to the prefix, not to an -oe- digraph), and
***Haemophilus*** (a genus name).

**Abbreviations are the opposite case**: the locked ruling in
`abbreviations.json` governs **choices only**. In prose you may abbreviate
freely after first mention, the way UWorld explanations do — write "computed
tomography (CT)" once and "CT" thereafter. Expanding every occurrence would
bloat the teaching without helping anyone. A choice is different because it is
read in isolation, against its siblings, under time pressure.

`check_prose_style.py` enforces the spelling half at export (SKILL.md → Export);
nothing enforces abbreviations in prose, by design.

## Every precise number in an explanation must be sourced

A figure with a unit — a dose, a cutoff, a survival %, a size in cm, an interval
— is the part of an explanation a student memorises, so it is the part that must
not be free-floating. Before finalising `concept`, `why`, `other_options` and
`take_home`, put every such figure in one of three tiers:

- **sourced** — it appears in one of this question's own supporting passages.
  Done; that is what the passage is for.
- **echoed** — it appears in the stem or in a choice. The explanation is
  restating the vignette, which is fine.
- **unsourced** — it appears in none of them. Either retrieve support and add
  the passage that carries it, or **replace the figure with a qualitative
  descriptor** ("a markedly elevated lipase", "within the first 24 hours"). A
  remembered threshold that no cited page states is exactly the number the audit
  charter forbids, and it is the hardest kind of error to catch later, because a
  wrong figure reads as authoritative.

`check_sourcing.py --all <run>/question_bank.csv --verify` sorts them for you
(see SKILL.md → Export). Its `--verify` pass retrieves the sentence *around* a
figure rather than the bare number, and reports *figure present in source* (real
support) versus *topic found, figure unconfirmed* — the second is a lead to read,
never a pass.

## Citation format — LOCKED

One style everywhere (reference lists, inline parentheticals, CSVs, PDFs):

- Reference line: `Schwartz's Principles of Surgery, 11th Edition, 2019, Page 1335.`
- Multiple pages: `…, Pages 1335, 1336.`
- Inline (after a quote or paraphrase):
  `"Perforated and gangrenous appendicitis are complicated forms of
  appendicitis, and severe infectious sequelae can include pylephlebitis,
  which is inflammation of the portal vein." (Schwartz's Principles of
  Surgery, 11th Edition, 2019, Page 1335.)`
- Page numbers are the **printed folio** — the number on the page itself, which
  is what a reader holding the book will turn to. It is NOT the PDF page: in the
  four print facsimiles (Schwartz, Sabiston, CST, ASCRS) the two differ, by 20 to
  45 pages, and the gap drifts within a book (Sabiston runs −23 early and −26
  later, across 12 segments), so there is no offset you can apply in your head.
  In Fischer they coincide, and in Greenfield the PDF page *is* the folio — but
  read the number off the hit rather than relying on that.
  **Take the folio from `search.py`'s `p.NNNN`** (or `meta.json:folios[pdf-1]`);
  `pdf#N` in the same line is the file you open, never the number you cite.
  `verify_and_render.py --page` expects the folio and resolves it for you — if
  it answers `page … is not a known printed page`, you have handed it a PDF
  page.
  **Greenfield is the exception, and not the one you'd guess**: it is a
  reflowed ebook — no running heads, no printed folios anywhere, its page breaks
  are conversion artifacts — so its PDF page is the only pagination it has and
  IS the right thing to cite. `folio` equals `page` there, `search.py` shows a
  normal `p.NNNN`, and the bank already cites it this way. Nothing special to do.
  A `p.?` would mean a book whose folios were never derived; cite that one
  without a page rather than substituting the PDF page.
- No publisher, no "11th ed." abbreviations, no bold, no machine tags in any
  user-facing output. Book identity travels as `book_id` in the entry JSON
  only.
- Title/edition/year come from the corpus `meta.json` for corpus books. A
  general-knowledge citation (book not in the corpus) has no `book_id`, is
  never verified, and gets no evidence page.

## Supporting Passage rules

- Quote VERBATIM the 1–3 sentences that directly state the answer or key
  fact — never chapter intros, overviews, or "this chapter will discuss…".
- May repair obvious extraction artifacts (broken hyphenation, split words).
- Each excerpt is a contiguous run from one page; separate blockquotes per
  page, each starting `(p. NNN)`.
- **Entity balance**: when the answer involves multiple distinct entities
  (small bowel AND colon; breast AND axilla), provide at least one quote per
  entity, each from a passage that explicitly names that entity. A colon-
  trauma passage does not support a small-bowel recommendation even if the
  principle reads identically. If no entity-specific passage exists for one
  entity: "⚠️ No passage in the references directly supports the [entity]
  management; this decision relies on general medical knowledge." — and only
  that entity's slot is hedged.
- No supporting text at all → "No directly matching passage found in
  retrieved references." (and `answer_supported: false`).
- Every quote goes through `verify_and_render.py`. A quote that fails
  verification keeps its ✗ in the outputs and gets no evidence page — never
  silently swap or trim a quote to make verification pass; fix it only if the
  source genuinely says it elsewhere.

## Paraphrased Passage rules

One paraphrase per supporting blockquote, in order: based SOLELY on that
quote's content, same clinical fact in different wording (1–2 sentences),
ending with the locked inline citation. Preserve entity specificity — never
generalize "small bowel" to "bowel". Hedged slots stay hedged.

## Tags — allowed values (from the app)

These are the app's `categories` rows, matched **by exact name**. The importer
never creates a category: a name that isn't on these lists is dropped with a
warning, and the question lands with no Subject (or no System) at all. Emit the
literal string, including the ampersands and commas.

**Subjects** (15): Anatomy | Biostatistics & Ethics | Fluids, Electrolytes &
Acid-Base | Immunology & Transplantation | Infection & Antimicrobial Therapy |
Nutrition & Metabolism | Oncology & Tumor Biology | Operative Principles &
Technique | Pharmacology | Physiology & Pathology | Preoperative, Perioperative
& Anesthesia | Radiology & Imaging Interpretation | Surgical Complications |
Transfusion & Coagulation | Wound Healing

**Systems** (16): Esophagus | Stomach | Small Intestine | Large Intestine |
Anorectal | Hernia | Biliary | Liver | Pancreas | Spleen | Breast | Endocrine |
Skin & Soft Tissue | Critical Care | Trauma | Subspecialty Surgery

Note the shape of the Subject list: it is a **surgical-topic** taxonomy, not the
basic-science one ("Physiology", "Microbiology", "Clinical Medicine", "Emergency
Medicine", "Trauma", "Critical Care" are NOT Subjects). Pathology rides with
physiology in `Physiology & Pathology`; trauma and critical care are **Systems**
only. When a question's natural subject has no row, pick the nearest existing one
rather than inventing a name — a missing category is a flag for the operator to
create in the app, never a string to make up.

"Subspecialty Surgery" is a single umbrella tag (pediatric, vascular,
thoracic, plastics, GU, gyn-ob, head & neck) — emit only the literal umbrella
string, never the sub-area.

Source of truth: `categories` (specialty `Subject` / `System`) in the sawab DB,
seeded by `supabase/migrations/20260508000000_seed_subjects_and_systems.sql` plus
later additions. Re-check these lists before a large batch — they grow.

## Quality control before finalizing

- All vitals/labs/imaging from the original preserved, and still inline in the
  prose (no tables — see *Values stay IN the prose*).
- Any reference range copied from `lab_ranges.py`, never recalled; analytes the
  sheet lacks carry no range.
- Intent and action verb unchanged; a negative lead-in is still negative, in
  capitals, with `negative_leadin: true` set.
- Vignette reads board-authored, not grammar-corrected.
- Four choices A–D, canonical forms used consistently everywhere. Four is this
  skill's house standard for new questions and `Choice E` stays empty; the bank
  itself accepts 4 or 5, so an imported 5-choice question is not a defect and
  the audit skill will not flag one.
- Choice set passes the house-style check (length parity, parallel form,
  sentence case, American spelling, abbreviation ruling, no stem echo) — and
  **no `GIVEAWAY`**.
- Prose cells pass the American-spelling check too (`check_prose_style.py`);
  abbreviations in prose are fine after first mention and are not checked.
- No unsourced precise number in any explanation field.
- One entity spelled one way across the batch.
- Explanations teach decision-making, not restatement.
- Every citation verified (or honestly marked ✗ / hedged), carrying the PRINTED
  folio and a canonical book title.
