import math
import os
import tempfile
import threading

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf


_PLOT_LOCK = threading.Lock()


class PortfolioPerformanceChartProvider:

    PERIOD = "2y"
    BENCHMARKS = {
        "SPY": "S&P 500 (SPY)",
        "DIA": "Dow Jones Industrial Average (DIA)"
    }

    def generate(self, holdings):
        weights, weight_total, error = self._holding_weights(holdings)
        if error:
            return {"status": "failed", "error": error}

        tickers = list(dict.fromkeys(
            list(weights) + list(self.BENCHMARKS)
        ))
        try:
            downloaded = yf.download(
                tickers=tickers,
                period=self.PERIOD,
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=False,
                timeout=20
            )
        except Exception as exc:
            return {
                "status": "failed",
                "error": f"Historical portfolio prices could not be retrieved: {exc}"
            }

        close_prices = self._close_prices(downloaded, tickers)
        missing = [ticker for ticker in tickers if ticker not in close_prices]
        if missing:
            return {
                "status": "failed",
                "error": (
                    "Historical prices were unavailable for: "
                    + ", ".join(missing)
                )
            }

        prices = pd.concat(
            [close_prices[ticker].rename(ticker) for ticker in tickers],
            axis=1,
            join="inner"
        ).dropna()
        if prices.empty:
            return {
                "status": "failed",
                "error": (
                    "The holdings and both benchmarks have no overlapping "
                    "historical prices."
                )
            }

        ytd = self._year_to_date_returns(prices, weights)
        rolling = self._rolling_12_month_returns(prices, weights)
        if ytd is None or rolling is None:
            return {
                "status": "failed",
                "error": (
                    "Not enough overlapping adjusted-price history to "
                    "calculate both year-to-date and rolling 12-month returns."
                )
            }

        charts = []
        try:
            charts.append(self._save_chart(
                ytd,
                "Average Year-to-Date Return",
                "Portfolio YTD return, compared with market benchmarks"
            ))
            charts.append(self._save_chart(
                rolling,
                "Rolling 12-Month Return",
                "Trailing 12-month return, compared with market benchmarks"
            ))
        except Exception as exc:
            for chart in charts:
                try:
                    os.unlink(chart["path"])
                except FileNotFoundError:
                    pass
            return {
                "status": "failed",
                "error": f"Portfolio performance charts could not be generated: {exc}"
            }

        return {
            "status": "completed",
            "charts": charts,
            "source": "Yahoo Finance adjusted daily prices",
            "holdings": list(weights),
            "weight_total": weight_total
        }

    @staticmethod
    def _holding_weights(holdings):
        if not isinstance(holdings, list):
            return {}, 0, "Portfolio holdings are unavailable."

        weights = {}
        for holding in holdings:
            if not isinstance(holding, dict):
                return {}, 0, "Portfolio holding data is invalid."
            ticker = str(holding.get("ticker") or "").strip().upper()
            weight = holding.get("weight")
            if (
                not ticker
                or not isinstance(weight, (int, float))
                or isinstance(weight, bool)
                or not math.isfinite(weight)
                or weight < 0
            ):
                return {}, 0, (
                    "Every portfolio holding needs a ticker and a "
                    "finite, non-negative numeric weight."
                )
            if weight > 0:
                weights[ticker] = weights.get(ticker, 0) + weight

        total_weight = sum(weights.values())
        if not weights or total_weight <= 0:
            return {}, 0, "No valid positive holding weights were available."

        return {
            ticker: weight / total_weight
            for ticker, weight in weights.items()
        }, total_weight, None

    @staticmethod
    def _close_prices(downloaded, tickers):
        if not isinstance(downloaded, pd.DataFrame) or downloaded.empty:
            return {}

        result = {}
        columns = downloaded.columns
        if isinstance(columns, pd.MultiIndex):
            for ticker in tickers:
                for column in columns:
                    parts = {str(part).upper() for part in column}
                    if ticker.upper() in parts and "CLOSE" in parts:
                        values = downloaded[column]
                        if isinstance(values, pd.DataFrame):
                            values = values.iloc[:, 0]
                        result[ticker] = pd.to_numeric(
                            values,
                            errors="coerce"
                        ).dropna()
                        break
        elif len(tickers) == 1 and "Close" in columns:
            result[tickers[0]] = pd.to_numeric(
                downloaded["Close"],
                errors="coerce"
            ).dropna()
        return result

    @classmethod
    def _year_to_date_returns(cls, prices, weights):
        year_start = pd.Timestamp(
            year=prices.index[-1].year,
            month=1,
            day=1,
            tz=prices.index.tz
        )
        baseline_position = prices.index.searchsorted(year_start, side="left") - 1
        if baseline_position < 0:
            return None

        ytd_prices = prices.loc[prices.index >= year_start]
        if ytd_prices.empty:
            return None
        baseline = prices.iloc[baseline_position]
        returns = pd.DataFrame(index=ytd_prices.index)
        portfolio_return = sum(
            (ytd_prices[ticker] / baseline[ticker] - 1) * weight
            for ticker, weight in weights.items()
        )
        returns["Portfolio (weighted)"] = portfolio_return * 100
        for ticker, label in cls.BENCHMARKS.items():
            returns[label] = (
                ytd_prices[ticker] / baseline[ticker] - 1
            ) * 100
        return returns

    @classmethod
    def _rolling_12_month_returns(cls, prices, weights):
        dates = prices.index
        trailing_start = dates[-1] - pd.DateOffset(years=1)
        plotted_dates = dates[dates >= trailing_start]
        if plotted_dates.empty:
            return None

        target_dates = plotted_dates - pd.DateOffset(years=1)
        baseline_positions = dates.get_indexer(target_dates, method="pad")
        valid = baseline_positions >= 0
        if not valid.any():
            return None

        plotted_dates = plotted_dates[valid]
        baseline_prices = prices.iloc[baseline_positions[valid]]
        current_prices = prices.loc[plotted_dates]
        returns = pd.DataFrame(index=plotted_dates)
        portfolio_return = sum(
            (
                current_prices[ticker].to_numpy()
                / baseline_prices[ticker].to_numpy()
                - 1
            ) * weight
            for ticker, weight in weights.items()
        )
        returns["Portfolio (weighted)"] = portfolio_return * 100
        for ticker, label in cls.BENCHMARKS.items():
            returns[label] = (
                current_prices[ticker].to_numpy()
                / baseline_prices[ticker].to_numpy()
                - 1
            ) * 100
        return returns

    @staticmethod
    def _save_chart(returns, title, description):
        handle = tempfile.NamedTemporaryFile(
            prefix="performance_portfolio_return_",
            suffix=".png",
            delete=False
        )
        path = handle.name
        handle.close()

        figure = None
        try:
            with _PLOT_LOCK:
                figure, axis = plt.subplots(
                    figsize=(11, 6.5),
                    constrained_layout=True
                )
                for column in returns.columns:
                    axis.plot(
                        returns.index,
                        returns[column],
                        linewidth=2,
                        label=column
                    )
                axis.axhline(
                    0,
                    color="#64748b",
                    linewidth=0.8,
                    alpha=0.7
                )
                axis.set_title(
                    title,
                    loc="left",
                    fontsize=16,
                    fontweight="bold"
                )
                axis.set_ylabel("Return (%)")
                axis.set_xlabel("Date")
                axis.grid(True, color="#cbd5e1", alpha=0.45)
                axis.legend(loc="best", frameon=False)
                axis.xaxis.set_major_locator(
                    mdates.MonthLocator(interval=2)
                )
                axis.xaxis.set_major_formatter(
                    mdates.DateFormatter("%b %Y")
                )
                figure.savefig(
                    path,
                    format="png",
                    dpi=150,
                    facecolor="white"
                )
        except Exception:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            raise
        finally:
            if figure is not None:
                with _PLOT_LOCK:
                    plt.close(figure)

        return {
            "path": path,
            "title": title,
            "caption": (
                f"{description}. The portfolio line uses the listed holding "
                "weights normalized to their total; SPY and DIA are used as "
                "adjusted-total-return proxies for the S&P 500 and Dow Jones "
                "Industrial Average. Source: Yahoo Finance adjusted daily "
                "prices."
            )
        }
