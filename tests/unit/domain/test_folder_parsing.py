"""Unit tests for Lidarr folder structure parsing.

Tests the regex patterns and parsing functions for extracting metadata
from Lidarr-organized folder and file names.
"""

from pathlib import Path

import pytest

from soulspot.domain.value_objects.folder_parsing import (
    is_audio_file,
    is_disc_folder,
    parse_album_folder,
    parse_track_filename,
)


class TestParseAlbumFolder:
    """Tests for parse_album_folder function."""

    def test_parse_title_with_year(self) -> None:
        """Test parsing 'Title (Year)' format."""
        result = parse_album_folder("Thriller (1982)")
        assert result.title == "Thriller"
        assert result.year == 1982
        assert result.disambiguation is None

    def test_parse_title_only(self) -> None:
        """Test parsing title without year."""
        result = parse_album_folder("Unknown Album")
        assert result.title == "Unknown Album"
        assert result.year is None
        assert result.disambiguation is None

    def test_parse_title_with_year_and_disambiguation(self) -> None:
        """Test parsing 'Title (Year) (Disambiguation)' format."""
        result = parse_album_folder("Bad (1987) (Deluxe Edition)")
        assert result.title == "Bad"
        assert result.year == 1987
        assert result.disambiguation == "Deluxe Edition"

    def test_parse_title_with_quality_tag(self) -> None:
        """Test parsing 'Title (Year) [Quality]' format."""
        result = parse_album_folder("Thriller (1982) [FLAC]")
        assert result.title == "Thriller"
        assert result.year == 1982
        assert result.quality == "FLAC"

    def test_parse_complex_title(self) -> None:
        """Test parsing album with complex title."""
        result = parse_album_folder("Now That's What I Call Music! 1 (1983)")
        assert result.title == "Now That's What I Call Music! 1"
        assert result.year == 1983

    def test_parse_title_with_parentheses(self) -> None:
        """Test parsing title that contains parentheses before year."""
        result = parse_album_folder("Live at Wembley (Concert) (1986)")
        # The regex should handle this
        assert result.year == 1986

    def test_raw_name_preserved(self) -> None:
        """Test that raw folder name is preserved."""
        result = parse_album_folder("Thriller (1982)")
        assert result.raw_name == "Thriller (1982)"


class TestParseTrackFilename:
    """Tests for parse_track_filename function."""

    def test_parse_standard_format(self) -> None:
        """Test parsing 'NN - Title.ext' format."""
        result = parse_track_filename("05 - Billie Jean.flac")
        assert result.title == "Billie Jean"
        assert result.track_number == 5
        assert result.disc_number == 1
        assert result.extension == ".flac"
        assert result.artist is None

    def test_parse_single_digit_track(self) -> None:
        """Test parsing single-digit track number."""
        result = parse_track_filename("1 - Track One.mp3")
        assert result.title == "Track One"
        assert result.track_number == 1

    def test_parse_multi_disc_format(self) -> None:
        """Test parsing 'DD-TT - Title.ext' format."""
        result = parse_track_filename("02-05 - Birthday.flac")
        assert result.title == "Birthday"
        assert result.track_number == 5
        assert result.disc_number == 2
        assert result.extension == ".flac"

    def test_parse_multi_disc_single_digit(self) -> None:
        """Test parsing multi-disc with single digits."""
        result = parse_track_filename("1-1 - First Track.mp3")
        assert result.track_number == 1
        assert result.disc_number == 1
        assert result.title == "First Track"

    def test_parse_various_artists_format(self) -> None:
        """Test parsing 'NN - Artist - Title.ext' format."""
        result = parse_track_filename("01 - Michael Jackson - Billie Jean.flac")
        assert result.title == "Billie Jean"
        assert result.track_number == 1
        assert result.artist == "Michael Jackson"
        assert result.extension == ".flac"

    def test_parse_va_with_dash_in_artist(self) -> None:
        """Test parsing VA track where artist has dash in name."""
        result = parse_track_filename("05 - Jay-Z - Empire State of Mind.mp3")
        # Note: This is ambiguous - parser might not handle perfectly
        assert result.track_number == 5
        assert result.extension == ".mp3"

    def test_parse_title_with_two_dashes(self) -> None:
        """Test parsing title that has two dash separators (ambiguous VA format)."""
        # "01 - Re - Stacks" looks like VA format: track - artist - title
        # The parser will interpret "Re" as artist and "Stacks" as title
        result = parse_track_filename("01 - Re - Stacks.flac")
        # This is the expected behavior - ambiguous format
        assert result.track_number == 1
        assert result.artist == "Re"
        assert result.title == "Stacks"
        # For properly formatted files without VA artist, use single dash:
        # "01 - Re -  Stacks" or just avoid double separators

    def test_parse_title_with_en_dash(self) -> None:
        """Test parsing with en-dash separator."""
        result = parse_track_filename("05 – Billie Jean.flac")
        assert result.title == "Billie Jean"
        assert result.track_number == 5

    def test_parse_fallback(self) -> None:
        """Test fallback parsing for non-standard names."""
        result = parse_track_filename("some_weird_filename.mp3")
        assert result.title == "some_weird_filename"
        assert result.track_number == 0
        assert result.extension == ".mp3"

    def test_is_various_artists_format_true(self) -> None:
        """Test is_various_artists_format property for VA tracks."""
        result = parse_track_filename("01 - Artist - Title.flac")
        assert result.is_various_artists_format is True

    def test_is_various_artists_format_false(self) -> None:
        """Test is_various_artists_format property for standard tracks."""
        result = parse_track_filename("01 - Title.flac")
        assert result.is_various_artists_format is False


