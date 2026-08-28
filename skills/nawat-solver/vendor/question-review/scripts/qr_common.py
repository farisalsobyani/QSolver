# --- VENDORED COPY - DO NOT EDIT ------------------------------------
# source : .claude/skills/question-review/scripts/qr_common.py   (sawab repo - the source of truth)
# sha256 : 25b1da1ffe81e0fe979b2162b6de0ed2f57d92b44d27eedf75552e3f5bb813c5
# synced : 2026-08-28 by tools/sync_from_sawab.py
# Edit the sawab original, not this file. `sync_from_sawab.py --check`
# fails when the two have drifted apart.
# --------------------------------------------------------------------

"""Shared helpers for question-review: CSV field norm, content hash, ledger IO.

`norm()` MUST mirror the sawab importer's normalization
(src/lib/questionCsvSync.ts): string-ify, CRLF/CR -> LF, trim. The content hash
is computed over the same field set the eligibility/ledger logic compares, so an
unchanged round-trip (export -> audit -> import -> re-export) re-hashes identically.
"""

import hashlib
import json
import pathlib
import re

# CSV headers whose normalized values define a question's content identity.
# Order is fixed — it's part of the hash. `Choice A–E` collapse to the non-empty
# choices in label order; `Correct Answer` is the keyed letter.
HASH_TEXT_FIELDS = [
    "Reformatted Question", "Concept", "Why",
    "Reasons Wrong Answers Are Wrong", "Take-Home Message",
    "References", "Cited Passages",
]
CHOICE_LABELS = ["A", "B", "C", "D", "E"]

# Header names the sawab importer itself accepts for a column
# (questionCsvSync.ts FieldSpec.aliases; BulkImport.tsx reads the same pairs).
# A CSV written by the nawat-solver skill names the passages column
# "Paraphrased Passages"; a checker that looks only for "Cited Passages" reads it
# as empty, which silently turns every sourcing/parity judgement into a false
# positive rather than an error.
CSV_ALIASES = {
    "Cited Passages": ["Paraphrased Passages"],
    "Take-Home Message": ["Bottom Line"],
    "Subject": ["Subjects"],
    "System": ["Systems"],
}


def csv_cell(row: dict, col: str) -> str:
    """A row's normalized value for a column, honouring the importer's aliases."""
    for key in [col, *CSV_ALIASES.get(col, [])]:
        if key in row:
            return norm(row.get(key))
    return ""


