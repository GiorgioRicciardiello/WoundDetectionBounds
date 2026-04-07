import pathlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re
import cv2
from typing import Tuple, Optional
import pickle

# ============================================================
# 1. SHOW FUNCTION (generic image viewer)
# ============================================================

def show(
    img: np.ndarray,
    title: str = "",
    cmap: str = "gray",
    dpi: int = 100,
    scalebar: Optional[Tuple[int, str]] = None
) -> None:
    """
    General-purpose high-resolution image display.

    Parameters
    ----------
    img : np.ndarray
        Grayscale or RGB image.
    title : str
        Title displayed above the image.
    cmap : str
        Matplotlib colormap for grayscale images.
    dpi : int
        Figure DPI for size scaling.
    scalebar : Optional[Tuple[int, str]]
        Add a scalebar. Provide (length_pixels, label).
        Example: (100, "100 µm")
    """

    height, width = img.shape[:2]
    fig_size = (width / dpi, height / dpi)

    plt.figure(figsize=fig_size, dpi=dpi)

    if img.ndim == 2:
        plt.imshow(img, cmap=cmap)
    else:
        plt.imshow(img)

    plt.title(title)
    plt.axis("off")

    # Optional scalebar
    if scalebar:
        length_px, label = scalebar
        y = height - int(height * 0.05)
        x0 = int(width * 0.05)
        x1 = x0 + length_px
        plt.plot([x0, x1], [y, y], color="white", linewidth=4)
        plt.text(x0, y - 10, label, color="white", fontsize=10)

    plt.tight_layout()
    plt.show()


def plot_mask_overlay(
    image_gray: np.ndarray,
    mask: np.ndarray,
    title: str = "Mask Overlay"
) -> np.ndarray:
    """
    Overlay a binary region-of-interest (ROI) mask on top of the raw grayscale image.

    Parameters
    ----------
    image_gray : np.ndarray
        Raw grayscale microscopy/brightfield image.
    mask : np.ndarray
        Binary mask (0/1) representing ROI (e.g., wound region).
    title : str
        Plot title.

    Returns
    -------
    overlay : np.ndarray
        RGB image showing the overlay.
    """

    # Normalize background image
    img_f = image_gray.astype(np.float32)
    img_f = (img_f - img_f.min()) / (img_f.max() - img_f.min() + 1e-6)
    bg = (img_f * 255).astype(np.uint8)
    bg_rgb = cv2.cvtColor(bg, cv2.COLOR_GRAY2RGB)

    # Mask → uint8
    mask_u8 = (mask.astype(np.uint8) * 255)

    overlay = bg_rgb.copy()

    # ROI shown as semi-transparent blue
    blue = np.zeros_like(bg_rgb)
    blue[..., 2] = 255  # Blue channel
    alpha = 0.35

    overlay[mask_u8 == 255] = (
        (1 - alpha) * overlay[mask_u8 == 255] +
        alpha * blue[mask_u8 == 255]
    ).astype(np.uint8)

    # Outline ROI
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours,
                     -1, (0, 150, 255), 2)  # Gold/Cyan border

    plt.figure(figsize=(7, 7))
    plt.imshow(overlay)
    plt.title(title + " (ROI highlighted)")
    plt.axis("off")
    plt.tight_layout()
    plt.show()

    return overlay



