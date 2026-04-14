import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import contextily as cx
from pyproj import Transformer
import warnings
warnings.filterwarnings("ignore")

# ── Data ─────────────────────────────────────────────────────
points = [
    ("Tower Base",         37.570679, -84.289675,   0,      0),
    ("Parking",            37.56984,  -84.28946,  -63,    262),
    ("2nd Stop",           37.56693,  -84.28813,  -73,   1437),
    ("Hiking Trail",       37.56572,  -84.28803,  -73,   1876),
    ("Church",             37.56131,  -84.28601,  -96,   3593),
    ("Dead End",           37.56180,  -84.28292,  -96,   3786),
    ("Bratchet",           37.55460,  -84.27962,  -98,   6534),
    ("Bethlehem Baptist",  37.55912,  -84.28295, -101,   4637),
    ("Sweet Bakery",       37.55697,  -84.28159,  -97,   5594),
    ("Angle / Max Range",  37.54925,  -84.27275,  -98,   9195),
    ("Bridge",             37.56633,  -84.28807,  -88,   1652),
    ("Alumni Circle",      37.57106,  -84.28880,  -78,    263),
    ("Pressers",           37.57038,  -84.29258,  -95,    874),
    ("Pressers Parking",   37.56937,  -84.29225,  -81,    909),
    ("Chestnut Mall",      37.56835,  -84.29714,  -97,   2350),
]

names  = [p[0] for p in points]
lats   = np.array([p[1] for p in points])
lons   = np.array([p[2] for p in points])
rssis  = np.array([p[3] for p in points], dtype=float)
dists  = np.array([p[4] for p in points], dtype=float)

# ── Convert lat/lon → Web Mercator (EPSG:3857) ──────────────
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
xs, ys = transformer.transform(lons, lats)

# ── Colour map: green (strong) → red (weak) ─────────────────
rssi_test  = rssis[1:]
rssi_min, rssi_max = rssi_test.min(), rssi_test.max()
norm  = Normalize(vmin=rssi_min, vmax=rssi_max)
cmap  = plt.cm.RdYlGn

# ── Figure ───────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(20, 20), dpi=150)
bg = "#080c10"
fig.patch.set_facecolor(bg)
ax.set_facecolor(bg)

# ── Scale helpers (Web Mercator metres are larger than local) ─
# Compute a reference scale for ring radii and glow sizes
# 1 degree lat ≈ 111320 m, but in Web Mercator the scale factor
# at this latitude stretches things.  We use the actual projected
# distance of 1 arc-second to calibrate ring radii.
ref_lon1, ref_lat1 = transformer.transform(lons[0], lats[0])
ref_lon2, ref_lat2 = transformer.transform(lons[0], lats[0] + 0.001)
scale_m = (ref_lat2 - ref_lat1) / (0.001 * 111320.0)  # mercator m per real m

def real_m(m):
    """Convert real-world metres to Web Mercator map units."""
    return m * scale_m

# ── Range rings (real-world metres) ──────────────────────────
ring_m   = [500, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9195]
for r in ring_m:
    theta  = np.linspace(0, 2*np.pi, 360)
    rx = xs[0] + real_m(r) * np.cos(theta)
    ry = ys[0] + real_m(r) * np.sin(theta)
    alpha  = 0.10 if r % 1000 != 0 else 0.22
    lw     = 0.5  if r % 1000 != 0 else 0.9
    ax.plot(rx, ry, color="white", alpha=alpha, linewidth=lw,
            linestyle="--" if r % 1000 != 0 else ":", zorder=4)
    ax.text(xs[0] + real_m(r + 30), ys[0] - real_m(50),
            "{:.1f}km".format(r/1000),
            color="white", fontsize=6.5, alpha=0.45,
            fontfamily="monospace", va="top", zorder=5)

# ── Signal "cone" fill ───────────────────────────────────────
spread = real_m(25)
for i in range(1, len(points)):
    col   = cmap(norm(rssis[i]))
    ax.fill([xs[0], xs[i]-spread, xs[i]+spread],
            [ys[0], ys[i]-spread, ys[i]+spread],
            color=col, alpha=0.10, zorder=5)

