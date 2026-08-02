"""Agent state definition.

Extends Milestone 5's Reason -> Plan state with the fields needed for
Act -> Observe. The Act node stores the selected tool, its input, and
its result, while the Observe node generates the final natural-language
response returned to the user.
"""

from typing import Any, TypedDict


class AgentState(TypedDict):
    """State threaded through every node of the LangGraph graph."""

    # User input
    user_message: str

    # Reason node
    intent: str

    # Plan node
    plan: list[str]

    # Workflow metadata
    workflow_id: str | None
    current_step: str  # "REASON" | "PLAN" | "ACT" | "OBSERVE" | "DONE"
    status: str  # "RUNNING" | "COMPLETED" | "FAILED"
    metadata: dict[str, Any]

    # Act node
    tool_name: str | None
    tool_input: dict[str, Any]
    tool_result: dict[str, Any]

    # Observe node
    final_response: str | None


def create_initial_state(
    workflow_id: str | None,
    user_message: str,
) -> AgentState:
    """Build the initial state for a new agent run."""

    return AgentState(
        user_message=user_message,
        intent="",
        plan=[],
        workflow_id=workflow_id,
        current_step="REASON",
        status="RUNNING",
        metadata={},

        # Act node
        tool_name=None,
        tool_input={},
        tool_result={},

        # Observe node
        final_response=None,
    )