"""Download Error Codes - standardized error classification.

Hey future me - this module standardizes HOW we classify download failures!

The problem: Different parts of the code use different error strings ("file not found",
"File Not Found", "FILE_NOT_FOUND"). Inconsistent error handling leads to:
- Retrying non-retryable errors (wasting time)
- Not retrying transient errors (missing successful downloads)
- Confusing error messages for users

The solution: A canonical set of error codes with:
1. Clear categorization (retryable vs non-retryable)
2. Human-readable descriptions
3. Helper functions for classification

ERROR CATEGORIES:

NON-RETRYABLE (permanent failures - don't waste time retrying):
- FILE_NOT_FOUND: The file doesn't exist on Soulseek network
- USER_BLOCKED: We're blocked by the sharing user
- INVALID_FILE: Downloaded file is corrupted/invalid
- FILE_TOO_SMALL: File smaller than minimum threshold (likely corrupt)

RETRYABLE (transient issues - try again later):
- TIMEOUT: Connection timed out (user might be back online later)
- USER_OFFLINE: User went offline during download
- TRANSFER_FAILED: Transfer error (network glitch, user disconnected)
- QUEUE_TIMEOUT: Waited too long in user's queue
- CONNECTION_ERROR: Couldn't connect (server issue, network)
- RATE_LIMITED: Too many requests (backoff and retry)
- SLSKD_UNAVAILABLE: slskd service is down (will come back)
- UNKNOWN: Unexpected error (retry in case it's transient)

USAGE:
    from soulspot.domain.entities.error_codes import (
        DownloadErrorCode,
        is_retryable_error,
        get_error_description,
    )

    # In download worker:
    error_code = DownloadErrorCode.TIMEOUT

    # In retry scheduler:
    if is_retryable_error(download.last_error_code):
        download.schedule_retry()
"""

from enum import StrEnum


class DownloadErrorCode(StrEnum):
    """Standardized error codes for download failures.

    Hey future me - StrEnum means values ARE strings!
    So DownloadErrorCode.TIMEOUT == "timeout" (True)
    This makes DB storage and comparison easy.
    """

    # Non-retryable errors (permanent failures)
    FILE_NOT_FOUND = "file_not_found"
    USER_BLOCKED = "user_blocked"
    INVALID_FILE = "invalid_file"
    FILE_TOO_SMALL = "file_too_small"

    # Retryable errors (transient failures)
    TIMEOUT = "timeout"
    USER_OFFLINE = "user_offline"
    TRANSFER_FAILED = "transfer_failed"
    QUEUE_TIMEOUT = "queue_timeout"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMITED = "rate_limited"
    SLSKD_UNAVAILABLE = "slskd_unavailable"
    UNKNOWN = "unknown"


# Hey future me - this set MUST match _NON_RETRYABLE_ERRORS in Download entity!
# If you add a new non-retryable error here, add it there too!
NON_RETRYABLE_ERRORS: frozenset[str] = frozenset(
    {
        DownloadErrorCode.FILE_NOT_FOUND,
        DownloadErrorCode.USER_BLOCKED,
        DownloadErrorCode.INVALID_FILE,
        DownloadErrorCode.FILE_TOO_SMALL,
    }
)

RETRYABLE_ERRORS: frozenset[str] = frozenset(
    {
        DownloadErrorCode.TIMEOUT,
        DownloadErrorCode.USER_OFFLINE,
        DownloadErrorCode.TRANSFER_FAILED,
        DownloadErrorCode.QUEUE_TIMEOUT,
        DownloadErrorCode.CONNECTION_ERROR,
        DownloadErrorCode.RATE_LIMITED,
        DownloadErrorCode.SLSKD_UNAVAILABLE,
        DownloadErrorCode.UNKNOWN,
    }
)

