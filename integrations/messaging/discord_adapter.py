class DiscordAdapter:

    SOURCE = "discord"

    def __init__(
        self,
        router
    ):
        self.router = router

    def normalize(
        self,
        text,
        user_id=None,
        channel_id=None,
        message_id=None
    ):
        return (
            self.router.normalize_message(
                source=self.SOURCE,
                text=text,
                user_id=user_id,
                channel_id=channel_id,
                message_id=message_id
            )
        )

    def validate(
        self,
        message
    ):
        return (
            self.router.validate_message(
                message
            )
        )

    def get_priority(
        self
    ):
        return (
            self.router.get_priority(
                self.SOURCE
            )
        )
        
    def route(
        self,
        message
    ):

        return (
            self.router.route(
                message
            )
        )