"""
Flask Application
=================

Single-page web application for manual verification of Gemini wound
segmentation results.

Architecture
------------
- REST API serves images (raw + mask + debug PNG) as base64-encoded PNGs.
- Session state (annotations) is persisted to a JSON file on every save
  so the reviewer can close the browser and resume later.
- Metric computation happens server-side (numpy) when the user submits
  polygon vertices from the browser canvas.
- Excel export is triggered via a POST endpoint and the file is served
  for download.

Routes
------
GET  /                        — Main page (single-page app).
GET  /api/records             — JSON list of all trajectory metadata.
GET  /api/image/<key>         — t=0 raw grayscale image as PNG.
GET  /api/mask/<key>          — t=0 model mask as PNG.
GET  /api/debug_png/<key>     — 6-panel debug image from disk.
GET  /api/session             — Current annotation state.
POST /api/annotate            — Save one annotation (verdict + polygons + notes).
POST /api/compute_metrics     — Compute metrics for submitted polygons.
POST /api/export              — Generate Excel and return download URL.
GET  /api/download/<filename> — Download exported file.
GET  /api/edges/<key>        — Upper/lower edge arrays for edge correction mode.
POST /api/compute_edge_metrics — Compute metrics from edge corrections.
"""

from __future__ import annotations

import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
)
from PIL import Image

from library.verification.data_loader import (
    extract_t0_records,
    load_master_trajectories,
)
from library.verification.export import export_results
from library.verification.ground_truth import correct_edges, polygons_to_mask
from library.verification.metrics import compute_pixel_metrics

logger = logging.getLogger(__name__)


# ===================================================================
# Application factory
# ===================================================================

