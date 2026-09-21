class ResultAggregator:

    def aggregate(
        self,
        execution_results,
        quality_review
    ):

        return {
            "research": execution_results.get(
                "research"
            ),
            "sentiment": execution_results.get(
                "sentiment"
            ),
            "risk": execution_results.get(
                "risk"
            ),
            "quant": execution_results.get(
                "quant"
            ),
            "quality_review": quality_review
        }