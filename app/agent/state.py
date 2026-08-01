
"""Agent state definition.

Extends Milestone 4's minimal echo state into a real Reason -> Plan
pipeline: `intent` and `plan` are now first-class fields, and
`current_step`/`metadata` track pipeline progress and per-node debug
context that gets persisted to workflow_steps.
"""

from typing import Any, TypedDict


class AgentState(TypedDict):
    """State threaded through every node of the LangGraph graph."""

    user_message: str
    intent: str
    plan: list[str]
    workflow_id: str | None  # matches Workflow.id (UUID string primary key)
    current_step: str  # "REASON" | "PLAN" | "DONE"
    status: str  # "RUNNING" | "COMPLETED" | "FAILED"
    metadata: dict[str, Any]


def create_initial_state(workflow_id: str | None, user_message: str) -> AgentState:
    """Build the initial state for a new agent run."""
    return AgentState(
        user_message=user_message,
        intent="",
        plan=[],
        workflow_id=workflow_id,
        current_step="REASON",
        status="RUNNING",
        metadata={},
    )
