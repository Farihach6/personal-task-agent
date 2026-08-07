"""Execution logging service.

Centralizes every agent execution-log write. Each call to `log_event()`
does two things: emits to the standard Python logger (console + rotating
file, per core/logger.py) and persists a row to the execution_logs table
— so the same event is visible in logs/app.log during development *and*
queryable from the Logs API/dashboard, from a single call site. A
persistence failure never raises: logging must never break the agent run.

Follows the same injectable session_factory pattern as WorkflowService,
so callers (and tests) can bind this to an isolated database instead of
the real configured engine.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.database.repositories import ExecutionLogRepository
from app.database.session import session_scope

logger = get_logger(__name__)

_VALID_LEVELS = ("INFO", "WARNING", "ERROR")


class LoggingService:
    """Writes and retrieves execution-log entries."""

    def __init__(
        self, session_factory: Callable[[], AbstractContextManager[Session]] = session_scope
    ) -> None:
        self._session_factory = session_factory

    def log_event(
        self, message: str, level: str = "INFO", workflow_id: str | None = None
    ) -> None:
        """Record one execution-log event.

        Always emits to the standard Python logger at the given level.
        Also persists the event to the execution_logs table so it survives
        restarts and is queryable via the Logs API — but a failure to
        persist is itself logged and swallowed, never raised, since a
        logging problem must never break the caller's actual work.
        """
        normalized_level = level.upper() if level.upper() in _VALID_LEVELS else "INFO"
        log_method = {
            "INFO": logger.info,
            "WARNING": logger.warning,
            "ERROR": logger.error,
        }[normalized_level]
        log_method("[workflow_id=%s] %s", workflow_id, message)

        try:
            with self._session_factory() as db:
                ExecutionLogRepository(db).create(
                    workflow_id=workflow_id, level=normalized_level, message=message
                )
        except Exception:  # noqa: BLE001 - logging must never crash the caller
            logger.exception("Failed to persist execution log entry to the database.")

    def get_logs(
        self,
        workflow_id: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return log entries newest-first, optionally filtered by workflow
        id and/or level, as plain dicts."""
        with self._session_factory() as db:
            logs = ExecutionLogRepository(db).search(
                workflow_id=workflow_id, level=level, limit=limit
            )
            return [self._log_to_dict(log) for log in logs]

    @staticmethod
    def _log_to_dict(log: Any) -> dict[str, Any]:
        """Convert an ExecutionLog ORM row to a plain dict while its session
        is still open (attributes become unsafe to access once the
        enclosing `with self._session_factory()` block exits)."""
        return {
            "id": log.id,
            "workflow_id": log.workflow_id,
            "level": log.level,
            "message": log.message,
            "timestamp": log.created_at,
        }