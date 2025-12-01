"""MusicBrainz HTTP client implementation with rate limiting."""

import asyncio
from typing import Any, cast

import httpx

from soulspot.config.settings import MusicBrainzSettings
from soulspot.domain.ports import IMusicBrainzClient


class MusicBrainzClient(IMusicBrainzClient):
    """HTTP client for MusicBrainz API operations with rate limiting."""

    API_BASE_URL = "https://musicbrainz.org/ws/2"
    RATE_LIMIT_DELAY = 1.0  # 1 request per second as per MusicBrainz guidelines

    # Hey future me, MusicBrainz is STRICT about rate limiting - 1 req/sec, NO EXCEPTIONS!
    # That's why we track _last_request_time and have a lock. If you violate this, they'll
    # IP-ban you for hours (or days if you're really naughty). The lock ensures even with
    # concurrent requests, we stay compliant. Don't remove this thinking "oh we're not busy
    # enough" - you WILL get banned eventually!
    def __init__(self, settings: MusicBrainzSettings) -> None:
        """
        Initialize MusicBrainz client.

        Args:
            settings: MusicBrainz configuration settings
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0.0
        self._rate_limit_lock = asyncio.Lock()

    # Listen future me, MusicBrainz REQUIRES a User-Agent with your app name, version, AND
    # contact info. If you don't set this, they'll reject requests with 403. The contact is
    # so they can reach you if your app misbehaves (hammering their servers, etc.). Put a
    # real email or URL there! The format matters: "AppName/Version ( contact )" with those
    # exact spaces and parens. Don't ask me why, just do it.
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            # User-Agent is required by MusicBrainz
            user_agent = (
                f"{self.settings.app_name}/{self.settings.app_version} "
                f"( {self.settings.contact} )"
            )

            self._client = httpx.AsyncClient(
                base_url=self.API_BASE_URL,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    # Hey, same cleanup drill - close the client or leak connections. Use context manager!
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # Yo future me, this is THE CORE of our rate limiting. The lock ensures only one request
    # happens at a time, even from multiple coroutines. We calculate time since last request
    # and sleep if needed to hit exactly 1 req/sec. CRITICAL: We update _last_request_time
    # AFTER the request completes, not before! This accounts for slow requests. If you move
    # that line before the request, you'll accidentally speed up and violate the rate limit
    # when responses are slow. I learned this the hard way after getting IP-banned for 6 hours.
    async def _rate_limited_request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """
        Make a rate-limited request to MusicBrainz API.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: If the request fails
        """
        async with self._rate_limit_lock:
            # Ensure we respect the rate limit
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time

            if time_since_last < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)

            client = await self._get_client()
            response = await client.request(method, url, **kwargs)

            self._last_request_time = asyncio.get_event_loop().time()

            return response

    # Listen up, ISRC lookup is GOLD when it works but... ISRC codes aren't always in MB's
    # database. Even major label tracks sometimes missing! When found, MB returns a LIST of
    # recordings (same ISRC can have multiple versions - remasters, re-releases, etc.). We
    # just grab the first one which is usually the original/canonical version. If you need
    # to be more sophisticated, loop through all recordings and pick the best match. Also,
    # 404 means "ISRC not found" - that's normal, don't treat it as an error!
    async def lookup_recording_by_isrc(self, isrc: str) -> dict[str, Any] | None:
        """
        Lookup a recording by ISRC code.

        Args:
            isrc: International Standard Recording Code

        Returns:
            Recording information or None if not found

        Raises:
            httpx.HTTPError: If the request fails
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                "/isrc/" + isrc,
                params={"fmt": "json", "inc": "artists+releases"},
            )
            response.raise_for_status()
            data = response.json()

            # ISRC lookup returns a list of recordings
            if "recordings" in data and data["recordings"]:
                return cast(dict[str, Any], data["recordings"][0])

            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # Hey future me, MusicBrainz search uses Lucene query syntax. The quotes around artist
    # and title are IMPORTANT for exact phrase matching. Without quotes, "The Beatles" becomes
    # "the OR beatles" and you get garbage results. Search quality varies - common artists
    # are well-covered, obscure ones not so much. The results are sorted by relevance score
    # which is usually good, but sometimes returns live versions or covers first. If you need
    # better matching, grab more results (higher limit) and filter yourself based on artist
    # MBID or other criteria. Pro tip: MusicBrainz data is community-edited - sometimes the
    # artist name spelling is wrong or uses a variant (e.g., "Prince" vs "Prince and the
    # Revolution"). Be fuzzy in your matching!
    async def search_recording(
        self, artist: str, title: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search for recordings by artist and title.

        Args:
            artist: Artist name
            title: Track title
            limit: Maximum number of results

        Returns:
            List of recording matches

        Raises:
            httpx.HTTPError: If the request fails
        """
        # Build Lucene query
        query_parts = []
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if title:
            query_parts.append(f'recording:"{title}"')

        query = " AND ".join(query_parts)

        response = await self._rate_limited_request(
            "GET",
            "/recording",
            params={
                "query": query,
                "fmt": "json",
                "limit": limit,
            },
        )
        response.raise_for_status()
        data = response.json()

        return cast(list[dict[str, Any]], data.get("recordings", []))

    # Yo future me, "release" in MusicBrainz means a specific pressing/version of an album.
    # The same album can have dozens of releases (original CD, vinyl reissue, Japanese import,
    # digital download, etc.). We include "release-groups" in the response to get the parent
    # album concept. The "recordings" gives us track listings. Without these "inc" params,
    # you get minimal data - just title and MBID. Always specify what you need! Also, 404
    # here means the release_id doesn't exist or was merged/deleted - that's not an error!
    async def lookup_release(self, release_id: str) -> dict[str, Any] | None:
        """
        Lookup a release (album) by MusicBrainz ID.

        Args:
            release_id: MusicBrainz release ID

        Returns:
            Release information or None if not found

        Raises:
            httpx.HTTPError: If the request fails
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/release/{release_id}",
                params={
                    "fmt": "json",
                    "inc": "artists+recordings+release-groups",
                },
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # Hey, artist lookup is straightforward BUT artist data quality varies wildly. Big artists
    # (Beatles, Beyoncé) have tons of aliases, tags, and genre info. Obscure artists might
    # just have a name and country. Tags and genres are community-voted so they can be... weird.
    # Someone tagged "Metallica" as "cute" once (seriously). Don't trust tags blindly! Aliases
    # are super useful though - they include alternate names, legal names, name variations in
    # different languages, etc. Good for matching when user input doesn't exactly match MB.
    async def lookup_artist(self, artist_id: str) -> dict[str, Any] | None:
        """
        Lookup an artist by MusicBrainz ID.

        Args:
            artist_id: MusicBrainz artist ID

        Returns:
            Artist information or None if not found

        Raises:
            httpx.HTTPError: If the request fails
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/artist/{artist_id}",
                params={
                    "fmt": "json",
                    "inc": "aliases+tags+genres",
                },
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # Hey, use "async with MusicBrainzClient(...) as client:" for proper cleanup. Essential!
    async def __aenter__(self) -> "MusicBrainzClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # =============================================================================
    # COMPILATION DETECTION - Various Artists Verification
    # =============================================================================

    # MusicBrainz's official "Various Artists" MBID - this is THE canonical VA!
    # All true compilations reference this artist. If album's artist-credit contains
    # this ID, it's a compilation for sure. Lidarr uses this same approach.
    VARIOUS_ARTISTS_MBID = "89ad4ac3-39f7-470e-963a-56509c546377"

    async def lookup_release_group(
        self, release_group_id: str
    ) -> dict[str, Any] | None:
        """Lookup a release group (album concept) by MusicBrainz ID.

        Hey future me - release GROUP is the abstract "album" while release is a specific
        pressing/edition. Release groups have the "type" field we need for compilation detection!

        Args:
            release_group_id: MusicBrainz release group ID

        Returns:
            Release group info with type, or None if not found.
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/release-group/{release_group_id}",
                params={
                    "fmt": "json",
                    "inc": "artists+releases",
                },
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def search_release_group(
        self, artist: str | None, album: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Search for release groups (albums) by artist and title.

        Hey future me - this is how we verify compilations! Search for the album,
        check if result has "Compilation" in secondary-types or artist is Various Artists.

        Args:
            artist: Artist name (optional - useful for regular albums)
            album: Album title
            limit: Max results

        Returns:
            List of release group matches with type info.
        """
        # Build Lucene query
        query_parts = [f'releasegroup:"{album}"']
        if artist:
            query_parts.append(f'artist:"{artist}"')

        query = " AND ".join(query_parts)

        response = await self._rate_limited_request(
            "GET",
            "/release-group",
            params={
                "query": query,
                "fmt": "json",
                "limit": limit,
            },
        )
        response.raise_for_status()
        data = response.json()

        return cast(list[dict[str, Any]], data.get("release-groups", []))

    async def verify_compilation(
        self, album_title: str, album_artist: str | None = None
    ) -> dict[str, Any]:
        """Verify if an album is a compilation via MusicBrainz.

        Hey future me - this is the Phase 3 compilation verification!
        Call this for borderline cases (50-75% diversity) where local heuristics aren't sure.

        Detection methods (in order):
        1. Artist credit contains Various Artists MBID → True
        2. Release group secondary-type-list contains "Compilation" → True
        3. Primary-type is "Compilation" → True (rare but happens)
        4. Not found or no indicators → False (uncertain)

        Args:
            album_title: Album title to search
            album_artist: Optional artist name (helps narrow search)

        Returns:
            Dict with:
            - is_compilation: bool
            - confidence: float (0.0-1.0)
            - reason: str (mb_various_artists, mb_compilation_type, mb_not_found, etc.)
            - mbid: str | None (release group MBID if found)
            - match_score: int (0-100 from MusicBrainz search)
        """
        result: dict[str, Any] = {
            "is_compilation": False,
            "confidence": 0.0,
            "reason": "mb_not_searched",
            "mbid": None,
            "match_score": 0,
        }

        try:
            # Search for release group
            release_groups = await self.search_release_group(
                artist=album_artist,
                album=album_title,
                limit=5,
            )

            if not release_groups:
                result["reason"] = "mb_not_found"
                result["confidence"] = 0.3  # Low confidence - MB might just not have it
                return result

            # Check top result (highest score)
            top_match = release_groups[0]
            result["mbid"] = top_match.get("id")
            result["match_score"] = top_match.get("score", 0)

            # Check 1: Artist credit contains Various Artists
            artist_credit = top_match.get("artist-credit", [])
            for credit in artist_credit:
                artist_data = credit.get("artist", {})
                if artist_data.get("id") == self.VARIOUS_ARTISTS_MBID:
                    result["is_compilation"] = True
                    result["reason"] = "mb_various_artists"
                    result["confidence"] = 0.95
                    return result

            # Check 2: Secondary type is "Compilation"
            secondary_types = top_match.get("secondary-type-list", [])
            if "Compilation" in secondary_types:
                result["is_compilation"] = True
                result["reason"] = "mb_compilation_type"
                result["confidence"] = 0.9
                return result

            # Check 3: Primary type is "Compilation" (rare)
            primary_type = top_match.get("primary-type", "")
            if primary_type.lower() == "compilation":
                result["is_compilation"] = True
                result["reason"] = "mb_primary_compilation"
                result["confidence"] = 0.9
                return result

            # Not a compilation in MusicBrainz
            result["is_compilation"] = False
            result["reason"] = "mb_not_compilation"
            result["confidence"] = 0.8 if result["match_score"] >= 90 else 0.6
            return result

        except Exception as e:
            result["reason"] = f"mb_error: {type(e).__name__}"
            result["confidence"] = 0.0
            return result
