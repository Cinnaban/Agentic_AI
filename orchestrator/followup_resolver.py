class FollowUpResolver:

    FOLLOWUP_PHRASES = (
        "which",
        "which one",
        "which company",
        "what about",
        "how about",
        "of those",
        "among them",
        "between them",
        "their",
        "them"
    )


    def resolve(
        self,
        message,
        context
    ):

        if not isinstance(
            message,
            str
        ):

            return None


        if not isinstance(
            context,
            dict
        ):

            return None


        active_entities = (
            context.get(
                "active_entities",
                []
            )
        )


        if not active_entities:

            return None


        last_intent = (
            context.get(
                "last_intent"
            )
        )


        if last_intent not in {
            "company_comparison",
            "company_analysis"
        }:

            return None


        normalized = (
            message
            .strip()
            .lower()
        )


        is_followup = any(
            phrase in normalized
            for phrase
            in self.FOLLOWUP_PHRASES
        )


        if not is_followup:

            return None


        return {
            "is_followup":
                True,

            "intent":
                last_intent,

            "entities":
                active_entities
        }
