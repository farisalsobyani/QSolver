# --- VENDORED COPY - DO NOT EDIT ------------------------------------
# source : .claude/skills/question-review/scripts/check_sourcing.py   (sawab repo - the source of truth)
# sha256 : 6e373bebe6241251daeaf9ebe93bfe7ef83f0cbaeebc8a801f51c7b555ead5c9
# synced : 2026-08-28 by tools/sync_from_sawab.py
# Edit the sawab original, not this file. `sync_from_sawab.py --check`
# fails when the two have drifted apart.
# --------------------------------------------------------------------

#!/usr/bin/env python3
"""Guard: is every precise number in an explanation actually sourced?

    check_sourcing.py --all EXPORT.csv          # sweep the bank
    check_sourcing.py --csv V2.csv              # a built v2 CSV
    check_sourcing.py --all EXPORT.csv --verify # also query the textbook index

Charter rule 2 stops an AUDITOR introducing a precise number. It says nothing
about the numbers already sitting in the bank's explanations, and those are the
ones a student memorises. A value in Why / Reasons Wrong / Take-Home that appears
nowhere in the stem, nowhere in the choices, and nowhere in the question's own
cited passages is unsourced: nothing in the question supports it.

Three tiers, because they need different work:

- SOURCED    — the number appears in the question's Cited Passages. Nothing to do.
- ECHOED     — it appears in the stem or a choice. The explanation is restating
               the vignette, which is fine.
- UNSOURCED  — it appears in none of them. Retrieve support from the textbook
               index and cite it, or drop the number for a qualitative
               descriptor. `--verify` runs the retrieval for you.

Bare years, list ordinals and small counts are ignored: "the 1990s", "step 2",
"3 doses" carry no clinical claim. Only values with a clinical unit, or a
percentage, count.
"""
import argparse, csv, json, pathlib, re, subprocess, sys

from qr_common import csv_cell

csv.field_size_limit(10 ** 9)
EXPLANATION_FIELDS = ["Why", "Reasons Wrong Answers Are Wrong", "Take-Home Message", "Concept"]
CONTEXT_FIELDS = ["Reformatted Question", "Choice A", "Choice B", "Choice C", "Choice D", "Choice E"]

# A number is a claim only when it carries a clinical unit or is a percentage.
UNIT = (r"%|mg/dL|g/dL|mg/kg|mcg|µg|mg|mL/kg|mL|L/min|L|mEq/L|mEq|mmol/L|mmol|mOsm|"
        r"U/L|IU|ng/mL|pg/mL|cm|mm Hg|mmHg|mm|°C|°F|kg|hours|hour|days|day|weeks|week|"
        r"months|month|years|year|minutes|min|Gy|Fr")
NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(" + UNIT + r")\b")
YEARISH = re.compile(r"^(19|20)\d{2}$")


def norm(v):
    return ("" if v is None else str(v)).replace("\r\n", "\n").replace("\r", "\n").strip()


def numbers_in(text):
    """{normalised value: surface form} for every unit-bearing number."""
    out = {}
    for m in NUMBER.finditer(text or ""):
        raw = m.group(1).replace(",", "")
        if YEARISH.match(raw):
            continue
        try:
            val = float(raw)
        except ValueError:
            continue
        if val <= 1:                     # "1 dose", "0.5 mg" carry little claim
            continue
        out.setdefault(raw.rstrip("0").rstrip(".") or raw, m.group(0).strip())
    return out


def bare_numbers(text):
    """Every number anywhere, unit or not — used to test whether support exists."""
    return {n.replace(",", "").rstrip("0").rstrip(".") or n.replace(",", "")
            for n in re.findall(r"(?<![\w.])(\d{1,3}(?:,\d{3})*(?:\.\d+)?)", text or "")}