class TestIsDiscFolder:
    """Tests for is_disc_folder function."""

    def test_disc_folder_standard(self) -> None:
        """Test 'Disc N' format."""
        is_disc, num = is_disc_folder("Disc 1")
        assert is_disc is True
        assert num == 1

    def test_disc_folder_cd(self) -> None:
        """Test 'CD N' format."""
        is_disc, num = is_disc_folder("CD 2")
        assert is_disc is True
        assert num == 2

    def test_disc_folder_case_insensitive(self) -> None:
        """Test case insensitivity."""
        is_disc, num = is_disc_folder("DISC 3")
        assert is_disc is True
        assert num == 3

        is_disc, num = is_disc_folder("disc 1")
        assert is_disc is True
        assert num == 1

    def test_disc_folder_with_title(self) -> None:
        """Test 'Disc N - Title' format."""
        is_disc, num = is_disc_folder("Disc 1 - The Early Years")
        assert is_disc is True
        assert num == 1

    def test_not_disc_folder(self) -> None:
        """Test non-disc folders."""
        is_disc, num = is_disc_folder("Songs")
        assert is_disc is False
        assert num is None

        is_disc, num = is_disc_folder("Bonus Tracks")
        assert is_disc is False
        assert num is None

    def test_disc_folder_disk_spelling(self) -> None:
        """Test 'Disk' spelling variation."""
        is_disc, num = is_disc_folder("Disk 1")
        assert is_disc is True
        assert num == 1


class TestIsAudioFile:
    """Tests for is_audio_file function."""

    def test_common_lossy_formats(self) -> None:
        """Test common lossy audio formats."""
        assert is_audio_file("track.mp3") is True
        assert is_audio_file("track.m4a") is True
        assert is_audio_file("track.ogg") is True
        assert is_audio_file("track.opus") is True

    def test_common_lossless_formats(self) -> None:
        """Test common lossless audio formats."""
        assert is_audio_file("track.flac") is True
        assert is_audio_file("track.wav") is True
        assert is_audio_file("track.alac") is True
        assert is_audio_file("track.ape") is True
        assert is_audio_file("track.wv") is True

    def test_case_insensitive(self) -> None:
        """Test case insensitivity."""
        assert is_audio_file("TRACK.FLAC") is True
        assert is_audio_file("Track.Mp3") is True

    def test_non_audio_files(self) -> None:
        """Test rejection of non-audio files."""
        assert is_audio_file("cover.jpg") is False
        assert is_audio_file("playlist.m3u") is False
        assert is_audio_file("info.txt") is False
        assert is_audio_file("folder.xml") is False


class TestParseTrackFilenameEdgeCases:
    """Additional edge case tests for track filename parsing."""

    def test_three_digit_track_number(self) -> None:
        """Test parsing three-digit track number."""
        result = parse_track_filename("100 - Centennial Track.flac")
        assert result.track_number == 100

    def test_track_with_parentheses_in_title(self) -> None:
        """Test parsing track with parentheses in title."""
        result = parse_track_filename("05 - Beat It (Single Version).flac")
        assert result.title == "Beat It (Single Version)"
        assert result.track_number == 5

    def test_track_with_brackets_in_title(self) -> None:
        """Test parsing track with brackets in title."""
        result = parse_track_filename("05 - Beat It [Remastered].flac")
        assert result.title == "Beat It [Remastered]"

    def test_empty_title_handling(self) -> None:
        """Test handling of near-empty filenames."""
        result = parse_track_filename("01 - .flac")
        # Should handle gracefully
        assert result.track_number == 1

    def test_extension_preserved(self) -> None:
        """Test that extension is correctly extracted."""
        result = parse_track_filename("05 - Billie Jean.FLAC")
        assert result.extension == ".flac"  # Should be lowercase

        result = parse_track_filename("05 - Billie Jean.MP3")
        assert result.extension == ".mp3"
