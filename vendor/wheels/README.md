# pdf-inspector wheels

`index_textbook.py` prefers [pdf-inspector](https://github.com/firecrawl/pdf-inspector)
over PyMuPDF for extraction: multi-column reading order, markdown heading
structure that feeds `map.md`, and OCR routing that detects broken encodings a
text-length heuristic misses. Without it the indexer falls back to PyMuPDF
silently — the run still succeeds, and the page text is simply worse.

**Every book in this corpus was extracted with it** (`meta.json:extractor`).
Indexing a new book without it therefore leaves you with a mixed corpus:
different reading order, no heading structure, in a library whose `map.md` and
`concept-index.md` were written against the better extraction. The mismatch is
invisible once it is in — check `extractor` in a book's `meta.json` if you are
unsure what built it.

You do NOT need this to USE the corpus that ships here, or to `--rebuild-fts`;
only to index something new.

## Offline install

Wheels for macOS (arm64, x86_64), Linux (x86_64, aarch64) and Windows (x64) are
here so a machine with no network can install. pip picks the one matching the
platform:

    pip install --no-index --find-links vendor/wheels pdf-inspector

With network, `pip install pdf-inspector` is equivalent.

## Provenance

pdf-inspector 1.17.0, downloaded from PyPI, unmodified. MIT licensed; each
wheel carries its own LICENSE under `*.dist-info/licenses/`. It has no
dependencies of its own — these five files are the whole install.
