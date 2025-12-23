"""Circuit breaker wrappers for external integration clients."""

import logging
from typing import Any, cast

from soulspot.config.settings import Settings
from soulspot.domain.ports import IMusicBrainzClient, ISlskdClient, ISpotifyClient
from soulspot.infrastructure.observability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)

logger = logging.getLogger(__name__)


class CircuitBreakerSlskdClient(ISlskdClient):
    """slskd client with circuit breaker protection."""

    # Hey future me, this is a DECORATOR PATTERN wrapper around the real slskd client. The
    # circuit breaker protects us from hammering a dead/slow slskd service. If slskd goes down
    # or starts timing out, the breaker "opens" and fails fast instead of waiting 30s per request.
    # The config values (failure_threshold, etc.) come from settings - tweak those in .env if
    # you're getting too many false opens or not opening fast enough when things actually fail.
    def __init__(self, client: ISlskdClient, settings: Settings) -> None:
        """
        Initialize circuit breaker wrapper for slskd client.

        Args:
            client: Underlying slskd client implementation
            settings: Application settings with circuit breaker configuration
        """
        self._client = client
        self._circuit_breaker = CircuitBreaker(
            name="slskd-api",
            config=CircuitBreakerConfig(
                failure_threshold=settings.observability.circuit_breaker.failure_threshold,
                success_threshold=settings.observability.circuit_breaker.success_threshold,
                timeout=settings.observability.circuit_breaker.timeout,
                reset_timeout=settings.observability.circuit_breaker.reset_timeout,
            ),
        )

    # Listen up, all these wrapper methods follow the same pattern: call the real client
    # through the circuit breaker. If the breaker is OPEN (too many recent failures), it
    # raises CircuitBreakerOpenError immediately without even trying the request. This is
    # GOOD - fail fast, don't waste time! The cast() is for type checking - the breaker
    # returns Any but we know what type it actually is. This pattern repeats for every method.
    async def search(self, query: str, timeout: int = 30) -> list[dict[str, Any]]:
        """Search for files on the Soulseek network."""
        result = await self._circuit_breaker.call(
            self._client.search,
            query=query,
            timeout=timeout,
        )
        return cast(list[dict[str, Any]], result)

    async def download(self, username: str, filename: str) -> str:
        """Start a download from a user."""
        result = await self._circuit_breaker.call(
            self._client.download,
            username=username,
            filename=filename,
        )
        return cast(str, result)

    async def get_download_status(self, download_id: str) -> dict[str, Any]:
        """Get the status of a download."""
        result = await self._circuit_breaker.call(
            self._client.get_download_status,
            download_id=download_id,
        )
        return cast(dict[str, Any], result)

    async def list_downloads(self) -> list[dict[str, Any]]:
        """List all downloads."""
        result = await self._circuit_breaker.call(self._client.list_downloads)
        return cast(list[dict[str, Any]], result)

    async def cancel_download(self, download_id: str) -> None:
        """Cancel a download."""
        await self._circuit_breaker.call(
            self._client.cancel_download,
            download_id=download_id,
        )

    async def close(self) -> None:
        """Close the underlying client."""
        if hasattr(self._client, "close"):
            await self._client.close()

    async def __aenter__(self) -> "CircuitBreakerSlskdClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


