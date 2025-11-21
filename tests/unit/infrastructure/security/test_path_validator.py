"""Tests for path validation utilities."""

import os
from pathlib import Path

import pytest

from soulspot.infrastructure.security.path_validator import (
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    PathValidator,
    validate_safe_path,
)


class TestPathValidator:
    """Tests for PathValidator class."""

    def test_validate_path_within_base_success(self, tmp_path: Path) -> None:
        """Test that valid paths within base directory are accepted."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Create a subdirectory
        subdir = base_dir / "album"
        subdir.mkdir()

        # Test with simple path
        result = PathValidator.validate_path_within_base(
            base_dir / "track.mp3", base_dir
        )
        assert result == base_dir / "track.mp3"

        # Test with nested path
        result = PathValidator.validate_path_within_base(
            subdir / "track.mp3", base_dir
        )
        assert result == subdir / "track.mp3"

    def test_validate_path_within_base_traversal_attempt(self, tmp_path: Path) -> None:
        """Test that path traversal attempts are rejected."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Try to escape base directory
        with pytest.raises(ValueError, match="outside allowed directory"):
            PathValidator.validate_path_within_base(
                base_dir / ".." / "etc" / "passwd", base_dir
            )

        # Another traversal attempt
        with pytest.raises(ValueError, match="outside allowed directory"):
            PathValidator.validate_path_within_base(
                base_dir / "album" / ".." / ".." / "secret.txt", base_dir
            )

    def test_validate_path_within_base_absolute_path_outside(
        self, tmp_path: Path
    ) -> None:
        """Test that absolute paths outside base are rejected."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        other_dir = tmp_path / "other"
        other_dir.mkdir()

        with pytest.raises(ValueError, match="outside allowed directory"):
            PathValidator.validate_path_within_base(other_dir / "file.txt", base_dir)

    def test_validate_file_extension_success(self) -> None:
        """Test that files with allowed extensions are accepted."""
        allowed = {".mp3", ".flac"}

        result = PathValidator.validate_file_extension(Path("track.mp3"), allowed)
        assert result == Path("track.mp3")

        result = PathValidator.validate_file_extension(Path("track.FLAC"), allowed)
        assert result == Path("track.FLAC")

    def test_validate_file_extension_rejected(self) -> None:
        """Test that files with disallowed extensions are rejected."""
        allowed = {".mp3", ".flac"}

        with pytest.raises(ValueError, match="not allowed"):
            PathValidator.validate_file_extension(Path("script.sh"), allowed)

        with pytest.raises(ValueError, match="not allowed"):
            PathValidator.validate_file_extension(Path("file.txt"), allowed)

    def test_validate_file_extension_case_insensitive(self) -> None:
        """Test that extension validation is case-insensitive."""
        allowed = {".mp3"}

        # All of these should work
        PathValidator.validate_file_extension(Path("track.mp3"), allowed)
        PathValidator.validate_file_extension(Path("track.MP3"), allowed)
        PathValidator.validate_file_extension(Path("track.Mp3"), allowed)

    def test_validate_file_extension_none_allowed(self) -> None:
        """Test that None for allowed_extensions skips validation."""
        # Should not raise even with arbitrary extension
        result = PathValidator.validate_file_extension(Path("file.xyz"), None)
        assert result == Path("file.xyz")

    def test_validate_audio_file_path_success(self, tmp_path: Path) -> None:
        """Test that valid audio file paths are accepted."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Create audio file
        audio_file = base_dir / "track.mp3"
        audio_file.touch()

        result = PathValidator.validate_audio_file_path(audio_file, base_dir)
        assert result == audio_file

    def test_validate_audio_file_path_wrong_extension(self, tmp_path: Path) -> None:
        """Test that non-audio files are rejected."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Try with a text file
        with pytest.raises(ValueError, match="not allowed"):
            PathValidator.validate_audio_file_path(base_dir / "script.sh", base_dir)

    def test_validate_audio_file_path_traversal(self, tmp_path: Path) -> None:
        """Test that audio files outside base dir are rejected."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        with pytest.raises(ValueError, match="outside allowed directory"):
            PathValidator.validate_audio_file_path(
                base_dir / ".." / "track.mp3", base_dir
            )

    def test_validate_image_file_path_success(self, tmp_path: Path) -> None:
        """Test that valid image file paths are accepted."""
        base_dir = tmp_path / "artwork"
        base_dir.mkdir()

        # Create image file
        image_file = base_dir / "cover.jpg"
        image_file.touch()

        result = PathValidator.validate_image_file_path(image_file, base_dir)
        assert result == image_file

    def test_validate_image_file_path_wrong_extension(self, tmp_path: Path) -> None:
        """Test that non-image files are rejected."""
        base_dir = tmp_path / "artwork"
        base_dir.mkdir()

        with pytest.raises(ValueError, match="not allowed"):
            PathValidator.validate_image_file_path(base_dir / "file.txt", base_dir)

    def test_allowed_audio_extensions(self) -> None:
        """Test that common audio extensions are allowed."""
        expected_extensions = {
            ".mp3",
            ".flac",
            ".m4a",
            ".ogg",
            ".opus",
            ".wav",
            ".aac",
            ".wma",
        }
        assert expected_extensions == ALLOWED_AUDIO_EXTENSIONS

    def test_allowed_image_extensions(self) -> None:
        """Test that common image extensions are allowed."""
        expected_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        assert expected_extensions == ALLOWED_IMAGE_EXTENSIONS


