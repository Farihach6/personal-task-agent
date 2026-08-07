"""Plan node: turns the identified intent into an ordered list of steps,
and determines which tool (search, notes, or email) the Act node should
execute and with what input.
"""

import re
from typing import Any

from app.agent.prompts import PLAN_PROMPT_TEMPLATE
from app.agent.state import AgentState
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient
from app.services.logging_service import LoggingService
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


# ----------------------------------------------------------------------
# Email routing
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Notes routing
# ----------------------------------------------------------------------

_NOTES_DELETE_PHRASES = (
    "delete note",
    "remove note",
    "delete the note",
    "remove the note",
)

_NOTES_UPDATE_PHRASES = (
    "update note",
    "edit note",
    "update the note",
    "edit the note",
    "change note",
)

_NOTES_LIST_PHRASES = (
    "show all my notes",
    "show my notes",
    "show notes",
    "list notes",
    "list my notes",
    "what notes do i have",
    "what are my notes",
    "display notes",
    "display my notes",
)

_NOTES_GET_PHRASES = (
    "get note",
    "find note",
    "read note",
    "show note",
)

_NOTES_CREATE_PHRASES = (
    "save a note",
    "save note",
    "create a note",
    "create note",
    "remember this",
    "remember that",
    "take a note",
    "note that",
    "note down",
    "make a note",
)

_NOTES_CREATE_STRIP_PHRASES = (
    "save a note that",
    "save a note",
    "save note that",
    "save note",
    "create a note that",
    "create a note",
    "create note that",
    "create note",
    "remember that",
    "remember this",
    "take a note that",
    "take a note",
    "make a note that",
    "make a note",
    "note down that",
    "note down",
    "note that",
)

_UPDATE_CONNECTOR_PATTERN = re.compile(
    r"^(to say|to|that|:|-)\s*",
    re.IGNORECASE,
)


def _extract_note_id(text: str) -> int | None:
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _extract_create_content(user_message: str) -> str:
    lowered = user_message.strip().lower()

    for phrase in _NOTES_CREATE_STRIP_PHRASES:
        if lowered.startswith(phrase):
            remainder = user_message.strip()[len(phrase):].strip(" :,-")

            if remainder:
                return remainder

    return user_message.strip()


def _extract_update_content(user_message: str) -> str | None:
    match = re.search(r"\d+", user_message)

    if not match:
        return None

    remainder = user_message[match.end():].strip()
    remainder = _UPDATE_CONNECTOR_PATTERN.sub(
        "",
        remainder,
    ).strip()

    return remainder or None


def _determine_tool_call(
    user_message: str,
    intent: str,
) -> tuple[str, dict[str, Any]]:
    """Determine which tool should execute the request."""

    message = user_message.lower()

    if _looks_like_email_request(message):
        return (
            "email",
            {
                "to": _extract_email_address(user_message),
                "subject": _extract_email_subject(
                    user_message,
                    intent,
                ),
                "body": _extract_email_body(user_message),
            },
        )

    if any(phrase in message for phrase in _NOTES_DELETE_PHRASES):
        return (
            "notes",
            {
                "action": "delete",
                "note_id": _extract_note_id(message),
            },
        )

    if any(phrase in message for phrase in _NOTES_UPDATE_PHRASES):
        tool_input: dict[str, Any] = {
            "action": "update",
            "note_id": _extract_note_id(message),
        }

        content = _extract_update_content(user_message)

        if content:
            tool_input["content"] = content

        return "notes", tool_input

    if any(phrase in message for phrase in _NOTES_LIST_PHRASES):
        return "notes", {"action": "list"}

    if any(phrase in message for phrase in _NOTES_GET_PHRASES):
        return (
            "notes",
            {
                "action": "get",
                "note_id": _extract_note_id(message),
            },
        )

    if any(phrase in message for phrase in _NOTES_CREATE_PHRASES):
        content = _extract_create_content(user_message)

        return (
            "notes",
            {
                "action": "create",
                "content": content,
                "title": content[:60],
            },
        )

    return (
        "search",
        {
            "query": intent or user_message,
        },
    )
def build_plan_node(
    llm_client: GroqClient,
    logging_service: LoggingService | None = None,
):
    """Create a Plan node bound to the provided LLM client."""

    def plan_node(state: AgentState) -> AgentState:
        workflow_id = state["workflow_id"]

        logger.info(
            "Plan node started for workflow_id=%s",
            workflow_id,
        )

        if logging_service is not None:
            logging_service.log_event(
                message="Plan node started.",
                level="INFO",
                workflow_id=workflow_id,
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

            # Continue to the Act node
            state["current_step"] = "ACT"

            state["metadata"] = {
                **state["metadata"],
                "plan_raw_response": raw_response,
                "selected_tool": tool_name,
            }

            logger.info(
                "Plan node completed successfully with %d steps. Selected tool=%s",
                len(plan),
                tool_name,
            )

            if logging_service is not None:
                logging_service.log_event(
                    message=(
                        f"Plan node completed: generated {len(plan)} step(s); "
                        f"selected tool '{tool_name}'."
                    ),
                    level="INFO",
                    workflow_id=workflow_id,
                )

            return state

        except Exception as exc:
            logger.exception("Plan node failed.")

            if logging_service is not None:
                logging_service.log_event(
                    message=f"Plan node failed: {exc}",
                    level="ERROR",
                    workflow_id=workflow_id,
                )

            state["status"] = "FAILED"

            state["metadata"] = {
                **state["metadata"],
                "plan_error": str(exc),
            }

            # Re-raise so AgentService can finalize workflow as FAILED
            raise

    return plan_node