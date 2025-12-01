"""Unit tests for Lidarr-style naming service.

Tests the NamingConfig, NamingService, and helper functions for generating
file and folder names following Lidarr conventions.
"""

from pathlib import Path

import pytest

from soulspot.domain.value_objects.naming import (
    ColonReplacement,
    MultiDiscStyle,
    NamingConfig,
    NamingService,
    clean_name,
    sort_name,
)


class TestNamingConfig:
    """Tests for NamingConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration matches Lidarr defaults."""
        config = NamingConfig()

        assert config.artist_folder_format == "{Artist Name}"
        assert config.album_folder_format == "{Album Title} ({Release Year})"
        assert config.standard_track_format == "{track:00} - {Track Title}"
        assert config.multi_disc_track_format == "{medium:00}-{track:00} - {Track Title}"
        assert config.various_artist_track_format == "{track:00} - {Artist Name} - {Track Title}"
        assert config.multi_disc_style == MultiDiscStyle.PREFIX
        assert config.replace_illegal_characters is True
        assert config.colon_replacement == ColonReplacement.SPACE_DASH

    def test_get_track_format_standard(self) -> None:
        """Test getting standard track format."""
        config = NamingConfig()
        assert config.get_track_format(is_multi_disc=False, is_various_artists=False) == "{track:00} - {Track Title}"

    def test_get_track_format_multi_disc(self) -> None:
        """Test getting multi-disc track format."""
        config = NamingConfig()
        assert config.get_track_format(is_multi_disc=True, is_various_artists=False) == "{medium:00}-{track:00} - {Track Title}"

    def test_get_track_format_various_artists(self) -> None:
        """Test getting Various Artists track format."""
        config = NamingConfig()
        # VA format takes precedence over multi-disc
        assert config.get_track_format(is_multi_disc=False, is_various_artists=True) == "{track:00} - {Artist Name} - {Track Title}"
        assert config.get_track_format(is_multi_disc=True, is_various_artists=True) == "{track:00} - {Artist Name} - {Track Title}"


class TestNamingService:
    """Tests for NamingService."""

    def test_format_artist_folder_simple(self) -> None:
        """Test simple artist folder naming."""
        service = NamingService()
        result = service.format_artist_folder("Michael Jackson")
        assert result == "Michael Jackson"

    def test_format_artist_folder_with_disambiguation(self) -> None:
        """Test artist folder with disambiguation."""
        service = NamingService()
        result = service.format_artist_folder("Genesis", "UK band")
        assert result == "Genesis (UK band)"

    def test_format_artist_folder_sanitizes_colons(self) -> None:
        """Test that colons are replaced in artist names."""
        service = NamingService()
        result = service.format_artist_folder("Artist: Special Name")
        assert ":" not in result
        assert result == "Artist - Special Name"

    def test_format_album_folder_with_year(self) -> None:
        """Test album folder with release year."""
        service = NamingService()
        result = service.format_album_folder("Thriller", 1982)
        assert result == "Thriller (1982)"

    def test_format_album_folder_without_year(self) -> None:
        """Test album folder without release year."""
        service = NamingService()
        result = service.format_album_folder("Unknown Album")
        # Without year, the format becomes "Album ()" which should be cleaned
        assert result == "Unknown Album ()"  # Default format includes year placeholder

    def test_format_album_folder_with_disambiguation(self) -> None:
        """Test album folder with disambiguation."""
        service = NamingService()
        result = service.format_album_folder("Bad", 1987, disambiguation="Deluxe Edition")
        assert result == "Bad (1987) (Deluxe Edition)"

    def test_format_album_folder_sanitizes_illegal_chars(self) -> None:
        """Test that illegal characters are removed from album names."""
        service = NamingService()
        result = service.format_album_folder("Re: Stacks", 2007)
        assert ":" not in result

    def test_format_track_filename_standard(self) -> None:
        """Test standard track filename."""
        service = NamingService()
        result = service.format_track_filename(
            track_title="Billie Jean",
            track_number=5,
            extension=".flac",
        )
        assert result == "05 - Billie Jean.flac"

    def test_format_track_filename_with_extension_without_dot(self) -> None:
        """Test that extension without dot is handled."""
        service = NamingService()
        result = service.format_track_filename(
            track_title="Billie Jean",
            track_number=5,
            extension="flac",
        )
        assert result == "05 - Billie Jean.flac"

    def test_format_track_filename_multi_disc(self) -> None:
        """Test multi-disc track filename."""
        service = NamingService()
        result = service.format_track_filename(
            track_title="Come Together",
            track_number=1,
            extension=".flac",
            medium_number=2,
            is_multi_disc=True,
        )
        assert result == "02-01 - Come Together.flac"

    def test_format_track_filename_various_artists(self) -> None:
        """Test Various Artists track filename."""
        service = NamingService()
        result = service.format_track_filename(
            track_title="You Can't Hurry Love",
            track_number=1,
            extension=".flac",
            artist_name="Phil Collins",
            is_various_artists=True,
        )
        assert result == "01 - Phil Collins - You Can't Hurry Love.flac"

    def test_format_track_filename_sanitizes(self) -> None:
        """Test that track filenames are sanitized."""
        service = NamingService()
        result = service.format_track_filename(
            track_title='Track: "Special"',
            track_number=1,
            extension=".mp3",
        )
        assert ":" not in result
        assert '"' not in result

    def test_format_full_path(self) -> None:
        """Test full path generation."""
        service = NamingService()
        result = service.format_full_path(
            root_folder=Path("/music"),
            artist_name="Michael Jackson",
            album_title="Thriller",
            track_title="Billie Jean",
            track_number=5,
            extension=".flac",
            release_year=1982,
        )
        assert result == Path("/music/Michael Jackson/Thriller (1982)/05 - Billie Jean.flac")

    def test_format_full_path_multi_disc_prefix(self) -> None:
        """Test full path with multi-disc prefix style."""
        service = NamingService()
        result = service.format_full_path(
            root_folder=Path("/music"),
            artist_name="The Beatles",
            album_title="The White Album",
            track_title="Birthday",
            track_number=1,
            extension=".flac",
            release_year=1968,
            medium_number=2,
            is_multi_disc=True,
        )
        assert result == Path("/music/The Beatles/The White Album (1968)/02-01 - Birthday.flac")

    def test_format_full_path_multi_disc_subfolder(self) -> None:
        """Test full path with multi-disc subfolder style."""
        config = NamingConfig(multi_disc_style=MultiDiscStyle.SUBFOLDER)
        service = NamingService(config=config)
        result = service.format_full_path(
            root_folder=Path("/music"),
            artist_name="The Beatles",
            album_title="The White Album",
            track_title="Birthday",
            track_number=1,
            extension=".flac",
            release_year=1968,
            medium_number=2,
            is_multi_disc=True,
        )
        assert result == Path("/music/The Beatles/The White Album (1968)/Disc 2/01 - Birthday.flac")

    def test_format_full_path_various_artists(self) -> None:
        """Test full path for Various Artists compilation."""
        service = NamingService()
        result = service.format_full_path(
            root_folder=Path("/music"),
            artist_name="Phil Collins",  # This is the track artist
            album_title="Now That's What I Call Music! 1",
            track_title="You Can't Hurry Love",
            track_number=1,
            extension=".flac",
            release_year=1983,
            is_various_artists=True,
        )
        # Note: Artist folder will be track artist, but track filename includes artist
        assert "01 - Phil Collins - You Can't Hurry Love.flac" in str(result)


