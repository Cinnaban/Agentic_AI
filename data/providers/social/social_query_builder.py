class SocialQueryBuilder:

    def build(
        self,
        ticker,
        company_name=None
    ):
        
        ticker = str(
            ticker
        ).strip()
        
        queries = [
            ticker,
            f"${ticker}",
            f"{ticker} stock"
        ]

        if company_name:
            queries.extend([
                company_name,
                f"{company_name} stock"
            ])

        return list(
            dict.fromkeys(queries)
        )
