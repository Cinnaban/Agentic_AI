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
        self.session = (
            requests.Session()
        )

        self.session.trust_env = (
            False
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


        companies = (
            work_package.companies
        )


        if not isinstance(
            companies,
            list
        ):

            return {
                "job_id":
                    work_package.job_id,

                "worker":
                    self.worker_name,

                "status":
                    "failed",

                "results":
                    [],

                "failed_companies":
                    [],

                "error":
                    "Invalid companies configuration"
            }


        if not companies:

            return {
                "job_id":
                    work_package.job_id,

                "worker":
                    self.worker_name,

                "status":
                    "failed",

                "results":
                    [],

                "failed_companies":
                    [],

                "error":
                    "No companies were supplied"
            }


        combined_results = []

        failed_companies = []


        for company in companies:

            if not isinstance(
                company,
                dict
            ):

                continue


            ticker = (
                company.get(
                    "ticker"
                )
            )


            if not isinstance(
                ticker,
                str
            ):

                continue


            ticker = (
                ticker
                .strip()
                .upper()
            )


            if not ticker:

                continue


            print()
            print("=" * 60)
            print(
                "GAMING PC QUANT REQUEST:",
                ticker
            )
            print("=" * 60)


            compute_request = (
                ComputeRequest(
                    job_id=(
                        work_package.job_id
                    ),

                    companies=[
                        company
                    ],

                    original_message=(
                        work_package
                        .original_message
                    ),

                    requested_tasks=(
                        requested_tasks
                    ),

                    source=(
                        work_package.source
                    )
                )
            )


            payload = (
                compute_request.to_dict()
            )


            try:

                response = self.session.post(
                    Config.GAMING_PC_COMPUTE_URL,

                    json=payload,

                    timeout=(
                        Config.GAMING_PC_TIMEOUT
                    )
                )


                response.raise_for_status()


                response_data = (
                    response.json()
                )

                if not isinstance(response_data, dict):
                    raise ValueError(
                        "Gaming PC returned an invalid response; "
                        "expected a JSON object"
                    )

                remote_results = (
                    response_data.get(
                        "results",
                        None
                    )
                )

                if not isinstance(remote_results, list):
                    response_error = response_data.get("error")
                    detail = (
                        f": {response_error}"
                        if isinstance(response_error, str)
                        and response_error.strip()
                        else ""
                    )
                    raise ValueError(
                        "Gaming PC response did not include a valid "
                        f"results list{detail}"
                    )

                if not remote_results:
                    response_error = response_data.get("error")
                    detail = (
                        f": {response_error}"
                        if isinstance(response_error, str)
                        and response_error.strip()
                        else ""
                    )
                    raise ValueError(
                        "Gaming PC returned no quant results"
                        f"{detail}"
                    )

                if any(
                    not isinstance(item, dict)
                    for item in remote_results
                ):
                    raise ValueError(
                        "Gaming PC returned malformed quant results"
                    )

                combined_results.extend(
                    remote_results
                )


                print(
                    "GAMING PC QUANT COMPLETE:",
                    ticker
                )


            except (
                requests.RequestException,
                ValueError
            ) as e:

                print(
                    "GAMING PC QUANT FAILED:",
                    ticker,
                    repr(
                        e
                    )
                )


                failed_companies.append(
                    {
                        "company":
                            company,

                        "ticker":
                            ticker,

                        "error":
                            str(
                                e
                            )
                    }
                )


        if (
            not combined_results
            and failed_companies
        ):

            return {
                "job_id":
                    work_package.job_id,

                "worker":
                    self.worker_name,

                "status":
                    "failed",

                "results":
                    [],

                "failed_companies":
                    failed_companies,

                "error":
                    (
                        "All Gaming PC "
                        "quant requests failed"
                    )
            }


        return {
            "job_id":
                work_package.job_id,

            "worker":
                self.worker_name,

            "status":
                (
                    "partial"
                    if failed_companies
                    else "completed"
                ),

            "results":
                combined_results,

            "failed_companies":
                failed_companies
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
            response = self.session.get(
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
