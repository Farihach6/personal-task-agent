"""Reason node: interprets the user's message and extracts an intent."""

from app.agent.prompts import REASON_PROMPT_TEMPLATE
from app.agent.state import AgentState
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient
from app.services.logging_service import LoggingService

logger = get_logger(__name__)


def build_reason_node(
    llm_client: GroqClient,
    logging_service: LoggingService | None = None,
):
    """Create a Reason node bound to the provided LLM client."""

    def reason_node(state: AgentState) -> AgentState:
        workflow_id = state["workflow_id"]

        logger.info(
            "Reason node started for workflow_id=%s",
            workflow_id,
        )

        if logging_service is not None:
            logging_service.log_event(
                message="Reason node started.",
                level="INFO",
                workflow_id=workflow_id,
            )

        try:
            prompt = REASON_PROMPT_TEMPLATE.format(
                user_message=state["user_message"]
            )

            intent = llm_client.generate(prompt).strip()

            if not intent:
                raise ValueError("LLM returned an empty intent.")

            state["intent"] = intent
            state["current_step"] = "PLAN"

            state["metadata"] = {
                **state["metadata"],
                "reason_raw_response": intent,
            }

            logger.info(
                "Reason node completed successfully: %s",
                intent,
            )

            if logging_service is not None:
                logging_service.log_event(
                    message=f"Reason node completed: identified intent {intent!r}.",
                    level="INFO",
                    workflow_id=workflow_id,
                )

            return state

        except Exception as exc:
            logger.exception("Reason node failed.")

            if logging_service is not None:
                logging_service.log_event(
                    message=f"Reason node failed: {exc}",
                    level="ERROR",
                    workflow_id=workflow_id,
                )

            state["status"] = "FAILED"

            state["metadata"] = {
                **state["metadata"],
                "reason_error": str(exc),
            }

            # Re-raise so AgentService can finalize workflow as FAILED
            raise

    return reason_node