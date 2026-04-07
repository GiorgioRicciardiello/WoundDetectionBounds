# Experimental Design and Methods

## Study Overview

This study evaluated the effects of selective pharmacological inhibitors of the renin-angiotensin and transforming growth factor-β (TGF-β) signaling pathways on scratch-wound healing kinetics in immortalized skeletal muscle cell lines. Using automated image segmentation and temporal constraint modeling, we quantified wound closure dynamics over 24 hours in two independent biological replicates across treatment conditions and doses.

---

## 1. Biological Rationale

### 1.1 Background

Cell migration and proliferation are fundamental biological processes governing tissue repair, development, and pathological states including fibrosis and metastatic dissemination (Friedl & Wolf, 2010; Liang et al., 2007). The scratch-wound assay (also termed wound-healing assay) provides a reproducible *in vitro* model for studying collective cell migration in a physiologically relevant two-dimensional geometry (Jonkman et al., 2014). In this assay, a linear cell-free gap is created in a confluent monolayer, and the rate and completeness of wound closure serve as quantitative proxies for migratory and proliferative capacity.

### 1.2 Biological Hypotheses

This study tested two complementary hypotheses:

1. **Renin-Angiotensin System Modulation (Candasertan)**: The angiotensin II type-1 receptor (AT1R) mediates pro-migratory signaling in multiple cell types. We hypothesized that AT1R blockade via Candasertan would attenuate scratch-wound healing.

2. **TGF-β Pathway Inhibition (ALK5i)**: TGF-β signaling promotes epithelial-to-mesenchymal transition (EMT) and cell migration through ALK5 (TGF-β receptor I) activation. We hypothesized that ALK5 inhibition would suppress wound closure kinetics.

### 1.3 Biological Models

Two independent immortalized skeletal muscle cell lines (myoblasts) were employed:
- **Line 1 (iMC ISOR544C)**: Derived from normal muscle tissue
- **Line 2 (iMC MUTR544C)**: Derived from muscular dystrophy tissue (carrying MUTR544 mutation)

This design enabled assessment of whether drug responsiveness differs between normal and dystrophic myoblasts, yielding insights into whether pharmacological interventions have cell-autonomous versus context-dependent effects.

---

## 2. Materials and Methods

### 2.1 Cell Culture

#### 2.1.1 Cell Lines and Maintenance

Two immortalized myoblast cell lines were cultured:
- **iMC ISOR544C** (normal control myoblast)
- **iMC MUTR544C** (dystrophic myoblast with MUTR544 mutation)

Cells were maintained in [**UNKNOWN**: complete growth medium composition]. Environmental conditions during maintenance: [**UNKNOWN**: temperature, CO₂ level]. Cells were routinely tested for mycoplasma contamination using [**UNKNOWN**: method/kit].

#### 2.1.2 Passage and Seeding

Cells were passaged [**UNKNOWN**: frequency, method, trypsin concentration, confluence threshold]. For wound-healing experiments, cells were seeded in [**UNKNOWN**: culture vessel format and cell density] and cultured to confluence prior to wounding. All experiments were conducted using [**UNKNOWN**: passage number protocol].

### 2.2 Experimental Design and Treatment Groups

#### 2.2.1 Study Design Overview

A full factorial experimental design was employed with the following factors:

| Factor | Levels | Description |
|--------|--------|-------------|
| Cell Line | 2 | iMC ISOR544C, iMC MUTR544C |
| Treatment Condition | 4 | DMSO (vehicle), Candasertan, ALK5i, Media (basal control) |
| Concentration | 4 | 0.0 mM, 0.01 mM, 0.1 mM, 1.0 mM |
| Experiment | 2 | EXP1, EXP2 (independent biological replicates) |

This design yielded **2 × 4 × 4 × 2 = 64 treatment conditions** with multiple replicates per condition (n = 100–167 wells per experiment).

#### 2.2.2 Treatment Groups

**Vehicle Control (DMSO)**: Cells received [**UNKNOWN**: DMSO concentration]. This control accounts for potential solvent toxicity.

