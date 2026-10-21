import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


class ConsoleFilter(logging.Filter):
    """Show crawler events and important errors, not routine library logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "crawler" or record.name.startswith("crawler."):
            return True

        return record.levelno >= logging.ERROR


def setup_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper())

    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Clean, colored terminal output.
    console = RichHandler(
        show_time=True,
        show_level=True,
        show_path=False,
        rich_tracebacks=True,
        markup=False,
    )
    console.setLevel(log_level)
    console.addFilter(ConsoleFilter())
    console.setFormatter(logging.Formatter("%(message)s"))

    # Detailed persistent debugging logs.
    file_handler = RotatingFileHandler(
        log_dir / "crawler.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
    )

    logging.basicConfig(
        level=logging.INFO,
        handlers=[console, file_handler],
        force=True,
    )

    # Allow detailed crawler logs when requested.
    logging.getLogger("crawler").setLevel(log_level)

    # Preserve SQL and HTTP request information in the log file.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.INFO)