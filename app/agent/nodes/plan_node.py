"""Plan node: turns the identified intent into an ordered list of steps."""

import re
from typing import Any

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


# -----------------------
# Email routing
# -----------------------

_EMAIL_INTENT_PATTERN = re.compile(
    r"\b(email|mail|compose|send a message to)\b",
    re.IGNORECASE,
)

_EMAIL_ADDRESS_PATTERN = re.compile(
    r"[\w.\-+]+@[\w\-]+\.[\w.\-]+"
)

_EMAIL_SUBJECT_PATTERN = re.compile(
    r"subject\s*[:\-]\s*(.+?)(?:\.\s|$)",
    re.IGNORECASE,
)

_EMAIL_BODY_CONNECTOR_PATTERN = re.compile(
    r"^(that|saying|:|-)\s*",
    re.IGNORECASE,
)


def _looks_like_email_request(text: str) -> bool:
    return (

        bool(_EMAIL_INTENT_PATTERN.search(text))
        and bool(_EMAIL_ADDRESS_PATTERN.search(text))
    )
    


def _extract_email_address(user_message: str) -> str | None:
    match = _EMAIL_ADDRESS_PATTERN.search(user_message)
    return match.group() if match else None


def _extract_email_subject(
    user_message: str,
    intent: str,
) -> str:
    match = _EMAIL_SUBJECT_PATTERN.search(user_message)

    if match:
        return match.group(1).strip()

    return intent or "Message from your assistant"


def _extract_email_body(user_message: str) -> str:
    match = _EMAIL_ADDRESS_PATTERN.search(user_message)

    if not match:
        return user_message.strip()

    remainder = user_message[match.end():].strip()
    remainder = _EMAIL_BODY_CONNECTOR_PATTERN.sub(
        "",
        remainder,
    ).strip()

    return remainder or user_message.strip()


def _determine_tool_call(
    user_message: str,
    intent: str,
) -> tuple[str, dict[str, Any]]:
    """Determine which tool should execute the request."""

    message = user_message.lower()

    # -----------------------
    # Email
    # -----------------------

    if _looks_like_email_request(message):
        return (
            "email",
            {
                "to": _extract_email_address(user_message),
                "subject": _extract_email_subject(
                    user_message,
                    intent,
                ),
                "body": _extract_email_body(
                    user_message,
                ),
            },
        )

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
            "save note that", 
            "take a note that",
            "take a note",
            "create a note that",
            "create a note",
            "create note that",
            "create note",
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
                "title": content[:60],
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
        tool_input: dict[str, Any] = {
            "action": "update",
            "note_id": int(match.group(1)),
        }

        content = match.group(2).strip()

        if content:
            tool_input["content"] = content

        return "notes", tool_input

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
                "selected_tool": tool_name,
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
