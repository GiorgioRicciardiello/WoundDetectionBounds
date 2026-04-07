# Model Weakness Analysis

Systematic assessment of algorithmic limitations in both wound detection
models and their impact on accurate wound tracking.

---

## Standard Model (`wound_standard/`)

### W1. Column-wise edge extraction used Python for-loops

**File:** `detector.py` :: `_extract_edges_per_column()`
**Severity:** Performance (High)
**Status:** FIXED -- vectorized with `np.argmax` on boolean arrays.

The original code iterated per-column with a nested per-row loop in
Python (~1.3 M comparisons for a 1024x1280 image).  Now uses a single
`np.argmax(below_thresh, axis=0)` call per edge.

### W2. Bare `except:` in RANSAC swallowed all exceptions

**File:** `detector.py` :: `_ransac_single_edge()`
**Severity:** Correctness (Medium)
**Status:** FIXED -- now catches `(np.linalg.LinAlgError, ValueError)`.

A bare `except:` silently swallowed `MemoryError`, `KeyboardInterrupt`,
and genuine bugs.  Only polynomial-fitting errors should trigger a break.

### W3. Fixed threshold heuristics lack adaptation

**File:** `detector.py` :: `_extract_edges_per_column()`
**Severity:** Robustness (Medium)
**Status:** OPEN

The edge-detection threshold is `cell_median * 0.5`.  This assumes:
- Cell regions above/below the wound are pure (no artifacts, borders)
- The variance distribution is unimodal
- 50 % of cell variance is always the wound/cell boundary

**Recommendation:** Use per-column adaptive thresholding or Otsu on the
within-band variance distribution.

### W4. Single global minimum for Y-band detection

**File:** `detector.py` :: `_detect_y_band()`
**Severity:** Robustness (Medium)
**Status:** OPEN

`np.argmin(y_smooth)` finds only one global minimum.  Multiple low-
variance bands (partial closure, artefacts) will confuse this.

**Recommendation:** Use `scipy.signal.find_peaks(-y_smooth)` to detect
all valleys, then select the one with the widest spatial extent.

### W5. Contour scoring dominated by raw width

**File:** `preprocessor.py` :: `_pp_contour_filtering()`
**Severity:** Correctness (Low)
**Status:** FIXED -- `horizontal_extent` is now normalized by `W`.

The original formula `horizontal_extent * fill_ratio * penalty` made
width (hundreds of pixels) dominate the unit-interval terms.

### W6. Gradient-based preprocessing sensitive to contrast

**File:** `preprocessor.py` :: `pre_processing()`
**Severity:** Robustness (Medium)
**Status:** OPEN

Sobel gradient + a fixed 70th-percentile threshold fails on low-contrast
or out-of-focus images where gradients are globally weak.

**Recommendation:** Use local adaptive thresholding (Niblack/Sauvola)
or compute the gradient relative to local statistics.

### W7. Visualization tightly coupled into detection

**File:** (was `wound_identification.py`, `pre_processing.py`, `sequence_segmentation.py`)
**Severity:** Design (Low)
**Status:** FIXED -- all `plot_wound_fit()` / `show()` calls removed
from model code.  Callers handle visualization.

---

## Quantification Model (`wound_quantification/`)

### W8. Per-pixel monotonic constraint is irreversible

**File:** `segmenter.py` :: `_enforce_monotonic()`
**Severity:** Correctness (High)
**Status:** MITIGATED

If one column's edge is mis-detected at frame `t` (shifted inward by an
artefact), all subsequent frames inherit that error permanently for that
column.  There is no relaxation or error-correction mechanism.

**Recommendation:**
- Apply the monotonic constraint to a *spatially smoothed* version of
  the edges (e.g., Savgol across columns) rather than raw per-column values.
- Add a confidence-weighted constraint that allows small violations when
  the current detection has high QC confidence but the previous bound
  looks anomalous.
- Consider a Kalman-filter approach combining prediction (previous bound)
  with observation (current detection) weighted by uncertainty.

**Resolution:** Implemented per-column Kalman filter in
`kalman_constraint.py` (default `use_kalman=True`).  The Kalman filter
assigns high observation noise R to spurious edges, attenuating their
effect.  A hard safety net after the blend preserves the biological
invariant.  To reproduce legacy behaviour, set `use_kalman=False`.

### W9. No sub-pixel accuracy

