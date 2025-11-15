"""Unit tests for library scanner service."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from soulspot.application.services.library_scanner import (
    FileInfo,
    LibraryScannerService,
)


@pytest.fixture
def scanner_service() -> LibraryScannerService:
    """Create a library scanner service instance."""
    return LibraryScannerService(hash_algorithm="sha256")


class TestLibraryScannerService:
    """Test LibraryScannerService."""

    def test_init_default_algorithm(self) -> None:
        """Test initialization with default algorithm."""
        service = LibraryScannerService()
        assert service.hash_algorithm == "sha256"

    def test_init_custom_algorithm(self) -> None:
        """Test initialization with custom algorithm."""
        service = LibraryScannerService(hash_algorithm="md5")
        assert service.hash_algorithm == "md5"

    def test_discover_audio_files_nonexistent_path(
        self, scanner_service: LibraryScannerService
    ) -> None:
        """Test discovering files in nonexistent path."""
        result = scanner_service.discover_audio_files(Path("/nonexistent/path"))
        assert result == []

    def test_discover_audio_files_file_not_directory(
        self, scanner_service: LibraryScannerService, tmp_path: Path
    ) -> None:
        """Test discovering files when path is a file not directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = scanner_service.discover_audio_files(test_file)
        assert result == []

    def test_discover_audio_files_empty_directory(
        self, scanner_service: LibraryScannerService, tmp_path: Path
    ) -> None:
        """Test discovering files in empty directory."""
        result = scanner_service.discover_audio_files(tmp_path)
        assert result == []

    def test_discover_audio_files_with_audio_files(
        self, scanner_service: LibraryScannerService, tmp_path: Path
    ) -> None:
        """Test discovering audio files in directory."""
        # Create test audio files
        mp3_file = tmp_path / "test1.mp3"
        flac_file = tmp_path / "test2.flac"
        txt_file = tmp_path / "readme.txt"

        mp3_file.write_bytes(b"fake mp3 content")
        flac_file.write_bytes(b"fake flac content")
        txt_file.write_text("readme")

        result = scanner_service.discover_audio_files(tmp_path)

        # Should only find audio files
        assert len(result) == 2
        assert mp3_file in result
        assert flac_file in result
        assert txt_file not in result

    def test_discover_audio_files_recursive(
        self, scanner_service: LibraryScannerService, tmp_path: Path
    ) -> None:
        """Test discovering audio files recursively."""
        # Create nested directories with audio files
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        mp3_file = tmp_path / "test.mp3"
        flac_file = subdir / "test.flac"

        mp3_file.write_bytes(b"fake mp3 content")
        flac_file.write_bytes(b"fake flac content")

        result = scanner_service.discover_audio_files(tmp_path)

        # Should find both files recursively
        assert len(result) == 2
        assert mp3_file in result
        assert flac_file in result

    def test_calculate_file_hash(
        self, scanner_service: LibraryScannerService, tmp_path: Path
    ) -> None:
        """Test calculating file hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        hash_value = scanner_service.calculate_file_hash(test_file)

        # Should return a non-empty hash
        assert hash_value
        assert len(hash_value) == 64  # SHA256 produces 64 hex chars

    def test_calculate_file_hash_same_content(
        self, scanner_service: LibraryScannerService, tmp_path: Path
    ) -> None:
        """Test that same content produces same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("identical content")
        file2.write_text("identical content")

        hash1 = scanner_service.calculate_file_hash(file1)
        hash2 = scanner_service.calculate_file_hash(file2)

        assert hash1 == hash2

    def test_calculate_file_hash_different_content(
        self, scanner_service: LibraryScannerService, tmp_path: Path
    ) -> None:
        """Test that different content produces different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("content one")
        file2.write_text("content two")

        hash1 = scanner_service.calculate_file_hash(file1)
        hash2 = scanner_service.calculate_file_hash(file2)

        assert hash1 != hash2

    def test_calculate_file_hash_nonexistent_file(
        self, scanner_service: LibraryScannerService
    ) -> None:
        """Test calculating hash of nonexistent file."""
        result = scanner_service.calculate_file_hash(Path("/nonexistent/file.txt"))
        assert result == ""

    @patch("soulspot.application.services.library_scanner.MutagenFile")
    def test_validate_audio_file_valid(
        self,
        mock_mutagen: Mock,
        scanner_service: LibraryScannerService,
        tmp_path: Path,
    ) -> None:
        """Test validating valid audio file."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio")

        # Mock mutagen to return valid audio info
        mock_audio = MagicMock()
        mock_audio.info.length = 180.0
        mock_mutagen.return_value = mock_audio

        is_valid, error = scanner_service.validate_audio_file(test_file)

        assert is_valid is True
        assert error is None

    @patch("soulspot.application.services.library_scanner.MutagenFile")
    def test_validate_audio_file_unsupported(
        self,
        mock_mutagen: Mock,
        scanner_service: LibraryScannerService,
        tmp_path: Path,
    ) -> None:
        """Test validating unsupported file format."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio")

        # Mock mutagen to return None for unsupported format
        mock_mutagen.return_value = None

        is_valid, error = scanner_service.validate_audio_file(test_file)

        assert is_valid is False
        assert error == "Unsupported audio format"

    @patch("soulspot.application.services.library_scanner.MutagenFile")
    def test_validate_audio_file_zero_length(
        self,
        mock_mutagen: Mock,
        scanner_service: LibraryScannerService,
        tmp_path: Path,
    ) -> None:
        """Test validating audio file with zero length."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio")

        # Mock mutagen to return audio with zero length
        mock_audio = MagicMock()
        mock_audio.info.length = 0.0
        mock_mutagen.return_value = mock_audio

        is_valid, error = scanner_service.validate_audio_file(test_file)

        assert is_valid is False
        assert error == "Invalid audio length"

    def test_detect_duplicates_no_duplicates(
        self, scanner_service: LibraryScannerService
    ) -> None:
        """Test duplicate detection with no duplicates."""
        file1 = FileInfo(
            path=Path("/path/file1.mp3"),
            size=1000,
            hash_value="hash1",
            hash_algorithm="sha256",
        )
        file2 = FileInfo(
            path=Path("/path/file2.mp3"),
            size=2000,
            hash_value="hash2",
            hash_algorithm="sha256",
        )

        result = scanner_service.detect_duplicates([file1, file2])

        assert len(result) == 0

    def test_detect_duplicates_with_duplicates(
        self, scanner_service: LibraryScannerService
    ) -> None:
        """Test duplicate detection with duplicates."""
        file1 = FileInfo(
            path=Path("/path/file1.mp3"),
            size=1000,
            hash_value="samehash",
            hash_algorithm="sha256",
        )
        file2 = FileInfo(
            path=Path("/path/file2.mp3"),
            size=1000,
            hash_value="samehash",
            hash_algorithm="sha256",
        )
        file3 = FileInfo(
            path=Path("/path/file3.mp3"),
            size=2000,
            hash_value="differenthash",
            hash_algorithm="sha256",
        )

        result = scanner_service.detect_duplicates([file1, file2, file3])

        # Should have one duplicate group
        assert len(result) == 1
        assert "samehash" in result
        assert len(result["samehash"]) == 2

    def test_analyze_broken_files(
        self, scanner_service: LibraryScannerService
    ) -> None:
        """Test analyzing broken files."""
        file1 = FileInfo(
            path=Path("/path/file1.mp3"),
            size=1000,
            hash_value="hash1",
            hash_algorithm="sha256",
            is_valid=True,
        )
        file2 = FileInfo(
            path=Path("/path/file2.mp3"),
            size=2000,
            hash_value="hash2",
            hash_algorithm="sha256",
            is_valid=False,
            error="Corrupted file",
        )

        result = scanner_service.analyze_broken_files([file1, file2])

        # Should only return broken files
        assert len(result) == 1
        assert result[0].path == Path("/path/file2.mp3")
        assert result[0].is_valid is False
