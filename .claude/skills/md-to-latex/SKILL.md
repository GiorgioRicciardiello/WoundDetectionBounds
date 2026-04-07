---
name: md-to-latex
description: Generate a complete, publication-ready LaTeX manuscript from structured research inputs — results tables (CSV/Parquet/TXT), figures (PNG/PDF), methods documentation (.md), and literature references. Handles epidemiological studies with HR/OR tables, mixed models, GEE, and survival analyses. Enforces strict table formatting (HR [95% CI], rounding, bold significance), formal model equations, sequential figure numbering, and zero ?? compile errors. Targets Sleep, JAMA, Nature Medicine submission quality with ~6000-word limit.
allowed-tools: Read Write Edit Bash Glob Grep
license: MIT license
metadata:
    skill-author: EyeTempRand Project
    version: 3.0-results-pipeline
---

# Markdown to LaTeX — Publication-Ready Scientific Manuscripts

## Overview

You are an expert scientific writer, epidemiologist, and LaTeX engineer. Generate a complete, publication-ready scientific manuscript in LaTeX from structured research pipeline outputs.

**Two operating modes:**

| Mode | Use When | Primary Inputs |
|------|----------|----------------|
| **Results-pipeline** | Building manuscript from analysis outputs | Results directory (CSV/Parquet/TXT + figures) + methods .md files |
| **Manuscript-convert** | Converting an existing .md manuscript | Single manuscript .md file + figures |

Identify the mode from what the user provides. If the user supplies a results directory, use **Results-pipeline** mode.

---

## Input Structure

### Mode A — Results-Pipeline (Primary)

```
results_dir/
├── *.csv / *.parquet / *.txt   # Statistical output tables
├── *.png / *.pdf               # Figures
├── primary/                    # Primary analysis outputs
├── sensitivity/                # Sensitivity analyses
├── subgroup/                   # Subgroup analyses
└── competing_risk/             # Competing risk analyses (if present)

docs/
├── quantification_methodology_paper.md  # Methods documentation
├── full_paper.md                        # Full paper draft (if available)
└── literature_references.md            # Literature / references
```

### Mode B — Manuscript-Convert

| Input | Description |
|-------|-------------|
| Manuscript `.md` | Full paper draft |
| Figure directories | Paths to `.png` / `.pdf` files |

### Always Required

| Input | Description |
|-------|-------------|
| Output directory | Where to create the LaTeX project (e.g., `publication-latex/`) |

**ALWAYS ask for the output directory before doing any other work**, even if the user has provided all other inputs. Do not assume or default to any path.

Prompt the user with:
> "Where should the LaTeX project be saved? Please provide the full path to the output directory (it will be created if it does not exist)."

Once the user provides the path:
1. Check whether the directory exists using `Bash`: `[ -d "/path/to/output" ] && echo "exists" || echo "missing"`
2. If it does not exist, create it with all necessary parent directories: `mkdir -p "/path/to/output"`
3. Confirm to the user: "Output directory ready: `/path/to/output`"
4. Then proceed with the rest of the execution steps.

If any other required input is missing after confirming the output directory, ask for it before proceeding.

---

## Output Structure

```
{output_dir}/
├── main.tex
├── sections/
│   ├── abstract.tex
│   ├── introduction.tex
│   ├── methods.tex
│   ├── results.tex
│   ├── discussion.tex
│   └── conclusions.tex
├── tables/
│   └── table_N_name.tex
├── figures/          # Copies of figures (PDF preferred, PNG fallback)
├── supplement.tex    # Copies of All supplementary tables and figures
└── references.bib
```

Use `\input{}` modular structure — zero prose in `main.tex`.

---

## Execution Steps

### Step 1: Inventory All Inputs

**For Results-Pipeline mode:**
1. List all CSV/Parquet/TXT files in the results directory and subfolders
2. List all PNG/PDF figures
3. Read all `.md` files in the docs directory
4. Build a mapping: which tables and figures belong to which manuscript section

