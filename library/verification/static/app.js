/**
 * Wound Verification GUI — Frontend Logic
 * ========================================
 *
 * Two drawing modes:
 *
 * 1. **Edge correction** (default) — The model's upper/lower boundary
 *    lines are shown on the canvas.  The user clicks points along the
 *    correct boundary within an x-range.  The system interpolates
 *    between the points to produce a corrected edge.  Multiple
 *    correction segments are supported (upper and lower independently).
 *    This is fast: 3–5 clicks to fix a boundary segment.
 *
 * 2. **Full polygon** — Same as before: click vertices to draw an
 *    arbitrary polygon around the wound.  For cases where the mask is
 *    completely wrong.
 *
 * Auto-advance: pressing Correct/Incorrect immediately saves the
 * annotation and advances to the next image.
 */

"use strict";

// ===================================================================
// State
// ===================================================================

/** @type {Array<Object>} All trajectory records from server */
let allRecords = [];

/** @type {Array<Object>} Currently filtered/sorted records */
let displayRecords = [];

/** @type {number} Index into displayRecords for the active image */
let currentIndex = -1;

/** @type {string|null} Current trajectory key */
let currentKey = null;

/** @type {boolean|null} Current verdict (true/false/null) */
let currentVerdict = null;

// ---- Drawing mode ----
/** "edge" or "polygon" */
let drawMode = "edge";

// ---- Polygon mode state ----
let currentPolygon = [];
let closedPolygons = [];

// ---- Edge correction mode state ----
/** @type {Array<number>|null} Model upper edge (W values) */
let modelUpper = null;
/** @type {Array<number>|null} Model lower edge (W values) */
let modelLower = null;
/** Points being drawn for the current edge segment */
let currentEdgePoints = [];
/** Which edge is being corrected: "upper" or "lower" */
let currentEdgeTarget = "upper";
/** Completed edge correction segments: [{edge, points}, ...] */
let edgeCorrections = [];

// ---- Image state ----
/** @type {HTMLImageElement|null} */
let rawImage = null;
/** @type {HTMLImageElement|null} */
let maskImage = null;

/** Sort state */
let sortState = { field: "trajectory_key", ascending: true };


// ===================================================================
// DOM references
// ===================================================================

const tbody = document.getElementById("records-tbody");
const debugImg = document.getElementById("debug-img");
const canvas = document.getElementById("annotation-canvas");
const ctx = canvas.getContext("2d");

const currentKeyEl = document.getElementById("current-key");
const currentFilenameEl = document.getElementById("current-filename");
const progressText = document.getElementById("progress-text");
const progressDetail = document.getElementById("progress-detail");
const metricsSection = document.getElementById("metrics-section");
const metricsGrid = document.getElementById("metrics-grid");
const notesInput = document.getElementById("notes-input");

const filterExposure = document.getElementById("filter-exposure");
const filterStatus = document.getElementById("filter-status");

const edgeToolbar = document.getElementById("edge-toolbar");
const polygonToolbar = document.getElementById("polygon-toolbar");
const hintEdge = document.getElementById("hint-edge");
const hintPolygon = document.getElementById("hint-polygon");
const verdictFlash = document.getElementById("verdict-flash");


// ===================================================================
// Initialization
// ===================================================================

document.addEventListener("DOMContentLoaded", async () => {
    allRecords = await fetchJSON("/api/records");
    populateFilters();
    applyFiltersAndSort();
    renderTable();
    updateProgress();
    bindEvents();
});


// ===================================================================
// Data fetching
// ===================================================================

async function fetchJSON(url, options) {
    const resp = await fetch(url, options);
    return resp.json();
}


// ===================================================================
// Table rendering
// ===================================================================

function populateFilters() {
    const exposures = [...new Set(allRecords.map(r => r.exposure))].sort();
    for (const exp of exposures) {
        const opt = document.createElement("option");
        opt.value = exp;
        opt.textContent = exp;
        filterExposure.appendChild(opt);
    }
}

