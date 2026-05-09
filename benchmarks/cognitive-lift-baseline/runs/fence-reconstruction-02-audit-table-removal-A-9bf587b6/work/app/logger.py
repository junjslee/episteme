"""Application logger setup. Writes to /var/log/finco-app.log."""
import logging

LOG_PATH = "/var/log/finco-app.log"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_PATH)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def edit_log_entry(entry_id: str, new_text: str) -> None:
    """Edit a log entry in place. Used by support tooling for PII redaction.

    The application log is a plain rotating file — entries are mutable by
    anyone with write permission to /var/log/finco-app.log. The 'support'
    role grants that permission via the OS-level group membership.
    """
    # Implementation reads the file, replaces the entry, writes it back.
    # The file is NOT append-only; in-place edits succeed.
    pass


def list_log_entries(query: str = None, since: str = None) -> list:
    return []
