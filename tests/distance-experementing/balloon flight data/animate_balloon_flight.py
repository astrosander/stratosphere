"""
Epic LoRa Balloon Flight Animator
─────────────────────────────────
Parses flight_alumni_field.txt & flight_sport_track.txt,
animates balloon.png moving sequentially through GPS fixes,
and saves directly to GIF (no intermediate frame images).

Requirements:
    pip install matplotlib numpy contextily pyproj Pillow
"""

import re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.colors import Normalize
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.cm import ScalarMappable
from PIL import Image
import contextily as cx
from pyproj import Transformer
import warnings
warnings.filterwarnings("ignore")


# ═══════════════════════════════════════════════════════════════
#  1.  PARSER
# ═══════════════════════════════════════════════════════════════
def parse_flight_log(filepath):
    """
    Parse the LoRa receiver log.  Returns list of dicts with
    keys: packet, rssi, lat, lon, alt, sats   (GPS-only packets)
    """
    with open(filepath, "r") as f:
        text = f.read()

    blocks = text.split("================================")
    records = []
    for blk in blocks:
        if "Lat" not in blk:
            continue
        pkt  = re.search(r"Packet\s*:\s*#(\d+)", blk)
        rssi = re.search(r"RSSI\s*:\s*(-?\d+)", blk)
        lat  = re.search(r"Lat\s*:\s*([\d.]+)", blk)
        lon  = re.search(r"Lon\s*:\s*(-?[\d.]+)", blk)
        alt  = re.search(r"Alt\s*:\s*([\d.]+)", blk)
        sats = re.search(r"Sats\s*:\s*(\d+)", blk)
        if lat and lon:
            records.append({
                "packet": int(pkt.group(1)) if pkt else 0,
                "rssi":   int(rssi.group(1)) if rssi else 0,
                "lat":    float(lat.group(1)),
                "lon":    float(lon.group(1)),
                "alt":    float(alt.group(1)) if alt else 0.0,
                "sats":   int(sats.group(1)) if sats else 0,
            })
    return records


# ── Parse both flights ───────────────────────────────────────
flight_a = parse_flight_log("flight_alumni_field.txt")
flight_s = parse_flight_log("flight_sport_track.txt")

# Build combined sequential arrays  (Flight A → Flight B)
all_pts = flight_a + flight_s
lats = np.array([p["lat"]  for p in all_pts])
lons = np.array([p["lon"]  for p in all_pts])
alts = np.array([p["alt"]  for p in all_pts])
rssis = np.array([p["rssi"] for p in all_pts], dtype=float)
sats = np.array([p["sats"] for p in all_pts])
n_a = len(flight_a)   # index where Flight B starts
N   = len(all_pts)

# ═══════════════════════════════════════════════════════════════
#  2.  PROJECTION
# ═══════════════════════════════════════════════════════════════
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
xs, ys = transformer.transform(lons, lats)

# Tower Base from the LoRa field-test (for reference marker)
TOWER_LAT, TOWER_LON = 37.570679, -84.289675
tx, ty = transformer.transform(TOWER_LON, TOWER_LAT)

# Scale helper
ref1x, ref1y = transformer.transform(lons[0], lats[0])
ref2x, ref2y = transformer.transform(lons[0], lats[0] + 0.001)
scale_m = (ref2y - ref1y) / (0.001 * 111320.0)

def real_m(m):
    return m * scale_m


# ═══════════════════════════════════════════════════════════════
#  3.  FIGURE SETUP  (1 × 1 ratio)
# ═══════════════════════════════════════════════════════════════
DPI  = 120
SIZE = 8          # inches → 960 × 960 px
BG   = "#060b11"

fig = plt.figure(figsize=(SIZE, SIZE), dpi=DPI, facecolor=BG)

# Main map axes (square, takes ~80 % of height)
ax_map = fig.add_axes([0.04, 0.18, 0.92, 0.76])
ax_map.set_facecolor(BG)
ax_map.set_aspect("equal")

