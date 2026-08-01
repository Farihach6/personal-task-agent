"""Agent service.

The single entry point the API layer uses to run the agent graph. Streams
the graph node-by-node so each Reason/Plan step can be persisted to
workflow_steps as it completes, then finalizes the workflow row.
"""

from functools import lru_cache
from typing import Any

from app.agent.graph import build_graph
from app.agent.state import create_initial_state
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient
from app.services.workflow_service import WorkflowService

logger = get_logger(__name__)


class AgentService:
    """Runs the compiled Reason → Plan graph for a single user message."""

    def __init__(
        self,
        llm_client: GroqClient | None = None,
        workflow_service: WorkflowService | None = None,
    ) -> None:
        self._graph = build_graph(llm_client)
        self._workflow_service = workflow_service or WorkflowService()

    def run(self, user_message: str) -> dict[str, Any]:
        """Run the agent graph and persist workflow + workflow steps."""
        workflow_id = self._workflow_service.create_workflow(user_message)

        logger.info(
            "Agent graph run starting: workflow_id=%s prompt_length=%d",
            workflow_id,
            len(user_message),
        )

        initial_state = create_initial_state(workflow_id, user_message)
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
            )

        except Exception:
            logger.exception(
                "Agent graph run failed: workflow_id=%s",
                workflow_id,
            )

            self._workflow_service.finalize_workflow(
                workflow_id=workflow_id,
                status="FAILED",
            )
            raise

        logger.info(
            "Agent graph run finished: workflow_id=%s status=%s",
            workflow_id,
            final_state["status"],
        )

        return {
            "workflow_id": workflow_id,
            "intent": final_state["intent"],
            "plan": final_state["plan"],
            "status": final_state["status"],
        }

    def _record_node_step(
        self,
        workflow_id: str,
        node_name: str,
        user_message: str,
        node_state: dict[str, Any],
    ) -> None:
        """Persist one workflow_steps row for a graph node."""

        if node_name == "reason_node":
            input_data = {
                "user_message": user_message,
            }

            output_data = {
                "intent": node_state["intent"],
            }

        elif node_name == "plan_node":
            input_data = {
                "user_message": user_message,
                "intent": node_state["intent"],
            }

            output_data = {
                "plan": node_state["plan"],
            }

        else:
            input_data = {}
            output_data = {}

        node_type = {
            "reason_node": "REASON",
            "plan_node": "PLAN",
        }.get(node_name, node_name.upper())

        self._workflow_service.record_step(
            workflow_id=workflow_id,
            node_type=node_type,
            input_data=input_data,
            output_data=output_data,
        )


@lru_cache
def get_agent_service() -> AgentService:
    """FastAPI dependency returning a cached AgentService."""
    return AgentService()