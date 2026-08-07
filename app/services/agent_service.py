"""Agent service.

The single entry point the API layer uses to run the agent graph. Streams
the graph node-by-node so each Reason/Plan/Act/Observe step can be
persisted to workflow_steps as it completes, then finalizes the workflow
row with the final status and final_response.

Also handles the human-approval flow: `run()` pauses (rather than
finalizing) a workflow whose Act node set status="WAITING_APPROVAL", and
`resume()` continues a paused workflow after a human approves or rejects
it — reconstructing the necessary state entirely from what's already
persisted in workflow_steps, then executing the tool (if approved) and
running Observe directly, exactly as the graph itself would have.
"""

from functools import lru_cache
from typing import Any

from app.agent.graph import build_graph
from app.agent.nodes.observe_node import build_observe_node
from app.agent.state import create_initial_state
from app.agent.tools.tool_executor import ToolExecutor
from app.core.exceptions import GuardrailViolation
from app.core.logger import get_logger
from app.database.session import session_scope
from app.llm.groq_client import GroqClient
from app.services.logging_service import LoggingService
from app.services.workflow_service import WorkflowService

logger = get_logger(__name__)

_AWAITING_APPROVAL_RESPONSE = "This action requires your approval before it can proceed."


class AgentService:
    """Runs the compiled Reason -> Plan -> Act -> Observe graph for a single
    user message, and can resume a workflow that paused for human approval."""

    def __init__(
        self,
        llm_client: GroqClient | None = None,
        workflow_service: WorkflowService | None = None,
        tool_executor: ToolExecutor | None = None,
        logging_service: LoggingService | None = None,
    ) -> None:
        # Resolved once and kept (rather than left to build_graph to resolve
        # internally) so resume() can reuse the exact same LLM client and
        # tool executor instances the original run used.
        self._llm_client = llm_client or GroqClient()
        self._tool_executor = tool_executor or ToolExecutor()
        self._workflow_service = workflow_service or WorkflowService()
        self._logging_service = logging_service or LoggingService(
            session_factory=getattr(
                self._workflow_service,
                "_session_factory",
                session_scope,
            )
        )
        self._graph = build_graph(
            self._llm_client,
            self._tool_executor,
            self._logging_service,
        )

    def run(self, user_message: str) -> dict[str, Any]:
        """Run the agent graph once and return the workflow_id, intent, plan,
        final_response, and status.

        Persists a workflow row up front, one workflow_steps row per node as
        the graph streams through Reason/Plan/Act/Observe, and either pauses
        the workflow (status WAITING_APPROVAL, for sensitive tools) or
        finalizes it — even on failure, so no run is left silently unrecorded.
        """
        workflow_id = self._workflow_service.create_workflow(user_message)
        logger.info(
            "Agent graph run starting: workflow_id=%s prompt_length=%d",
            workflow_id,
            len(user_message),
        )
        self._logging_service.log_event(
            f"Workflow started: {user_message[:200]!r}",
            level="INFO",
            workflow_id=workflow_id,
        )

        initial_state = create_initial_state(workflow_id, user_message)
        final_state = initial_state

        try:
            for chunk in self._graph.stream(initial_state):
                for node_name, node_state in chunk.items():
                    self._record_node_step(workflow_id, node_name, user_message, node_state)
                    final_state = node_state

            if final_state["status"] == "WAITING_APPROVAL":
                self._logging_service.log_event(
                    "Workflow paused: awaiting human approval.",
                    level="WARNING",
                    workflow_id=workflow_id,
                )
                self._workflow_service.mark_awaiting_approval(workflow_id)
            else:
                self._workflow_service.finalize_workflow(
                    workflow_id=workflow_id,
                    status=final_state["status"],
                    final_response=final_state.get("final_response"),
                )
                self._log_workflow_finalized(
                    workflow_id,
                    final_state["status"],
                )
        except Exception as exc:
            logger.exception("Agent graph run failed: workflow_id=%s", workflow_id)
            self._logging_service.log_event(
                f"Workflow failed: unexpected error: {exc}",
                level="ERROR",
                workflow_id=workflow_id,
            )
            self._workflow_service.finalize_workflow(workflow_id=workflow_id, status="FAILED")
            raise

        logger.info(
            "Agent graph run finished: workflow_id=%s status=%s",
            workflow_id,
            final_state["status"],
        )

        final_response = final_state.get("final_response")
        if final_state["status"] == "WAITING_APPROVAL" and not final_response:
            final_response = _AWAITING_APPROVAL_RESPONSE

        return {
            "workflow_id": workflow_id,
            "intent": final_state["intent"],
            "plan": final_state["plan"],
            "final_response": final_response or "",
            "status": final_state["status"],
        }

    def resume(self, workflow_id: str, approved: bool) -> dict[str, Any]:
        """Resume a workflow that's waiting on a human approval decision.

        Reconstructs the paused state entirely from persisted workflow_steps
        (no separate in-memory state is kept between the pause and this
        call), then either executes the approved tool and runs Observe, or
        completes the workflow gracefully without executing it if rejected.
        """
        context = self._workflow_service.get_workflow_context(workflow_id)
        tool_name = context.get("tool_name")
        logger.info(
            "Resuming workflow_id=%s approved=%s tool=%s",
            workflow_id,
            approved,
            tool_name,
        )

        if context.get("status") != "WAITING_APPROVAL":
            raise GuardrailViolation(
                f"Workflow {workflow_id} is not awaiting approval "
                f"(current status: {context.get('status')!r}); it may have already been resolved."
            )

        self._logging_service.log_event(
            f"Human approval received: {'approved' if approved else 'rejected'} tool '{tool_name}'.",
            level="INFO",
            workflow_id=workflow_id,
        )

        state = create_initial_state(workflow_id, context["user_message"])
        state["intent"] = context["intent"]
        state["plan"] = context["plan"]
        state["tool_name"] = context["tool_name"]
        state["tool_input"] = context["tool_input"]

        approval_status = "APPROVED" if approved else "REJECTED"

        try:
            self._workflow_service.save_step(
                workflow_id=workflow_id,
                node_name="approval",
                action_summary=(
                    f"Human approved running tool '{context.get('tool_name')}'."
                    if approved
                    else f"Human rejected running tool '{context.get('tool_name')}'."
                ),
                tool_name=context.get("tool_name"),
                tool_input=context.get("tool_input"),
            )

            if approved:
                self._logging_service.log_event(
                    f"Tool execution started: '{tool_name}'.",
                    level="INFO",
                    workflow_id=workflow_id,
                )
                try:
                    tool_result = self._tool_executor.execute(
                        context["tool_name"], context["tool_input"]
                    )
                    state["tool_result"] = tool_result
                    state["status"] = "RUNNING"
                    state["metadata"] = {
                        **state["metadata"],
                        "act_tool_used": context["tool_name"],
                    }
                    self._logging_service.log_event(
                        f"Tool execution completed: '{tool_name}'.",
                        level="INFO",
                        workflow_id=workflow_id,
                    )
                except Exception as exc:  # noqa: BLE001 - a failed tool must not crash resume
                    logger.error(
                        "Resumed tool execution failed for workflow_id=%s: %s", workflow_id, exc
                    )
                    self._logging_service.log_event(
                        f"Tool execution failed: '{tool_name}': {exc}",
                        level="ERROR",
                        workflow_id=workflow_id,
                    )
                    state["tool_result"] = None
                    state["status"] = "FAILED"
                    state["metadata"] = {**state["metadata"], "error": str(exc)}
            else:
                state["tool_result"] = {
                    "observation": "action_rejected",
                    "tool_name": context["tool_name"],
                }
                state["status"] = "RUNNING"
                state["metadata"] = {**state["metadata"], "rejected": True}

            self._record_node_step(workflow_id, "act_node", context["user_message"], state)

            observe_node = build_observe_node(
                self._llm_client,
                self._logging_service,
            )
            state = observe_node(state)
            self._record_node_step(workflow_id, "observe_node", context["user_message"], state)

            self._workflow_service.finalize_workflow(
                workflow_id=workflow_id,
                status=state["status"],
                final_response=state.get("final_response"),
                approval_status=approval_status,
            )
            self._log_workflow_finalized(
                workflow_id,
                state["status"],
            )
        except Exception:
            logger.exception("Resume failed unexpectedly for workflow_id=%s", workflow_id)
            self._logging_service.log_event(
                "Workflow failed: unexpected error during resume.",
                level="ERROR",
                workflow_id=workflow_id,
            )
            self._workflow_service.finalize_workflow(
                workflow_id=workflow_id, status="FAILED", approval_status=approval_status
            )
            raise

        logger.info("Resume finished for workflow_id=%s status=%s", workflow_id, state["status"])

        return {
            "workflow_id": workflow_id,
            "intent": state["intent"],
            "plan": state["plan"],
            "final_response": state.get("final_response") or "",
            "status": state["status"],
        }

    def _log_workflow_finalized(
        self,
        workflow_id: str,
        status: str,
    ) -> None:
        if status == "COMPLETED":
            self._logging_service.log_event(
                "Workflow completed successfully.",
                level="INFO",
                workflow_id=workflow_id,
            )
        elif status == "FAILED":
            self._logging_service.log_event(
                "Workflow failed.",
                level="ERROR",
                workflow_id=workflow_id,
            )

    def _record_node_step(
        self, workflow_id: str, node_name: str, user_message: str, node_state: dict[str, Any]
    ) -> None:
        """Persist one workflow_steps row, shaped per node type."""
        tool_name: str | None = None

        if node_name == "reason_node":
            node_type = "REASON"
            input_data = {"user_message": user_message}
            output_data = {"intent": node_state["intent"]}
        elif node_name == "plan_node":
            node_type = "PLAN"
            input_data = {"user_message": user_message, "intent": node_state["intent"]}
            output_data = {"plan": node_state["plan"]}
        elif node_name == "act_node":
            node_type = "ACT"
            tool_name = node_state.get("tool_name")
            input_data = {"tool_name": node_state.get("tool_name"), "tool_input": node_state.get("tool_input")}
            output_data = {"tool_result": node_state.get("tool_result"), "status": node_state["status"]}
        elif node_name == "observe_node":
            node_type = "OBSERVE"
            input_data = {"tool_result": node_state.get("tool_result")}
            output_data = {
                "final_response": node_state.get("final_response"),
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
            tool_name=tool_name,
        )


@lru_cache
def get_agent_service() -> AgentService:
    """FastAPI dependency returning a cached AgentService (one GroqClient per process)."""
    return AgentService()