**Candasertan (AT1R Blocker)**: A selective antagonist of the angiotensin II type-1 receptor. Concentrations tested: 0.01, 0.1, and 1.0 mM.

**ALK5 Inhibitor (TGF-β Pathway Inhibitor)**: A selective inhibitor of ALK5 (TGF-β receptor I), blocking TGF-β–mediated signaling. Concentrations tested: 0.01, 0.1, and 1.0 mM.

**Media Control**: Cells received fresh medium without drug supplementation, providing a basal reference for wound closure in the absence of pharmacological or vehicle effects.

#### 2.2.3 Replication Strategy

Two independent experiments (EXP1, EXP2) were conducted as biological replicates. Each experiment included all treatment conditions and both cell lines. **Total wound regions**: 325 across two experiments (EXP1: 158 images, EXP2: 167 images).

### 2.3 Scratch-Wound Creation

#### 2.3.1 Wounding Protocol

Confluent monolayers were wounded using a standardized mechanical scratch. Wounding was performed [**UNKNOWN**: specific timing post-seeding, instrument used, technique]]. Immediately after wounding, wells were [**UNKNOWN**: rinsing protocol]]. Treatment medium was applied: either DMSO-vehicle, pharmacological drug at specified concentration, or fresh media control. The serum concentration in treatment medium: [**UNKNOWN**].

#### 2.3.2 Temporal Sampling

Time-lapse imaging commenced immediately following wounding (t = 0) and continued for approximately 24 hours. Images were acquired at 1-hour intervals, yielding 20–25 time points per wound trajectory depending on experiment duration. At the earliest time point (t = 0, the "baseline wound"), the wound was fully open, providing a reference for computing fractional closure.

### 2.4 Time-Lapse Microscopy

#### 2.4.1 Imaging Hardware

Microscope system: [**UNKNOWN**: microscope model, objective magnification, numerical aperture, working distance]

Camera system: [**UNKNOWN**: camera type, bit depth, pixel size in µm/pixel]

Field of view dimensions: Approximately 900 × 735 pixels

Illumination mode: [**UNKNOWN**: brightfield, phase-contrast, or other]

#### 2.4.2 Environmental Control During Imaging

Cells were maintained during live-cell imaging at: [**UNKNOWN**: temperature, CO₂ level, humidity]

Environmental control: [**UNKNOWN**: stage incubation chamber specifications]

#### 2.4.3 Image Acquisition Parameters

- **Exposure time**: [**UNKNOWN**]
- **Sampling interval**: Approximately 1 hour
- **Total duration**: ~24 hours (20–25 frames per trajectory)
- **File format**: Images stored as [**UNKNOWN**: bit depth and file format]]
- **Scope**: Single wound region per trajectory

### 2.5 Pharmacological Agents

#### 2.5.1 Compound Information

| Compound | Target | Manufacturer | Stock Concentration |
|----------|--------|--------------|-------------------|
| Candasertan | AT1R | [**UNKNOWN**: manufacturer] | [**UNKNOWN**: stock concentration and solvent] |
| ALK5 Inhibitor | ALK5 (TGF-βR1) | [**UNKNOWN**: manufacturer] | [**UNKNOWN**: stock concentration and solvent] |
| DMSO (vehicle) | N/A | [**UNKNOWN**: manufacturer] | [**UNKNOWN**: concentration used]] |

Working concentrations (0.01–1.0 mM) were prepared: [**UNKNOWN**: preparation protocol, timing, storage]]

#### 2.5.2 Concentration Rationale

Concentrations spanning 0.01–1.0 mM were selected to allow assessment of dose-response relationships across a physiologically relevant range.

---

## 3. Image Analysis and Segmentation

### 3.1 Automated Wound Segmentation

Wound segmentation was performed using the **Quantification** pipeline, a fully automated computational algorithm that operates without user parameter tuning or training data requirements.

#### 3.1.1 Single-Frame Detection

