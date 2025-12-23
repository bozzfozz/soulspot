"""Domain exceptions."""

from typing import Any


class DomainException(Exception):
    """Base exception for all domain exceptions."""

    # Hey future me, we store message as an attribute so code can inspect it without parsing str(exception).
    # The *args lets subclasses pass extra context. This is your base class - DON'T raise it directly!
    # Always use a specific subclass (EntityNotFound, Validation, etc) so callers can catch precisely.
    def __init__(self, message: str, *args: Any) -> None:
        super().__init__(message, *args)
        self.message = message


class EntityNotFoundException(DomainException):
    """Raised when an entity is not found."""

    # Yo, this is for "get by ID" operations that fail - Track 123 doesn't exist, Playlist "abc" not found.
    # We store entity_type and entity_id separately so error handlers can log them structured (not just
    # string parsing). Use this instead of returning None when "not found" is truly exceptional! If you
    # expect missing entities often, use Optional return type instead of exceptions (exceptions are slow!).
    def __init__(self, entity_type: str, entity_id: Any) -> None:
        super().__init__(f"{entity_type} with id {entity_id} not found")
        self.entity_type = entity_type
        self.entity_id = entity_id


class ValidationException(DomainException):
    """Raised when entity validation fails.

    Used to signal that an entity's invariants or business rules
    have been violated (e.g., invalid email format, negative price).
    """

    pass


class InvalidStateException(DomainException):
    """Raised when an entity is in an invalid state for the requested operation.

    Example: Attempting to cancel a download that's already completed,
    or trying to publish a draft that hasn't been reviewed.
    """

    pass


class DuplicateEntityException(DomainException):
    """Raised when trying to create a duplicate entity."""

    # Listen, this is for uniqueness violations - trying to create a Watchlist for an artist that already
    # has one, importing a track with duplicate Spotify ID, etc. DON'T use this for DB unique constraint
    # violations (that's infrastructure layer)! This is domain logic - "business rule says this must be unique".
    # Callers should catch this and show user-friendly "already exists" message, not 500 error!
    def __init__(self, entity_type: str, entity_id: Any) -> None:
        super().__init__(f"{entity_type} with id {entity_id} already exists")
        self.entity_type = entity_type
        self.entity_id = entity_id


class TokenRefreshException(DomainException):
    """Raised when token refresh fails and re-authentication is required.

    Hey future me - this exception is thrown when Spotify's refresh token is no longer valid.
    Common causes:
    - User revoked app access in Spotify settings
    - Refresh token expired (usually doesn't happen with Spotify, but possible)
    - App credentials changed
    - Spotify flagged the token as suspicious

    When this is caught, the UI should show a warning banner prompting user to re-authenticate.
    Background workers should skip work gracefully (no crash loop!).
    """

    def __init__(
        self,
        message: str = "Token refresh failed. Please re-authenticate with Spotify.",
        error_code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code  # e.g., "invalid_grant"
        self.http_status = http_status  # e.g., 400, 401

    @property
    def requires_reauth(self) -> bool:
        """Check if error requires user re-authentication."""
        # Hey - 400 with invalid_grant means refresh token is dead
        # 401/403 mean access denied (user revoked, etc.)
        return self.error_code == "invalid_grant" or self.http_status in (400, 401, 403)


# =============================================================================
# DEPRECATED ALIASES (Dec 2025)
# Hey future me - these are for backward compatibility with old exception names!
# The codebase used to have domain/exceptions.py with these names.
# Now we have domain/exceptions/__init__.py with better naming conventions.
# TODO: Migrate all code to use new names and remove these aliases!
# =============================================================================

EntityNotFoundError = EntityNotFoundException
InvalidOperationError = InvalidStateException


class OperationFailedError(DomainException):
    """Operation failed due to external dependency or system error.

    DEPRECATED: Use DomainException or a more specific exception instead.
    This is kept for backward compatibility with old code.

    Raised when an operation fails due to file system errors, network
    errors, or other external factors.
    """

    pass


# =============================================================================
# New Exception Classes (Dec 2025)
# These provide more specific error semantics with clear HTTP status mappings.
# =============================================================================


class BusinessRuleViolation(DomainException):
    """A business rule was violated.

    Raised when an operation violates business logic constraints
    (e.g., duplicate names, invalid state transitions, conflicting operations).

    HTTP Status: 400

    Example:
        raise BusinessRuleViolation("Cannot merge artist with itself")
        raise BusinessRuleViolation("keep_id cannot be in merge_ids")
    """

    pass


class ValidationError(DomainException):
    """Input validation failed.

    Raised when input data fails validation rules (missing fields,
    invalid formats, out-of-range values).

    HTTP Status: 422

    Example:
        raise ValidationError("Invalid Spotify artist DTO: missing spotify_id")
        raise ValidationError("Invalid quality profile: high-quality")
    """

    pass


class ConfigurationError(DomainException):
    """Application misconfiguration.

    Raised when required configuration is missing or invalid.

    HTTP Status: 503 (Service Unavailable)

    Example:
        raise ConfigurationError("Spotify credentials not configured")
        raise ConfigurationError("session_scope not provided")
    """

    pass


class AuthenticationError(DomainException):
    """User is not authenticated or token expired.

    Raised when authentication is required but not provided or invalid.

    HTTP Status: 401

    Example:
        raise AuthenticationError("No token found for user")
        raise AuthenticationError("Token expired - please re-authenticate")
    """

    pass


class AuthorizationError(DomainException):
    """User is authenticated but not authorized for this action.

    Raised when user lacks permissions for the requested operation.

    HTTP Status: 403

    Example:
        raise AuthorizationError("File path is not in allowed directories")
    """

    pass


class ExternalServiceError(DomainException):
    """External service (Spotify, Deezer, etc.) returned an error.

    Raised when an external API call fails.

    HTTP Status: 502 (Bad Gateway)

    Example:
        raise ExternalServiceError("Spotify API error: 503 Service Unavailable")
    """

    pass


class RateLimitExceededError(DomainException):
    """External service rate limit was exceeded.

    Raised when an API returns 429 Too Many Requests.

    HTTP Status: 429

    Example:
        raise RateLimitExceededError("Spotify rate limit exceeded - retry after 30s")
    """

    pass


class DuplicateEntityError(DuplicateEntityException):
    """Alias for DuplicateEntityException with standardized naming.

    HTTP Status: 409 (Conflict)
    """

    pass


class PluginError(DomainException):
    """Plugin operation failed.

    Raised when a plugin (Spotify, Deezer, etc.) fails to perform an operation.

    HTTP Status: 500

    Example:
        raise PluginError("Spotify plugin failed to authenticate")
    """

    pass


# =============================================================================
# Public API - All exceptions that can be imported
# =============================================================================
__all__ = [
    # Base
    "DomainException",
    # Entity exceptions
    "EntityNotFoundException",
    "EntityNotFoundError",  # Alias
    "DuplicateEntityException",
    "DuplicateEntityError",  # Alias
    # Validation exceptions
    "ValidationException",
    "ValidationError",
    # State exceptions
    "InvalidStateException",
    "InvalidOperationError",  # Alias (deprecated)
    # Business logic
    "BusinessRuleViolation",
    # External service exceptions
    "ExternalServiceError",
    "RateLimitExceededError",
    # Auth exceptions
    "AuthenticationError",
    "AuthorizationError",
    "TokenRefreshException",
    # Configuration
    "ConfigurationError",
    # Generic
    "OperationFailedError",  # Deprecated
    "PluginError",
]
