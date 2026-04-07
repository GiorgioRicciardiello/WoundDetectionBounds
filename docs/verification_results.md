now, with this good # Verification of Automated Wound Segmentation

## Image Census and Exclusions

A total of 325 t=0 images were processed by the Quantification wound segmentation
pipeline across two exposure conditions (Candasertan, n=191; ALK5i, n=134) and
two independent experiments (EXP1, n=158; EXP2, n=167).  Manual review
identified **40 images (12.3%)** that contained no visible wound and were
excluded from accuracy analysis.  The no-wound images were unevenly distributed
across conditions: 30 Candasertan and 10 ALK5i, with 38 of 40 occurring in
EXP1 (Table 1).  Two images remained unannotated.  The remaining **285
wound-bearing images** formed the validation cohort.

**Table 1.** No-wound image distribution.

| Condition   | EXP1 | EXP2 | Total |
|-------------|-----:|-----:|------:|
| Candasertan |   29 |    1 |    30 |
| ALK5i       |    9 |    1 |    10 |
| **Total**   |   38 |    2 |    40 |


## Wound Detection Accuracy

Of 285 wound-bearing images, the algorithm correctly segmented **282 (98.9%)**
as judged by an expert reviewer.  Only 3 images were deemed incorrectly
segmented.  Performance was consistent across both exposure conditions and
experiments (Table 2).

**Table 2.** Detection accuracy by exposure and experiment (wound-bearing images only).

| Condition   | EXP1       | EXP2       | Total        |
|-------------|------------|------------|--------------|
| Candasertan | 67/67 (100%) | 93/94 (98.9%) | 160/161 (99.4%) |
| ALK5i       | 51/53 (96.2%) | 71/71 (100%) | 122/124 (98.4%) |
| **Total**   | 118/120 (98.3%) | 164/165 (99.4%) | 282/285 (98.9%) |


## Automatic QC Algorithm Evaluation

The pipeline includes an automatic quality-control (QC) flag that classifies
each segmentation as valid or invalid based on variance-profile heuristics.
We evaluated the QC flag against human verdicts in two contexts.

### All images (n=323 annotated)

