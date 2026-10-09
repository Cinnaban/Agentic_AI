import re


class PortfolioRequestParser:

    HOLDING_PATTERN = re.compile(
        r"^\s*"
        r"(?P<ticker>[A-Za-z][A-Za-z0-9.\-]{0,9})"
        r"\s+"
        r"(?P<weight>\d+(?:\.\d+)?)"
        r"\s*%"
        r"\s*$"
    )

    PORTFOLIO_TERMS = {
        "portfolio",
        "allocation",
        "holdings",
        "positions",
        "weight",
        "weighting",
        "reverse engineer",
        "reverse-engineer"
    }

    def is_portfolio_request(
        self,
        message
    ):
        normalized = str(
            message
            or ""
        ).lower()

        return any(
            term in normalized
            for term in self.PORTFOLIO_TERMS
        )

    def parse(
        self,
        message
    ):
        holdings = []
        seen = set()

        for raw_line in str(
            message
            or ""
        ).splitlines():

            match = (
                self.HOLDING_PATTERN
                .match(raw_line)
            )

            if not match:
                continue

            ticker = (
                match.group("ticker")
                .strip()
                .upper()
            )

            if ticker in seen:
                continue

            seen.add(ticker)

            holdings.append(
                {
                    "ticker": ticker,
                    "weight": float(
                        match.group(
                            "weight"
                        )
                    )
                }
            )

        return {
            "is_portfolio_request":
                self.is_portfolio_request(
                    message
                ),
            "holdings":
                holdings
        }