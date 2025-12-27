# Hey future me - Batch repair operations for missing images!
#
# REFACTORED (Dec 2025): Extracted from ImageRepairService.
# This module contains the IMPLEMENTATION of repair operations.
# The ImageService class provides the PUBLIC API via delegation.
#
# Usage:
#   from soulspot.application.services.images import ImageService
#   service = ImageService(...)
#   result = await service.repair_artist_images(limit=50)
#
# The repair logic handles:
# 1. Finding entities with CDN URL but missing local file
# 2. Downloading via ImageService.download_*_image_with_result()
# 3. Handling FAILED markers (24h retry)
# 4. API fallback when CDN URL is missing
"""Batch repair operations for missing images."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from soulspot.application.services.images.failed_markers import (
    classify_error,
    guess_provider_from_url,
    make_failed_marker,
    parse_failed_marker,
)
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
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


# Rate limit between API calls (50ms = 20 requests/second)
API_RATE_LIMIT_SECONDS = 0.05


async def get_artists_missing_images(
    session: "AsyncSession",
    limit: int = 50,
) -> list[ArtistModel]:
    """Get artists with CDN URL but missing local file.

    Hey future me - this finds artists that NEED image downloads!
    We prioritize artists with image_url (CDN URL already known).
    """
    stmt = (
        select(ArtistModel)
        .where(
            ArtistModel.image_url.isnot(None),
            ArtistModel.image_url != "",
            or_(
                ArtistModel.image_path.is_(None),
                ArtistModel.image_path == "",
            ),
            # Exclude FAILED (will be retried after 24h)
            ~ArtistModel.image_path.like("FAILED%"),
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_artists_with_provider_id_but_no_image(
    session: "AsyncSession",
    limit: int = 50,
) -> list[ArtistModel]:
    """Get artists with provider ID but no image_url.

    Hey future me - these artists were enriched but the provider
    didn't return an image URL. We try API lookup.
    """
    stmt = (
        select(ArtistModel)
        .where(
            or_(
                ArtistModel.deezer_id.isnot(None),
                ArtistModel.spotify_uri.isnot(None),
            ),
            or_(
                ArtistModel.image_url.is_(None),
                ArtistModel.image_url == "",
            ),
            or_(
                ArtistModel.image_path.is_(None),
                ArtistModel.image_path == "",
            ),
            # Exclude FAILED
            ~ArtistModel.image_path.like("FAILED%"),
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def repair_artist_images(
    session: "AsyncSession",
    image_service: "ImageService",
    image_provider_registry: "ImageProviderRegistry | None" = None,
    spotify_plugin: "SpotifyPlugin | None" = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Download images for artists that have CDN URL but missing local file.

    Hey future me - REFACTORED (Dec 2025) to work with ANY provider!
    Previously required spotify_uri, now works with:
    - Deezer-enriched artists (have deezer_id + image_url)
    - Spotify-enriched artists (have spotify_uri + image_url)
    - Any artist with image_url (CDN URL)

    Strategy:
    1. Find artists with image_url but no image_path
    2. Download from CDN URL (no API calls needed!)
    3. Update database with local path
    4. Fallback: API lookup for artists without image_url

    Args:
        session: SQLAlchemy async session
        image_service: ImageService for downloads
        image_provider_registry: Optional multi-provider registry for API fallback
        spotify_plugin: Optional Spotify plugin for API fallback
        limit: Maximum number of artists to process

    Returns:
        Stats dict with repaired count, processed count, and errors
    """
    # Get total counts for progress tracking
    total_missing_query = (
        select(func.count())
        .select_from(ArtistModel)
        .where(
            ArtistModel.image_url.isnot(None),
            ArtistModel.image_url != "",
            or_(
                ArtistModel.image_path.is_(None),
                ArtistModel.image_path == "",
            ),
            ~ArtistModel.image_path.like("FAILED%"),
        )
    )
    total_missing_result = await session.execute(total_missing_query)
    total_missing = total_missing_result.scalar() or 0

    # Count FAILED artists
    failed_query = (
        select(func.count())
        .select_from(ArtistModel)
        .where(ArtistModel.image_path.like("FAILED%"))
    )
    failed_result = await session.execute(failed_query)
    total_failed = failed_result.scalar() or 0

    # Get breakdown by failure reason
    failed_breakdown: dict[str, int] = {}
    failed_reasons_query = select(ArtistModel.image_path).where(
        ArtistModel.image_path.like("FAILED%")
    )
    failed_reasons_result = await session.execute(failed_reasons_query)
    for row in failed_reasons_result.scalars().all():
        is_failed, reason, _ = parse_failed_marker(row)
        if is_failed and reason:
            failed_breakdown[reason] = failed_breakdown.get(reason, 0) + 1

    stats: dict[str, Any] = {
        "processed": 0,
        "repaired": 0,
        "no_image_url": 0,
        "errors": [],
        "total_missing_before": total_missing,
        "total_failed": total_failed,
        "failed_breakdown": failed_breakdown,
        "limit": limit,
    }

    # Phase 1: Download from existing CDN URLs
    artists = await get_artists_missing_images(session, limit=limit)
    logger.info(
        f"Found {len(artists)} artists with missing images (total: {total_missing})"
    )

    for artist in artists:
        if not artist.image_url:
            stats["no_image_url"] += 1
            continue

        stats["processed"] += 1

        try:
            spotify_id = (
                artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None
            )
            deezer_id = artist.deezer_id

            image_url = artist.image_url
            provider = guess_provider_from_url(image_url)

            provider_id = deezer_id or spotify_id or str(artist.id)
            download_result = await image_service.download_artist_image_with_result(
                provider_id=provider_id,
                image_url=image_url,
                provider=provider,
            )

            if download_result.success:
                artist.image_url = image_url
                artist.image_path = download_result.path
                artist.updated_at = datetime.now(UTC)
                stats["repaired"] += 1
                logger.info(f"Repaired image for artist: {artist.name}")
            else:
                error_msg = download_result.error_message or "Download failed"
                reason = classify_error(error_msg)
                artist.image_path = make_failed_marker(reason)
                artist.updated_at = datetime.now(UTC)
                stats["errors"].append(
                    {"name": artist.name, "error": error_msg, "reason": reason}
                )
                logger.warning(
                    f"Marked artist '{artist.name}' image as FAILED ({reason})"
                )

        except Exception as e:
            error_msg = str(e)
            reason = classify_error(error_msg)
            artist.image_path = make_failed_marker(reason)
            artist.updated_at = datetime.now(UTC)
            logger.warning(f"Failed to repair image for {artist.name}: {e} ({reason})")
            stats["errors"].append(
                {"name": artist.name, "error": error_msg, "reason": reason}
            )

    # Phase 2: API fallback for artists without image_url
    artists_without_url = await get_artists_with_provider_id_but_no_image(
        session, limit=limit
    )
    stats["artists_without_url_found"] = len(artists_without_url)

    if artists_without_url:
        from soulspot.infrastructure.plugins import DeezerPlugin

        deezer_plugin = DeezerPlugin()

        for artist in artists_without_url:
            try:
                image_url = None
                provider = "unknown"

                # Try Deezer first (no auth needed!)
                if artist.deezer_id:
                    try:
                        artist_dto = await deezer_plugin.get_artist(artist.deezer_id)
                        if artist_dto and artist_dto.image and artist_dto.image.url:
                            image_url = artist_dto.image.url
                            provider = "deezer"
                    except Exception as e:
                        logger.warning(
                            f"Deezer API lookup failed for {artist.name}: {e}"
                        )
                    await asyncio.sleep(API_RATE_LIMIT_SECONDS)

                # Fallback: Search by name if no deezer_id
                if not image_url and not artist.deezer_id:
                    try:
                        search_result = await deezer_plugin.search_artists(
                            artist.name, limit=1
                        )
                        if search_result.items and search_result.items[0].image:
                            best_match = search_result.items[0]
                            if best_match.image and best_match.image.url:
                                image_url = best_match.image.url
                                provider = "deezer"
                                if best_match.deezer_id:
                                    artist.deezer_id = best_match.deezer_id
                    except Exception as e:
                        logger.debug(f"Deezer name search failed for {artist.name}: {e}")
                    await asyncio.sleep(API_RATE_LIMIT_SECONDS)

                # Try Spotify if plugin available
                if not image_url and spotify_plugin and artist.spotify_uri:
                    spotify_id = artist.spotify_uri.split(":")[-1]
                    try:
                        artist_dto = await spotify_plugin.get_artist(spotify_id)
                        if artist_dto and artist_dto.image and artist_dto.image.url:
                            image_url = artist_dto.image.url
                            provider = "spotify"
                    except Exception as e:
                        logger.debug(f"Spotify API lookup failed for {artist.name}: {e}")
                    await asyncio.sleep(API_RATE_LIMIT_SECONDS)

                if not image_url:
                    stats["api_lookup_no_image"] = (
                        stats.get("api_lookup_no_image", 0) + 1
                    )
                    continue

                # Download the image
                provider_id = artist.deezer_id or (
                    artist.spotify_uri.split(":")[-1]
                    if artist.spotify_uri
                    else str(artist.id)
                )

                download_result = await image_service.download_artist_image_with_result(
                    provider_id=provider_id,
                    image_url=image_url,
                    provider=provider,
                )

                if download_result.success:
                    artist.image_url = image_url
                    artist.image_path = download_result.path
                    artist.updated_at = datetime.now(UTC)
                    stats["repaired"] += 1
                    stats["api_lookup_success"] = (
                        stats.get("api_lookup_success", 0) + 1
                    )
                    logger.info(
                        f"Repaired image for artist via API: {artist.name} ({provider})"
                    )
                else:
                    error_msg = download_result.error_message or "Download failed"
                    reason = classify_error(error_msg)
                    artist.image_path = make_failed_marker(reason)
                    artist.updated_at = datetime.now(UTC)
                    stats["errors"].append(
                        {"name": artist.name, "error": error_msg, "reason": reason}
                    )

            except Exception as e:
                error_msg = str(e)
                reason = classify_error(error_msg)
                artist.image_path = make_failed_marker(reason)
                artist.updated_at = datetime.now(UTC)
                stats["errors"].append(
                    {"name": artist.name, "error": error_msg, "reason": reason}
                )

    # Calculate remaining
    remaining_query = (
        select(func.count())
        .select_from(ArtistModel)
        .where(
            or_(
                ArtistModel.image_path.is_(None),
                ArtistModel.image_path == "",
            ),
        )
    )
    remaining_result = await session.execute(remaining_query)
    stats["total_remaining"] = remaining_result.scalar() or 0

    return stats


