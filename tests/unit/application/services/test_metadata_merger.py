"""Tests for metadata merger service."""

from datetime import UTC, datetime

import pytest

from soulspot.application.services.metadata_merger import MetadataMerger
from soulspot.domain.entities import Album, Artist, MetadataSource, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId


@pytest.fixture
def metadata_merger():
    """Create metadata merger instance."""
    return MetadataMerger()


@pytest.fixture
def sample_track():
    """Create a sample track."""
    return Track(
        id=TrackId.generate(),
        title="Test Song",
        artist_id=ArtistId.generate(),
        duration_ms=240000,
        isrc="USRC12345678",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_artist():
    """Create a sample artist."""
    return Artist(
        id=ArtistId.generate(),
        name="Test Artist feat. Other Artist",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_album():
    """Create a sample album."""
    return Album(
        id=AlbumId.generate(),
        title="Test Album",
        artist_id=ArtistId.generate(),
        release_year=2020,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class TestMetadataMerger:
    """Tests for MetadataMerger."""

    def test_authority_hierarchy(self, metadata_merger):
        """Test authority hierarchy order."""
        # Assert
        assert (
            metadata_merger._get_source_priority(MetadataSource.MANUAL)
            < metadata_merger._get_source_priority(MetadataSource.MUSICBRAINZ)
        )
        assert (
            metadata_merger._get_source_priority(MetadataSource.MUSICBRAINZ)
            < metadata_merger._get_source_priority(MetadataSource.SPOTIFY)
        )
        assert (
            metadata_merger._get_source_priority(MetadataSource.SPOTIFY)
            < metadata_merger._get_source_priority(MetadataSource.LASTFM)
        )

    def test_select_best_value_higher_priority(self, metadata_merger):
        """Test selecting value with higher priority source."""
        # Arrange
        current_value = "old value"
        current_source = MetadataSource.SPOTIFY
        new_value = "new value"
        new_source = MetadataSource.MUSICBRAINZ

        # Act
        best_value, best_source = metadata_merger._select_best_value(
            current_value, current_source, new_value, new_source
        )

        # Assert
        assert best_value == new_value
        assert best_source == new_source

    def test_select_best_value_lower_priority(self, metadata_merger):
        """Test selecting value with lower priority source."""
        # Arrange
        current_value = "current value"
        current_source = MetadataSource.MUSICBRAINZ
        new_value = "new value"
        new_source = MetadataSource.LASTFM

        # Act
        best_value, best_source = metadata_merger._select_best_value(
            current_value, current_source, new_value, new_source
        )

        # Assert
        assert best_value == current_value
        assert best_source == current_source

    def test_select_best_value_empty_new_value(self, metadata_merger):
        """Test selecting value when new value is empty."""
        # Arrange
        current_value = "current value"
        current_source = MetadataSource.SPOTIFY
        new_value = None
        new_source = MetadataSource.MUSICBRAINZ

        # Act
        best_value, best_source = metadata_merger._select_best_value(
            current_value, current_source, new_value, new_source
        )

        # Assert
        assert best_value == current_value

    def test_merge_lists(self, metadata_merger):
        """Test merging lists with deduplication."""
        # Arrange
        current_list = ["rock", "indie", "alternative"]
        new_list = ["rock", "electronic", "pop"]

        # Act
        merged = metadata_merger._merge_lists(current_list, new_list, max_items=5)

        # Assert
        assert len(merged) == 5
        assert "rock" in merged
        assert "indie" in merged
        assert "electronic" in merged
        assert merged.count("rock") == 1  # No duplicates

    def test_merge_lists_with_max_items(self, metadata_merger):
        """Test merging lists respects max_items limit."""
        # Arrange
        current_list = ["tag1", "tag2", "tag3"]
        new_list = ["tag4", "tag5", "tag6"]

        # Act
        merged = metadata_merger._merge_lists(current_list, new_list, max_items=4)

        # Assert
        assert len(merged) == 4

    def test_normalize_artist_name_feat(self, metadata_merger):
        """Test normalizing artist name with feat. variations."""
        # Test cases
        test_cases = [
            ("Artist ft. Other", "Artist feat. Other"),
            ("Artist featuring Other", "Artist feat. Other"),
            ("Artist Feat. Other", "Artist feat. Other"),
            ("Artist Ft Other", "Artist feat. Other"),
            ("Artist feat Other", "Artist feat. Other"),
        ]

        for input_name, expected in test_cases:
            # Act
            result = metadata_merger.normalize_artist_name(input_name)

            # Assert
            assert result == expected, f"Failed for input: {input_name}"

    def test_normalize_artist_name_no_change(self, metadata_merger):
        """Test normalizing artist name when no change needed."""
        # Arrange
        name = "Simple Artist Name"

        # Act
        result = metadata_merger.normalize_artist_name(name)

        # Assert
        assert result == name

    def test_merge_track_metadata_from_musicbrainz(
        self, metadata_merger, sample_track
    ):
        """Test merging track metadata from MusicBrainz."""
        # Arrange
        musicbrainz_data = {
            "length": 250000,
            "isrc-list": ["GBRC12345678"],
            "tags": [{"name": "rock"}, {"name": "indie"}],
        }

        # Act
        result = metadata_merger.merge_track_metadata(
            track=sample_track,
            musicbrainz_data=musicbrainz_data,
        )

        # Assert
        assert result.duration_ms == 250000
        assert result.isrc == "GBRC12345678"
        assert "rock" in result.tags
        assert "indie" in result.tags
        assert result.metadata_sources["duration_ms"] == MetadataSource.MUSICBRAINZ.value

    def test_merge_track_metadata_from_lastfm(
        self, metadata_merger, sample_track
    ):
        """Test merging track metadata from Last.fm."""
        # Arrange
        lastfm_data = {
            "toptags": {
                "tag": [
                    {"name": "electronic"},
                    {"name": "dance"},
                ]
            }
        }

        # Act
        result = metadata_merger.merge_track_metadata(
            track=sample_track,
            lastfm_data=lastfm_data,
        )

        # Assert
        assert "electronic" in result.tags
        assert "dance" in result.tags

    def test_merge_track_metadata_with_manual_override(
        self, metadata_merger, sample_track
    ):
        """Test merging track metadata with manual overrides."""
        # Arrange
        sample_track.duration_ms = 240000
        sample_track.metadata_sources["duration_ms"] = MetadataSource.SPOTIFY.value

        musicbrainz_data = {"length": 245000}
        manual_overrides = {"duration_ms": 242000}

        # Act
        result = metadata_merger.merge_track_metadata(
            track=sample_track,
            musicbrainz_data=musicbrainz_data,
            manual_overrides=manual_overrides,
        )

        # Assert
        assert result.duration_ms == 242000  # Manual override wins
        assert result.metadata_sources["duration_ms"] == MetadataSource.MANUAL.value

    def test_merge_artist_metadata(self, metadata_merger, sample_artist):
        """Test merging artist metadata from multiple sources."""
        # Arrange
        spotify_data = {"genres": ["rock", "indie rock"]}
        musicbrainz_data = {
            "tags": [{"name": "alternative"}, {"name": "indie"}],
            "genres": [{"name": "rock"}],
        }
        lastfm_data = {
            "tags": {
                "tag": [
                    {"name": "indie"},
                    {"name": "alternative rock"},
                ]
            }
        }

        # Act
        result = metadata_merger.merge_artist_metadata(
            artist=sample_artist,
            spotify_data=spotify_data,
            musicbrainz_data=musicbrainz_data,
            lastfm_data=lastfm_data,
        )

        # Assert
        assert result.name == "Test Artist feat. Other Artist"  # Normalized
        assert len(result.genres) > 0
        assert len(result.tags) > 0

    def test_merge_album_metadata(self, metadata_merger, sample_album):
        """Test merging album metadata from multiple sources."""
        # Arrange
        musicbrainz_data = {
            "date": "2022-03-15",
            "tags": [{"name": "rock"}, {"name": "alternative"}],
        }
        lastfm_data = {
            "tags": {
                "tag": [
                    {"name": "indie"},
                ]
            }
        }

        # Act
        result = metadata_merger.merge_album_metadata(
            album=sample_album,
            musicbrainz_data=musicbrainz_data,
            lastfm_data=lastfm_data,
        )

        # Assert
        assert result.release_year == 2022
        assert "rock" in result.tags
        assert "indie" in result.tags
        assert result.metadata_sources["release_year"] == MetadataSource.MUSICBRAINZ.value

    def test_merge_album_metadata_invalid_date(
        self, metadata_merger, sample_album
    ):
        """Test merging album metadata with invalid date."""
        # Arrange
        musicbrainz_data = {
            "date": "invalid",
        }

        # Act
        result = metadata_merger.merge_album_metadata(
            album=sample_album,
            musicbrainz_data=musicbrainz_data,
        )

        # Assert
        assert result.release_year == 2020  # Original value preserved
