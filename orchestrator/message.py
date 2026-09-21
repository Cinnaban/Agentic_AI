from dataclasses import dataclass


@dataclass
class UserMessage:

    source: str

    user_id: str

    content: str