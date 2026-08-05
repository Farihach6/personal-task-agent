"""Email tool.

Sending email is a sensitive action: `requires_approval = True` is read
generically by ToolExecutor/the Act node via getattr(), so no special-
casing is needed anywhere else in the pipeline — the graph's conditional
edge after Act pauses the workflow whenever a tool sets this flag.
"""

from typing import Any

from app.core.exceptions import GuardrailViolation
from app.services.email_service import EmailService


class EmailTool:
    """Sends an email via EmailService. Always requires human approval."""

    name = "email"
    requires_approval = True

    def __init__(self, email_service: EmailService | None = None) -> None:
        self._email_service = email_service or EmailService()

    def run(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Send the email described by tool_input.

        Raises:
            GuardrailViolation: if the recipient or body is missing/blank.
        """
        tool_input = tool_input or {}

        to = (tool_input.get("to") or "").strip()
        subject = (
            (tool_input.get("subject") or "").strip()
            or "Message from your assistant"
        )
        body = (tool_input.get("body") or "").strip()

        if not to:
            raise GuardrailViolation("An email recipient ('to') is required.")

        if not body:
            raise GuardrailViolation("Email body cannot be empty.")

        result = self._email_service.send_email(
            to=to,
            subject=subject,
            body=body,
        )

        return {
            "observation": "email_sent",
            "sent": result["sent"],
            "simulated": result["simulated"],
            "to": result["to"],
            "subject": result["subject"],
            "body": result["body"],
        }