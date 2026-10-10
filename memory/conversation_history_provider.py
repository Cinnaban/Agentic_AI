from memory.conversation_context import (
    ConversationContext
)


class ConversationHistoryProvider:

    def __init__(
        self,
        conversation_context=None
    ):
        self.conversation_context = (
            conversation_context
            or ConversationContext()
        )

    def get_context(
        self,
        source,
        channel_id=None,
        chat_id=None,
        user_id=None,
        limit=50
    ):
        key = (
            self.conversation_context
            .make_key(
                source=source,
                channel_id=channel_id,
                user_id=user_id
            )
        )

        context = (
            self.conversation_context
            .get(
                key
            )
        )

        recent_messages = (
            context.get(
                "recent_messages",
                []
            )
        )

        recent_portfolios = []

        recent_analyses = []

        recent_watchlists = []

        for message in recent_messages:

            if not isinstance(
                message,
                dict
            ):
                continue

            content = str(
                message.get(
                    "content",
                    ""
                )
            )

            if "%" in content:
                recent_portfolios.append(
                    content
                )

            if (
                "analysis"
                in content.lower()
            ):
                recent_analyses.append(
                    content
                )

            if (
                "watchlist"
                in content.lower()
            ):
                recent_watchlists.append(
                    content
                )

        return {
            "recent_messages":
                recent_messages[
                    -limit:
                ],

            "recent_portfolios":
                recent_portfolios,

            "recent_analyses":
                recent_analyses,

            "recent_watchlists":
                recent_watchlists
        }