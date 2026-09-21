import sys

from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agents.company_detection_agent import (CompanyDetectionAgent)
from agents.research_assignment_agent import (ResearchAssignmentAgent)
from agents.qwen_manager import (QwenManager)
from agents.general_response_agent import (GeneralResponseAgent)
from job_queue.job_factory import JobFactory
from workers.agent_executor import AgentExecutor
from orchestrator.result_aggregator import (ResultAggregator)
from orchestrator.final_response_builder import (FinalResponseBuilder)
from orchestrator.quality_context_builder import(QualityContextBuilder)
from security.outbound_gate import (OutboundResponseGate)
from shared_storage.storage_manager import (StorageManager)
from memory.workflow_state import (
    WorkflowState,
    WorkflowStatus
)


class Hermes:

    def __init__(self):
        self.company_agent = (CompanyDetectionAgent())
        self.assignment_agent = (ResearchAssignmentAgent())
        self.general_response_agent = (GeneralResponseAgent())
        self.job_factory = JobFactory()
        self.executor = AgentExecutor()
        self.aggregator = ResultAggregator()
        self.quality_manager = QwenManager()
        self.response_builder = (FinalResponseBuilder())
        self.outbound_gate = (OutboundResponseGate())
        self.workflow_state = (WorkflowState())
        self.storage_manager = (StorageManager())
        self.quality_context_builder = (QualityContextBuilder())
        self.quality_manager = QwenManager()

    def build_workflow(
        self,
        message
    ):

        company_result = (
            self.company_agent.analyze(
                message
            )
        )

        if not company_result.get(
            "is_company_request",
            False
        ):

            return {
                "route": "local_agents"
            }

        assignment_result = (
            self.assignment_agent.analyze(
                company_result["companies"],
                message
            )
        )

        work_package = (
            self.job_factory
            .create_work_package(
                companies=company_result[
                    "companies"
                ],
                required_agents=assignment_result,
                original_message=message
            )
        )

        return work_package

    def process_request(
        self,
        message,
        source="unknown"
    ):

        work_package = None

        try:

            work_package = (
                self.build_workflow(
                    message
                )
            )

            if not hasattr(
                work_package,
                "job_id"
            ):

                general_result = (
                    self.general_response_agent.analyze(
                        message
                    )
                )

                safe_response = (
                    self.outbound_gate.prepare(
                        general_result
                    )
                )

                return safe_response

            work_package.source = source

            self.storage_manager.create_job_record(
                job_id=work_package.job_id,
                data={
                    "message":
                        work_package.original_message,

                    "source":
                        work_package.source,

                    "companies":
                        work_package.companies,

                    "required_agents":
                        work_package.required_agents
                }
            )

            self.workflow_state.register_job(
                job_id=work_package.job_id,
                original_message=(
                    work_package.original_message
                )
            )

            self.workflow_state.update_status(
                work_package.job_id,
                WorkflowStatus.PLANNING
            )
            
            self.storage_manager.move_job(
                job_id=work_package.job_id,
                from_status="incoming",
                to_status="processing"
            )
            
            self.workflow_state.update_status(
                work_package.job_id,
                WorkflowStatus.EXECUTING
            )

            execution_results = (
                self.executor.execute(
                    work_package
                )
            )
            if not execution_results:
                raise RuntimeError(
                    "Agent execution returned no results"
                )

            if execution_results.get(
                "status"
            ) == "failed":

                raise RuntimeError(
                    execution_results.get(
                        "error",
                        "Agent execution failed"
                    )
                )
            self.workflow_state.update_status(
                work_package.job_id,
                WorkflowStatus.QUALITY_REVIEW
            )

            quality_context = (
                self.quality_context_builder.build(
                    execution_results
                )
            )

            quality_review = (
                self.quality_manager.review(
                    quality_context
                )
            )

            quality_approved = bool(
                quality_review.get(
                    "approved",
                    False
                )
            )
        
            aggregated_results = (
                self.aggregator.aggregate(
                    execution_results,
                    quality_review
                )
            )

            final_response = (
                self.response_builder.build(
                    aggregated_results
                )
            )
            response_approved = bool(
                final_response.get(
                    "approved",
                    False
                )
            )

            if response_approved != quality_approved:

                raise RuntimeError(
                    "Quality review and final response "
                    "approval states do not match"
                )
                       
            self.storage_manager.update_job_record(
                job_id=work_package.job_id,
                status="processing",
                updates={
                    "quality_review":
                        quality_review,

                    "final_status":
                        (
                            "completed"
                            if quality_approved
                            else "quality_rejected"
                        )
                }
            )
            
            self.workflow_state.update_status(
                    work_package.job_id,
                    WorkflowStatus.SANITIZING
                )
            safe_response = (
                    self.outbound_gate.prepare(
                    final_response
                )
            )
            
            if quality_approved:
                completed_path = (
                    self.storage_manager.move_job(
                        job_id=work_package.job_id,
                        from_status="processing",
                        to_status="completed"
                    )
                )
                if (
                    completed_path is None
                    or not completed_path.exists()
                ):
                    raise RuntimeError(
                        "Completed job record was not persisted"
                    )
                    
                self.workflow_state.update_status(
                    work_package.job_id,
                    WorkflowStatus.COMPLETED
                )
                

            else:
                failed_path = (
                    self.storage_manager.fail_job(
                        job_id=work_package.job_id,
                        updates={
                            "final_status":
                                "quality_rejected",

                            "quality_review":
                                quality_review
                        }
                    )
                )
                if (
                    failed_path is None
                    or not failed_path.exists()
                ):
                    raise RuntimeError(
                        "Quality-rejected job record "
                        "was not persisted"
                    )
                self.workflow_state.update_status(
                    work_package.job_id,
                    WorkflowStatus.QUALITY_REJECTED
                )
            safe_response["job_id"] = (
                work_package.job_id
            )

            safe_response["status"] = (
                self.workflow_state
                .get_job(
                    work_package.job_id
                )["status"]
            )
            return safe_response

        except Exception as e:
            if (
                work_package is not None
                and hasattr(
                    work_package,
                    "job_id"
                )
            ):
                self.workflow_state.set_error(
                    work_package.job_id,
                    e
                )
                self.storage_manager.fail_job(
                    job_id=work_package.job_id,
                    updates={
                        "final_status": "failed"
                    }
                )
                job_id = (
                    work_package.job_id
                )

            else:
                job_id = None

            error_response = {
                "approved": False,
                "confidence": 0,
                "status": "failed",
                "job_id": job_id,
                "issues": [
                    "The request could not be completed."
                ]
            }
            return self.outbound_gate.prepare(
                error_response
            )