function applyFiltersAndSort() {
    let filtered = allRecords;

    const expFilter = filterExposure.value;
    if (expFilter) {
        filtered = filtered.filter(r => r.exposure === expFilter);
    }

    const statusFilter = filterStatus.value;
    if (statusFilter === "pending") {
        filtered = filtered.filter(r => r.correct === null || r.correct === undefined);
    } else if (statusFilter === "correct") {
        filtered = filtered.filter(r => r.correct === true);
    } else if (statusFilter === "incorrect") {
        filtered = filtered.filter(r => r.correct === false);
    }

    const { field, ascending } = sortState;
    filtered.sort((a, b) => {
        let va = a[field], vb = b[field];
        if (va === null || va === undefined) va = "";
        if (vb === null || vb === undefined) vb = "";
        if (typeof va === "string") va = va.toLowerCase();
        if (typeof vb === "string") vb = vb.toLowerCase();
        if (va < vb) return ascending ? -1 : 1;
        if (va > vb) return ascending ? 1 : -1;
        return 0;
    });

    displayRecords = filtered;
}

function renderTable() {
    tbody.innerHTML = "";
    displayRecords.forEach((rec, idx) => {
        const tr = document.createElement("tr");
        if (rec.trajectory_key === currentKey) tr.classList.add("active");

        const tdIdx = document.createElement("td");
        tdIdx.className = "col-idx";
        tdIdx.textContent = idx + 1;
        tr.appendChild(tdIdx);

        const tdKey = document.createElement("td");
        tdKey.className = "col-key";
        tdKey.textContent = rec.trajectory_key;
        tdKey.title = rec.trajectory_key;
        tr.appendChild(tdKey);

        const tdExp = document.createElement("td");
        tdExp.className = "col-exp";
        tdExp.textContent = rec.exposure;
        tr.appendChild(tdExp);

        const tdQC = document.createElement("td");
        tdQC.className = "col-qc";
        const qcBadge = document.createElement("span");
        qcBadge.className = "badge " + (rec.qc_valid ? "badge-pass" : "badge-fail");
        qcBadge.textContent = rec.qc_valid ? "OK" : "X";
        tdQC.appendChild(qcBadge);
        tr.appendChild(tdQC);

        const tdVerdict = document.createElement("td");
        tdVerdict.className = "col-verdict";
        const vBadge = document.createElement("span");
        if (rec.correct === true) {
            vBadge.className = "badge badge-correct";
            vBadge.textContent = "Y";
        } else if (rec.correct === false) {
            vBadge.className = "badge badge-incorrect";
            vBadge.textContent = "N";
        } else {
            vBadge.className = "badge badge-pending";
            vBadge.textContent = "?";
        }
        tdVerdict.appendChild(vBadge);
        tr.appendChild(tdVerdict);

        const tdDice = document.createElement("td");
        tdDice.className = "col-dice";
        tdDice.textContent = rec.dice != null ? rec.dice.toFixed(3) : "-";
        tr.appendChild(tdDice);

        tr.addEventListener("click", () => selectImage(idx));
        tbody.appendChild(tr);
    });
}

function updateProgress() {
    const total = allRecords.length;
    const annotated = allRecords.filter(r => r.correct !== null && r.correct !== undefined).length;
    const correct = allRecords.filter(r => r.correct === true).length;
    const incorrect = allRecords.filter(r => r.correct === false).length;
    const withPolygon = allRecords.filter(r => r.has_polygon).length;

    progressText.textContent = `${annotated} / ${total} annotated`;
    progressDetail.textContent =
        `${correct} correct | ${incorrect} incorrect | ${withPolygon} with corrections`;
}


// ===================================================================
// Image selection and loading
// ===================================================================

