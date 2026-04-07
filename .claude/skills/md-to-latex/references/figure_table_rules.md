# Figure and Table Referencing Rules

These rules guarantee that the compiled PDF contains zero `??` marks and that every display item is properly integrated into the narrative.

---

## Rule 1: Every Label Must Have a Ref

**Every `\label{X}` defined in any `.tex` file MUST have a corresponding `\ref{X}`, `Figure~\ref{X}`, `Table~\ref{X}`, or `Equation~\ref{X}` somewhere in the body text.**

An orphan label (defined but never referenced) means the reader encounters a figure or table with no textual connection — it floats without context.

### Exception: Subfigure Labels

Subfigure labels (e.g., `\label{fig:violin-depth}` inside a `subfigure` environment) do NOT require their own `\ref{}` — they exist for optional granular cross-referencing. However, the **parent figure** label MUST be referenced.

```latex
% Parent label fig:violins MUST be referenced in text
% Subfigure labels fig:violin-depth and fig:violin-extent are optional
\begin{figure}[htbp]
\begin{subfigure}{0.48\textwidth}
  \label{fig:violin-depth}   % Optional ref
\end{subfigure}
\begin{subfigure}{0.48\textwidth}
  \label{fig:violin-extent}  % Optional ref
\end{subfigure}
\caption{...}
\label{fig:violins}          % MUST be referenced
\end{figure}
```

---

## Rule 2: Every Ref Must Have a Label

**Every `\ref{X}` in the body text MUST have a corresponding `\label{X}` defined somewhere.** A dangling ref produces `??` in the compiled PDF.

### Common Causes of Dangling Refs

| Cause | Fix |
|-------|-----|
| Typo in label key | Check spelling: `fig:qq-residuals` vs `fig:qq-resdiuals` |
| Label in a file not `\input{}`-ed | Ensure `main.tex` inputs the file containing the label |
| `\cite{}` with no bib entry | Remove `\cite{}` or add the entry to `.bib` |
| Label removed during editing | Remove the corresponding `\ref{}` |

---

## Rule 3: Main-Body Placement — After the Referencing Paragraph

**Main-body figures and tables MUST be placed immediately AFTER the paragraph that first references them.**

### Correct

```latex
The score distributions are shown in Figure~\ref{fig:distributions}.

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{distributions.pdf}
\caption{Score distributions by condition.}
\label{fig:distributions}
\end{figure}

The next paragraph continues the narrative...
```

### Incorrect — Figure Before Reference

```latex
\begin{figure}[htbp]          % BAD: figure appears before it's mentioned
...
\label{fig:distributions}
\end{figure}

The score distributions are shown in Figure~\ref{fig:distributions}.
```

### Incorrect — Figure Multiple Paragraphs Later

```latex
The distributions are shown in Figure~\ref{fig:distributions}.

Here is another paragraph about something else.

Yet another paragraph about a different topic.

\begin{figure}[htbp]          % BAD: too far from the reference
...
\label{fig:distributions}
\end{figure}
```

### Placement for Tables with `\input{}`

Tables follow the same rule — the `\input{}` call goes immediately after the referencing paragraph:

```latex
Table~\ref{tab:lmm} presents the LMM results.

\input{tables/table_1_lmm}    % Immediately after the referencing paragraph

The condition effect was not significant...
```

---

## Rule 4: Supplementary Figures — Referenced from Main Text

**Supplementary figures stay in `supplementary.tex` but MUST be referenced from the main text.**

The reference appears in the relevant paragraph of results, methods, or discussion using `Supplementary Figure~\ref{fig:supp-...}`:

### In `results.tex`:

```latex
Bland--Altman plots confirmed the systematic bias (Figure~\ref{fig:bland-altman}).
Additional grader comparisons including scatter plots and box plots by grader
are presented in Supplementary Figures~\ref{fig:supp-grader-scatter}
and~\ref{fig:supp-box-grader}.
```

### In `supplementary.tex`:

```latex
\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{grader_scatter_depth.pdf}
\caption{Scatter plots of Grader~1 vs.\ Grader~2 scores.}
\label{fig:supp-grader-scatter}    % This label is referenced from results.tex
\end{figure}
```

### Grouping Supplementary References

When multiple supplementary figures support the same point, group them in a single sentence:

```latex
% GOOD: grouped
Additional distributional views are provided in Supplementary
Figures~\ref{fig:supp-distributions},~\ref{fig:supp-proportions},
and~\ref{fig:supp-raincloud}.

% BAD: scattered across separate sentences
% Supplementary Figure~\ref{fig:supp-distributions} shows the distributions.
% Supplementary Figure~\ref{fig:supp-proportions} shows proportions.
% Supplementary Figure~\ref{fig:supp-raincloud} shows raincloud plots.
```

---

## Rule 5: No `\cite{}` Without Bib Entries

**Every `\cite{key}` MUST have a matching `@article{key, ...}` or `@book{key, ...}` in `references.bib`.** A missing bib entry produces `??` on compile — the most common source of unresolved references.

### When `.bib` Is a Placeholder

If `references.bib` contains only comments or TODO markers:
- There MUST be **zero** `\cite{}` commands in any `.tex` file
- Leave in-text citations as plain text: `(Smith, 2024)` instead of `\cite{smith2024}`
- This can be upgraded later when real bib entries are added

### Verification

```bash
# Count \cite{} calls
grep -roh '\\cite{[^}]*}' sections/ | wc -l

# Count bib entries
grep -c '^@' references.bib

# If cite count > 0 and bib count == 0 → FAIL
```

---

## Rule 6: `\input{}` Files Must Exist

Every `\input{path}` MUST point to an existing file. LaTeX will error (not just `??`) if an input file is missing.

### Verification

```bash
# Extract all \input{} paths and check existence
grep -roh '\\input{[^}]*}' main.tex sections/ | \
  sed 's/\\input{\(.*\)}/\1.tex/' | \
  while read f; do
    [ -f "$f" ] || echo "MISSING: $f"
  done
```

---

## Rule 7: `\includegraphics{}` Files Must Exist

Every `\includegraphics{filename}` MUST resolve to an existing file in the `\graphicspath`. LaTeX will error if the file is not found.

### Verification

```bash
# Extract all includegraphics filenames and check in figures/
grep -roh '\\includegraphics\[.*\]{[^}]*}' sections/ | \
  sed 's/.*{\(.*\)}/\1/' | \
  while read f; do
    [ -f "figures/$f" ] || echo "MISSING: figures/$f"
  done
```

---

## Summary Checklist

Before delivering the LaTeX project, confirm ALL of the following:

- [ ] Every `\label{}` (except subfigures) has a matching `\ref{}`
- [ ] Every `\ref{}` has a matching `\label{}`
- [ ] Every `\cite{}` has a matching bib entry (or zero `\cite{}` if bib is placeholder)
- [ ] Every `\includegraphics{}` resolves to an existing file in `figures/`
- [ ] Every `\input{tables/...}` resolves to an existing `.tex` file
- [ ] Every `\input{sections/...}` resolves to an existing `.tex` file
- [ ] Main-body figures/tables are placed after their referencing paragraph
- [ ] Supplementary figures are referenced from the main text
- [ ] All parent figure labels are referenced (subfigure labels are optional)
