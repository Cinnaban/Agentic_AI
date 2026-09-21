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


hermes = Hermes()

executor = AgentExecutor()

def print_structure(
    value,
    indent=0,
    max_depth=4
):

    prefix = (
        " " * indent
    )

    if indent > max_depth * 2:
        return

    if isinstance(
        value,
        dict
    ):

        for key, item in value.items():

            print(
                f"{prefix}{key}: "
                f"{type(item).__name__}"
            )

            if isinstance(
                item,
                (
                    dict,
                    list
                )
            ):

                print_structure(
                    item,
                    indent + 2,
                    max_depth
                )

    elif isinstance(
        value,
        list
    ):

        print(
            f"{prefix}"
            f"[list: {len(value)} items]"
        )

        if value:

            print_structure(
                value[0],
                indent + 2,
                max_depth
            )

work_package = hermes.build_workflow(
    "Analyze Nvidia"
)


execution_results = executor.execute(
    work_package
)


quant_result = execution_results.get(
    "quant"
)
if quant_result is None:

    print(
        "Quant result was not returned."
    )

    print(
        "Execution result categories:",
        list(
            execution_results.keys()
        )
    )

    sys.exit(1)

print()
print("=" * 60)
print("QUANT PAYLOAD INSPECTION")
print("=" * 60)


print(
    "Type:",
    type(quant_result)
)


if isinstance(
    quant_result,
    dict
):

    print(
        "Top-level keys:"
    )

    for key in quant_result.keys():

        print(
            " -",
            key
        )


print("=" * 60)
print()
print("QUANT STRUCTURE:")
print()

print_structure(
    quant_result
)