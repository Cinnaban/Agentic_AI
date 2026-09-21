from security.sanitizer import SecuritySanitizer


class OutboundResponseGate:

    def __init__(self):
        self.sanitizer = SecuritySanitizer()

    def prepare(
        self,
        response
    ):

        sanitized_response = (
            self.sanitizer.sanitize(
                response
            )
        )

        return sanitized_response