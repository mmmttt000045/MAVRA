# MAVRA Manuscript (PVLDB Vol. 20 / VLDB 2027)

`main.tex` is the single compilation entry point (`acmart` `sigconf` + `pvldb.sty`, compiled with `pdfLaTeX`). Inline Chinese translations in `\bi{English}{Chinese}`, `\bt`, `\bh`, `\bhl`, and `\bid` are author-facing reading aids only and are never typeset.

## Build

```bash
bash build.sh en     # compiles build/main.pdf via latexmk (or tectonic)
bash build.sh pack   # bundles the exact dependency closure into build/mavra-pvldb.zip
```

## Layout

- `main.tex`, `paper.tex`, `preamble.tex` — PVLDB Vol. 20 entry, top matter, and shared macros
- `acmart.cls`, `pvldb.sty`, `ACM-Reference-Format.bst` — pinned official PVLDB template files
- `sections/` — `abstract`, `01-introduction` .. `06-conclusion`, and `implementation`
- `figures/` — figure wrappers (`.tex`) and vector graphics (`.pdf`)
- `tables/` — tabular environments included by the manuscript
- `algorithms/` — pseudocode blocks (`maintenance.tex`)
- `gen/` — script-generated numerical macros backing the tables and prose
- `references.bib` — BibTeX bibliography

## Standalone Paper Repository Sync

`overleaf/` is the single source of truth; `https://github.com/mmmttt000045/icde-2027-paper` (`main`) mirrors its compilation closure for Overleaf GitHub integration:

```bash
python3 tools/sync-paper-repo.py --repo <clone>                  # dry run
python3 tools/sync-paper-repo.py --repo <clone> --apply --push   # sync, commit, push, and record
```
