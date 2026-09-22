class ResponseFormatter:

    def format(
        self,
        result
    ):

        if not isinstance(
            result,
            dict
        ):

            return (
                "The request could not be "
                "processed."
            )

        status = result.get(
            "status"
        )

        if status == "failed":

            return (
                result.get(
                    "error"
                )
                or
                "The request failed."
            )


        response = result.get(
            "response"
        )

        if isinstance(
            response,
            str
        ) and response.strip():

            return response.strip()


        final_response = result.get(
            "final_response"
        )

        if isinstance(
            final_response,
            str
        ) and final_response.strip():

            return final_response.strip()


        if status == "completed":

            return (
                "Analysis completed successfully."
            )


        return (
            "The request finished without "
            "a response message."
        )
        
    def split(
        self,
        text,
        max_length=3500
    ):

        if not isinstance(
            text,
            str
        ):

            return []

        text = text.strip()

        if not text:

            return []

        return [
            text[
                index:
                index + max_length
            ]

            for index in range(
                0,
                len(text),
                max_length
            )
        ]