import sys
from pathlib import Path

ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

if str(ROOT_DIR) not in sys.path:
    sys.path.append(
        str(ROOT_DIR)
    )


from orchestrator.hermes import Hermes
from workers.agent_executor import AgentExecutor
from orchestrator.quality_context_builder import (
    QualityContextBuilder
)
from agents.qwen_manager import (
    QwenManager
)

hermes = Hermes()

executor = AgentExecutor()

builder = QualityContextBuilder()


work_package = hermes.build_workflow(
    "Analyze Nvidia"
)

work_package.required_agents[
    "quant"
] = True

work_package.required_agents[
    "risk"
] = True


results = executor.execute(
    work_package
)


context = builder.build(
    results
)
quality_manager = QwenManager()
quality_review = (
    quality_manager.review(
        context
    )
)
print()
print("=" * 60)
print("QUALITY CONTEXT TEST")
print("=" * 60)

print(
    "Agents:",
    context.get(
        "agents_present"
    )
)

print(
    "Failed agents:",
    context.get(
        "failed_agents"
    )
)

print(
    "Quant summary:",
    context.get(
        "quant_summary"
    )
)

print(
    "Signal reconciliation:",
    context.get(
        "signal_reconciliation"
    )
)

print(
    "Risk:",
    context.get(
        "risk"
    )
)

print("=" * 60)