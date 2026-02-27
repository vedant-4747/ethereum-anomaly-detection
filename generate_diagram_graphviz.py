import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ──────────────────────────────────────────────
# Architecture Diagram for IEEE Paper
# On-chain Anomaly Detection Pipeline
# Uses only matplotlib — no external binaries
# ──────────────────────────────────────────────

NODES = [
    {
        "title": "Data\nSources",
        "sub":   "BigQuery · Kaggle\nEtherscan",
    },
    {
        "title": "Data\nIngestion",
        "sub":   "Download · Sample\nStructure & Store",
    },
    {
        "title": "Preprocessing\n& Cleaning",
        "sub":   "Normalize · Standardize\nFormat Addresses",
    },
    {
        "title": "Feature\nEngineering",
        "sub":   "Tx Count · Ratios\nActive Days · Peers",
    },
    {
        "title": "Modeling\nLayer",
        "sub":   "Unsupervised (Iso. Forest, LOF)\nSupervised (XGBoost, RF)",
    },
    {
        "title": "Evaluation &\nExplainability",
        "sub":   "Precision@k · ROC-AUC\nSHAP Interpretability",
    },
    {
        "title": "Visualization\n& Reporting",
        "sub":   "Dashboards · Sankey\nReports & GitHub",
    },
]

# Layout constants
FIG_W, FIG_H = 22, 5
N = len(NODES)
BOX_W, BOX_H = 2.5, 1.8
GAP = 0.55          # gap between boxes
TOTAL_W = N * BOX_W + (N - 1) * GAP
X_START = (FIG_W - TOTAL_W) / 2
Y_CENTER = FIG_H / 2 - BOX_H / 2

COLORS = {
    "box_face":   "#FFFFFF",
    "box_edge":   "#1A1A2E",
    "title_fg":   "#1A1A2E",
    "sub_fg":     "#444444",
    "arrow":      "#1A1A2E",
    "bg":         "#F4F6F9",
    "header_bg":  "#1A1A2E",
    "header_fg":  "#FFFFFF",
}

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor(COLORS["bg"])
ax.set_facecolor(COLORS["bg"])
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")

# ── Header ───────────────────────────────────────
header = FancyBboxPatch(
    (0.3, FIG_H - 0.65), FIG_W - 0.6, 0.52,
    boxstyle="round,pad=0.05",
    facecolor=COLORS["header_bg"], edgecolor="none", zorder=2
)
ax.add_patch(header)
ax.text(
    FIG_W / 2, FIG_H - 0.39,
    "Proposed System Architecture for On-Chain Anomaly Detection",
    ha="center", va="center",
    fontsize=13, fontweight="bold",
    color=COLORS["header_fg"], fontfamily="DejaVu Sans", zorder=3
)

# ── Draw each block ───────────────────────────────
for i, node in enumerate(NODES):
    x = X_START + i * (BOX_W + GAP)
    y = Y_CENTER

    # Shadow
    shadow = FancyBboxPatch(
        (x + 0.07, y - 0.07), BOX_W, BOX_H,
        boxstyle="round,pad=0.12",
        facecolor="#CCCCCC", edgecolor="none", zorder=1, alpha=0.5
    )
    ax.add_patch(shadow)

    # Main box
    box = FancyBboxPatch(
        (x, y), BOX_W, BOX_H,
        boxstyle="round,pad=0.12",
        facecolor=COLORS["box_face"],
        edgecolor=COLORS["box_edge"],
        linewidth=1.8, zorder=2
    )
    ax.add_patch(box)

    # Step number badge
    badge_r = 0.18
    badge = plt.Circle(
        (x + BOX_W / 2, y + BOX_H + 0.005),
        badge_r,
        color=COLORS["box_edge"], zorder=5
    )
    ax.add_patch(badge)
    ax.text(
        x + BOX_W / 2, y + BOX_H,
        str(i + 1),
        ha="center", va="center",
        fontsize=8, fontweight="bold",
        color="white", zorder=6
    )

    # Title text
    ax.text(
        x + BOX_W / 2, y + BOX_H * 0.62,
        node["title"],
        ha="center", va="center",
        fontsize=10.5, fontweight="bold",
        color=COLORS["title_fg"],
        fontfamily="DejaVu Sans", zorder=3
    )

    # Divider line
    ax.plot(
        [x + 0.25, x + BOX_W - 0.25],
        [y + BOX_H * 0.40, y + BOX_H * 0.40],
        color="#CCCCCC", linewidth=0.8, zorder=3
    )

    # Sub-label text
    ax.text(
        x + BOX_W / 2, y + BOX_H * 0.185,
        node["sub"],
        ha="center", va="center",
        fontsize=8, color=COLORS["sub_fg"],
        fontfamily="DejaVu Sans", zorder=3,
        linespacing=1.55
    )

    # ── Arrow to next block ──────────────
    if i < N - 1:
        ax_start = x + BOX_W + 0.04
        ax_end   = x + BOX_W + GAP - 0.04
        ay       = y + BOX_H / 2
        ax.annotate(
            "", xy=(ax_end, ay), xytext=(ax_start, ay),
            arrowprops=dict(
                arrowstyle="->,head_width=0.35,head_length=0.22",
                color=COLORS["arrow"], lw=1.8
            ),
            zorder=4
        )

# ── Footer caption ────────────────────────────────
ax.text(
    FIG_W / 2, 0.22,
    "Fig. 1.  Sequential pipeline architecture for blockchain anomaly detection — "
    "from raw transaction data to anomaly insights.",
    ha="center", va="center",
    fontsize=9, color="#555555",
    fontstyle="italic", fontfamily="DejaVu Sans"
)

plt.tight_layout(pad=0)
output_file = "architecture_diagram.png"
plt.savefig(output_file, dpi=300, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print(f"✅  Diagram saved → {output_file}  (300 dpi, IEEE-ready)")
