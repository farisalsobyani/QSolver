# --- VENDORED COPY - DO NOT EDIT ------------------------------------
# source : .claude/skills/question-review/scripts/check_term_consistency.py   (sawab repo - the source of truth)
# sha256 : 0e4d55fd509fd9367b04bb3f151851275019866f5f85afc7f6183b74b9be7c6b
# synced : 2026-08-28 by tools/sync_from_sawab.py
# Edit the sawab original, not this file. `sync_from_sawab.py --check`
# fails when the two have drifted apart.
# --------------------------------------------------------------------

#!/usr/bin/env python3
"""Guard: is one clinical entity written the same way everywhere in the bank?

    check_term_consistency.py --all EXPORT.csv [--overlay V2.csv]
    check_term_consistency.py --all EXPORT.csv --json families.json

Finds a choice written several ways across DIFFERENT questions — the general form
of the ECG/EKG, NG/NGT and Ringer's-lactate splits fixed by hand. Variants are
grouped into families by connected component, not pairs, because the drift runs
deeper than two: the duodenal parts appear as `1st part of duodenum`,
`1st part of the duodenum` and `First part of duodenum` at once.

Four kinds of look-alike are deliberately NOT drift, each verified against the
real bank before being excluded:

- case-only differences — already the Title Case rule's job.
- two options of the SAME question — `10 mEq/hr` beside `20 mEq/hr` is a numeric
  option family, which is correct design.
- strings differing only in their numbers — same reason, across questions.
- a shared taxonomy — `Cardiogenic / Hemorrhagic / Neurogenic / Septic shock`
  reused across vignettes with different keys is one classification tested three
  ways, not duplication.

It NOMINATES; it never asserts. `Axillary lymph nodes` and `Maxillary lymph node`
score 0.90 similar and are different structures, so a human picks the canonical
form. The proposal is the most frequent variant, tie-broken toward the house
style: sentence case, American spelling, and the abbreviation ruling.
"""
import argparse, collections, csv, difflib, itertools, json, pathlib, re, sys

from qr_common import british_hits

csv.field_size_limit(10 ** 9)
SLOTS = "ABCDE"
SIMILAR = 0.90


def norm(v):
    return ("" if v is None else str(v)).replace("\r\n", "\n").replace("\r", "\n").strip()


