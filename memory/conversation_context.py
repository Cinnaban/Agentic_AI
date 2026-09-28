from copy import deepcopy


class ConversationContext:

    def __init__(
        self,
        history_limit=12
    ):

        self.history_limit = (
            history_limit
        )

        self._contexts = {}


    def make_key(
        self,
        source,
        channel_id=None,
        user_id=None
    ):

        source = (
            str(
                source
                or "unknown"
            )
        )

        channel_id = (
            str(
                channel_id
                or "unknown"
            )
        )

        user_id = (
            str(
                user_id
                or "unknown"
            )
        )


        return (
            source,
            channel_id,
            user_id
        )


    def _ensure(
        self,
        key
    ):

        if key not in self._contexts:

            self._contexts[
                key
            ] = {
                "active_entities":
                    [],

                "last_intent":
                    None,

                "last_request":
                    None,

                "recent_messages":
                    []
            }


        return self._contexts[
            key
        ]


    def get(
        self,
        key
    ):

        context = (
            self._ensure(
                key
            )
        )


        return deepcopy(
            context
        )


    def set_active_entities(
        self,
        key,
        entities,
        intent=None,
        request=None
    ):

        context = (
            self._ensure(
                key
            )
        )


        normalized = []

        seen = set()


        if isinstance(
            entities,
            list
        ):

            for entity in entities:

                if not isinstance(
                    entity,
                    dict
                ):

                    continue


                ticker = (
                    entity.get(
                        "ticker"
                    )
                )


                if not isinstance(
                    ticker,
                    str
                ):

                    continue


                ticker = (
                    ticker
                    .strip()
                    .upper()
                )


                if not ticker:

                    continue


                if ticker in seen:

                    continue


                seen.add(
                    ticker
                )


                normalized.append(
                    {
                        "name":
                            entity.get(
                                "name"
                            ),

                        "ticker":
                            ticker,

                        "entity_type":
                            entity.get(
                                "entity_type",
                                "company"
                            )
                    }
                )


        context[
            "active_entities"
        ] = normalized


        if intent is not None:

            context[
                "last_intent"
            ] = intent


        if request is not None:

            context[
                "last_request"
            ] = request


    def add_message(
        self,
        key,
        role,
        content
    ):

        if not isinstance(
            content,
            str
        ):

            return


        content = (
            content.strip()
        )


        if not content:

            return


        context = (
            self._ensure(
                key
            )
        )


        context[
            "recent_messages"
        ].append(
            {
                "role":
                    role,

                "content":
                    content
            }
        )


        context[
            "recent_messages"
        ] = (
            context[
                "recent_messages"
            ][
                -self.history_limit:
            ]
        )


    def clear(
        self,
        key
    ):

        self._contexts.pop(
            key,
            None
        )