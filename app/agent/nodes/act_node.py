"""Act node: executes the selected tool (Search) and records its result.

Only the Search tool is available in Milestone 6. The execution still goes
through ToolExecutor so future tools can be added without changing this node.
"""

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

        tool_name = "search"
        tool_input: dict[str, Any] = {
            "query": state["intent"] or state["user_message"],
        }

        # Always record tool information, even if execution fails.
        state["tool_name"] = tool_name
        state["tool_input"] = tool_input

        try:
            tool_result = tool_executor.execute(
                tool_name=tool_name,
                tool_input=tool_input,
            )

            state["tool_result"] = tool_result
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

            # IMPORTANT:
            # Tests expect metadata["error"], not metadata["act_error"].
            state["metadata"] = {
                **state["metadata"],
                "error": str(exc),
            }

        return state

    return act_node