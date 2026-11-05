"""Shared dark chart theme so every generated image matches."""
from cycler import cycler

BG = "#0f1115"
FG = "#e8e8e8"
GRID = "#2a2d34"
MUTED = "#9aa0aa"
PALETTE = ["#4f8df5", "#f5a742", "#4fd18b", "#e0605e", "#b07cf0"]

DARK_RC = {
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "axes.edgecolor": GRID,
    "axes.labelcolor": FG,
    "axes.titlecolor": FG,
    "text.color": FG,
    "xtick.color": FG,
    "ytick.color": FG,
    "grid.color": GRID,
    "legend.facecolor": BG,
    "legend.edgecolor": GRID,
    "legend.labelcolor": FG,
    "axes.prop_cycle": cycler(color=PALETTE),
}