class TestColonReplacement:
    """Tests for colon replacement options."""

    def test_delete_colon(self) -> None:
        """Test deleting colons."""
        config = NamingConfig(colon_replacement=ColonReplacement.DELETE)
        service = NamingService(config=config)
        result = service.format_track_filename("Re: Stacks", 1, ".flac")
        assert result == "01 - Re Stacks.flac"

    def test_dash_colon(self) -> None:
        """Test replacing colons with dash."""
        config = NamingConfig(colon_replacement=ColonReplacement.DASH)
        service = NamingService(config=config)
        result = service.format_track_filename("Re: Stacks", 1, ".flac")
        assert result == "01 - Re- Stacks.flac"

    def test_space_dash_colon(self) -> None:
        """Test replacing colons with space-dash (Lidarr default)."""
        config = NamingConfig(colon_replacement=ColonReplacement.SPACE_DASH)
        service = NamingService(config=config)
        result = service.format_track_filename("Re: Stacks", 1, ".flac")
        assert result == "01 - Re - Stacks.flac"


class TestCleanName:
    """Tests for clean_name helper."""

    def test_clean_name_removes_spaces(self) -> None:
        """Test that spaces are removed."""
        assert clean_name("Michael Jackson") == "michaeljackson"

    def test_clean_name_lowercase(self) -> None:
        """Test that result is lowercase."""
        assert clean_name("The BEATLES") == "thebeatles"

    def test_clean_name_removes_special_chars(self) -> None:
        """Test that special characters are removed."""
        assert clean_name("AC/DC") == "acdc"
        assert clean_name("Guns N' Roses") == "gunsnroses"

    def test_clean_name_empty(self) -> None:
        """Test handling of empty/special-only names."""
        assert clean_name("") == "unknown"
        assert clean_name("@#$%") == "unknown"


class TestSortName:
    """Tests for sort_name helper."""

    def test_sort_name_with_the(self) -> None:
        """Test moving 'The' to end."""
        assert sort_name("The Beatles") == "Beatles, The"

    def test_sort_name_with_a(self) -> None:
        """Test moving 'A' to end."""
        assert sort_name("A Tribe Called Quest") == "Tribe Called Quest, A"

    def test_sort_name_without_article(self) -> None:
        """Test name without article remains unchanged."""
        assert sort_name("Michael Jackson") == "Michael Jackson"

    def test_sort_name_empty(self) -> None:
        """Test empty string handling."""
        assert sort_name("") == ""