# ── Connection lines ─────────────────────────────────────────
for i in range(1, len(points)):
    col = cmap(norm(rssis[i]))
    ax.plot([xs[0], xs[i]], [ys[0], ys[i]],
            color=col, alpha=0.50, linewidth=1.4,
            linestyle="--", zorder=6)

# ── Glow halos per point ─────────────────────────────────────
for i in range(1, len(points)):
    col = cmap(norm(rssis[i]))
    for radius, alpha in [(real_m(350),0.04),
                          (real_m(240),0.07),
                          (real_m(140),0.13),
                          (real_m(75), 0.22)]:
        halo = plt.Circle((xs[i], ys[i]), radius,
                          color=col, alpha=alpha, zorder=7)
        ax.add_patch(halo)

# ── Scatter: outer ring + filled dot ─────────────────────────
for i in range(1, len(points)):
    col  = cmap(norm(rssis[i]))
    size = 180 + (dists[i] / 9195) * 400
    for s_mult, a in [(4.0,0.18),(2.5,0.28),(1.4,0.45)]:
        ax.scatter(xs[i], ys[i], s=size*s_mult,
                   facecolors="none", edgecolors=col,
                   linewidths=0.8, alpha=a, zorder=8)
    ax.scatter(xs[i], ys[i], s=size*0.55,
               color=col, alpha=0.95,
               edgecolors="white", linewidths=0.5, zorder=9)
    # RSSI value label
    ax.text(xs[i], ys[i], "{}".format(int(rssis[i])),
            ha="center", va="center",
            fontsize=6.5, color="white", fontweight="bold",
            fontfamily="monospace", zorder=11,
            path_effects=[pe.withStroke(linewidth=2, foreground="black")])

# ── Point name labels (offset to avoid overlap) ─────────────
label_offsets = {
    "Parking":          ( 0.6, -1.0),
    "2nd Stop":         ( 0.8,  0.3),
    "Hiking Trail":     ( 0.8,  0.0),
    "Church":           ( 0.8,  0.0),
    "Dead End":         ( 0.6, -0.6),
    "Bratchet":         ( 0.7,  0.3),
    "Bethlehem Baptist":( 0.8,  0.0),
    "Sweet Bakery":     ( 0.8,  0.0),
    "Angle / Max Range":( 0.0, -1.0),
    "Bridge":           (-1.2,  0.3),
    "Alumni Circle":    ( 0.7,  0.3),
    "Pressers":         (-1.2,  0.0),
    "Pressers Parking": (-1.2, -0.5),
    "Chestnut Mall":    (-1.2,  0.0),
}
for i in range(1, len(points)):
    dx, dy = label_offsets.get(names[i], (0.7, 0.0))
    ax.annotate(
        names[i],
        xy=(xs[i], ys[i]),
        xytext=(xs[i] + real_m(dx*180), ys[i] + real_m(dy*180)),
        fontsize=7, color="#eeffee", fontfamily="monospace",
        fontweight="bold", alpha=0.85,
        zorder=12,
        path_effects=[pe.withStroke(linewidth=2.5, foreground="#000000")],
        arrowprops=dict(arrowstyle="-", color="#aaffaa",
                        lw=0.6, alpha=0.5),
    )

# ── Antenna / tower marker ───────────────────────────────────
for r, a in [(real_m(300),0.12),(real_m(190),0.22),(real_m(100),0.38)]:
    ring = plt.Circle((xs[0], ys[0]), r,
                      color="#FFD700", alpha=a, zorder=9)
    ax.add_patch(ring)
ax.scatter(xs[0], ys[0], s=700, marker="*",
           color="white", edgecolors="#FFD700",
           linewidths=2, zorder=12,
           path_effects=[pe.withStroke(linewidth=3,
                                       foreground="#FFD700")])
ax.text(xs[0], ys[0] + real_m(180), "Tower Base",
        ha="center", va="bottom",
        fontsize=8, color="#FFD700", fontweight="bold",
        fontfamily="monospace", zorder=12,
        path_effects=[pe.withStroke(linewidth=2.5, foreground="#000000")])