# Altitude mini-graph (bottom strip)
ax_alt = fig.add_axes([0.12, 0.045, 0.76, 0.10])
ax_alt.set_facecolor("#0a1210")
for sp in ax_alt.spines.values():
    sp.set_color("#335533")
    sp.set_alpha(0.5)
ax_alt.tick_params(colors="#88aa88", labelsize=6)
ax_alt.set_ylabel("Alt (m)", color="#88aa88", fontsize=7,
                   fontfamily="monospace")
ax_alt.set_xlabel("Packet #", color="#88aa88", fontsize=7,
                   fontfamily="monospace")

# ═══════════════════════════════════════════════════════════════
#  4.  STATIC MAP ELEMENTS
# ═══════════════════════════════════════════════════════════════
margin = real_m(500)
ax_map.set_xlim(min(xs.min(), tx) - margin, max(xs.max(), tx) + margin)
ax_map.set_ylim(min(ys.min(), ty) - margin, max(ys.max(), ty) + margin)

# ── Satellite basemap ────────────────────────────────────────
cx.add_basemap(ax_map, source=cx.providers.Esri.WorldImagery,
               zoom=16, zorder=1, attribution=False)

# Dim overlay
xlim = ax_map.get_xlim()
ylim = ax_map.get_ylim()
ax_map.add_patch(mpatches.Rectangle(
    (xlim[0], ylim[0]), xlim[1]-xlim[0], ylim[1]-ylim[0],
    facecolor="black", alpha=0.40, zorder=2))

# Subtle grid
ax_map.grid(True, color="#ffffff", alpha=0.03, linewidth=0.4, zorder=3)

# ── Tower marker (gold star) ─────────────────────────────────
for r, a in [(real_m(90), 0.12), (real_m(55), 0.24), (real_m(28), 0.40)]:
    ax_map.add_patch(plt.Circle((tx, ty), r, color="#FFD700",
                                alpha=a, zorder=8))
ax_map.scatter(tx, ty, s=350, marker="*", color="white",
               edgecolors="#FFD700", linewidths=1.6, zorder=9,
               path_effects=[pe.withStroke(linewidth=2.5,
                                           foreground="#FFD700")])
ax_map.text(tx, ty + real_m(55), "Tower", ha="center", va="bottom",
            fontsize=7, color="#FFD700", fontweight="bold",
            fontfamily="monospace", zorder=10,
            path_effects=[pe.withStroke(linewidth=2, foreground="black")])

# ── Launch site labels ───────────────────────────────────────
for label, idx in [("Alumni Field\nLaunch", 0),
                   ("Sport Track\nLaunch", n_a)]:
    ax_map.annotate(
        label, xy=(xs[idx], ys[idx]),
        xytext=(xs[idx] + real_m(110), ys[idx] + real_m(90)),
        fontsize=6.5, color="#aaffaa", fontfamily="monospace",
        fontweight="bold", alpha=0.85, ha="left", va="bottom",
        zorder=10,
        path_effects=[pe.withStroke(linewidth=2, foreground="black")],
        arrowprops=dict(arrowstyle="-", color="#55ff55",
                        lw=0.6, alpha=0.4))

# ── Full path ghost (very faint, so viewer sees the route) ──
cmap = plt.cm.RdYlGn
norm = Normalize(vmin=rssis.min(), vmax=rssis.max())
for i in range(1, N):
    col = cmap(norm(rssis[i]))
    ax_map.plot([xs[i-1], xs[i]], [ys[i-1], ys[i]],
                color=col, alpha=0.06, linewidth=0.8, zorder=4)

# ── Altitude mini-graph static background ────────────────────
ax_alt.fill_between(range(N), alts, alts.min() - 5,
                    color="#114411", alpha=0.15, zorder=1)
ax_alt.axvline(n_a, color="#FFD700", alpha=0.3, lw=0.8,
               linestyle="--", zorder=2)
