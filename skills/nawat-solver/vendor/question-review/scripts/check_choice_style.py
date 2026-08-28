# --- VENDORED COPY - DO NOT EDIT ------------------------------------
# source : .claude/skills/question-review/scripts/check_choice_style.py   (sawab repo - the source of truth)
# sha256 : cb95e01661ab74962d8437762d8c93157a891b572984dd4f4bbb5b74a15e20df
# synced : 2026-08-28 by tools/sync_from_sawab.py
# Edit the sawab original, not this file. `sync_from_sawab.py --check`
# fails when the two have drifted apart.
# --------------------------------------------------------------------

#!/usr/bin/env python3
"""Guard: do a question's choices obey the house style in reference/field_spec.md?

    check_choice_style.py RESULTS.json --source SOURCE.csv   # audited/edited set
    check_choice_style.py --csv V2.csv [--source SOURCE.csv] # the built v2 CSV
    check_choice_style.py --all EXPORT.csv                   # sweep the whole bank

Five rules. Four are properties of the WHOLE choice set and the fifth compares
the set against the stem — which is why this needs the source row, not just an
edited `after` cell:

1. LENGTH PARITY — no choice may tower over the others. A key that is the long
   option is guessable without any medicine, and the bank skews that way: the
   correct answer is uniquely shortest in only 16% of questions against a ~25%
   chance baseline, so "eliminate the terse options" already works.
2. PARALLEL FORM — every choice in a question shares one grammatical shape
   (all verb-led, or all noun phrases). The odd one out is a tell.
3. SENTENCE CASE — capitalise the first character, then only proper nouns,
   eponyms and genuine acronyms. No Title Case.
4. AMERICAN SPELLING — esophagus/hemorrhage/tumor/edema, never the -oe-/-ae-/-our
   British forms.
5. ABBREVIATIONS — a choice may carry only what reference/abbreviations.json
   allows bare; anything on its expand list must be written out with exactly the
   words recorded there, and an unlisted token is surfaced, never guessed at.
6. STEM ECHO — a distinctive stem term landing in exactly one choice, and that
   choice the key, lets a reader word-match to the answer. The fix belongs in
   the STEM (paraphrase the term); never degrade the key's precision to hide it.
   The loosest of the six: expect roughly half of its hits to be unavoidable
   overlap, so it nominates for the auditor to judge rather than asserting.

`--source` supplies the answer key, which the v2 CSV deliberately omits. Without
it the key-independent rules still run; with it, an outlier that turns out to be
the KEY is escalated, because that is the case that actually leaks the answer.

Exits non-zero if any question is flagged. Heuristic by design — a hit means
"look at this one". Eponyms and acronyms are the expected false positives.
"""
import argparse, csv, json, pathlib, re, statistics, sys

from qr_common import british_hits

csv.field_size_limit(10 ** 9)
SLOTS = "ABCDE"

# --- 1. length parity -------------------------------------------------------
LEN_RATIO = 1.5     # longest vs mean of the others
LEN_MARGIN = 15     # …and this many characters clear of the next longest

# --- 2. parallel form -------------------------------------------------------
# Base-form verbs that open a management option. A choice starting with one is
# "verb-led"; everything else counts as a noun phrase.
#
# Deliberately EXCLUDED as noun/verb ambiguous in surgical English, because each
# produced false "not parallel" flags against the real bank: repeat ("Repeat CT
# scan" is a noun phrase), repair ("Primary repair with buttress"), drain
# ("Drain removal"), control ("Control of source"). There is no gerund class
# either — medical -ing words are usually noun modifiers ("Diverting loop
# ileostomy", "Dumping syndrome", "Feeding jejunostomy"), not verbs.
VERBS = {
    "add", "adjust", "administer", "apply", "arrange", "aspirate", "avoid", "base",
    "begin", "check", "close", "consult", "continue", "correct", "decompress",
    "decrease", "delay", "discharge", "discontinue", "elevate", "excise", "explore",
    "extubate", "give", "hold", "increase", "initiate", "insert", "intubate",
    "irrigate", "ligate", "manage", "measure", "monitor", "obtain", "observe",
    "order", "perform", "place", "prescribe", "proceed", "refer", "remove",
    "request", "resect", "restrict", "resuscitate", "schedule", "send", "start",
    "stop", "switch", "take", "transfuse", "treat", "withhold",
}