def canon(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def skeleton(s):
    """Canonical form with every number blanked — two strings that differ only in
    their figures are a numeric option family, not a wording split."""
    return re.sub(r"\d+(?:\.\d+)?", "#", canon(s))


def load_exceptions():
    """Families the operator has ruled must stay apart.

    Without this the checker re-nominates the same rejected family on every run,
    which trains the reader to skim past it — the opposite of what a guard is for.
    """
    p = pathlib.Path(__file__).resolve().parent.parent / "reference" / "term_exceptions.json"
    if not p.is_file():
        return []
    return [frozenset(canon(v) for v in e["variants"])
            for e in json.loads(p.read_text()).get("keep_distinct", [])]


def load_policy():
    p = pathlib.Path(__file__).resolve().parent.parent / "reference" / "abbreviations.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text())


def house_score(text, policy):
    """Higher is closer to the house style — used only to break a frequency tie."""
    s = 0
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+", text):     # Title Case
        s -= 2
    if british_hits(text):                                   # British spelling
        s -= 2
    if policy:
        for tok in re.findall(r"\b[A-Z][A-Za-z]*[A-Z][A-Za-z0-9]*\b", text):
            if tok in policy.get("expand", {}):
                s -= 2                                        # a banned abbreviation
            elif tok in policy.get("bare", []):
                s += 1
    if text[:1].isupper():
        s += 1
    return s


ORDINAL = re.compile(r"^(\d+(st|nd|rd|th)|first|second|third|fourth|fifth)$")

# Words whose swap REVERSES the clinical meaning. "Decreased cardiac output" and
# "Increased cardiac output" are 0.92 similar and are opposites — a wording rule
# that merged them would be worse than the drift it fixes.
POLARITY = [("increased", "decreased"), ("increase", "decrease"), ("high", "low"),
            ("hyper", "hypo"), ("with", "without"), ("pre", "post"),
            ("proximal", "distal"), ("left", "right"), ("acute", "chronic"),
            ("before", "after"), ("more", "less"), ("early", "late"),
            ("elevated", "reduced"), ("positive", "negative"), ("open", "closed"),
            ("above", "below"), ("upper", "lower"), ("primary", "secondary"),
            ("benign", "malignant"), ("partial", "complete"), ("never", "always")]


def reverses_meaning(a, b):
    ca, cb = " " + canon(a) + " ", " " + canon(b) + " "
    for x, y in POLARITY:
        if (f" {x} " in ca and f" {y} " in cb) or (f" {y} " in ca and f" {x} " in cb):
            return True
        if ca.replace(x, y) == cb or cb.replace(x, y) == ca:   # hyper/hypo inside a word
            return True
    return False


def distinct_entities(a, b):
    """True when the two strings differ by a token that DISCRIMINATES.

    High string similarity is not sameness. "2nd part of duodenum" and "3rd part
    of the duodenum" are 0.93 similar and are different anatomy; so are Vitamin
    B12, D and K deficiency. The tell is that the differing token is an ordinal,
    carries a digit, or is a lone letter — those name which one, so a wording
    rule must never merge them.
    """
    ta, tb = canon(a).split(), canon(b).split()
    diff = set(ta) ^ set(tb)
    return any(ORDINAL.match(t) or re.search(r"\d", t) or len(t) == 1 for t in diff)


def families(strings, owners):
    """Connected components over the >=SIMILAR graph."""
    parent = {s: s for s in strings}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    buckets = collections.defaultdict(list)
    for s in strings:
        buckets[len(s) // 12].append(s)
    for k in list(buckets):
        pool = sorted(set(buckets[k] + buckets.get(k + 1, [])))
        for a, b in itertools.combinations(pool, 2):
            if abs(len(a) - len(b)) > 12 or canon(a) == canon(b):
                continue
            if owners[a] & owners[b]:                 # same question -> option family
                continue
            # Similarity FIRST, cheapest form first. The guards below are far more
            # expensive per pair than the ratio, and almost every pair fails the
            # ratio — running them first made a full-bank sweep take over five
            # minutes. real_quick_ratio and quick_ratio are upper bounds, so a
            # pair they reject cannot pass the real one.
            ca, cb = canon(a), canon(b)
            m = difflib.SequenceMatcher(None, ca, cb)
            if m.real_quick_ratio() < SIMILAR or m.quick_ratio() < SIMILAR:
                continue
            if m.ratio() < SIMILAR:
                continue
            if skeleton(a) == skeleton(b):            # differs only by its numbers
                continue
            if distinct_entities(a, b):               # differs by a discriminator
                continue
            if reverses_meaning(a, b):                # opposites, not variants
                continue
            union(a, b)
    out = collections.defaultdict(list)
    for s in strings:
        out[find(s)].append(s)
    return [v for v in out.values() if len(v) > 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", dest="export", required=True)
    ap.add_argument("--overlay", help="a v2 CSV whose edits are pending import")
    ap.add_argument("--json", help="write the families here")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    with open(args.export, newline="", encoding="utf-8-sig") as fh:
        rows = {norm(r["ID"]): r for r in csv.DictReader(fh)}
    if args.overlay:
        with open(args.overlay, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                qid = norm(r["ID"])
                if qid in rows:
                    for L in SLOTS:
                        rows[qid][f"Choice {L}"] = r[f"Choice {L}"]

    owners, count = collections.defaultdict(set), collections.Counter()
    where = collections.defaultdict(list)     # variant -> every place it is used
    for qid, r in rows.items():
        key = norm(r.get("Correct Answer")).upper()[:1]
        for L in SLOTS:
            t = norm(r.get(f"Choice {L}"))
            if t:
                owners[t].add(qid[:8])
                count[t] += 1
                where[t].append({
                    "question_id": qid, "qid": qid[:8], "slot": L, "is_key": L == key,
                    "stem": re.sub(r"\s+", " ", norm(r.get("Reformatted Question")))[:190],
                    "siblings": {M: norm(r.get(f"Choice {M}")) for M in SLOTS
                                 if norm(r.get(f"Choice {M}"))},
                })

    policy, exceptions = load_policy(), load_exceptions()
    fams = [f for f in families(sorted(owners), owners)
            if not any(ex <= {canon(v) for v in f} for ex in exceptions)]
    fams.sort(key=lambda f: -sum(count[v] for v in f))

    report = []
    for fam in fams:
        ranked = sorted(fam, key=lambda v: (-count[v], -house_score(v, policy), len(v)))
        report.append({
            "proposed": ranked[0],
            "variants": [{"text": v, "uses": count[v], "questions": sorted(owners[v]),
                          "occurrences": where[v]} for v in ranked],
        })

    print(json.dumps({"families": len(report),
                      "strings_involved": sum(len(f["variants"]) for f in report),
                      "uses_involved": sum(sum(v["uses"] for v in f["variants"]) for f in report)},
                     indent=1))
    for f in report[: args.limit]:
        print(f"\n  → {f['proposed']!r}")
        for v in f["variants"][1:]:
            print(f"      {v['text']!r}  ×{v['uses']}  [{','.join(v['questions'][:3])}]")
    if len(report) > args.limit:
        print(f"\n  … {len(report)-args.limit} more families")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(report, indent=1, ensure_ascii=False))
        print(f"\nwrote {args.json}")
    sys.exit(1 if report else 0)


if __name__ == "__main__":
    main()
