# Hey future me - ImageRepairService handles batch image repair operations!
#
# Migrated from LocalLibraryEnrichmentService (deprecated) in Dec 2025.
# This handles:
# - repair_artist_images(): Fix artists with Spotify URI but no image
# - repair_album_images(): Fix albums with local tracks but no cover
#
# KEY INSIGHT: Repair is an ON-DEMAND batch operation triggered by user,
# NOT a background worker job. User decides when to run it via UI/API.
#
# NAME: ImageRepairService (not ArtworkRepairService) for consistency with ImageService!
#
# Dependencies:
# - ImageService: For downloading and caching images
# - ImageProviderRegistry: For multi-provider fallback search
# - SpotifyPlugin: For artist/album metadata (when registry fails)
# - Session: For DB updates
"""Image Repair Service - Batch repair for missing artist/album images."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.application.services.images.image_provider_registry import (
        ImageProviderRegistry,
    )
    from soulspot.application.services.images.image_service import ImageService
    from soulspot.infrastructure.persistence.repositories import ArtistRepository
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class ImageRepairService:
    """Service for repairing missing images on library entities.

    Hey future me - this is the dedicated service for image repair operations!
    Extracted from LocalLibraryEnrichmentService to follow single-responsibility.
    Named ImageRepairService (not ArtworkRepairService) for consistency with ImageService!

    Operations:
    - repair_artist_images(): Batch fix artists with missing images
    - repair_album_images(): Batch fix albums with missing covers

    Strategy:
    1. Find entities with Spotify/Deezer URI but missing image file
    2. Use ImageProviderRegistry for multi-provider fallback
    3. Download via ImageService
    4. Update database with new URLs/paths

    Usage:
        service = ImageRepairService(
            session=session,
            image_service=image_service,
            image_provider_registry=registry,
            spotify_plugin=plugin,
        )
        result = await service.repair_artist_images(limit=50)
    """

    # Rate limit between API calls (50ms = 20 requests/second)
    API_RATE_LIMIT_SECONDS = 0.05

    def __init__(
        self,
        session: AsyncSession,
        image_service: ImageService,
        image_provider_registry: ImageProviderRegistry | None = None,
        spotify_plugin: SpotifyPlugin | None = None,
        artist_repository: ArtistRepository | None = None,
    ) -> None:
        """Initialize image repair service.

        Hey future me - image_provider_registry is the PREFERRED way to get images!
        It handles multi-provider fallback (Deezer → Spotify → MusicBrainz).
        spotify_plugin is only used as legacy fallback when registry fails.

        Args:
            session: SQLAlchemy async session for DB updates
            image_service: ImageService for downloading/caching
            image_provider_registry: Multi-provider registry (preferred)
            spotify_plugin: Legacy fallback for Spotify images
            artist_repository: For artist queries (optional, uses raw queries if None)
        """
        self._session = session
        self._image_service = image_service
        self._image_provider_registry = image_provider_registry
        self._spotify_plugin = spotify_plugin
        self._artist_repo = artist_repository

    async def repair_artist_images(
        self,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Re-download images for artists that have Spotify URI but missing image.

        Hey future me - this is for fixing artists whose initial enrichment succeeded
        (got Spotify URI) but image download failed (network issues, rate limits).

        Strategy:
        1. Find artists with spotify_uri but no image_path
        2. Use ImageProviderRegistry for multi-provider fallback
        3. Download and cache via ImageService
        4. Update database with new paths

        Args:
            limit: Maximum number of artists to process

        Returns:
            Stats dict with repaired count, processed count, and errors
        """
        stats: dict[str, Any] = {
            "processed": 0,
            "repaired": 0,
            "errors": [],
        }

        # Get artists with missing images
        artists = await self._get_artists_missing_images(limit=limit)
        logger.info(f"Found {len(artists)} artists with missing images")

        for artist in artists:
            if not artist.spotify_uri:
                continue

            stats["processed"] += 1

            try:
                # Extract Spotify ID from URI (spotify:artist:XXXXX -> XXXXX)
                spotify_id = artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None

                image_url: str | None = None
                provider = "spotify"

                # Strategy 1: Use ImageProviderRegistry (multi-provider fallback)
                if self._image_provider_registry:
                    image_result = await self._image_provider_registry.get_artist_image(
                        artist_name=artist.name,
                        artist_ids={"spotify": spotify_id} if spotify_id else {},
                    )
                    if image_result:
                        image_url = image_result.url
                        provider = image_result.provider

                # Strategy 2: Direct Spotify plugin call (legacy fallback)
                if not image_url and self._spotify_plugin and spotify_id:
                    try:
                        artist_dto = await self._spotify_plugin.get_artist(
                            artist_id=spotify_id,
                        )
                        if artist_dto and artist_dto.image and artist_dto.image.url:
                            image_url = artist_dto.image.url
                    except Exception as e:
                        logger.debug(f"Spotify fallback failed for {artist.name}: {e}")

                if not image_url:
                    logger.debug(f"No image URL found for artist: {artist.name}")
                    continue

                # Download image via ImageService
                provider_id = spotify_id or str(artist.id)
                download_result = await self._image_service.download_artist_image_with_result(
                    provider_id=provider_id,
                    image_url=image_url,
                    provider=provider,
                )

                # Update database
                if download_result.success:
                    artist.image_url = image_url
                    artist.image_path = download_result.path
                    artist.updated_at = datetime.now(UTC)
                    stats["repaired"] += 1
                    logger.info(f"Repaired image for artist: {artist.name}")
                else:
                    stats["errors"].append({
                        "name": artist.name,
                        "error": download_result.error_message or "Download failed",
                    })

                # Rate limiting
                await asyncio.sleep(self.API_RATE_LIMIT_SECONDS)

            except Exception as e:
                logger.warning(f"Failed to repair image for {artist.name}: {e}")
                stats["errors"].append({"name": artist.name, "error": str(e)})

        await self._session.commit()
        logger.info(f"Image repair complete: {stats['repaired']}/{stats['processed']} artists repaired")

        return stats

    # Alias for backward compatibility with routes
    repair_missing_artwork = repair_artist_images

    async def repair_album_images(
        self,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch and download covers for local albums missing images.

        Hey future me - this is for albums that have local tracks but no cover art.
        The UI enrichment button was originally "fetch artist images"; users also expect
        album covers to appear for their local library.

        Strategy:
        1. Find albums with local tracks but no cover_url/cover_path
        2. Use ImageProviderRegistry (Deezer/Spotify search + fallback)
        3. Download via ImageService
        4. Update database with new URLs/paths

        Args:
            limit: Maximum number of albums to process

        Returns:
            Stats dict with repaired count, processed count, and errors
        """
        stats: dict[str, Any] = {
            "processed": 0,
            "repaired": 0,
            "already_has_image": 0,
            "no_image_found": 0,
            "errors": [],
        }

        # Get albums with missing images that have local tracks
        albums = await self._get_albums_missing_images(limit=limit)
        logger.info(f"Found {len(albums)} albums with missing images")

        for album in albums:
            stats["processed"] += 1

            try:
                # Extract IDs from URIs
                spotify_id = None
                deezer_id = None

                if album.spotify_uri:
                    spotify_id = album.spotify_uri.split(":")[-1]
                if album.deezer_id:
                    deezer_id = album.deezer_id

                image_url: str | None = None
                provider = "unknown"

                # Strategy 1: Use ImageProviderRegistry (multi-provider fallback)
                if self._image_provider_registry:
                    # Get artist name for better search matching
                    artist_name = album.artist.name if album.artist else None

                    image_result = await self._image_provider_registry.get_album_image(
                        album_title=album.title,
                        artist_name=artist_name,
                        album_ids={
                            "spotify": spotify_id,
                            "deezer": deezer_id,
                        },
                    )
                    if image_result:
                        image_url = image_result.url
                        provider = image_result.provider

                # Strategy 2: Direct Spotify plugin call (legacy fallback)
                if not image_url and self._spotify_plugin and spotify_id:
                    try:
                        album_dto = await self._spotify_plugin.get_album(
                            album_id=spotify_id,
                        )
                        if album_dto and album_dto.image and album_dto.image.url:
                            image_url = album_dto.image.url
                            provider = "spotify"
                    except Exception as e:
                        logger.debug(f"Spotify fallback failed for {album.title}: {e}")

                if not image_url:
                    stats["no_image_found"] += 1
                    logger.debug(f"No image URL found for album: {album.title}")
                    continue

                # Download image via ImageService
                provider_id = spotify_id or deezer_id or str(album.id)
                download_result = await self._image_service.download_album_image_with_result(
                    provider_id=provider_id,
                    image_url=image_url,
                    provider=provider,
                )

                # Update database
                if download_result.success:
                    album.cover_url = image_url
                    album.cover_path = download_result.path
                    album.updated_at = datetime.now(UTC)
                    stats["repaired"] += 1
                    logger.info(f"Repaired image for album: {album.title}")
                else:
                    stats["errors"].append({
                        "title": album.title,
                        "error": download_result.error_message or "Download failed",
                    })

                # Rate limiting
                await asyncio.sleep(self.API_RATE_LIMIT_SECONDS)

            except Exception as e:
                logger.warning(f"Failed to repair image for {album.title}: {e}")
                stats["errors"].append({"title": album.title, "error": str(e)})

        await self._session.commit()
        logger.info(
            f"Album image repair complete: {stats['repaired']}/{stats['processed']} albums repaired, "
            f"{stats['no_image_found']} without image source"
        )

        return stats

    # Alias for backward compatibility with routes
    repair_missing_album_artwork = repair_album_images

    async def _get_artists_missing_images(
        self,
        limit: int = 50,
    ) -> list[ArtistModel]:
        """Get artists with Spotify URI but missing image.

        Hey future me - we only repair artists that have a Spotify URI!
        These are artists we've already matched, so they should have images available.
        """
        stmt = (
            select(ArtistModel)
            .where(
                ArtistModel.spotify_uri.isnot(None),
                (ArtistModel.image_path.is_(None) | (ArtistModel.image_path == "")),
            )
            .order_by(ArtistModel.name)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _get_albums_missing_images(
        self,
        limit: int = 100,
    ) -> list[AlbumModel]:
        """Get albums with local tracks but missing images.

        Hey future me - we only repair albums that actually have local files!
        This ensures we're not wasting API calls on albums we don't own.
        """
        # Subquery: album has at least one track with file_path
        has_local_tracks = (
            select(TrackModel.id)
            .where(TrackModel.album_id == AlbumModel.id)
            .where(TrackModel.file_path.isnot(None))
            .exists()
        )

        stmt = (
            select(AlbumModel)
            .where(has_local_tracks)
            .where(
                AlbumModel.cover_url.is_(None) | (AlbumModel.cover_url == "")
            )
            .order_by(AlbumModel.title)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