# --- 3. sentence case -------------------------------------------------------
# Inverted whitelist: rather than enumerate every eponym, list ordinary words
# that must never carry a capital mid-phrase. Far fewer false positives.
NEVER_CAPS = {
    "abdominal", "acid", "acids", "acute", "administration", "agent", "alone",
    "analysis", "and", "antibiotic", "antibiotics", "artery", "aspiration",
    "biopsy", "block", "blood", "bowel", "bypass", "cancer", "care", "catheter",
    "cell", "cells", "chest", "chronic", "closure", "colon", "complete",
    "conservative", "contrast", "control", "count", "decompression", "deficiency",
    "delayed", "disease", "distal", "drainage", "early", "elective", "emergency",
    "endoscopic", "exploration", "factor", "fatty", "feeding", "fluid", "fluids",
    "gastric", "globulin", "high", "hormone", "immediate", "immediately",
    "infection", "infusion", "injection", "injury", "intravenous", "late",
    "level", "levels", "liver", "low", "lymph", "management", "massive",
    "measurement", "monitoring", "necrosis", "node", "nodes", "observation",
    "obstruction", "only", "open", "oral", "outlet", "pain", "pancreatic",
    "partial", "perforation", "placement", "proximal", "radiation", "rate",
    "reconstruction", "rectal", "removal", "repair", "replacement", "resection",
    "rest", "resuscitation", "scan", "screening", "secretion", "shunt", "small",
    "study", "supportive", "surgery", "surgical", "suture", "syndrome", "test",
    "testing", "therapy", "tissue", "total", "transfusion", "treatment", "tube",
    "ulcer", "ultrasound", "urgent", "urine", "vein", "vitamin", "volume", "wound",
}

# --- 4. american spelling (BRITISH table + british_hits live in qr_common) ---

# --- 5. stem echo (verbal association cue) ----------------------------------
# A distinctive stem term that surfaces in exactly ONE choice, and that choice is
# the key, lets a reader word-match their way to the answer with no medicine.
# Ordinary vignette vocabulary is excluded: it is not distinctive, so its landing
# in one option is coincidence rather than a cue.
STEM_STOPWORDS = {
    "abdomen", "abdominal", "admission", "admitted", "adult", "after", "again",
    "already", "another", "assessment", "associated", "before", "being", "below",
    "besides", "between", "brought", "cannot", "chronic", "clinical", "complains",
    "condition", "consistent", "course", "demonstrates", "denies", "department",
    "developed", "develops", "diagnosis", "diagnostic", "differential", "discharge",
    "doing", "during", "elderly", "emergency", "episode", "episodes", "evaluated",
    "evaluation", "examination", "excluded", "explains", "female", "finding",
    "findings", "follow", "following", "further", "given", "helpful", "history",
    "hospital", "however", "imaging", "improve", "indicated", "initial", "injury",
    "inpatient", "instability", "investigation", "laboratory", "likely", "little",
    "management", "manage", "months", "morning", "negative", "normal", "noted",
    "obtained", "office", "operative", "otherwise", "outpatient", "overall",
    "patient", "patients", "performed", "physical", "positive", "postoperative",
    "practice", "presentation", "presented", "presents", "previous", "previously",
    "principally", "problem", "procedure", "prompted", "reported", "response",
    "responsible", "result", "results", "reveals", "review", "period", "remains",
    "routine", "scheduled", "screening", "several", "shortly", "should", "showed",
    "shows", "significant", "since", "started", "status", "studies", "study",
    "subsequent", "suggests", "surgery", "surgical", "symptom", "symptoms",
    "systemic", "taking", "temperature", "testing", "therapy", "these", "those",
    "though", "throughout", "today", "treated", "treatment", "underwent",
    "undergoing", "unremarkable", "using", "vital", "weeks", "which", "while",
    "without", "woman", "worsening", "years",
}
MIN_CUE_LEN = 7          # shorter words carry too little signal
LEADIN = re.compile(r"[^.?!]*\?\s*$")

