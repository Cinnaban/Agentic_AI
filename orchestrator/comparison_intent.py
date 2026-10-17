import re


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


        if re.search(
            r"\bvs\b\.?|\bversus\b|\bagainst\b|\bor\b",
            normalized
        ) and any(
            isinstance(c, dict) and c.get("ticker")
            for c in companies
        ):
            return True

        return any(
            keyword in normalized
            for keyword in self.KEYWORDS
        )