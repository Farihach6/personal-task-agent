"""Approvals API router.

Sensitive actions (currently: sending email) pause the agent workflow and
surface here for a human to approve or reject before they execute.
"""

from fastapi import APIRouter, Depends

from app.schemas.approval import (
    ApprovalDecisionResponse,
    PendingApproval,
    PendingApprovalListResponse,
)
from app.services.agent_service import AgentService, get_agent_service
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/approvals", tags=["approvals"])


def get_workflow_service() -> WorkflowService:
    """FastAPI dependency returning a WorkflowService bound to the real engine."""
    return WorkflowService()


@router.get("", response_model=PendingApprovalListResponse)
def list_pending_approvals(
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> PendingApprovalListResponse:
    """List all workflows currently waiting on a human approval decision."""
    items = workflow_service.get_pending_approvals()
    return PendingApprovalListResponse(
        items=[PendingApproval(**item) for item in items], total=len(items)
    )


@router.post("/{workflow_id}/approve", response_model=ApprovalDecisionResponse)
def approve_workflow(
    workflow_id: str, service: AgentService = Depends(get_agent_service)
) -> ApprovalDecisionResponse:
    """Approve a pending action and resume its workflow, executing the tool."""
    result = service.resume(workflow_id, approved=True)
    return ApprovalDecisionResponse(**result)


@router.post("/{workflow_id}/reject", response_model=ApprovalDecisionResponse)
def reject_workflow(
    workflow_id: str, service: AgentService = Depends(get_agent_service)
) -> ApprovalDecisionResponse:
    """Reject a pending action and complete its workflow without executing the tool."""
    result = service.resume(workflow_id, approved=False)
    return ApprovalDecisionResponse(**result)