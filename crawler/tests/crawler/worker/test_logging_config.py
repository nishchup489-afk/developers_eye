import logging
from logging.handlers import RotatingFileHandler

from crawler.worker.logging_config import setup_logging


def test_production_logging_creates_no_file_and_quiets_sql(monkeypatch, tmp_path):
    root = logging.getLogger()
    previous, level = root.handlers[:], root.level
    sql = logging.getLogger("sqlalchemy.engine")
    http = logging.getLogger("httpx")
    crawler = logging.getLogger("crawler")
    levels = [logger.level for logger in (sql, http, crawler)]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CRAWLER_LOG_TO_FILE", "false")
    try:
        setup_logging()
        assert not (tmp_path / "logs").exists()
        assert not any(isinstance(handler, RotatingFileHandler) for handler in root.handlers)
        assert sql.level == http.level == logging.WARNING
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers, root.level = previous, level
        for logger, old in zip((sql, http, crawler), levels):
            logger.setLevel(old)