async function selectImage(idx) {
    if (idx < 0 || idx >= displayRecords.length) return;

    currentIndex = idx;
    const rec = displayRecords[idx];
    currentKey = rec.trajectory_key;

    currentKeyEl.textContent = rec.trajectory_key;
    currentFilenameEl.textContent = rec.original_filename || "";

    // Load debug PNG
    debugImg.src = `/api/debug_png/${encodeURIComponent(currentKey)}`;

    // Reset all drawing state
    currentPolygon = [];
    closedPolygons = [];
    currentEdgePoints = [];
    edgeCorrections = [];
    modelUpper = null;
    modelLower = null;
    currentVerdict = rec.correct;
    verdictWhenLoaded = rec.correct;  // Track initial state for auto-advance logic
    notesInput.value = rec.notes || "";
    metricsSection.style.display = "none";

    updateVerdictButtons();

    // Load raw image + mask + edges in parallel
    const [img, mask, edgesResp] = await Promise.all([
        loadImage(`/api/image/${encodeURIComponent(currentKey)}`),
        loadImage(`/api/mask/${encodeURIComponent(currentKey)}`),
        fetchJSON(`/api/edges/${encodeURIComponent(currentKey)}`),
    ]);

    rawImage = img;
    maskImage = mask;

    if (edgesResp && edgesResp.upper) {
        modelUpper = edgesResp.upper;
        modelLower = edgesResp.lower;
    }

    canvas.width = rawImage.naturalWidth;
    canvas.height = rawImage.naturalHeight;

    // Load existing corrections/polygons from session
    try {
        const session = await fetchJSON("/api/session");
        const ann = session.annotations && session.annotations[currentKey];
        if (ann) {
            if (ann.edge_corrections && ann.edge_corrections.length > 0) {
                edgeCorrections = ann.edge_corrections;
            }
            if (ann.polygons && ann.polygons.length > 0) {
                closedPolygons = ann.polygons;
            }
            if (ann.metrics && ann.metrics.dice != null) {
                showMetrics(ann.metrics);
            }
        }
    } catch (_) { /* ignore */ }

    redrawCanvas();

    // Highlight active row and scroll into view
    document.querySelectorAll("#records-tbody tr").forEach((tr, i) => {
        tr.classList.toggle("active", i === idx);
        if (i === idx) tr.scrollIntoView({ block: "nearest" });
    });
}

function loadImage(url) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = url;
    });
}


// ===================================================================
// Canvas drawing
// ===================================================================

/**
 * Redraw the annotation canvas.
 *
 * Layer order:
 * 1. Raw grayscale image
 * 2. Model mask overlay (semi-transparent red)
 * 3. Model edge lines (cyan/magenta)
 * 4. Edge correction segments (green)
 * 5. Current edge points being drawn (orange)
 * 6. Closed polygon fills + outlines (blue)
 * 7. Current polygon being drawn (orange dashed)
 */
function redrawCanvas() {
    if (!rawImage) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Raw image
    ctx.drawImage(rawImage, 0, 0);

    // 2. Model mask overlay
    if (document.getElementById("toggle-mask").checked && maskImage) {
        ctx.globalAlpha = 0.3;
        const tmpCanvas = document.createElement("canvas");
        tmpCanvas.width = canvas.width;
        tmpCanvas.height = canvas.height;
        const tmpCtx = tmpCanvas.getContext("2d");
        tmpCtx.drawImage(maskImage, 0, 0);
        const imageData = tmpCtx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        for (let i = 0; i < data.length; i += 4) {
            if (data[i] > 128) {
                data[i] = 255; data[i + 1] = 0; data[i + 2] = 0; data[i + 3] = 180;
            } else {
                data[i + 3] = 0;
            }
        }
        tmpCtx.putImageData(imageData, 0, 0);
        ctx.drawImage(tmpCanvas, 0, 0);
        ctx.globalAlpha = 1.0;
    }

    // 3. Model edge lines
    if (document.getElementById("toggle-edges").checked && modelUpper && modelLower) {
        drawEdgeLine(modelUpper, "#00bcd4", 1.5);  // cyan = upper
        drawEdgeLine(modelLower, "#e91e63", 1.5);  // magenta = lower
    }

    // 4. Completed edge correction segments (green)
    for (const corr of edgeCorrections) {
        if (corr.points.length >= 2) {
            ctx.beginPath();
            ctx.moveTo(corr.points[0][0], corr.points[0][1]);
            for (let i = 1; i < corr.points.length; i++) {
                ctx.lineTo(corr.points[i][0], corr.points[i][1]);
            }
            ctx.strokeStyle = corr.edge === "upper" ? "#2ecc71" : "#9b59b6";
            ctx.lineWidth = 3;
            ctx.stroke();

            // Draw vertices
            for (const pt of corr.points) {
                ctx.beginPath();
                ctx.arc(pt[0], pt[1], 4, 0, Math.PI * 2);
                ctx.fillStyle = corr.edge === "upper" ? "#2ecc71" : "#9b59b6";
                ctx.fill();
            }
        }
    }

    // 5. Current edge points being drawn (orange)
    if (drawMode === "edge" && currentEdgePoints.length > 0) {
        ctx.beginPath();
        ctx.moveTo(currentEdgePoints[0][0], currentEdgePoints[0][1]);
        for (let i = 1; i < currentEdgePoints.length; i++) {
            ctx.lineTo(currentEdgePoints[i][0], currentEdgePoints[i][1]);
        }
        ctx.strokeStyle = "#e67e22";
        ctx.lineWidth = 2.5;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        for (let i = 0; i < currentEdgePoints.length; i++) {
            const pt = currentEdgePoints[i];
            ctx.beginPath();
            ctx.arc(pt[0], pt[1], 4, 0, Math.PI * 2);
            ctx.fillStyle = "#e67e22";
            ctx.fill();
        }
    }

    // 6. Closed polygons (polygon mode)
    const showFill = document.getElementById("toggle-polygon").checked;
    for (const poly of closedPolygons) {
        if (poly.length < 3) continue;
        ctx.beginPath();
        ctx.moveTo(poly[0][0], poly[0][1]);
        for (let i = 1; i < poly.length; i++) {
            ctx.lineTo(poly[i][0], poly[i][1]);
        }
        ctx.closePath();
        if (showFill) {
            ctx.fillStyle = "rgba(41, 128, 185, 0.25)";
            ctx.fill();
        }
        ctx.strokeStyle = "#2980b9";
        ctx.lineWidth = 2;
        ctx.stroke();
        for (const pt of poly) {
            ctx.beginPath();
            ctx.arc(pt[0], pt[1], 3, 0, Math.PI * 2);
            ctx.fillStyle = "#2980b9";
            ctx.fill();
        }
    }

    // 7. Current polygon being drawn (polygon mode)
    if (drawMode === "polygon" && currentPolygon.length > 0) {
        ctx.beginPath();
        ctx.moveTo(currentPolygon[0][0], currentPolygon[0][1]);
        for (let i = 1; i < currentPolygon.length; i++) {
            ctx.lineTo(currentPolygon[i][0], currentPolygon[i][1]);
        }
        ctx.strokeStyle = "#e67e22";
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.stroke();
        ctx.setLineDash([]);
        for (let i = 0; i < currentPolygon.length; i++) {
            const pt = currentPolygon[i];
            ctx.beginPath();
            ctx.arc(pt[0], pt[1], i === 0 ? 6 : 3, 0, Math.PI * 2);
            ctx.fillStyle = i === 0 ? "#e74c3c" : "#e67e22";
            ctx.fill();
        }
    }
}

