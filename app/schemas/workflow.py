"""Pydantic schemas for workflow history responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkflowResponse(BaseModel):
    """A single workflow's metadata."""

    workflow_id: str
    user_input: str
    final_response: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None


class WorkflowListResponse(BaseModel):
    """A page of workflows, newest first."""

    items: list[WorkflowResponse]
    total: int


class WorkflowStepResponse(BaseModel):
    """A single recorded step in a workflow's execution trace."""

    workflow_id: str
    sequence_number: int
    node_name: str
    action_summary: str
    tool_name: str | None
    tool_input: dict[str, Any] | None
    tool_output: dict[str, Any] | None
    timestamp: datetime


class WorkflowStepListResponse(BaseModel):
    """The full chronological step trace for one workflow."""

    items: list[WorkflowStepResponse]
    total: int