def create_app(
    trajectories_path: str | Path,
    output_dir: str | Path,
) -> Flask:
    """Create and configure the Flask verification application.

    Parameters
    ----------
    trajectories_path : str or Path
        Path to ``trajectories.pickle``.
    output_dir : str or Path
        Directory for session files and exports.

    Returns
    -------
    Flask
        Configured application instance.
    """
    trajectories_path = Path(trajectories_path)
    output_dir = Path(output_dir)

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    # ---- Load data ----
    logger.info("Loading master trajectories from %s ...", trajectories_path)
    trajectories = load_master_trajectories(trajectories_path)
    logger.info("Loaded %d trajectories.", len(trajectories))

    records = extract_t0_records(trajectories, None)
    logger.info("Extracted %d t=0 records for verification.", len(records))

    # Index records by key for fast lookup
    records_by_key: Dict[str, Dict[str, Any]] = {
        r["trajectory_key"]: r for r in records
    }

    # QC lookup for aggregate metrics
    records_qc: Dict[str, bool] = {
        r["trajectory_key"]: r["qc_valid"] for r in records
    }

    # ---- Session persistence ----
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    session_path = output_dir / "verification_session.json"

    def _load_session() -> Dict[str, Any]:
        """Load session from disk, or return empty structure."""
        if session_path.exists():
            try:
                with open(session_path, "r") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt session file, starting fresh.")
        return {"annotations": {}, "last_modified": None}

    def _save_session(session: Dict[str, Any]) -> None:
        """Persist session to disk."""
        session["last_modified"] = datetime.now().isoformat()
        with open(session_path, "w") as fh:
            json.dump(session, fh, indent=2)

    # ---- Helper: numpy array → PNG bytes ----
    def _array_to_png_bytes(arr: np.ndarray, mode: str = "L") -> bytes:
        """Convert a numpy array to PNG-encoded bytes.

        Parameters
        ----------
        arr : np.ndarray
            Image array.  For mode "L": (H, W) uint8.
            For mask visualisation: values {0, 1} are scaled to {0, 255}.
        mode : str
            PIL image mode ("L" for grayscale, "RGBA" for overlay).

        Returns
        -------
        bytes
            PNG-encoded image.
        """
        if mode == "L" and arr.max() <= 1:
            arr = (arr * 255).astype(np.uint8)
        img = Image.fromarray(arr, mode=mode)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    # ===============================================================
    # Routes
    # ===============================================================

    @app.route("/")
    def index() -> str:
        """Serve the main verification page."""
        return render_template("index.html")

    @app.route("/api/records")
    def api_records() -> Response:
        """Return metadata for all t=0 records (no image data).

        Response JSON is a list of objects with keys:
        trajectory_key, qc_valid, exposure, experiment, sample_name,
        original_filename, img_shape.
        """
        session = _load_session()
        annotations = session.get("annotations", {})

        result = []
        for r in records:
            key = r["trajectory_key"]
            ann = annotations.get(key, {})
            result.append({
                "trajectory_key": key,
                "qc_valid": r["qc_valid"],
                "exposure": r["exposure"],
                "experiment": r["experiment"],
                "sample_name": r["sample_name"],
                "original_filename": r["original_filename"],
                "img_shape": r["img_shape"],
                "correct": ann.get("correct"),
                "has_polygon": bool(ann.get("polygons")),
                "dice": ann.get("metrics", {}).get("dice"),
                "notes": ann.get("notes", ""),
            })
        return jsonify(result)

    @app.route("/api/image/<key>")
    def api_image(key: str) -> Response:
        """Serve the t=0 raw grayscale image as PNG."""
        rec = records_by_key.get(key)
        if rec is None:
            return Response("Not found", status=404)
        png_bytes = _array_to_png_bytes(rec["img_raw"], mode="L")
        return Response(png_bytes, mimetype="image/png")

    @app.route("/api/mask/<key>")
    def api_mask(key: str) -> Response:
        """Serve the t=0 model mask as PNG (0/255 grayscale)."""
        rec = records_by_key.get(key)
        if rec is None:
            return Response("Not found", status=404)
        png_bytes = _array_to_png_bytes(rec["mask"], mode="L")
        return Response(png_bytes, mimetype="image/png")

    @app.route("/api/debug_png/<key>")
    def api_debug_png(key: str) -> Response:
        """Serve the 6-panel debug PNG from disk."""
        rec = records_by_key.get(key)
        if rec is None:
            return Response("Not found", status=404)

        debug_path = rec.get("debug_png_path")
        if debug_path is None or not Path(debug_path).exists():
            return Response("Debug PNG not available", status=404)

        return send_file(str(debug_path), mimetype="image/png")

    @app.route("/api/session")
    def api_session() -> Response:
        """Return current session state."""
        session = _load_session()
        return jsonify(session)

    @app.route("/api/annotate", methods=["POST"])
    def api_annotate() -> Response:
        """Save an annotation for one trajectory.

        Expected JSON body::

            {
                "key": "alk5i_b7_1-EXP1-alk5i",
                "correct": true,
                "polygons": [[[x1,y1],[x2,y2],...], ...],
                "notes": "optional text"
            }
        """
        data = request.get_json(force=True)
        key = data.get("key")
        if not key or key not in records_by_key:
            return jsonify({"error": "Invalid trajectory key"}), 400

        session = _load_session()
        annotations = session.setdefault("annotations", {})

        # Preserve existing metrics if not recomputing
        existing = annotations.get(key, {})
        annotations[key] = {
            "correct": data.get("correct"),
            "polygons": data.get("polygons", []),
            "notes": data.get("notes", ""),
            "metrics": existing.get("metrics", {}),
        }

        _save_session(session)
        return jsonify({"status": "ok"})

    @app.route("/api/compute_metrics", methods=["POST"])
    def api_compute_metrics() -> Response:
        """Compute pixel metrics for user-drawn polygons vs model mask.

        Expected JSON body::

            {
                "key": "alk5i_b7_1-EXP1-alk5i",
                "polygons": [[[x1,y1],[x2,y2],...], ...]
            }

        Returns
        -------
        JSON with all per-image metrics (dice, iou, precision, recall, ...).
        """
        data = request.get_json(force=True)
        key = data.get("key")
        polygons = data.get("polygons", [])

        rec = records_by_key.get(key)
        if rec is None:
            return jsonify({"error": "Invalid trajectory key"}), 400

        if not polygons or not any(len(p) >= 3 for p in polygons):
            return jsonify({"error": "Need at least one polygon with >= 3 vertices"}), 400

        # Filter out degenerate polygons
        valid_polygons = [p for p in polygons if len(p) >= 3]

        # Build ground-truth mask from user polygons
        manual_mask = polygons_to_mask(
            [[(pt[0], pt[1]) for pt in poly] for poly in valid_polygons],
            img_shape=rec["img_raw"].shape,
        )

        # Compute metrics against model mask
        metrics = compute_pixel_metrics(rec["mask"], manual_mask)

        # Persist metrics in session
        session = _load_session()
        annotations = session.setdefault("annotations", {})
        ann = annotations.setdefault(key, {})
        ann["metrics"] = metrics
        ann["polygons"] = polygons
        _save_session(session)

        return jsonify(metrics)

    @app.route("/api/export", methods=["POST"])
    def api_export() -> Response:
        """Generate Excel export and return the filename for download."""
        session = _load_session()
        annotations = session.get("annotations", {})

        # Build metadata list for export
        records_metadata = [
            {
                "trajectory_key": r["trajectory_key"],
                "original_filename": r["original_filename"],
                "exposure": r["exposure"],
                "experiment": r["experiment"],
                "sample_name": r["sample_name"],
            }
            for r in records
        ]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_filename = f"verification_results_{timestamp}.xlsx"
        export_path = output_dir / export_filename

        export_results(annotations, records_metadata, records_qc, export_path)

        return jsonify({"filename": export_filename, "path": str(export_path)})

    @app.route("/api/download/<filename>")
    def api_download(filename: str) -> Response:
        """Download an exported file."""
        return send_from_directory(str(output_dir), filename, as_attachment=True)

    @app.route("/api/bulk_annotate", methods=["POST"])
    def api_bulk_annotate() -> Response:
        """Bulk-set verdicts based on QC status.

        Expected JSON body::

            {"action": "approve_qc_valid" | "reject_qc_invalid"}
        """
        data = request.get_json(force=True)
        action = data.get("action")

        session = _load_session()
        annotations = session.setdefault("annotations", {})

        count = 0
        for r in records:
            key = r["trajectory_key"]
            existing = annotations.get(key, {})
            # Only modify un-annotated images
            if existing.get("correct") is not None:
                continue

            if action == "approve_qc_valid" and r["qc_valid"]:
                annotations.setdefault(key, {})["correct"] = True
                annotations[key].setdefault("polygons", [])
                annotations[key].setdefault("notes", "")
                annotations[key].setdefault("metrics", {})
                count += 1
            elif action == "reject_qc_invalid" and not r["qc_valid"]:
                annotations.setdefault(key, {})["correct"] = False
                annotations[key].setdefault("polygons", [])
                annotations[key].setdefault("notes", "")
                annotations[key].setdefault("metrics", {})
                count += 1

        _save_session(session)
        return jsonify({"status": "ok", "modified": count})

    # ---- Edge correction endpoints ----

    @app.route("/api/edges/<key>")
    def api_edges(key: str) -> Response:
        """Return upper and lower edge arrays as JSON lists.

        Used by the edge correction drawing mode so the browser can
        render the model boundaries and let the user draw corrections.
        """
        rec = records_by_key.get(key)
        if rec is None:
            return Response("Not found", status=404)

        upper = rec.get("upper_edge")
        lower = rec.get("lower_edge")
        if upper is None or lower is None:
            return jsonify({"error": "Edge data not available"}), 404

        return jsonify({
            "upper": upper.tolist(),
            "lower": lower.tolist(),
        })

    @app.route("/api/compute_edge_metrics", methods=["POST"])
    def api_compute_edge_metrics() -> Response:
        """Compute metrics from edge correction data.

        Expected JSON body::

            {
                "key": "alk5i_b7_1-EXP1-alk5i",
                "corrections": [
                    {"edge": "upper", "points": [[x1,y1],[x2,y2],...]},
                    {"edge": "lower", "points": [[x1,y1],[x2,y2],...]}
                ]
            }

        The corrections are merged with the model's original edges to
        produce a corrected mask.  Metrics compare the corrected mask
        (ground truth) against the original model mask.
        """
        data = request.get_json(force=True)
        key = data.get("key")
        corrections = data.get("corrections", [])

        rec = records_by_key.get(key)
        if rec is None:
            return jsonify({"error": "Invalid trajectory key"}), 400

        upper = rec.get("upper_edge")
        lower = rec.get("lower_edge")
        if upper is None or lower is None:
            return jsonify({"error": "Edge data not available"}), 400

        if not corrections:
            return jsonify({"error": "No corrections provided"}), 400

        try:
            _, _, corrected_mask = correct_edges(
                upper, lower, corrections, rec["img_raw"].shape
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        metrics = compute_pixel_metrics(rec["mask"], corrected_mask)

        # Persist in session
        session = _load_session()
        annotations = session.setdefault("annotations", {})
        ann = annotations.setdefault(key, {})
        ann["metrics"] = metrics
        ann["edge_corrections"] = corrections
        _save_session(session)

        return jsonify(metrics)

    return app
