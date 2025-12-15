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
