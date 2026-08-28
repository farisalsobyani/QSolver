#!/usr/bin/env bash
# Install the nawat-solver skill into ~/.claude/skills/ (or $CLAUDE_SKILLS_DIR).
#
# Symlinks the skill tree, so `git pull` updates the installed skill with no
# reinstall — and so a prompt you tweak is a tweak to the checkout, where git
# can show it to you. Also points the skill at this checkout's corpus via
# NAWAT_CORPUS, printed below for your shell profile.
#
# The link breaks if you move or delete this checkout; re-run to repair it.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
SRC="$REPO/skills/nawat-solver"
LINK="$DEST/nawat-solver"

[ -f "$SRC/SKILL.md" ] || { echo "no skill at $SRC — wrong checkout?" >&2; exit 1; }

mkdir -p "$DEST"
if [ -L "$LINK" ]; then
    # A symlink: replacing it touches the link only, never the target.
    rm "$LINK"
elif [ -e "$LINK" ]; then
    # A real directory — an older copy-install, or someone's own edits. Say so
    # and keep it rather than deleting work this script did not create.
    BAK="$LINK.replaced-$(date +%Y%m%d%H%M%S)"
    mv "$LINK" "$BAK"
    echo "moved aside  $BAK"
    echo "             (previous non-symlink install — delete it once you have"
    echo "              checked it holds nothing you want to keep)"
fi
ln -s "$SRC" "$LINK"

echo "linked     $LINK -> $SRC"

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
    print("\nNo book is searchable yet. Point this at your PDFs:")
    print(f"  {corpus.parent}/tools/add_book.py ~/wherever/your/textbooks/are")
    print("It identifies each book by page count and supplies the exact title,")
    print("edition and year the citations and the shipped maps depend on.")
PY

cat <<EOF

Add this to your shell profile so the skill finds the library:

  export NAWAT_CORPUS="$REPO/corpus"

Missing dependency? pip install pymupdf rapidfuzz
EOF