def sentence_around(text, surface):
    """The sentence the figure sits in — a bare number retrieves nothing.

    Searching the index for "6 hours" scores -4.65, pure noise. The claim it sits
    inside ("antibiotics within 6 hours of injury") is what can actually be
    supported or refuted, so that is what gets retrieved.
    """
    for sent in re.split(r"(?<=[.;])\s+", text or ""):
        if surface in sent:
            return re.sub(r"^[A-Ea-e]:\s*", "", sent).strip()[:220]
    return surface


def audit_row(row):
    ctx = bare_numbers(" ".join(norm(row.get(c)) for c in CONTEXT_FIELDS))
    cited = bare_numbers(csv_cell(row, "Cited Passages"))
    findings = []
    for fld in EXPLANATION_FIELDS:
        for val, surface in numbers_in(norm(row.get(fld))).items():
            tier = "sourced" if val in cited else "echoed" if val in ctx else "unsourced"
            findings.append({"field": fld, "value": surface, "tier": tier,
                             "claim": sentence_around(norm(row.get(fld)), surface)})
    return findings


def verify(claim, figure, skill_dir):
    """Retrieve the claim, then check whether the FIGURE is in what came back.

    A long clinical sentence retrieves strongly on topic alone — that only proves
    the subject is discussed, not that the cutoff is 6 hours. So the verdict turns
    on whether the number itself appears in the retrieved snippet. Anything else
    is "topic found, figure unconfirmed", which is a lead for an auditor to read,
    never a pass.
    """
    q = re.sub(r"\s+", " ", claim)[:180]
    digits = re.sub(r"[^0-9.]", "", figure).rstrip(".") or figure
    try:
        out = subprocess.run([sys.executable, str(skill_dir / "scripts" / "search_textbooks.py"),
                              "--limit", "5", q], capture_output=True, text=True, timeout=60)
        hits = json.loads(out.stdout or "[]")
    except Exception as e:
        return {"error": str(e)}
    if not hits:
        return {"verdict": "nothing retrieved"}
    with_fig = [h for h in hits if digits and digits in re.sub(r",", "", h.get("snippet", ""))]
    top = (with_fig or hits)[0]
    # Report the PRINTED folio: this line is a lead for a human to go and read,
    # and the PDF page runs 20-45 sheets off it in the print facsimiles.
    return {"book": top.get("book"), "page": top.get("page"), "folio": top.get("folio"),
            "score": min(h.get("score", 0) for h in hits),
            "verdict": "figure present in source" if with_fig else "topic found, figure UNCONFIRMED"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", dest="export"); ap.add_argument("--csv")
    ap.add_argument("--verify", action="store_true",
                    help="run each unsourced figure against the textbook index")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    path = args.export or args.csv
    if not path:
        ap.error("pass --all EXPORT.csv or --csv V2.csv")
    skill_dir = pathlib.Path(__file__).resolve().parent.parent

    tiers, flagged = {"sourced": 0, "echoed": 0, "unsourced": 0}, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            fs = audit_row(row)
            for f in fs:
                tiers[f["tier"]] += 1
            bad = [f for f in fs if f["tier"] == "unsourced"]
            if bad:
                flagged.append({"qid": norm(row.get("ID"))[:8], "unsourced": bad})

    print(json.dumps({
        "questions_with_unsourced_numbers": len(flagged),
        "figures_by_tier": tiers,
    }, indent=1))

    for f in flagged[: args.limit]:
        vals = ", ".join(f"{b['value']} ({b['field']})" for b in f["unsourced"][:3])
        line = f"  {f['qid']}  {vals}"
        if args.verify:
            b = f["unsourced"][0]
            v = verify(b.get("claim") or b["value"], b["value"], skill_dir)
            line += f"   -> {v.get('verdict')}"
            if v.get("book"):
                page = v.get("folio") or f"pdf#{v['page']}"
                line += f" ({v['book']} p.{page})"
        print(line)
    if len(flagged) > args.limit:
        print(f"  … {len(flagged)-args.limit} more")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
