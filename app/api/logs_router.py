"""Execution Logs API router.

Read-only endpoint surfacing the execution_logs audit trail that
LoggingService writes during every agent run (workflow lifecycle, per-node
events, approvals, and tool execution). Route handlers stay thin — all
lookup logic lives in LoggingService.
"""

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import GuardrailViolation
from app.schemas.log import LogEntryResponse, LogListResponse
from app.services.logging_service import LoggingService

router = APIRouter(prefix="/logs", tags=["logs"])

_VALID_LEVELS = ("INFO", "WARNING", "ERROR")


def get_logging_service() -> LoggingService:
    """FastAPI dependency returning a LoggingService bound to the real engine."""
    return LoggingService()


@router.get("", response_model=LogListResponse)
def list_logs(
    workflow_id: str | None = Query(default=None, description="Filter by workflow id"),
    level: str | None = Query(default=None, description="Filter by log level (INFO/WARNING/ERROR)"),
    limit: int = Query(default=100, ge=1, le=1000),
    logging_service: LoggingService = Depends(get_logging_service),
) -> LogListResponse:
    """Return execution log entries, newest first, with optional filters.

    Raises:
        GuardrailViolation: (400) if `level` is provided but isn't one of
            INFO, WARNING, or ERROR.
    """
    normalized_level = _validate_level(level)
    items = logging_service.get_logs(workflow_id=workflow_id, level=normalized_level, limit=limit)
    return LogListResponse(items=[LogEntryResponse(**item) for item in items], total=len(items))


def _validate_level(level: str | None) -> str | None:
    """Normalize and validate the `level` filter, or raise GuardrailViolation."""
    if level is None:
        return None
    normalized = level.upper()
    if normalized not in _VALID_LEVELS:
        raise GuardrailViolation(
            f"Invalid log level: {level!r}. Must be one of {', '.join(_VALID_LEVELS)}."
        )
    return normalized