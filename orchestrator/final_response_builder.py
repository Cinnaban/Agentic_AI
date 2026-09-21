class FinalResponseBuilder:

    def build(
        self,
        aggregated_results
    ):

        quality_review = (
            aggregated_results[
                "quality_review"
            ]
        )

        return {
            "approved": quality_review.get(
                "approved",
                False
            ),
            "confidence": quality_review.get(
                "confidence",
                0
            ),
            "results": aggregated_results
        }