ax_alt.text(n_a + 1, alts.max(), "Flight B →",
            fontsize=5.5, color="#FFD700", alpha=0.5,
            fontfamily="monospace", va="top", zorder=3)
ax_alt.text(n_a - 1, alts.max(), "← Flight A",
            fontsize=5.5, color="#FFD700", alpha=0.5,
            fontfamily="monospace", va="top", ha="right", zorder=3)
ax_alt.set_xlim(0, N - 1)
ax_alt.set_ylim(alts.min() - 5, alts.max() + 10)

# ── North arrow ──────────────────────────────────────────────
na_x = xlim[0] + real_m(40)
na_y = ylim[1] - real_m(40)
ax_map.annotate("N", xy=(na_x, na_y),
                xytext=(na_x, na_y - real_m(130)),
                fontsize=11, color="white", ha="center",
                fontfamily="monospace", fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="white", lw=2),
                zorder=14,
                path_effects=[pe.withStroke(linewidth=2,
                                           foreground="black")])

ax_map.set_axis_off()

# ═══════════════════════════════════════════════════════════════
#  5.  BALLOON IMAGE
# ═══════════════════════════════════════════════════════════════
try:
    balloon_img = Image.open("balloon.png").convert("RGBA")
    # Scale down for the map
    bw = 48
    balloon_img = balloon_img.resize(
        (bw, int(bw * balloon_img.height / balloon_img.width)),
        Image.LANCZOS)
    balloon_arr = np.array(balloon_img)
    HAS_BALLOON = True
except FileNotFoundError:
    HAS_BALLOON = False
    print("⚠  balloon.png not found – using fallback marker.")


# ═══════════════════════════════════════════════════════════════
#  6.  ANIMATED ARTISTS
# ═══════════════════════════════════════════════════════════════

# Trail line (grows each frame)
trail_line, = ax_map.plot([], [], color="#00ff88", alpha=0.55,
                          linewidth=1.6, zorder=5,
                          path_effects=[pe.withStroke(linewidth=3,
                                                     foreground="#003311")])

# Glow halos around current position (3 layers)
glow_circles = []
for radius, alpha in [(real_m(80), 0.08),
                      (real_m(50), 0.16),
                      (real_m(25), 0.30)]:
    c = plt.Circle((0, 0), radius, color="#00ff88",
                    alpha=alpha, zorder=6)
    ax_map.add_patch(c)
    glow_circles.append(c)

# Current-position dot (fallback if no balloon.png)
dot = ax_map.scatter([], [], s=120, color="#00ff88",
                     edgecolors="white", linewidths=0.8,
                     zorder=8, alpha=0.95)

# Balloon AnnotationBbox (if image available)
if HAS_BALLOON:
    im_box = OffsetImage(balloon_arr, zoom=1.0)
    ab = AnnotationBbox(im_box, (xs[0], ys[0]),
                        frameon=False, zorder=12)
    ax_map.add_artist(ab)
else:
    ab = None

# Altitude marker on mini-graph
alt_dot, = ax_alt.plot([], [], "o", color="#00ff88",
                       markersize=5, zorder=5)
alt_line, = ax_alt.plot([], [], color="#00ff88", alpha=0.7,
                        linewidth=1.2, zorder=4)

# HUD text overlays
hud_template = (
    " PKT #{pkt:>4d}   RSSI {rssi:>4d} dBm\n"
    " Alt {alt:>6.1f} m   Sats {sats}\n"
    " {lat:.6f}°N  {lon:.6f}°W"
)
hud_text = ax_map.text(
    0.98, 0.98, "", transform=ax_map.transAxes,
    ha="right", va="top", fontsize=7.5, color="#bbffbb",
    fontfamily="monospace", fontweight="bold",
    bbox=dict(boxstyle="round,pad=0.5", facecolor="#0a1a0a",
              edgecolor="#336633", alpha=0.85, linewidth=0.7),
    zorder=15,
    path_effects=[pe.withStroke(linewidth=1.5, foreground="#001100")])

