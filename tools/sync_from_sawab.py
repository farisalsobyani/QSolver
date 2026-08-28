#!/usr/bin/env python3
"""Re-copy the question-review checkers from the sawab repo into vendor/, and
detect when this public copy has drifted from that original.

WHY THIS EXISTS
The nawat-solver skill's own doctrine is that a rule living in two places with
nothing comparing them WILL diverge silently — the uploaded copy three weeks
behind, two folio writers disagreeing, a third spelling table. Publishing the
checkers here creates exactly that second home. This script is the thing that
compares them, so drift is loud instead of silent.

The sawab repo stays the source of truth. Never edit a file under
vendor/question-review/ — edit the sawab original and re-run this script.

USAGE
  export SAWAB_REPO=~/Downloads/sawab-main

  tools/sync_from_sawab.py            # re-copy + stamp + rewrite PROVENANCE.json
  tools/sync_from_sawab.py --check    # compare only; exit 1 on any drift

--check reports three kinds of drift:
  UPSTREAM  the sawab original changed since the last sync   -> re-run the sync
  LOCAL     the vendored copy was hand-edited here           -> re-run the sync
  MISSING   the sawab checkout has no such file              -> wrong SAWAB_REPO?

It is safe to run --check without SAWAB_REPO set: it then verifies only that
the vendored copies still match the hashes recorded in PROVENANCE.json (LOCAL
drift), and says that the upstream comparison was skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VENDOR = REPO / 'skills' / 'nawat-solver' / 'vendor' / 'question-review'
MANIFEST = VENDOR / 'PROVENANCE.json'

SKILL_REL = '.claude/skills/question-review'

# vendored path (relative to VENDOR)  ->  path in the sawab repo
FILES = {
    'scripts/check_choice_style.py':     f'{SKILL_REL}/scripts/check_choice_style.py',
    'scripts/check_prose_style.py':      f'{SKILL_REL}/scripts/check_prose_style.py',
    'scripts/check_sourcing.py':         f'{SKILL_REL}/scripts/check_sourcing.py',
    'scripts/check_term_consistency.py': f'{SKILL_REL}/scripts/check_term_consistency.py',
    'scripts/qr_common.py':              f'{SKILL_REL}/scripts/qr_common.py',
    'reference/abbreviations.json':      f'{SKILL_REL}/reference/abbreviations.json',
    'reference/term_exceptions.json':    f'{SKILL_REL}/reference/term_exceptions.json',
}

BEGIN = '# --- VENDORED COPY - DO NOT EDIT ------------------------------------'
END = '# --------------------------------------------------------------------'


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def stamp(rel: str, src_rel: str, digest: str) -> str:
    """The provenance header prepended to vendored .py files.

    Comments are not statements, so this never displaces the module docstring.
    JSON cannot carry comments — those files are covered by PROVENANCE.json only.
    """
    return '\n'.join([
        BEGIN,
        f'# source : {src_rel}   (sawab repo - the source of truth)',
        f'# sha256 : {digest}',
        f'# synced : {date.today().isoformat()} by tools/sync_from_sawab.py',
        '# Edit the sawab original, not this file. `sync_from_sawab.py --check`',
        '# fails when the two have drifted apart.',
        END,
        '',
        '',
    ])


def strip_stamp(text: str) -> str:
    """Return the file as it exists upstream, with any stamp block removed."""
    if not text.startswith(BEGIN):
        return text
    end = text.find(END)
    if end == -1:
        return text
    # The stamp ends with END followed by exactly the two newlines its trailing
    # blank entries produce; upstream content resumes after those. Remove that
    # many and no more, so a file that genuinely starts with a blank line
    # round-trips byte for byte.
    rest = text[end + len(END):]
    for _ in range(2):
        if rest.startswith('\n'):
            rest = rest[1:]
    return rest


def sawab_root() -> Path | None:
    env = os.environ.get('SAWAB_REPO')
    if not env:
        return None
    root = Path(env).expanduser().resolve()
    return root if (root / SKILL_REL).is_dir() else None


def read_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    return {'files': {}}


def do_sync(root: Path) -> int:
    recorded, changed = {}, []
    for rel, src_rel in FILES.items():
        src = root / src_rel
        if not src.is_file():
            print(f'MISSING  {src_rel} - not in {root}', file=sys.stderr)
            return 2
        upstream = src.read_text(encoding='utf-8')
        digest = sha256(upstream)
        dest = VENDOR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        before = strip_stamp(dest.read_text(encoding='utf-8')) if dest.exists() else None
        body = (stamp(rel, src_rel, digest) + upstream) if rel.endswith('.py') else upstream
        dest.write_text(body, encoding='utf-8')
        recorded[rel] = {'source': src_rel, 'sha256': digest,
                         'stamped': rel.endswith('.py')}
        if before != upstream:
            changed.append(rel)

    MANIFEST.write_text(json.dumps({
        'note': ('Vendored from the sawab repo. That repo is the source of truth; '
                 'these copies exist so the public skill can run its export checks '
                 'without it. Re-sync with tools/sync_from_sawab.py.'),
        'source_repo': 'farisalsobyani/sawab',
        'source_skill': SKILL_REL,
        'synced': date.today().isoformat(),
        'files': recorded,
    }, indent=2) + '\n', encoding='utf-8')

    print(f'synced {len(FILES)} files from {root}')
    for rel in changed:
        print(f'  updated  {rel}')
    if not changed:
        print('  (all already current)')
    print(f'wrote {MANIFEST.relative_to(REPO)}')
    return 0


def do_check(root: Path | None) -> int:
    man = read_manifest().get('files', {})
    if not man:
        print('no PROVENANCE.json - run the sync first', file=sys.stderr)
        return 2

    drift = []
    for rel, rec in man.items():
        dest = VENDOR / rel
        if not dest.exists():
            drift.append(('LOCAL', rel, 'vendored copy is missing'))
            continue
        local = strip_stamp(dest.read_text(encoding='utf-8'))
        if sha256(local) != rec['sha256']:
            drift.append(('LOCAL', rel, 'vendored copy was edited here'))
        if root is not None:
            src = root / rec['source']
            if not src.is_file():
                drift.append(('MISSING', rel, f'not found at {rec["source"]}'))
            elif sha256(src.read_text(encoding='utf-8')) != rec['sha256']:
                drift.append(('UPSTREAM', rel, 'sawab original has changed'))

    if root is None:
        print('SAWAB_REPO not set - upstream comparison skipped, '
              'local integrity only')

    if not drift:
        scope = 'in sync with sawab' if root else 'locally intact'
        print(f'{len(man)} vendored files {scope} '
              f'(last sync {read_manifest().get("synced", "?")})')
        return 0

    for kind, rel, why in drift:
        print(f'{kind:9} {rel}  - {why}', file=sys.stderr)
    print(f'\n{len(drift)} drifted - re-run: tools/sync_from_sawab.py',
          file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true',
                    help='compare only, change nothing; exit 1 on drift')
    args = ap.parse_args()

    root = sawab_root()
    if args.check:
        return do_check(root)
    if root is None:
        print('set SAWAB_REPO to a sawab checkout that contains '
              f'{SKILL_REL}/ (got: {os.environ.get("SAWAB_REPO") or "unset"})',
              file=sys.stderr)
        return 2
    return do_sync(root)


if __name__ == '__main__':
    raise SystemExit(main())
