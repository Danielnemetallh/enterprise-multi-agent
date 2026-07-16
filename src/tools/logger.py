"""
Central logging configuration for the multi-agent system.
"""

import logging
import sys


def setup_logging(level=logging.WARNING, log_file: str | None = None, quiet: bool = False):
    """
    Configure logging once for the application.

    - level: default WARNING to keep console output quiet during workflow runs
    - log_file: optional path to a log file
    - quiet: when True, suppress console handlers entirely
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    if logger.handlers:
        logger.handlers.clear()

    if not quiet:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(console)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        ))
        logger.addHandler(file_handler)

    for noisy in (
        "httpx",
        "openai",
        "httpcore",
        "langchain",
        "langgraph",
        "urllib3",
    ):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    return logger


if __name__ == "__main__":
    setup_logging(level=logging.INFO)
    logger = logging.getLogger("test")
    logger.info("Logger is working")
    logger.warning("This is a warning")
    logger.error("This is an error")
