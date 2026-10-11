import math
import os
import tempfile
import threading

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


_PLOT_LOCK = threading.Lock()


class PortfolioAllocationChartProvider:

    COLORS = {
        "stock": "#4472C4",
        "etf": "#70AD47",
        "unresolved": "#A5A5A5"
    }

    def generate(self, holdings):
        if not isinstance(holdings, list):
            return {
                "status": "failed",
                "error": "Portfolio holdings are unavailable."
            }

        plotted = []
        for holding in holdings:
            if not isinstance(holding, dict):
                continue
            ticker = str(holding.get("ticker") or "").strip().upper()
            weight = holding.get("weight")
            if (
                not ticker
                or not isinstance(weight, (int, float))
                or isinstance(weight, bool)
                or not math.isfinite(weight)
                or weight < 0
            ):
                continue
            entity_type = holding.get("entity_type", "unresolved")
            if entity_type not in self.COLORS:
                entity_type = "unresolved"
            plotted.append((ticker, weight, entity_type))

        if not plotted:
            return {
                "status": "failed",
                "error": "No valid holding weights were available to chart."
            }

        total_weight = sum(weight for _, weight, _ in plotted)
        exact_total = math.isclose(total_weight, 100.0, abs_tol=0.01)
        with _PLOT_LOCK:
            figure, axis = plt.subplots(
                figsize=(9, max(4.5, min(12, len(plotted) * 0.35)))
            )
            positions = list(range(len(plotted)))
            bars = axis.barh(
                positions,
                [weight for _, weight, _ in plotted],
                color=[
                    self.COLORS[entity_type]
                    for _, _, entity_type in plotted
                ]
            )
            axis.set_yticks(positions)
            axis.set_yticklabels(
                [ticker for ticker, _, _ in plotted],
            )
            axis.invert_yaxis()
            axis.set_xlabel(
                "Portfolio proportion (%)"
                if exact_total
                else "Stated holding weight (%)"
            )
            axis.set_title("Portfolio Allocation by Holding")
            axis.grid(axis="x", alpha=0.25)
            for bar, (_, weight, _) in zip(bars, plotted):
                axis.annotate(
                    f"{weight:g}%",
                    (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    xytext=(4, 0),
                    textcoords="offset points",
                    ha="left",
                    va="center",
                    fontsize=8
                )
            handles = [
                plt.Rectangle((0, 0), 1, 1, color=color, label=label)
                for label, color in (
                    ("Stock", self.COLORS["stock"]),
                    ("ETF", self.COLORS["etf"]),
                    ("Unclassified", self.COLORS["unresolved"])
                )
                if any(item[2] == label.lower() for item in plotted)
            ]
            axis.legend(handles=handles, loc="best")
            if not exact_total:
                axis.text(
                    0.99,
                    0.98,
                    f"Listed weights total {total_weight:.2f}%; not normalized",
                    transform=axis.transAxes,
                    ha="right",
                    va="bottom",
                    fontsize=8
                )
            figure.tight_layout()

            handle = tempfile.NamedTemporaryFile(
                prefix="performance_portfolio_allocation_",
                suffix=".png",
                delete=False
            )
            path = handle.name
            handle.close()
            try:
                figure.savefig(path, dpi=150)
            except Exception as error:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
                return {
                    "status": "failed",
                    "error": f"Portfolio allocation chart failed: {error}"
                }
            finally:
                plt.close(figure)

        return {
            "status": "completed",
            "path": path,
            "caption": (
                "Portfolio allocation by holding "
                "(blue: stock, green: ETF, gray: unclassified)."
                if exact_total
                else (
                    "Stated holding weights by instrument type; listed "
                    f"weights total {total_weight:.2f}% and are not normalized."
                )
            ),
            "total_weight": total_weight
        }