**File:** `segmenter.py`, `detector.py`
**Severity:** Precision (Medium)
**Status:** OPEN

Both models extract edges at integer pixel resolution.  For thin wounds
close to closure, a 1-pixel quantization error is a significant fraction
of the remaining width.

**Recommendation:** Fit a parabola to the variance profile around the
threshold crossing to obtain sub-pixel edge positions.  Maintain
floating-point edges throughout the pipeline.

### W10. Forced 1-pixel gap prevented full wound closure

**File:** `segmenter.py` :: `_enforce_monotonic()`
**Severity:** Correctness (Medium)
**Status:** FIXED -- columns where `upper >= lower` are now treated as
fully closed (zero wound width) instead of forcing a 1-pixel gap.

The original code set `lower = mid + 1` when edges met, introducing a
systematic area bias at late timepoints.

### W11. No temporal smoothing of detection results

**File:** `segmenter.py`
**Severity:** Precision (Low)
**Status:** MITIGATED

The Quantification model enforces monotonic constraints but does not smooth
results across time.  If the detector oscillates between slightly
different edge positions (within the monotonic bound), the area curve
will be noisy.

**Recommendation:** Apply an exponential moving average or Savgol filter
to the edge positions across time, respecting the monotonic constraint.

**Resolution:** The Kalman filter (`use_kalman=True`, default) provides
temporal smoothing of edge positions via the Kalman state estimate,
weighted by per-frame observation confidence.  This smooths detector
oscillations while respecting the monotonic constraint.

### W12. Mask rebuild used Python for-loop

**File:** `segmenter.py` :: `_enforce_monotonic()`
**Severity:** Performance (High)
**Status:** FIXED -- vectorized with NumPy broadcasting:
`mask = (rows >= y_up) & (rows <= y_lo) & open_cols`

---

## Cross-Model Weaknesses

### W13. No uncertainty quantification

**Severity:** Statistical (High)
**Status:** OPEN

Neither model produces confidence intervals for wound area.  The QC
dict has pass/fail flags but no probabilistic bounds.  Per the CLAUDE.md
requirements for statistical integrity, measurements should carry
uncertainty.

**Recommendation:** Bootstrap area estimates from small perturbations of
the edge positions (e.g., +/- 1--2 pixels sampled from a noise model).

### W14. No physical unit calibration

**Severity:** Analytical (Medium)
**Status:** OPEN

All measurements are in pixels.  The `visualization.py` module has a
`scalebar` parameter but no calibration propagates to area calculations.

**Recommendation:** Add an optional `pixel_size_um` parameter to
`WoundDetectorConfig` and propagate it to `WoundResult.area_um2` and
`SegmentationResult.area_um2`.

### W15. Duplicate `verify_wound_by_distribution` implementations

**File:** `wound_standard/utils.py` and `woundtrack/qc.py`
**Severity:** Maintainability (Medium)
**Status:** MITIGATED -- `filtering/cross_sectional.py` now imports
from `woundtrack/qc.py` (canonical version).  The copy in
`wound_standard/utils.py` is retained for backward compatibility but
should be deprecated in a future release.

---

## Summary Table

| ID  | Model    | Category      | Severity | Status  |
|-----|----------|---------------|----------|---------|
| W1  | Standard | Performance   | High     | FIXED   |
| W2  | Standard | Correctness   | Medium   | FIXED   |
| W3  | Standard | Robustness    | Medium   | OPEN    |
| W4  | Standard | Robustness    | Medium   | OPEN    |
| W5  | Standard | Correctness   | Low      | FIXED   |
| W6  | Standard | Robustness    | Medium   | OPEN    |
| W7  | Standard | Design        | Low      | FIXED   |
| W8  | Quantification   | Correctness   | High     | MITIGATED |
| W9  | Both     | Precision     | Medium   | OPEN    |
| W10 | Quantification   | Correctness   | Medium   | FIXED   |
| W11 | Quantification   | Precision     | Low      | MITIGATED |
| W12 | Quantification   | Performance   | High     | FIXED   |
| W13 | Both     | Statistical   | High     | OPEN    |
| W14 | Both     | Analytical    | Medium   | OPEN    |
| W15 | Both     | Maintenance   | Medium   | MITIGATED |

**Fixed:** 6 | **Open:** 5 | **Mitigated:** 3
