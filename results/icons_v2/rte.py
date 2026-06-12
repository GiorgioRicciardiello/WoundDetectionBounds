import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import make_interp_spline
from pathlib import Path

outdir = Path(r"C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds\results\icons_v2\figure_line_plots")
outdir.mkdir(exist_ok=True)
#
# def smooth_curve(x, y, n=300):
#     x = np.array(x)
#     y = np.array(y)
#     xs = np.linspace(x.min(), x.max(), n)
#     ys = make_interp_spline(x, y, k=3)(xs)
#     return xs, ys
#
# def save_transparent_plot(fig, name):
#     fig.savefig(outdir / f"{name}.png", dpi=600, transparent=True, bbox_inches="tight", pad_inches=0.05)
#     fig.savefig(outdir / f"{name}.svg", transparent=True, bbox_inches="tight", pad_inches=0.05)
#     plt.close(fig)
#
# # 1) Wound area trajectory
# x = [0, 3, 6, 10, 15, 20, 25]
# area = [1.00, 0.78, 0.60, 0.42, 0.25, 0.12, 0.04]
#
# xs, ys = smooth_curve(x, area)
# upper = np.clip(ys + 0.08, 0, 1)
# lower = np.clip(ys - 0.08, 0, 1)
#
# fig, ax = plt.subplots(figsize=(4, 3))
# ax.fill_between(xs, lower, upper, alpha=0.20)
# ax.plot(xs, ys, linewidth=3)
# ax.set_xlim(0, 25)
# ax.set_ylim(0, 1.05)
# ax.axis("off")
# save_transparent_plot(fig, "wound_area_curve")
#
#
# # 2) Closure fraction trajectory
# fraction = [0.00, 0.25, 0.48, 0.68, 0.84, 0.92, 0.95]
#
# xs, ys = smooth_curve(x, fraction)
# upper = np.clip(ys + 0.08, 0, 1)
# lower = np.clip(ys - 0.08, 0, 1)
#
# fig, ax = plt.subplots(figsize=(4, 3))
# ax.fill_between(xs, lower, upper, alpha=0.20)
# ax.plot(xs, ys, linewidth=3)
# ax.set_xlim(0, 25)
# ax.set_ylim(0, 1.05)
# ax.axis("off")
# save_transparent_plot(fig, "closure_fraction_curve")
#
#
# # 3) Edge displacement trajectories
# x_edge = [0, 2, 5, 8, 12, 16, 20]
# upper_edge = [0.00, 0.15, 0.35, 0.52, 0.58, 0.70, 0.88]
# lower_edge = [0.00, -0.10, -0.25, -0.35, -0.40, -0.62, -0.85]
#
# xs_u, ys_u = smooth_curve(x_edge, upper_edge)
# xs_l, ys_l = smooth_curve(x_edge, lower_edge)
#
# fig, ax = plt.subplots(figsize=(4, 3))
# ax.plot(xs_u, ys_u, linewidth=3)
# ax.plot(xs_l, ys_l, linewidth=3)
# ax.axhline(0, linewidth=1.5, alpha=0.4)
# ax.set_xlim(0, 25)
# ax.set_ylim(-1, 1)
# ax.axis("off")
# save_transparent_plot(fig, "edge_displacement_curves")
#
# print(f"Saved PNG and SVG files in: {outdir.resolve()}")


# ---------------------------------------------------------------------------------------
# %%

# -----------------------------
# Nature-style formatting
# -----------------------------
plt.rcParams.update({
    "font.size": 12,
    "axes.linewidth": 1.5,
    "xtick.major.width": 1.2,
    "ytick.major.width": 1.2,
    "xtick.major.size": 4,
    "ytick.major.size": 4,
})

def smooth_curve(x, y, n=300):
    x = np.array(x)
    y = np.array(y)

    xs = np.linspace(min(x), max(x), n)
    ys = make_interp_spline(x, y, k=3)(xs)

    return xs, ys