# --- 6. abbreviation policy -------------------------------------------------
# reference/abbreviations.json is the operator's locked ruling: what may stand
# bare, what must be written out and with exactly which words, and which symbols
# were never abbreviations. A token in none of those lists has no ruling yet, so
# it is surfaced rather than guessed at.
ABBREV_TOKEN = re.compile(r"\b[A-Z][A-Za-z]*[A-Z][A-Za-z0-9]*\b")
GENUS_TOKEN = re.compile(r"\b[A-Z]\.\s*[a-z]{3,}\b")
_NUMERAL = re.compile(r"^[IVXL]+[a-cA-C]?$")


def load_policy():
    p = pathlib.Path(__file__).resolve().parent.parent / "reference" / "abbreviations.json"
    if not p.is_file():
        return None
    d = json.loads(p.read_text())
    return {"bare": set(d.get("bare", [])), "expand": d.get("expand", {}),
            "proper": set(d.get("proper_names", [])), "ambiguous": d.get("ambiguous", {})}


def check_abbreviations(live, key, policy):
    if not policy:
        return []
    out, keyed = [], (lambda L: " [THE KEY]" if key and L == key else "")
    for L in sorted(live):
        text = live[L]
        toks = [m.group(0) for m in GENUS_TOKEN.finditer(text)]
        toks += [m.group(0) for m in ABBREV_TOKEN.finditer(text) if not _NUMERAL.match(m.group(0))]
        for tok in dict.fromkeys(toks):
            t = re.sub(r"\.\s*", ". ", tok)
            if t in policy["bare"] or t in policy["proper"] or t in policy["ambiguous"]:
                # Ambiguous tokens are settled cell by cell, not by a global rule.
                continue
            if t in policy["expand"]:
                out.append(f"choice {L}{keyed(L)}: {t!r} must be written out as "
                           f"{policy['expand'][t]!r} (abbreviation policy)")
            else:
                out.append(f"choice {L}{keyed(L)}: {t!r} has no ruling in "
                           f"reference/abbreviations.json — decide it, don't guess")
    return out


POLICY = load_policy()

PARENTHETICAL = re.compile(r"\([^)]{3,}\)")
FIRST_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
WORDS = re.compile(r"[A-Za-z][A-Za-z'-]*")


def norm(v):
    return ("" if v is None else str(v)).replace("\r\n", "\n").replace("\r", "\n").strip()


def form_of(text):
    m = FIRST_WORD.search(text)
    if not m:
        return "noun-phrase"
    return "verb-led" if m.group(0).lower() in VERBS else "noun-phrase"


def title_case_words(text):
    """Ordinary words carrying a capital they haven't earned."""
    ws = WORDS.findall(text)
    return [w for w in ws[1:] if w[0].isupper() and not w.isupper()
            and w.lower() in NEVER_CAPS]


def stem_of(word):
    """Crude suffix strip, so 'cholangitis'/'cholangitic' and 'recurrent'/
    'recurrence' collapse together. Good enough to match a repeat; not a stemmer."""
    w = word.lower()
    for suf in ("ations", "ation", "ities", "ity", "ings", "ing", "edly", "ence",
                "ency", "ly", "ed", "es", "s", "al", "ic"):
        if w.endswith(suf) and len(w) - len(suf) >= 5:
            return w[: -len(suf)]
    return w