**For Manuscript-Convert mode:**
1. Read the manuscript `.md` fully
2. Build inventories: sections → headings, tables → markdown tables, figures → files

Classify each figure/table as **main-body** or **supplementary**:
- **Main-body**: primary results, key model outputs, main diagnostic plots
- **Supplementary**: sensitivity analyses, secondary results, exploratory visualizations, large tables (>10 rows)

### Step 2: Parse Methods Documentation

Read ALL `.md` files provided. Synthesize into a coherent Methods section:
- Preserve epidemiological rigor — population, design, outcomes, covariates
- Include formal statistical equations (see Step 6)
- Define all variables and model notation explicitly
- Do NOT reference Python function names or file names in the manuscript text

### Step 3: Create Directory Structure

```bash
mkdir -p {output_dir}/sections {output_dir}/tables {output_dir}/figures
```

### Step 4: Copy Figures

- **PDF preferred**: copy `.pdf` when both PDF and PNG exist for the same base name
- **Flatten paths**: `phase5/diag_qq.pdf` → `figures/diag_qq.pdf`
- **PNG fallback**: copy `.png` only when no `.pdf` counterpart exists
- **Sequential numbering**: assign Figure 1, Figure 2, ... in order of first appearance in text
- Copy all figures to `{output_dir}/figures/`

### Step 5: Extract and Format Tables

**CRITICAL — read all table rules before writing any table.**

#### 5A. Rounding Rules (MANDATORY)

| Statistic | Format |
|-----------|--------|
| Hazard Ratio (HR) | 2 decimal places (e.g., `1.27`) |
| Odds Ratio (OR) | 2 decimal places |
| Coefficient (β) | 3 decimal places |
| Confidence Interval bounds | 2 decimal places |
| p-value < 0.001 | `$<$0.001` |
| p-value ≥ 0.001 | 3 decimal places (e.g., `0.023`) |
| N, Events | Integers, no decimals |
| Percentages | 1 decimal place |
| Mean ± SD | 1 decimal place |

#### 5B. Effect Size Column Format

**ALWAYS combine HR/OR/β and CI into a single column.** Never separate them.

```
Column header:  HR [95\% CI]
Cell content:   1.27 [1.20, 1.34]
```

For models without HR (LMM, GEE with identity link):
```
Column header:  β [95\% CI]
Cell content:   −0.034 [−0.487, 0.420]
```

#### 5C. Standard Table Layout

Every primary results table must contain these columns (adapt as needed):

| Variable | Model | HR [95% CI] | p-value | N | Events |
|----------|-------|-------------|---------|---|--------|

- **Variable names**: human-readable (e.g., "Age at diagnosis", not `age_dx`)
- **Models**: group logically — M0 (unadjusted), M1, M2 (fully adjusted)
- **Significance**: bold rows where p < 0.05 using `\textbf{}`

#### 5D. Table Placement

- **Main results** → `tables/` + included in main manuscript
- **Secondary / sensitivity analyses** → `supplement.tex`
- **Large tables (>10 rows or >6 columns)** → automatically moved to Supplementary; reference in text as `Supplementary Table~\ref{tab:supp-...}`

#### 5E. LaTeX Table Template

```latex
\begin{table}[htbp]
\centering
\caption{Descriptive standalone caption. Model M0 is unadjusted; M1 adjusts for age and sex; M2 additionally adjusts for comorbidities.}
\label{tab:primary-results}
\begin{tabular}{l l S[table-format=1.2] @{\,} l S[table-format=1.3] r r}
\toprule
{Variable} & {Model} & \multicolumn{2}{c}{HR [95\% CI]} & {p-value} & {N} & {Events} \\
\midrule
\multicolumn{7}{l}{\textit{Primary Exposure}} \\
\midrule
Age (per year) & M0 & \multicolumn{2}{c}{\textbf{1.27 [1.20, 1.34]}} & \textbf{$<$0.001} & 1{,}234 & 456 \\
               & M1 & \multicolumn{2}{c}{\textbf{1.24 [1.17, 1.31]}} & \textbf{$<$0.001} & 1{,}234 & 456 \\
               & M2 & \multicolumn{2}{c}{\textbf{1.21 [1.14, 1.29]}} & \textbf{$<$0.001} & 1{,}234 & 456 \\
\bottomrule
\end{tabular}
\smallskip
\noindent\textit{Note:} HR, hazard ratio; CI, confidence interval. Bold indicates $p < 0.05$.
\end{table}
```

