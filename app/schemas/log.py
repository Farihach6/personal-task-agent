"""Pydantic schemas for the Execution Logs API."""

from datetime import datetime

from pydantic import BaseModel


class LogEntryResponse(BaseModel):
    """A single execution-log entry."""

    id: int
    workflow_id: str | None
    level: str
    message: str
    timestamp: datetime


class LogListResponse(BaseModel):
    """A page of execution-log entries, newest first."""

    items: list[LogEntryResponse]
    total: int