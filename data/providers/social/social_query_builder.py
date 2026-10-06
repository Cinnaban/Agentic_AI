# social_query_builder.py

class SocialQueryBuilder:

    def build(
        self,
        ticker,
        company_name=None
    ):
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
