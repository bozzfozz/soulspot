"""Metadata Service - Download and embed ID3/FLAC tags including cover artwork.

Hey future me - REFACTORED from ArtworkService (Nov 2025)!

Was macht der MetadataService?
- Lädt Cover-Artwork für Audio-Embedding (ID3/FLAC Tags)
- Verarbeitet Bilder (Resize, JPEG-Konvertierung)
- Multi-Provider: Cached URL → CoverArtArchive → Deezer → Spotify

WICHTIG: Dieser Service ist für AUDIO-METADATEN (ID3 Tags), nicht für UI-Bilder!
UI-Bilder (für die Webseite) werden vom ArtworkService verwaltet.

Flow:
  Track downloaded → MetadataService holt Cover → mutagen embeddet es in MP3/FLAC

Quellen (Fallback-Kette):
1. Cached artwork_url aus DB (schnellster Pfad)
2. CoverArtArchive (FREE, hochauflösend, via MusicBrainz ID)
3. Deezer (FREE, keine Auth nötig!)
4. Spotify (braucht OAuth)
"""

import asyncio
import logging
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image as PILImage

from soulspot.config import Settings
from soulspot.domain.entities import Album, Track
from soulspot.infrastructure.security import PathValidator

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class MetadataService:
    """Service for downloading and processing artwork for audio file embedding.

    Hey future me - dieser Service ist für ID3/FLAC-Tag-Embedding!
    
    NICHT verwechseln mit ArtworkService:
    - MetadataService = Artwork für AUDIO-DATEIEN (ID3 Tags)
    - ArtworkService = Bilder für UI (Webseite)

    Multi-Provider Fallback-Kette:
    1. Cached URL (DB) - schnellster Pfad
    2. CoverArtArchive - FREE, via MusicBrainz ID
    3. Deezer - FREE, keine OAuth nötig!
    4. Spotify - braucht OAuth
    """

    # CoverArtArchive API base URL
    COVERART_API_BASE = "https://coverartarchive.org"

    def __init__(
        self,
        settings: Settings,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
    ) -> None:
        """Initialize metadata service.

        Hey future me - jetzt mit Deezer-Fallback!
        Deezer ist FREE (keine OAuth nötig) - perfekt als Backup.

        Args:
            settings: Application settings
            spotify_plugin: Optional SpotifyPlugin for artwork fallback
            deezer_plugin: Optional DeezerPlugin for artwork fallback (NO AUTH!)
        """
        self._settings = settings
        self._spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin
        self._artwork_path = settings.storage.artwork_path
        self._max_size = settings.postprocessing.artwork_max_size
        self._quality = settings.postprocessing.artwork_quality

        # Ensure artwork directory exists
        self._artwork_path.mkdir(parents=True, exist_ok=True)

    def set_spotify_plugin(self, plugin: "SpotifyPlugin") -> None:
        """Update the Spotify plugin reference.

        Hey future me - allows setting the plugin after construction,
        useful when plugin is initialized asynchronously after service init.

        Args:
            plugin: Authenticated SpotifyPlugin instance
        """
        self._spotify_plugin = plugin

    def set_deezer_plugin(self, plugin: "DeezerPlugin") -> None:
        """Update the Deezer plugin reference.

        Args:
            plugin: DeezerPlugin instance (no auth needed!)
        """
        self._deezer_plugin = plugin

    async def download_artwork(
        self,
        track: Track,
        album: Album | None = None,
    ) -> bytes | None:
        """Download artwork for a track/album - MULTI-PROVIDER FALLBACK.

        Hey future me - jetzt mit Deezer als zusätzlicher Fallback!

        Fallback-Kette:
        1. Cached artwork_url from DB (fastest - no API calls needed)
        2. CoverArtArchive (via MusicBrainz release ID)
        3. Deezer (via album/artist search - FREE, NO AUTH!)
        4. Spotify (via album/track Spotify URI)

        Args:
            track: Track entity
            album: Optional album entity

        Returns:
            Processed artwork data (JPEG bytes) or None if not found
        """
        # 1. Try cached artwork_url first (saves API calls!)
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

        # 2. Try CoverArtArchive if we have a MusicBrainz ID
        if album and album.musicbrainz_id:
            logger.info(
                "Attempting to download artwork from CoverArtArchive for album: %s",
                album.title,
            )
            artwork_data = await self._download_from_coverart(album.musicbrainz_id)
            if artwork_data:
                return artwork_data

        # 3. NEW: Try Deezer (FREE - no auth needed!)
        if self._deezer_plugin and album:
            logger.info(
                "Attempting to download artwork from Deezer for album: %s",
                album.title,
            )
            artwork_data = await self._download_from_deezer(
                album_title=album.title,
                artist_name=track.artist_name if track else None,
            )
            if artwork_data:
                return artwork_data

        # 4. Try Spotify as fallback
        if self._spotify_plugin and album and album.spotify_uri:
            logger.info(
                "Attempting to download artwork from Spotify for album: %s",
                album.title,
            )
            artwork_data = await self._download_from_spotify(album.spotify_uri)
            if artwork_data:
                return artwork_data

        # 5. Try Spotify track artwork as last resort
        if self._spotify_plugin and track.spotify_uri:
            logger.info(
                "Attempting to download artwork from Spotify track: %s", track.title
            )
            artwork_data = await self._download_from_spotify_track(track.spotify_uri)
            if artwork_data:
                return artwork_data

        logger.warning("No artwork found for track: %s", track.title)
        return None

    async def _download_from_url(self, url: str) -> bytes | None:
        """Download artwork directly from a URL.

        Args:
            url: Direct URL to artwork image (e.g., Spotify/Deezer CDN URL)

        Returns:
            Processed artwork data or None
        """
        try:
            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            client = await HttpClientPool.get_client()
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            image_data = response.content
            logger.debug("Downloaded %d bytes from cached URL", len(image_data))
            return await self._process_image(image_data)
        except Exception as e:
            logger.warning("Error downloading from cached URL: %s - %s", url, e)
            return None

    async def _download_from_coverart(self, release_id: str) -> bytes | None:
        """Download artwork from CoverArtArchive.

        Hey future me - CoverArtArchive ist FREE und hochauflösend!
        Verwendet MusicBrainz Release ID für direkten Lookup.

        Args:
            release_id: MusicBrainz release ID

        Returns:
            Processed artwork data or None
        """
        try:
            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            url = f"{self.COVERART_API_BASE}/release/{release_id}/front"
            client = await HttpClientPool.get_client()
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            image_data = response.content
            return await self._process_image(image_data)
        except Exception as e:
            if hasattr(e, "response") and e.response.status_code == 404:
                logger.debug("No artwork found on CoverArtArchive for: %s", release_id)
            else:
                logger.warning("Error downloading from CoverArtArchive: %s", e)
            return None

    async def _download_from_deezer(
        self,
        album_title: str,
        artist_name: str | None = None,
    ) -> bytes | None:
        """Download artwork from Deezer - FREE, NO AUTH NEEDED!

        Hey future me - Deezer ist perfekt als Fallback!
        - Kein OAuth erforderlich
        - Hochauflösende Cover (cover_xl = 1000x1000)
        - Gute Suche auch für Compilation-Alben

        Args:
            album_title: Album title to search for
            artist_name: Optional artist name for better matching

        Returns:
            Processed artwork data or None
        """
        if not self._deezer_plugin:
            return None

        try:
            # Build search query
            search_query = album_title
            if artist_name:
                search_query = f"{artist_name} {album_title}"

            # Search for album on Deezer
            search_result = await self._deezer_plugin.search_albums(
                query=search_query, limit=5
            )

            if not search_result.items:
                logger.debug(f"No Deezer album found for '{album_title}'")
                return None

            # Find best match (prefer exact title match)
            best_match = None
            album_title_lower = album_title.lower().strip()

            for album_dto in search_result.items:
                if album_dto.title.lower().strip() == album_title_lower:
                    best_match = album_dto
                    break

            # Fallback to first result
            if not best_match:
                best_match = search_result.items[0]

            # Check if we have artwork URL
            if not best_match.artwork_url:
                logger.debug(f"Deezer album has no artwork: {best_match.title}")
                return None

            # Download artwork
            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            client = await HttpClientPool.get_client()
            response = await client.get(best_match.artwork_url, follow_redirects=True)
            response.raise_for_status()
            image_data = response.content

            logger.info(
                "Downloaded artwork from Deezer for album: %s (%d bytes)",
                best_match.title,
                len(image_data),
            )
            return await self._process_image(image_data)

        except Exception as e:
            logger.warning("Error downloading artwork from Deezer: %s", e)
            return None

    async def _download_from_spotify(self, album_uri: str) -> bytes | None:
        """Download artwork from Spotify album via SpotifyPlugin.

        Args:
            album_uri: Spotify album URI (spotify:album:XXX) or ID

        Returns:
            Processed artwork data or None
        """
        if not self._spotify_plugin:
            logger.debug("SpotifyPlugin not available for artwork download")
            return None

        try:
            album_id = self._extract_spotify_id(str(album_uri))
            if not album_id:
                logger.warning("Could not extract album ID from: %s", album_uri)
                return None

            album_dto = await self._spotify_plugin.get_album(album_id)

            if not album_dto.artwork_url:
                logger.debug("No artwork URL found for album: %s", album_id)
                return None

            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            client = await HttpClientPool.get_client()
            response = await client.get(album_dto.artwork_url, follow_redirects=True)
            response.raise_for_status()
            image_data = response.content
            logger.info(
                "Downloaded artwork from Spotify for album: %s (%d bytes)",
                album_dto.title,
                len(image_data),
            )
            return await self._process_image(image_data)

        except Exception as e:
            logger.warning("Error downloading artwork from Spotify: %s", e)
            return None

    async def _download_from_spotify_track(self, track_uri: str) -> bytes | None:
        """Download artwork from Spotify track (via its album).

        Args:
            track_uri: Spotify track URI (spotify:track:XXX) or ID

        Returns:
            Processed artwork data or None
        """
        if not self._spotify_plugin:
            return None

        try:
            track_id = self._extract_spotify_id(str(track_uri))
            if not track_id:
                logger.warning("Could not extract track ID from: %s", track_uri)
                return None

            track_dto = await self._spotify_plugin.get_track(track_id)

            if not track_dto.album_spotify_id:
                logger.debug("Track has no album reference: %s", track_id)
                return None

            album_dto = await self._spotify_plugin.get_album(track_dto.album_spotify_id)
            if not album_dto.artwork_url:
                return None

            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            client = await HttpClientPool.get_client()
            response = await client.get(album_dto.artwork_url, follow_redirects=True)
            response.raise_for_status()
            image_data = response.content
            logger.info(
                "Downloaded artwork from Spotify track: %s → album %s (%d bytes)",
                track_dto.title,
                album_dto.title,
                len(image_data),
            )
            return await self._process_image(image_data)

        except Exception as e:
            logger.warning("Error downloading track artwork from Spotify: %s", e)
            return None

    def _extract_spotify_id(self, uri_or_id: str) -> str | None:
        """Extract Spotify ID from various URI/URL formats.

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
                spotify_id = parts[-1].split("?")[0]
                return spotify_id

        return uri_or_id if len(uri_or_id) >= 10 else None

    async def _process_image(self, image_data: bytes) -> bytes:
        """Process and optimize image for ID3 embedding.

        Hey future me - konvertiert zu JPEG weil ID3 APIC kein PNG mit Alpha unterstützt!
        
        Args:
            image_data: Raw image data

        Returns:
            Processed JPEG image data
        """
        return await asyncio.to_thread(self._process_image_sync, image_data)

    def _process_image_sync(self, image_data: bytes) -> bytes:
        """Synchronous image processing.

        Args:
            image_data: Raw image data

        Returns:
            Processed JPEG image data
        """
        try:
            img: PILImage.Image = PILImage.open(BytesIO(image_data))

            # Convert to RGB (ID3 doesn't support alpha channel)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # Resize if larger than max size
            if max(img.size) > self._max_size:
                img.thumbnail(
                    (self._max_size, self._max_size), PILImage.Resampling.LANCZOS
                )
                logger.debug("Resized image to %s", img.size)

            # Save as JPEG
            output = BytesIO()
            img.save(output, format="JPEG", quality=self._quality, optimize=True)
            return output.getvalue()

        except Exception as e:
            logger.exception("Error processing image: %s", e)
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

        Raises:
            ValueError: If path validation fails
        """
        filename = f"{album.id.value}.jpg"
        filepath = self._artwork_path / filename

        validated_path = PathValidator.validate_image_file_path(
            filepath, self._artwork_path, resolve=False
        )

        await asyncio.to_thread(validated_path.write_bytes, artwork_data)
        logger.info("Saved artwork to: %s", validated_path)

        return validated_path


# Backward compatibility alias
# Hey future me - ArtworkService wurde zu MetadataService umbenannt!
# Dieser Alias stellt sicher, dass alter Code noch funktioniert.
ArtworkService = MetadataService
