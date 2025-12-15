"""Custom exceptions for SoulSpot domain layer.

Hey future me - these exceptions provide clear error semantics across the application!

Usage Pattern:
- EntityNotFoundError → Convert to HTTP 404 in routes
- InvalidOperationError → Convert to HTTP 400 in routes
- OperationFailedError → Convert to HTTP 500 in routes

All services should raise these instead of generic ValueError/Exception.
"""


class EntityNotFoundError(Exception):
    """Entity not found in database.

    Raised when a requested entity (track, artist, album, playlist, etc.)
    does not exist.

    Example:
        raise EntityNotFoundError(f"Playlist {playlist_id} not found")
    """

    pass


class InvalidOperationError(Exception):
    """Operation cannot be performed due to invalid state or parameters.

    Raised when an operation is logically invalid (e.g., applying an
    already-processed candidate, resolving with invalid action).

    Example:
        raise InvalidOperationError("Candidate already processed")
    """

    pass


class OperationFailedError(Exception):
    """Operation failed due to external dependency or system error.

    Raised when an operation fails due to file system errors, network
    errors, or other external factors.

    Example:
        raise OperationFailedError(f"Failed to delete file: {e}")
    """

    pass
