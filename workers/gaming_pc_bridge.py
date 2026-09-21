import sys
import requests 

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from configs.config import Config
from job_queue.compute_request import ComputeRequest

class GamingPCBridge:

    def __init__(self):
        self.worker_name = (
            Config.GAMING_PC_WORKER_NAME
        )

    def submit_job(
        self,
        work_package
    ):

        requested_tasks = [
            agent_name
            for agent_name, enabled
            in work_package.required_agents.items()
            if enabled
        ]

        compute_request = ComputeRequest(
            job_id=work_package.job_id,
            companies=work_package.companies,
            original_message=work_package.original_message,
            requested_tasks=requested_tasks,
            source=work_package.source
        )

        payload = compute_request.to_dict()

        try:
            response = requests.post(
                Config.GAMING_PC_COMPUTE_URL,
                json=payload,
                timeout=Config.GAMING_PC_TIMEOUT
            )
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            return {
                "job_id": work_package.job_id,
                "worker": self.worker_name,
                "status": "failed",
                "error": str(e)
            }

    def get_results(
        self,
        job_id
    ):
        return {
            "job_id": job_id,
            "worker": self.worker_name,
            "status": "pending"
        }
    def health_check(self):
        try:
            response = requests.get(
                Config.GAMING_PC_HEALTH_URL,
                timeout=10
            )

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            return {
                "status": "offline",
                "worker": self.worker_name,
                "error": str(e)
            }
