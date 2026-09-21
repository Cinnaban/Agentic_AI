import json
from pathlib import Path


class AgentRegistry:

    def __init__(self):
        self.config_path = (
            Path(__file__)
            .parent.parent
            / "configs"
            / "agents.json"
        )

    def load(self):

        with open(self.config_path, "r") as f:
            return json.load(f)

    def get_enabled_agents(self):

        agents = self.load()

        return {
            name: data
            for name, data in agents.items()
            if data.get("enabled")
        }