import sys
import traceback
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes

hermes = Hermes()
message = "Compare Nvidia, Intel and AMD"

print("=" * 70)
print("COMPARISON FIRST-TURN TRACE")
print("=" * 70)

try:
    detection = (
    hermes.company_agent
    .analyze(
        message
    )
)
    print("DETECTION:", detection)

    workflow = hermes.build_workflow(message)
    print("WORKFLOW TYPE:", type(workflow).__name__)
    print("WORKFLOW:", workflow)

    if hasattr(workflow, "job_id"):
        print("COMPANIES:", workflow.companies)
        print("REQUIRED AGENTS:", workflow.required_agents)
        print("COMPARISON INTENT:", hermes.comparison_intent.is_comparison(message, workflow.companies))

    result = hermes.process_request(
        message=message,
        source="comparison_trace",
        channel_id="comparison_chat",
        user_id="comparison_user",
    )

    print("RESULT:", result)
    print("STATUS:", result.get("status") if isinstance(result, dict) else None)
    print("ISSUES:", result.get("issues") if isinstance(result, dict) else None)
    print("HAS RESPONSE:", bool(result.get("response")) if isinstance(result, dict) else False)

except Exception as exc:
    print("EXCEPTION TYPE:", type(exc).__name__)
    print("EXCEPTION:", repr(exc))
    traceback.print_exc()