class CircuitBreakerSpotifyClient(ISpotifyClient):
    """Spotify client with circuit breaker protection."""

    def __init__(self, client: ISpotifyClient, settings: Settings) -> None:
        """
        Initialize circuit breaker wrapper for Spotify client.

        Args:
            client: Underlying Spotify client implementation
            settings: Application settings with circuit breaker configuration
        """
        self._client = client
        self._circuit_breaker = CircuitBreaker(
            name="spotify-api",
            config=CircuitBreakerConfig(
                failure_threshold=settings.observability.circuit_breaker.failure_threshold,
                success_threshold=settings.observability.circuit_breaker.success_threshold,
                timeout=settings.observability.circuit_breaker.timeout,
                reset_timeout=settings.observability.circuit_breaker.reset_timeout,
            ),
        )

    async def get_authorization_url(self, state: str, code_verifier: str) -> str:
        """Generate Spotify OAuth authorization URL."""
        result = await self._circuit_breaker.call(
            self._client.get_authorization_url,
            state=state,
            code_verifier=code_verifier,
        )
        return cast(str, result)

    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        result = await self._circuit_breaker.call(
            self._client.exchange_code,
            code=code,
            code_verifier=code_verifier,
        )
        return cast(dict[str, Any], result)

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh access token."""
        result = await self._circuit_breaker.call(
            self._client.refresh_token,
            refresh_token=refresh_token,
        )
        return cast(dict[str, Any], result)

    async def get_playlist(self, playlist_id: str, access_token: str) -> dict[str, Any]:
        """Get playlist details."""
        result = await self._circuit_breaker.call(
            self._client.get_playlist,
            playlist_id=playlist_id,
            access_token=access_token,
        )
        return cast(dict[str, Any], result)

    async def get_track(self, track_id: str, access_token: str) -> dict[str, Any]:
        """Get track details."""
        result = await self._circuit_breaker.call(
            self._client.get_track,
            track_id=track_id,
            access_token=access_token,
        )
        return cast(dict[str, Any], result)

    async def search_track(
        self, query: str, access_token: str, limit: int = 20
    ) -> dict[str, Any]:
        """Search for tracks."""
        result = await self._circuit_breaker.call(
            self._client.search_track,
            query=query,
            access_token=access_token,
            limit=limit,
        )
        return cast(dict[str, Any], result)

    async def get_user_playlists(
        self, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """
        Get current user's playlists.

        Args:
            access_token: OAuth access token
            limit: Maximum number of playlists to return (max 50)
            offset: The index of the first playlist to return

        Returns:
            Paginated list of user's playlists with 'items', 'next', 'total' fields
        """
        result = await self._circuit_breaker.call(
            self._client.get_user_playlists,
            access_token=access_token,
            limit=limit,
            offset=offset,
        )
        return cast(dict[str, Any], result)

    async def get_followed_artists(
        self, access_token: str, limit: int = 50, after: str | None = None
    ) -> dict[str, Any]:
        """
        Get current user's followed artists.

        Args:
            access_token: OAuth access token
            limit: Maximum number of artists to return (max 50)
            after: The last artist ID retrieved from previous page (for pagination)

        Returns:
            Paginated response with 'artists' containing 'items', 'cursors', and 'total' fields
        """
        result = await self._circuit_breaker.call(
            self._client.get_followed_artists,
            access_token=access_token,
            limit=limit,
            after=after,
        )
        return cast(dict[str, Any], result)

    # Hey future me, these album methods were added for Phase 1 of the Spotify Album Roadmap.
    # They follow the same circuit breaker pattern as all other methods - wrap the call,
    # let the breaker handle failures, and cast the result. If you need to debug album
    # fetching issues, check the circuit breaker state first - it might be open!

    async def get_album(self, album_id: str, access_token: str) -> dict[str, Any]:
        """
        Get single album by ID.

        Args:
            album_id: Spotify album ID
            access_token: OAuth access token

        Returns:
            Album object with tracks, images, etc.
        """
        result = await self._circuit_breaker.call(
            self._client.get_album,
            album_id=album_id,
            access_token=access_token,
        )
        return cast(dict[str, Any], result)

    async def get_albums(
        self, album_ids: list[str], access_token: str
    ) -> list[dict[str, Any]]:
        """
        Batch fetch up to 20 albums by IDs.

        Args:
            album_ids: List of Spotify album IDs (max 20)
            access_token: OAuth access token

        Returns:
            List of album objects (nulls filtered out)
        """
        result = await self._circuit_breaker.call(
            self._client.get_albums,
            album_ids=album_ids,
            access_token=access_token,
        )
        return cast(list[dict[str, Any]], result)

    async def get_album_tracks(
        self, album_id: str, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """
        Get album tracks with pagination.

        Args:
            album_id: Spotify album ID
            access_token: OAuth access token
            limit: Maximum number of tracks (max 50)
            offset: The index of the first track

        Returns:
            Paginated list of tracks with 'items', 'next', 'total' fields
        """
        result = await self._circuit_breaker.call(
            self._client.get_album_tracks,
            album_id=album_id,
            access_token=access_token,
            limit=limit,
            offset=offset,
        )
        return cast(dict[str, Any], result)

    async def get_artist(self, artist_id: str, access_token: str) -> dict[str, Any]:
        """Get detailed artist information including popularity and followers."""
        result = await self._circuit_breaker.call(
            self._client.get_artist,
            artist_id=artist_id,
            access_token=access_token,
        )
        return cast(dict[str, Any], result)

    async def get_several_artists(
        self, artist_ids: list[str], access_token: str
    ) -> list[dict[str, Any]]:
        """Get details for multiple artists in a single request (up to 50)."""
        result = await self._circuit_breaker.call(
            self._client.get_several_artists,
            artist_ids=artist_ids,
            access_token=access_token,
        )
        return cast(list[dict[str, Any]], result)

    async def get_artist_albums(
        self, artist_id: str, access_token: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get albums for an artist."""
        result = await self._circuit_breaker.call(
            self._client.get_artist_albums,
            artist_id=artist_id,
            access_token=access_token,
            limit=limit,
        )
        return cast(list[dict[str, Any]], result)

    async def get_artist_top_tracks(
        self, artist_id: str, access_token: str, market: str = "US"
    ) -> list[dict[str, Any]]:
        """Get artist's top 10 tracks by popularity."""
        result = await self._circuit_breaker.call(
            self._client.get_artist_top_tracks,
            artist_id=artist_id,
            access_token=access_token,
            market=market,
        )
        return cast(list[dict[str, Any]], result)

    async def get_related_artists(
        self, artist_id: str, access_token: str
    ) -> list[dict[str, Any]]:
        """Get up to 20 artists similar to the given artist."""
        result = await self._circuit_breaker.call(
            self._client.get_related_artists,
            artist_id=artist_id,
            access_token=access_token,
        )
        return cast(list[dict[str, Any]], result)

    async def search_artist(
        self, query: str, access_token: str, limit: int = 20
    ) -> dict[str, Any]:
        """Search for artists on Spotify."""
        result = await self._circuit_breaker.call(
            self._client.search_artist,
            query=query,
            access_token=access_token,
            limit=limit,
        )
        return cast(dict[str, Any], result)

    # =========================================================================
    # USER FOLLOWS: FOLLOW/UNFOLLOW ARTISTS
    # =========================================================================

    async def follow_artist(self, artist_ids: list[str], access_token: str) -> None:
        """Follow one or more artists on Spotify."""
        await self._circuit_breaker.call(
            self._client.follow_artist,
            artist_ids=artist_ids,
            access_token=access_token,
        )

    async def unfollow_artist(self, artist_ids: list[str], access_token: str) -> None:
        """Unfollow one or more artists on Spotify."""
        await self._circuit_breaker.call(
            self._client.unfollow_artist,
            artist_ids=artist_ids,
            access_token=access_token,
        )

    async def check_if_following_artists(
        self, artist_ids: list[str], access_token: str
    ) -> list[bool]:
        """Check if user follows one or more artists."""
        result = await self._circuit_breaker.call(
            self._client.check_if_following_artists,
            artist_ids=artist_ids,
            access_token=access_token,
        )
        return cast(list[bool], result)

    async def close(self) -> None:
        """Close the underlying client."""
        if hasattr(self._client, "close"):
            await self._client.close()

    async def __aenter__(self) -> "CircuitBreakerSpotifyClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


