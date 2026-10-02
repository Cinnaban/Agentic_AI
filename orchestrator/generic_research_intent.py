class GenericResearchIntent:

    RESEARCH_PHRASES = (
        "what is",
        "what does",
        "what do they do",
        "who is",
        "who are",
        "company",
        "organization",
        "competitor",
        "competition",
        "market",
        "industry",
        "potential",
        "growth",
        "large",
        "small",
        "size",
        "reputation",
        "customers",
        "products",
        "services"
    )


    def requires_research(
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


        if not normalized:

            return False


        return any(
            phrase in normalized
            for phrase in self.RESEARCH_PHRASES
        )
