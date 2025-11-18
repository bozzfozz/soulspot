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
    ) -> None:
        """Initialize artwork service.

        Args:
            settings: Application settings
            spotify_client: Optional Spotify client for artwork fallback
        """
        self._settings = settings
        self._spotify_client = spotify_client
        self._artwork_path = settings.storage.artwork_path
        self._max_size = settings.postprocessing.artwork_max_size
        self._quality = settings.postprocessing.artwork_quality

        # Ensure artwork directory exists
        self._artwork_path.mkdir(parents=True, exist_ok=True)

    async def download_artwork(
        self,
        track: Track,
        album: Album | None = None,
    ) -> bytes | None:
        """Download artwork for a track/album.

        Tries multiple sources in order:
        1. CoverArtArchive (via MusicBrainz release ID)
        2. Spotify (via album/track Spotify URI)

        Args:
            track: Track entity
            album: Optional album entity

        Returns:
            Processed artwork data or None if not found
        """
        # Try CoverArtArchive first if we have a MusicBrainz ID
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

    async def _download_from_spotify(self, album_uri: Any) -> bytes | None:
        """Download artwork from Spotify album.

        Args:
            album_uri: Spotify album URI

        Returns:
            Processed artwork data or None
        """
        if not self._spotify_client:
            return None

        try:
            # Extract album ID from URI format: spotify:album:XXXXX or https://open.spotify.com/album/XXXXX
            # album_id = str(album_uri).split(":")[-1]

            # This would require access token - stub for now
            # In production, this would:
            # 1. Call spotify_client.get_album(album_id, access_token)
            # 2. Extract image URLs from response['images'] (largest available)
            # 3. Download and process the image
            logger.debug(
                "Spotify artwork download not yet implemented for: %s", album_uri
            )
            return None
        except Exception as e:
            logger.exception("Error downloading artwork from Spotify: %s", e)
            return None

    async def _download_from_spotify_track(self, track_uri: Any) -> bytes | None:
        """Download artwork from Spotify track.

        Args:
            track_uri: Spotify track URI

        Returns:
            Processed artwork data or None
        """
        if not self._spotify_client:
            return None

        try:
            # Extract track ID from URI
            # track_id = str(track_uri).split(":")[-1]

            # Stub for Spotify track artwork
            logger.debug(
                "Spotify track artwork download not yet implemented for: %s", track_uri
            )
            return None
        except Exception as e:
            logger.exception("Error downloading track artwork from Spotify: %s", e)
            return None

    async def _process_image(self, image_data: bytes) -> bytes:
        """Process and optimize image.

        Args:
            image_data: Raw image data

        Returns:
            Processed image data
        """
        # Run image processing in thread pool to avoid blocking
        return await asyncio.to_thread(self._process_image_sync, image_data)

    def _process_image_sync(self, image_data: bytes) -> bytes:
        """Synchronous image processing.

        Args:
            image_data: Raw image data

        Returns:
            Processed image data
        """
        try:
            # Open image
            img = PILImage.open(BytesIO(image_data))

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
        """
        # Generate filename from album ID
        filename = f"{album.id.value}.jpg"
        filepath = self._artwork_path / filename

        # Save to disk
        await asyncio.to_thread(filepath.write_bytes, artwork_data)
        logger.info("Saved artwork to: %s", filepath)

        return filepath
