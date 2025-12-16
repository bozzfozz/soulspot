"""Path validation utilities to prevent path traversal attacks.

This module provides utilities to safely validate file paths and prevent
malicious path traversal attempts (e.g., ../../etc/passwd).
"""

import logging
from pathlib import Path

from soulspot.domain.exceptions import AuthorizationError, ValidationError

logger = logging.getLogger(__name__)

# Allowed file extensions for audio files
ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".ogg",
    ".opus",
    ".wav",
    ".aac",
    ".wma",
}

# Allowed file extensions for images
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
}


class PathValidator:
    """Validator for safe file path operations.

    This class provides methods to validate that file paths are safe
    and within expected directories, preventing path traversal attacks.
    """

    # Hey future me, this is THE SECURITY GATEKEEPER for path traversal attacks! Someone tries
    # "../../etc/passwd" and this catches it. resolve=True (default) converts symlinks and relative
    # paths to absolute which is CRITICAL - without it, "../" tricks still work! The is_relative_to
    # check ensures resolved path is actually INSIDE base_dir. If path is /tmp/evil and base is
    # /mnt/music, this raises ValueError. The try/except for AttributeError handles Python <3.9
    # (is_relative_to added in 3.9). We log WARNING on attacks so you can spot malicious users!
    @staticmethod
    def validate_path_within_base(
        path: Path | str, base_dir: Path | str, *, resolve: bool = True
    ) -> Path:
        """Validate that a path is within a base directory.

        Args:
            path: The path to validate
            base_dir: The base directory that path must be within
            resolve: Whether to resolve symlinks and relative paths (default: True)

        Returns:
            The validated path as a Path object

        Raises:
            AuthorizationError: If the path is outside the base directory or invalid
        """
        # Convert to Path objects
        path_obj = Path(path)
        base_dir_obj = Path(base_dir)

        # Resolve to absolute paths if requested
        if resolve:
            try:
                path_obj = path_obj.resolve()
                base_dir_obj = base_dir_obj.resolve()
            except (OSError, RuntimeError) as e:
                logger.warning("Failed to resolve path %s: %s", path, e)
                raise AuthorizationError(f"Invalid path: {path}") from e

        # Check if path is within base directory
        try:
            # is_relative_to is available in Python 3.9+
            if not path_obj.is_relative_to(base_dir_obj):
                logger.warning(
                    "Path traversal attempt detected: %s is not within %s",
                    path_obj,
                    base_dir_obj,
                )
                raise AuthorizationError(
                    f"Path {path_obj} is outside allowed directory {base_dir_obj}"
                )
        except AttributeError:
            # Fallback for older Python versions
            try:
                path_obj.relative_to(base_dir_obj)
            except ValueError as e:
                logger.warning(
                    "Path traversal attempt detected: %s is not within %s",
                    path_obj,
                    base_dir_obj,
                )
                raise AuthorizationError(
                    f"Path {path_obj} is outside allowed directory {base_dir_obj}"
                ) from e

        return path_obj

    # Yo, this validates file extension against whitelist - prevents uploading malicious files like
    # ".exe" or ".php" disguised as music. The .lower() is CRITICAL because Windows/Mac are case-
    # insensitive (".MP3" == ".mp3") but Python strings aren't! Without lower(), ".MP3" fails even
    # though it's valid. If allowed_extensions is None, we skip validation (dangerous - only do
    # this for trusted internal paths!). The sorted() in error message is just cosmetic for nicer
    # output. We log WARNING on failures to spot potential attacks or user mistakes.
    @staticmethod
    def validate_file_extension(
        path: Path | str,
        allowed_extensions: set[str] | None = None,
    ) -> Path:
        """Validate that a file has an allowed extension.

        Args:
            path: The file path to validate
            allowed_extensions: Set of allowed extensions (e.g., {'.mp3', '.flac'})
                              If None, no extension validation is performed

        Returns:
            The validated path as a Path object

        Raises:
            ValidationError: If the file extension is not allowed
        """
        path_obj = Path(path)

        if allowed_extensions is not None:
            extension = path_obj.suffix.lower()
            if extension not in allowed_extensions:
                logger.warning(
                    "Invalid file extension %s for path %s. Allowed: %s",
                    extension,
                    path_obj,
                    allowed_extensions,
                )
                raise ValidationError(
                    f"File extension {extension} is not allowed. "
                    f"Allowed extensions: {', '.join(sorted(allowed_extensions))}"
                )

        return path_obj

    # Listen future me, this is a COMBO validator - first checks path is in base_dir (security),
    # then checks extension is audio (type safety). Two-stage validation means better error messages.
    # If path is outside base_dir, you get "path traversal" error. If path is valid but wrong type
    # (like "music/cat.jpg"), you get "extension not allowed" error. The resolve param is passed
    # through to validate_path_within_base - usually True for security, but False for performance
    # if you already have absolute paths.
    @staticmethod
    def validate_audio_file_path(
        path: Path | str,
        base_dir: Path | str,
        *,
        resolve: bool = True,
    ) -> Path:
        """Validate an audio file path.

        Combines path validation with audio file extension validation.

        Args:
            path: The audio file path to validate
            base_dir: The base directory that path must be within
            resolve: Whether to resolve symlinks and relative paths (default: True)

        Returns:
            The validated path as a Path object

        Raises:
            ValueError: If the path is invalid or extension not allowed
        """
        # First validate the path is within base directory
        validated_path = PathValidator.validate_path_within_base(
            path, base_dir, resolve=resolve
        )

        # Then validate it's an audio file
        PathValidator.validate_file_extension(validated_path, ALLOWED_AUDIO_EXTENSIONS)

        return validated_path

    # Hey, same as validate_audio_file_path but for images (album art, etc). Images are less risky
    # than audio (smaller, no metadata exploits) but still need validation. If someone uploads a
    # 10GB "image.png" that's actually a zip bomb, this won't catch it - we only check extension!
    # Add size limits elsewhere if that's a concern.
    @staticmethod
    def validate_image_file_path(
        path: Path | str,
        base_dir: Path | str,
        *,
        resolve: bool = True,
    ) -> Path:
        """Validate an image file path.

        Combines path validation with image file extension validation.

        Args:
            path: The image file path to validate
            base_dir: The base directory that path must be within
            resolve: Whether to resolve symlinks and relative paths (default: True)

        Returns:
            The validated path as a Path object

        Raises:
            ValueError: If the path is invalid or extension not allowed
        """
        # First validate the path is within base directory
        validated_path = PathValidator.validate_path_within_base(
            path, base_dir, resolve=resolve
        )

        # Then validate it's an image file
        PathValidator.validate_file_extension(validated_path, ALLOWED_IMAGE_EXTENSIONS)

        return validated_path