Each image was independently processed using the Quantification multi-stage variance-based detector (full algorithmic details in Quantification methodology paper, Section 2.2):

1. **Local Variance Texture Map**: High variance regions (cell monolayers) were distinguished from low-variance regions (wound channel)

2. **Thresholding and Edge Detection**: Initial wound mask generation

3. **Robust Edge Fitting**: Outlier rejection and boundary localization

4. **Boundary Smoothing**: Noise elimination while preserving sharp transitions

5. **Morphological Refinement**: Topological cleanup

6. **Contour Extraction**: Wound region boundary identification

7. **Area Calculation**: Pixel-based area measurement

#### 3.1.2 Temporal Constraint Enforcement (Monotonic Closure, Kalman-filtered by default; hard constraint available via `use_kalman=False`)

To encode the biological axiom that scratch wounds can only close (never expand), the algorithm enforces a **monotonic non-increasing constraint** on wound area across the temporal sequence:

$$A(t+1) \leq A(t) \quad \forall \, t \geq 0$$

This is implemented at the per-column level: for each image column x, the upper edge u(x, t) and lower edge ℓ(x, t) from frame t are constrained to move inward (or remain static) relative to frame t−1. Mathematically:

$$u(x, t) \geq u(x, t-1) \quad \text{(upper edge moves down, or stays put)}$$
$$\ell(x, t) \leq \ell(x, t-1) \quad \text{(lower edge moves up, or stays put)}$$

This per-column constraint is strictly stronger than enforcing only the aggregate area constraint, ensuring spatial coherence and eliminating apparent wound re-opening due to noise.

#### 3.1.3 Quality Control Criteria

Each segmentation was automatically assessed using variance-profile heuristics to classify each segmentation as valid or invalid. The QC flag output was subsequently validated against manual expert review (Section 3.2).

