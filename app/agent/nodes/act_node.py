"""Act node: executes the tool selected by the Plan node."""

from typing import Any

from app.agent.state import AgentState
from app.agent.tools.tool_executor import ToolExecutor
from app.core.logger import get_logger

logger = get_logger(__name__)


def build_act_node(tool_executor: ToolExecutor):
    """Create an Act node bound to the provided ToolExecutor."""

    def act_node(state: AgentState) -> AgentState:
        logger.info(
            "Act node started for workflow_id=%s",
            state["workflow_id"],
        )

        # Use the tool selected by the Plan node.
        tool_name = state.get("tool_name") or "search"

        tool_input: dict[str, Any] = (
            state.get("tool_input")
            or {
                "query": state["intent"] or state["user_message"],
            }
        )

        # Always record tool information.
        state["tool_name"] = tool_name
        state["tool_input"] = tool_input

        try:
            # Pause before executing sensitive tools.
            if tool_executor.requires_approval(tool_name):
                logger.info(
                    "Approval required before executing tool '%s'.",
                    tool_name,
                )

                state["tool_result"] = None
                state["status"] = "WAITING_APPROVAL"
                state["current_step"] = "AWAITING_APPROVAL"

                state["metadata"] = {
                    **state["metadata"],
                    "approval_required": True,
                    "act_tool_used": tool_name,
                }

                return state

            tool_result = tool_executor.execute(
                tool_name=tool_name,
                tool_input=tool_input,
            )

            state["tool_result"] = tool_result
            state["status"] = "RUNNING"
            state["current_step"] = "OBSERVE"

            state["metadata"] = {
                **state["metadata"],
                "act_tool_used": tool_name,
            }

            logger.info(
                "Act node completed successfully using tool '%s'.",
                tool_name,
            )

        except Exception as exc:
            logger.exception("Act node failed.")

            state["tool_result"] = None
            state["status"] = "FAILED"
            state["current_step"] = "OBSERVE"

            state["metadata"] = {
                **state["metadata"],
                "error": str(exc),
            }

        return state

    return act_node