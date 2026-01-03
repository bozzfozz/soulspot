"""Auto-Fetch Service - Background fetching for images, albums, and tracks.

Hey future me - this is the CENTRAL service for all auto-fetch operations!
It handles:
1. Background image fetching for artists without images
2. Background cover fetching for albums without covers
3. Background track fetching for albums without tracks
4. Background discography fetching for artists

CRITICAL: This service belongs in the APPLICATION LAYER!
UI routes should call this service, NOT implement fetch logic themselves.

REFACTORED (Dec 2025): Uses modern repair functions directly from images/repair.py,
not the deprecated ImageRepairService wrapper!

Architecture:
  API (ui.py) → AutoFetchService → repair_artist_images() / repair_album_images()
                                 → ArtistService
                                 → Infrastructure (DB, API Clients)

Usage from routes:
```python
from soulspot.application.services.auto_fetch_service import AutoFetchService

# In route:
auto_fetch = AutoFetchService(session, settings)
await auto_fetch.fetch_missing_artist_images(limit=10)
await auto_fetch.fetch_missing_album_covers(limit=10)
await auto_fetch.fetch_artist_discography(artist_id, include_tracks=True)
```
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.config.settings import Settings

logger = logging.getLogger(__name__)


class AutoFetchService:
    """Service for background auto-fetching of missing data.

    Hey future me - this centralizes all auto-fetch logic that was
    previously scattered across UI routes!

    Features:
    - Batch image repair for artists/albums
    - Discography sync with tracks
    - All operations are idempotent (safe to call multiple times)
    - Graceful failure (logs errors but doesn't crash)
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize the auto-fetch service.

        Args:
            session: Database session for queries and updates
            settings: Application settings (for image paths, etc.)
        """
        self._session = session
        self._settings = settings

    async def fetch_missing_artist_images(
        self,
        limit: int = 10,
        use_api: bool = True,
    ) -> dict[str, Any]:
        """Fetch missing images for artists without image_url OR image_path.

        Hey future me - TWO MODES:
        1. use_api=True (DEFAULT): Uses Deezer API to FIND missing images
           - Artists without image_url → Search Deezer → Get URL → Download
           - Artists with image_url but no image_path → Download from URL
        2. use_api=False (fast): Only downloads from existing URLs
           - Only processes artists that already have image_url
           - Faster but finds less images

        REFACTORED (Dec 2025): Now uses modern repair functions directly,
        not the deprecated ImageRepairService wrapper!

        Args:
            limit: Maximum artists to process per call
            use_api: Whether to use Deezer API to find missing images

        Returns:
            Dict with stats: {"processed": int, "repaired": int, "errors": int}
        """
        try:
            # Use modern repair function directly (not deprecated wrapper!)
            from soulspot.application.services.images import ImageService
            from soulspot.application.services.images.repair import (
                repair_artist_images,
            )

            image_service = ImageService(
                cache_base_path=str(self._settings.storage.image_path),
                local_serve_prefix="/api/images",
            )

            # Create ImageProviderRegistry if API mode enabled
            image_provider_registry = None
            if use_api:
                from soulspot.application.services.images.image_provider_registry import (
                    ImageProviderRegistry,
                )
                from soulspot.infrastructure.plugins import DeezerPlugin
                from soulspot.infrastructure.providers.deezer_image_provider import (
                    DeezerImageProvider,
                )

                # Create Deezer provider (NO AUTH NEEDED!)
                deezer_plugin = DeezerPlugin()
                deezer_provider = DeezerImageProvider(deezer_plugin)

                # Create registry with Deezer provider
                image_provider_registry = ImageProviderRegistry()
                image_provider_registry.register(deezer_provider, priority=1)
                logger.debug("[AUTO_FETCH] Using Deezer API for artist image lookup")

            # Call modern function directly (no deprecated wrapper!)
            result = await repair_artist_images(
                session=self._session,
                image_service=image_service,
                image_provider_registry=image_provider_registry,
                spotify_plugin=None,
                limit=limit,
            )
            repaired = result.get("repaired", 0)

            if repaired > 0:
                logger.info(
                    f"[AUTO_FETCH] Repaired {repaired} artist images in background"
                )

            return result

        except Exception as e:
            logger.debug(f"[AUTO_FETCH] Artist image fetch failed: {e}")
            return {"processed": 0, "repaired": 0, "errors": 1, "error": str(e)}

    async def fetch_missing_album_covers(
        self,
        limit: int = 10,
        use_api: bool = True,
    ) -> dict[str, Any]:
        """Fetch missing covers for albums without cover_url OR cover_path.

        Hey future me - TWO MODES:
        1. use_api=True (DEFAULT): Uses Deezer API to FIND missing covers
           - Albums without cover_url → Search Deezer → Get URL → Download
           - Albums with cover_url but no cover_path → Download from URL
        2. use_api=False (fast): Only downloads from existing URLs
           - Only processes albums that already have cover_url
           - Faster but finds less covers

        REFACTORED (Dec 2025): Now uses modern repair functions directly,
        not the deprecated ImageRepairService wrapper!

        Args:
            limit: Maximum albums to process per call
            use_api: Whether to use Deezer API to find missing covers

        Returns:
            Dict with stats: {"processed": int, "repaired": int, "errors": int}
        """
        try:
            # Use modern repair function directly (not deprecated wrapper!)
            from soulspot.application.services.images import ImageService
            from soulspot.application.services.images.repair import (
                repair_album_images,
            )

            image_service = ImageService(
                cache_base_path=str(self._settings.storage.image_path),
                local_serve_prefix="/api/images",
            )

            # Create ImageProviderRegistry if API mode enabled
            image_provider_registry = None
            if use_api:
                from soulspot.application.services.images.image_provider_registry import (
                    ImageProviderRegistry,
                )
                from soulspot.infrastructure.plugins import DeezerPlugin
                from soulspot.infrastructure.providers.deezer_image_provider import (
                    DeezerImageProvider,
                )

                # Create Deezer provider (NO AUTH NEEDED!)
                deezer_plugin = DeezerPlugin()
                deezer_provider = DeezerImageProvider(deezer_plugin)

                # Create registry with Deezer provider
                image_provider_registry = ImageProviderRegistry()
                image_provider_registry.register(deezer_provider, priority=1)
                logger.debug("[AUTO_FETCH] Using Deezer API for album cover lookup")

            # Call modern function directly (no deprecated wrapper!)
            result = await repair_album_images(
                session=self._session,
                image_service=image_service,
                image_provider_registry=image_provider_registry,
                limit=limit,
            )
            repaired = result.get("repaired", 0)

            if repaired > 0:
                logger.info(
                    f"[AUTO_FETCH] Repaired {repaired} album covers in background"
                )

            return result

        except Exception as e:
            logger.debug(f"[AUTO_FETCH] Album cover fetch failed: {e}")
            return {"processed": 0, "repaired": 0, "errors": 1, "error": str(e)}

    async def fetch_artist_discography(
        self,
        artist_id: str,
        include_tracks: bool = True,
    ) -> dict[str, Any]:
        """Fetch complete discography for an artist (albums + tracks).

        Hey future me - this uses Deezer (NO AUTH NEEDED!) to fetch:
        1. All albums for the artist
        2. All tracks for each album (if include_tracks=True)

        Everything gets saved to DB so next visit loads from DB.

        Args:
            artist_id: Our internal artist ID
            include_tracks: Whether to also fetch tracks (default: True)

        Returns:
            Dict with stats: {"albums_added": int, "tracks_added": int, "source": str}
        """
        try:
            from soulspot.application.services.artist_service import ArtistService
            from soulspot.infrastructure.plugins import DeezerPlugin

            # Deezer is ALWAYS available (no auth needed!)
            deezer_plugin = DeezerPlugin()

            service = ArtistService(
                self._session,
                spotify_plugin=None,  # Deezer is sufficient
                deezer_plugin=deezer_plugin,
            )

            stats = await service.sync_artist_discography_complete(
                artist_id=artist_id,
                include_tracks=include_tracks,
            )

            albums_added = stats.get("albums_added", 0)
            tracks_added = stats.get("tracks_added", 0)

            if albums_added > 0 or tracks_added > 0:
                logger.info(
                    f"[AUTO_FETCH] Synced discography: albums={albums_added}, "
                    f"tracks={tracks_added}"
                )

            return stats

        except Exception as e:
            logger.warning(f"[AUTO_FETCH] Discography fetch failed: {e}")
            return {
                "albums_added": 0,
                "tracks_added": 0,
                "source": "none",
                "error": str(e),
            }

    async def save_streaming_tracks_to_db(
        self,
        album_id: str,
        artist_id: str,
        tracks: list[dict[str, Any]],
        source: str,
    ) -> dict[str, Any]:
        """Save streaming tracks to database (without file_path).

        Hey future me - this persists tracks from Deezer/Spotify to DB!
        Tracks are saved WITHOUT file_path, marking them as "streaming-only".
        Next visit loads from DB instead of calling API.

        REFACTORED (Jan 2025): Uses TrackRepository.upsert_from_provider() instead
        of direct ORM! Clean Architecture compliant.

        Args:
            album_id: Internal SoulSpot album UUID (NOT provider ID!)
            artist_id: Internal SoulSpot artist UUID (NOT provider ID!)
            tracks: List of track dicts from streaming provider
            source: Provider name ("deezer" or "spotify")

        Returns:
            Dict with stats: {"saved": int, "skipped": int, "errors": int}
        """
        from soulspot.infrastructure.persistence.repositories import TrackRepository

        stats = {"saved": 0, "skipped": 0, "errors": 0}

        try:
            # Use TrackRepository for Clean Architecture compliance!
            track_repo = TrackRepository(self._session)

            for track in tracks:
                try:
                    # Use unified upsert_from_provider - handles deduplication!
                    # Dedup priority: ISRC → provider ID → title+album
                    await track_repo.upsert_from_provider(
                        title=track["title"],
                        artist_id=artist_id,
                        album_id=album_id,
                        source=source,
                        duration_ms=track.get("duration_ms", 0),
                        track_number=track.get("track_number", 1),
                        disc_number=track.get("disc_number", 1),
                        isrc=track.get("isrc"),
                        deezer_id=track.get("deezer_id"),
                        spotify_id=track.get(
                            "spotify_id"
                        ),  # Converts to URI internally
                    )
                    stats["saved"] += 1

                except Exception as track_error:
                    logger.debug(f"[AUTO_FETCH] Track upsert failed: {track_error}")
                    stats["errors"] += 1

            if stats["saved"] > 0:
                await self._session.commit()
                logger.info(
                    f"[AUTO_FETCH] Saved {stats['saved']} tracks to DB (source={source})"
                )

        except Exception as e:
            logger.warning(f"[AUTO_FETCH] Track save batch failed: {e}")
            stats["errors"] += 1

        return stats
