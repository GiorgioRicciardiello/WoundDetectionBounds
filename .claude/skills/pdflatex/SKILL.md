---
name: pdflatex
description: Use pdflatex to compile LaTeX documents into PDFs on Windows (MiKTeX or TeX Live). Use when generating academic papers, research publications, or any documents written in LaTeX.
triggers:
- pdflatex
---

# pdflatex — Windows LaTeX Compilation

## Installed distributions on this machine

| Distribution | Executable |
|---|---|
| MiKTeX 25.12 (preferred) | `C:\Users\riccig01\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe` |
| TeX Live 2026 (fallback)  | `C:\texlive\2026\bin\windows\pdflatex.exe` |

Use **MiKTeX** by default — it auto-installs missing packages on first run.
Fall back to **TeX Live** only if MiKTeX fails.

## Compilation procedure

A LaTeX document with citations requires **four passes** to resolve all cross-references and build the bibliography:

```
cd <directory containing main.tex>

pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

Always `cd` into the document directory first so relative `\input{}`, `\includegraphics{}`, and `\bibliography{}` paths resolve correctly.

## How to run on this machine

Use the full path to the executable via Bash:

```bash
PDFLATEX="C:/Users/riccig01/AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe"
BIBTEX="C:/Users/riccig01/AppData/Local/Programs/MiKTeX/miktex/bin/x64/bibtex.exe"
DOC_DIR="<absolute path to folder containing main.tex>"
MAIN="main"   # filename without .tex

cd "$DOC_DIR"
"$PDFLATEX" -interaction=nonstopmode "$MAIN.tex"
"$BIBTEX"   "$MAIN"
"$PDFLATEX" -interaction=nonstopmode "$MAIN.tex"
"$PDFLATEX" -interaction=nonstopmode "$MAIN.tex"
```

## Checking the output

After compilation look for:
- `main.pdf`  — the compiled document
- `main.log`  — full compiler log (check for errors)
- `main.blg`  — BibTeX log (check for missing references)

Parse the log for errors:

```bash
grep -E "^!" "$DOC_DIR/main.log" | head -20          # fatal errors
grep -iE "warning|undefined|missing" "$DOC_DIR/main.log" | head -30  # warnings
```

## Common errors and fixes

| Error message | Cause | Fix |
|---|---|---|
| `! LaTeX Error: File '*.sty' not found` | Missing package | MiKTeX auto-installs; for TeX Live run `tlmgr install <pkg>` |
| `! Undefined control sequence` | Typo or missing `\usepackage` | Check the `.log` for line number and fix the `.tex` |
| `Overfull \hbox` | Line too wide | Warning only — PDF still builds |
| `Citation 'X' undefined` | BibTeX not run or key mismatch | Run full 4-pass sequence |
| `Label(s) may have changed` | Cross-references changed | Run `pdflatex` one more time |

## TeX Live fallback

If MiKTeX fails, substitute the TeX Live path:

```bash
PDFLATEX="C:/texlive/2026/bin/windows/pdflatex.exe"
BIBTEX="C:/texlive/2026/bin/windows/bibtex.exe"
```