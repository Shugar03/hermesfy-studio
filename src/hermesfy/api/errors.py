"""Error envelope and typed exceptions for the Hermesfy V5 API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    """Standard error envelope returned by every API endpoint on failure."""

    error: str = Field(..., description="Machine-readable error code, e.g. NOT_FOUND")
    message: str = Field(..., description="Human-readable description")
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Optional structured details (field errors, hints, etc.)"
    )


# ── Base app exception ───────────────────────────────────────────────────────


class AppError(Exception):
    """Base class for all API-layer exceptions.

    Attributes:
        status_code: HTTP status code to return.
        code: Machine-readable error code.
        message: Human-readable message.
        details: Optional additional data.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str = "Internal server error",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.details = details
        super().__init__(message)

    def to_envelope(self) -> ErrorEnvelope:
        return ErrorEnvelope(error=self.code, message=self.message, details=self.details)


# ── Specific exceptions ──────────────────────────────────────────────────────


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"

    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(message=f"{entity} '{entity_id}' not found")


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, details=details)


class VersionConflictError(ConflictError):
    code = "VERSION_CONFLICT"

    def __init__(self, expected_version: int, actual_version: int) -> None:
        super().__init__(
            message=f"Version conflict: expected {expected_version}, actual {actual_version}",
            details={"expected_version": expected_version, "actual_version": actual_version},
        )


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, details=details)


class AuthError(AppError):
    status_code = 401
    code = "AUTH_ERROR"

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message=message)


class HermesError(AppError):
    status_code = 502
    code = "HERMES_ERROR"

    def __init__(self, message: str = "Hermes agent subprocess failed") -> None:
        super().__init__(message=message)