# Human-readable descriptions for error codes
ERROR_DESCRIPTIONS: dict[str, str] = {
    DownloadErrorCode.FILE_NOT_FOUND: "File not found on Soulseek network",
    DownloadErrorCode.USER_BLOCKED: "Blocked by the sharing user",
    DownloadErrorCode.INVALID_FILE: "Downloaded file is corrupted or invalid",
    DownloadErrorCode.FILE_TOO_SMALL: "File smaller than minimum size threshold",
    DownloadErrorCode.TIMEOUT: "Connection timed out",
    DownloadErrorCode.USER_OFFLINE: "User went offline during download",
    DownloadErrorCode.TRANSFER_FAILED: "Transfer failed (network error)",
    DownloadErrorCode.QUEUE_TIMEOUT: "Waited too long in download queue",
    DownloadErrorCode.CONNECTION_ERROR: "Could not connect to user",
    DownloadErrorCode.RATE_LIMITED: "Too many requests (rate limited)",
    DownloadErrorCode.SLSKD_UNAVAILABLE: "slskd service is unavailable",
    DownloadErrorCode.UNKNOWN: "Unknown error occurred",
}


def is_retryable_error(error_code: str | None) -> bool:
    """Check if an error code is retryable.

    Hey future me - None means "no error recorded" which is weird but could happen
    if status was set to FAILED without an error code. We treat it as retryable
    since we don't know what went wrong.

    Args:
        error_code: The error code to check (string or None)

    Returns:
        True if the error is retryable, False if non-retryable
    """
    if error_code is None:
        return True  # Unknown error, try again

    return error_code not in NON_RETRYABLE_ERRORS


def is_non_retryable_error(error_code: str | None) -> bool:
    """Check if an error code is non-retryable (permanent failure).

    Args:
        error_code: The error code to check

    Returns:
        True if the error is non-retryable (permanent), False otherwise
    """
    if error_code is None:
        return False

    return error_code in NON_RETRYABLE_ERRORS


def get_error_description(error_code: str | None) -> str:
    """Get human-readable description for an error code.

    Args:
        error_code: The error code to describe

    Returns:
        Human-readable error description
    """
    if error_code is None:
        return "No error information available"

    return ERROR_DESCRIPTIONS.get(error_code, f"Unknown error: {error_code}")


def normalize_error_code(raw_error: str | None) -> str:
    """Normalize various error messages to standard error codes.

    Hey future me - slskd returns various error strings that we need to map
    to our standard codes. This handles common variations.

    Args:
        raw_error: Raw error string from slskd or other source

    Returns:
        Normalized DownloadErrorCode value (as string)
    """
    if raw_error is None:
        return DownloadErrorCode.UNKNOWN

    # Normalize to lowercase for comparison
    error_lower = raw_error.lower()

    # Map common error patterns to codes
    if any(x in error_lower for x in ["file not found", "not found", "does not exist"]):
        return DownloadErrorCode.FILE_NOT_FOUND

    if any(x in error_lower for x in ["blocked", "banned", "denied"]):
        return DownloadErrorCode.USER_BLOCKED

    if any(x in error_lower for x in ["corrupt", "invalid", "bad file", "malformed"]):
        return DownloadErrorCode.INVALID_FILE

    if any(x in error_lower for x in ["too small", "zero bytes", "empty file"]):
        return DownloadErrorCode.FILE_TOO_SMALL

    if any(x in error_lower for x in ["timeout", "timed out"]):
        return DownloadErrorCode.TIMEOUT

    if any(x in error_lower for x in ["offline", "not online", "unavailable"]):
        return DownloadErrorCode.USER_OFFLINE

    if any(x in error_lower for x in ["transfer failed", "transfer error", "aborted"]):
        return DownloadErrorCode.TRANSFER_FAILED

    if any(x in error_lower for x in ["queue", "queued too long"]):
        return DownloadErrorCode.QUEUE_TIMEOUT

    if any(x in error_lower for x in ["connection", "connect", "network"]):
        return DownloadErrorCode.CONNECTION_ERROR

    if any(x in error_lower for x in ["rate limit", "too many"]):
        return DownloadErrorCode.RATE_LIMITED

    if any(x in error_lower for x in ["slskd", "service unavailable", "503"]):
        return DownloadErrorCode.SLSKD_UNAVAILABLE

    # Default to unknown
    return DownloadErrorCode.UNKNOWN