def save_plot(fig, name):
    fig.savefig(
        outdir / f"{name}.png",
        dpi=600,
        transparent=True,
        bbox_inches="tight"
    )

    fig.savefig(
        outdir / f"{name}.svg",
        transparent=True,
        bbox_inches="tight"
    )

    plt.close(fig)


# ============================================================
# 1. AREA TRAJECTORY
# ============================================================

x = [0, 3, 6, 10, 15, 20, 25]
area = [1.00, 0.78, 0.60, 0.42, 0.25, 0.12, 0.04]

xs, ys = smooth_curve(x, area)

ci = 0.08
upper = np.clip(ys + ci, 0, 1)
lower = np.clip(ys - ci, 0, 1)

fig, ax = plt.subplots(figsize=(4,3))

ax.fill_between(xs, lower, upper, alpha=0.20)
ax.plot(xs, ys, linewidth=2.5, color="#1E88E5")

ax.set_xlim(0,25)
ax.set_ylim(0,1.05)

ax.set_xlabel("Time (h)")
ax.set_ylabel("Area")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

save_plot(fig, "area_trajectory")


# ============================================================
# 2. CLOSURE FRACTION
# ============================================================

fraction = [0.00, 0.25, 0.48, 0.68, 0.84, 0.92, 0.95]

xs, ys = smooth_curve(x, fraction)

upper = np.clip(ys + ci, 0, 1)
lower = np.clip(ys - ci, 0, 1)

fig, ax = plt.subplots(figsize=(4,3))

ax.fill_between(xs, lower, upper, alpha=0.20)
ax.plot(xs, ys, linewidth=2.5, color="#66BB6A")

ax.set_xlim(0,25)
ax.set_ylim(0,1.05)

ax.set_xlabel("Time (h)")
ax.set_ylabel("Fraction")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

save_plot(fig, "closure_fraction")


# ============================================================
# 3. EDGE DISPLACEMENT
# ============================================================

x_edge = [0,2,5,8,12,16,20]

upper_edge = [0.00,0.15,0.35,0.52,0.58,0.70,0.88]
lower_edge = [0.00,-0.10,-0.25,-0.35,-0.40,-0.62,-0.85]

xs_u, ys_u = smooth_curve(x_edge, upper_edge)
xs_l, ys_l = smooth_curve(x_edge, lower_edge)

fig, ax = plt.subplots(figsize=(4,3))

ax.plot(xs_u, ys_u, linewidth=2.5, color="#F57C00")
ax.plot(xs_l, ys_l, linewidth=2.5, color="#1565C0")

ax.axhline(
    y=0,
    linewidth=1.0,
    alpha=0.4
)

ax.set_xlim(0,25)
ax.set_ylim(-1,1)

ax.set_xlabel("Time (h)")
ax.set_ylabel("Displacement")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

save_plot(fig, "edge_displacement")


# ============================================================
# 4. CLOSURE SPEED
# ============================================================

x_speed = [0, 2, 4, 6, 8, 12, 16, 20, 25]

speed = [
    0.00,
    0.55,
    0.85,
    0.72,
    0.58,
    0.40,
    0.25,
    0.15,
    0.08
]

xs, ys = smooth_curve(x_speed, speed)

ci = 0.08
upper = np.clip(ys + ci, 0, None)
lower = np.clip(ys - ci, 0, None)

fig, ax = plt.subplots(figsize=(4,3))

ax.fill_between(
    xs,
    lower,
    upper,
    color="#B39DDB",  # light purple band
    alpha=0.25
)

ax.plot(
    xs,
    ys,
    linewidth=2.5,
    color="#5E35B1"   # deep purple
)

ax.set_xlim(0,25)
ax.set_ylim(0,1.05)

ax.set_xlabel("Time (h)")
ax.set_ylabel("Speed\n(pixels/h)")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

save_plot(fig, "closure_speed")

print(f"Saved files to: {outdir.resolve()}")

