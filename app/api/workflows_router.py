"""Workflow history API router.

Read-only endpoints surfacing the workflow/workflow_steps audit trail that
AgentService already persists during every Reason -> Plan -> Act -> Observe
run (and every approval decision). Route handlers stay thin — all lookup
logic lives in WorkflowService.
"""

from fastapi import APIRouter, Depends, Query

from app.api.approvals_router import get_workflow_service
from app.schemas.workflow import (
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowStepListResponse,
    WorkflowStepResponse,
)
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=WorkflowListResponse)
def list_workflows(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowListResponse:
    """Return all workflows, newest first."""
    items, total = workflow_service.get_workflows(limit=limit, offset=offset)
    return WorkflowListResponse(
        items=[WorkflowResponse(**item) for item in items], total=total
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str, workflow_service: WorkflowService = Depends(get_workflow_service)
) -> WorkflowResponse:
    """Return a single workflow's metadata."""
    item = workflow_service.get_workflow(workflow_id)
    return WorkflowResponse(**item)


@router.get("/{workflow_id}/steps", response_model=WorkflowStepListResponse)
def get_workflow_steps(
    workflow_id: str, workflow_service: WorkflowService = Depends(get_workflow_service)
) -> WorkflowStepListResponse:
    """Return every recorded step of a workflow, in chronological order."""
    items = workflow_service.get_workflow_steps(workflow_id)
    return WorkflowStepListResponse(
        items=[WorkflowStepResponse(**item) for item in items], total=len(items)
    )