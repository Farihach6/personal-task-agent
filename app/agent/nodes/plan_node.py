"""Plan node: turns the identified intent into an ordered list of steps."""

from app.agent.prompts import PLAN_PROMPT_TEMPLATE
from app.agent.state import AgentState
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient
from app.utils.serialization import from_json

logger = get_logger(__name__)


def _parse_plan(raw_response: str, fallback_message: str) -> list[str]:
    """Parse the LLM's JSON array response into a list of plan steps.

    Falls back to a single-step plan if the LLM output isn't valid JSON or
    isn't a non-empty list of strings.
    """
    parsed = from_json(raw_response, default=None)

    if (
        isinstance(parsed, list)
        and parsed
        and all(isinstance(item, str) for item in parsed)
    ):
        return parsed

    logger.warning(
        "Plan node could not parse a valid JSON step list; using fallback plan."
    )

    return [f"Respond to: {fallback_message}"]


def build_plan_node(llm_client: GroqClient):
    """Create a Plan node bound to the provided LLM client."""

    def plan_node(state: AgentState) -> AgentState:
        logger.info(
            "Plan node started for workflow_id=%s",
            state["workflow_id"],
        )

        try:
            prompt = PLAN_PROMPT_TEMPLATE.format(
                user_message=state["user_message"],
                intent=state["intent"],
            )

            raw_response = llm_client.generate(prompt)

            plan = _parse_plan(
                raw_response,
                state["user_message"],
            )

            state["plan"] = plan
            state["current_step"] = "DONE"
            state["status"] = "COMPLETED"

            state["metadata"] = {
                **state["metadata"],
                "plan_raw_response": raw_response,
            }

            logger.info(
                "Plan node completed successfully with %d steps.",
                len(plan),
            )

            return state

        except Exception as exc:
            logger.exception("Plan node failed.")

            state["status"] = "FAILED"

            state["metadata"] = {
                **state["metadata"],
                "plan_error": str(exc),
            }

            # Re-raise so AgentService can finalize workflow as FAILED
            raise

    return plan_node