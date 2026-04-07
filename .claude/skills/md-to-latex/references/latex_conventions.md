# LaTeX Conventions Reference

## Document Class and Packages

Standard preamble for scientific manuscripts:

```latex
\documentclass[12pt, a4paper]{article}

\usepackage[margin=1in]{geometry}
\usepackage{booktabs}          % Professional table rules
\usepackage{graphicx}          % Figure inclusion
\usepackage{amsmath}           % Math environments
\usepackage{hyperref}          % Clickable cross-references
\usepackage[round]{natbib}     % Author-year citations
\usepackage{caption}           % Caption customization
\usepackage{subcaption}        % Subfigures (a), (b), (c)
\usepackage{float}             % [H] placement specifier
\usepackage{longtable}         % Multi-page tables
\usepackage{siunitx}           % Number alignment in tables
\usepackage{setspace}          % Line spacing control

\graphicspath{{figures/}}
```

Do NOT add packages beyond this list without asking the user.

## Heading Conversion

| Markdown | LaTeX |
|----------|-------|
| `# Title` | `\title{}` (in preamble) |
| `## Section` | `\section{}` |
| `### Subsection` | `\subsection{}` |
| `#### Subsubsection` | `\subsubsection{}` |

## Text Formatting

| Markdown | LaTeX |
|----------|-------|
| `**bold**` | `\textbf{bold}` |
| `*italic*` | `\textit{italic}` |
| `` `code` `` | `\texttt{code}` |
| `---` (em-dash) | `---` |
| `--` (en-dash for ranges) | `--` |

## Mathematical Notation

| Markdown / Plain | LaTeX |
|-----------------|-------|
| `>=` | `$\geq$` |
| `<=` | `$\leq$` |
| `x` (multiplication sign) | `$\times$` |
| `alpha = 0.05` | `$\alpha = 0.05$` |
| `p < 0.001` | `$p < 0.001$` |
| `beta = -0.034` | `$\beta = -0.034$` |
| `sigma^2` | `$\sigma^2$` |
| `+/-` | `$\pm$` |
| Subscript `ICC(2,1)` | `ICC\textsubscript{2,1}` |
| `95% CI` | `95\% CI` (escape the percent) |
| Named subscripts | `$\sigma^2_{\text{patient}}$` |

### Equation Environments

For displayed model specifications:
```latex
\begin{equation}
\text{Outcome} \sim \text{Condition} + \text{Procedure Code} + \text{Grader} + (1 \mid \text{Patient})
\label{eq:lmm}
\end{equation}
```

Reference with `Equation~\ref{eq:lmm}` or `\eqref{eq:lmm}`.

## Table Conventions

### Epidemiological Results Table (HR/OR — Primary Format)

For Cox models, logistic regression, and survival analyses:

```latex
\begin{table}[htbp]
\centering
\caption{Association between exposure and outcome across model specifications.
  M0: unadjusted; M1: adjusted for age and sex; M2: fully adjusted (age, sex, comorbidities).}
\label{tab:primary-results}
\begin{tabular}{l l l r r}
\toprule
{Variable} & {Model} & {HR [95\% CI]} & {p-value} & {N} \\
\midrule
\multicolumn{5}{l}{\textit{Primary Exposure}} \\
\midrule
Age (per year) & M0 & \textbf{1.27 [1.20, 1.34]} & \textbf{$<$0.001} & 1{,}234 \\
               & M1 & \textbf{1.24 [1.17, 1.31]} & \textbf{$<$0.001} & 1{,}234 \\
               & M2 & \textbf{1.21 [1.14, 1.29]} & \textbf{$<$0.001} & 1{,}234 \\
\midrule
Sex (female)   & M0 & 1.05 [0.94, 1.17] & 0.412 & 1{,}234 \\
               & M2 & 0.98 [0.87, 1.10] & 0.721 & 1{,}234 \\
\bottomrule
\end{tabular}
\smallskip
\noindent\textit{Note:} HR, hazard ratio; CI, confidence interval.
Bold rows indicate $p < 0.05$.
\end{table}
```

### Mixed Model / GEE Table (β coefficients)

```latex
\begin{table}[htbp]
\centering
\caption{Linear mixed model results for [outcome].}
\label{tab:lmm}
\begin{tabular}{l S[table-format=-1.3] @{\,} l S[table-format=1.3]}
\toprule
{Variable} & \multicolumn{2}{c}{$\beta$ [95\% CI]} & {p-value} \\
\midrule
Condition     & \multicolumn{2}{c}{\textbf{$-$0.034 [$-$0.487, $-$0.001]}} & \textbf{0.045} \\
Age (per year)& \multicolumn{2}{c}{0.012 [$-$0.023, 0.047]} & 0.502 \\
\bottomrule
\end{tabular}
\smallskip
\noindent\textit{Note:} $\beta$, regression coefficient; CI, confidence interval.
\end{table}
```

### Rounding Rules (MANDATORY)

| Statistic | Rule | Example |
|-----------|------|---------|
| HR / OR | 2 decimal places | `1.27` |
| β (coefficient) | 3 decimal places | `−0.034` |
| CI bounds (HR/OR) | 2 decimal places | `[1.20, 1.34]` |
| CI bounds (β) | 3 decimal places | `[−0.487, 0.420]` |
| p < 0.001 | `$<$0.001` | |
| p ≥ 0.001 | 3 decimal places | `0.023` |
| N, Events | Integers | `1,234` |
| Mean ± SD | 1 decimal place | `45.3 ± 12.1` |
| Percentages | 1 decimal place | `34.5\%` |

### HR [95% CI] Combined Column — Formatting Rules