**Rules:**
- `booktabs` ONLY: `\toprule`, `\midrule`, `\bottomrule` — NEVER `\hline`
- No vertical lines
- Group model rows under the same variable with blank variable cell for M1/M2
- Use `\multicolumn` for grouped headers

### Step 6: Write Formal Model Equations

Include LaTeX equations for every statistical model used. Define all terms.

**Cox proportional hazards model:**
```latex
\begin{equation}
h(t \mid \mathbf{x}) = h_0(t) \exp\!\left(\beta_1 X_1 + \beta_2 X_2 + \cdots + \beta_p X_p\right)
\label{eq:cox}
\end{equation}
```

**Linear mixed model:**
```latex
\begin{equation}
Y_{ijk} = \mu + \alpha_i + \mathbf{x}_{ijk}^\top \boldsymbol{\beta} + b_j + b_{jk} + \varepsilon_{ijk}
\label{eq:lmm}
\end{equation}
```

**GEE:**
```latex
\begin{equation}
g\!\left(\mu_{ij}\right) = \beta_0 + \beta_1 X_{1ij} + \cdots + \beta_p X_{pij}
\label{eq:gee}
\end{equation}
```

After each equation, define every term in text. Reference equations as `Equation~\ref{eq:cox}` or `\eqref{eq:cox}`.

### Step 7: Write Section Files

Convert markdown content to LaTeX following [references/latex_conventions.md](references/latex_conventions.md).

**Section mapping:**

| Section | File | Notes |
|---------|------|-------|
| Abstract | `sections/abstract.tex` | Structured: Background, Methods, Results, Conclusions |
| Introduction | `sections/introduction.tex` | From `full_paper.md` or `literature_references.md` |
| Methods | `sections/methods.tex` | Synthesized from ALL `.md` docs; includes equations |
| Results | `sections/results.tex` | Numbers extracted directly from tables; no fabrication |
| Discussion | `sections/discussion.tex` | Clinical implications, limitations, future work |
| Conclusions | `sections/conclusions.tex` | 1–2 paragraphs max |

**Scientific writing quality (MANDATORY):**
- High-impact journal tone — precise, active voice, no redundancy
- No overclaiming — align claims strictly with results
- Explicitly address in Discussion:
  - Clinical implications
  - Methodological strengths
  - Study limitations (at least 3)
  - Future directions

**Word limit: ~6,000 words** for main manuscript. Move excess to Supplementary.

### Step 8: Apply Figure and Table Referencing Rules

Read [references/figure_table_rules.md](references/figure_table_rules.md). Summary:

1. **Every `\label{X}` MUST have a matching `\ref{X}` in body text** — no orphan labels
2. **Every `\ref{X}` MUST have a matching `\label{X}`** — no dangling refs, no `??`
3. **Main-body items** placed immediately after the paragraph that first references them
4. **Supplementary items** stay in `supplement.tex` but MUST be referenced from main text as `Supplementary Figure~\ref{fig:supp-...}` or `Supplementary Table~\ref{tab:supp-...}`
5. **Figure captions** must contain three elements:
   - What is shown (data/variable)
   - Model context (which model/adjustment)
   - Key observation (without overstating significance)

**Figure caption template:**
```latex
\caption{%
  \textbf{Kaplan--Meier survival curves by exposure group.}
  Unadjusted cumulative event probability over follow-up time for each group (N\,=\,1{,}234).
  Event rates diverge after 12 months, consistent with the primary Cox model findings (Table~\ref{tab:primary-results}).%
}
```

