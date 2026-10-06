class SocialSourcePolicy:

    SOURCE_AUTHORITY = {

        "sec": 100,

        "fred": 95,

        "market": 90,

        "company_ir": 85,

        "news": 75,

        "reddit": 30,

        "x": 25
    }

    DISCUSSION_SOURCES = {
        "reddit",
        "x"
    }

    FACTUAL_SOURCES = {
        "sec",
        "fred",
        "market",
        "company_ir"
    }

    def authority_score(
        self,
        source
    ):
        return (
            self.SOURCE_AUTHORITY.get(
                source,
                0
            )
        )

    def is_discussion_source(
        self,
        source
    ):
        return (
            source
            in self.DISCUSSION_SOURCES
        )

    def is_factual_source(
        self,
        source
    ):
        return (
            source
            in self.FACTUAL_SOURCES
        )