async def get_albums_missing_covers(
    session: "AsyncSession",
    limit: int = 50,
) -> list[AlbumModel]:
    """Get albums with CDN URL but missing local cover file."""
    stmt = (
        select(AlbumModel)
        .where(
            AlbumModel.cover_url.isnot(None),
            AlbumModel.cover_url != "",
            or_(
                AlbumModel.cover_path.is_(None),
                AlbumModel.cover_path == "",
            ),
            ~AlbumModel.cover_path.like("FAILED%"),
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def repair_album_images(
    session: "AsyncSession",
    image_service: "ImageService",
    image_provider_registry: "ImageProviderRegistry | None" = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Download covers for albums that have CDN URL but missing local file.

    Args:
        session: SQLAlchemy async session
        image_service: ImageService for downloads
        image_provider_registry: Optional multi-provider registry for API fallback
        limit: Maximum number of albums to process

    Returns:
        Stats dict with repaired count, processed count, and errors
    """
    # Get total counts
    total_missing_query = (
        select(func.count())
        .select_from(AlbumModel)
        .where(
            AlbumModel.cover_url.isnot(None),
            AlbumModel.cover_url != "",
            or_(
                AlbumModel.cover_path.is_(None),
                AlbumModel.cover_path == "",
            ),
            ~AlbumModel.cover_path.like("FAILED%"),
        )
    )
    total_missing_result = await session.execute(total_missing_query)
    total_missing = total_missing_result.scalar() or 0

    failed_query = (
        select(func.count())
        .select_from(AlbumModel)
        .where(AlbumModel.cover_path.like("FAILED%"))
    )
    failed_result = await session.execute(failed_query)
    total_failed = failed_result.scalar() or 0

    stats: dict[str, Any] = {
        "processed": 0,
        "repaired": 0,
        "no_cover_url": 0,
        "errors": [],
        "total_missing_before": total_missing,
        "total_failed": total_failed,
        "limit": limit,
    }

    albums = await get_albums_missing_covers(session, limit=limit)
    logger.info(
        f"Found {len(albums)} albums with missing covers (total: {total_missing})"
    )

    for album in albums:
        if not album.cover_url:
            stats["no_cover_url"] += 1
            continue

        stats["processed"] += 1

        try:
            spotify_id = album.spotify_id
            deezer_id = album.deezer_id

            cover_url = album.cover_url
            provider = guess_provider_from_url(cover_url)

            provider_id = deezer_id or spotify_id or str(album.id)
            download_result = await image_service.download_album_image_with_result(
                provider_id=provider_id,
                image_url=cover_url,
                provider=provider,
            )

            if download_result.success:
                album.cover_url = cover_url
                album.cover_path = download_result.path
                album.updated_at = datetime.now(UTC)
                stats["repaired"] += 1
                logger.info(f"Repaired cover for album: {album.title}")
            else:
                error_msg = download_result.error_message or "Download failed"
                reason = classify_error(error_msg)
                album.cover_path = make_failed_marker(reason)
                album.updated_at = datetime.now(UTC)
                stats["errors"].append(
                    {"name": album.title, "error": error_msg, "reason": reason}
                )
                logger.warning(
                    f"Marked album '{album.title}' cover as FAILED ({reason})"
                )

        except Exception as e:
            error_msg = str(e)
            reason = classify_error(error_msg)
            album.cover_path = make_failed_marker(reason)
            album.updated_at = datetime.now(UTC)
            logger.warning(f"Failed to repair cover for {album.title}: {e} ({reason})")
            stats["errors"].append(
                {"name": album.title, "error": error_msg, "reason": reason}
            )

    remaining_query = (
        select(func.count())
        .select_from(AlbumModel)
        .where(
            or_(
                AlbumModel.cover_path.is_(None),
                AlbumModel.cover_path == "",
            ),
        )
    )
    remaining_result = await session.execute(remaining_query)
    stats["total_remaining"] = remaining_result.scalar() or 0

    return stats