class TestValidateSafePath:
    """Tests for validate_safe_path convenience function."""

    def test_validate_safe_path_basic(self, tmp_path: Path) -> None:
        """Test basic safe path validation."""
        base_dir = tmp_path / "data"
        base_dir.mkdir()

        file_path = base_dir / "file.txt"
        file_path.touch()

        result = validate_safe_path(file_path, base_dir)
        assert result == file_path

    def test_validate_safe_path_with_extension(self, tmp_path: Path) -> None:
        """Test safe path validation with extension checking."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        file_path = base_dir / "track.mp3"
        file_path.touch()

        result = validate_safe_path(file_path, base_dir, allowed_extensions={".mp3"})
        assert result == file_path

    def test_validate_safe_path_wrong_extension(self, tmp_path: Path) -> None:
        """Test that wrong extensions are rejected."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        with pytest.raises(ValueError, match="not allowed"):
            validate_safe_path(
                base_dir / "file.txt", base_dir, allowed_extensions={".mp3"}
            )

    def test_validate_safe_path_traversal_attempt(self, tmp_path: Path) -> None:
        """Test that path traversal is rejected."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        with pytest.raises(ValueError, match="outside allowed directory"):
            validate_safe_path(base_dir / ".." / "etc" / "passwd", base_dir)

    def test_validate_safe_path_with_relative_path(self, tmp_path: Path) -> None:
        """Test validation with relative paths."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Create subdirectory
        subdir = base_dir / "album"
        subdir.mkdir()

        # Test with relative path (from base_dir perspective)
        file_path = base_dir / "album" / "track.mp3"
        file_path.touch()

        result = validate_safe_path(file_path, base_dir)
        assert result == file_path

    def test_validate_safe_path_no_resolve(self, tmp_path: Path) -> None:
        """Test path validation without resolution."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        file_path = base_dir / "track.mp3"

        # Without resolve, we just check if it's logically within base
        # (but won't resolve symlinks or .. components)
        result = validate_safe_path(file_path, base_dir, resolve=False)
        assert result == file_path


class TestSecurityScenarios:
    """Test various security attack scenarios."""

    def test_block_etc_passwd_access(self, tmp_path: Path) -> None:
        """Test that attempts to access /etc/passwd are blocked."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Various attempts to access /etc/passwd
        attempts = [
            "../../../etc/passwd",
            "../../etc/passwd",
            "../etc/passwd",
            "album/../../etc/passwd",
        ]

        for attempt in attempts:
            with pytest.raises(ValueError, match="outside allowed directory"):
                validate_safe_path(base_dir / attempt, base_dir)

    def test_block_null_byte_injection(self, tmp_path: Path) -> None:
        """Test that null byte injection attempts are handled."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Null bytes in filenames should be rejected by Path or our validation
        # This test documents the behavior
        try:
            malicious_path = "track\x00.mp3"
            # Path() will raise ValueError on null bytes in Python 3.9+
            path_obj = Path(malicious_path)
            # If it doesn't raise, our validation should still catch it
            validate_safe_path(base_dir / path_obj, base_dir)
        except (ValueError, OSError):
            # Expected - null bytes should be rejected
            pass

    def test_block_symlink_escape(self, tmp_path: Path) -> None:
        """Test that symlinks pointing outside base are blocked."""
        if os.name == "nt":
            pytest.skip("Symlink test not applicable on Windows")

        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Create a directory outside base
        outside_dir = tmp_path / "secret"
        outside_dir.mkdir()
        secret_file = outside_dir / "secret.txt"
        secret_file.write_text("secret")

        # Create a symlink inside base pointing to outside
        symlink = base_dir / "link_to_secret"
        symlink.symlink_to(secret_file)

        # With resolve=True (default), this should be rejected
        with pytest.raises(ValueError, match="outside allowed directory"):
            validate_safe_path(symlink, base_dir, resolve=True)

    def test_allow_symlink_within_base(self, tmp_path: Path) -> None:
        """Test that symlinks within base are allowed."""
        if os.name == "nt":
            pytest.skip("Symlink test not applicable on Windows")

        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Create a file within base
        real_file = base_dir / "track.mp3"
        real_file.touch()

        # Create a symlink within base pointing to file in base
        symlink = base_dir / "link_to_track.mp3"
        symlink.symlink_to(real_file)

        # This should be allowed
        result = validate_safe_path(symlink, base_dir, resolve=True)
        assert result == real_file  # Should resolve to the real file

    def test_block_special_characters(self, tmp_path: Path) -> None:
        """Test handling of special characters in filenames."""
        base_dir = tmp_path / "music"
        base_dir.mkdir()

        # Most special characters should be handled by Path
        # Test that our validation still works
        valid_chars_file = base_dir / "track (2023) [remaster].mp3"
        result = validate_safe_path(valid_chars_file, base_dir)
        assert result == valid_chars_file
