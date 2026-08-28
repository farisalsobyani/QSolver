#!/usr/bin/env bash
# Install the nawat-solver skill into ~/.claude/skills/ (or $CLAUDE_SKILLS_DIR).
#
# Copies the skill tree, then points it at this checkout's corpus by exporting
# NAWAT_CORPUS for you to add to your shell profile. Re-run after a git pull to
# pick up updated maps and prompts; it overwrites the installed copy.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
SRC="$REPO/skills/nawat-solver"

[ -f "$SRC/SKILL.md" ] || { echo "no skill at $SRC — wrong checkout?" >&2; exit 1; }

mkdir -p "$DEST"
rm -rf "$DEST/nawat-solver"
cp -R "$SRC" "$DEST/nawat-solver"

echo "installed  $DEST/nawat-solver"

python3 - "$REPO/corpus" <<'PY'
import json, pathlib, sys
corpus = pathlib.Path(sys.argv[1])
lib = json.loads((corpus / 'library.json').read_text(encoding='utf-8'))['books']
ready = [b for b in lib if (corpus / b / 'pages').is_dir()
         and (corpus / b / 'fts.sqlite').exists()]
print(f"corpus     {corpus}")
print(f"books      {len(ready)} of {len(lib)} indexed"
      + (f": {', '.join(ready)}" if ready else " — none yet"))
if not ready:
    print("\nNo book is searchable yet. Index one you own:")
    print("  python3 scripts/index_textbook.py <your.pdf> --book-id <id> \\")
    print("      --title <exact title from library.json> --edition ... --year ... \\")
    print(f"      --corpus {corpus}")
    print("The id/title/edition must match library.json so the shipped maps line up.")
PY

cat <<EOF

Add this to your shell profile so the skill finds the library:

  export NAWAT_CORPUS="$REPO/corpus"

Missing dependency? pip install pymupdf rapidfuzz
EOF