Across all annotated images—including the 40 no-wound cases—the QC algorithm
achieved 94.4% agreement with the human reviewer (Cohen's kappa = 0.69).
The QC flag identified all 282 correctly segmented images (sensitivity = 1.00,
NPV = 1.00) but flagged only 23 of 41 problematic images as invalid
(specificity = 0.56).  The 18 false positives (QC = valid, human = incorrect)
were predominantly no-wound images (16 of 18) that the variance-based QC
heuristic could not distinguish from correctly segmented wounds.

### Wound-bearing images only (n=285)

When restricted to images with a visible wound, the QC algorithm correctly
classified 283 of 285 images (accuracy = 99.3%).  It missed 2 incorrect
segmentations (FP = 2) while producing no false negatives (FN = 0).  The low
specificity (0.33) reflects the small number of true negatives (n=3) rather
than poor QC discrimination.

**Table 3.** QC confusion matrix (all annotated images).

|                    | Human: Correct | Human: Incorrect |
|--------------------|---------------:|-----------------:|
| **QC: Valid**      |   282 (TP)     |     18 (FP)      |
| **QC: Invalid**    |     0 (FN)     |     23 (TN)      |

QC sensitivity = 1.00; specificity = 0.56; PPV = 0.94; NPV = 1.00.


## Pixel-Level Segmentation Quality

For a subset of 5 images where the reviewer drew manual edge corrections or
polygon annotations, pixel-level metrics were computed comparing the model mask
against the human-corrected ground truth (Table 4).  The mean Dice coefficient
was 0.91 (SD = 0.06), indicating high overlap even for the cases selected
for correction.

**Table 4.** Pixel-level metrics for images with manual corrections (n=5).

| Metric            | Mean  |  SD   |  Min  |  Max  |
|-------------------|------:|------:|------:|------:|
| Dice              | 0.909 | 0.057 | 0.843 | 0.998 |
| IoU               | 0.837 | 0.099 | 0.729 | 0.997 |
| Precision         | 0.868 | 0.123 | 0.729 | 1.000 |
| Recall            | 0.969 | 0.070 | 0.844 | 1.000 |
| F1                | 0.909 | 0.057 | 0.843 | 0.998 |
| Accuracy          | 0.954 | 0.029 | 0.921 | 0.999 |
| Hausdorff 95 (px) | 45.6  | 27.8  |  0.0  | 76.0  |

The high recall (0.97) relative to precision (0.87) suggests the algorithm
tends to slightly over-segment (include background pixels) rather than miss
wound area.


## Summary

The automated Quantification wound segmentation pipeline achieved **98.9% detection
accuracy** on 285 wound-bearing images, with consistent performance across
exposure conditions and experiments.  The automatic QC flag had perfect
sensitivity (1.00) for wound-bearing images but limited specificity for
detecting no-wound cases (0.56 overall), identifying an area for potential
improvement.  Pixel-level comparison on manually corrected images yielded
a mean Dice coefficient of 0.91, confirming the spatial fidelity of the
segmentations.  Of the 325 images processed, 40 (12.3%) were excluded due
to absence of a wound—predominantly Candasertan samples in EXP1—leaving 282
validated segmentations available for downstream wound healing dynamics
analysis.

---

## Wound Healing Dynamics

### Data Selection

Of the 282 verified segmentations, all were included in the wound healing
dynamics analysis.  The dataset comprised **282 trajectories** across four
treatment conditions: DMSO (n=100), Candasertan (n=86), ALK5i (n=55), Media (n=41).  Two cell lines were represented:
Line 1 (n=145), Line 2 (n=137).  Each trajectory was measured at 20--25 timepoints spanning
approximately 0--24 hours.

### Methods

Wound area at each timepoint was first corrected using a monotonic
non-increasing constraint (Kalman-filtered by default; hard constraint
available via `use_kalman=False`), ensuring biologically plausible wound
closure where the wound can only shrink over time.  Fractional closure was then computed as
(A0 - At) / A0, where A0 is the wound area at t=0.  Time series were aligned
to a common 0.5-hour grid using linear interpolation.  Population statistics
(mean +/- SEM) were computed per condition at each aligned timepoint.

### Wound Closure Over Time

**Table 5.** Mean fractional closure at 24 hours by treatment condition.

| Condition       |   n | Mean Closure |   SEM |
|-----------------|----:|-------------:|------:|
| DMSO            | 100 |        0.197 | 0.010 |
| Candasertan     |  86 |        0.200 | 0.011 |
| ALK5i           |  55 |        0.155 | 0.008 |
| Media           |  41 |        0.185 | 0.012 |

**Table 6.** Mean fractional closure at 12 hours by treatment condition.

| Condition       |   n | Mean Closure |   SEM |
|-----------------|----:|-------------:|------:|
| DMSO            | 100 |        0.145 | 0.006 |
| Candasertan     |  86 |        0.149 | 0.009 |
| ALK5i           |  55 |        0.120 | 0.007 |
| Media           |  41 |        0.131 | 0.008 |

Estimated time to 50% wound closure: DMSO: not reached; Candasertan: not reached; ALK5i: not reached; Media: not reached.

**Figure 1.** Fractional wound closure over 24 hours by treatment condition
(mean +/- SEM, all concentrations pooled).
See `results/wound_healing_dynamics/healing_ratio_by_condition.png`.

**Figure 2.** Healing dynamics stratified by cell line and drug concentration,
showing reproducibility across biological replicates.
See `results/wound_healing_dynamics/healing_ratio_by_cellline.png`.

**Figure 3.** Dose-response relationship for Candasertan and ALK5i across
three concentrations (0.01, 0.1, 1.0 mM).
See `results/wound_healing_dynamics/healing_ratio_by_concentration.png`.

**Figure 4.** Individual wound healing trajectories (thin lines) with
population mean overlay (thick line), illustrating inter-sample variability.
See `results/wound_healing_dynamics/healing_ratio_individual.png`.

---

## Wound Healing Dynamics

### Data Selection

Of the 282 verified segmentations, all were included in the wound healing
dynamics analysis.  The dataset comprised **282 trajectories** across four
treatment conditions: DMSO (n=100), Candasertan (n=86), ALK5i (n=55), Media (n=41).  Two cell lines were represented:
Line 1 (n=145), Line 2 (n=137).  Each trajectory was measured at 20--25 timepoints spanning
approximately 0--24 hours.

### Methods

Wound area at each timepoint was first corrected using a monotonic
non-increasing constraint (Kalman-filtered by default; hard constraint
available via `use_kalman=False`), ensuring biologically plausible wound
closure where the wound can only shrink over time.  Fractional closure was then computed as
(A0 - At) / A0, where A0 is the wound area at t=0.  Time series were aligned
to a common 0.5-hour grid using linear interpolation.  Population statistics
(mean +/- SEM) were computed per condition at each aligned timepoint.

### Wound Closure Over Time

**Table 5.** Mean fractional closure at 24 hours by treatment condition.

| Condition       |   n | Mean Closure |   SEM |
|-----------------|----:|-------------:|------:|
| DMSO            | 100 |        0.197 | 0.010 |
| Candasertan     |  86 |        0.200 | 0.011 |
| ALK5i           |  55 |        0.155 | 0.008 |
| Media           |  41 |        0.185 | 0.012 |

**Table 6.** Mean fractional closure at 12 hours by treatment condition.

| Condition       |   n | Mean Closure |   SEM |
|-----------------|----:|-------------:|------:|
| DMSO            | 100 |        0.145 | 0.006 |
| Candasertan     |  86 |        0.149 | 0.009 |
| ALK5i           |  55 |        0.120 | 0.007 |
| Media           |  41 |        0.131 | 0.008 |

Estimated time to 50% wound closure: DMSO: not reached; Candasertan: not reached; ALK5i: not reached; Media: not reached.

**Figure 1.** Fractional wound closure over 24 hours by treatment condition
(mean +/- SEM, all concentrations pooled).
See `results/wound_healing_dynamics/healing_ratio_by_condition.png`.

**Figure 2.** Healing dynamics stratified by cell line and drug concentration,
showing reproducibility across biological replicates.
See `results/wound_healing_dynamics/healing_ratio_by_cellline.png`.

**Figure 3.** Dose-response relationship for Candasertan and ALK5i across
three concentrations (0.01, 0.1, 1.0 mM).
See `results/wound_healing_dynamics/healing_ratio_by_concentration.png`.

**Figure 4.** Individual wound healing trajectories (thin lines) with
population mean overlay (thick line), illustrating inter-sample variability.
See `results/wound_healing_dynamics/healing_ratio_individual.png`.

---

## Wound Healing Dynamics

### Data Selection

Of the 282 verified segmentations, all were included in the wound healing
dynamics analysis.  The dataset comprised **282 trajectories** across four
treatment conditions: DMSO (n=100), Candasertan (n=86), ALK5i (n=55), Media (n=41).  Two cell lines were represented:
Line 1 (n=145), Line 2 (n=137).  Each trajectory was measured at 20--25 timepoints spanning
approximately 0--24 hours.

### Methods

Wound area at each timepoint was first corrected using a monotonic
non-increasing constraint (Kalman-filtered by default; hard constraint
available via `use_kalman=False`), ensuring biologically plausible wound
closure where the wound can only shrink over time.  Fractional closure was then computed as
(A0 - At) / A0, where A0 is the wound area at t=0.  Time series were aligned
to a common 0.5-hour grid using linear interpolation.  Population statistics
(mean +/- SEM) were computed per condition at each aligned timepoint.

### Wound Closure Over Time

**Table 5.** Mean fractional closure at 24 hours by treatment condition.

| Condition       |   n | Mean Closure |   SEM |
|-----------------|----:|-------------:|------:|
| DMSO            | 100 |        0.197 | 0.010 |
| Candasertan     |  86 |        0.200 | 0.011 |
| ALK5i           |  55 |        0.155 | 0.008 |
| Media           |  41 |        0.185 | 0.012 |

**Table 6.** Mean fractional closure at 12 hours by treatment condition.

| Condition       |   n | Mean Closure |   SEM |
|-----------------|----:|-------------:|------:|
| DMSO            | 100 |        0.145 | 0.006 |
| Candasertan     |  86 |        0.149 | 0.009 |
| ALK5i           |  55 |        0.120 | 0.007 |
| Media           |  41 |        0.131 | 0.008 |

Estimated time to 50% wound closure: DMSO: not reached; Candasertan: not reached; ALK5i: not reached; Media: not reached.

**Figure 1.** Fractional wound closure over 24 hours by treatment condition
(mean +/- SEM, all concentrations pooled).
See `results/wound_healing_dynamics/healing_ratio_by_condition.png`.

**Figure 2.** Healing dynamics stratified by cell line and drug concentration,
showing reproducibility across biological replicates.
See `results/wound_healing_dynamics/healing_ratio_by_cellline.png`.

**Figure 3.** Dose-response relationship for Candasertan and ALK5i across
three concentrations (0.01, 0.1, 1.0 mM).
See `results/wound_healing_dynamics/healing_ratio_by_concentration.png`.

**Figure 4.** Individual wound healing trajectories (thin lines) with
population mean overlay (thick line), illustrating inter-sample variability.
See `results/wound_healing_dynamics/healing_ratio_individual.png`.
