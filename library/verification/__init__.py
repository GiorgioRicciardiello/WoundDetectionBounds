"""
Verification GUI Library
========================

Web-based manual verification tool for Gemini wound segmentation results.

Provides a Flask application that allows reviewers to:
- Visualize t=0 wound detection results (debug panels + raw image with mask)
- Mark each trajectory as correct/incorrect
- Optionally draw ground-truth polygons for quantitative comparison
- Compute pixel-level metrics (Dice, IoU, precision, recall)
- Export annotations and aggregate statistics to Excel

Modules
-------
data_loader : Load master trajectories pickle and extract t=0 records.
metrics     : Pixel-level and aggregate segmentation quality metrics.
ground_truth: Convert user-drawn polygons to binary masks.
export      : Build Excel workbook with per-image and summary sheets.
app         : Flask application with REST API and single-page frontend.
"""
