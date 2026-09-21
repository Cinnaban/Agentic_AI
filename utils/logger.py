import logging
from pathlib import Path

from configs.config import Config


class HermesLogger:

    def __init__(self):

        log_directory = Path(
            Config.LOG_DIRECTORY
        )

        log_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        log_file = (
            log_directory
            / "hermes.log"
        )

        self.logger = logging.getLogger(
            "Hermes"
        )

        self.logger.setLevel(
            logging.INFO
        )

        if not self.logger.handlers:

            formatter = logging.Formatter(
                "%(asctime)s | "
                "%(levelname)s | "
                "%(name)s | "
                "%(message)s"
            )

            file_handler = logging.FileHandler(
                log_file
            )

            file_handler.setFormatter(
                formatter
            )

            self.logger.addHandler(
                file_handler
            )

    def info(
        self,
        message
    ):
        self.logger.info(message)

    def warning(
        self,
        message
    ):
        self.logger.warning(message)

    def error(
        self,
        message
    ):
        self.logger.error(message)


hermes_logger = HermesLogger()