- **ALWAYS** combine HR and CI into one column: `HR [95\% CI]`
- **NEVER** split into separate HR, Lower, Upper columns
- Format: `1.27 [1.20, 1.34]` — brackets, comma-separated
- Negative CI bounds: use math-mode minus sign `$-$0.487`
- Bold significant cells (p < 0.05): `\textbf{1.27 [1.20, 1.34]}`

### Table Placement Rules

- **Main results** (≤10 rows, ≤6 columns) → include in main manuscript
- **Large tables** (>10 rows or >6 columns) → move to `supplement.tex`; reference as `Supplementary Table~\ref{tab:supp-...}`
- **Sensitivity/subgroup analyses** → always in `supplement.tex`

### General Template (LMM / mixed / custom)

```latex
\begin{table}[htbp]
\centering
\caption{Descriptive caption that stands alone.}
\label{tab:unique-key}
\begin{tabular}{l S[table-format=-1.3] S[table-format=1.3] c S[table-format=1.3]}
\toprule
{Column 1} & {Column 2} & {Column 3} & {Column 4} & {Column 5} \\
\midrule
Row 1 & -0.034 & 0.231 & $-0.487$ to $0.420$ & 0.885 \\
Row 2 &  0.029 & 0.146 & $-0.258$ to $0.316$ & 0.844 \\
\bottomrule
\end{tabular}

\smallskip
\noindent\textit{Note:} Explanation of abbreviations and methods.
\end{table}
```

### Rules

- ALWAYS use `booktabs`: `\toprule`, `\midrule`, `\bottomrule` — never `\hline`
- NO vertical lines
- Use `siunitx` S-columns for numeric alignment: `S[table-format=-1.3]`
- Wrap text column headers in `{braces}` when using S-columns
- Confidence intervals: `$-0.487$ to $0.420$` (math mode for negative signs)
- Notes go below the table with `\smallskip` + `\noindent\textit{Note:}`
- Footnote symbols: `\textsuperscript{*}`, `\textsuperscript{\dag}`
- Variable names: human-readable only — never raw variable codes (e.g., `age_dx`)

## Figure Conventions

### Single Figure

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{filename.pdf}
\caption{Descriptive standalone caption.}
\label{fig:unique-key}
\end{figure}
```

### Subfigures (Side by Side)

```latex
\begin{figure}[htbp]
\centering
\begin{subfigure}[b]{0.48\textwidth}
\includegraphics[width=\textwidth]{left_figure.pdf}
\caption{Left panel description}
\label{fig:left}
\end{subfigure}
\hfill
\begin{subfigure}[b]{0.48\textwidth}
\includegraphics[width=\textwidth]{right_figure.pdf}
\caption{Right panel description}
\label{fig:right}
\end{subfigure}
\caption{Overall figure caption.}
\label{fig:parent}
\end{figure}
```

### Three-Panel Figure

```latex
\begin{subfigure}[b]{0.32\textwidth}
...
\end{subfigure}
\hfill
\begin{subfigure}[b]{0.32\textwidth}
...
\end{subfigure}
\hfill
\begin{subfigure}[b]{0.32\textwidth}
...
\end{subfigure}
```

### Placement Specifiers

| Specifier | Meaning | When to Use |
|-----------|---------|-------------|
| `[htbp]` | Here, top, bottom, page | Default for all figures/tables |
| `[H]` | Force exactly here | Supplementary materials only (requires `float` package) |

## Cross-Reference Conventions

### Label Prefixes

| Prefix | Use For | Example |
|--------|---------|---------|
| `fig:` | Figures | `\label{fig:qq-residuals}` |
| `tab:` | Tables | `\label{tab:lmm}` |
| `eq:` | Equations | `\label{eq:lmm}` |
| `sec:` | Sections | `\label{sec:methods}` |
| `fig:supp-` | Supplementary figures | `\label{fig:supp-heatmaps}` |

### Reference Syntax

- Figures: `Figure~\ref{fig:key}` (use non-breaking space `~`)
- Tables: `Table~\ref{tab:key}`
- Equations: `Equation~\ref{eq:key}` or `\eqref{eq:key}`
- Supplementary: `Supplementary Figure~\ref{fig:supp-key}`
- Multiple: `Figures~\ref{fig:a} and~\ref{fig:b}`
- Range: `Supplementary Figures~\ref{fig:supp-a}--\ref{fig:supp-c}`

### Non-Breaking Spaces

ALWAYS use `~` between the word and `\ref{}`:
```latex
% CORRECT
Figure~\ref{fig:results}
Table~\ref{tab:demographics}

% WRONG — line break can separate "Figure" from the number
Figure \ref{fig:results}
```

## Citation Conventions

### When `.bib` Has Real Entries

```latex
\cite{smith2024}              % Parenthetical: (Smith, 2024)
\citet{smith2024}             % Textual: Smith (2024)
\citep{smith2024,jones2023}   % Multiple: (Smith, 2024; Jones, 2023)
```

### When `.bib` Is a Placeholder

Do NOT use `\cite{}` anywhere. Leave citations as plain text in the manuscript:
```latex
% CORRECT when .bib is empty
Previous work has shown this effect (Smith, 2024).

% WRONG — will produce ?? on compile
Previous work has shown this effect \cite{smith2024}.
```

This is critical for the zero-`??` guarantee.

## Special Characters to Escape

| Character | LaTeX | Notes |
|-----------|-------|-------|
| `%` | `\%` | Common in statistical reporting |
| `&` | `\&` | Rare in prose, required in tables |
| `#` | `\#` | |
| `$` | `\$` | Unless entering math mode |
| `_` | `\_` | Unless in math mode |
| `~` | `\textasciitilde` | Unless used as non-breaking space |
| `^` | `\textasciicircum` | Unless in math mode |
