
from agents.ollama_client import OllamaClient
from configs.config import Config
import json

class ResearchAssignmentAgent:

    def __init__(self):

        self.ollama = OllamaClient()

    def analyze(
        self,
        company_data,
        user_message
    ):

        prompt = f"""
You are the Hermes orchestration planner.

Determine which analysis agents
should be activated.

Available Agents:

- research
- sentiment
- quant
- risk

Return ONLY valid JSON using exactly this schema:

{{
    "agents": [
        "research",
        "sentiment",
        "quant",
        "risk"
    ]
}}

Only include agents that are actually required.

Message:

{user_message}

Companies:

{company_data}
"""

        response = self.ollama.generate(
            prompt,
            model=Config.RESEARCH_ASSIGNMENT_MODEL
        )

        model_response = response.get(
            "response",
            ""
        )

        if not model_response.strip():
            return {}

        try:
            parsed = json.loads(
                model_response
            )
        except json.JSONDecodeError:
            return {}
        
        agents = parsed.get(
            "agents",
            []
        )

        return {
            "research": "research" in agents,
            "sentiment": "sentiment" in agents,
            "quant": "quant" in agents,
            "risk": "risk" in agents
        }