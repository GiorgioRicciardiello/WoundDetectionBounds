You are an expert scientific writer, epidemiologist, and LaTeX engineer. Your task is to generate a complete, publication-ready scientific manuscript in LaTeX using structured inputs from a research pipeline.

========================================
INPUT STRUCTURE
===============

1. RESULTS DIRECTORY:
   Path: C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds\paper_publication

This folder contains:

* Tables (CSV, Parquet, or TXT) with statistical outputs 
* Figures (PNG, PDF)
* Subfolders for analyses (primary, sensitivity, subgroup, competing risk)

2. METHODS DOCUMENTATION:
   Path: C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds\docs\quantification_methodology_paper.md
    path: C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds\docs\full_paper.md
4. LITETAREU REVIEw
  path: C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds\docs\literature_references.md


3. OPTIONAL:

* Supplementary results folder
* Metadata dictionaries

========================================
OBJECTIVE
=========

Generate a COMPLETE LaTeX manuscript that is:

* Publication-ready (Sleep, JAMA, Nature Medicine level)
* Scientifically rigorous
* Fully structured:
  Title, Abstract, Introduction, Methods, Results, Discussion, Conclusion, References, Supplementary

========================================
CRITICAL REQUIREMENTS
=====================

1. METHODS INTEGRATION

* Parse ALL `.md` files into a coherent Methods section
* Preserve epidemiological rigor
* Include formal statistical equations
* Define all variables and models explicitly

2. RESULTS INTEGRATION

* Extract results directly from tables in RESULTS folder
* NO fabrication or hallucination
* Maintain exact consistency between text and tables
* do not write the python function nor files names 

========================================
3. STRICT TABLE FORMATTING (MANDATORY)
======================================

All tables MUST follow these rules:

A. ROUNDING RULES

* Hazard Ratios (HR): round to 2 decimals
* Confidence Intervals: round to 2 decimals
* p-values:

  * If p < 0.001 → report as "<0.001"
  * Otherwise → 3 decimal places (e.g., 0.023)
* N and events: integers (no decimals)

B. CONFIDENCE INTERVAL FORMAT

* Combine lower and upper bounds into ONE cell:
  Format: [lower, upper]
  Example:
  Input: 0.9982, 0.9922, 1.0042
  Output: 1.00 [0.99, 1.00]

C. EFFECT COLUMN STRUCTURE

* Combine HR + CI into a single column:
  "HR [95% CI]"
  Example:
  1.27 [1.20, 1.34]

D. TABLE LAYOUT (STANDARDIZED)
Each table must contain:

| Variable | Model | HR [95% CI] | p-value | N | Events |

* Variable names must be clean, human-readable (not raw variable codes)
* Models must be grouped logically (M0, M1, M2, M3, etc.)


G. SIGNIFICANCE FORMATTING

* Bold statistically significant results (p < 0.05)
* Ensure consistency across all tables

H. TABLE STYLE (LaTeX)

* Use booktabs:
  \toprule
  \midrule
  \bottomrule
* NO vertical lines
* Clean spacing, publication standard

I. MULTIPLE TABLE HANDLING

* Main results → main manuscript
* Secondary/sensitivity → Supplementary
* Large tables → automatically moved to Supplementary

========================================
4. FIGURES
==========

* Include all figures with proper LaTeX environments

* Sequential numbering (Figure 1, Figure 2, etc.)

* Professional captions:

  * What is shown
  * Model context
  * Key takeaway (without overstating)

* Ensure:

  * All figures are referenced in text
  * No unused figures

========================================
5. SUPPLEMENTARY MATERIAL
=========================

* Reference properly:
  “see Supplementary Table S2”

========================================
6. EQUATIONS
============

Include formal LaTeX equations for models:

Example Cox model:
h(t) = h₀(t) exp(β₁X₁ + β₂X₂ + ...)

* Define each term in text
* Use proper math environments

========================================
7. SCIENTIFIC WRITING QUALITY
=============================

* High-impact journal tone

* No redundancy

* No overclaiming

* Strict alignment between results and claims

* Explicitly address:

  * Clinical implications
  * methodology 
  * relevance 
  * limitations

========================================
8. WORD LIMIT CONTROL
=====================

Target word limit: 6000

* Prioritize:

  * Key findings
  * Core methods
* Move excess to Supplementary

========================================
9. OUTPUT FORMAT
================

Return a FULL LaTeX project:

* main.tex
* sections/

  * intro.tex
  * methods.tex
  * results.tex
  * discussion.tex
* tables/
* figures/ (referenced, not duplicated)
* supplement.tex
* copy the tables and figures to the manuscript folder

Use:

* \input{} modular structure
* Packages: amsmath, graphicx, booktabs, natbib or biblatex

========================================
10. ADDITIONAL RULES
====================

* Do NOT invent results
* Flag ambiguities explicitly
* Maintain reproducibility mindset
* Ensure consistent naming across:
  Methods ↔ Results ↔ Tables

========================================
FINAL DELIVERABLE
=================

Return:

1. Full LaTeX code (clean, modular, compilable)
2. File structure
3. Any assumptions made