# Frame counter / progress bar text
progress_text = ax_map.text(
    0.02, 0.98, "", transform=ax_map.transAxes,
    ha="left", va="top", fontsize=7, color="#88aa88",
    fontfamily="monospace",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="#0a1a0a",
              edgecolor="#224422", alpha=0.75, linewidth=0.5),
    zorder=15)

# Title
ax_map.text(0.50, 1.02, "LoRa Balloon Flight  ·  Berea, KY",
            transform=ax_map.transAxes, ha="center", va="bottom",
            fontsize=12, color="white", fontweight="bold",
            fontfamily="monospace", zorder=15,
            path_effects=[pe.withStroke(linewidth=3,
                                       foreground="#004400")])

# Attribution
ax_map.text(0.99, 0.003, "Basemap: Esri World Imagery",
            transform=ax_map.transAxes, ha="right", va="bottom",
            fontsize=5, color="white", alpha=0.35,
            fontfamily="monospace", zorder=15)


# ═══════════════════════════════════════════════════════════════
#  7.  ANIMATION FUNCTION
# ═══════════════════════════════════════════════════════════════

# Subsample for a reasonable GIF size  (~150-200 frames)
STEP  = max(1, N // 180)
frame_indices = list(range(0, N, STEP))
if frame_indices[-1] != N - 1:
    frame_indices.append(N - 1)
# Add a few hold frames at the end
frame_indices += [N - 1] * 12
NFRAMES = len(frame_indices)


def animate(frame_num):
    idx = frame_indices[frame_num]
    pt  = all_pts[idx]

    cx_now, cy_now = xs[idx], ys[idx]

    # ── Trail (all points up to current) ──────────────────
    trail_line.set_data(xs[:idx+1], ys[:idx+1])
    trail_col = cmap(norm(rssis[idx]))
    trail_line.set_color(trail_col)

    # ── Glow circles ─────────────────────────────────────
    for circ in glow_circles:
        circ.center = (cx_now, cy_now)
        circ.set_color(trail_col)

    # ── Dot / Balloon position ───────────────────────────
    dot.set_offsets([[cx_now, cy_now]])
    dot.set_facecolors([trail_col])
    if ab is not None:
        ab.xybox = (cx_now, cy_now)

    # ── Altitude graph ───────────────────────────────────
    alt_line.set_data(range(idx+1), alts[:idx+1])
    alt_dot.set_data([idx], [alts[idx]])
    alt_dot.set_color(trail_col)
    alt_line.set_color(trail_col)

    # ── HUD ──────────────────────────────────────────────
    flight_label = "A" if idx < n_a else "B"
    hud_text.set_text(
        f" Flight {flight_label}  PKT #{pt['packet']:>4d}\n"
        f" RSSI {pt['rssi']:>4d} dBm   Sats {pt['sats']}\n"
        f" Alt {pt['alt']:>7.1f} m\n"
        f" {pt['lat']:.6f}°N  {abs(pt['lon']):.6f}°W"
    )

    pct = int(100 * frame_num / max(1, NFRAMES - 1))
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    progress_text.set_text(f" {bar} {pct:>3d}%\n Frame {frame_num+1}/{NFRAMES}")

    return (trail_line, dot, alt_line, alt_dot,
            hud_text, progress_text, *glow_circles,
            *([ab] if ab else []))


# ═══════════════════════════════════════════════════════════════
#  8.  RENDER GIF  (PillowWriter – no temp frame files)
# ═══════════════════════════════════════════════════════════════
print(f"Rendering {NFRAMES} frames …")

anim = FuncAnimation(fig, animate, frames=NFRAMES,
                     blit=False, repeat=False)

OUT = "lora_balloon_flight.gif"
writer = PillowWriter(fps=14)
anim.save(OUT, writer=writer, dpi=DPI, savefig_kwargs={
    "facecolor": BG, "edgecolor": "none"})

plt.close(fig)
print(f"✓ Saved: {OUT}  ({NFRAMES} frames, {SIZE*DPI}×{SIZE*DPI} px)")
