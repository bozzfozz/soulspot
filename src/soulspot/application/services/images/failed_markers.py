# Hey future me - FAILED marker utilities for image processing!
#
# This module handles the FAILED|{reason}|{timestamp} format used in
# image_path and cover_path fields when an image download fails.
#
# The format allows us to:
# 1. Know WHY it failed (not_available, download_error, etc.)
# 2. Know WHEN it failed (for 24h retry logic)
# 3. Keep backward compatibility (still starts with FAILED)
#
# Used by:
# - ImageService.repair_artist_images()
# - ImageService.repair_album_images()
# - ImageWorker (background image downloads)
"""FAILED Marker utilities for image processing."""

from __future__ import annotations

from datetime import UTC, datetime


class FailedMarkerReason:
    """Standard failure reason codes.

    Hey future me - use these constants for consistency!
    They appear in the DB (image_path field) so don't change them.
    """

    DOWNLOAD_ERROR = "download_error"
    NOT_AVAILABLE = "not_available"  # Provider has no image
    INVALID_URL = "invalid_url"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    UNKNOWN = "unknown"


# Retry failed images after this many hours
FAILED_RETRY_HOURS = 24


def make_failed_marker(reason: str) -> str:
    """Create a FAILED marker with reason and timestamp.

    Hey future me - Format: FAILED|{reason}|{ISO timestamp}
    This allows us to:
    1. Know WHY it failed (not_available, download_error, etc.)
    2. Know WHEN it failed (for 24h retry logic)
    3. Keep backward compatibility (still starts with FAILED)

    Args:
        reason: One of the FailedMarkerReason constants

    Returns:
        Marker string like "FAILED|not_available|2025-01-15T10:30:00Z"
    """
    timestamp = datetime.now(UTC).isoformat()
    return f"FAILED|{reason}|{timestamp}"


def parse_failed_marker(marker: str | None) -> tuple[bool, str | None, datetime | None]:
    """Parse a FAILED marker to extract reason and timestamp.

    Args:
        marker: The image_path/cover_path value

    Returns:
        Tuple of (is_failed, reason, failed_at)
    """
    if not marker or not marker.startswith("FAILED"):
        return (False, None, None)

    parts = marker.split("|")
    if len(parts) >= 3:
        reason = parts[1]
        try:
            failed_at = datetime.fromisoformat(parts[2].replace("Z", "+00:00"))
        except ValueError:
            failed_at = None
        return (True, reason, failed_at)

    # Legacy format: just "FAILED"
    return (True, FailedMarkerReason.UNKNOWN, None)


def should_retry_failed(
    marker: str | None, retry_hours: int = FAILED_RETRY_HOURS
) -> bool:
    """Check if a FAILED marker is old enough to retry.

    Hey future me - we retry after retry_hours (default 24h).
    This gives CDN issues time to resolve, but doesn't give up permanently.

    Args:
        marker: The image_path/cover_path value
        retry_hours: Hours to wait before retrying (default: 24)

    Returns:
        True if we should retry this failed image
    """
    is_failed, _, failed_at = parse_failed_marker(marker)
    if not is_failed:
        return False

    if failed_at is None:
        # Legacy FAILED marker without timestamp - retry it
        return True

    # Check if enough time has passed
    hours_since_failure = (datetime.now(UTC) - failed_at).total_seconds() / 3600
    return hours_since_failure >= retry_hours


def classify_error(error_message: str) -> str:
    """Classify an error message into a failure reason code.

    Hey future me - this maps error messages to standardized reason codes.
    This helps UI show meaningful info and helps us track failure types.

    Args:
        error_message: The error message from download attempt

    Returns:
        One of the FailedMarkerReason constants
    """
    error_lower = error_message.lower()

    # Check for specific error patterns
    if "404" in error_lower or "not found" in error_lower:
        return FailedMarkerReason.NOT_AVAILABLE
    elif "timeout" in error_lower or "timed out" in error_lower:
        return FailedMarkerReason.TIMEOUT
    elif "invalid url" in error_lower or (
        "url" in error_lower and "invalid" in error_lower
    ):
        return FailedMarkerReason.INVALID_URL
    elif any(code in error_lower for code in ["500", "502", "503", "http"]):
        return FailedMarkerReason.HTTP_ERROR
    else:
        return FailedMarkerReason.DOWNLOAD_ERROR


def guess_provider_from_url(url: str) -> str:
    """Guess provider from CDN URL.

    Hey future me - simple heuristic to determine image source from URL.
    Used when we already have an image_url in DB and skip API calls.

    Args:
        url: CDN URL like "https://i.scdn.co/image/..." or "https://cdns-images.dzcdn.net/..."

    Returns:
        Provider name: "spotify", "deezer", "caa", "tidal", or "unknown"
    """
    url_lower = url.lower()
    if "scdn.co" in url_lower or "spotify" in url_lower:
        return "spotify"
    elif "dzcdn.net" in url_lower or "deezer" in url_lower:
        return "deezer"
    elif "coverartarchive" in url_lower or "musicbrainz" in url_lower:
        return "caa"
    elif "tidal" in url_lower:
        return "tidal"
    return "unknown"
