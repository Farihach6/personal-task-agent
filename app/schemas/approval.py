"""Pydantic schemas for the approvals API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PendingApproval(BaseModel):
    """A workflow currently waiting on a human approval decision."""

    workflow_id: str
    user_prompt: str
    tool_name: str | None
    tool_input: dict[str, Any]
    created_at: datetime


class PendingApprovalListResponse(BaseModel):
    """A list of workflows awaiting approval."""

    items: list[PendingApproval]
    total: int


class ApprovalDecisionResponse(BaseModel):
    """The result of resuming a workflow after an approve/reject decision."""

    workflow_id: str
    intent: str
    plan: list[str]
    final_response: str
    status: str