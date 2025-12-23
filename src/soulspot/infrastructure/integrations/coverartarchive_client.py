"""CoverArtArchive HTTP client implementation.

Hey future me - CoverArtArchive (CAA) is THE official source for MusicBrainz album artwork!
It's a separate service from MusicBrainz but tightly integrated. CAA hosts high-resolution
cover art (up to 1200x1200) that anyone can use for FREE.

Key concepts:
- CAA uses MusicBrainz Release IDs or Release Group IDs to lookup artwork
- Release = specific pressing/edition (e.g., "US CD release", "Japanese vinyl")
- Release Group = abstract album concept (e.g., "Abbey Road" regardless of edition)
- Release Group URLs redirect to the "best" Release's artwork

Rate limiting:
- CAA is more lenient than MusicBrainz proper (no strict 1 req/sec)
- Still be nice: don't hammer them with hundreds of requests
- The API returns redirect URLs to actual images hosted on archive.org

Response format:
- GET /release/{mbid}/ returns JSON with images array
- Each image has: front/back/etc types, thumbnails (250/500px), and original URL
- GET /release/{mbid}/front returns redirect to front cover image directly

GOTCHA: Not all releases have artwork! Many older/indie releases have no CAA coverage.
Always handle 404s gracefully.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CoverArt:
    """Cover art image data from CoverArtArchive.

    Hey future me - this is a simple container for one piece of artwork!
    type_name tells you if it's "Front", "Back", "Booklet", etc.
    original_url is the full-res image (usually 1000x1000 or larger).
    thumbnail_250/500 are pre-sized versions for UI display.
    """

    image_id: str
    type_name: str  # "Front", "Back", "Booklet", "Medium", etc.
    original_url: str
    thumbnail_250: str  # 250x250 thumbnail URL
    thumbnail_500: str  # 500x500 thumbnail URL (often large enough!)
    is_front: bool = False
    is_back: bool = False
    comment: str | None = None


@dataclass
class CoverArtRelease:
    """All cover art for a MusicBrainz release.

    Hey future me - this wraps all images for one release (album).
    mbid is the MusicBrainz Release ID we looked up.
    images is list of all available artwork (may be empty!).
    front_url is convenience - the URL of the primary front cover if available.
    """

    mbid: str
    images: list[CoverArt]
    front_url: str | None = None
    front_thumbnail_500: str | None = None


class CoverArtArchiveClient:
    """HTTP client for CoverArtArchive API.

    Hey future me - this is how we get high-quality album artwork!
    CoverArtArchive is free, no API key required, and has great coverage
    for popular releases. Use MusicBrainz Release IDs to look up artwork.

    Usage:
        async with CoverArtArchiveClient() as client:
            # Get all artwork info
            release_art = await client.get_release_artwork(release_mbid)
            print(release_art.front_url)  # Direct link to front cover

            # Or get just the front cover URL directly
            front_url = await client.get_front_cover_url(release_mbid)

            # Can also use Release Group ID (gets "best" release's artwork)
            front_url = await client.get_release_group_front_cover(rg_mbid)
    """

    API_BASE_URL = "https://coverartarchive.org"

    # Hey future me - CAA doesn't have strict rate limits like MB,
    # but let's be nice and add a small delay between requests.
    # 200ms is plenty fast for user-facing operations.
    RATE_LIMIT_DELAY = 0.2

    def __init__(self) -> None:
        """Initialize CoverArtArchive client.

        No settings needed - CAA is completely free and public!
        """
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0.0
        self._rate_limit_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Hey future me - we need a custom User-Agent just like MusicBrainz!
        CAA is hosted by Archive.org and they like to know who's using their API.
        Follow redirects is important - CAA returns 307s to actual image URLs.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.API_BASE_URL,
                headers={
                    "User-Agent": "SoulSpot/1.0 (https://github.com/bozzfozz/soulspot)",
                    "Accept": "application/json",
                },
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _rate_limited_request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Make a rate-limited request to CoverArtArchive.

        Hey future me - even though CAA is lenient, we're nice citizens!
        This ensures we don't accidentally hammer their servers during
        bulk enrichment operations.
        """
        async with self._rate_limit_lock:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time

            if time_since_last < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)

            client = await self._get_client()
            response = await client.request(method, url, **kwargs)

            self._last_request_time = asyncio.get_event_loop().time()

            return response

    async def get_release_artwork(self, release_mbid: str) -> CoverArtRelease | None:
        """Get all artwork for a MusicBrainz Release.

        Hey future me - this is the main method! Returns ALL available artwork
        for a specific release (CD pressing, vinyl edition, etc.).

        Args:
            release_mbid: MusicBrainz Release ID (UUID format)

        Returns:
            CoverArtRelease with all images, or None if no artwork/not found.

        Example:
            artwork = await client.get_release_artwork("12345678-1234-1234-1234-123456789012")
            if artwork and artwork.front_url:
                download_image(artwork.front_url)
        """
        try:
            response = await self._rate_limited_request(
                "GET", f"/release/{release_mbid}/"
            )

            if response.status_code == 404:
                logger.debug(f"No artwork found for release {release_mbid}")
                return None

            response.raise_for_status()
            data = response.json()

            images: list[CoverArt] = []
            front_url: str | None = None
            front_thumbnail_500: str | None = None

            for img_data in data.get("images", []):
                # Parse image types (can have multiple like "Front" + "Medium")
                types = img_data.get("types", [])
                type_name = types[0] if types else "Unknown"
                is_front = "Front" in types
                is_back = "Back" in types

                # Get thumbnails dict
                thumbnails = img_data.get("thumbnails", {})

                image = CoverArt(
                    image_id=str(img_data.get("id", "")),
                    type_name=type_name,
                    original_url=img_data.get("image", ""),
                    thumbnail_250=thumbnails.get("250", thumbnails.get("small", "")),
                    thumbnail_500=thumbnails.get("500", thumbnails.get("large", "")),
                    is_front=is_front,
                    is_back=is_back,
                    comment=img_data.get("comment"),
                )
                images.append(image)

                # Track front cover for convenience
                if is_front and img_data.get("front", False):
                    front_url = image.original_url
                    front_thumbnail_500 = image.thumbnail_500

            return CoverArtRelease(
                mbid=release_mbid,
                images=images,
                front_url=front_url,
                front_thumbnail_500=front_thumbnail_500,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.warning(f"CAA HTTP error for release {release_mbid}: {e}")
            raise
        except Exception as e:
            logger.error(f"CAA error for release {release_mbid}: {e}")
            return None

    async def get_front_cover_url(self, release_mbid: str) -> str | None:
        """Get just the front cover URL for a release.

        Hey future me - use this when you ONLY need the front cover!
        It's more efficient than get_release_artwork() because we just
        do a HEAD request and check the redirect URL.

        Args:
            release_mbid: MusicBrainz Release ID

        Returns:
            Direct URL to front cover image, or None if not available.
        """
        try:
            # CAA's /front endpoint redirects to the actual image
            client = await self._get_client()

            async with self._rate_limit_lock:
                current_time = asyncio.get_event_loop().time()
                time_since_last = current_time - self._last_request_time

                if time_since_last < self.RATE_LIMIT_DELAY:
                    await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)

                # Use follow_redirects=False to get the redirect URL without downloading image
                response = await client.request(
                    "HEAD",
                    f"/release/{release_mbid}/front",
                    follow_redirects=False,
                )

                self._last_request_time = asyncio.get_event_loop().time()

            if response.status_code in (301, 302, 307, 308):
                return response.headers.get("Location")
            elif response.status_code == 404:
                return None

            response.raise_for_status()
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.debug(f"CAA front cover error for {release_mbid}: {e}")
            return None

    async def get_release_group_front_cover(
        self, release_group_mbid: str
    ) -> str | None:
        """Get front cover for a Release Group (album concept).

        Hey future me - Release Group is the ABSTRACT album (e.g., "Abbey Road")
        while Release is a specific pressing (US CD, UK vinyl, etc.).
        CAA picks the "best" release's artwork when you use release-group endpoint.

        This is useful when you have a MusicBrainz Album search result which
        returns Release Groups, not specific Releases.

        Args:
            release_group_mbid: MusicBrainz Release Group ID

        Returns:
            Direct URL to front cover, or None if not available.
        """
        try:
            client = await self._get_client()

            async with self._rate_limit_lock:
                current_time = asyncio.get_event_loop().time()
                time_since_last = current_time - self._last_request_time

                if time_since_last < self.RATE_LIMIT_DELAY:
                    await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)

                response = await client.request(
                    "HEAD",
                    f"/release-group/{release_group_mbid}/front",
                    follow_redirects=False,
                )

                self._last_request_time = asyncio.get_event_loop().time()

            if response.status_code in (301, 302, 307, 308):
                return response.headers.get("Location")
            elif response.status_code == 404:
                return None

            return None

        except Exception as e:
            logger.debug(f"CAA release-group error for {release_group_mbid}: {e}")
            return None

    async def get_front_cover_thumbnail(
        self, release_mbid: str, size: int = 500
    ) -> str | None:
        """Get front cover thumbnail URL at specific size.

        Hey future me - thumbnails are pre-generated by CAA at fixed sizes:
        250px, 500px, and 1200px. Use these instead of original for UI display!

        Args:
            release_mbid: MusicBrainz Release ID
            size: Thumbnail size (250, 500, or 1200)

        Returns:
            Direct URL to thumbnail, or None if not available.
        """
        if size not in (250, 500, 1200):
            size = 500  # Default to medium

        try:
            client = await self._get_client()

            async with self._rate_limit_lock:
                current_time = asyncio.get_event_loop().time()
                time_since_last = current_time - self._last_request_time

                if time_since_last < self.RATE_LIMIT_DELAY:
                    await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)

                response = await client.request(
                    "HEAD",
                    f"/release/{release_mbid}/front-{size}",
                    follow_redirects=False,
                )

                self._last_request_time = asyncio.get_event_loop().time()

            if response.status_code in (301, 302, 307, 308):
                return response.headers.get("Location")

            return None

        except Exception as e:
            logger.debug(f"CAA thumbnail error for {release_mbid}: {e}")
            return None

    async def __aenter__(self) -> "CoverArtArchiveClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