**QC Algorithm Validation Results:**
- Overall agreement with human reviewer (all images, n=323): 94.4% (Cohen's κ = 0.69)
- Sensitivity (wound-bearing images): 100% (all correctly segmented images flagged as valid)
- Specificity (wound-bearing images): 33% (2 of 3 incorrect segmentations flagged as invalid)

### 3.2 Manual Verification and Ground-Truth Annotation

#### 3.2.1 Verification Protocol

A subset of 325 baseline (t=0) images was subjected to manual expert review using an interactive web-based GUI. A single expert reviewer (blinded to treatment condition) independently assessed each segmentation as:
- **Correct**: Wound boundary accurately reflects the visible cell-free gap
- **Incorrect**: Boundary misaligns with wound region, includes non-wound pixels, or exhibits topological errors
- **No wound**: Image contains no visible wound and should be excluded from analysis

#### 3.2.2 Validation Metrics

For images marked as "correct" and containing a visible wound (n = 282 after exclusions):
- **Pixel-level metrics** (Dice coefficient, IoU, precision, recall) were computed for a subset of 5 images where the reviewer manually traced polygon annotations. These served as ground-truth masks for quantitative evaluation.

#### 3.2.3 Image Exclusion Criteria

Images were excluded from analysis if:
1. The image contained no visible wound ("no wound" annotation) — n = 40 images excluded
2. The image was unannotated — n = 2 images excluded
3. The image was marked as incorrectly segmented — n = 3 images excluded (but included in QC sensitivity analysis)

This yielded a final validated cohort of **282 trajectories** (86.8% of the initial 325 images) suitable for quantitative wound healing dynamics analysis.

### 3.3 Fractional Wound Closure Computation

#### 3.3.1 Monotonic Smoothing

Raw wound area measurements were corrected for noise-induced fluctuations using piecewise cubic Hermite interpolation (PCHIP) with a cumulative minimum enforcement:

$$A_{\text{corrected}}(t) = \min\bigl(A(t), A_{\text{corrected}}(t-1)\bigr)$$

This ensures that the corrected trajectory is strictly monotonically non-increasing while preserving the interpolated shape of the original data at maximum extent.

#### 3.3.2 Fractional Closure Definition

Fractional wound closure was defined as:

$$f(t) = \frac{A(0) - A_{\text{corrected}}(t)}{A(0)}$$

where A(0) is the wound area at baseline (t=0) and A_corrected(t) is the monotonically smoothed area at time t. This metric ranges from 0 (no closure) to 1 (complete closure).

#### 3.3.3 Time Grid Alignment

Per-trajectory measurements were acquired at irregular time intervals (nominally 1 hour, but with slight acquisition delays). To enable population-level averaging, time series were aligned to a common grid with 0.5-hour resolution using linear interpolation. Target times ranged from 0 to 1440 minutes (24 hours), yielding 49 aligned time points per trajectory.

---

## 4. Statistical Analysis

### 4.1 Descriptive Statistics

#### 4.1.1 Sample Size and Composition

The final analyzed cohort comprised:
- **Total trajectories**: 282 (after exclusion of 40 no-wound and 3 incorrectly segmented)
- **Cell lines**: iMC ISOR544C (n = 145), iMC MUTR544C (n = 137)
- **Treatment conditions**: DMSO (n = 100), Candasertan (n = 86), ALK5i (n = 55), Media (n = 41)
- **Experiments**: EXP1 (n = 140), EXP2 (n = 142)

Counts per condition and experiment are shown in the results section.

#### 4.1.2 Time-Point Statistics

At each aligned time point, population-level statistics were computed:

$$\bar{f}(t) = \frac{1}{N_{\text{condition}}} \sum_{i=1}^{N_{\text{condition}}} f_i(t)$$

$$\text{SEM}(t) = \frac{\text{SD}(t)}{\sqrt{N_{\text{condition}}}}$$

where $\bar{f}(t)$ is the mean fractional closure and SEM is the standard error of the mean per condition at time t.

### 4.2 Wound Closure Kinetics

#### 4.2.1 Closure at Fixed Timepoints

Fractional closure was reported at:
- **12 hours**: Early timepoint
- **24 hours**: Late timepoint (end of 24-hour observation window)

#### 4.2.2 Time to 50% Closure

For each condition, the time (in hours) at which the population mean fractional closure reached 50% was estimated via linear interpolation between bracketing time points. If not reached within 24 hours, noted as "not reached."

### 4.3 Concentration-Response Analysis

Fractional closure at 24 hours was compared across drug concentrations (0.01, 0.1, 1.0 mM) within each drug condition (Candasertan and ALK5i).

### 4.4 Cell Line Comparisons

Fractional closure trajectories were compared between the two cell lines (iMC ISOR544C vs. iMC MUTR544C) across all conditions.

### 4.5 Experimental Reproducibility

Inter-experiment reproducibility was assessed by comparing results between EXP1 and EXP2 within each condition.

### 4.6 Image Segmentation Validation

#### 4.6.1 Detection Accuracy

The automated segmentation algorithm's accuracy was assessed on the 285 wound-bearing images (excluding the 40 no-wound and 2 unannotated images) using:

$$\text{Accuracy} = \frac{\text{# correctly segmented images}}{\text{Total wound-bearing images}} \times 100\%$$

Accuracy was stratified by treatment condition and experiment to assess condition-specific performance.

#### 4.6.2 QC Algorithm Evaluation

The automatic QC flag's performance was evaluated against human verdicts using a confusion matrix:

| | Human: Correct | Human: Incorrect |
|---|---|---|
| **QC: Valid** | TP | FP |
| **QC: Invalid** | FN | TN |

Derived metrics:
- **Sensitivity** = TP / (TP + FN): Ability to identify correct segmentations
- **Specificity** = TN / (TN + FP): Ability to identify incorrect segmentations
- **PPV** = TP / (TP + FP): Precision of "valid" predictions
- **NPV** = TN / (TN + FN): Precision of "invalid" predictions
- **Cohen's κ**: Agreement between QC flag and human reviewer, accounting for chance

### 4.7 Pixel-Level Segmentation Quality

For the 5 images where manual polygon annotations were provided, pixel-level metrics were computed:

- **Dice coefficient** = 2|X ∩ Y| / (|X| + |Y|): Measure of overlap (range 0–1)
- **Intersection over Union (IoU)** = |X ∩ Y| / |X ∪ Y|: Jaccard similarity
- **Precision** = TP / (TP + FP): Fraction of predicted pixels that are correct
- **Recall** = TP / (TP + FN): Fraction of true wound pixels that are detected
- **F1 score** = 2(Precision × Recall) / (Precision + Recall): Harmonic mean
- **Hausdorff distance (95th percentile)** = 95th percentile of minimum distances between predicted and ground-truth boundaries (in pixels)

These metrics quantify the spatial fidelity of automated segmentations relative to expert-drawn masks.

### 4.8 Software Implementation and Reproducibility

All analyses were implemented in Python 3.11 using NumPy (vectorized array operations), pandas (data manipulation), and scikit-image (image processing). The Quantification segmentation pipeline is fully deterministic and reproducible; analysis scripts include explicit logging of all parameters and random seeds where applicable. All code and data processing steps are documented in the associated computational repository to enable verification and replication by independent groups.

---

## 5. Study Design Justification

### 5.1 Choice of Model System

Two immortalized myoblast cell lines were used:
- **iMC ISOR544C**: Normal control
- **iMC MUTR544C**: Dystrophic variant (MUTR544 mutation)

This design allows comparison of drug responsiveness between normal and dystrophic cell backgrounds.

### 5.2 Selection of Pharmacological Targets

**Renin-Angiotensin System (Candasertan)**: [**UNKNOWN**: rationale for selecting this target in myoblast wound healing context]

**TGF-β Pathway (ALK5i)**: [**UNKNOWN**: rationale for selecting this target in myoblast wound healing context]

### 5.3 Experimental Controls

- **Vehicle control (DMSO)**: Solvent control for drug compounds
- **Media control**: Basal wound-healing without pharmacological modulation
- **Biological replicates (two experiments)**: EXP1 and EXP2
- **Multiple cell lines**: Normal vs. dystrophic background comparison

### 5.4 Temporal Resolution and Duration

- **Sampling interval**: Approximately 1 hour
- **Total duration**: ~24 hours (20–25 timepoints per trajectory)

This sampling captures the full time course of scratch-wound closure over one day.

### 5.5 Dose-Response Design

Concentrations tested: 0.01, 0.1, and 1.0 mM for each drug. These allow assessment of dose-response relationships.

---

## 6. Reproducibility and Data Availability

### 6.1 Data and Code Availability

- Raw microscopy images: [**UNKNOWN**: archival location and access policy]
- Processed segmentations and quantitative metrics: Available in Excel format
- Quantification segmentation pipeline: [**UNKNOWN**: repository URL and license]
- Analysis scripts: [**UNKNOWN**: repository URL]
- Software version: Python 3.11
- Core dependencies: NumPy, scipy, scikit-image, pandas, matplotlib

### 6.2 Analytical Assumptions

- **Temporal data**: Time series aligned to common 0.5-hour grid; linear interpolation used between points
- **Population statistics**: SEM computed per condition at each timepoint
- **Monotonic closure**: Enforced at algorithm level (Kalman-filtered by default; hard constraint available via `use_kalman=False`)
- **Cell line comparison**: Two lines compared; not assumed *a priori* to show identical responses

---

## References

Standard wound-healing assay literature:
- Liang, C. C., et al. (2007). In vitro scratch assay: a convenient and inexpensive cell migration assay. *Nature Protocols*, 2(2), 329-333.
- Jonkman, J. E., et al. (2014). An introduction to the wound healing assay using live-cell microscopy. *Cell Adhesion & Migration*, 8(5), 440-451.

Quantification algorithm:
- [Quantification methodology reference: See `docs/quantification_methodology_paper.md` in this repository]

[Additional references to be completed based on biological hypotheses and methods]

---

**Document Version**: 1.0
**Last Updated**: March 2026
**Corresponding Author Contact**: [To be filled]
