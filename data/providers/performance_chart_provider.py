import os
import tempfile
import threading

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf


# Matplotlib pyplot shares process-global state across concurrent bot requests.
_PLOT_LOCK = threading.Lock()


class PerformanceChartProvider:

    PERIOD = "1y"
    SP500_TICKER = "SPY"
    MAX_PEER_LOOKUPS = 10
    MAX_PEERS = 8
    MIN_PEERS = 3

    def generate(self, company):
        if not isinstance(company, dict):
            return {
                "status": "failed",
                "error": "Instrument details are unavailable."
            }

        ticker = str(company.get("ticker") or "").strip().upper()
        entity_type = str(
            company.get("entity_type") or ""
        ).strip().lower()
        if not ticker or entity_type not in {"stock", "etf"}:
            return {
                "status": "failed",
                "ticker": ticker or None,
                "error": (
                    "A verified stock or ETF instrument type is required."
                )
            }

        benchmark_ticker = (
            "VOO"
            if ticker == self.SP500_TICKER
            else self.SP500_TICKER
        )
        industry = company.get("industry")
        peers = []
        industry_error = None
        if entity_type == "stock":
            if not isinstance(industry, str) or not industry.strip():
                try:
                    industry = (
                        yf.Ticker(ticker).info or {}
                    ).get("industry")
                except Exception as exc:
                    industry_error = str(exc)
            if isinstance(industry, str) and industry.strip():
                industry = industry.strip()
                peers, industry_error = self._find_industry_peers(
                    ticker,
                    industry
                )
            elif not industry_error:
                industry_error = (
                    "Yahoo Finance did not report an industry for "
                    f"{ticker}."
                )

        requested_tickers = [
            ticker,
            benchmark_ticker
        ] + peers

        try:
            downloaded = yf.download(
                tickers=requested_tickers,
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
                "ticker": ticker,
                "error": f"Historical prices could not be retrieved: {exc}"
            }

        close_prices = self._close_prices(
            downloaded,
            requested_tickers
        )
        if ticker not in close_prices or benchmark_ticker not in close_prices:
            return {
                "status": "failed",
                "ticker": ticker,
                "error": (
                    f"Historical prices were unavailable for {ticker} "
                    "or the S&P 500 benchmark."
                )
            }

        primary = close_prices[ticker].dropna()
        sp500 = close_prices[benchmark_ticker].dropna()
        common_prices = pd.concat(
            [primary.rename(ticker), sp500.rename(benchmark_ticker)],
            axis=1,
            join="inner"
        ).dropna()
        if len(common_prices) < 2:
            return {
                "status": "failed",
                "ticker": ticker,
                "error": (
                    "Not enough overlapping historical prices to compare "
                    f"{ticker} with the S&P 500."
                )
            }

        performance = pd.DataFrame(
            {
                ticker: (
                    common_prices[ticker]
                    / common_prices[ticker].iloc[0]
                    - 1
                ) * 100,
                f"S&P 500 ({benchmark_ticker})": (
                    common_prices[benchmark_ticker]
                    / common_prices[benchmark_ticker].iloc[0]
                    - 1
                ) * 100
            }
        )

        industry_peer_count = 0
        industry_status = "not_applicable"
        if entity_type == "stock":
            peer_series = [
                close_prices[peer]
                for peer in peers
                if peer in close_prices
            ]
            if len(peer_series) >= self.MIN_PEERS:
                peer_returns = pd.concat(
                    [
                        series.pct_change().rename(str(index))
                        for index, series in enumerate(peer_series)
                    ],
                    axis=1
                )
                valid_peer_returns = peer_returns.dropna(
                    thresh=self.MIN_PEERS
                )
                average_return = valid_peer_returns.mean(
                    axis=1,
                    skipna=True
                )
                industry_index = (1 + average_return).cumprod()
                industry_index = industry_index[
                    industry_index.index.isin(performance.index)
                ]
                if len(industry_index) >= 2:
                    industry_index = (
                        industry_index / industry_index.iloc[0] - 1
                    ) * 100
                    industry_series_name = (
                        f"{industry} peer average"
                    )
                    performance[industry_series_name] = (
                        industry_index.reindex(performance.index)
                    )
                    industry_peer_count = len(peer_series)
                    industry_status = "available"
                else:
                    industry_error = (
                        "Industry peers did not have enough overlapping "
                        "price history."
                    )
            elif peers:
                industry_error = (
                    "Fewer than three industry peers had usable price data."
                )
            industry_status = (
                "available"
                if industry_status == "available"
                else "unavailable"
            )

        caption = (
            f"{ticker} adjusted total return since "
            f"{performance.index[0].date().isoformat()} "
            "through the latest available date in the trailing year; "
            "source: Yahoo Finance adjusted daily prices"
        )
        if industry_status == "available":
            caption += (
                f"; industry line is an equal-weighted average of "
                f"{industry_peer_count} matched peers."
            )
        elif entity_type == "stock":
            caption += (
                "; industry comparison unavailable"
                + (
                    f": {industry_error}"
                    if industry_error
                    else "."
                )
            )

        file_path = None
        figure = None
        try:
            with _PLOT_LOCK:
                file = tempfile.NamedTemporaryFile(
                    prefix="performance_",
                    suffix=".png",
                    delete=False
                )
                file_path = file.name
                file.close()

                figure, axis = plt.subplots(
                    figsize=(11, 6.5),
                    constrained_layout=True
                )
                for column in performance.columns:
                    axis.plot(
                        performance.index,
                        performance[column],
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
                    f"{ticker} vs S&P 500 — Trailing 1 Year",
                    loc="left",
                    fontsize=16,
                    fontweight="bold"
                )
                axis.set_ylabel("Total return (%)")
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
                    file_path,
                    format="png",
                    dpi=150,
                    facecolor="white"
                )
        except Exception as exc:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
            return {
                "status": "failed",
                "ticker": ticker,
                "error": f"Performance chart could not be generated: {exc}"
            }
        finally:
            if figure is not None:
                with _PLOT_LOCK:
                    plt.close(figure)

        return {
            "status": "completed",
            "ticker": ticker,
            "instrument_type": entity_type,
            "period": self.PERIOD,
            "benchmark": benchmark_ticker,
            "industry_status": industry_status,
            "industry_peer_count": industry_peer_count,
            "industry_error": industry_error,
            "caption": caption,
            "path": file_path,
            "source": "Yahoo Finance adjusted daily prices",
            "asset_return_pct": float(performance[ticker].iloc[-1]),
            "benchmark_return_pct": float(
                performance[f"S&P 500 ({benchmark_ticker})"].iloc[-1]
            ),
            "benchmark_label": f"S&P 500 ({benchmark_ticker})",
            "start_date": performance.index[0].date().isoformat(),
            "end_date": performance.index[-1].date().isoformat()
        }

    def _find_industry_peers(self, ticker, industry):
        try:
            search = yf.Search(
                f"{industry} stocks",
                max_results=self.MAX_PEER_LOOKUPS,
                news_count=0,
                lists_count=0,
                include_cb=False,
                recommended=0,
                timeout=15,
                raise_errors=True
            )
        except Exception as exc:
            return [], f"Industry peer search failed: {exc}"

        candidates = []
        seen = {ticker}
        for quote in search.quotes:
            if not isinstance(quote, dict):
                continue
            symbol = str(quote.get("symbol") or "").strip().upper()
            if (
                not symbol
                or symbol in seen
                or quote.get("quoteType") != "EQUITY"
            ):
                continue
            seen.add(symbol)
            candidates.append(symbol)
            if len(candidates) >= self.MAX_PEER_LOOKUPS:
                break

        peers = []
        for candidate in candidates:
            try:
                info = yf.Ticker(candidate).info or {}
            except Exception:
                continue
            peer_industry = str(info.get("industry") or "").strip()
            if (
                str(info.get("quoteType") or "").upper() == "EQUITY"
                and peer_industry.casefold() == industry.casefold()
            ):
                peers.append(candidate)
                if len(peers) >= self.MAX_PEERS:
                    break

        if len(peers) < self.MIN_PEERS:
            return [], (
                f"Yahoo Finance returned fewer than {self.MIN_PEERS} "
                f"verified peers in {industry}."
            )
        return peers, None

    @staticmethod
    def _close_prices(downloaded, tickers):
        if not isinstance(downloaded, pd.DataFrame) or downloaded.empty:
            return {}

        result = {}
        columns = downloaded.columns
        if isinstance(columns, pd.MultiIndex):
            for ticker in tickers:
                for column in columns:
                    if (
                        ticker.upper() in {
                            str(part).upper()
                            for part in column
                        }
                        and "CLOSE" in {
                            str(part).upper()
                            for part in column
                        }
                    ):
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