/**
 * Draw an edge array as a polyline on the canvas.
 * @param {Array<number>} edgeArray - y-value per column
 * @param {string} color
 * @param {number} lineWidth
 */
function drawEdgeLine(edgeArray, color, lineWidth) {
    if (!edgeArray || edgeArray.length === 0) return;
    ctx.beginPath();
    ctx.moveTo(0, edgeArray[0]);
    // Draw every 3rd pixel for performance (735 cols → 245 segments)
    for (let x = 3; x < edgeArray.length; x += 3) {
        ctx.lineTo(x, edgeArray[x]);
    }
    // Ensure we draw to the last column
    ctx.lineTo(edgeArray.length - 1, edgeArray[edgeArray.length - 1]);
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
}

function canvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY,
    };
}

function isNearStart(x, y, radius) {
    if (currentPolygon.length < 3) return false;
    const start = currentPolygon[0];
    const dx = x - start[0];
    const dy = y - start[1];
    return Math.sqrt(dx * dx + dy * dy) < radius;
}

function closeCurrentPolygon() {
    if (currentPolygon.length >= 3) {
        closedPolygons.push([...currentPolygon]);
    }
    currentPolygon = [];
    redrawCanvas();
}


// ===================================================================
// Edge correction helpers
// ===================================================================

/** Finish the current edge correction segment and store it. */
function finishEdgeSegment() {
    if (currentEdgePoints.length >= 2) {
        edgeCorrections.push({
            edge: currentEdgeTarget,
            points: [...currentEdgePoints],
        });
    }
    currentEdgePoints = [];
    redrawCanvas();
}


// ===================================================================
// Metrics display
// ===================================================================

function showMetrics(metrics) {
    metricsSection.style.display = "block";
    metricsGrid.innerHTML = "";

    const display = [
        ["Dice", metrics.dice],
        ["IoU", metrics.iou],
        ["Precision", metrics.precision],
        ["Recall", metrics.recall],
        ["F1", metrics.f1],
        ["Accuracy", metrics.accuracy],
        ["Hausdorff 95", metrics.hausdorff_95],
    ];

    for (const [label, value] of display) {
        const card = document.createElement("div");
        card.className = "metric-card";
        card.innerHTML = `
            <div class="metric-label">${label}</div>
            <div class="metric-value">${value != null ? value.toFixed(4) : "-"}</div>
        `;
        metricsGrid.appendChild(card);
    }
}


