"""Tests for EmailTool and EmailService.

EmailService falls back to a simulated send whenever SMTP credentials
aren't configured, which is exactly the state of a clean test environment
(no .env loaded) — so these tests never attempt a real network connection
unless a fake/real EmailService is explicitly wired in.
"""

import pytest

from app.agent.tools.email_tool import EmailTool
from app.core.exceptions import ExternalServiceError, GuardrailViolation
from app.services.email_service import EmailService


class _FakeEmailService:
    """Records calls in-memory instead of touching smtplib at all."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def send_email(self, to: str, subject: str, body: str) -> dict:
        self.calls.append({"to": to, "subject": subject, "body": body})
        if self.error is not None:
            raise self.error
        return {"sent": True, "simulated": False, "to": to, "subject": subject, "body": body,}


def test_email_tool_requires_approval_is_true():
    assert EmailTool.requires_approval is True


def test_email_tool_has_expected_name():
    assert EmailTool().name == "email"


def test_email_tool_sends_email_via_email_service():
    fake_service = _FakeEmailService()
    tool = EmailTool(email_service=fake_service)

    result = tool.run({"to": "john@example.com", "subject": "Meeting", "body": "3pm works for me."})

    assert result["observation"] == "email_sent"
    assert result["sent"] is True
    assert fake_service.calls == [
        {"to": "john@example.com", "subject": "Meeting", "body": "3pm works for me."}
    ]


def test_email_tool_uses_default_subject_when_missing():
    fake_service = _FakeEmailService()
    tool = EmailTool(email_service=fake_service)

    tool.run({"to": "john@example.com", "body": "Hello there"})

    assert fake_service.calls[0]["subject"] == "Message from your assistant"


def test_email_tool_raises_guardrail_violation_on_missing_recipient():
    tool = EmailTool(email_service=_FakeEmailService())
    with pytest.raises(GuardrailViolation):
        tool.run({"body": "Hello there"})


def test_email_tool_raises_guardrail_violation_on_blank_recipient():
    tool = EmailTool(email_service=_FakeEmailService())
    with pytest.raises(GuardrailViolation):
        tool.run({"to": "   ", "body": "Hello there"})


def test_email_tool_raises_guardrail_violation_on_blank_body():
    tool = EmailTool(email_service=_FakeEmailService())
    with pytest.raises(GuardrailViolation):
        tool.run({"to": "john@example.com", "body": "   "})


def test_email_tool_propagates_email_service_errors():
    fake_service = _FakeEmailService(error=ExternalServiceError("SMTP down"))
    tool = EmailTool(email_service=fake_service)

    with pytest.raises(ExternalServiceError):
        tool.run({"to": "john@example.com", "body": "Hello"})


def test_email_service_simulates_send_when_smtp_unconfigured():
    # A clean test environment has no SMTP credentials configured, so
    # EmailService must simulate rather than attempt a real connection.
    service = EmailService()

    result = service.send_email(to="john@example.com", subject="Hi", body="Test body")

    assert result["sent"] is True
    assert result["simulated"] is True
    assert result["to"] == "john@example.com"