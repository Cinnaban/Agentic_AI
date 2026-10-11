import os
import tempfile
from pathlib import Path


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

    @staticmethod
    def get_attachments(result):
        if not isinstance(result, dict):
            return []
        attachments = result.get("attachments", [])
        if not isinstance(attachments, list):
            return []
        return [
            attachment
            for attachment in attachments
            if (
                isinstance(attachment, dict)
                and isinstance(attachment.get("path"), str)
                and attachment.get("path")
            )
        ]

    @staticmethod
    def cleanup_attachments(result):
        temp_directory = Path(tempfile.gettempdir()).resolve()
        for attachment in ResponseFormatter.get_attachments(result):
            path = Path(attachment["path"])
            try:
                resolved_path = path.resolve()
                if (
                    resolved_path.parent == temp_directory
                    and resolved_path.name.startswith("performance_")
                    and resolved_path.suffix.lower() == ".png"
                ):
                    os.unlink(resolved_path)
            except FileNotFoundError:
                continue