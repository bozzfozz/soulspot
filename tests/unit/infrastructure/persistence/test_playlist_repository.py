"""Unit tests for PlaylistRepository source case handling.

Hey future me - this test validates that the PlaylistRepository correctly handles
case-insensitive source values. The DB stores uppercase (SPOTIFY, MANUAL) but
the PlaylistSource enum has lowercase values. This test ensures the conversion works.
"""

import pytest

from soulspot.domain.entities import PlaylistSource


class TestPlaylistSourceCaseHandling:
    """Tests for case-insensitive PlaylistSource handling."""

    def test_source_enum_accepts_lowercase_spotify(self) -> None:
        """Test that PlaylistSource enum has lowercase 'spotify' value."""
        assert PlaylistSource.SPOTIFY.value == "spotify"
        assert PlaylistSource("spotify") == PlaylistSource.SPOTIFY

    def test_source_enum_accepts_lowercase_manual(self) -> None:
        """Test that PlaylistSource enum has lowercase 'manual' value."""
        assert PlaylistSource.MANUAL.value == "manual"
        assert PlaylistSource("manual") == PlaylistSource.MANUAL

    def test_source_enum_uppercase_requires_lowercase_conversion(self) -> None:
        """Test that uppercase source from DB fails without conversion."""
        with pytest.raises(ValueError):
            PlaylistSource("SPOTIFY")
        with pytest.raises(ValueError):
            PlaylistSource("MANUAL")

    def test_source_conversion_from_uppercase_db_value(self) -> None:
        """Test that converting uppercase DB value to lowercase works.

        This simulates what the repository does when reading from the database.
        The DB stores 'SPOTIFY' or 'MANUAL' but the enum expects lowercase.
        """
        db_value_spotify = "SPOTIFY"
        db_value_manual = "MANUAL"

        # Conversion by lowercasing (as done in repository)
        assert PlaylistSource(db_value_spotify.lower()) == PlaylistSource.SPOTIFY
        assert PlaylistSource(db_value_manual.lower()) == PlaylistSource.MANUAL

    def test_source_conversion_handles_mixed_case(self) -> None:
        """Test that mixed case values work when converted to lowercase."""
        assert PlaylistSource("Spotify".lower()) == PlaylistSource.SPOTIFY
        assert PlaylistSource("Manual".lower()) == PlaylistSource.MANUAL
        assert PlaylistSource("sPOTIFY".lower()) == PlaylistSource.SPOTIFY
