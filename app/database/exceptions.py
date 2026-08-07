"""Database-specific exceptions."""

from app.core.exceptions import AppException


class DatabaseOperationError(AppException):
    """Raised when a database operation fails."""

    status_code = 500
    error_code = "database_operation_error"

    def __init__(self, message: str = "Database operation failed") -> None:
        super().__init__(message)


class RecordNotFoundError(DatabaseOperationError):
    """Raised when a requested database record does not exist."""

    status_code = 404
    error_code = "not_found"

    def __init__(self, message: str = "Record not found") -> None:
        super().__init__(message)


class IntegrityConstraintError(DatabaseOperationError):
    """Raised when a database integrity constraint is violated."""

    status_code = 409
    error_code = "integrity_constraint_error"

    def __init__(
        self,
        message: str = "Database integrity constraint violated",
    ) -> None:
        super().__init__(message)