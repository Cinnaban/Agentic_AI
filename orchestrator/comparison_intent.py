class ComparisonIntent:

    KEYWORDS = (
        "compare",
        "comparison",
        "versus",
        " vs ",
        "which is better",
        "which has",
        "between"
    )


    def is_comparison(
        self,
        message,
        companies
    ):

        if not isinstance(
            message,
            str
        ):

            return False


        if not isinstance(
            companies,
            list
        ):

            return False


        if len(
            companies
        ) < 2:

            return False


        normalized = (
            message
            .strip()
            .lower()
        )


        return any(
            keyword in normalized
            for keyword in self.KEYWORDS
        )