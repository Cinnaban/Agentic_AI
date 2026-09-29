import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from orchestrator.hermes import Hermes

hermes = Hermes()
message = "Compare Nvidia, Intel and AMD"

work_package = hermes.build_workflow(message)
result = hermes.executor.execute(work_package)

print("COMPANIES:", work_package.companies)
print("RESULT KEYS:", list(result.keys()) if isinstance(result, dict) else type(result).__name__)

company_results = result.get("company_results", {}) if isinstance(result, dict) else {}
for ticker in [
    "AMD",
    "NVDA",
    "INTC"
]:

    company_result = (
        company_results.get(
            ticker,
            {}
        )
    )


    print()
    print(
        "TICKER:",
        ticker
    )

    print(
        "QUANT AVAILABLE:",
        bool(
            company_result.get(
                "quant"
            )
        )
    )

    print(
        "RESEARCH AVAILABLE:",
        bool(
            company_result.get(
                "research"
            )
        )
    )


    assert company_result.get(
        "quant"
    )


    assert company_result.get(
        "research"
    )


print()
print(
    "MULTI-COMPANY RESEARCH TEST PASSED"
)
print("COMPANY RESULT TICKERS:", list(company_results.keys()))

assert {"AMD", "NVDA", "INTC"}.issubset(set(company_results.keys()))
print("MULTI-COMPANY EXECUTOR TEST PASSED")