# ── Max range annotation arrow ───────────────────────────────
mi = list(dists).index(dists.max())
ax.annotate("",
            xy=(xs[mi], ys[mi]),
            xytext=(xs[mi]+real_m(400), ys[mi]-real_m(400)),
            arrowprops=dict(arrowstyle="-|>", color="#FFD700",
                            lw=1.8, mutation_scale=14),
            zorder=13)

# ── North arrow ──────────────────────────────────────────────
pad_x = xs.min() - real_m(350)
pad_y = ys.max() - real_m(100)
ax.annotate("N", xy=(pad_x, pad_y + real_m(350)),
            xytext=(pad_x, pad_y),
            fontsize=14, color="white", ha="center",
            fontfamily="monospace", fontweight="bold",
            arrowprops=dict(arrowstyle="-|>", color="white", lw=2.5),
            zorder=14,
            path_effects=[pe.withStroke(linewidth=2, foreground="black")])

# ── Set extent & add satellite tiles ─────────────────────────
margin = real_m(800)
ax.set_xlim(xs.min() - margin, xs.max() + margin)
ax.set_ylim(ys.min() - margin*1.1, ys.max() + margin*0.6)
ax.set_aspect("equal")

# Fetch satellite tiles (Esri World Imagery)
cx.add_basemap(
    ax,
    source=cx.providers.Esri.WorldImagery,
    zoom=15,          # good detail for ~2 km span
    zorder=1,
    attribution=False,
)

# Dim the satellite image so overlays pop
# We draw a translucent dark rectangle over the whole extent
xlim = ax.get_xlim()
ylim = ax.get_ylim()
dim_rect = mpatches.Rectangle(
    (xlim[0], ylim[0]),
    xlim[1] - xlim[0],
    ylim[1] - ylim[0],
    facecolor="black", alpha=0.35, zorder=2,
)
ax.add_patch(dim_rect)

# Light grid over satellite
ax.grid(True, color="#ffffff", alpha=0.04, linewidth=0.5,
        linestyle="-", zorder=3)

# ── Colourbar ────────────────────────────────────────────────
sm = ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax, fraction=0.022, pad=0.008,
                    orientation="vertical", shrink=0.55)
cbar.set_label("RSSI  (dBm)", color="white", fontsize=11,
               labelpad=10, fontfamily="monospace")
cbar.ax.yaxis.set_tick_params(color="white", labelsize=9)
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white",
         fontfamily="monospace")
cbar.outline.set_edgecolor("white")
cbar.outline.set_alpha(0.2)

# ── Stats box ────────────────────────────────────────────────
stats = (
    "  LoRa RFM95x  SF7 / 125kHz / 915MHz  \n"
    "  Berea College Observation Tower       \n"
    "  Elevation 62°  Antenna facing South   \n"
    "──────────────────────────────────────  \n"
    "  Max range   1.74 mi  (2.81 km)        \n"
    "  Best RSSI   -63 dBm  (Parking)        \n"
    "  Worst RSSI  -101 dBm (Bethlehem)      \n"
    "  GPS lock    8–10 satellites            \n"
    "  Altitude    309 – 314 m               \n"
    "  Packets     #530+  decoded             \n"
)
ax.text(0.015, 0.015, stats,
        transform=ax.transAxes,
        ha="left", va="bottom",
        color="#ccddcc", fontsize=8.5,
        fontfamily="monospace",
        bbox=dict(boxstyle="round,pad=0.6",
                  facecolor="#0a1a0a",
                  edgecolor="#336633",
                  alpha=0.88, linewidth=0.8),
        zorder=15)

# ── Title ────────────────────────────────────────────────────
ax.set_title(
    "LoRa RF Field Test  ·  Berea, KY",
    color="white", fontsize=16, pad=16,
    fontfamily="monospace", fontweight="bold",
    path_effects=[pe.withStroke(linewidth=3, foreground="#004400")]
)

# ── Attribution line ─────────────────────────────────────────
ax.text(0.99, 0.003, "Basemap: Esri World Imagery",
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=6, color="white", alpha=0.4,
        fontfamily="monospace", zorder=15)

ax.set_axis_off()
plt.tight_layout(pad=0.3)

out = "lora_field_test_satellite.svg"
plt.savefig(out, dpi=900, bbox_inches="tight",
            facecolor=bg, edgecolor="none")
plt.close()
print("Saved:", out)