### Step 9: Write `supplement.tex`

Structure:
```latex
\clearpage
\appendix
\setcounter{table}{0}
\renewcommand{\thetable}{S\arabic{table}}
\setcounter{figure}{0}
\renewcommand{\thefigure}{S\arabic{figure}}

\section*{Supplementary Material}

\subsection*{Supplementary Tables}
% \input{} supplementary tables here

\subsection*{Supplementary Figures}
% Supplementary figures here
```

Reference from main text as: "see Supplementary Table~\ref{tab:supp-sensitivity}" and "Supplementary Figure~\ref{fig:supp-...}".

### Step 10: Verify — Zero `??` Guarantee

Run [scripts/verify_latex.py](scripts/verify_latex.py) or check manually:

1. Every `\includegraphics{X}` → `figures/X` exists
2. Every `\input{tables/X}` → `tables/X.tex` exists
3. Every `\input{sections/X}` → `sections/X.tex` exists
4. Every `\label{X}` has a matching `\ref{X}` (except subfigure labels)
5. Every `\ref{X}` has a matching `\label{X}`
6. If `.bib` is a placeholder → zero `\cite{}` in any `.tex` file
7. Every `\cite{X}` has a matching `@article{X,...}` in `.bib`

Output a verification report listing each check and pass/fail status.

### Step 11: Output Manifest

After all files are created, output:
- Complete file list with line counts
- Figure count (main / supplementary)
- Table count (main / supplementary)
- Approximate word count for main manuscript
- Verification report from Step 10
- Any warnings (missing figures, unreferenced items, large tables moved to supplementary)

---

## Constraints — NEVER Violate

- **No fabrication**: Extract results directly from provided tables. Do NOT invent numbers, p-values, or effect sizes.
- **No Python/file references**: Do NOT mention script names, file paths, or function names in manuscript text.
- **No `??` on compile**: Zero unresolved references — no `\cite{}` without bib entries, no `\ref{}` without labels, no `\includegraphics{}` for missing files.
- **Exact number preservation**: Every statistical value from the source data MUST appear exactly in the `.tex`. Apply rounding rules; do not omit values.
- **Blinding**: If the study is blinded, use condition labels only (e.g., "Condition 0" / "Condition 1"). NEVER reveal treatment identity.
- **Scope lock**: Only create/modify files within the output directory. Do NOT touch any existing project files.
- **No variable codes**: Use human-readable variable names throughout (methods, results, table headers, captions).

## Forbidden Actions

- Do NOT modify files outside the output directory
- Do NOT run `pdflatex`, `bibtex`, `latexmk`, or any build command
- Do NOT add LaTeX packages beyond those in the template without asking
- Do NOT create Makefiles, CI configs, or Docker files
- Do NOT use `\cite{}` when `references.bib` is a placeholder
- Do NOT write Python function names or file paths in manuscript text

---

## Idempotency

This skill is designed to be rerun. Each invocation:
1. Reads current source files (which may have changed)
2. Overwrites `{output_dir}/` completely
3. Re-copies all figures from source directories
4. Regenerates all `.tex` files from scratch

The output directory is a build artifact — never edit it manually.

---

## Reference Files

Load only when needed:

| File | Load When |
|------|-----------|
| [references/latex_conventions.md](references/latex_conventions.md) | Converting markdown syntax, writing tables/figures |
| [references/figure_table_rules.md](references/figure_table_rules.md) | Placing figures/tables, writing cross-references |
| [references/diagnostic_checklist.md](references/diagnostic_checklist.md) | Running final verification pass |

## Assets

| File | Purpose |
|------|---------|
| [assets/main_template.tex](assets/main_template.tex) | Skeleton `main.tex` with preamble and package list |
| [assets/table_template.tex](assets/table_template.tex) | Booktabs table skeleton for consistent formatting |

## Scripts

| File | Purpose |
|------|---------|
| [scripts/verify_latex.py](scripts/verify_latex.py) | Automated verification: file existence, label/ref integrity, cite/bib consistency |
