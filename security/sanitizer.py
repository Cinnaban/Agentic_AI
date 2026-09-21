import re
from typing import Any


class SecuritySanitizer:

    def sanitize_text(
        self,
        text: str
    ) -> str:

        if not isinstance(text, str):
            return text

        if not text:
            return text

        # IPv4 addresses
        text = re.sub(
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            "[REDACTED_IP]",
            text
        )

        # Windows drive paths
        # Example: D:\Agentic_AI\data.json
        text = re.sub(
            r"\b[A-Za-z]:\\\S+",
            "[REDACTED_PATH]",
            text
        )
        
        # macOS user paths
        text = re.sub(
            r"/Users/\S+",
            "[REDACTED_PATH]",
            text
        )

        # Linux home paths
        text = re.sub(
            r"/home/\S+",
            "[REDACTED_PATH]",
            text
        )

        # Windows UNC / network paths
        text = re.sub(
            r"\\\\\S+",
            "[REDACTED_NETWORK_PATH]",
            text
        )

        # Bearer tokens
        text = re.sub(
            r"\bBearer\s+\S+",
            "Bearer [REDACTED_TOKEN]",
            text,
            flags=re.IGNORECASE
        )

        # API keys
        text = re.sub(
            r"\bapi_key\s*[:=]\s*\S+",
            "api_key=[REDACTED]",
            text,
            flags=re.IGNORECASE
        )

        # Tokens
        text = re.sub(
            r"\btoken\s*[:=]\s*\S+",
            "token=[REDACTED]",
            text,
            flags=re.IGNORECASE
        )

        # Passwords
        text = re.sub(
            r"\bpassword\s*[:=]\s*\S+",
            "password=[REDACTED]",
            text,
            flags=re.IGNORECASE
        )

        # Secrets
        text = re.sub(
            r"\bsecret\s*[:=]\s*\S+",
            "secret=[REDACTED]",
            text,
            flags=re.IGNORECASE
        )

        return text
    
    def sanitize(
        self,
        value: Any
    ) -> Any:

        if isinstance(value, str):
            return self.sanitize_text(value)

        if isinstance(value, dict):
            return {
                key: self.sanitize(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                self.sanitize(item)
                for item in value
            ]

        if isinstance(value, tuple):
            return tuple(
                self.sanitize(item)
                for item in value
            )

        return value