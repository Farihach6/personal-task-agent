"""Custom exception hierarchy and global FastAPI exception handlers.

Keeping exceptions typed (rather than raising bare Exception / string checks)
lets every layer branch on error type instead of parsing messages.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logger import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    """Base class for all application-specific exceptions."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class GuardrailViolation(AppException):
    """Raised when a request or action violates a safety guardrail."""

    status_code = 400
    error_code = "guardrail_violation"


class ToolExecutionError(AppException):
    """Raised when a tool fails during execution."""

    status_code = 502
    error_code = "tool_execution_error"


class ApprovalRequiredError(AppException):
    """Raised/used to signal that a workflow is paused pending human approval."""

    status_code = 202
    error_code = "approval_required"


class AgentMaxStepsExceeded(AppException):
    """Raised when the agent exceeds the configured maximum step count."""

    status_code = 400
    error_code = "max_steps_exceeded"


class ExternalServiceError(AppException):
    """Raised when an external dependency (Groq, SMTP, ...) fails."""

    status_code = 502
    error_code = "external_service_error"


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    status_code = 404
    error_code = "not_found"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.error("AppException: %s | path=%s", exc.message, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error_code": "internal_error", "message": "An unexpected error occurred."},
        )
