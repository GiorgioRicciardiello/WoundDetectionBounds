# Diagnostic Checklist — Zero `??` Verification

Run this checklist after generating all `.tex` files and before delivering the project. Every item MUST pass. If any item fails, fix the issue before proceeding.

---

## 1. File Existence Checks

### 1a. Figures

For every `\includegraphics{filename}` in any `.tex` file:
- Confirm `figures/filename` exists in the output directory
- If missing: either the figure was not copied (fix Step 3) or the filename is misspelled

```bash
grep -roh '\\includegraphics\[.*\]{[^}]*}' sections/ | \
  sed 's/.*{\(.*\)}/\1/' | sort -u | \
  while read f; do
    [ -f "figures/$f" ] && echo "OK: $f" || echo "FAIL: $f"
  done
```

### 1b. Table Inputs

For every `\input{tables/...}` in any `.tex` file:
- Confirm the `.tex` file exists in `tables/`

```bash
grep -roh '\\input{tables/[^}]*}' sections/ | \
  sed 's/\\input{\(.*\)}/\1.tex/' | sort -u | \
  while read f; do
    [ -f "$f" ] && echo "OK: $f" || echo "FAIL: $f"
  done
```

### 1c. Section Inputs

For every `\input{sections/...}` in `main.tex`:
- Confirm the `.tex` file exists in `sections/`

```bash
grep -oh '\\input{sections/[^}]*}' main.tex | \
  sed 's/\\input{\(.*\)}/\1.tex/' | \
  while read f; do
    [ -f "$f" ] && echo "OK: $f" || echo "FAIL: $f"
  done
```

---

## 2. Cross-Reference Integrity

### 2a. Orphan Labels (label without ref)

Extract all `\label{X}` and all `\ref{X}`. Every label (except subfigure labels) should have a matching ref.

```bash
# All labels
grep -roh '\\label{[^}]*}' sections/ tables/ | \
  sed 's/.*{\(.*\)}/\1/' | sort -u > /tmp/labels.txt

# All refs
grep -roh '\\ref{[^}]*}' sections/ | \
  sed 's/.*{\(.*\)}/\1/' | sort -u > /tmp/refs.txt

# Labels without refs (potential orphans)
echo "=== Orphan labels (no matching ref) ==="
comm -23 /tmp/labels.txt /tmp/refs.txt
```

**Acceptable orphans**: Subfigure labels (check that their parent figure label IS referenced).

**Unacceptable orphans**: Any parent `fig:`, `tab:`, or `eq:` label not referenced in text.

### 2b. Dangling Refs (ref without label)

```bash
echo "=== Dangling refs (no matching label) ==="
comm -13 /tmp/labels.txt /tmp/refs.txt
```

**Any dangling ref = FAIL.** This will produce `??` on compile.

---

## 3. Citation Integrity

### 3a. Count Citations vs. Bib Entries

```bash
cite_count=$(grep -roh '\\cite[tp]*{[^}]*}' sections/ 2>/dev/null | wc -l)
bib_count=$(grep -c '^@' references.bib 2>/dev/null || echo 0)

echo "\\cite{} calls: $cite_count"
echo "Bib entries: $bib_count"

if [ "$cite_count" -gt 0 ] && [ "$bib_count" -eq 0 ]; then
  echo "FAIL: Citations exist but .bib is empty — will produce ??"
else
  echo "OK"
fi
```

### 3b. Citation Key Matching (when bib has entries)

If `references.bib` has real entries, every `\cite{key}` must match a `@type{key,` in the bib:

```bash
# Extract cite keys
grep -roh '\\cite[tp]*{[^}]*}' sections/ | \
  sed 's/.*{\(.*\)}/\1/' | tr ',' '\n' | tr -d ' ' | sort -u > /tmp/citekeys.txt

# Extract bib keys
grep -o '^@[a-z]*{[^,]*' references.bib | \
  sed 's/.*{\(.*\)/\1/' | sort -u > /tmp/bibkeys.txt

echo "=== Cite keys without bib entries ==="
comm -23 /tmp/citekeys.txt /tmp/bibkeys.txt
```

---

## 4. Placement Verification (Manual)

These cannot be fully automated — review visually:

- [ ] Every main-body `\begin{figure}` appears **after** the paragraph containing its `\ref{}`
- [ ] Every main-body `\input{tables/...}` appears **after** the paragraph containing its `Table~\ref{}`
- [ ] Supplementary figures in `supplementary.tex` are referenced from `results.tex` or `methods.tex`
- [ ] No figure or table appears before its first textual mention

---

## 5. Compile-Readiness Summary

| Check | Status |
|-------|--------|
| All `\includegraphics` files exist | PASS / FAIL |
| All `\input{tables/}` files exist | PASS / FAIL |
| All `\input{sections/}` files exist | PASS / FAIL |
| Zero dangling `\ref{}` | PASS / FAIL |
| Zero dangling `\cite{}` | PASS / FAIL |
| Orphan labels are subfigures only | PASS / FAIL |
| Figures placed after referencing paragraph | PASS / FAIL |
| Supplementary figures referenced from main text | PASS / FAIL |

**All items MUST be PASS before delivering the project.**