def plot_wound_fit(
    raw_image: np.ndarray,
    wound_mask: np.ndarray,
    title: str = "Wound Segmentation",
    roi_color: Tuple[int, int, int] = (255, 140, 0),  # journal-friendly orange
    alpha: float = 0.35,
    contour_darkening: float = 0.6,
    contour_thickness: int = 2,
    figsize: Tuple[int, int] = (7, 7),
    path_out: pathlib.Path = None,
    verbose: bool = True,
) -> np.ndarray:
    """
    Overlay comparison between:
      - initial (raw) image, the cell
      - Wound maks identify by the code (final) wound mask (filled + contoured)

    Styling is journal-oriented:
      - single hue for wound
      - darker contour of same color
      - neutral background

    # Excellent for wounds / tissue
    roi_color = (255, 140, 0)   # orange (default)
    # Cell biology / healing
    roi_color = (60, 179, 113)  # green
    # Clinical / vascular
    roi_color = (178, 34, 34)   # dark red
    # Monochrome-safe blue
    roi_color = (70, 130, 180)

    Parameters
    ----------
    raw_image : np.ndarray
        RGB image, original image.
    wound_mask : np.ndarray
        Binary mask of refined wound segmentation.
    title : str
        Figure title.
    roi_color : tuple(int, int, int)
        RGB color used for wound fill.
    alpha : float
        Transparency of wound fill (0–1).
    contour_darkening : float
        Multiplier (<1) to darken contour relative to fill.
    contour_thickness : int
        Thickness of wound contour.
    figsize : tuple
        Figure size in inches.
    path_out : pathlib.Path, optional
        If provided, saves figure at high DPI.
    verbose : bool
        Whether to display the figure.

    Returns
    -------
    overlay : np.ndarray
        RGB image with wound overlay.
    """

    # -------------------------------------------------
    # Prepare masks
    # -------------------------------------------------

    # 1. Prepare the Background (Raw Image)
    # Ensure raw_image is in RGB format for plotting
    if len(raw_image.shape) == 2:  # If grayscale
        bg_rgb = cv2.cvtColor(raw_image, cv2.COLOR_GRAY2RGB)
    else:
        bg_rgb = raw_image.copy()

    overlay = bg_rgb.copy().astype(np.float32)  # Use float for blending math

    # 2. Prepare the Mask
    ref_u8 = (wound_mask > 0).astype(np.uint8)
    roi_color_arr = np.array(roi_color, dtype=np.float32)

    # 3. Apply Alpha Blending ONLY where mask exists
    mask_indices = ref_u8 == 1
    overlay[mask_indices] = (
            (1 - alpha) * overlay[mask_indices] +
            alpha * roi_color_arr
    )

    # Convert back to uint8 for OpenCV and plotting
    overlay = np.clip(overlay, 0, 255).astype(np.uint8)

    # 4. Draw Darker Contour
    contour_color = tuple(int(c * contour_darkening) for c in roi_color)
    contours_refined, _ = cv2.findContours(
        ref_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    cv2.drawContours(
        overlay, contours_refined, -1,
        color=contour_color, thickness=contour_thickness
    )

    # 5. Plotting
    plt.figure(figsize=figsize)
    plt.imshow(overlay)
    plt.title(title)
    plt.axis("off")
    plt.tight_layout()

    if path_out is not None:
        plt.savefig(path_out, dpi=300, bbox_inches="tight")

    if verbose:
        plt.show()

    plt.close()
    return overlay



def plot_wound_raw(raw_mask, smooth_mask, raw_image=None, title="Wound Overlay"):
    """
    Enhanced overlay visualization:
    - Brightened raw background
    - Light red wound fill
    - Thin yellow border for raw wound mask
    - Cyan/white border for smooth wound mask
    """

    # ---------------------------------------------
    # Background = RAW IMAGE if provided, else raw mask
    # ---------------------------------------------
    if raw_image is not None:
        img = raw_image.copy()

        # Normalize and enhance contrast
        img_f = img.astype(np.float32)
        img_f = (img_f - img_f.min()) / (img_f.max() - img_f.min() + 1e-6)
        bg = (img_f * 255).astype(np.uint8)

        # Convert to RGB
        bg = cv2.cvtColor(bg, cv2.COLOR_GRAY2RGB)

    else:
        bg = (raw_mask.astype(np.uint8) * 255)
        bg = cv2.cvtColor(bg, cv2.COLOR_GRAY2RGB)

    # ---------------------------------------------
    # Convert masks to uint8
    # ---------------------------------------------
    raw_u8 = (raw_mask.astype(np.uint8) * 255)
    smooth_u8 = (smooth_mask.astype(np.uint8) * 255)

    overlay = bg.copy()

    # ---------------------------------------------
    # Fill smooth wound area (light red)
    # ---------------------------------------------
    red_layer = np.zeros_like(bg)
    red_layer[..., 0] = 255  # Red channel
    alpha = 0.25  # more transparent

    overlay[smooth_u8 == 255] = (
        (1 - alpha) * overlay[smooth_u8 == 255] +
        alpha * red_layer[smooth_u8 == 255]
    ).astype(np.uint8)

    # ---------------------------------------------
    # Smooth mask contour (cyan border)
    # ---------------------------------------------
    contours_smooth, _ = cv2.findContours(smooth_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours_smooth, -1, (0, 255, 255), 2)  # Cyan border

    # ---------------------------------------------
    # Raw wound mask contour (thin yellow)
    # ---------------------------------------------
    contours_raw, _ = cv2.findContours(raw_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours_raw, -1, (255, 255, 0), 1)      # Yellow thin border

    # ---------------------------------------------
    # Show
    # ---------------------------------------------
    plt.figure(figsize=(7, 7))
    plt.imshow(overlay)
    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.show()

    return overlay


def plot_wound_boundaries_on_image(
    img_f: np.ndarray,
    upper: np.ndarray,
    lower: np.ndarray,
    title: str = "Wound Boundaries",
    dpi: int = 100,
    shade: bool = True
) -> None:
    """
    Plot the upper and lower wound boundaries on the original grayscale image.

    Parameters
    ----------
    img_f : np.ndarray
        Grayscale float32 image in range [0,1].
    upper : np.ndarray
        Array of row indices for the upper wound boundary (len = W).
    lower : np.ndarray
        Array of row indices for the lower wound boundary (len = W).
    title : str
        Title of the plot.
    dpi : int
        DPI for accurate figure size display.
    shade : bool
        If True, shade the wound region between upper/lower boundaries.
    """

    H, W = img_f.shape

    # --- Clip boundaries so we do not plot outside the image ---
    upper_clipped = np.clip(upper, 0, H-1)
    lower_clipped = np.clip(lower, 0, H-1)

    # --- Create figure sized to real pixels ---
    fig_w = W / dpi
    fig_h = H / dpi

    plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
    plt.imshow(img_f, cmap="gray")

    # --- Shade in between boundaries (wound region) ---
    if shade:
        xs = np.arange(W)
        plt.fill_between(
            xs,
            upper_clipped,
            lower_clipped,
            color="cyan",
            alpha=0.20,
            linewidth=0
        )

    # --- Plot upper & lower boundaries ---
    plt.plot(upper_clipped, color="red", linewidth=1.5, label="Upper boundary")
    plt.plot(lower_clipped, color="cyan", linewidth=1.5, label="Lower boundary")

    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


# %%  Generate final reports
def _parse_time_from_filename(fname):
    """
    Parse time from filename pattern: XXdYYhZZm
    Returns time in hours (float).
    """
    m = re.search(r"(\d+)d(\d+)h(\d+)m", str(fname))
    if not m:
        raise ValueError(f"Time not found in filename: {fname}")

    d, h, m_ = map(int, m.groups())
    return d * 24 + h + m_ / 60.0

def report(
    all_results,
    title="Wound Healing Dynamics",
    figsize=(7, 4),
    save_dir=None,
):
    """
    Generate wound healing report and plot.

    Accepts:
      - results = segment_wound_video(paths)
      - OR:
        all_results[key] = {"results": results}
    """

    # -------------------------------------------------
    # Normalize input
    # -------------------------------------------------
    if isinstance(all_results, list):
        all_results = {"experiment": {"results": all_results}}

    fig, ax = plt.subplots(figsize=figsize)
    summary_rows = []

    # -------------------------------------------------
    # Iterate groups
    # -------------------------------------------------
    for key, data in all_results.items():
        results = data["results"]

        times = []
        areas_pct = []

        for r in results:
            # --- time ---
            t = _parse_time_from_filename(r["file_name"])
            times.append(t)

            # --- wound area percentage ---
            area_px = r["area"]
            H, W = r["img_raw"].shape[:2]
            area_pct = 100.0 * area_px / (H * W)
            areas_pct.append(area_pct)

        times = np.array(times)
        areas_pct = np.array(areas_pct)

        # sort by time
        idx = np.argsort(times)
        times = times[idx]
        areas_pct = areas_pct[idx]

        # -------------------------------------------------
        # Healing metrics
        # -------------------------------------------------
        A0 = areas_pct[0]
        A_end = areas_pct[-1]
        closure = A0 - A_end
        duration = times[-1] - times[0]

        healing_rate = closure / duration if duration > 0 else np.nan

        summary_rows.append({
            "key": key,
            "initial_area_%": A0,
            "final_area_%": A_end,
            "closure_%": closure,
            "duration_h": duration,
            "healing_rate_%_per_h": healing_rate,
        })

        # -------------------------------------------------
        # Plot curve
        # -------------------------------------------------
        ax.plot(
            times,
            areas_pct,
            marker="o",
            linewidth=2,
            label=f"{key} (rate={healing_rate:.2f}%/h)",
        )

        # mark start / end
        ax.scatter(times[0], A0, s=40)
        ax.scatter(times[-1], A_end, s=40)

    # -------------------------------------------------
    # Plot formatting (publication-ready)
    # -------------------------------------------------
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("Time (hours)", fontsize=11)
    ax.set_ylabel("Wound area (% of image)", fontsize=11)

    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(frameon=False, fontsize=9)

    plt.tight_layout()

    # -------------------------------------------------
    # Summary table
    # -------------------------------------------------
    df_summary = pd.DataFrame(summary_rows)

    if save_dir is not None:
        if len(all_results) == 1:
            # Construct the base filename from the tuple keys
            first_key = list(all_results.keys())[0]
            file_name = ''.join(first_key) + '.png'
        else:
            file_name = 'report_multi_cell.png'

        # 1. Define the full image path
        img_path = save_dir.joinpath(file_name)
        plt.savefig(img_path, dpi=300)

        # 2. Change the suffix from .png to .pkl for the data file
        pickle_path = img_path.with_suffix('.pkl')

        # 3. Save the pickle file
        with open(pickle_path, 'wb') as file:
            pickle.dump(all_results, file)

        frame_path = img_path.with_suffix('.xlsx')
        df_summary.to_excel(frame_path, index=False)

    plt.show()
    plt.close()

    return df_summary

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.cm import get_cmap

def plot_population_dynamics(
    trajectories,
    title="Wound Healing Dynamics (Population)",
    figsize=(7, 4),
    save_path=None,
):
    """
    Population-level wound healing plot with optional legend strip.

    Parameters
    ----------
    summary_df : pd.DataFrame
        Cell-level summary statistics (used only for consistency checks).
    trajectories : dict
        {key: {"times": np.ndarray, "areas": np.ndarray}}
    show_legend_strip : bool
        Whether to show a bottom color-strip legend for trajectories.
    max_legend_items : int
        Maximum number of legend rectangles to draw (subsample if larger).
    """

    # -------------------------------------------------
    # Figure layout
    # -------------------------------------------------

    fig, ax = plt.subplots(figsize=figsize)
    ax_leg = None

    # -------------------------------------------------
    # Common time grid
    # -------------------------------------------------
    all_times = sorted(
        set(t for traj in trajectories.values() for t in traj["times"])
    )

    # -------------------------------------------------
    # Color handling
    # -------------------------------------------------
    cmap = get_cmap("tab20")
    keys = list(trajectories.keys())

    color_map = {
        k: cmap(i % cmap.N) for i, k in enumerate(keys)
    }

    # -------------------------------------------------
    # Plot individual trajectories
    # -------------------------------------------------
    Y = []

    for key, traj in trajectories.items():
        y_interp = np.interp(all_times, traj["times"], traj["areas"])
        Y.append(y_interp)

        ax.plot(
            all_times,
            y_interp,
            color=color_map[key],
            alpha=0.6,
            linewidth=1.0
        )

    Y = np.vstack(Y)

    # -------------------------------------------------
    # Median + IQR
    # -------------------------------------------------
    median = np.nanmedian(Y, axis=0)
    q25 = np.nanpercentile(Y, 25, axis=0)
    q75 = np.nanpercentile(Y, 75, axis=0)

    ax.fill_between(
        all_times,
        q25,
        q75,
        color="#4C72B0",
        alpha=0.25,
        label="IQR"
    )

    ax.plot(
        all_times,
        median,
        color="#1B3A57",
        linewidth=2.8,
        label="Median"
    )

    # -------------------------------------------------
    # Axes formatting
    # -------------------------------------------------
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("Time (hours)", fontsize=11)
    ax.set_ylabel("Wound area (% of image)", fontsize=11)

    ax.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    ax.legend(frameon=False, loc="upper right")


    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300)

    plt.show()
    plt.close(fig)

