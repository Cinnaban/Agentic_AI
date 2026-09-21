# agents/base_response.py

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class AgentResponse:
    success: bool
    agent_name: str
    data: Dict
    errors: List[str]