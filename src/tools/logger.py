"""
Zentrale Logger-Konfiguration für das Multi-Agent-System.
=========================================================
Ermöglicht einheitliches Logging in allen Modulen.
"""

import logging
import sys


def setup_logging(level=logging.INFO, log_file: str | None = None):
    """
    Richtet das Logging einmalig ein.

    - level: logging.INFO (Standard), logging.DEBUG, logging.WARNING, etc.
    - log_file: Optionaler Pfad zu einer Log-Datei
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # Verhindert doppelte Handler bei mehrmaligem Aufruf
    if logger.handlers:
        return logger

    # Konsolen-Handler (immer)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(console)

    # Datei-Handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        ))
        logger.addHandler(file_handler)

    return logger


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger("test")
    logger.info("Logger funktioniert!")
    logger.warning("Das ist eine Warnung.")
    logger.error("Das ist ein Fehler.")
