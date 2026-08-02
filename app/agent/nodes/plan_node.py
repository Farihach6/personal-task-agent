"""Plan node: turns the identified intent into an ordered list of steps."""

import re

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


def _determine_tool_call(
    user_message: str,
    intent: str,
) -> tuple[str, dict]:
    """Determine which tool should execute the request."""

    message = user_message.lower()

    # -----------------------
    # Create note
    # -----------------------
    if any(
        phrase in message
        for phrase in (
            "save a note",
            "save note",
            "remember",
            "take a note",
            "create note",
            "create a note",
            "note that",
        )
    ):
        content = user_message

        prefixes = [
            "save a note that",
            "save a note",
            "save note",
            "remember that",
            "remember",
            "take a note that",
            "take a note",
            "create a note that",
            "create a note",
            "note that",
        ]

        lowered = message

        for prefix in prefixes:
            if lowered.startswith(prefix):
                content = user_message[len(prefix):].strip()
                break

        return (
            "notes",
            {
                "action": "create",
                "content": content,
            },
        )

    # -----------------------
    # List notes
    # -----------------------
    if (
        "show all my notes" in message
        or "show my notes" in message
        or "list my notes" in message
        or "list notes" in message
        or "all notes" in message
    ):
        return "notes", {"action": "list"}

    # -----------------------
    # Delete note
    # -----------------------
    match = re.search(r"delete note\s+(\d+)", message)
    if match:
        return (
            "notes",
            {
                "action": "delete",
                "note_id": int(match.group(1)),
            },
        )

    # -----------------------
    # Update note
    # -----------------------
    match = re.search(
        r"update note\s+(\d+)\s+to\s+say\s+(.+)",
        user_message,
        re.IGNORECASE,
    )
    if match:
        return (
            "notes",
            {
                "action": "update",
                "note_id": int(match.group(1)),
                "content": match.group(2).strip(),
            },
        )

    # -----------------------
    # Get note
    # -----------------------
    match = re.search(r"(?:show|get|read|find)\s+note\s+(\d+)", message)
    if match:
        return (
            "notes",
            {
                "action": "get",
                "note_id": int(match.group(1)),
            },
        )

    # -----------------------
    # Default: Search
    # -----------------------
    return (
        "search",
        {
            "query": intent or user_message,
        },
    )


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

            tool_name, tool_input = _determine_tool_call(
                state["user_message"],
                state["intent"],
            )

            state["plan"] = plan
            state["tool_name"] = tool_name
            state["tool_input"] = tool_input
            state["status"] = "COMPLETED"

            # Let the graph continue to Act
            state["current_step"] = "ACT"

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

            raise

    return plan_node