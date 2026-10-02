class ComparisonRequestPlanner:

    def plan(
        self,
        message
    ):

        if not isinstance(
            message,
            str
        ):

            message = ""


        normalized = (
            message
            .strip()
            .lower()
        )


        dimensions = []

        needs_quant = False

        needs_research = True

        needs_risk = False

        needs_live = False


        dimension_rules = {
            "profitability": [
                "profitability",
                "profitable",
                "profit",
                "margin"
            ],

            "financial_strength": [
                "balance sheet",
                "financial strength",
                "cash",
                "debt"
            ],

            "valuation": [
                "valuation",
                "value",
                "cheapest",
                "expensive",
                "p/e"
            ],

            "growth": [
                "growth",
                "growing",
                "revenue growth",
                "earnings growth"
            ],

            "risk": [
                "risk",
                "risky",
                "safest",
                "volatility"
            ],

            "momentum": [
                "momentum",
                "performance",
                "performing"
            ]
        }


        for dimension, keywords in (
            dimension_rules.items()
        ):

            if any(
                keyword in normalized
                for keyword in keywords
            ):

                dimensions.append(
                    dimension
                )


        quantitative_dimensions = {
            "profitability",
            "financial_strength",
            "valuation",
            "growth",
            "risk",
            "momentum"
        }


        if any(
            dimension
            in quantitative_dimensions

            for dimension
            in dimensions
        ):

            needs_quant = True


        if "risk" in dimensions:

            needs_risk = True


        freshness_terms = (
            "current",
            "currently",
            "latest",
            "recent",
            "today",
            "now",
            "this week"
        )


        if any(
            term in normalized
            for term in freshness_terms
        ):

            needs_live = True


        if not dimensions:

            dimensions = [
                "overview",
                "business_model",
                "competitive_position",
                "growth",
                "profitability",
                "financial_strength",
                "valuation",
                "risk"
            ]

            needs_quant = True

            needs_risk = True


        return {
            "dimensions":
                dimensions,

            "needs_quant":
                needs_quant,

            "needs_research":
                needs_research,

            "needs_risk":
                needs_risk,

            "needs_live":
                needs_live
        }