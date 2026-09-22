class MessageRouter:

    SOURCE_PRIORITY = {
        "telegram": 0,
        "discord": 10
    }


    def __init__(
        self,
        hermes
    ):

        self.hermes = hermes


    def get_priority(
        self,
        source
    ):

        return self.SOURCE_PRIORITY.get(
            str(source).lower(),
            100
        )


    def normalize_message(
        self,
        source,
        text,
        user_id=None,
        channel_id=None,
        message_id=None
    ):

        return {
            "source":
                str(
                    source
                ).strip().lower(),

            "text":
                str(
                    text
                ).strip(),

            "user_id":
                user_id,

            "channel_id":
                channel_id,

            "message_id":
                message_id
        }


    def validate_message(
        self,
        message
    ):

        if not isinstance(
            message,
            dict
        ):

            return False

        source = message.get(
            "source"
        )

        text = message.get(
            "text"
        )

        if source not in {
            "telegram",
            "discord"
        }:

            return False

        if not isinstance(
            text,
            str
        ):

            return False

        if not text.strip():

            return False

        return True
    
    def route(
        self,
        message
    ):

        if not self.validate_message(
            message
        ):

            return {
                "status":
                    "failed",

                "error":
                    "Invalid message"
            }

        if self.hermes is None:

            return {
                "status":
                    "failed",

                "error":
                    "Hermes is unavailable"
            }

        text = message.get(
            "text"
        )

        source = message.get(
            "source"
        )

        try:

            result = (
                self.hermes.process_request(
                    message=text,
                    source=source
                )
            )

        except Exception as exc:

            return {
                "status":
                    "failed",

                "error":
                    str(exc)
            }

        if not isinstance(
            result,
            dict
        ):

            return {
                "status":
                    "failed",

                "error":
                    "Hermes returned an invalid result"
            }

        result[
            "source"
        ] = source

        result[
            "message_id"
        ] = message.get(
            "message_id"
        )

        result[
            "channel_id"
        ] = message.get(
            "channel_id"
        )

        result[
            "user_id"
        ] = message.get(
            "user_id"
        )

        return result