# Yo future me, this is a CONVENIENCE wrapper around PathValidator class methods! Use this for
# quick one-off validations. If you're doing repeated validations with same params, instantiate
# PathValidator once instead (oh wait, it's all static methods, nevermind). The allowed_extensions
# is optional - if None, we only check path traversal, not file type. Good for directories or when
# you don't care about extension. This function has a nice docstring example - keep it updated!
def validate_safe_path(
    path: Path | str,
    base_dir: Path | str,
    *,
    allowed_extensions: set[str] | None = None,
    resolve: bool = True,
) -> Path:
    """Convenience function to validate a safe file path.

    Args:
        path: The path to validate
        base_dir: The base directory that path must be within
        allowed_extensions: Optional set of allowed file extensions
        resolve: Whether to resolve symlinks and relative paths (default: True)

    Returns:
        The validated path as a Path object

    Raises:
        AuthorizationError: If the path is outside allowed directory
        ValidationError: If the file extension is not allowed

    Example:
        >>> from pathlib import Path
        >>> base = Path("/mnt/music")
        >>> # This is safe
        >>> validate_safe_path("album/track.mp3", base, allowed_extensions={".mp3"})
        PosixPath('/mnt/music/album/track.mp3')
        >>> # This would raise AuthorizationError (path traversal)
        >>> validate_safe_path("../../etc/passwd", base)
        Traceback (most recent call last):
        ...
        AuthorizationError: Path ... is outside allowed directory ...
    """
    # Validate path is within base directory
    validated_path = PathValidator.validate_path_within_base(
        path, base_dir, resolve=resolve
    )

    # Optionally validate file extension
    if allowed_extensions is not None:
        PathValidator.validate_file_extension(validated_path, allowed_extensions)

    return validated_path