class CircuitBreakerMusicBrainzClient(IMusicBrainzClient):
    """MusicBrainz client with circuit breaker protection."""

    def __init__(self, client: IMusicBrainzClient, settings: Settings) -> None:
        """
        Initialize circuit breaker wrapper for MusicBrainz client.

        Args:
            client: Underlying MusicBrainz client implementation
            settings: Application settings with circuit breaker configuration
        """
        self._client = client
        self._circuit_breaker = CircuitBreaker(
            name="musicbrainz-api",
            config=CircuitBreakerConfig(
                failure_threshold=settings.observability.circuit_breaker.failure_threshold,
                success_threshold=settings.observability.circuit_breaker.success_threshold,
                timeout=settings.observability.circuit_breaker.timeout,
                reset_timeout=settings.observability.circuit_breaker.reset_timeout,
            ),
        )

    async def lookup_recording_by_isrc(self, isrc: str) -> dict[str, Any] | None:
        """Lookup a recording by ISRC code."""
        result = await self._circuit_breaker.call(
            self._client.lookup_recording_by_isrc,
            isrc=isrc,
        )
        return cast(dict[str, Any] | None, result)

    async def search_recording(
        self, artist: str, title: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Search for recordings by artist and title."""
        result = await self._circuit_breaker.call(
            self._client.search_recording,
            artist=artist,
            title=title,
            limit=limit,
        )
        return cast(list[dict[str, Any]], result)

    async def lookup_release(self, release_id: str) -> dict[str, Any] | None:
        """Lookup a release (album) by MusicBrainz ID."""
        result = await self._circuit_breaker.call(
            self._client.lookup_release,
            release_id=release_id,
        )
        return cast(dict[str, Any] | None, result)

    async def lookup_artist(self, artist_id: str) -> dict[str, Any] | None:
        """Lookup an artist by MusicBrainz ID."""
        result = await self._circuit_breaker.call(
            self._client.lookup_artist,
            artist_id=artist_id,
        )
        return cast(dict[str, Any] | None, result)

    async def close(self) -> None:
        """Close the underlying client."""
        if hasattr(self._client, "close"):
            await self._client.close()

    async def __aenter__(self) -> "CircuitBreakerMusicBrainzClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
