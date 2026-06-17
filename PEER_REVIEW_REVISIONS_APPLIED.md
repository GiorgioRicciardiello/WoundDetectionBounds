# Peer Review Revisions Applied — 2026-06-17

## Summary

Applied grounded, transparent revisions to manuscript addressing peer-review major comments #1 (phrasing/claims) and minor comment #2 (jump penalty formula definition). All changes emphasize honest limitations, public tool mission, and ethical scientific communication.

---

## Changes by Section

### 1. **Abstract** (sections/abstract.tex)

**Removed:**
- "without annotated training data, deep-learning models, or user-defined thresholds"

**Added:**
- "without annotated training data or deep-learning models"
- "The pipeline requires minimal parameter tuning and operates on standard laboratory hardware"
- Final sentence: "freely available to the research community without reliance on annotated datasets or specialized infrastructure"

**Rationale:** 
- Honest about parameter tuning (w=15, percentiles, margins are tuned)
- Emphasizes public tool mission
- Avoids overclaiming parity with supervised methods

---

### 2. **Methods § Temporal Constraint** (sections/methods.tex, lines 186–199)

**Added explicit formula for jump penalty J(x,t):**

$$J(x, t) = 1.0 + \left(\frac{|\tilde{u}_\text{det}(x,t) - u(x,t-1)|}{\text{median}_x(|\tilde{u}_\text{det}(\cdot,t) - u(\cdot,t-1)|)}\right)^2$$

**Rationale:**
- Peer-review minor comment #2: "J(x,t) is mentioned but not formally defined"
- Formula extracted directly from code (kalman_constraint.py, lines 273–282)
- Median frame-level jump used to normalize per-column deviations
- Large jumps → high R → Kalman relies on prior (monotonic constraint)

---

### 3. **Discussion § Opening** (sections/discussion.tex, lines 3–5)

**Revised first paragraph:**
- Removed: "...all without annotated training data, user-defined threshold tuning, or specialist infrastructure"
- Added: "Like existing computational approaches, the method applies learned parameters (local variance window size, edge thresholds, smoothing window lengths) that were developed on this dataset; full parameter documentation is provided to support transparency and reproducibility."
- Reframed unconstrained baseline as context for improvement
- Quantified improvement: "96.8% improvement over unconstrained detection"

**Rationale:** 
- Grounded, not celebratory
- Acknowledges parameters are learned/tuned (not magic)
- Transparency-first framing

---

### 4. **Discussion § QC Performance** (sections/discussion.tex, lines 11–13)

**Expanded QC portability discussion:**

**Added new paragraph (bolded text):**
> "However, this design point is dataset-specific. **Extension to new imaging conditions, microscope settings, cell types, or magnifications will likely require re-tuning of the QC thresholds.** The validation criteria (aspect ratio, edge homogeneity, width coverage) were optimized empirically on this 126-image cohort; their performance on new datasets remains to be established. We provide source code and threshold documentation to support this process; users are advised to validate on a small local cohort (e.g., 20–30 manually annotated images) before applying the pipeline to large datasets in a new context."

**Rationale:**
- Peer-review major comment #1: QC thresholds are dataset-specific
- Explicit warning about generalization
- Practical guidance for users (20–30 manual annotations)

---

### 5. **Discussion § Single-Observer Validation** (sections/discussion.tex, lines 17)

**Added new paragraph (bolded):**
> "**Validation was performed by a single trained observer, blinded to treatment condition but not cell-line identity.** While the strict annotation criterion renders the reported accuracy a conservative lower bound, single-observer validation is an important limitation. Inter-rater reliability was not quantified, and we cannot exclude systematic biases in the reviewer's threshold or condition-dependent drift in decision-making. For high-stakes applications, independent validation on domain-specific datasets before deployment is recommended. Future work should include multi-observer validation (inter-rater ICC or Cohen's κ) and testing on imaging systems or cell types not present in this cohort."

**Rationale:**
- Peer-review major comment #3: Single observer is a significant limitation
- Elevates this concern from buried in text to prominent paragraph
- Clear statement of what was NOT done (inter-rater reliability)
- Recommends multi-observer validation in follow-up work
- Honest about potential systematic biases

---

## Tone & Framing Changes

| Aspect | Before | After |
|--------|--------|-------|
| Claims | "without thresholds" | "minimal tuning required" |
| Authority | Implies supervised-method parity | "no direct comparison on identical images" |
| Community | "practical solution" | "freely available to the research community" |
| Limitations | Acknowledged but brief | Prominent, actionable, transparent |
| Validation | "92.1% accuracy" (leading) | "92.1% on publication cohort; single observer" (grounded) |
| Generalization | Implicit | Explicit re-tuning requirement for new contexts |

---

## PDF Status

✅ **Compiled successfully** (`pdflatex -interaction=nonstopmode main.tex`)
- 41 pages, 14.8 MB
- No blocking errors; minor overfull \vbox (expected when adding content)

---

## Scientific Integrity Notes

All revisions align with **CLAUDE.md ethics requirements:**
1. **Reproducibility** — Full parameter documentation; formula explicitly defined
2. **Mathematical correctness** — J(x,t) formula matches code implementation
3. **Transparency** — Honest about what was/wasn't done (inter-rater reliability)
4. **Ethical stance** — Warn users about generalization limits; don't overclaim
5. **Public tool mission** — Emphasize "freely available to research community"

---

## Next Steps

- [ ] Verify PDF visual layout (check if Eq. 195-198 formatted correctly)
- [ ] Commit with message: `docs: revise abstract, methods, discussion per peer review feedback`
- [ ] Prepare submission package for *Scientific Reports* / *PLoS Computational Biology* / *Computational Biology*
