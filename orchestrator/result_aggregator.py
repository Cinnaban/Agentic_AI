class ResultAggregator:

    def aggregate(
        self,
        execution_results,
        quality_review
    ):

        return {
            "research":
                execution_results.get(
                    "research"
                ),

            "sentiment":
                execution_results.get(
                    "sentiment"
                ),

            "risk":
                execution_results.get(
                    "risk"
                ),

            "quant":
                execution_results.get(
                    "quant"
                ),

            "signal_reconciliation":
                execution_results.get(
                    "signal_reconciliation"
                ),

            "challenger":
                execution_results.get(
                    "challenger"
                ),

            "quality_review":
                quality_review
        }