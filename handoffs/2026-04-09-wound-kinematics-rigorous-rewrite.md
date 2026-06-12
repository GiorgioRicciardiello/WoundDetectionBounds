# Session Handoff: Rigorous Wound Kinematics Module

**Date:** 2026-04-09
**Project:** `C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds`
**Session Duration:** ~1 hour

## Current State

**Task:** Implement a mathematically rigorous replacement for the existing
velocity/distance/closure quantification, addressing axiom violations in the
current column-averaged edge model.
**Phase:** Implementation complete, end-to-end tested on synthetic data.
**Progress:** ~100% for the standalone module; integration with existing
publication pipeline is **not** done (and was intentionally out of scope).

## What We Did

Audited the existing distance/speed/velocity math in `library/filtering/` and
`scripts/publication/generate_sequence.py`, identified 8 axiom/consistency
violations (unweighted column averaging, asymmetric valid columns, `abs()`
before averaging, secular-vs-instantaneous velocity, missing area/boundary
consistency check, lost curvature, frame-index time, peak normalisation),
then implemented a new standalone module `scripts/publication/wound_kinematics.py`
covering all four planned phases plus an orchestrator, and verified with a
synthetic monotonic-closure test.

## Decisions Made

- **Standalone module, zero modifications to existing files** — Keeps
  publication pipeline output reproducible while the new metrics are validated
  against it.
- **Intersection of valid columns** across both edges and all timepoints —
  eliminates mixed-denominator averages; preferred over per-timepoint
  intersection because it guarantees a single consistent spatial domain.
- **Width-weighted averaging using `w0(x) = l(x,0) - u(x,0)`** — aligns
  displacement with area change (the axiom `ΔA = Σ_x [w(x,0) - w(x,T)]`).
- **Signed displacement, not absolute** — closure direction is known *a priori*;
  `abs()` before mean is a modelling error that hides migration reversals.
- **Forward differences for velocity + boundary-filled last point** — simpler
  than central differences, and matches the physical "what changed between
  frame i and i+1" interpretation. Last point is backward-filled to preserve
  array length.
- **Block bootstrap with block size = decorrelation length** — naive SEM
  underestimates uncertainty because columns are spatially autocorrelated. 1/e
  threshold on ACF is the standard decorrelation-length definition.
- **`HOURS_PER_FRAME = 1.0` as configurable default** — docs/experiment_design.md
  says ~1 h intervals (20-25 frames over ~24 h). Not verified against actual
  per-frame timestamps. **The user did NOT confirm this.** See open questions.
- **Area-rate decomposition uses velocities as a proxy** for upper/lower
  front contributions (`v_upper * w0_sum`-style). True per-front boundary
  integral would require splitting the boundary integral expression; the
  current plot approximates it by showing `v_upper` and `v_upper + v_lower`
  stacked. Documented inline.
- **Output directory: `config['publication_dir'] / "kinematics"`** — which
  currently resolves to `manuscript/kinematics/` because `publication_dir`
  was recently repointed. The user did NOT explicitly confirm this choice.

## Code Changes

**Files created:**

- `scripts/publication/wound_kinematics.py` — 840+ line standalone module.
  Public API documented via `__all__`.

**Files NOT modified (intentionally):**

- `library/filtering/cross_sectional.py` — the broken `distance_calculator`
  lives here (abs-before-avg, unweighted, asymmetric columns).
- `library/filtering/timeseries.py` — same issue in `distance_calculator_timeseries`.
- `scripts/publication/generate_sequence.py` — peak-normalised velocities
  in `plot_wound_healing_dynamics`.

**Key code context:**

- `compute_displacement(traj, um_per_pixel)` returns `(d_upper, d_lower, d_mean)`
  — each shape `(T,)`, **signed**, in um, width-weighted.
- `compute_velocity()` — forward-difference per-column velocity, width-weighted,
  um/h. Positive = closing.
- `compute_area_rate()` — both direct (`-ΔA/Δt`) and boundary integral
  (`Σ_x [dl/dt + du/dt] * dx`) returned. Residual is the QC signal.
- `estimate_decorrelation_length()` — ACF along x, 1/e threshold.
- `block_bootstrap_ci()` — reproducible (seeded), resamples contiguous blocks
  of columns of length ≈ decorrelation length.
- `compute_kinematics(trajectory_key, results)` — one-call full pipeline per
  trajectory; returns a frozen `KinematicsResult` dataclass.
- `run_kinematics(trajectories, output_dir)` — top-level orchestrator; writes
  `kinematics_table.xlsx` (long-format, one row per trajectory×time) and
  `kinematics_summary.xlsx` (one row per trajectory, final-timepoint metrics).

**Synthetic validation results (from end-of-session test):**

