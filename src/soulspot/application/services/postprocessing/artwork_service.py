"""Artwork download and embedding service."""

import asyncio
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image as PILImage

from soulspot.config import Settings
from soulspot.domain.entities import Album, Track
from soulspot.infrastructure.security import PathValidator

logger = logging.getLogger(__name__)


class ArtworkService:
    """Service for downloading and embedding album artwork.

    This service:
    1. Downloads artwork from multiple sources (CoverArtArchive, Spotify)
    2. Resizes and optimizes images
    3. Saves artwork to disk
    4. Returns artwork data for embedding in audio files
    """

    # CoverArtArchive API base URL
    COVERART_API_BASE = "https://coverartarchive.org"

    def __init__(
        self,
        settings: Settings,
        spotify_client: Any | None = None,
        access_token: str | None = None,
    ) -> None:
        """Initialize artwork service.

        Args:
            settings: Application settings
            spotify_client: Optional Spotify client for artwork fallback
            access_token: Optional Spotify access token for API calls
        """
        self._settings = settings
        self._spotify_client = spotify_client
        self._access_token = access_token
        self._artwork_path = settings.storage.artwork_path
        self._max_size = settings.postprocessing.artwork_max_size
        self._quality = settings.postprocessing.artwork_quality

        # Ensure artwork directory exists
        self._artwork_path.mkdir(parents=True, exist_ok=True)

    def set_access_token(self, token: str) -> None:
        """Update the Spotify access token.

        Hey future me - this allows setting the token after construction,
        useful when the token is obtained asynchronously after service init.

        Args:
            token: Valid Spotify OAuth access token
        """
        self._access_token = token

    # Hey future me: Artwork downloading - the album art pipeline
    # WHY multiple sources? CoverArtArchive is free and high-quality, Spotify as fallback (needs auth token)
    # WHY resize images? A 5000x5000px JPEG is 15MB - overkill for ID3 tags (most players show 300x300)
    # GOTCHA: We save artwork to disk AND return bytes for embedding - might want to cache this
    async def download_artwork(
        self,
        track: Track,
        album: Album | None = None,
    ) -> bytes | None:
        """Download artwork for a track/album.

        Tries multiple sources in order:
        1. Cached artwork_url from DB (fastest - no API calls needed)
        2. CoverArtArchive (via MusicBrainz release ID)
        3. Spotify (via album/track Spotify URI)

        Args:
            track: Track entity
            album: Optional album entity

        Returns:
            Processed artwork data or None if not found
        """
        # Try cached artwork_url first (saves API calls!)
        # Hey future me - this is the fast path: if we already have the URL from a previous
        # Spotify sync, just download directly without hitting any API
        if album and album.artwork_url:
            logger.info(
                "Using cached artwork URL for album: %s (%s)",
                album.title,
                album.artwork_url[:50] + "..." if len(album.artwork_url) > 50 else album.artwork_url,
            )
            artwork_data = await self._download_from_url(album.artwork_url)
            if artwork_data:
                return artwork_data
            logger.warning(
                "Cached artwork URL failed for album %s, trying other sources",
                album.title,
            )

        # Try CoverArtArchive if we have a MusicBrainz ID
        if album and album.musicbrainz_id:
            logger.info(
                "Attempting to download artwork from CoverArtArchive for album: %s",
                album.title,
            )
            artwork_data = await self._download_from_coverart(album.musicbrainz_id)
            if artwork_data:
                return artwork_data

        # Try Spotify as fallback
        if self._spotify_client and album and album.spotify_uri:
            logger.info(
                "Attempting to download artwork from Spotify for album: %s",
                album.title,
            )
            artwork_data = await self._download_from_spotify(album.spotify_uri)
            if artwork_data:
                return artwork_data

        # Try Spotify track artwork as last resort
        if self._spotify_client and track.spotify_uri:
            logger.info(
                "Attempting to download artwork from Spotify track: %s", track.title
            )
            artwork_data = await self._download_from_spotify_track(track.spotify_uri)
            if artwork_data:
                return artwork_data

        logger.warning("No artwork found for track: %s", track.title)
        return None

    # Hey future me: Direct URL downloader - fastest path when we have cached URL from DB
    # This skips all API calls and just downloads from the CDN directly
    # Used when album.artwork_url is populated from previous Spotify sync
    async def _download_from_url(self, url: str) -> bytes | None:
        """Download artwork directly from a URL.

        Args:
            url: Direct URL to artwork image (e.g., Spotify CDN URL)

        Returns:
            Processed artwork data or None
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                image_data = response.content
                logger.debug("Downloaded %d bytes from cached URL", len(image_data))
                return await self._process_image(image_data)
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error downloading from cached URL: %s - %s", url, e)
            return None
        except Exception as e:
            logger.warning("Error downloading from cached URL: %s - %s", url, e)
            return None

    # Hey future me: CoverArtArchive downloader - free high-quality album art source
    # WHY /front endpoint? Gets front cover specifically (not back, booklet, etc)
    # follow_redirects=True because CAA returns 307 redirect to actual image URL
    # 404 is normal (album doesn't have artwork), don't spam error logs
    async def _download_from_coverart(self, release_id: str) -> bytes | None:
        """Download artwork from CoverArtArchive.

        Args:
            release_id: MusicBrainz release ID

        Returns:
            Processed artwork data or None
        """
        try:
            url = f"{self.COVERART_API_BASE}/release/{release_id}/front"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                image_data = response.content
                return await self._process_image(image_data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug("No artwork found on CoverArtArchive for: %s", release_id)
            else:
                logger.warning("Error downloading from CoverArtArchive: %s", e)
            return None
        except Exception as e:
            logger.exception("Error downloading artwork from CoverArtArchive: %s", e)
            return None

    # Yo Spotify album artwork - IMPLEMENTED!
    # WHY Spotify? Almost 100% coverage for albums - way better than CoverArtArchive
    # Spotify images array is sorted largest first (usually 640x640)
    # We extract album_id from the URI/URL, then fetch via Spotify API
    async def _download_from_spotify(self, album_uri: Any) -> bytes | None:
        """Download artwork from Spotify album.

        Args:
            album_uri: Spotify album URI (spotify:album:XXX) or ID

        Returns:
            Processed artwork data or None
        """
        if not self._spotify_client or not self._access_token:
            logger.debug(
                "Spotify client or access token not available for artwork download"
            )
            return None

        try:
            # Extract album ID from various URI formats
            album_id = self._extract_spotify_id(str(album_uri))
            if not album_id:
                logger.warning("Could not extract album ID from: %s", album_uri)
                return None

            # Fetch album data from Spotify
            album_data = await self._spotify_client.get_album(
                album_id, self._access_token
            )
            if not album_data:
                logger.debug("Album not found on Spotify: %s", album_id)
                return None

            # Extract image URL (largest first)
            images = album_data.get("images", [])
            if not images:
                logger.debug("No images found for album: %s", album_id)
                return None

            # Get largest image (first in array)
            image_url = images[0].get("url")
            if not image_url:
                return None

            # Download the image
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url, follow_redirects=True)
                response.raise_for_status()
                image_data = response.content
                logger.info(
                    "Downloaded artwork from Spotify for album: %s (%d bytes)",
                    album_data.get("name", album_id),
                    len(image_data),
                )
                return await self._process_image(image_data)

        except Exception as e:
            logger.warning("Error downloading artwork from Spotify: %s", e)
            return None

    # Listen, Spotify track artwork - tracks inherit album artwork
    # When album artwork fails, try getting it via the track's album reference
    async def _download_from_spotify_track(self, track_uri: Any) -> bytes | None:
        """Download artwork from Spotify track (via its album).

        Hey future me - tracks don't have their own artwork, they inherit from album.
        So we fetch the track, get its album, then download album artwork.

        Args:
            track_uri: Spotify track URI (spotify:track:XXX) or ID

        Returns:
            Processed artwork data or None
        """
        if not self._spotify_client or not self._access_token:
            return None

        try:
            # Extract track ID
            track_id = self._extract_spotify_id(str(track_uri))
            if not track_id:
                logger.warning("Could not extract track ID from: %s", track_uri)
                return None

            # Fetch track data to get album
            track_data = await self._spotify_client.get_track(
                track_id, self._access_token
            )
            if not track_data:
                return None

            # Get album from track
            album_data = track_data.get("album", {})
            images = album_data.get("images", [])
            if not images:
                return None

            # Download largest image
            image_url = images[0].get("url")
            if not image_url:
                return None

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url, follow_redirects=True)
                response.raise_for_status()
                image_data = response.content
                logger.info(
                    "Downloaded artwork from Spotify track: %s (%d bytes)",
                    track_data.get("name", track_id),
                    len(image_data),
                )
                return await self._process_image(image_data)

        except Exception as e:
            logger.warning("Error downloading track artwork from Spotify: %s", e)
            return None

    def _extract_spotify_id(self, uri_or_id: str) -> str | None:
        """Extract Spotify ID from various URI/URL formats.

        Hey future me - Spotify IDs come in many flavors:
        - spotify:album:1DFixLWuPkv3KT3TnV35m3
        - https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3
        - 1DFixLWuPkv3KT3TnV35m3 (just the ID)

        Args:
            uri_or_id: Spotify URI, URL, or plain ID

        Returns:
            Spotify ID or None if parsing failed
        """
        if not uri_or_id:
            return None

        uri_or_id = uri_or_id.strip()

        # Plain ID (22 char base62)
        if len(uri_or_id) == 22 and uri_or_id.isalnum():
            return uri_or_id

        # URI format: spotify:type:id
        if uri_or_id.startswith("spotify:"):
            parts = uri_or_id.split(":")
            if len(parts) >= 3:
                return parts[-1]

        # URL format: https://open.spotify.com/type/id
        if "open.spotify.com" in uri_or_id:
            parts = uri_or_id.rstrip("/").split("/")
            if parts:
                # Handle query params (?si=...)
                spotify_id = parts[-1].split("?")[0]
                return spotify_id

        # Fallback: assume it's the ID itself
        return uri_or_id if len(uri_or_id) >= 10 else None
            return None

    # Hey future me: Image processing - resize and optimize to keep file sizes sane
    # WHY asyncio.to_thread? PIL is SYNCHRONOUS and blocking - would freeze the event loop
    # WHY JPEG quality=85? Sweet spot between quality and file size (90+ is diminishing returns)
    # WHY Lanczos resampling? Best quality downscaling algorithm (slower but worth it)
    # GOTCHA: We convert all images to RGB - some PNGs with transparency will get black backgrounds
    # Hey async-to-sync wrapper - delegates to blocking PIL code in thread pool
    # WHY to_thread? PIL/Pillow is synchronous - would block event loop
    # Returns processed bytes ready for embedding
    async def _process_image(self, image_data: bytes) -> bytes:
        """Process and optimize image.

        Args:
            image_data: Raw image data

        Returns:
            Processed image data
        """
        # Run image processing in thread pool to avoid blocking
        return await asyncio.to_thread(self._process_image_sync, image_data)

    # Yo synchronous PIL image processing - the actual resize/optimize logic
    # WHY convert RGB? Some PNG with alpha channel - ID3 APIC doesn't support transparency
    # GOTCHA: Transparent backgrounds become BLACK after conversion
    # thumbnail() is in-place (modifies img) and maintains aspect ratio
    # optimize=True enables compression optimization (slower but smaller files)
    def _process_image_sync(self, image_data: bytes) -> bytes:
        """Synchronous image processing.

        Args:
            image_data: Raw image data

        Returns:
            Processed image data
        """
        try:
            # Open image
            img: PILImage.Image = PILImage.open(BytesIO(image_data))

            # Convert to RGB if necessary
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # Resize if larger than max size
            if max(img.size) > self._max_size:
                img.thumbnail(
                    (self._max_size, self._max_size), PILImage.Resampling.LANCZOS
                )
                logger.debug("Resized image to %s", img.size)

            # Save to buffer
            output = BytesIO()
            img.save(output, format="JPEG", quality=self._quality, optimize=True)
            return output.getvalue()

        except Exception as e:
            logger.exception("Error processing image: %s", e)
            # Return original if processing fails
            return image_data

    # Listen, artwork persistence - saves to disk with path validation
    # WHY validate path? SECURITY - prevent path traversal attacks
    # File named by album.id to avoid special chars in album names
    # asyncio.to_thread for write_bytes because filesystem I/O is blocking
    async def save_artwork(
        self,
        artwork_data: bytes,
        album: Album,
    ) -> Path:
        """Save artwork to disk.

        Args:
            artwork_data: Artwork image data
            album: Album entity

        Returns:
            Path to saved artwork file

        Raises:
            ValueError: If path validation fails
        """
        # Generate filename from album ID
        filename = f"{album.id.value}.jpg"
        filepath = self._artwork_path / filename

        # Validate path is within artwork directory (path traversal protection)
        validated_path = PathValidator.validate_image_file_path(
            filepath, self._artwork_path, resolve=False
        )

        # Save to disk
        await asyncio.to_thread(validated_path.write_bytes, artwork_data)
        logger.info("Saved artwork to: %s", validated_path)

        return validated_path