def plot_healing_rate_distribution(df_summary, save_path=None):
    fig, ax = plt.subplots(figsize=(5, 3))

    ax.hist(
        df_summary["healing_rate_%_per_h"],
        bins=20,
        color="steelblue",
        edgecolor="black",
        alpha=0.8
    )

    ax.set_xlabel("Healing rate (% / hour)")
    ax.set_ylabel("Number of cells")
    ax.set_title("Distribution of healing rates")
    ax.grid(True, linestyle="--", alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300)

    plt.show()
    plt.close()


def extract_trajectories_from_results(all_results):
    trajectories = {}

    for key, data in all_results.items():
        results = data["results"]

        times = []
        areas = []

        for r in results:
            # --- time ---
            if "t" in r:
                t = r["t"]                       # integer frame index
            else:
                t = _parse_time_from_filename(r["file_name"])

            # --- wound area (% image) ---
            H, W = r["img_raw"].shape[:2]
            area_pct = 100.0 * r["area"] / (H * W)

            times.append(t)
            areas.append(area_pct)

        idx = np.argsort(times)

        trajectories[key] = {
            "times": np.array(times)[idx],
            "areas": np.array(areas)[idx],
        }

    return trajectories



def plot_wound_healing_subplots(
    df: pd.DataFrame,
    group_cols=("cell_line", "sample_condition"),
    magnitude: str = "healing_ratio",
    time_col: str = "time_h",
    xlabel: str = "Time (hours)",
    concentration_col: str = "concentration_mm",
    show_std: bool = True,
    figsize=(18, 6),
    dpi=120,
    show: bool = True,
    axes=None,              # 🔹 NEW
):
    """
    Subplots by concentration.
    Color = unique (cell_line, sample_condition) combination.
    Same group has same color across all subplots.
    """
    from matplotlib.colors import to_rgb
    def _generate_hierarchical_colors(
            df: pd.DataFrame,
            primary_col: str,
            secondary_col: str,
            base_cmap: str = "tab10",
            shade_range=(0.4, 1.0),
    ):
        """
        Assign one base color per primary group and shaded variants
        for secondary groups.

        Returns
        -------
        dict
            {(primary, secondary): color}
        """

        primary_vals = sorted(df[primary_col].unique())
        secondary_vals = sorted(df[secondary_col].unique())

        base_colors = plt.get_cmap(base_cmap).colors
        if len(primary_vals) > len(base_colors):
            raise ValueError("Too many primary groups for base colormap")

        # Map primary → base color
        primary_color_map = {
            p: base_colors[i]
            for i, p in enumerate(primary_vals)
        }

        # Shade factors for secondary groups
        shades = np.linspace(shade_range[0], shade_range[1], len(secondary_vals))

        combo_color_map = {}

        for p in primary_vals:
            base_rgb = np.array(to_rgb(primary_color_map[p]))

            for s, alpha in zip(secondary_vals, shades):
                shaded = base_rgb * alpha + (1 - alpha)
                combo_color_map[(p, s)] = shaded

        return combo_color_map

    # -----------------------------
    # Validation
    # -----------------------------
    required = {time_col, concentration_col, magnitude, *group_cols}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.dropna(subset=[time_col, concentration_col, magnitude])

    # -----------------------------
    # Build GLOBAL color map per combination
    # -----------------------------
    combos = (
        df[list(group_cols)]
        .drop_duplicates()
        .sort_values(list(group_cols))
        .apply(tuple, axis=1)
        .tolist()
    )

    cmap = plt.get_cmap("tab10")  # high contrast
    colors = cmap.colors

    if len(combos) > len(colors):
        raise ValueError("Too many group combinations for tab10 colormap")


    primary_col, secondary_col = group_cols

    combo_color_map = _generate_hierarchical_colors(
        df=df,
        primary_col=primary_col,
        secondary_col=secondary_col,
        base_cmap="tab10",  # perceptually distinct hues
        shade_range=(0.45, 1.0),
    )

    # -----------------------------
    # Setup subplots
    # -----------------------------
    concentrations = sorted(df[concentration_col].unique())
    ncols = len(concentrations)

    if axes is None:
        fig, axes = plt.subplots(
            1,
            ncols,
            figsize=figsize,
            dpi=dpi,
            sharey=True,
            constrained_layout=False,
        )
        if ncols == 1:
            axes = [axes]
    else:
        fig = axes[0].figure

    # -----------------------------
    # Plot
    # -----------------------------
    for ax, conc in zip(axes, concentrations):
        df_conc = df[df[concentration_col] == conc]

        for combo, df_group in df_conc.groupby(list(group_cols)):
            color = combo_color_map[combo]

            agg = (
                df_group
                .groupby(time_col)
                .agg(
                    mean_val=(magnitude, "mean"),
                    std_val=(magnitude, "std"),
                    n=(magnitude, "count"),
                )
                .reset_index()
                .sort_values(time_col)
            )

            ax.plot(
                agg[time_col],
                agg["mean_val"],
                color=color,
                linewidth=2.2,
                marker="o",
                markersize=3,
                label=f"{combo[0]} | {combo[1]}",
            )

            if show_std:
                sem = agg["std_val"] / np.sqrt(agg["n"])

                ax.fill_between(
                    agg[time_col],
                    agg["mean_val"] - sem,
                    agg["mean_val"] + sem,
                    color=color,
                    alpha=0.18,
                )

        ax.set_title(f"Concentration = {conc}", fontsize=11)
        ax.set_xlabel(xlabel)
        ax.grid(alpha=0.3)

        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.38),
            frameon=False,
            fontsize=8,
            title="Cell line | Condition",
            title_fontsize=9,
        )

    # -----------------------------
    # Labels & layout
    # -----------------------------
    axes[0].set_ylabel(
        "Healing ratio (0 = open, 1 = closed)"
        if magnitude == "healing_ratio"
        else magnitude.replace("_", " ").capitalize()
    )

    fig.suptitle(
        f"Wound Healing – Mean trajectories ({magnitude})",
        fontsize=14,
        y=0.98,
    )

    fig.subplots_adjust(
        left=0.06,
        right=0.98,
        top=0.85,
        bottom=0.42,
        wspace=0.25,
    )
    if show and axes is None:
        plt.show()

    return fig

