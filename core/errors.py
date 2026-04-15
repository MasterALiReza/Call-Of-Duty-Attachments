"""Application error taxonomy for predictable user-facing and infrastructure failures."""

from __future__ import annotations


class AppError(Exception):
    """Base class for controlled application errors."""


class UserFacingError(AppError):
    """An error safe to surface to end users after localization/wrapping."""


class PermissionDeniedError(UserFacingError):
    """The actor is authenticated but not authorized for the requested action."""


class ValidationError(UserFacingError):
    """The input or requested operation is invalid."""


class NotFoundError(UserFacingError):
    """A requested resource does not exist."""


class ConflictError(UserFacingError):
    """The operation conflicts with current state."""


class InfrastructureError(AppError):
    """Unexpected internal failure while serving the request."""


class ExternalDependencyError(InfrastructureError):
    """A required external system failed or was unreachable."""


class TransientError(InfrastructureError):
    """A temporary failure that may succeed on retry."""
