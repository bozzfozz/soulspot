"""Spotify HTTP client implementation with OAuth PKCE."""

import base64
import hashlib
import secrets
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from soulspot.config.settings import SpotifySettings
from soulspot.domain.ports import ISpotifyClient


class SpotifyClient(ISpotifyClient):
    """HTTP client for Spotify API operations with OAuth PKCE."""

    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"  # nosec B105 - this is a public API endpoint URL, not a password
    API_BASE_URL = "https://api.spotify.com/v1"

    # Hey future me, this init is deceptively simple - we DON'T create the HTTP client here
    # because we need to be async-friendly. The actual client gets lazy-loaded in _get_client().
    # If you try to create httpx.AsyncClient here, you'll get weird asyncio loop issues.
    def __init__(self, settings: SpotifySettings) -> None:
        """
        Initialize Spotify client.

        Args:
            settings: Spotify configuration settings
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    # Listen up, future me: This is our lazy HTTP client factory. Timeout is 30s because
    # Spotify can be SLOW sometimes, especially for playlist fetches with tons of tracks.
    # Don't reduce this timeout unless you like getting random timeouts on big playlists.
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    # Hey, this close() is IMPORTANT - if you don't call it, you'll leak connections and
    # eventually run out of file descriptors. Always use this client as an async context
    # manager (async with) or explicitly call close() in finally blocks. Trust me on this.
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # Yo future me, PKCE is that OAuth security dance Spotify requires. This generates a
    # random 32-byte code verifier. We strip the "=" padding because OAuth specs say so.
    # The verifier MUST be stored securely - if someone steals it during auth flow, they
    # can hijack the token exchange. Don't log this value or put it in URLs!
    @staticmethod
    def generate_code_verifier() -> str:
        """
        Generate a PKCE code verifier.

        Returns:
            Random code verifier string
        """
        return (
            base64.urlsafe_b64encode(secrets.token_bytes(32))
            .decode("utf-8")
            .rstrip("=")
        )

    # Hey, this is the other half of PKCE - we SHA256 hash the verifier to create the
    # challenge. The challenge goes in the auth URL (public), but only we know the verifier
    # (secret). Spotify will verify them later. Again, strip "=" padding for OAuth compliance.
    @staticmethod
    def generate_code_challenge(code_verifier: str) -> str:
        """
        Generate a PKCE code challenge from verifier.

        Args:
            code_verifier: Code verifier string

        Returns:
            SHA256 hash of code verifier as base64 URL-safe string
        """
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    # Listen future me, this builds the URL to send users to Spotify for auth. The scopes
    # listed here are MINIMAL - we only ask for read permissions. If you need write access
    # (like modifying playlists), you'll need to add more scopes. But remember: users get
    # scared by too many permissions, so only add what you actually need. The state param
    # prevents CSRF attacks - ALWAYS validate it matches when the user comes back!
    async def get_authorization_url(self, state: str, code_verifier: str) -> str:
        """
        Generate Spotify OAuth authorization URL.

        Args:
            state: State parameter for CSRF protection
            code_verifier: PKCE code verifier

        Returns:
            Authorization URL

        Raises:
            ValueError: If redirect_uri is not configured
        """
        # Hey future me, ALWAYS validate redirect_uri is set before building auth URL!
        # Empty redirect_uri causes cryptic Spotify errors. Better to fail fast here
        # with a clear message than let user hit Spotify's error page.
        if not self.settings.redirect_uri or not self.settings.redirect_uri.strip():
            raise ValueError(
                "SPOTIFY_REDIRECT_URI is not configured. "
                "Set it in .env to match your callback URL "
                "(e.g., http://localhost:8000/api/auth/callback)"
            )

        code_challenge = self.generate_code_challenge(code_verifier)

        params = {
            "client_id": self.settings.client_id,
            "response_type": "code",
            "redirect_uri": self.settings.redirect_uri,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            # Hey future me - we request ALL potentially useful scopes upfront!
            # This avoids re-auth later when new features need additional permissions.
            # User sees permission list once on initial auth, not repeatedly.
            #
            # SCOPES EXPLAINED:
            # - playlist-*: Read/write playlists (sync, create, modify)
            # - user-library-*: Read/write saved albums/tracks ("Your Library")
            # - user-follow-*: Read/write followed artists/users
            # - user-top-read: Top artists/tracks (for recommendations)
            # - user-read-recently-played: Recently played (for "Continue listening")
            "scope": " ".join(
                [
                    # Playlists
                    "playlist-read-private",
                    "playlist-read-collaborative",
                    "playlist-modify-private",
                    "playlist-modify-public",
                    # Library (Saved Albums/Tracks)
                    "user-library-read",
                    "user-library-modify",
                    # Follow (Artists/Users)
                    "user-follow-read",
                    "user-follow-modify",
                    # Listening History (for future features)
                    "user-top-read",
                    "user-read-recently-played",
                ]
            ),
        }

        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    # Yo future me, this is THE critical step after user auth. We send the code + verifier
    # to Spotify and get back tokens. IMPORTANT: This code is single-use and expires in 10
    # minutes! If the user takes forever on the auth screen, this will fail. Also, the
    # redirect_uri MUST match EXACTLY what we used in get_authorization_url(), or Spotify
    # will reject it. And yeah, it HAS to be form-urlencoded, not JSON. Don't ask why.
    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code
            code_verifier: PKCE code verifier

        Returns:
            Token response with access_token, refresh_token, expires_in

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
            "client_id": self.settings.client_id,
            "code_verifier": code_verifier,
        }

        response = await client.post(
            self.TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Hey future me, access tokens expire after 1 hour. This is how you get a new one without
    # making the user re-authorize. The refresh token is long-lived (usually doesn't expire).
    # BUT if the user revokes access or your app gets de-authorized, this will fail with 400.
    # Handle that gracefully by redirecting them back to the auth flow. Don't spam this
    # endpoint - only refresh when you actually need a new token, not preemptively!
    #
    # UPDATE: Now includes better error handling for invalid refresh tokens. Spotify returns
    # 400 Bad Request with error="invalid_grant" when refresh token is revoked. We raise
    # TokenRefreshException in this case to signal that re-authentication is required.
    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh access token using refresh token.

        When access token expires, use this method to get a new one without
        requiring user to log in again.

        Args:
            refresh_token: Refresh token from previous authentication

        Returns:
            Token response with:
            - access_token: New access token
            - token_type: Usually "Bearer"
            - expires_in: Seconds until expiration (usually 3600)
            - refresh_token: New refresh token (if Spotify rotated it, else absent)
            - scope: Granted scopes (space-separated)

        Raises:
            TokenRefreshException: If refresh token is invalid/revoked (requires re-auth)
            httpx.HTTPStatusError: For other HTTP errors (network, server issues)
        """
        from soulspot.domain.exceptions import TokenRefreshException

        client = await self._get_client()

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.client_id,
        }

        response = await client.post(
            self.TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Hey future me - check for invalid_grant BEFORE raise_for_status!
        # Spotify returns 400 with {"error": "invalid_grant"} when refresh token is revoked.
        # This is different from other 4xx errors - it specifically means re-auth is required.
        if response.status_code == 400:
            try:
                error_data = response.json()
                error_code = error_data.get("error", "")
                error_description = error_data.get(
                    "error_description", "Refresh token is invalid or has been revoked"
                )

                if error_code == "invalid_grant":
                    raise TokenRefreshException(
                        message=f"Refresh token invalid: {error_description}. Please re-authenticate with Spotify.",
                        error_code=error_code,
                        http_status=400,
                    )
            except (ValueError, KeyError):
                # JSON parsing failed, fall through to raise_for_status
                pass

        # For 401/403, also raise TokenRefreshException (access denied)
        if response.status_code in (401, 403):
            raise TokenRefreshException(
                message="Spotify access denied. Please re-authenticate with Spotify.",
                error_code="access_denied",
                http_status=response.status_code,
            )

        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Listen up, this fetches a playlist with ALL its details. Beware: Spotify paginates track
    # lists after 100 tracks. So if you have a massive playlist (500+ tracks), you'll only get
    # the first 100 here. You'll need to follow the 'next' URL in the response to get more.
    # This has bitten me before - don't assume you got everything! Also, private playlists
    # require the playlist-read-private scope or you'll get 403.
    async def get_playlist(self, playlist_id: str, access_token: str) -> dict[str, Any]:
        """
        Get playlist details.

        Args:
            playlist_id: Spotify playlist ID
            access_token: OAuth access token

        Returns:
            Playlist information including tracks

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.get(
            f"{self.API_BASE_URL}/playlists/{playlist_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Hey future me, this fetches the CURRENT USER's playlists using /me/playlists! It returns a
    # paginated response with 'items' array containing playlist metadata (no tracks yet - just names,
    # IDs, images, etc.). Spotify limits to max 50 playlists per request, so you MUST handle pagination
    # via 'next' URL or offset parameter if user has 100+ playlists. The 'total' field tells you how
    # many playlists exist total. Use this for the "sync playlist library" feature - fetch ALL user
    # playlists, store metadata in DB, then let user choose which to fully import with tracks!
    async def get_user_playlists(
        self, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """
        Get current user's playlists.

        Args:
            access_token: OAuth access token
            limit: Maximum number of playlists to return (1-50, default 50)
            offset: The index of the first playlist to return (for pagination)

        Returns:
            Paginated response with:
            - items: List of playlist objects (metadata only, no full track lists)
            - next: URL for next page (null if no more pages)
            - total: Total number of playlists
            - limit: Requested limit
            - offset: Requested offset

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        # Clamp limit to Spotify's max of 50
        limit = min(limit, 50)

        response = await client.get(
            f"{self.API_BASE_URL}/me/playlists",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Hey, straightforward track fetch. Nothing tricky here. But remember: if a track gets
    # removed from Spotify (regional licensing, artist request, etc.), this returns 404.
    # Don't panic - it's not a bug. Just handle it gracefully and mark the track as unavailable.
    async def get_track(self, track_id: str, access_token: str) -> dict[str, Any]:
        """
        Get track details.

        Args:
            track_id: Spotify track ID
            access_token: OAuth access token

        Returns:
            Track information

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.get(
            f"{self.API_BASE_URL}/tracks/{track_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Yo future me, Spotify search is... interesting. It uses their own query syntax with
    # operators like "artist:" and "album:". The default limit is 20 which is usually fine.
    # Pro tip: Search quality REALLY improves if you include artist name in the query.
    # Also, search results are ranked by "popularity" which doesn't always match what you
    # want - sometimes the obscure live version ranks higher than the studio version. Fun!
    async def search_track(
        self, query: str, access_token: str, limit: int = 20
    ) -> dict[str, Any]:
        """
        Search for tracks.

        Args:
            query: Search query
            access_token: OAuth access token
            limit: Maximum number of results

        Returns:
            Search results

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        params: dict[str, str | int] = {
            "q": query,
            "type": "track",
            "limit": limit,
        }

        response = await client.get(
            f"{self.API_BASE_URL}/search",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Hey future me, this fetches FULL artist details including images, genres, and popularity!
    # Unlike track data which only has artist name/ID, this gives you the complete artist object.
    # The images array typically has 3 sizes: 640x640, 320x320, 160x160. Pick medium (index 1)
    # for UI display. Genres come from Spotify's classification - useful for filtering/recommendations.
    # Popularity is 0-100 score based on recent streams - changes frequently. Use this when you need
    # artist metadata beyond just the name, like for the followed artists feature or artist pages!
    async def get_artist(self, artist_id: str, access_token: str) -> dict[str, Any]:
        """
        Get full artist details.

        Args:
            artist_id: Spotify artist ID
            access_token: OAuth access token

        Returns:
            Artist object with name, genres, images, popularity, etc.

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.get(
            f"{self.API_BASE_URL}/artists/{artist_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Yo future me, this is THE PERFORMANCE BOOSTER for playlist imports! Instead of fetching
    # artists one-by-one (100 artists = 100 API calls), we batch them up to 50 per request.
    # Spotify's /artists endpoint (plural!) accepts comma-separated IDs. This is CRITICAL for
    # large playlists - reduces import time from 30 seconds to 3 seconds! The response is an
    # object with "artists" array containing full artist objects (same as get_artist). IMPORTANT:
    # If an artist ID is invalid/deleted, Spotify returns null in that position - filter those out!
    # Max 50 IDs per request - if you need more, call this multiple times. Use this in playlist
    # import to fetch all unique artists in 1-2 calls instead of hundreds!
    async def get_several_artists(
        self, artist_ids: list[str], access_token: str
    ) -> list[dict[str, Any]]:
        """
        Get details for multiple artists in a single request (up to 50).

        Args:
            artist_ids: List of Spotify artist IDs (max 50)
            access_token: OAuth access token

        Returns:
            List of artist objects (nulls filtered out)

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        # Spotify API accepts comma-separated IDs, max 50
        if len(artist_ids) > 50:
            artist_ids = artist_ids[:50]

        ids_param = ",".join(artist_ids)

        response = await client.get(
            f"{self.API_BASE_URL}/artists",
            params={"ids": ids_param},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        result = cast(dict[str, Any], response.json())

        # Filter out null entries (deleted/invalid artists)
        artists = result.get("artists", [])
        return [artist for artist in artists if artist is not None]

    # Listen future me, this gets an artist's albums AND singles (hence include_groups).
    # Default limit is 50 but artists like Bob Dylan have 500+ releases (compilations, live,
    # etc.). You'll need pagination for prolific artists. Also, Spotify groups "appears_on"
    # separately - we DON'T include those here because that's features/compilations and would
    # flood the results. If you need those, add "appears_on" to include_groups. You've been
    # warned: it's a LOT of data for some artists!
    async def get_artist_albums(
        self, artist_id: str, access_token: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get albums for an artist.

        Args:
            artist_id: Spotify artist ID
            access_token: OAuth access token
            limit: Maximum number of albums to return

        Returns:
            List of album objects

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        params: dict[str, str | int] = {
            "include_groups": "album,single",
            "limit": limit,
        }

        response = await client.get(
            f"{self.API_BASE_URL}/artists/{artist_id}/albums",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        result = cast(dict[str, Any], response.json())
        return cast(list[dict[str, Any]], result.get("items", []))

    # Hey future me, this fetches the CURRENT USER's followed artists from Spotify! It uses the
    # /me/following endpoint with type=artist. Spotify paginates this with a cursor-based system
    # (not offset!). The "after" parameter is the last artist ID from previous page - use it to get
    # next batch. Limit is max 50 per request. Response has "artists.items" array (artist objects),
    # "artists.cursors.after" (next page cursor), and "artists.total" (total count). IMPORTANT: This
    # requires user-follow-read scope in OAuth, which we DON'T currently request! You'll need to add
    # that scope to get_authorization_url() or this will fail with 403. Use this for the "sync followed
    # artists" feature - fetch all artists user follows on Spotify, then create watchlists for them!
    async def get_followed_artists(
        self, access_token: str, limit: int = 50, after: str | None = None
    ) -> dict[str, Any]:
        """
        Get current user's followed artists.

        Args:
            access_token: OAuth access token
            limit: Maximum number of artists to return (1-50, default 50)
            after: The last artist ID retrieved from previous page (for pagination)

        Returns:
            Paginated response with:
            - artists.items: List of artist objects (name, id, genres, images, etc.)
            - artists.cursors.after: Cursor for next page (null if no more pages)
            - artists.total: Total number of followed artists
            - artists.limit: Requested limit

        Raises:
            httpx.HTTPError: If the request fails (403 if missing user-follow-read scope)
        """
        client = await self._get_client()

        # Clamp limit to Spotify's max of 50
        limit = min(limit, 50)

        params: dict[str, str | int] = {
            "type": "artist",
            "limit": limit,
        }

        if after:
            params["after"] = after

        response = await client.get(
            f"{self.API_BASE_URL}/me/following",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Hey future me, this fetches an artist's TOP TRACKS (most popular songs)! The market param is
    # required because Spotify tracks availability varies by country. Use ISO 3166-1 alpha-2 code
    # (e.g., "US", "DE", "GB"). Returns up to 10 tracks ranked by popularity. These are typically the
    # artist's most streamed songs - great for "best of" playlists or discovering singles. The tracks
    # returned include full details (album, duration, ISRC, etc.). GOTCHA: some of these tracks ARE
    # on albums - you'll need to filter by album_type="single" in the album object if you only want
    # standalone singles! Use this for the "sync artist songs" feature to get popular non-album tracks.
    async def get_artist_top_tracks(
        self, artist_id: str, access_token: str, market: str = "US"
    ) -> list[dict[str, Any]]:
        """Get an artist's top tracks (most popular songs).

        Args:
            artist_id: Spotify artist ID
            access_token: OAuth access token
            market: ISO 3166-1 alpha-2 country code (e.g., "US", "DE")

        Returns:
            List of track objects (up to 10 tracks, ranked by popularity)

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.get(
            f"{self.API_BASE_URL}/artists/{artist_id}/top-tracks",
            params={"market": market},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        result = cast(dict[str, Any], response.json())
        return cast(list[dict[str, Any]], result.get("tracks", []))

    # Hey future me, this fetches a SINGLE album with ALL details! The response includes tracks
    # (up to 50), images (3 sizes), artists, release date, UPC, label, etc. For albums with >50
    # tracks (rare, but happens for compilations), you'll need to use get_album_tracks() to fetch
    # the rest. The 'tracks' object in response has 'total' field - check it against 'items'
    # length. If they differ, there are more tracks to fetch. Use this when you need complete
    # album metadata for display or import. Tip: store the raw response in DB for debugging!
    async def get_album(self, album_id: str, access_token: str) -> dict[str, Any]:
        """
        Get single album by ID.

        Args:
            album_id: Spotify album ID
            access_token: OAuth access token

        Returns:
            Album information including tracks, images, etc.

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.get(
            f"{self.API_BASE_URL}/albums/{album_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Hey future me, this is the BATCH version for albums - same performance trick as get_several_artists!
    # Instead of 20 individual requests for 20 albums, we make ONE request. Spotify's /albums endpoint
    # accepts comma-separated IDs with max 20 per request. CRITICAL: If an album ID is invalid or was
    # removed (licensing, etc.), Spotify returns null in that array position - we filter those out!
    # Use this for "sync album library" or when processing playlist tracks to fetch all unique albums
    # efficiently. If you need >20 albums, call this multiple times in batches.
    async def get_albums(
        self, album_ids: list[str], access_token: str
    ) -> list[dict[str, Any]]:
        """
        Get details for multiple albums in a single request (up to 20).

        Args:
            album_ids: List of Spotify album IDs (max 20)
            access_token: OAuth access token

        Returns:
            List of album objects (nulls filtered out)

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        # Return empty list early if no IDs provided - avoids API error with empty ids param
        if not album_ids:
            return []

        # Spotify API accepts comma-separated IDs, max 20 for albums
        if len(album_ids) > 20:
            album_ids = album_ids[:20]

        ids_param = ",".join(album_ids)

        response = await client.get(
            f"{self.API_BASE_URL}/albums",
            params={"ids": ids_param},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        result = cast(dict[str, Any], response.json())

        # Filter out null entries (deleted/invalid albums)
        albums = result.get("albums", [])
        return [album for album in albums if album is not None]

    # Hey future me, this fetches album tracks with PAGINATION! Use this when an album has more than
    # 50 tracks (compilations, box sets, etc.) or when you only need tracks without full album metadata.
    # The response is paginated: 'items' has track objects, 'total' tells you total count, 'next' is URL
    # for next page. Limit max is 50, offset starts at 0. Tracks here are SIMPLIFIED - they don't have
    # full artist objects, just name/id. If you need full track details, use get_track() separately.
    # Pro tip: check 'total' vs returned 'items' length to know if you need more pages!
    async def get_album_tracks(
        self, album_id: str, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """
        Get album tracks with pagination.

        Args:
            album_id: Spotify album ID
            access_token: OAuth access token
            limit: Maximum number of tracks to return (max 50)
            offset: The index of the first track to return

        Returns:
            Paginated response with 'items' (tracks), 'total', 'next', 'limit', 'offset'

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        # Clamp limit to Spotify's max of 50
        limit = min(limit, 50)

        response = await client.get(
            f"{self.API_BASE_URL}/albums/{album_id}/tracks",
            params={"limit": limit, "offset": offset},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Hey future me, this fetches artists that are SIMILAR to a given artist! Spotify's recommendation
    # engine figures this out based on listener overlap, genre tags, and probably magic. Returns up to
    # 20 related artists - great for "fans also like" sections or discovery features. The returned artists
    # have full details (images, genres, popularity). GOTCHA: This endpoint has no pagination - you get
    # exactly what Spotify decides to return, usually 20 but sometimes fewer for niche artists. Also,
    # related artists can change over time as listening patterns evolve. Don't cache this forever!
    async def get_related_artists(
        self, artist_id: str, access_token: str
    ) -> list[dict[str, Any]]:
        """Get up to 20 artists similar to the given artist.

        Args:
            artist_id: Spotify artist ID
            access_token: OAuth access token

        Returns:
            List of artist objects with keys: id, name, genres, popularity, images

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()
        response = await client.get(
            f"{self.API_BASE_URL}/artists/{artist_id}/related-artists",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        result = cast(dict[str, Any], response.json())
        return cast(list[dict[str, Any]], result.get("artists", []))

    # Hey future me, this is artist search - like search_track but for artists! Use this when you need
    # to find artists by name, or let users browse/discover artists. The query supports Spotify's search
    # syntax so "genre:metal" works too. Default limit is 20 which is usually enough for autocomplete.
    # Returns paginated response with 'artists.items' containing artist objects. For exact name matches,
    # first result is usually the right one, but watch out for tribute bands and cover artists with
    # similar names! Pro tip: combine with get_artist for full details after user selects one.
    async def search_artist(
        self, query: str, access_token: str, limit: int = 20
    ) -> dict[str, Any]:
        """Search for artists on Spotify.

        Args:
            query: Search query
            access_token: OAuth access token
            limit: Maximum number of results

        Returns:
            Search results with 'artists' key containing items

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()
        params: dict[str, str | int] = {
            "q": query,
            "type": "artist",
            "limit": limit,
        }
        response = await client.get(
            f"{self.API_BASE_URL}/search",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # =========================================================================
    # USER LIBRARY: LIKED SONGS & SAVED ALBUMS
    # =========================================================================
    # Hey future me - these endpoints access the user's PERSONAL library!
    # - "Liked Songs" = tracks the user explicitly saved (the ❤️ button)
    # - "Saved Albums" = albums the user explicitly saved (saves all tracks)
    # Both use cursor-based pagination. Max 50 items per request.
    # IMPORTANT: Requires "user-library-read" scope!
    # =========================================================================

    async def get_saved_tracks(
        self, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """Get user's Liked Songs (saved tracks).

        This is the "Liked Songs" playlist that every Spotify user has.
        Returns tracks the user has explicitly saved with the heart button.

        Args:
            access_token: OAuth access token
            limit: Maximum number of tracks to return (1-50, default 50)
            offset: The index of the first item to return

        Returns:
            Paginated response with:
            - items: List of saved track objects, each containing:
              - added_at: Timestamp when user saved this track
              - track: Full track object with album, artists, etc.
            - next: URL for next page (null if no more)
            - total: Total number of saved tracks
            - limit/offset: Pagination parameters

        Raises:
            httpx.HTTPError: If the request fails

        Note:
            Requires "user-library-read" scope in OAuth flow.
        """
        client = await self._get_client()

        limit = min(limit, 50)

        response = await client.get(
            f"{self.API_BASE_URL}/me/tracks",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def get_saved_albums(
        self, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """Get user's Saved Albums.

        Returns albums the user has explicitly saved to their library.
        Different from artist albums - these are user-curated.

        Args:
            access_token: OAuth access token
            limit: Maximum number of albums to return (1-50, default 50)
            offset: The index of the first album to return

        Returns:
            Paginated response with:
            - items: List of saved album objects, each containing:
              - added_at: Timestamp when user saved this album
              - album: Full album object with artists, tracks, images
            - next: URL for next page (null if no more)
            - total: Total number of saved albums
            - limit/offset: Pagination parameters

        Raises:
            httpx.HTTPError: If the request fails

        Note:
            Requires "user-library-read" scope in OAuth flow.
        """
        client = await self._get_client()

        limit = min(limit, 50)

        response = await client.get(
            f"{self.API_BASE_URL}/me/albums",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    # Hey future me, these context manager methods let you use this client with
    # "async with SpotifyClient(...) as client:" syntax. This is THE preferred way
    # to use this client - it guarantees cleanup even if exceptions happen. Use it!
    async def __aenter__(self) -> "SpotifyClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