def stem_echo(stem_text, live, key):
    """Distinctive stem terms that land in exactly one choice — the key."""
    if not stem_text or not key or key not in live or len(live) < 3:
        return []
    leadin = LEADIN.search(stem_text)
    leadin = leadin.group(0) if leadin else ""
    leadin_stems = {stem_of(w) for w in WORDS.findall(leadin)}

    terms = {}
    for w in WORDS.findall(stem_text):
        if len(w) >= MIN_CUE_LEN and w.lower() not in STEM_STOPWORDS:
            terms.setdefault(stem_of(w), w)

    choice_stems = {L: {stem_of(w) for w in WORDS.findall(t)} for L, t in live.items()}
    cues = []
    for st, surface in sorted(terms.items(), key=lambda kv: -len(kv[1])):
        hits = [L for L, s in choice_stems.items() if st in s]
        if len(hits) == 1 and hits[0] == key:
            cues.append((surface, st in leadin_stems))
    if not cues:
        return []
    words = ", ".join(f"{w!r}{' (in the LEAD-IN)' if inlead else ''}" for w, inlead in cues[:4])
    return [f"stem echo: {words} appear(s) in the stem and in choice {key} [THE KEY] alone "
            f"— a reader can word-match to the answer. Paraphrase it in the STEM; never "
            f"degrade the key's precision to hide it"]




def check_choices(texts, key=None, stem_text=""):
    """texts: {slot: text} for populated slots. key: correct slot, if known."""
    live = {L: t for L, t in texts.items() if t.strip()}
    if len(live) < 2:
        return []
    out = stem_echo(stem_text, live, key)
    out += check_abbreviations(live, key, POLICY)
    keyed = (lambda L: " [THE KEY]" if key and L == key else "")

    # 1. length parity
    lens = {L: len(t) for L, t in live.items()}
    longest = max(lens, key=lambda L: lens[L])
    others = [v for L, v in lens.items() if L != longest]
    runner_up = max(others)
    if lens[longest] >= LEN_RATIO * statistics.mean(others) and \
            lens[longest] - runner_up >= LEN_MARGIN:
        sev = "GIVEAWAY" if key and longest == key else "length outlier"
        out.append(f"{sev}: choice {longest}{keyed(longest)} is {lens[longest]} chars vs "
                   f"{runner_up} for the next longest — bring the distractors up to the "
                   f"same specificity (never trim the key's meaning)")

    # 1b. a qualifier only the key carries is the same tell in miniature
    withp = [L for L, t in live.items() if PARENTHETICAL.search(t)]
    if len(withp) == 1 and len(live) > 2:
        L = withp[0]
        out.append(f"{'GIVEAWAY: ' if key and L == key else ''}choice {L}{keyed(L)} is the "
                   f"only one with a parenthetical qualifier — match it across the set or drop it")

    # 2. parallel form
    forms = {L: form_of(t) for L, t in live.items()}
    kinds = set(forms.values())
    if len(kinds) > 1:
        counts = {k: sum(1 for v in forms.values() if v == k) for k in kinds}
        dominant = max(counts, key=lambda k: counts[k])
        if counts[dominant] * 2 > len(live):
            odd = [f"{L} ({forms[L]}){keyed(L)}" for L in sorted(live) if forms[L] != dominant]
            out.append(f"form not parallel: most choices are {dominant}; recast {', '.join(odd)}")
        else:
            # An even split has no majority to conform to — the operator picks.
            grouped = {k: [L for L in sorted(live) if forms[L] == k] for k in sorted(kinds)}
            out.append("form not parallel and evenly split — pick one shape for the set: "
                       + "; ".join(f"{k}: {', '.join(v)}" for k, v in grouped.items()))

    # 3. sentence case
    for L in sorted(live):
        bad = title_case_words(live[L])
        if bad:
            out.append(f"choice {L}{keyed(L)}: Title Case on ordinary word(s) "
                       f"{bad} — use sentence case")
        elif live[L][:1].islower() and not re.match(r"^[a-z][A-Z]", live[L]):
            # 'aPTT', 'tPA', 'pH' are correctly lowercase-initial — not a case error.
            out.append(f"choice {L}{keyed(L)}: starts lowercase — capitalise the first character")

    # 4. american spelling
    for L in sorted(live):
        for found, repl in british_hits(live[L]):
            out.append(f"choice {L}{keyed(L)}: British spelling {found!r} — use the "
                       f"American form ({repl}…)")
    return out


