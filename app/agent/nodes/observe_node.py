"""Observe node: turns the tool result into a natural-language final answer."""

from app.agent.prompts import OBSERVE_PROMPT_TEMPLATE
from app.agent.state import AgentState
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient
from app.services.logging_service import LoggingService
from app.utils.serialization import to_json

logger = get_logger(__name__)

_FAILURE_FALLBACK_RESPONSE = (
    "I couldn't complete that request due to a tool error. Please try again."
)

_OBSERVE_ERROR_FALLBACK_RESPONSE = (
    "I ran into an error while preparing a response."
)


def build_observe_node(
    llm_client: GroqClient,
    logging_service: LoggingService | None = None,
):
    """Create an Observe node bound to the provided LLM client."""

    def observe_node(state: AgentState) -> AgentState:
        workflow_id = state["workflow_id"]

        logger.info(
            "Graph node 'observe' started for workflow_id=%s",
            workflow_id,
        )

        if logging_service is not None:
            logging_service.log_event(
                message="Observe node started.",
                level="INFO",
                workflow_id=workflow_id,
            )

        # Skip the LLM if a previous node already failed.
        if state["status"] == "FAILED":
            state["final_response"] = _FAILURE_FALLBACK_RESPONSE
            state["current_step"] = "DONE"

            logger.info(
                "Graph node 'observe' skipped LLM call for workflow_id=%s (upstream failure)",
                workflow_id,
            )

            if logging_service is not None:
                logging_service.log_event(
                    message="Observe node skipped response generation: an earlier step already failed.",
                    level="WARNING",
                    workflow_id=workflow_id,
                )

            return state

        try:
            prompt = OBSERVE_PROMPT_TEMPLATE.format(
                user_message=state["user_message"],
                intent=state["intent"],
                plan=to_json(state["plan"]),
                tool_result=to_json(state["tool_result"]),
            )

            logger.info(
                "Generating final response for workflow_id=%s",
                workflow_id,
            )

            if logging_service is not None:
                logging_service.log_event(
                    message="Generating final response using LLM.",
                    level="INFO",
                    workflow_id=workflow_id,
                )

            final_response = llm_client.generate(prompt).strip()

            # Preserve existing behavior/tests
            if not final_response:
                raise ValueError("LLM returned an empty response.")

            state["final_response"] = final_response
            state["status"] = "COMPLETED"
            state["current_step"] = "DONE"

            state["metadata"] = {
                **state["metadata"],
                "observe_raw_response": final_response,
            }

            logger.info(
                "Graph node 'observe' finished for workflow_id=%s response_length=%d",
                workflow_id,
                len(final_response),
            )

            if logging_service is not None:
                logging_service.log_event(
                    message="Observe node completed: final response generated.",
                    level="INFO",
                    workflow_id=workflow_id,
                )

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Graph node 'observe' failed for workflow_id=%s",
                workflow_id,
            )

            if logging_service is not None:
                logging_service.log_event(
                    message=f"Observe node failed: {exc}",
                    level="ERROR",
                    workflow_id=workflow_id,
                )

            state["final_response"] = _OBSERVE_ERROR_FALLBACK_RESPONSE
            state["status"] = "FAILED"
            state["current_step"] = "DONE"

            state["metadata"] = {
                **state["metadata"],
                "error": str(exc),
            }

        return state

    return observe_node