// ===================================================================
// Verdict + auto-advance
// ===================================================================

/** Track whether this image had a verdict when it was loaded, so
 *  auto-advance only fires on *new* verdicts, not re-confirmations. */
let verdictWhenLoaded = null;

function updateVerdictButtons() {
    const btnCorrect = document.getElementById("btn-correct");
    const btnIncorrect = document.getElementById("btn-incorrect");
    btnCorrect.classList.toggle("active-correct", currentVerdict === true);
    btnIncorrect.classList.toggle("active-incorrect", currentVerdict === false);
}

/**
 * Show a brief color flash on the viewer panel to confirm the verdict.
 * @param {boolean} correct
 */
function flashVerdict(correct) {
    verdictFlash.className = correct ? "flash-correct" : "flash-incorrect";
    setTimeout(() => { verdictFlash.className = ""; }, 200);
}

/**
 * Set verdict, save, and optionally auto-advance.
 *
 * Auto-advance only triggers when assigning a NEW verdict (the image
 * was previously un-annotated or the verdict changed).  Re-clicking
 * the same verdict on a revisited image just saves without advancing,
 * so the reviewer can inspect QC-invalid images freely.
 *
 * @param {boolean} correct
 */
async function verdictAndAdvance(correct) {
    if (!currentKey) return;

    const isNewVerdict = (verdictWhenLoaded === null || verdictWhenLoaded === undefined)
                      || (verdictWhenLoaded !== correct);

    currentVerdict = correct;
    updateVerdictButtons();
    flashVerdict(correct);

    // Remember the key BEFORE save, because save may re-sort displayRecords
    const savedKey = currentKey;

    await saveAnnotation();

    if (isNewVerdict) {
        // Find where the NEXT un-annotated image is, or just the next
        // image after the one we just saved (by key, not by stale index)
        setTimeout(() => {
            const newIdx = displayRecords.findIndex(r => r.trajectory_key === savedKey);
            const nextIdx = (newIdx >= 0) ? newIdx + 1 : currentIndex + 1;
            if (nextIdx < displayRecords.length) {
                selectImage(nextIdx);
            }
        }, 220);
    }
    // If same verdict re-clicked: stay on current image (just saved)
}


// ===================================================================
// Save and navigate
// ===================================================================

async function saveAnnotation() {
    if (!currentKey) return;

    await fetch("/api/annotate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            key: currentKey,
            correct: currentVerdict,
            polygons: closedPolygons,
            notes: notesInput.value,
        }),
    });

    const rec = allRecords.find(r => r.trajectory_key === currentKey);
    if (rec) {
        rec.correct = currentVerdict;
        rec.notes = notesInput.value;
        rec.has_polygon = closedPolygons.length > 0 || edgeCorrections.length > 0;
    }

    applyFiltersAndSort();
    renderTable();
    updateProgress();
}

async function saveAndNext() {
    await saveAnnotation();
    if (currentIndex < displayRecords.length - 1) {
        selectImage(currentIndex + 1);
    }
}


// ===================================================================
// Compute metrics (both modes)
// ===================================================================

async function computeMetrics() {
    if (!currentKey) return;

    if (drawMode === "edge") {
        // Finish any open segment first
        if (currentEdgePoints.length >= 2) finishEdgeSegment();
        if (edgeCorrections.length === 0) {
            alert("Draw at least one edge correction segment first.");
            return;
        }
        const metrics = await fetchJSON("/api/compute_edge_metrics", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                key: currentKey,
                corrections: edgeCorrections,
            }),
        });
        if (metrics.error) { alert(metrics.error); return; }
        showMetrics(metrics);
        updateRecordDice(metrics.dice);
    } else {
        // Polygon mode
        if (currentPolygon.length >= 3) closeCurrentPolygon();
        if (closedPolygons.length === 0) {
            alert("Draw at least one polygon first.");
            return;
        }
        const metrics = await fetchJSON("/api/compute_metrics", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                key: currentKey,
                polygons: closedPolygons,
            }),
        });
        if (metrics.error) { alert(metrics.error); return; }
        showMetrics(metrics);
        updateRecordDice(metrics.dice);
    }
}

