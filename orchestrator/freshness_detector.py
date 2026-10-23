class FreshnessDetector:

    TERMS = {
        "current",
        "currently",
        "today",
        "latest",
        "recent",
        "recently",
        "now",
        "this week",
        "this month"
    }


    def requires_live_data(
        self,
        message
    ):

        if not isinstance(
            message,
            str
        ):
            return False

        normalized = (
            message
            .strip()
            .lower()
        )

        return any(
            term in normalized
            for term in self.TERMS
        )


    FINANCE_PATTERN = (
        r"\b(stocks?|shares?|share price|equity|equities|etfs?|funds?|"
        r"index|indices|s&p|sp500|nasdaq|dow|russell|ticker|earnings|"
        r"dividends?|ipo|market|markets|trading|trader|invest\w*|"
        r"portfolio|bonds?|treasur\w+|yields?|interest rates?|inflation|"
        r"fed|fomc|gdp|forex|currency|crypto\w*|bitcoin|ethereum|"
        r"commodit\w+|oil prices?|gold prices?|price target|valuation|"
        r"bull|bear|rally|selloff|sell-off|volatility|vix|economy|"
        r"economic|financ\w+|quote|premarket|after-hours)\b|\$[a-z]{1,5}\b"
    )


    def is_financial_query(
        self,
        message
    ):

        import re

        if not isinstance(
            message,
            str
        ):
            return False

        return bool(
            re.search(
                self.FINANCE_PATTERN,
                message,
                re.IGNORECASE
            )
        )
