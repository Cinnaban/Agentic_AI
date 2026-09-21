import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes
from workers.agent_executor import AgentExecutor
from orchestrator.result_aggregator import ResultAggregator
from agents.qwen_manager import QwenManager
from orchestrator.final_response_builder import FinalResponseBuilder
from security.outbound_gate import OutboundResponseGate
from memory.workflow_state import (
    WorkflowState,
    WorkflowStatus
)

hermes = Hermes()
executor = AgentExecutor()
aggregator = ResultAggregator()
quality_manager = QwenManager()
response_builder = FinalResponseBuilder()
outbound_gate = OutboundResponseGate()
workflow_state = WorkflowState()

message = "Analyze Nvidia"

# Step 1 
print()
print("=" * 60)
print("STEP 1 - USER MESSAGE")
print("=" * 60)
print(message)

work_package = hermes.build_workflow(
    message
)
workflow_state.register_job(
    job_id=work_package.job_id,
    original_message=work_package.original_message
)

workflow_state.update_status(
    work_package.job_id,
    WorkflowStatus.PLANNING
)

# Step 2
print()
print("=" * 60)
print("STEP 2 - WORK PACKAGE CREATED")
print("=" * 60)
print(work_package)

# Step 3
print()
print("=" * 60)
print("STEP 3 - EXECUTING AGENTS")
print("=" * 60)
workflow_state.update_status(
    work_package.job_id,
    WorkflowStatus.EXECUTING
)
execution_results = executor.execute(
    work_package
)
print("Agent execution completed.")
print(
    "Result categories:",
    list(execution_results.keys())
)

# Step 4
print()
print("=" * 60)
print("STEP 4 - QUALITY REVIEW")
print("=" * 60)
workflow_state.update_status(
    work_package.job_id,
    WorkflowStatus.QUALITY_REVIEW
)
quality_review = quality_manager.review(
    execution_results
)
quality_rejected = False

if not quality_review.get(
    "approved",
    False
):
    quality_rejected = True

    workflow_state.update_status(
        work_package.job_id,
        WorkflowStatus.QUALITY_REJECTED
    )
print("Quality review:")
print(quality_review)

# Step 5
print()
print("=" * 60)
print("STEP 5 - AGGREGATING RESULTS")
print("=" * 60)
aggregated_results = aggregator.aggregate(
    execution_results,
    quality_review
)
print(
    "Aggregated categories:",
    list(aggregated_results.keys())
)

# Step 6
print()
print("=" * 60)
print("STEP 6 - BUILDING FINAL RESPONSE")
print("=" * 60)
final_response = response_builder.build(
    aggregated_results
)
print(
    "Approved:",
    final_response.get(
        "approved"
    )
)

print(
    "Confidence:",
    final_response.get(
        "confidence"
    )
)

# Step 7 SECURITY REVIEW
print()
print("=" * 60)
print("STEP 7 - SECURITY SANITIZATION")
print("=" * 60)

workflow_state.update_status(
    work_package.job_id,
    WorkflowStatus.SANITIZING
)

safe_response = outbound_gate.prepare(
    final_response
)

print("Outbound security processing completed.")

if quality_rejected:

    workflow_state.update_status(
        work_package.job_id,
        WorkflowStatus.QUALITY_REJECTED
    )

else:

    workflow_state.update_status(
        work_package.job_id,
        WorkflowStatus.COMPLETED
    )

# Step 8 
print()
print("=" * 60)
print("FINAL SAFE RESPONSE")
print("=" * 60)
print(
    "Approved:",
    safe_response.get(
        "approved",
        False
    )
)
print(
    "Confidence:",
    safe_response.get(
        "confidence",
        0
    )
)
quality_issues = (
    safe_response
    .get("results", {})
    .get("quality_review", {})
    .get("issues", [])
)

print(
    "Quality Issues:",
    quality_issues
)
print("=" * 60)
print("PIPELINE COMPLETED")
print("=" * 60)
print()
print("=" * 60)
print("FINAL WORKFLOW STATE")
print("=" * 60)

job_state = workflow_state.get_job(
    work_package.job_id
)

print(job_state)

print("=" * 60)
