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