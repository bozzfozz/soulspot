# Hey future me - this service handles MusicBrainz-based enrichment operations!
#
# Migrated from LocalLibraryEnrichmentService (deprecated) in Dec 2025.
# This handles:
# - Artist disambiguation (e.g., "Genesis (English rock band)")
# - Album disambiguation (e.g., "Greatest Hits (Remastered 2023)")
# - MusicBrainz ID population
#
# KEY INSIGHT: Disambiguation is an ON-DEMAND operation triggered by user,
# NOT a background worker job. User decides when to run it via UI/API.
#
# MusicBrainz Rate Limiting: 1 request/second - don't speed this up!
"""MusicBrainz Enrichment Service - Disambiguation and metadata from MusicBrainz."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from rapidfuzz import fuzz
from sqlalchemy import select

from soulspot.infrastructure.persistence.models import AlbumModel, ArtistModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.infrastructure.integrations.musicbrainz_client import (
        MusicBrainzClient,
    )

logger = logging.getLogger(__name__)


class MusicBrainzEnrichmentService:
    """Service for enriching library entities with MusicBrainz data.

    Hey future me - this is the dedicated service for MusicBrainz operations!
    Extracted from LocalLibraryEnrichmentService to follow single-responsibility.

    Operations:
    - enrich_disambiguation_batch(): Batch process artists/albums without disambiguation
    - enrich_artist_disambiguation(): Single artist disambiguation lookup
    - enrich_album_disambiguation(): Single album disambiguation lookup

    Rate Limiting:
    - MusicBrainz requires 1 request/second - built into all methods
    - Do NOT parallelize MusicBrainz calls!

    Usage:
        service = MusicBrainzEnrichmentService(session, mb_client, settings_service)
        result = await service.enrich_disambiguation_batch(limit=50)
    """

    # MusicBrainz rate limit: 1 request per second (enforced by client + extra safety here)
    MB_RATE_LIMIT_SECONDS = 1.0

    # Minimum similarity score to accept a MusicBrainz match (0.0-1.0)
    MIN_MATCH_SCORE = 0.80

    def __init__(
        self,
        session: AsyncSession,
        musicbrainz_client: MusicBrainzClient,
        settings_service: AppSettingsService | None = None,
    ) -> None:
        """Initialize MusicBrainz enrichment service.

        Hey future me - settings_service is optional! If not provided, we skip
        the provider-enabled check and just run. This makes testing easier.

        Args:
            session: SQLAlchemy async session
            musicbrainz_client: MusicBrainz API client instance
            settings_service: Optional settings service for provider check
        """
        self._session = session
        self._mb_client = musicbrainz_client
        self._settings_service = settings_service

    async def enrich_disambiguation_batch(
        self,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Enrich artists and albums with MusicBrainz disambiguation data.

        Hey future me - this is the main entry point for disambiguation enrichment!
        It processes artists first, then albums, with proper rate limiting.

        Process:
        1. Find artists/albums without disambiguation but with existing metadata
        2. Search MusicBrainz by name/title
        3. Match by similarity score and store disambiguation string

        Args:
            limit: Maximum number of items to process per entity type

        Returns:
            Stats dict with enriched counts, errors, and timing
        """
        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "artists_processed": 0,
            "artists_enriched": 0,
            "albums_processed": 0,
            "albums_enriched": 0,
            "errors": [],
        }

        # Check if MusicBrainz provider is enabled (if settings service available)
        if self._settings_service is not None:
            musicbrainz_enabled = await self._settings_service.is_provider_enabled(
                "musicbrainz"
            )
            if not musicbrainz_enabled:
                logger.info(
                    "Disambiguation enrichment skipped: MusicBrainz provider disabled"
                )
                stats["skipped"] = True
                stats["reason"] = "MusicBrainz provider disabled in settings"
                return stats

        # Phase 1: Enrich artists without disambiguation
        artists = await self._get_artists_without_disambiguation(limit=limit)
        logger.info(f"Found {len(artists)} artists without disambiguation")

        for artist in artists:
            stats["artists_processed"] += 1
            try:
                result = await self._enrich_artist_disambiguation(artist)
                if result:
                    stats["artists_enriched"] += 1
            except Exception as e:
                logger.warning(f"Disambiguation failed for artist '{artist.name}': {e}")
                stats["errors"].append(
                    {
                        "type": "artist",
                        "name": artist.name,
                        "error": str(e),
                    }
                )

            # Rate limiting - MusicBrainz requires 1 req/sec
            await asyncio.sleep(self.MB_RATE_LIMIT_SECONDS)

        # Phase 2: Enrich albums without disambiguation
        albums = await self._get_albums_without_disambiguation(limit=limit)
        logger.info(f"Found {len(albums)} albums without disambiguation")

        for album in albums:
            stats["albums_processed"] += 1
            try:
                result = await self._enrich_album_disambiguation(album)
                if result:
                    stats["albums_enriched"] += 1
            except Exception as e:
                logger.warning(f"Disambiguation failed for album '{album.title}': {e}")
                stats["errors"].append(
                    {
                        "type": "album",
                        "name": album.title,
                        "error": str(e),
                    }
                )

            # Rate limiting
            await asyncio.sleep(self.MB_RATE_LIMIT_SECONDS)

        # Commit all changes at the end
        await self._session.commit()
        stats["completed_at"] = datetime.now(UTC).isoformat()

        logger.info(
            f"Disambiguation enrichment complete: "
            f"{stats['artists_enriched']}/{stats['artists_processed']} artists, "
            f"{stats['albums_enriched']}/{stats['albums_processed']} albums enriched"
        )

        return stats

    async def _get_artists_without_disambiguation(
        self,
        limit: int = 50,
    ) -> list[ArtistModel]:
        """Get artists that don't have disambiguation but have names.

        Hey future me - we prioritize artists that have some existing enrichment
        (like spotify_uri) because they're more likely to be real, matched artists.
        Random unknown artists are less likely to be in MusicBrainz anyway.
        """
        stmt = (
            select(ArtistModel)
            .where(
                (
                    ArtistModel.disambiguation.is_(None)
                    | (ArtistModel.disambiguation == "")
                ),
                ArtistModel.name.isnot(None),
            )
            .order_by(
                # Prioritize artists with existing enrichment (spotify_uri, deezer_id)
                ArtistModel.spotify_uri.desc().nullslast(),
                ArtistModel.deezer_id.desc().nullslast(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _get_albums_without_disambiguation(
        self,
        limit: int = 50,
    ) -> list[AlbumModel]:
        """Get albums that don't have disambiguation but have titles.

        Hey future me - same priority logic as artists: enriched albums first!
        
        CRITICAL: Must use selectinload for artist relationship!
        Otherwise accessing album.artist.name after asyncio.sleep() will fail
        with "greenlet_spawn has not been called" error.
        """
        from sqlalchemy.orm import selectinload
        
        stmt = (
            select(AlbumModel)
            .options(selectinload(AlbumModel.artist))  # Eager load artist!
            .where(
                (
                    AlbumModel.disambiguation.is_(None)
                    | (AlbumModel.disambiguation == "")
                ),
                AlbumModel.title.isnot(None),
            )
            .order_by(
                # Prioritize albums with existing enrichment
                AlbumModel.spotify_uri.desc().nullslast(),
                AlbumModel.deezer_id.desc().nullslast(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _enrich_artist_disambiguation(self, artist: ArtistModel) -> bool:
        """Enrich a single artist with MusicBrainz disambiguation.

        Hey future me - this searches MusicBrainz for the artist name and finds
        the best match based on fuzzy string similarity. If MB has a disambiguation
        string for that artist, we store it.

        Also stores MusicBrainz ID as a bonus if we don't have one!

        Args:
            artist: Artist model to enrich

        Returns:
            True if disambiguation was found and stored
        """
        if not artist.name:
            return False

        try:
            # Search MusicBrainz for artist matches with disambiguation
            mb_results = await self._mb_client.search_artist_with_disambiguation(
                artist_name=artist.name,
                limit=5,
            )

            if not mb_results:
                logger.debug(f"No MusicBrainz results for artist '{artist.name}'")
                return False

            # Find best match by name similarity
            best_match = None
            best_score = 0.0

            for mb_artist in mb_results:
                mb_name = mb_artist.get("name", "")
                # Use thefuzz for fuzzy matching
                score = fuzz.ratio(artist.name.lower(), mb_name.lower()) / 100.0

                if score > best_score:
                    best_score = score
                    best_match = mb_artist

            # Require decent match (>80% similarity)
            if best_match and best_score >= self.MIN_MATCH_SCORE:
                disambiguation = best_match.get("disambiguation")

                if disambiguation:
                    artist.disambiguation = disambiguation
                    artist.updated_at = datetime.now(UTC)

                    # Bonus: store MusicBrainz ID if we don't have one
                    if not artist.musicbrainz_id and best_match.get("id"):
                        artist.musicbrainz_id = best_match["id"]

                    logger.info(
                        f"Added disambiguation for artist '{artist.name}': "
                        f"'{disambiguation}' (score: {best_score:.2f})"
                    )
                    return True
                else:
                    logger.debug(
                        f"MusicBrainz has no disambiguation for artist '{artist.name}' "
                        f"(matched: {best_match.get('name')})"
                    )

            return False

        except Exception as e:
            logger.warning(
                f"MusicBrainz disambiguation failed for artist '{artist.name}': {e}"
            )
            return False

    async def _enrich_album_disambiguation(self, album: AlbumModel) -> bool:
        """Enrich a single album with MusicBrainz disambiguation.

        Hey future me - albums can also have disambiguation in MusicBrainz!
        For example "Greatest Hits (1998 compilation)" vs "Greatest Hits (2005 remaster)".
        This helps differentiate albums with generic titles.

        Args:
            album: Album model to enrich

        Returns:
            True if disambiguation was found and stored
        """
        if not album.title:
            return False

        try:
            # Search MusicBrainz for album matches with disambiguation
            # Use artist name if available for better matching
            artist_name = album.artist.name if album.artist else None

            mb_results = await self._mb_client.search_album_with_disambiguation(
                title=album.title,
                artist=artist_name,
                limit=5,
            )

            if not mb_results:
                logger.debug(f"No MusicBrainz results for album '{album.title}'")
                return False

            # Find best match by title similarity
            best_match = None
            best_score = 0.0

            for mb_album in mb_results:
                mb_title = mb_album.get("title", "")
                score = fuzz.ratio(album.title.lower(), mb_title.lower()) / 100.0

                # Boost score if artist also matches
                if artist_name:
                    mb_artist_credit = mb_album.get("artist-credit", [])
                    if mb_artist_credit:
                        # artist-credit is a list of dicts with 'name' or 'artist' keys
                        for credit in mb_artist_credit:
                            credit_name = credit.get("name") or credit.get(
                                "artist", {}
                            ).get("name", "")
                            if credit_name:
                                artist_similarity = (
                                    fuzz.ratio(artist_name.lower(), credit_name.lower())
                                    / 100.0
                                )
                                # Boost title score by up to 10% if artist matches well
                                score = score + (artist_similarity * 0.1)
                                break

                if score > best_score:
                    best_score = score
                    best_match = mb_album

            # Require decent match
            if best_match and best_score >= self.MIN_MATCH_SCORE:
                disambiguation = best_match.get("disambiguation")

                if disambiguation:
                    album.disambiguation = disambiguation
                    album.updated_at = datetime.now(UTC)

                    # Bonus: store MusicBrainz release ID if we don't have one
                    if not album.musicbrainz_id and best_match.get("id"):
                        album.musicbrainz_id = best_match["id"]

                    logger.info(
                        f"Added disambiguation for album '{album.title}': "
                        f"'{disambiguation}' (score: {best_score:.2f})"
                    )
                    return True
                else:
                    logger.debug(
                        f"MusicBrainz has no disambiguation for album '{album.title}' "
                        f"(matched: {best_match.get('title')})"
                    )

            return False

        except Exception as e:
            logger.warning(
                f"MusicBrainz disambiguation failed for album '{album.title}': {e}"
            )
            return False
