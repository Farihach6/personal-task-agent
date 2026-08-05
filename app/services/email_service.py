"""Email sending service.

Thin wrapper around smtplib — the only module that imports it directly,
mirroring how GroqClient is the only module that imports the Groq SDK. If
SMTP credentials aren't configured, sends are simulated (logged, not
delivered) so the rest of the pipeline stays fully testable without a
real mailbox or network access.
"""

import smtplib
from email.mime.text import MIMEText
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.core.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """Sends plain-text emails via SMTP, or simulates sending if unconfigured."""

    def __init__(self) -> None:
        settings = get_settings()
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._user = settings.smtp_user
        self._password = settings.smtp_app_password

    def send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        """Send an email, or simulate the send if SMTP credentials are unset.

        Raises:
            ExternalServiceError: if a real SMTP send attempt fails.
        """
        if not self._user or not self._password:
            logger.info(
                "SMTP not configured; simulating email send to=%s subject=%r",
                to,
                subject,
            )
            return {
                "sent": True,
                "simulated": True,
                "to": to,
                "subject": subject,
                "body": body,
            }

        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = self._user
        message["To"] = to

        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.sendmail(self._user, [to], message.as_string())
        except Exception as exc:  # noqa: BLE001 - any SMTP/network failure
            logger.error("Failed to send email to=%s: %s", to, exc)
            raise ExternalServiceError(f"Failed to send email: {exc}") from exc

        logger.info("Email sent to=%s subject=%r", to, subject)

        return {
            "sent": True,
            "simulated": False,
            "to": to,
            "subject": subject,
            "body": body,
        }