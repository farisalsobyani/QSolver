# Stage 1 — Reasoning rubric

Adapted from Nawat's `REASONING_SYSTEM_PROMPT`. This is internal analysis — its
product is the fields of the entry JSON (`answer`, `gates`, per-choice notes),
not user-facing prose. Think thoroughly; the final card's quality depends
entirely on the rigor here. Unlike the original pipeline, retrieval is not
frozen before reasoning: whenever a step below hinges on a fact you haven't
seen, go back to the corpus (map → search.py → open pages) and get it.

For every MCQ, perform these steps in order:

## 1. Classify the intent
What is the stem actually asking for?
`diagnosis | next-best-step | most-likely-cause | mechanism | contraindication |
best-initial-test | definitive-test | prognosis | risk-factor | pharmacology | other`
— plus one sentence restating the specific request (e.g. "the most immediate
action that changes management, not the underlying diagnosis"). A "next step"
answer must be an action; a "confirmatory test" answer must be confirmatory,
not screening.

## 2. Extract disqualifiers from the stem
Details that RULE OUT otherwise-plausible answers. List all of them as short
phrases ("age 82", "CKD stage 4", "6 hours since onset"): age extremes,
comorbidities (CKD, pregnancy, allergies, immunosuppression), timing
(acute/chronic, hours since onset for time-dependent therapies), prior
treatment already tried, hemodynamic state, lab/imaging values that exclude a
diagnosis.

## 3. State the pathology scope and management paradigm
Three to four sentences that prevent the two biggest failure modes — applying
management of a *neighboring* entity, and explanations that ignore legitimate
alternative treatments:

(a) Name the entity precisely ("LCIS — lobular carcinoma in situ").
(b) State its clinical category in a way that determines management ("a risk
    marker / non-obligate precursor, NOT a single excisable lesion").
(c) Name the adjacent entities you are explicitly NOT treating as equivalent
    (LCIS vs DCIS vs invasive; SBO vs LBO; UC vs Crohn's; stable vs unstable).
(d) **List the FULL management spectrum WITH DECISION CRITERIA** — every major
    path in standard practice, and for each, the specific trigger/threshold
    that selects it. A bare list of options is not enough; state the rule that
    separates one path from its neighbor. Example: "Penetrating small bowel:
    nondestructive SINGLE injury → primary repair; nondestructive MULTIPLE
    injuries too closely spaced for separate tension-free repair (<10 cm
    apart) → segmental resection + single anastomosis; destructive (>50%
    wall, devascularized) → resection; unstable / massive contamination →
    damage control." Never omit a legitimate path even if it isn't among the
    choices — the card's teaching needs the full paradigm.

## 4. Canonicalize the choices
Reproduce the stem's choices with surface cleanup only. The cleaned text is
the CANONICAL form, reused verbatim everywhere downstream (choice list,
✅ Answer line, Other Options headers, all prose mentions).

- APPLY: capitalization ("defecography" → "Defecography"; "ct angiography" →
  "CT angiography"), obvious misspellings and OCR artifacts ("laparo- scopy" →
  "laparoscopy", "Iaparotomy" → "laparotomy"), minor grammar/parallelism.
- NEVER CHANGE: drug names, doses, units, numbers, lab values, anatomical
  terms, procedure names, eponyms, clinical qualifiers (timing, laterality,
  "with"/"without"). Never add, drop, reorder, or merge choices; never reword
  toward or away from correctness. When unsure whether an edit changes
  meaning, leave the text as written.
- Fewer than 4 choices (or none): GENERATE plausible distractors to make
  exactly 4 (A–D) — clinically related but clearly incorrect (common
  misconceptions, adjacent diagnoses). The correct answer must be one of the
  four.
- **Generated choice sets must be HOMOGENEOUS**: every choice is the same
  category of thing as what the lead-in asks for — all investigations, all
  next-step actions, all diagnoses, all mechanisms. A diagnosis sitting among
  "next step" actions (or vice versa) is a giveaway distractor; match the
  category of the existing correct answer and lead-in. (Choices taken from
  the source are exempt — they stay as written even if heterogeneous.)
- Only exception to canonical-form reuse: verbatim quotes in the Supporting
  Passage keep the source's exact casing.

### House style — a property of the SET, not of one choice

A choice set can be medically flawless and still hand the answer away on
format. Three of these seven rules (1, 2, 5) are properties of the whole SET, so
judge them by reading the four choices side by side, against the stem; the rest
apply string by string.

1. **Length parity.** The key must not tower over the distractors. If it is
   half again as long as the rest, a student eliminates the terse options and
   is right more often than chance — no medicine required. Fix it by **raising
   the distractors to the key's specificity**, or by a *meaning-preserving*
   reduction of the key where one exists (`Alpha-1 agonist (phenylephrine)` →
   `Phenylephrine`, beside Dopamine/Dobutamine/Epinephrine). **Never trim the
   key's clinical content** to make it fit — `Low anterior resection with
   coloanal anastomosis` → `Low anterior resection` loses the operation. If a
   distractor cannot be raised without becoming arguably correct, leave the set
   and say so in the entry.
   The same tell in miniature: a **parenthetical qualifier only the key
   carries**. Match it across the set or drop it.
2. **Parallel form.** One grammatical shape for the whole set — all verb-led
   (`Administer IV fluids`) or all noun phrases (`Nasogastric decompression`).
   A "most likely diagnosis" lead-in wants noun phrases; a "best next step"
   lead-in usually wants verbs. The odd one out is the tell. (This is the
   set-level companion to the homogeneity rule above.)
3. **Sentence case.** Capitalize the first character, then only proper nouns,
   eponyms and genuine acronyms. **No Title Case** — `Immediate Oral Feeding` →
   `Immediate oral feeding`. Untouched: `Roux-en-Y gastric bypass`, `E. coli`,
   `CT abdomen`.
4. **American spelling** throughout: `oesophagectomy` → `esophagectomy`,
   `haemostasis` → `hemostasis`, `tumour` → `tumor`, `ischaemia` → `ischemia`.
5. **No stem echo.** A distinctive stem term must not appear in exactly one
   choice when that choice is the key — the reader word-matches to the answer.
   The fix belongs in the **stem** (paraphrase the term there); never degrade
   the key's precision to hide the overlap, and never rename a disease to dodge
   its own name. Unavoidable overlap is fine: if the stem establishes a
   pseudocyst and the answer is pseudocyst drainage, the word has to appear.
6. **Abbreviations follow the bank's locked ruling.** It is settled, not a
   judgement call: `$SAWAB_REPO/.claude/skills/question-review/reference/abbreviations.json`
   holds four lists — `bare` (may stand unexpanded: `CT`, `ERCP`, `WBC`, `NGT`,
   `E. coli`, `FAST`, `TPN`…), `expand` (write out **using exactly the recorded
   words**, not a synonym: `ABG` → `arterial blood gas`, `APR` →
   `abdominoperineal resection`), `proper_names` (gene/molecule/brand symbols,
   never expanded: `BRAF`, `CHEK2`, `DNA`, `DAMPs`), and `ambiguous` (two
   meanings in this bank — `CO` carbon monoxide vs cardiac output, `PD`
   peritoneal dialysis vs pancreaticoduodenectomy — decided per occurrence from
   context). A token on none of the four lists **has no ruling yet**: leave it as
   the source wrote it and say so in the entry, rather than inventing policy.
   Expanding lengthens a choice, so re-check rule 1 afterwards — an expansion
   that only the key carries manufactures a length tell.
7. **Write an entity the way the bank already writes it.** One clinical entity,
   one spelling, bank-wide — `Angioembolization` not `Angioembolisation` or
   `Angio-embolization`; `Ringer's lactate` in the bank's existing form. Before
   coining a phrasing for a common procedure or finding, prefer the string the
   bank already uses. **But parallel form inside THIS question wins**: if the set
   reads `Add zinc · Add iron · Add copper`, the fourth choice is `Add essential
   fatty acids` even though the bank's commoner bare form is `Essential fatty
   acids`. Bank-wide consistency governs only what the question does not
   constrain.

These are the sawab bank's rules, not new ones — the authoritative statement is
`reference/field_spec.md` → *House style* in the question-review skill, and
`check_choice_style.py` enforces 1-6 mechanically at export, and
`check_term_consistency.py` nominates drift for 7 (see SKILL.md → Export). Getting them right here is much cheaper than having the audit pipeline
flag them later: on recent batches that checker flags **over half** of the
questions, most often because the key is the longest option.

## 5. Per-choice analysis
For every letter: verdict (`correct | wrong | uncertain`), a short reason tag
(`ignores-disqualifier`, `scope-mismatch`, `right-diagnosis-wrong-intent`,
`wrong-mechanism`, `contraindicated-in-CKD`, `outdated-timing`, `correct`),
and `supportedBy` / `contradictedBy` — short references (book + page) drawn
ONLY from corpus pages you actually opened. Never invent a citation.

**Check each choice against the DECISION CRITERIA, not just the entity-level
heuristic.** Two-step check: (i) which criterion from step 3(d) does this
choice correspond to? (ii) do the stem's specific quantifiers actually trigger
that criterion? Scan the stem for counts, spacing, percentages, hours, grades.
If two choices fall under the same entity-level heuristic (both
"bowel-preserving"), the differentiator is almost always a stem quantifier —
find it. Do NOT stop at the entity level when the stem contains
count/spacing/timing/size/grade modifiers; those routinely decide the answer.

If evidence for a choice is thin, search the corpus again with different terms
before settling on `uncertain`.

## 6. Pick the answer
Exactly one letter — the one whose verdict is `correct` in step 5.

## 7. Self-check (honest, three booleans)
- `intentMatch` — does the chosen answer satisfy step 1's intent?
- `answerSupported` — is the answer backed by at least one corpus passage that
  states the same clinical fact at the DECISION level? Semantic equivalents
  COUNT ("annual" ≡ "every 12 months"; "chemoprevention with tamoxifen" ≡
  "tamoxifen for risk reduction"; "laparotomy" ≡ "operative intervention").
  What does NOT count: mere topical relevance, chapter introductions, or a
  passage about a neighboring entity.
- `distractorsRefuted` — for each wrong choice, is there either a
  contradicting passage or a clear stem disqualifier?

## 8. Self-check integrity
`answerSupported` is a soft confidence signal for reviewers, NOT a refusal
switch — the answer is rendered regardless. If you set it `true`, you must be
able to point at a specific page whose stated fact matches the answer at the
decision level; if you cannot, set it `false` and still emit your best letter.
Do not flip it to `true` to "make the question answerable" — the escalation
retry exists precisely so unsupported answers get a second chance with wider
retrieval.

## 9. Review flag
`needs_review = (answerSupported == false)`. Nothing else raises the flag —
an unrefuted distractor or an `uncertain` verdict is reported honestly in its
own field but does not, by itself, flag the question.