- Wound band (H=100, W=200) narrowing by 2 px/frame each side over 5 frames.
- `d_upper = [0, 2, 4, 6, 8]` ✓ (exactly 2 px/frame)
- `v_upper[:-1] = 2.0` ✓ (constant 2 px/h)
- `dAdt_direct = dAdt_boundary = 800` ✓ (perfect consistency, residual = 0)
- Decorrelation length = 1 column (expected for perfectly uniform front)

## Open Questions

- [ ] **`HOURS_PER_FRAME` value**: Is it exactly 1.0 for all trajectories? Or
      do per-frame timestamps exist in metadata that should be used for
      irregular intervals? `docs/full_paper.md` says "irregular time intervals
      (nominally 1 hour, but with slight acquisition delays)".
- [ ] **Output directory**: Should kinematics outputs live in `paper_publication/`
      alongside existing figures, or in `manuscript/` (current
      `config['publication_dir']`)? The module currently uses
      `config['publication_dir']`.
- [ ] **Replace or complement** the old `distance_calculator[_timeseries]`?
      The user has not yet said whether `generate_figures.py` should be
      rewired to call `compute_kinematics()` instead of `distance_calculator`.
- [ ] **Area-rate decomposition plot** — currently shows stacked velocities,
      not area-rate-per-column split. Rigorous version would compute
      `upper_contribution(t) = Σ_x du/dt(x,t) * dx` and same for lower,
      both in um²/h. Easy refactor if requested.

## Blockers / Issues

- **Not run against real data yet.** Only synthetic validation has been
  executed. Running `python -m scripts.publication.wound_kinematics` will
  load `trajectories_pickle` and process all trajectories. Bootstrap with
  `n_bootstrap=2000` over ~48 trajectories × ~24 frames × ~1000 columns may
  be slow — consider reducing or parallelising if it's a problem.
- **Consistency residual on real data is unknown.** On synthetic uniform
  closure it's zero, but real edge detection has noise so we expect a
  non-zero residual. Large residuals will flag trajectories with edge-
  detection artifacts — this is a feature, not a bug.

## Context to Remember

- User role: senior research engineer working on scratch-wound healing
  quantification for a publication. Acted here as a "physicist" verifying
  mathematical rigor.
- Two cell lines (Line 1 = iMC ISOR544C, Line 2 = iMC MUTR544C).
- Three conditions: DMSO, Media, Alk5i. **Candesartan excluded from all
  publication results** (enforced by `filter_candesartan()`).
- Incucyte 10x → `UM_PER_PIXEL = 1.24` (defined in `scripts/publication/generate_figures.py:91`
  and replicated at module level in `wound_kinematics.py`).
- `t` values in trajectory pickle are **frame indices**, not hours.
- Monotonic closure constraint is a biological invariant — never bypass it
  silently (see `CLAUDE.md` mandatory constraint #8).
- The existing `distance_calculator` family has an in-code comment flagging
  that `dt = float(t_used)` is frame index, not hours — the issue is known
  but was deferred.

## Next Steps

1. [ ] Run `python -m scripts.publication.wound_kinematics` against the real
      `trajectories.pickle` and inspect the consistency residual distribution.
2. [ ] Confirm with user: `HOURS_PER_FRAME` value, output directory, whether
      to rewire `generate_figures.py`.
3. [ ] If consistency residual reveals problematic trajectories, add a QC
      flag based on residual magnitude.
4. [ ] (Optional) Replace the approximate area-rate decomposition plot with
      a true per-column `Σ_x du/dt * dx` split.
5. [ ] (Optional) Add unit tests in `tests/` covering `compute_displacement`,
      `compute_velocity`, `compute_area_rate`, `block_bootstrap_ci` (reproducibility),
      and `estimate_decorrelation_length`.
6. [ ] (Optional) Update LaTeX methods section (`latexdoc/sections/methods.tex`)
      to describe the new kinematic framework once it's adopted.

## Files to Review on Resume

- `scripts/publication/wound_kinematics.py` — the new module; start with the
  module docstring, then `compute_kinematics()`, then `run_kinematics()`.
- `library/filtering/cross_sectional.py:216` (`distance_calculator`) — the
  legacy implementation being replaced. Useful for side-by-side comparison.
- `library/filtering/timeseries.py:30` (`distance_calculator_timeseries`) —
  same pattern, time-series version.
- `scripts/publication/generate_sequence.py:459` (`_boundary_velocity`) —
  the peak-normalised velocity function that motivated the rewrite.
- `scripts/publication/generate_figures.py` — current consumer of the legacy
  distance/speed functions; the integration target if the user asks to rewire.
- `docs/experiment_design.md` — imaging interval documentation (supports
  `HOURS_PER_FRAME ≈ 1.0`).
- `config/config.py` — `publication_dir` is currently set to `manuscript/`
  (not `paper_publication/`).