def row_choices(row):
    return {L: norm(row.get(f"Choice {L}")) for L in SLOTS}


def load_source(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return {norm(r.get("ID")): r for r in csv.DictReader(fh)}


def from_export(path, key_col=True):
    src = load_source(path)
    for qid, row in src.items():
        key = norm(row.get("Correct Answer")).upper()[:1] if key_col else None
        yield qid, check_choices(row_choices(row), key or None,
                                 norm(row.get("Reformatted Question")))


def from_csv(path, source):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            qid = norm(row.get("ID"))
            key = None
            if source and qid in source:
                key = norm(source[qid].get("Correct Answer")).upper()[:1] or None
            yield qid, check_choices(row_choices(row), key,
                                     norm(row.get("Reformatted Question")))


def from_results(path, source):
    """Overlay each question's accepted choice edits onto its source row, so the
    set is judged as it will actually ship — not cell by cell."""
    if not source:
        sys.exit("RESULTS.json needs --source SOURCE.csv (the choice set is judged whole)")
    data = json.loads(pathlib.Path(path).read_text())
    for q in data.get("results", []):
        qid = q["question_id"]
        row = source.get(qid)
        if not row:
            continue
        texts = row_choices(row)
        touched = False
        for f in q.get("findings", []):
            if (f.get("verify") or {}).get("verdict") == "refuted":
                continue
            fld = f.get("field", "")
            if fld.startswith("choice_") and norm(f.get("after")):
                texts[fld[-1]] = norm(f["after"])
                touched = True
        stem_txt = norm(row.get("Reformatted Question"))
        for f in q.get("findings", []):
            if f.get("field") == "stem" and norm(f.get("after")) and \
                    (f.get("verify") or {}).get("verdict") != "refuted":
                stem_txt = norm(f["after"])
        if touched or stem_txt != norm(row.get("Reformatted Question")):
            yield qid, check_choices(texts, norm(row.get("Correct Answer")).upper()[:1] or None,
                                     stem_txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?")
    ap.add_argument("--csv", help="a built v2 CSV")
    ap.add_argument("--all", dest="export", help="a full admin export — sweep the bank")
    ap.add_argument("--source", help="source export, for the answer key")
    ap.add_argument("--limit", type=int, default=15, help="examples to print")
    args = ap.parse_args()

    source = load_source(args.source) if args.source else None
    if args.export:
        pairs = list(from_export(args.export))
    elif args.csv:
        pairs = list(from_csv(args.csv, source))
    elif args.results:
        pairs = list(from_results(args.results, source))
    else:
        ap.error("pass RESULTS.json, --csv V2.csv, or --all EXPORT.csv")

    flagged = [(q, m) for q, m in pairs if m]
    tally = {}
    for _, msgs in flagged:
        for m in msgs:
            kind = ("giveaway" if m.startswith("GIVEAWAY") else
                    "length outlier" if "length outlier" in m else
                    "lone parenthetical" if "parenthetical" in m else
                    "form not parallel" if m.startswith("form") else
                    "Title Case" if "Title Case" in m else
                    "lowercase start" if "starts lowercase" in m else
                    "must be written out" if "must be written out" in m else
                    "no ruling yet" if "no ruling" in m else
                    "British spelling" if "British spelling" in m else
                    "stem echo" if m.startswith("stem echo") else "other")
            tally[kind] = tally.get(kind, 0) + 1

    print(json.dumps({
        "questions_checked": len(pairs),
        "questions_flagged": len(flagged),
        "issues_by_kind": dict(sorted(tally.items(), key=lambda kv: -kv[1])),
    }, indent=1, ensure_ascii=False))
    for qid, msgs in flagged[: args.limit]:
        print(f"\n[{qid[:8]}]")
        for m in msgs:
            print(f"  - {m}")
    if len(flagged) > args.limit:
        print(f"\n… {len(flagged) - args.limit} more flagged question(s)")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
