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
    # NOTE: This is ONLY for API calls, NOT for CDN downloads!
    API_RATE_LIMIT_SECONDS = 0.05

    # Retry failed images after this many hours
    FAILED_RETRY_HOURS = 24

    # Failure reason codes
    FAIL_REASON_DOWNLOAD_ERROR = "download_error"
    FAIL_REASON_NOT_AVAILABLE = "not_available"  # Provider has no image
    FAIL_REASON_INVALID_URL = "invalid_url"
    FAIL_REASON_TIMEOUT = "timeout"
    FAIL_REASON_HTTP_ERROR = "http_error"

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

    def _make_failed_marker(self, reason: str) -> str:
        """Create a FAILED marker with reason and timestamp.

        Hey future me - Format: FAILED|{reason}|{ISO timestamp}
        This allows us to:
        1. Know WHY it failed (not_available, download_error, etc.)
        2. Know WHEN it failed (for 24h retry logic)
        3. Keep backward compatibility (still starts with FAILED)

        Args:
            reason: One of the FAIL_REASON_* constants

        Returns:
            Marker string like "FAILED|not_available|2025-01-15T10:30:00Z"
        """
        timestamp = datetime.now(UTC).isoformat()
        return f"FAILED|{reason}|{timestamp}"

    def _parse_failed_marker(self, marker: str | None) -> tuple[bool, str | None, datetime | None]:
        """Parse a FAILED marker to extract reason and timestamp.

        Args:
            marker: The image_path/cover_path value

        Returns:
            Tuple of (is_failed, reason, failed_at)
        """
        if not marker or not marker.startswith("FAILED"):
            return (False, None, None)

        parts = marker.split("|")
        if len(parts) >= 3:
            reason = parts[1]
            try:
                failed_at = datetime.fromisoformat(parts[2].replace("Z", "+00:00"))
            except ValueError:
                failed_at = None
            return (True, reason, failed_at)

        # Legacy format: just "FAILED"
        return (True, "unknown", None)

    def _should_retry_failed(self, marker: str | None) -> bool:
        """Check if a FAILED marker is old enough to retry.

        Hey future me - we retry after FAILED_RETRY_HOURS (default 24h).
        This gives CDN issues time to resolve, but doesn't give up permanently.

        Args:
            marker: The image_path/cover_path value

        Returns:
            True if we should retry this failed image
        """
        is_failed, _, failed_at = self._parse_failed_marker(marker)
        if not is_failed:
            return False

        if failed_at is None:
            # Legacy FAILED marker without timestamp - retry it
            return True

        # Check if enough time has passed
        hours_since_failure = (datetime.now(UTC) - failed_at).total_seconds() / 3600
        return hours_since_failure >= self.FAILED_RETRY_HOURS

    def _classify_error(self, error_message: str) -> str:
        """Classify an error message into a failure reason code.

        Hey future me - this maps error messages to standardized reason codes.
        This helps UI show meaningful info and helps us track failure types.

        Args:
            error_message: The error message from download attempt

        Returns:
            One of the FAIL_REASON_* constants
        """
        error_lower = error_message.lower()

        # Check for specific error patterns
        if "404" in error_lower or "not found" in error_lower:
            return self.FAIL_REASON_NOT_AVAILABLE
        elif "timeout" in error_lower or "timed out" in error_lower:
            return self.FAIL_REASON_TIMEOUT
        elif "invalid url" in error_lower or "url" in error_lower and "invalid" in error_lower:
            return self.FAIL_REASON_INVALID_URL
        elif any(code in error_lower for code in ["500", "502", "503", "http"]):
            return self.FAIL_REASON_HTTP_ERROR
        else:
            return self.FAIL_REASON_DOWNLOAD_ERROR

    def _guess_provider_from_url(self, url: str) -> str:
        """Guess provider from CDN URL.

        Hey future me - simple heuristic to determine image source from URL.
        Used when we already have an image_url in DB and skip API calls.

        Args:
            url: CDN URL like "https://i.scdn.co/image/..." or "https://cdns-images.dzcdn.net/..."

        Returns:
            Provider name: "spotify", "deezer", or "unknown"
        """
        url_lower = url.lower()
        if "scdn.co" in url_lower or "spotify" in url_lower:
            return "spotify"
        elif "dzcdn.net" in url_lower or "deezer" in url_lower:
            return "deezer"
        elif "coverartarchive" in url_lower or "musicbrainz" in url_lower:
            return "caa"
        elif "tidal" in url_lower:
            return "tidal"
        return "unknown"

    async def repair_artist_images(
        self,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Download images for artists that have CDN URL but missing local file.

        Hey future me - REFACTORED (Dec 2025) to work with ANY provider!
        Previously required spotify_uri, now works with:
        - Deezer-enriched artists (have deezer_id + image_url)
        - Spotify-enriched artists (have spotify_uri + image_url)
        - Any artist with image_url (CDN URL)

        Strategy:
        1. Find artists with image_url but no image_path (CDN URL exists, local file missing)
        2. Download from CDN URL (no API calls needed!)
        3. Update database with local path

        Args:
            limit: Maximum number of artists to process

        Returns:
            Stats dict with repaired count, processed count, and errors
        """
        # Hey future me - get TOTAL counts before processing to show progress!
        from sqlalchemy import func, or_

        # Count all artists still needing images (not limited)
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
                ArtistModel.image_path.notlike("FAILED%"),  # Exclude all FAILED variants
            )
        )
        total_missing_result = await self._session.execute(total_missing_query)
        total_missing = total_missing_result.scalar() or 0

        # Count FAILED artists (all FAILED variants)
        failed_query = (
            select(func.count())
            .select_from(ArtistModel)
            .where(ArtistModel.image_path.like("FAILED%"))
        )
        failed_result = await self._session.execute(failed_query)
        total_failed = failed_result.scalar() or 0

        # Get breakdown by failure reason
        failed_breakdown: dict[str, int] = {}
        failed_reasons_query = (
            select(ArtistModel.image_path)
            .where(ArtistModel.image_path.like("FAILED%"))
        )
        failed_reasons_result = await self._session.execute(failed_reasons_query)
        for row in failed_reasons_result.scalars().all():
            is_failed, reason, _ = self._parse_failed_marker(row)
            if is_failed and reason:
                failed_breakdown[reason] = failed_breakdown.get(reason, 0) + 1

        stats: dict[str, Any] = {
            "processed": 0,
            "repaired": 0,
            "no_image_url": 0,
            "errors": [],
            "total_missing_before": total_missing,
            "total_failed": total_failed,
            "failed_breakdown": failed_breakdown,  # Shows WHY images failed
            "limit": limit,
        }

        # Get artists with missing images
        artists = await self._get_artists_missing_images(limit=limit)
        logger.info(f"Found {len(artists)} artists with missing images (total: {total_missing})")

        for artist in artists:
            # FIXED: Don't skip Deezer-only artists!
            # Previously: if not artist.spotify_uri: continue
            # Now: We only need image_url to download
            if not artist.image_url:
                stats["no_image_url"] += 1
                continue

            stats["processed"] += 1

            try:
                # Get provider IDs for filename generation
                spotify_id = (
                    artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None
                )
                deezer_id = artist.deezer_id

                # Use existing image_url from DB (NO API call needed!)
                # Hey future me - LibraryDiscoveryWorker saves CDN URLs, use them!
                # This path is FAST because we skip API calls entirely.
                image_url = artist.image_url
                provider = self._guess_provider_from_url(artist.image_url)
                logger.debug(
                    f"Using existing image_url for '{artist.name}' (no API call)"
                )

                # Download image via ImageService
                # Hey future me - use deezer_id OR spotify_id OR artist.id!
                # Deezer-enriched artists might not have spotify_id.
                provider_id = deezer_id or spotify_id or str(artist.id)
                download_result = (
                    await self._image_service.download_artist_image_with_result(
                        provider_id=provider_id,
                        image_url=image_url,
                        provider=provider,
                    )
                )

                # Update database
                if download_result.success:
                    artist.image_url = image_url
                    artist.image_path = download_result.path
                    artist.updated_at = datetime.now(UTC)
                    stats["repaired"] += 1
                    logger.info(f"Repaired image for artist: {artist.name}")
                else:
                    # Hey future me - Mark as FAILED with reason and timestamp!
                    # Format: FAILED|{reason}|{ISO timestamp}
                    # This allows 24h retry and shows WHY it failed.
                    error_msg = download_result.error_message or "Download failed"
                    reason = self._classify_error(error_msg)
                    artist.image_path = self._make_failed_marker(reason)
                    artist.updated_at = datetime.now(UTC)
                    stats["errors"].append(
                        {
                            "name": artist.name,
                            "error": error_msg,
                            "reason": reason,
                        }
                    )
                    logger.warning(f"Marked artist '{artist.name}' image as FAILED ({reason})")

                # NOTE: NO rate limit here for CDN downloads!
                # Hey future me - CDN downloads (i.scdn.co, cdns-images.dzcdn.net)
                # have NO rate limits!

            except Exception as e:
                # Hey future me - Also mark exceptions as FAILED with reason!
                error_msg = str(e)
                reason = self._classify_error(error_msg)
                artist.image_path = self._make_failed_marker(reason)
                artist.updated_at = datetime.now(UTC)
                logger.warning(f"Failed to repair image for {artist.name}: {e} ({reason})")
                stats["errors"].append({"name": artist.name, "error": error_msg, "reason": reason})

        # Phase 2: Try to fetch images for artists that have provider ID but no image_url
        # Hey future me - this handles artists where enrichment found a match but
        # the provider didn't return an image at that time. We try again!
        artists_without_url = await self._get_artists_with_provider_id_but_no_image(
            limit=limit
        )
        stats["artists_without_url_found"] = len(artists_without_url)

        if artists_without_url:
            # Log summary of what IDs we have
            has_deezer = sum(1 for a in artists_without_url if a.deezer_id)
            has_spotify = sum(1 for a in artists_without_url if a.spotify_uri)
            logger.info(
                f"Found {len(artists_without_url)} enriched artists without image_url: "
                f"{has_deezer} have deezer_id, {has_spotify} have spotify_uri"
            )

            # Create DeezerPlugin for API lookups (NO AUTH NEEDED!)
            from soulspot.infrastructure.plugins import DeezerPlugin

            deezer_plugin = DeezerPlugin()

            for artist in artists_without_url:
                try:
                    image_url = None
                    provider = "unknown"
                    
                    logger.debug(
                        f"Processing '{artist.name}': deezer_id={artist.deezer_id}, "
                        f"spotify_uri={artist.spotify_uri}"
                    )

                    # Try Deezer first (no auth needed!)
                    if artist.deezer_id:
                        try:
                            logger.info(
                                f"Fetching image for '{artist.name}' via Deezer API (deezer_id={artist.deezer_id})"
                            )
                            artist_dto = await deezer_plugin.get_artist(
                                artist.deezer_id
                            )
                            if artist_dto:
                                logger.info(
                                    f"Deezer returned artist_dto for '{artist.name}': "
                                    f"has_image={artist_dto.image is not None}, "
                                    f"image_url={artist_dto.image.url if artist_dto.image else 'None'}"
                                )
                                if artist_dto.image and artist_dto.image.url:
                                    image_url = artist_dto.image.url
                                    provider = "deezer"
                            else:
                                logger.warning(
                                    f"Deezer returned None for artist '{artist.name}' (deezer_id={artist.deezer_id})"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Deezer API lookup failed for {artist.name}: {e}"
                            )
                        await asyncio.sleep(0.05)  # Rate limit

                    # Fallback: If no deezer_id, search Deezer by artist name
                    # Hey future me - this handles Spotify-only artists when Spotify isn't authenticated!
                    if not image_url and not artist.deezer_id:
                        try:
                            logger.info(
                                f"No deezer_id for '{artist.name}', searching Deezer by name"
                            )
                            search_result = await deezer_plugin.search_artists(
                                artist.name, limit=1
                            )
                            if search_result.items and search_result.items[0].image:
                                best_match = search_result.items[0]
                                if best_match.image.url:
                                    image_url = best_match.image.url
                                    provider = "deezer"
                                    # Also save the deezer_id for future lookups
                                    if best_match.deezer_id:
                                        artist.deezer_id = best_match.deezer_id
                                    logger.info(
                                        f"Found image for '{artist.name}' via Deezer name search"
                                    )
                        except Exception as e:
                            logger.debug(
                                f"Deezer name search failed for {artist.name}: {e}"
                            )
                        await asyncio.sleep(0.05)  # Rate limit

                    # Try Spotify if we have plugin and spotify_uri
                    if not image_url and self._spotify_plugin and artist.spotify_uri:
                        spotify_id = artist.spotify_uri.split(":")[-1]
                        try:
                            artist_dto = await self._spotify_plugin.get_artist(
                                spotify_id
                            )
                            if artist_dto and artist_dto.image and artist_dto.image.url:
                                image_url = artist_dto.image.url
                                provider = "spotify"
                                logger.debug(
                                    f"Found image for '{artist.name}' via Spotify API"
                                )
                        except Exception as e:
                            logger.debug(
                                f"Spotify API lookup failed for {artist.name}: {e}"
                            )
                        await asyncio.sleep(0.05)  # Rate limit

                    if not image_url:
                        stats["api_lookup_no_image"] = (
                            stats.get("api_lookup_no_image", 0) + 1
                        )
                        continue

                    # Download the image
                    provider_id = artist.deezer_id or (
                        artist.spotify_uri.split(":")[-1] if artist.spotify_uri else str(artist.id)
                    )
                    download_result = (
                        await self._image_service.download_artist_image_with_result(
                            provider_id=provider_id,
                            image_url=image_url,
                            provider=provider,
                        )
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
                            f"Repaired image for artist '{artist.name}' via {provider} API"
                        )

                except Exception as e:
                    logger.warning(
                        f"Failed to fetch image via API for {artist.name}: {e}"
                    )

        await self._session.commit()

        # Calculate remaining after this run
        stats["total_remaining"] = stats["total_missing_before"] - stats["repaired"]
        
        logger.info(
            f"Image repair complete: {stats['repaired']}/{stats['processed']} artists repaired, "
            f"{stats['total_remaining']} still missing, {stats['total_failed']} previously failed"
        )

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
        # Hey future me - get TOTAL counts before processing to show progress!
        from sqlalchemy import func

        # Count all albums still needing images (not limited)
        total_missing_query = (
            select(func.count())
            .select_from(AlbumModel)
            .where(
                AlbumModel.cover_url.is_(None) | (AlbumModel.cover_url == ""),
            )
        )
        total_missing_result = await self._session.execute(total_missing_query)
        total_missing = total_missing_result.scalar() or 0

        # Count FAILED albums
        failed_query = (
            select(func.count())
            .select_from(AlbumModel)
            .where(AlbumModel.cover_path == "FAILED")
        )
        failed_result = await self._session.execute(failed_query)
        total_failed = failed_result.scalar() or 0

        stats: dict[str, Any] = {
            "processed": 0,
            "repaired": 0,
            "already_has_image": 0,
            "no_image_found": 0,
            "errors": [],
            "total_missing_before": total_missing,
            "total_failed": total_failed,
            "limit": limit,
        }

        # Get albums with missing images that have local tracks
        albums = await self._get_albums_missing_images(limit=limit)
        logger.info(f"Found {len(albums)} albums with missing images (total: {total_missing})")

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

                # Strategy 0: Use existing cover_url from DB (NO API call needed!)
                # Hey future me - LibraryDiscoveryWorker saves CDN URLs, use them!
                # This path is FAST because we skip API calls entirely.
                if album.cover_url:
                    image_url = album.cover_url
                    provider = self._guess_provider_from_url(album.cover_url)
                    logger.debug(
                        f"Using existing cover_url for '{album.title}' (no API call)"
                    )

                # Strategy 1: Use ImageProviderRegistry (multi-provider fallback)
                # Only if we don't have a cover_url yet - needs API calls!
                if not image_url and self._image_provider_registry:
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
                    # Rate limit only when we made an API call
                    await asyncio.sleep(self.API_RATE_LIMIT_SECONDS)

                # Strategy 2: Direct Spotify plugin call (legacy fallback)
                if not image_url and self._spotify_plugin and spotify_id:
                    try:
                        album_dto = await self._spotify_plugin.get_album(
                            album_id=spotify_id,
                        )
                        if album_dto and album_dto.image and album_dto.image.url:
                            image_url = album_dto.image.url
                            provider = "spotify"
                        # Rate limit only when we made an API call
                        await asyncio.sleep(self.API_RATE_LIMIT_SECONDS)
                    except Exception as e:
                        logger.debug(f"Spotify fallback failed for {album.title}: {e}")

                if not image_url:
                    stats["no_image_found"] += 1
                    logger.debug(f"No image URL found for album: {album.title}")
                    continue

                # Download image via ImageService
                provider_id = spotify_id or deezer_id or str(album.id)
                download_result = (
                    await self._image_service.download_album_image_with_result(
                        provider_id=provider_id,
                        image_url=image_url,
                        provider=provider,
                    )
                )

                # Update database
                if download_result.success:
                    album.cover_url = image_url
                    album.cover_path = download_result.path
                    album.updated_at = datetime.now(UTC)
                    stats["repaired"] += 1
                    logger.info(f"Repaired image for album: {album.title}")
                else:
                    # Hey future me - Mark as FAILED with reason and timestamp!
                    error_msg = download_result.error_message or "Download failed"
                    reason = self._classify_error(error_msg)
                    album.cover_path = self._make_failed_marker(reason)
                    album.updated_at = datetime.now(UTC)
                    stats["errors"].append(
                        {
                            "title": album.title,
                            "error": error_msg,
                            "reason": reason,
                        }
                    )
                    logger.warning(f"Marked album '{album.title}' cover as FAILED ({reason})")

                # NOTE: NO rate limit here for CDN downloads!
                # Hey future me - CDN downloads (i.scdn.co, cdns-images.dzcdn.net)
                # have NO rate limits! Rate limiting only happens when we make
                # API calls above (ImageProviderRegistry, SpotifyPlugin).

            except Exception as e:
                # Hey future me - Also mark exceptions as FAILED with reason!
                error_msg = str(e)
                reason = self._classify_error(error_msg)
                album.cover_path = self._make_failed_marker(reason)
                album.updated_at = datetime.now(UTC)
                logger.warning(f"Failed to repair image for {album.title}: {e} ({reason})")
                stats["errors"].append({"title": album.title, "error": error_msg, "reason": reason})

        await self._session.commit()

        # Calculate remaining after this run
        stats["total_remaining"] = stats["total_missing_before"] - stats["repaired"]

        logger.info(
            f"Album image repair complete: {stats['repaired']}/{stats['processed']} albums repaired, "
            f"{stats['no_image_found']} without image source, {stats['total_remaining']} still missing"
        )

        return stats

    # Alias for backward compatibility with routes
    repair_missing_album_artwork = repair_album_images

    async def _get_artists_missing_images(
        self,
        limit: int = 50,
    ) -> list[ArtistModel]:
        """Get artists that have a CDN URL but missing local image file.

        Hey future me - FIXED (Dec 2025) to include Deezer-only artists!
        Previously this ONLY looked at spotify_uri, excluding artists enriched via Deezer.
        Now we check for EITHER:
        - Has image_url (CDN URL exists from enrichment) → download needed
        - Has deezer_id or spotify_uri (was enriched) → might have image_url

        The key criteria:
        - Artist has image_url (CDN URL from Deezer/Spotify)
        - Artist does NOT have image_path (local file missing or empty)
        - OR Artist image_path is FAILED but older than 24h (retry after cooldown)
        """
        from sqlalchemy import or_

        # First get artists with no image_path at all
        stmt = (
            select(ArtistModel)
            .where(
                # Has CDN URL from enrichment (Deezer OR Spotify)
                ArtistModel.image_url.isnot(None),
                ArtistModel.image_url != "",
                # Missing local file (NULL or empty)
                or_(
                    ArtistModel.image_path.is_(None),
                    ArtistModel.image_path == "",
                ),
            )
            .order_by(ArtistModel.name)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        artists_no_path = list(result.scalars().all())

        # Also get artists with FAILED markers that are old enough to retry
        remaining_slots = limit - len(artists_no_path)
        if remaining_slots > 0:
            stmt_failed = (
                select(ArtistModel)
                .where(
                    ArtistModel.image_url.isnot(None),
                    ArtistModel.image_url != "",
                    ArtistModel.image_path.like("FAILED%"),  # Includes FAILED|reason|timestamp
                )
                .order_by(ArtistModel.name)
                .limit(remaining_slots * 2)  # Get more, filter in Python
            )
            result_failed = await self._session.execute(stmt_failed)
            failed_artists = list(result_failed.scalars().all())

            # Filter to only those old enough to retry
            for artist in failed_artists:
                if self._should_retry_failed(artist.image_path):
                    artists_no_path.append(artist)
                    logger.debug(f"Retrying FAILED artist after 24h: {artist.name}")
                    if len(artists_no_path) >= limit:
                        break

        return artists_no_path[:limit]

    async def _get_artists_with_provider_id_but_no_image(
        self,
        limit: int = 50,
    ) -> list[ArtistModel]:
        """Get artists that have deezer_id/spotify_uri but no image_url.

        Hey future me - this is for artists where enrichment found a match
        but the provider didn't return an image at that time!

        We can try fetching the image again via:
        1. Deezer API (using deezer_id)
        2. Spotify API (using spotify_uri)

        The key criteria:
        - Artist has deezer_id OR spotify_uri (was successfully enriched)
        - Artist does NOT have image_url (provider had no image at enrichment time)
        """
        from sqlalchemy import or_

        stmt = (
            select(ArtistModel)
            .where(
                # Was enriched (has at least one provider ID)
                or_(
                    ArtistModel.deezer_id.isnot(None),
                    ArtistModel.spotify_uri.isnot(None),
                ),
                # But has no image URL yet
                or_(
                    ArtistModel.image_url.is_(None),
                    ArtistModel.image_url == "",
                ),
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
            .where(AlbumModel.cover_url.is_(None) | (AlbumModel.cover_url == ""))
            .order_by(AlbumModel.title)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
