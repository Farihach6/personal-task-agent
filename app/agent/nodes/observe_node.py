"""Observe node: turns the tool result into a natural-language final answer."""

from app.agent.prompts import OBSERVE_PROMPT_TEMPLATE
from app.agent.state import AgentState
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient
from app.utils.serialization import to_json

logger = get_logger(__name__)

_FAILURE_FALLBACK_RESPONSE = (
    "I couldn't complete that request due to a tool error. Please try again."
)

_OBSERVE_ERROR_FALLBACK_RESPONSE = (
    "I ran into an error while preparing a response."
)


def build_observe_node(llm_client: GroqClient):
    """Create an Observe node bound to the provided LLM client."""

    def observe_node(state: AgentState) -> AgentState:
        logger.info(
            "Observe node started for workflow_id=%s",
            state["workflow_id"],
        )

        # Skip the LLM if a previous node already failed.
        if state["status"] == "FAILED":
            state["final_response"] = _FAILURE_FALLBACK_RESPONSE
            state["current_step"] = "DONE"

            logger.info(
                "Observe node skipped because workflow is already FAILED."
            )

            return state

        try:
            prompt = OBSERVE_PROMPT_TEMPLATE.format(
                user_message=state["user_message"],
                intent=state["intent"],
                plan=to_json(state["plan"]),
                tool_result=to_json(state["tool_result"]),
            )

            final_response = llm_client.generate(prompt).strip()

            if not final_response:
                raise ValueError("LLM returned an empty response.")

            state["final_response"] = final_response
            state["status"] = "COMPLETED"
            state["current_step"] = "DONE"

            state["metadata"] = {
                **state["metadata"],
                "observe_raw_response": final_response,
            }

            logger.info("Observe node completed successfully.")

        except Exception as exc:
            logger.exception("Observe node failed.")

            state["final_response"] = _OBSERVE_ERROR_FALLBACK_RESPONSE
            state["status"] = "FAILED"
            state["current_step"] = "DONE"

            # ✅ FIX: tests expect metadata["error"]
            state["metadata"] = {
                **state["metadata"],
                "error": str(exc),
            }

        return state

    return observe_node