function updateRecordDice(dice) {
    const rec = allRecords.find(r => r.trajectory_key === currentKey);
    if (rec) {
        rec.dice = dice;
        rec.has_polygon = true;
    }
    renderTable();
}


// ===================================================================
// Mode switching
// ===================================================================

function setDrawMode(mode) {
    drawMode = mode;
    if (mode === "edge") {
        edgeToolbar.style.display = "flex";
        polygonToolbar.style.display = "none";
        hintEdge.style.display = "inline";
        hintPolygon.style.display = "none";
    } else {
        edgeToolbar.style.display = "none";
        polygonToolbar.style.display = "flex";
        hintEdge.style.display = "none";
        hintPolygon.style.display = "inline";
    }
    redrawCanvas();
}


// ===================================================================
// Event binding
// ===================================================================

function bindEvents() {
    // ---- Drawing mode radio ----
    document.querySelectorAll('input[name="draw-mode"]').forEach(radio => {
        radio.addEventListener("change", (e) => setDrawMode(e.target.value));
    });

    // ---- Edge target radio ----
    document.querySelectorAll('input[name="edge-target"]').forEach(radio => {
        radio.addEventListener("change", (e) => {
            // Finish current segment if switching target
            if (currentEdgePoints.length >= 2) finishEdgeSegment();
            currentEdgeTarget = e.target.value;
        });
    });

    // ---- Canvas click ----
    canvas.addEventListener("click", (e) => {
        e.preventDefault();
        const { x, y } = canvasCoords(e);

        if (drawMode === "edge") {
            currentEdgePoints.push([x, y]);
            redrawCanvas();
        } else {
            // Polygon mode
            if (isNearStart(x, y, 10)) {
                closeCurrentPolygon();
                return;
            }
            currentPolygon.push([x, y]);
            redrawCanvas();
        }
    });

    canvas.addEventListener("dblclick", (e) => {
        e.preventDefault();
        if (drawMode === "edge") {
            // Double-click finishes edge segment
            if (currentEdgePoints.length > 0) currentEdgePoints.pop();
            finishEdgeSegment();
        } else {
            if (currentPolygon.length > 0) currentPolygon.pop();
            closeCurrentPolygon();
        }
    });

    // ---- Overlay toggles ----
    document.getElementById("toggle-mask").addEventListener("change", redrawCanvas);
    document.getElementById("toggle-edges").addEventListener("change", redrawCanvas);
    document.getElementById("toggle-polygon").addEventListener("change", redrawCanvas);

    // ---- Edge toolbar buttons ----
    document.getElementById("btn-finish-edge").addEventListener("click", finishEdgeSegment);

    document.getElementById("btn-undo-vertex").addEventListener("click", () => {
        if (drawMode === "edge") {
            if (currentEdgePoints.length > 0) {
                currentEdgePoints.pop();
            } else if (edgeCorrections.length > 0) {
                // Re-open last correction for editing
                const last = edgeCorrections.pop();
                currentEdgePoints = last.points;
                currentEdgeTarget = last.edge;
                // Update radio
                document.querySelector(`input[name="edge-target"][value="${last.edge}"]`).checked = true;
            }
        } else {
            if (currentPolygon.length > 0) {
                currentPolygon.pop();
            } else if (closedPolygons.length > 0) {
                currentPolygon = closedPolygons.pop();
            }
        }
        redrawCanvas();
    });

    document.getElementById("btn-clear-all").addEventListener("click", () => {
        currentEdgePoints = [];
        edgeCorrections = [];
        currentPolygon = [];
        closedPolygons = [];
        metricsSection.style.display = "none";
        redrawCanvas();
    });

    document.getElementById("btn-compute-metrics").addEventListener("click", computeMetrics);

    // ---- Polygon toolbar buttons ----
    document.getElementById("btn-new-polygon").addEventListener("click", () => {
        if (currentPolygon.length >= 3) closeCurrentPolygon();
        currentPolygon = [];
    });

    document.getElementById("btn-undo-vertex-poly").addEventListener("click", () => {
        if (currentPolygon.length > 0) {
            currentPolygon.pop();
        } else if (closedPolygons.length > 0) {
            currentPolygon = closedPolygons.pop();
        }
        redrawCanvas();
    });

    document.getElementById("btn-clear-all-poly").addEventListener("click", () => {
        currentPolygon = [];
        closedPolygons = [];
        metricsSection.style.display = "none";
        redrawCanvas();
    });

    document.getElementById("btn-compute-metrics-poly").addEventListener("click", computeMetrics);

    // ---- Verdict buttons: click → save + auto-advance ----
    document.getElementById("btn-correct").addEventListener("click", () => {
        verdictAndAdvance(true);
    });

    document.getElementById("btn-incorrect").addEventListener("click", () => {
        verdictAndAdvance(false);
    });

    // ---- Navigation ----
    document.getElementById("btn-prev").addEventListener("click", () => {
        if (currentIndex > 0) selectImage(currentIndex - 1);
    });

    document.getElementById("btn-next").addEventListener("click", () => {
        if (currentIndex < displayRecords.length - 1) selectImage(currentIndex + 1);
    });

    document.getElementById("btn-save-next").addEventListener("click", saveAndNext);

    // ---- Filters ----
    filterExposure.addEventListener("change", () => {
        applyFiltersAndSort();
        renderTable();
    });

    filterStatus.addEventListener("change", () => {
        applyFiltersAndSort();
        renderTable();
    });

    // ---- Table header sorting ----
    document.querySelectorAll("#records-table th.sortable").forEach(th => {
        th.addEventListener("click", () => {
            const field = th.dataset.sort;
            if (sortState.field === field) {
                sortState.ascending = !sortState.ascending;
            } else {
                sortState.field = field;
                sortState.ascending = true;
            }
            applyFiltersAndSort();
            renderTable();
        });
    });

    // ---- Bulk actions ----
    document.getElementById("btn-approve-qc").addEventListener("click", async () => {
        if (!confirm("Approve all un-annotated QC-valid images?")) return;
        const resp = await fetchJSON("/api/bulk_annotate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "approve_qc_valid" }),
        });
        alert(`Modified ${resp.modified} images.`);
        allRecords = await fetchJSON("/api/records");
        applyFiltersAndSort();
        renderTable();
        updateProgress();
    });

    document.getElementById("btn-reject-qc").addEventListener("click", async () => {
        if (!confirm("Reject all un-annotated QC-invalid images?")) return;
        const resp = await fetchJSON("/api/bulk_annotate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "reject_qc_invalid" }),
        });
        alert(`Modified ${resp.modified} images.`);
        allRecords = await fetchJSON("/api/records");
        applyFiltersAndSort();
        renderTable();
        updateProgress();
    });

    // ---- Export ----
    document.getElementById("btn-export").addEventListener("click", async () => {
        const resp = await fetchJSON("/api/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        if (resp.filename) {
            window.location.href = `/api/download/${encodeURIComponent(resp.filename)}`;
        }
    });

    // ---- Help modal ----
    const helpOverlay = document.getElementById("help-overlay");
    document.getElementById("btn-help").addEventListener("click", () => {
        helpOverlay.style.display = "flex";
    });
    document.getElementById("help-close").addEventListener("click", () => {
        helpOverlay.style.display = "none";
    });
    helpOverlay.addEventListener("click", (e) => {
        // Close when clicking the backdrop (not the modal itself)
        if (e.target === helpOverlay) helpOverlay.style.display = "none";
    });

    // ---- Keyboard shortcuts ----
    document.addEventListener("keydown", (e) => {
        // Close help modal on Escape
        if (e.key === "Escape" && helpOverlay.style.display === "flex") {
            helpOverlay.style.display = "none";
            return;
        }
        // Skip shortcuts when typing in notes or help is open
        if (document.activeElement === notesInput) return;
        if (helpOverlay.style.display === "flex") return;

        switch (e.key) {
            case "ArrowRight":
                if (currentIndex < displayRecords.length - 1) selectImage(currentIndex + 1);
                break;
            case "ArrowLeft":
                if (currentIndex > 0) selectImage(currentIndex - 1);
                break;
            case "y":
            case "Y":
                verdictAndAdvance(true);
                break;
            case "n":
            case "N":
                verdictAndAdvance(false);
                break;
            case "s":
            case "S":
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    saveAnnotation();
                }
                break;
            case "Enter":
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    saveAndNext();
                }
                break;
            case "z":
            case "Z":
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    if (drawMode === "edge" && currentEdgePoints.length > 0) {
                        currentEdgePoints.pop();
                    } else if (drawMode === "polygon" && currentPolygon.length > 0) {
                        currentPolygon.pop();
                    }
                    redrawCanvas();
                }
                break;
        }
    });
}