def norm(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\r\n", "\n").replace("\r", "\n").strip()


def content_hash(row: dict) -> str:
    """Stable per-question hash over stem, choices, correct letter, and the text
    fields — using the importer's norm() so a no-op round-trip is a hash match."""
    parts = []
    for f in HASH_TEXT_FIELDS:
        parts.append(f"{f}={norm(row.get(f))}")
    for l in CHOICE_LABELS:
        t = norm(row.get(f"Choice {l}"))
        if t:
            parts.append(f"Choice {l}={t}")
    parts.append(f"Correct Answer={norm(row.get('Correct Answer')).upper()}")
    blob = "".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_ledger(path: pathlib.Path) -> dict:
    """Ledger keyed by question_id -> entry. Accepts a list or a dict on disk."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return {e["question_id"]: e for e in data}
    return data


def save_ledger(path: pathlib.Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(entries.values(), key=lambda e: e["question_id"])
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------- house style
# The bank is written in American English. This lives here, not in one checker,
# because the rule is bank-wide: it governs the choice set AND the prose cells
# (stem, concept, why, reasons wrong, take-home, cited passages), which are just
# as student-facing. check_choice_style.py and check_prose_style.py share it.
BRITISH = [
    # haemo excludes Haemophilus: that is a genus name, spelled the same in
    # American English, not a British spelling of anything.
    (r"\boesophag", "esophag"), (r"\bhaemo(?!philus)", "hemo"), (r"ischaemi", "ischemi"),
    (r"\btumour", "tumor"), (r"\banaesthe", "anesthe"), (r"\bpaediatr", "pediatr"),
    (r"diarrhoea", "diarrhea"), (r"\boedema", "edema"), (r"\bcoeliac", "celiac"),
    (r"\bfibre(s?)\b", "fiber\\1"), (r"\bcolour", "color"), (r"catheteris(e|es|ed|ing|ation|ations)", "catheteriz\\1"),
    (r"\bmanoeuvre", "maneuver"), (r"\bfoetal", "fetal"), (r"haematolog", "hematolog"),
    # NOT a bare \bembolis prefix: that also matches "embolism", which is already
    # the American form (106 uses in the bank against 8 genuine British ones), so
    # the naive rule proposed turning "pulmonary embolism" into "embolizm".
    (r"embolis(e|es|ed|ing|ation)", "emboliz\\1"),
    (r"\borganis(e|ing|ed|ation)", "organiz\\1"),
    (r"\bfaec", "fec"), (r"\bleucocyte", "leukocyte"), (r"\bdiarrhoe", "diarrhe"),
    (r"\bhaemat", "hemat"), (r"\bcaecum", "cecum"), (r"\bcaecal", "cecal"),
    (r"\banaemi", "anemi"), (r"\bhypovolaemi", "hypovolemi"), (r"\bnormovolaemi", "normovolemi"),
    (r"\bhypercalcaemi", "hypercalcemi"), (r"\bbacteraemi", "bacteremi"),
    (r"\bsepticaemi", "septicemi"), (r"\buraemi", "uremi"), (r"\bsulphur", "sulfur"),
    (r"stabilis(e|es|ed|ing|ation|ations)", "stabiliz\\1"), (r"normalis(e|es|ed|ing|ation|ations)", "normaliz\\1"), (r"mobilis(e|es|ed|ing|ation|ations)", "mobiliz\\1"),
    (r"visualis(e|es|ed|ing|ation|ations)", "visualiz\\1"), (r"\bprogramme\b", "program"),
    # British COMPOUNDS, listed one by one rather than by unanchoring the stems
    # above. Dropping \b from "oesophag" or "oedema" looks tempting but corrupts
    # correct American words that contain those letters across a morpheme seam —
    # gastr(o)+esophageal, angi(o)+edema — turning them into "gastresophageal"
    # and "angiedema". Each entry here is a form with no such collision.
    (r"\btransoesophag", "transesophag"), (r"\blymphoedema", "lymphedema"),
    (r"\bpapilloedema", "papilledema"), (r"\bileocaec", "ileocec"),
    (r"\bmethaemoglobin", "methemoglobin"), (r"\bdiscolour", "discolor"),
    # -re/-ce/-ise families. NOT a blanket "-ise -> -ize" rule: excise, incise,
    # revise, supervise, compromise and expertise are all correct with -ise, and
    # several are surgical. Each verb stem is listed, and every -is stem carries
    # the (e|es|ed|ing|ation) suffix guard: a bare stem also matches the NOUN it
    # shares letters with — characteristic, optimism, generalist, embolism — all
    # correct American words a naive rule would mangle.
    (r"theatre", "theater"), (r"litre", "liter"), (r"metre", "meter"),
    (r"\bgrey(?! turner)", "gray"),
    (r"\bpractis", "practic"), (r"\blicence", "license"), (r"\bdefence", "defense"),
    (r"hospitalis(e|es|ed|ing|ation|ations)", "hospitaliz\\1"), (r"randomis(e|es|ed|ing|ation|ations)", "randomiz\\1"), (r"minimis(e|es|ed|ing|ation|ations)", "minimiz\\1"),
    (r"maximis(e|es|ed|ing|ation|ations)", "maximiz\\1"), (r"optimis(e|es|ed|ing|ation|ations)", "optimiz\\1"), (r"characteris(e|es|ed|ing|ation|ations)", "characteriz\\1"),
    (r"standardis(e|es|ed|ing|ation|ations)", "standardiz\\1"), (r"utilis(e|es|ed|ing|ation|ations)", "utiliz\\1"), (r"immunis(e|es|ed|ing|ation|ations)", "immuniz\\1"),
    (r"sterilis(e|es|ed|ing|ation|ations)", "steriliz\\1"), (r"localis(e|es|ed|ing|ation|ations)", "localiz\\1"), (r"generalis(e|es|ed|ing|ation|ations)", "generaliz\\1"),
    (r"neutralis(e|es|ed|ing|ation|ations)", "neutraliz\\1"), (r"pressuris(e|es|ed|ing|ation|ations)", "pressuriz\\1"), (r"oxygenis(e|es|ed|ing|ation|ations)", "oxygeniz\\1"),
]


def british_hits(text):
    """[(matched_text, american_form)] for every British spelling in `text`."""
    out = []
    for pat, repl in BRITISH:
        for m in re.finditer(pat, text or "", re.I):
            found = m.group(0)
            # Resolve the replacement against the matched text so backreferences
            # expand: "organisation" -> "organization", not the bare stem
            # "organiz". The emitted edits are applied verbatim, so a truncated
            # replacement would silently eat the rest of the word.
            fixed = re.sub(pat, repl, found, flags=re.I)
            # Preserve the matched capitalisation: "Haemo" -> "Hemo", not "hemo".
            if found[:1].isupper():
                fixed = fixed[:1].upper() + fixed[1:]
            if (found, fixed) not in out:
                out.append((found, fixed))
    return out


def correct_text(text):
    """`text` with every British spelling rewritten, matched case preserved.

    This is the AUTHORITATIVE correction. british_hits() reports fragments, and a
    fragment applied with str.replace is not always equivalent: a cell holding
    both "oedema" and "angioedema" flags the first (correctly) but a blunt
    "oedema"->"edema" swap also mangles the second into "angiedema". Callers that
    emit edits must compare a naive substring swap against this and fall back to
    a whole-cell edit when they disagree.
    """
    out = text or ""
    for pat, repl in BRITISH:
        def _sub(m, _p=pat, _r=repl):
            fixed = re.sub(_p, _r, m.group(0), flags=re.I)
            return fixed[:1].upper() + fixed[1:] if m.group(0)[:1].isupper() else fixed
        out = re.sub(pat, _sub, out, flags=re.I)
    return out
