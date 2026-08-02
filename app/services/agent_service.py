"""Agent service.

The single entry point the API layer uses to run the agent graph.
Streams the graph node-by-node so each Reason/Plan/Act/Observe step
is persisted to workflow_steps as it completes, then finalizes the
workflow row with final status and final_response.
"""

from functools import lru_cache
from typing import Any

from app.agent.graph import build_graph
from app.agent.state import create_initial_state
from app.agent.tools.tool_executor import ToolExecutor
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient
from app.services.workflow_service import WorkflowService

logger = get_logger(__name__)


class AgentService:
    """Runs the compiled Reason → Plan → Act → Observe graph."""

    def __init__(
        self,
        llm_client: GroqClient | None = None,
        workflow_service: WorkflowService | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:

        self._graph = build_graph(
            llm_client=llm_client,
            tool_executor=tool_executor,
        )

        self._workflow_service = workflow_service or WorkflowService()

    def run(self, user_message: str) -> dict[str, Any]:
        """Execute agent workflow and persist every node execution."""

        workflow_id = self._workflow_service.create_workflow(
            user_message
        )

        logger.info(
            "Agent run started workflow_id=%s",
            workflow_id,
        )

        initial_state = create_initial_state(
            workflow_id,
            user_message,
        )

        final_state = initial_state

        try:
            for chunk in self._graph.stream(initial_state):

                for node_name, node_state in chunk.items():

                    self._record_node_step(
                        workflow_id=workflow_id,
                        node_name=node_name,
                        user_message=user_message,
                        node_state=node_state,
                    )

                    final_state = node_state


            self._workflow_service.finalize_workflow(
                workflow_id=workflow_id,
                status=final_state["status"],
                final_response=final_state.get(
                    "final_response"
                ),
            )

        except Exception:

            logger.exception(
                "Agent execution failed workflow_id=%s",
                workflow_id,
            )

            self._workflow_service.finalize_workflow(
                workflow_id=workflow_id,
                status="FAILED",
            )

            raise


        logger.info(
            "Agent run completed workflow_id=%s status=%s",
            workflow_id,
            final_state["status"],
        )


        return {
            "workflow_id": workflow_id,
            "intent": final_state["intent"],
            "plan": final_state["plan"],
            "final_response": final_state.get(
                "final_response"
            ) or "",
            "status": final_state["status"],
        }


    def _record_node_step(
        self,
        workflow_id: str,
        node_name: str,
        user_message: str,
        node_state: dict[str, Any],
    ) -> None:
        """Save each graph node execution into workflow_steps."""

        if node_name == "reason_node":

            node_type = "REASON"

            input_data = {
                "user_message": user_message,
            }

            output_data = {
                "intent": node_state["intent"],
            }


        elif node_name == "plan_node":

            node_type = "PLAN"

            input_data = {
                "user_message": user_message,
                "intent": node_state["intent"],
            }

            output_data = {
                "plan": node_state["plan"],
            }


        elif node_name == "act_node":

            node_type = "ACT"

            input_data = {
                "tool_name": node_state.get(
                    "tool_name"
                ),
                "tool_input": node_state.get(
                    "tool_input"
                ),
            }

            output_data = {
                "tool_result": node_state.get(
                    "tool_result"
                ),
                "status": node_state["status"],
            }


        elif node_name == "observe_node":

            node_type = "OBSERVE"

            input_data = {
                "tool_result": node_state.get(
                    "tool_result"
                ),
            }

            output_data = {
                "final_response": node_state.get(
                    "final_response"
                ),
                "status": node_state["status"],
            }


        else:

            node_type = node_name.upper()

            input_data = {}
            output_data = {}


        self._workflow_service.record_step(
            workflow_id=workflow_id,
            node_type=node_type,
            input_data=input_data,
            output_data=output_data,
        )


@lru_cache
def get_agent_service() -> AgentService:
    """FastAPI dependency returning cached AgentService."""

    return AgentService()