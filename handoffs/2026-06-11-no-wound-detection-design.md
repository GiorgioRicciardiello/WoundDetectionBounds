# Session Handoff: No-Wound Detection Design (NOT YET ACCEPTED)

**Date:** 2026-06-11
**Project:** C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds
**Phase:** Planning / design debate — **user is NOT happy with the current plan direction**

> ⚠️ **Status flag:** The design below is a *proposal under active dispute*, not an agreed plan.
> The user pushed back hard on the validation logic ("what are you actually validating? when we
> have an external dataset we will not have a validation, so which parameters are you tuning?")
> and then called for this handoff because they are **not liking** where the plan landed.
> Do **not** start implementing. Re-open the design with fresh eyes.

---

## Part 1 — Icon Generator (DONE, working, side-quest)

A throwaway one-shot script built earlier in the session to make Figure-1 illustration icons.
This is **finished and unrelated to the no-wound work** — captured only so it isn't lost.

**File:** `scripts/tmp_icon_generator.py`

- Reproduces `WoundDetector.detect()` internals **without modifying any library code** — it
  instantiates `WoundDetector(WoundDetectorConfig())` and calls the private stage methods
  directly (`_compute_local_variance`, `_detect_y_band`, `_extract_edges_per_column`,
  `_ransac_smooth_edges`, `_savgol_smooth`, `_edges_to_mask`).
- Loads `config['trajectories_pickle']`, scores QC-valid t=0 candidates, picks a sample, renders
  6 icons to **`results/icons_v1/`** at 300 DPI, full-frame (no crop):
  - `icon_0_raw.png` — plain grayscale, no overlays
  - `icon_1_variance.png` — variance map, `viridis`, clipped at 99th pct
  - `icon_2_edge_raw.png` — raw per-column edges (red upper `#FF0000` / cyan lower `#00CCFF`, s=3 dots)
  - `icon_3_edge_ransac.png` — RANSAC-cleaned edges
  - `icon_4_edge_savgol.png` — Savitzky-Golay smooth (solid lines, lw=2.5)
  - `icon_5_wound_mask.png` — cyan mask overlay on grayscale
- **Selection logic (current):** among QC-valid t=0 candidates with wound area ≥ median, picks the
  **75th-percentile RANSAC-change** sample (mean |raw − ransac| across both edges). Lands on
  `alk5i_e12_1-EXP2-alk5i` (score 8.1 px, 31.5% coverage). A larger-wound pinned sample
  `alk5i_f3_1-EXP1-alk5i` (269k px², 40.8% coverage) was used at one point and is referenced in
  history if a "more obvious wound" example is wanted again.
- **OUT_DIR is currently `results/icons_v1`.** Earlier runs wrote to `icons_main` and `icons_v2`;
  the user asked to NOT touch `icons_main`. Output dir is a one-line constant near top of file.
- Run: `powershell.exe -Command "& 'C:\Users\riccig01\anaconda3\envs\imgai_env\python.exe' scripts/tmp_icon_generator.py"`
  (the conda python path must be quoted-and-called this way; bare `python` / the raw `.exe` path
  via the Bash tool fails on this Windows box).

---

## Part 2 — KEY DISCOVERY: ground truth already exists

The motivating problem: the pipeline **always assumes a wound exists** and will draw a band on a
closed/empty field. `_detect_y_band` does `np.argmin(y_smooth)` — it always finds *some* minimum.
The shape-only QC (`_validate_wound_geometry`) never asks "is this region actually smoother than
the surrounding cells?" — there is **no variance-contrast check**.

This is already a **documented, quantified weakness** and there is **already a labeled dataset**:

**`config['verification_results']`** →
`...\results_quantification_updated\verification_results.xlsx` (325 rows, 17 cols, expert-annotated).
Key columns: `trajectory_key`, `exposure`, `experiment`, `qc_auto_valid` (current QC flag),
`correct` (human verdict), `polygon_drawn`, pixel metrics (`dice`/`iou`/…), `notes`, `keep`.

Label encoding:
- `correct == 1.0` → 282 (wound-bearing, correctly segmented)
- `correct == 0.0` → 41 (bad)  •  `correct == NaN` → 2 (unannotated)
- `notes == "no wound"` → exactly **40** images (the no-wound ground truth)
- `keep` mirrors `correct` (282 kept / 41 dropped / 2 NaN)

**Current QC confusion matrix (vs human, all annotated):**
| | Human correct | Human incorrect |
|---|---|---|
| QC valid | 282 (TP) | **18 (FP)** |
| QC invalid | 0 (FN) | 23 (TN) |

→ **sensitivity = 1.00** (never rejects a real wound), **specificity = 0.56**.
The 18 misses are the gap. **16 of 18 are Candesartan**, only 2 ALK5i.

**Where the 40 no-wound cases live (decisive for scoping):**
| no-wound | EXP1 | EXP2 | total |
|---|---|---|---|
| Candesartan (EXCLUDED from publication) | 29 | 1 | 30 |
| ALK5i (kept) | 9 | 1 | 10 |
| DMSO / Media (kept) | 0 | 0 | **0** |

So in the *published* cohort the no-wound problem is 10 ALK5i images, 8 already caught → only ~2
missed. The problem is real but **mostly lives in the excluded condition + EXP1**.

Relevant existing infrastructure (do NOT rebuild):
- `library/woundtrack/qc.py` — `verify_wound_by_distribution()` (canonical t=0 QC, X/Y projections)
- `library/verification/` — full GUI (`app.py`), `ground_truth.py` (polygon + edge-correction GT),
  `metrics.py` (Dice/IoU/Hausdorff95/Cohen's κ), `analyze_results.py`
- `docs/verification_results.md` — the written eval (note: this doc has the closure tables
  triplicated and a count discrepancy — claims "3 incorrectly segmented wound-bearing" but the
  xlsx shows only 41−40 = 1 non-"no wound" incorrect; worth reconciling)
- `docs/model_weakness_analysis.md` — W1–W15 catalog. **"No-wound detection" is NOT in it** —
  this would be a new W16. Closest existing: W4 (single global argmin Y-band).

---

## Part 3 — The disputed design (decisions tentatively reached, then questioned)

Walked the design tree via /grill-me. Reached these *tentative* positions before the user soured:

- **Scope = B (CONFIRMED by user):** full pipeline robustness, **condition-agnostic AND
  config-agnostic**, will be **public** (other teams, other cell lines / magnifications /
  modalities). User explicitly accepts **t>0 has no ground truth**.
- **Output contract = Option B (CONFIRMED):** emit a continuous **`wound_presence_score`** (+ its
  sub-signals in the `qc` dict for transparency), with a **self-calibrating** per-dataset decision
  (Otsu/antimode on the score histogram). No fixed magic threshold travels between labs.
- **Candidate signals (all dimensionless, chosen so the *score* transfers even if a threshold
  wouldn't):** (1) variance **contrast ratio** = mean cell-region variance / mean wound-band
  variance; (2) **valley-depth z-score** of the row-mean variance profile; (3) wound-band
  **uniformity CV**.
- **Calibration axes (tentative):** Axis 1 = across wells at t=0 → gates *trajectory admission*
  (validatable against the 40 labels). Axis 2 = across time within a trajectory → gates *per-frame
  validity* (the real t>0 motivation; partly overlaps existing `closure_threshold`). Recommended
  NOT pooling, to preserve temporal-monotonicity as a free sanity check for the unvalidated t>0.
- **Mandatory guard:** a **unimodality test (Hartigan dip)** before any split — a clean all-wound
  plate is unimodal; naive Otsu would manufacture a split and reject real wounds, breaking the
  sensitivity = 1.00 guarantee. Only split if genuinely bimodal.

### The validation argument that the user challenged
Reframed "validation" away from tuning a threshold toward **threshold-free separability**:
- The only thing that must transfer is that the **score ranks** wound > no-wound. Measure with
  **AUROC / AUPRC** on 40 no-wound vs 282 wound-bearing — operating point never enters.
- **Nothing is tuned to the 40 labels.** Parameter classes: (1) per-dataset Otsu cut — fit to the
  *external* data at runtime; (2) universal stats constants (dip α, percentile); (3) the score's
  structural form — **the only leakage channel**, so it must be **fixed a priori from physics and
  NOT iterated to chase AUROC**. The 40 are a one-shot TEST set, never a training set.
- Honest limit stated: 38/40 positives are EXP1, 30/40 Candesartan, one modality — so AUROC
  confirms separability **on Mt Sinai Incucyte brightfield only**. Universality rests on the
  *physical* argument (a wound is lower local-variance than a monolayer in any transmitted-light
  modality; a ratio is dimensionless), with the 40 as a single confirming instance.

### The OPEN question the user pushed back on (unresolved)
**Q4: parameter-free score vs learned fusion.**
- Recommended **A — parameter-free** (e.g. `contrast_ratio` alone, or fixed equal-weight combo),
  with the first empirical step being "does `contrast_ratio` alone separate the 40, threshold-free,
  under leave-one-experiment-out?"
- User's pushback (the trigger for the handoff): *"what are you actually validating? when we have
  an external dataset we will not have a validation, so which parameters are you tuning?"* — i.e.
  skepticism that there's anything legitimate to validate / that self-calibration + "no tuning"
  is coherent. **This was being answered when the user called for the handoff. They are not
  satisfied.**

---

## Why the user may be unhappy (hypotheses to probe next session — ASK, don't assume)

1. **Cost/benefit mismatch:** huge agnostic-design apparatus for a problem that is ~2 missed
   images in the published cohort. Possibly over-engineered for the actual payoff.
2. **The "self-calibrating but nothing to validate" position feels circular** — if the threshold is
   always re-derived per dataset, the user may see the AUROC validation as not validating the thing
   that actually ships (the runtime Otsu cut + dip guard on *unseen* distributions).
3. **t>0 — the case that actually motivated this — has no ground truth**, so the most important
   axis can't be validated at all, which may feel like building on sand.
4. Possible preference for a **simpler, more concrete** mechanism over the AUROC/Otsu/dip-test
   machinery.

---

## Next Steps (when resuming — RE-OPEN, do not implement)

1. [ ] Ask the user *directly* what specifically they dislike (scope? the self-calibration story?
       the cost/benefit? the validation framing?) — map to the 4 hypotheses above.
2. [ ] Consider reframing around the **cheapest defensible win**: a single dimensionless
       `contrast_ratio` reported in the `qc` dict as a **diagnostic**, no automatic rejection —
       lets users see/threshold it themselves. Much smaller surface, still agnostic, no overfit.
3. [ ] Decide whether t>0 is even in scope now given zero ground truth, or whether to first run a
       **read-only analysis** computing `contrast_ratio` over all 325 t=0 frames and plotting the
       distribution split by `notes=="no wound"` — confirm separability *before* any design.
4. [ ] Reconcile the count discrepancy in `docs/verification_results.md` (3 vs 1 incorrect
       wound-bearing) while there.

## Files to Review on Resume

- `library/wound_standard/detector.py` — `_detect_y_band` (root cause, `np.argmin`),
  `_validate_wound_geometry` (shape-only QC, the place a contrast check would slot in),
  `_compute_local_variance`
- `library/core/types.py` — `WoundDetectorConfig`, `WoundResult.qc` dict shape
- `library/woundtrack/qc.py` — canonical t=0 QC (do not duplicate)
- `library/verification/metrics.py` + `docs/verification_results.md` — existing eval & GT
- `config/config.py` — `verification_results` path
- `scripts/tmp_icon_generator.py` — the finished side-quest (only if revisiting figures)

## Constraints to remember

- **No new code in the pipeline until the design is agreed** (user's explicit ordering: reason
  first, code last).
- Monotonic constraint is a biological invariant; Candesartan excluded from publication;
  `verify_wound_by_distribution` is canonical (CLAUDE.md hard rules).
- Reproducibility / agnosticism is the whole point — no threshold tuned to this lab's data may
  ship as a fixed constant.
