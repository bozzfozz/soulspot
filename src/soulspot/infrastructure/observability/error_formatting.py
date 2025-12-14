"""Enhanced error formatting for better logging readability.

This module provides utilities for creating human-readable error messages,
especially for filesystem-related errors that are common in Docker environments.
"""

import errno
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Hey future me - THIS IS THE MAGIC! Maps errno codes to user-friendly messages with HINTS!
# Users see "Read-only filesystem (Errno 30)" not just "OSError 30" - way more helpful!
# The hints tell users WHAT TO DO - check Docker volumes, permissions, disk space, etc.
# Add more errno mappings as needed when users report confusing errors.
ERRNO_MESSAGES = {
    errno.EACCES: (
        "Permission denied",
        "Check file permissions and PUID/PGID in Docker. "
        "Run: ls -la <path> to see permissions.",
    ),
    errno.EROFS: (
        "Read-only filesystem",
        "Docker volume might be mounted read-only. "
        "Check docker-compose.yml for ':ro' flags. "
        "Run: mount | grep <path> to check mount options.",
    ),
    errno.ENOSPC: (
        "No space left on device",
        "Disk is full! Check available space with 'df -h'. "
        "Clean up old files or increase disk size.",
    ),
    errno.ENOENT: (
        "File or directory not found",
        "Path does not exist. Check if parent directories are created. "
        "Verify Docker volume mounts in docker-compose.yml.",
    ),
    errno.EEXIST: (
        "File or directory already exists",
        "Target path already exists. Check for duplicate operations or race conditions.",
    ),
    errno.EISDIR: (
        "Is a directory",
        "Tried to operate on directory as file. Check path resolution logic.",
    ),
    errno.ENOTDIR: (
        "Not a directory",
        "Tried to operate on file as directory. Check path resolution logic.",
    ),
    errno.EXDEV: (
        "Cross-device link not permitted",
        "Cannot move files across different filesystems. "
        "App will automatically use copy+delete fallback.",
    ),
    errno.EMFILE: (
        "Too many open files",
        "Process has too many files open. Increase ulimit or fix file handle leaks.",
    ),
    errno.EBUSY: (
        "Device or resource busy",
        "File is locked by another process. Check for concurrent access.",
    ),
}


def format_oserror_message(
    e: OSError,
    operation: str,
    path: Path | str | None = None,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """Format OSError with human-readable explanation and hints.

    Hey future me - USE THIS EVERYWHERE instead of just logging str(e)!
    It transforms cryptic "[Errno 30]" into actionable messages users can understand.

    Example WITHOUT this function:
        ERROR │ Failed to save: [Errno 30] Read-only file system

    Example WITH this function:
        ERROR │ Failed to save '/music/track.mp3': Read-only filesystem (Errno 30)
        ℹ️  HINT: Docker volume might be mounted read-only. Check docker-compose.yml for ':ro' flags.

    Args:
        e: The OSError exception
        operation: What was being attempted (e.g., "save file", "move track", "create directory")
        path: The file/directory path involved (optional but recommended)
        extra_context: Additional context to include in message (optional)

    Returns:
        Formatted error message with errno, description, and actionable hints

    Example:
        try:
            file_path.write_bytes(data)
        except OSError as e:
            msg = format_oserror_message(e, "save image", file_path, {"size": len(data)})
            logger.error(msg, exc_info=True)
    """
    # Get errno code and lookup friendly message
    error_code = e.errno
    error_name = errno.errorcode.get(error_code, f"UNKNOWN_{error_code}")

    # Get friendly description and hint from our mapping
    if error_code in ERRNO_MESSAGES:
        description, hint = ERRNO_MESSAGES[error_code]
    else:
        # Fallback for unmapped errors
        description = str(e)
        hint = "Check system logs and file permissions."

    # Build base message
    parts = [f"Failed to {operation}"]

    # Add path if provided
    if path:
        parts.append(f"'{path}'")

    # Add errno info
    parts.append(f": {description} (Errno {error_code} / {error_name})")

    base_message = " ".join(parts)

    # Add extra context if provided
    if extra_context:
        context_str = ", ".join(f"{k}={v}" for k, v in extra_context.items())
        base_message += f" [{context_str}]"

    # Add hint on new line
    full_message = f"{base_message}\nℹ️  HINT: {hint}"

    return full_message


def format_permission_error_message(
    e: PermissionError,
    operation: str,
    path: Path | str | None = None,
) -> str:
    """Format PermissionError with Docker-specific hints.

    Hey future me - PermissionErrors in Docker usually mean PUID/PGID mismatch!
    This adds Docker-specific troubleshooting steps automatically.

    Example output:
        Failed to write '/config/settings.json': Permission denied (Errno 13 / EACCES)
        ℹ️  HINT: Check PUID/PGID settings in Docker. File owner might not match container user.
        🐳 Docker Fix: Set PUID=1000 PGID=1000 in docker-compose.yml or .env file

    Args:
        e: The PermissionError exception
        operation: What was being attempted
        path: The file/directory path involved

    Returns:
        Formatted error message with Docker-specific hints
    """
    base_msg = format_oserror_message(e, operation, path)

    # Add Docker-specific hint
    docker_hint = (
        "\n🐳 Docker Fix: "
        "Set PUID=$(id -u) PGID=$(id -g) in docker-compose.yml. "
        "Run: docker compose exec soulspot ls -la <path> to check ownership."
    )

    return base_msg + docker_hint


def log_filesystem_operation(
    operation: str,
    path: Path | str,
    success: bool = True,
    error: Exception | None = None,
    **kwargs: Any,
) -> None:
    """Log filesystem operation with consistent formatting.

    Hey future me - use this for ANY filesystem op (read, write, move, delete)!
    It ensures all fs operations are logged the same way with proper context.

    Args:
        operation: Operation type ("read", "write", "move", "delete", etc.)
        path: The file/directory path
        success: Whether operation succeeded
        error: Exception if operation failed
        **kwargs: Additional context (size, destination, etc.)
    """
    context_str = " ".join(f"{k}={v}" for k, v in kwargs.items())

    if success:
        logger.debug(
            f"Filesystem {operation} succeeded: {path}" + (f" [{context_str}]" if context_str else "")
        )
    else:
        if isinstance(error, (OSError, PermissionError)):
            if isinstance(error, PermissionError):
                msg = format_permission_error_message(error, operation, path)
            else:
                msg = format_oserror_message(error, operation, path, kwargs)
            logger.error(msg, exc_info=True)
        else:
            logger.error(
                f"Filesystem {operation} failed: {path}" + (f" [{context_str}]" if context_str else ""),
                exc_info=True,
            )


# Hey future me - EXAMPLE USAGE patterns below. Copy-paste these into your code!
# They show best practices for different filesystem operations.

# Example 1: File Write
# try:
#     file_path.write_bytes(data)
#     log_filesystem_operation("write", file_path, size=len(data))
# except OSError as e:
#     log_filesystem_operation("write", file_path, success=False, error=e, size=len(data))
#     raise

# Example 2: File Move
# try:
#     shutil.move(source, dest)
#     log_filesystem_operation("move", source, destination=dest)
# except OSError as e:
#     msg = format_oserror_message(e, "move file", source, {"destination": str(dest)})
#     logger.error(msg, exc_info=True)
#     raise

# Example 3: Directory Creation
# try:
#     directory.mkdir(parents=True, exist_ok=True)
#     log_filesystem_operation("create directory", directory)
# except PermissionError as e:
#     msg = format_permission_error_message(e, "create directory", directory)
#     logger.error(msg, exc_info=True)
#     raise
