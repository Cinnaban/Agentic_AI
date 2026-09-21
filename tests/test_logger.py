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


from utils.logger import (
    hermes_logger
)


hermes_logger.info(
    "Hermes logger test"
)

hermes_logger.warning(
    "Hermes warning test"
)

hermes_logger.error(
    "Hermes error test"
)


print(
    "Logger test completed."
)