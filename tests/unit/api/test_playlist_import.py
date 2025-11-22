"""Tests for playlist import endpoint URL/ID parsing."""
# AI-Model: Copilot

import pytest

from soulspot.api.routers.playlists import _extract_playlist_id
from soulspot.domain.exceptions import ValidationException


class TestExtractPlaylistId:
    """Test the _extract_playlist_id helper function."""

    def test_extract_from_full_url(self) -> None:
        """Test extracting playlist ID from full Spotify URL."""
        url = "https://open.spotify.com/playlist/2ZBCi09CSeWMBOoHZdN6Nl"
        result = _extract_playlist_id(url)
        assert result == "2ZBCi09CSeWMBOoHZdN6Nl"

    def test_extract_from_url_with_query_params(self) -> None:
        """Test extracting playlist ID from URL with query parameters."""
        url = "https://open.spotify.com/playlist/2ZBCi09CSeWMBOoHZdN6Nl?si=abc123"
        result = _extract_playlist_id(url)
        assert result == "2ZBCi09CSeWMBOoHZdN6Nl"

    def test_extract_from_bare_id(self) -> None:
        """Test that bare playlist IDs are returned as-is."""
        playlist_id = "2ZBCi09CSeWMBOoHZdN6Nl"
        result = _extract_playlist_id(playlist_id)
        assert result == "2ZBCi09CSeWMBOoHZdN6Nl"

    def test_extract_from_url_with_trailing_slash(self) -> None:
        """Test extracting from URL with trailing slash."""
        url = "https://open.spotify.com/playlist/2ZBCi09CSeWMBOoHZdN6Nl/"
        result = _extract_playlist_id(url)
        assert result == "2ZBCi09CSeWMBOoHZdN6Nl"

    def test_reject_track_url(self) -> None:
        """Test that track URLs are rejected (only playlists accepted)."""
        url = "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp"
        with pytest.raises(ValidationException, match="must be a playlist"):
            _extract_playlist_id(url)

    def test_reject_album_url(self) -> None:
        """Test that album URLs are rejected."""
        url = "https://open.spotify.com/album/6tbjWDEIzxoDsBA1FuhfPW"
        with pytest.raises(ValidationException, match="must be a playlist"):
            _extract_playlist_id(url)

    def test_non_spotify_url_rejected(self) -> None:
        """Test that non-Spotify URLs with protocol are rejected."""
        invalid_url = "https://example.com/not-a-spotify-url"
        # URLs with protocol ("://") are parsed, and non-Spotify ones are rejected
        with pytest.raises(ValidationException, match="Invalid Spotify URL"):
            _extract_playlist_id(invalid_url)

    def test_reject_malformed_spotify_url(self) -> None:
        """Test that malformed Spotify URLs are rejected."""
        malformed_url = "https://open.spotify.com/"
        with pytest.raises(ValidationException):
            _extract_playlist_id(malformed_url)
