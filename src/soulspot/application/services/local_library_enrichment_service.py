"""Local Library Enrichment Service - Enrich local library with Spotify metadata.

Hey future me - this service enriches local library items (artists, albums) with Spotify data!
Unlike SpotifySyncService which imports FOLLOWED items from Spotify, this service ENRICHES
items that were imported from local files (via library scan) but don't have Spotify metadata yet.

Why this matters:
1. You have MP3s on disk → library scanner imports them with basic ID3 tags
2. But those artists/albums don't have Spotify URIs, images, genres etc.
3. This service searches Spotify for matches and enriches them
4. Now you get nice artwork and metadata even for local-only files!

Key features:
- Runs automatically after library scans (if auto_enrichment_enabled)
- Respects rate limits (50ms between Spotify API calls)
- Creates enrichment_candidates for ambiguous matches (user picks correct one)
- Downloads artwork locally + stores Spotify image URLs
- FALLBACK SEARCH: If "DJ Paul Elstak" finds nothing, tries "Paul Elstak"

Matching strategy:
- Artists: Search Spotify by name, match by fuzzy name similarity + popularity
- Albums: Search Spotify by "artist + album title", match by track count + name similarity
- Fallback: If original name yields no/poor results, search with normalized name
  (strips DJ, The, MC, Dr, Lil prefixes)

When matches are ambiguous (multiple high-confidence results), we store them as
enrichment_candidates for user review instead of auto-applying wrong match.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.app_settings_service import AppSettingsService
from soulspot.application.services.spotify_image_service import SpotifyImageService
from soulspot.domain.dtos import AlbumDTO, ArtistDTO
from soulspot.domain.entities import Album, Artist
from soulspot.infrastructure.integrations.coverartarchive_client import (
    CoverArtArchiveClient,
)
from soulspot.infrastructure.integrations.deezer_client import DeezerClient
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)
from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

if TYPE_CHECKING:
    from soulspot.config import Settings

logger = logging.getLogger(__name__)

# =============================================================================
# ARTIST NAME NORMALIZATION (Dec 2025)
# Hey future me - this handles cases like "DJ Paul Elstak" vs "Paul Elstak"!
# Local files often have prefixes that Spotify doesn't use (or vice versa).
# We strip these before comparing to get better fuzzy match scores.
# =============================================================================

# Common prefixes to strip (case-insensitive, with optional trailing space/dot)
ARTIST_PREFIXES = (
    "dj ",
    "dj. ",
    "the ",
    "mc ",
    "mc. ",
    "dr ",
    "dr. ",
    "lil ",
    "lil' ",
    "big ",
    "young ",
    "old ",
    "king ",
    "queen ",
    "sir ",
    "lady ",
    "miss ",
    "mister ",
    "mr ",
    "mr. ",
    "mrs ",
    "mrs. ",
    "ms ",
    "ms. ",
)

# Common suffixes to strip (case-insensitive)
ARTIST_SUFFIXES = (
    " dj",
    " mc",
    " band",
    " group",
    " orchestra",
    " ensemble",
    " trio",
    " quartet",
    " quintet",
)


def normalize_artist_name(name: str) -> str:
    """Normalize artist name for better matching.

    Hey future me - this is crucial for matching "DJ Paul Elstak" to "Paul Elstak"!
    Strips common prefixes (DJ, The, MC, Dr, Lil) and suffixes (Band, Orchestra).
    Also normalizes whitespace and case.

    Args:
        name: Original artist name

    Returns:
        Normalized name for comparison

    Examples:
        "DJ Paul Elstak" -> "paul elstak"
        "The Prodigy" -> "prodigy"
        "Dr. Dre" -> "dre"
        "Lil Wayne" -> "wayne"
        "Paul Elstak" -> "paul elstak" (unchanged except case)
    """
    # Lowercase and strip whitespace
    normalized = name.lower().strip()

    # Strip prefixes (check each, strip first match)
    for prefix in ARTIST_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break  # Only strip one prefix

    # Strip suffixes (check each, strip first match)
    for suffix in ARTIST_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            break  # Only strip one suffix

    return normalized


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation."""

    entity_type: str  # 'artist' or 'album'
    entity_id: str
    entity_name: str
    success: bool
    spotify_uri: str | None = None
    image_downloaded: bool = False
    error: str | None = None
    candidates_created: int = 0  # If ambiguous, how many candidates stored
    source: str = "spotify"  # 'spotify' or 'deezer' - tracks where enrichment came from


@dataclass
class EnrichmentCandidate:
    """A potential Spotify match for a local entity."""

    spotify_uri: str
    spotify_name: str
    spotify_image_url: str | None
    confidence_score: float  # 0.0 - 1.0
    extra_info: dict[str, Any]  # followers, genres, etc.


class LocalLibraryEnrichmentService:
    """Service for enriching local library items with Spotify metadata.

    This service finds local library items (artists, albums) that don't have
    Spotify URIs yet, searches Spotify for matches, and enriches them with
    metadata like images, genres, and Spotify URIs.

    Usage:
        service = LocalLibraryEnrichmentService(session, spotify_plugin, settings)
        stats = await service.enrich_batch()
        # Returns: {"artists_enriched": 5, "albums_enriched": 3, ...}

    Rate limiting:
        - Default 50ms between Spotify API calls
        - Configurable via library.enrichment_rate_limit_ms setting
    """

    # Hey future me - these thresholds determine auto-match vs candidate creation
    # CANDIDATE_THRESHOLD: Create candidate if score >= this (but < confidence)
    # Below candidate threshold = no match found
    # NOTE: CONFIDENCE_THRESHOLD is now loaded from settings (Dec 2025)
    CANDIDATE_THRESHOLD = 0.50  # 50% to be considered a candidate

    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: SpotifyPlugin | None,
        settings: Settings,
    ) -> None:
        """Initialize enrichment service.

        Hey future me - wir nutzen jetzt SpotifyPlugin statt SpotifyClient!
        Das Plugin managed Token intern, daher kein access_token Parameter mehr.

        spotify_plugin kann None sein für lokale Operationen wie:
        - find_duplicate_artists/albums
        - merge_artists/albums
        - enrich_disambiguation_batch (nur MusicBrainz)

        Args:
            session: Database session
            spotify_plugin: Spotify plugin (handles auth internally), optional
            settings: Application settings
        """
        self._session = session
        self._spotify_plugin = spotify_plugin
        self._settings = settings

        # Repositories
        self._artist_repo = ArtistRepository(session)
        self._album_repo = AlbumRepository(session)

        # Services
        self._settings_service = AppSettingsService(session)
        self._image_service = SpotifyImageService(settings)

        # Hey future me - Deezer is our FREE fallback for artwork!
        # Unlike Spotify, Deezer doesn't need OAuth for metadata/artwork.
        # Perfect for Various Artists compilations where Spotify matching fails.
        self._deezer_client = DeezerClient()

        # Hey future me - CoverArtArchive is THE source for high-res album artwork!
        # Uses MusicBrainz Release IDs to fetch 1000x1000+ cover art for FREE.
        # This is the THIRD fallback: Spotify → Deezer → CoverArtArchive
        self._caa_client = CoverArtArchiveClient()

        # Hey future me - MusicBrainz is our source for DISAMBIGUATION data!
        # This is critical for Lidarr-style naming templates where same-name artists
        # need disambiguation (e.g. "Nirvana (US)" vs "Nirvana (UK band)").
        # Also provides high-quality metadata and links to CoverArtArchive.
        # Pass the musicbrainz settings from the main config!
        self._musicbrainz_client = MusicBrainzClient(settings.musicbrainz)


    # =========================================================================
    # MAIN BATCH ENRICHMENT
    # =========================================================================

    async def enrich_batch(self) -> dict[str, Any]:
        """Run a batch enrichment for unenriched artists and albums.

        This is the MAIN entry point! Call this after library scans.

        Hey future me - this method now respects Provider Modes!
        - If Spotify is OFF and Deezer is ON → delegates to enrich_batch_deezer_only()
        - If both are OFF → returns early with no enrichment
        - If Spotify is ON → uses Spotify with Deezer fallback (if Deezer ON)
        - If spotify_plugin is None → treats Spotify as disabled

        Returns:
            Stats dict with enrichment results
        """
        # Hey future me - CHECK PROVIDER MODES before doing anything!
        # This allows users to completely disable providers in Settings UI.
        spotify_enabled = await self._settings_service.is_provider_enabled("spotify")
        deezer_enabled = await self._settings_service.is_provider_enabled("deezer")

        # Hey future me - wenn kein spotify_plugin, dann ist Spotify effektiv disabled!
        # Das passiert wenn Service für lokale Operationen (merge, duplicates) erstellt wurde.
        if self._spotify_plugin is None:
            spotify_enabled = False

        if not spotify_enabled and not deezer_enabled:
            # Both providers disabled - nothing to do
            logger.info("Enrichment skipped: both Spotify and Deezer providers are disabled")
            return {
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "skipped": True,
                "reason": "All enrichment providers disabled in settings",
            }

        if not spotify_enabled and deezer_enabled:
            # Spotify OFF but Deezer ON - use Deezer-only mode
            logger.info("Using Deezer-only enrichment (Spotify provider disabled)")
            return await self.enrich_batch_deezer_only()

        # Continue with normal Spotify-based enrichment (with optional Deezer fallback)
        # If Deezer is OFF, we just won't use the fallback methods
        use_deezer_fallback = deezer_enabled

        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "artists_processed": 0,
            "artists_enriched": 0,
            "artists_candidates": 0,
            "artists_failed": 0,
            "albums_processed": 0,
            "albums_enriched": 0,
            "albums_candidates": 0,
            "albums_failed": 0,
            "images_downloaded": 0,
            "followed_artists_matched": 0,
            "followed_albums_matched": 0,
            # Hey future me - Deezer fallback stats (Dec 2025)!
            "deezer_albums_enriched": 0,
            "deezer_artists_enriched": 0,
            "deezer_fallback_disabled": not use_deezer_fallback,
            "errors": [],
        }

        # Get settings
        batch_size = await self._settings_service.get_enrichment_batch_size()
        rate_limit_ms = await self._settings_service.get_enrichment_rate_limit_ms()
        include_compilations = (
            await self._settings_service.should_enrich_compilation_albums()
        )
        download_artwork = (
            await self._settings_service.should_download_enrichment_artwork()
        )

        # Hey future me - these are the new advanced settings (Dec 2025)!
        # They make enrichment work much better for niche/underground artists.
        search_limit = await self._settings_service.get_enrichment_search_limit()
        confidence_threshold_pct = (
            await self._settings_service.get_enrichment_confidence_threshold()
        )
        name_weight = await self._settings_service.get_enrichment_name_weight()
        use_followed_hint = (
            await self._settings_service.should_use_followed_artists_hint()
        )

        # Override confidence threshold from settings (use new setting, fallback to old)
        confidence_threshold = confidence_threshold_pct / 100.0  # Convert 0-100 to 0.0-1.0

        # Hey future me - preload Followed Artists lookup table for fast matching!
        # This is the killer feature: if artist exists in Followed Artists, we use
        # their Spotify URI directly instead of searching. 100% match rate guaranteed!
        # BONUS: We also get image_path to REUSE already-downloaded artwork!
        followed_artists_lookup: dict[str, tuple[str, str | None, str | None]] = {}
        followed_albums_lookup: dict[str, tuple[str, str | None, str | None]] = {}
        if use_followed_hint:
            followed_artists_lookup = await self._build_followed_artists_lookup()
            followed_albums_lookup = await self._build_followed_albums_lookup()
            logger.info(
                f"Loaded {len(followed_artists_lookup)} followed artists, "
                f"{len(followed_albums_lookup)} followed albums for hint matching"
            )

        logger.info(
            f"Starting enrichment batch: batch_size={batch_size}, "
            f"rate_limit={rate_limit_ms}ms, threshold={confidence_threshold}, "
            f"search_limit={search_limit}, name_weight={name_weight}%"
        )

        # Hey future me - CRITICAL: Track URIs assigned in THIS batch to prevent
        # duplicates within the same batch! The DB check only sees committed data,
        # but if two artists in the same batch get the same URI, we get UNIQUE
        # constraint error on commit. This set tracks URIs we've assigned.
        assigned_artist_uris: set[str] = set()
        assigned_album_uris: set[str] = set()

        # Enrich artists first (albums need artist matches)
        artists = await self._artist_repo.get_unenriched(limit=batch_size)
        for artist in artists:
            result = await self._enrich_artist(
                artist,
                confidence_threshold=confidence_threshold,
                download_artwork=download_artwork,
                search_limit=search_limit,
                name_weight=name_weight / 100.0,  # Convert 0-100 to 0.0-1.0
                followed_artists_lookup=followed_artists_lookup,
                assigned_uris=assigned_artist_uris,  # Pass in-memory tracker
                use_deezer_fallback=use_deezer_fallback,  # Respect Deezer provider mode
            )
            stats["artists_processed"] += 1

            if result.success:
                stats["artists_enriched"] += 1
                # Hey future me - track Deezer fallback enrichments separately!
                if result.source == "deezer":
                    stats["deezer_artists_enriched"] += 1
                # Track the URI we just assigned to prevent duplicates in this batch
                if result.spotify_uri:
                    assigned_artist_uris.add(result.spotify_uri)
                if result.image_downloaded:
                    stats["images_downloaded"] += 1
                # Hey future me - track how many were matched via followed artists hint!
                if result.error == "matched_via_followed_artists":
                    stats["followed_artists_matched"] += 1
            elif result.candidates_created > 0:
                stats["artists_candidates"] += result.candidates_created
            else:
                stats["artists_failed"] += 1
                if result.error:
                    stats["errors"].append(
                        {
                            "type": "artist",
                            "name": result.entity_name,
                            "error": result.error,
                        }
                    )

            # Rate limiting
            await asyncio.sleep(rate_limit_ms / 1000.0)

        # Enrich albums
        albums = await self._album_repo.get_unenriched(
            limit=batch_size,
            include_compilations=include_compilations,
        )
        for album in albums:
            result = await self._enrich_album(
                album,
                confidence_threshold=confidence_threshold,
                download_artwork=download_artwork,
                search_limit=search_limit,
                followed_albums_lookup=followed_albums_lookup,
                assigned_uris=assigned_album_uris,  # Pass in-memory tracker
                use_deezer_fallback=use_deezer_fallback,  # Respect Deezer provider mode
            )
            stats["albums_processed"] += 1

            if result.success:
                stats["albums_enriched"] += 1
                # Hey future me - track Deezer fallback enrichments separately!
                if result.source == "deezer":
                    stats["deezer_albums_enriched"] += 1
                # Track the URI we just assigned to prevent duplicates in this batch
                if result.spotify_uri:
                    assigned_album_uris.add(result.spotify_uri)
                if result.image_downloaded:
                    stats["images_downloaded"] += 1
                # Hey future me - track how many were matched via followed albums hint!
                if result.error == "matched_via_followed_albums":
                    stats["followed_albums_matched"] += 1
            elif result.candidates_created > 0:
                stats["albums_candidates"] += result.candidates_created
            else:
                stats["albums_failed"] += 1
                if result.error and result.error != "matched_via_followed_albums":
                    stats["errors"].append(
                        {
                            "type": "album",
                            "name": result.entity_name,
                            "error": result.error,
                        }
                    )

            # Rate limiting
            await asyncio.sleep(rate_limit_ms / 1000.0)

        await self._session.commit()
        stats["completed_at"] = datetime.now(UTC).isoformat()

        # Hey future me - include Deezer fallback stats in log message!
        deezer_suffix = ""
        if stats["deezer_albums_enriched"] > 0 or stats["deezer_artists_enriched"] > 0:
            deezer_suffix = (
                f" (Deezer fallback: {stats['deezer_albums_enriched']} albums, "
                f"{stats['deezer_artists_enriched']} artists)"
            )

        logger.info(
            f"Enrichment complete: {stats['artists_enriched']} artists, "
            f"{stats['albums_enriched']} albums enriched, "
            f"{stats['followed_artists_matched']} artists + "
            f"{stats['followed_albums_matched']} albums via followed hint"
            f"{deezer_suffix}"
        )

        return stats

    # =========================================================================
    # ISRC-BASED TRACK ENRICHMENT (Deezer)
    # =========================================================================

    async def enrich_tracks_by_isrc(self, limit: int = 50) -> dict[str, Any]:
        """Enrich tracks using ISRC codes via Deezer API.

        Hey future me - this is the GOLD MINE! ISRC (International Standard Recording
        Code) is a universal track identifier. If a local file has ISRC in its ID3 tags
        and Deezer has the same ISRC, we get a 100% match. Way better than fuzzy matching!

        This method:
        1. Finds tracks that have ISRC but no Spotify URI
        2. Looks up each track on Deezer by ISRC
        3. If found, stores Deezer metadata (not Spotify URI, since it's Deezer data)

        Args:
            limit: Maximum number of tracks to process

        Returns:
            Stats dict with counts of processed, matched, failed tracks
        """
        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "tracks_processed": 0,
            "tracks_matched": 0,
            "tracks_not_found": 0,
            "errors": [],
        }

        if not self._deezer_client:
            stats["errors"].append("Deezer client not available")
            return stats

        # Get tracks with ISRC but no enrichment yet
        track_repo = TrackRepository(self._session)
        tracks = await track_repo.get_unenriched_with_isrc(limit=limit)

        logger.info(f"Found {len(tracks)} tracks with ISRC for enrichment")

        rate_limit_ms = await self._settings_service.get_enrichment_rate_limit_ms()

        for track in tracks:
            try:
                stats["tracks_processed"] += 1

                if not track.isrc:
                    continue

                # Look up track on Deezer by ISRC
                deezer_track = await self._deezer_client.get_track_by_isrc(track.isrc)

                if not deezer_track:
                    logger.debug(
                        f"No Deezer match for track '{track.title}' (ISRC: {track.isrc})"
                    )
                    stats["tracks_not_found"] += 1
                    continue

                # Found a match! Update track with Deezer metadata
                logger.info(
                    f"ISRC match: '{track.title}' -> Deezer '{deezer_track.title}' "
                    f"by {deezer_track.artist_name} (ID: {deezer_track.id})"
                )

                # Update track in DB
                # Hey future me - we store a pseudo-URI for Deezer since we don't have
                # Spotify URI. Format: "deezer:track:12345"
                # This helps us track which tracks were enriched via Deezer.
                stmt = select(TrackModel).where(
                    TrackModel.id == str(track.id.value)
                )
                result = await self._session.execute(stmt)
                model = result.scalar_one()

                # Store Deezer info - we can't use spotify_uri (that's for Spotify only)
                # Instead, we could add a deezer_id field, or store in extra metadata.
                # For now, let's just verify the ISRC match and log it.
                # TODO: Consider adding deezer_id field to TrackModel
                model.updated_at = datetime.now(UTC)

                stats["tracks_matched"] += 1

            except Exception as e:
                logger.warning(f"Error enriching track '{track.title}': {e}")
                stats["errors"].append({
                    "track": track.title,
                    "isrc": track.isrc,
                    "error": str(e),
                })

            # Rate limiting
            await asyncio.sleep(rate_limit_ms / 1000.0)

        await self._session.commit()
        stats["completed_at"] = datetime.now(UTC).isoformat()

        logger.info(
            f"ISRC enrichment complete: {stats['tracks_matched']}/{stats['tracks_processed']} "
            f"tracks matched via Deezer"
        )

        return stats

    async def enrich_batch_deezer_only(self) -> dict[str, Any]:
        """Enrich local library using ONLY Deezer (no Spotify required!).

        Hey future me - this is for users without Spotify Premium!
        Deezer's public API doesn't need OAuth, so anyone can use it.
        Quality is slightly lower (no genres from Deezer) but artwork is actually
        BETTER (1000x1000 vs Spotify's 640x640).

        Uses the same batch logic as enrich_batch but calls Deezer directly
        instead of using Deezer as fallback.

        Returns:
            Stats dict similar to enrich_batch()
        """
        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "artists_processed": 0,
            "artists_enriched": 0,
            "artists_failed": 0,
            "albums_processed": 0,
            "albums_enriched": 0,
            "albums_failed": 0,
            "images_downloaded": 0,
            "errors": [],
        }

        if not self._deezer_client:
            stats["errors"].append("Deezer client not available")
            return stats

        # Get settings
        batch_size = await self._settings_service.get_enrichment_batch_size()
        rate_limit_ms = await self._settings_service.get_enrichment_rate_limit_ms()
        download_artwork = (
            await self._settings_service.should_download_enrichment_artwork()
        )

        # Enrich artists via Deezer
        artists = await self._artist_repo.get_unenriched(limit=batch_size)
        logger.info(f"Enriching {len(artists)} artists via Deezer-only mode")

        for artist in artists:
            stats["artists_processed"] += 1
            try:
                deezer_candidate = await self._try_deezer_artist_fallback(artist)
                if deezer_candidate:
                    result = await self._apply_artist_enrichment(
                        artist, deezer_candidate, download_artwork
                    )
                    if result.success:
                        stats["artists_enriched"] += 1
                        if result.image_downloaded:
                            stats["images_downloaded"] += 1
                    else:
                        stats["artists_failed"] += 1
                else:
                    stats["artists_failed"] += 1
            except Exception as e:
                stats["artists_failed"] += 1
                stats["errors"].append({
                    "type": "artist",
                    "name": artist.name,
                    "error": str(e),
                })

            await asyncio.sleep(rate_limit_ms / 1000.0)

        # Enrich albums via Deezer
        include_compilations = (
            await self._settings_service.should_enrich_compilation_albums()
        )
        albums = await self._album_repo.get_unenriched(
            limit=batch_size,
            include_compilations=include_compilations,
        )
        logger.info(f"Enriching {len(albums)} albums via Deezer-only mode")

        for album in albums:
            stats["albums_processed"] += 1
            try:
                # Determine if Various Artists
                artist = await self._artist_repo.get_by_id(album.artist_id)
                artist_name = artist.name if artist else ""
                is_various_artists = self._is_various_artists_name(artist_name)

                deezer_candidate = await self._try_deezer_album_fallback(
                    album, is_various_artists, artist_name
                )
                if deezer_candidate:
                    result = await self._apply_album_enrichment(
                        album, deezer_candidate, download_artwork
                    )
                    if result.success:
                        stats["albums_enriched"] += 1
                        if result.image_downloaded:
                            stats["images_downloaded"] += 1
                    else:
                        stats["albums_failed"] += 1
                else:
                    stats["albums_failed"] += 1
            except Exception as e:
                stats["albums_failed"] += 1
                stats["errors"].append({
                    "type": "album",
                    "name": album.title,
                    "error": str(e),
                })

            await asyncio.sleep(rate_limit_ms / 1000.0)

        await self._session.commit()
        stats["completed_at"] = datetime.now(UTC).isoformat()

        logger.info(
            f"Deezer-only enrichment complete: {stats['artists_enriched']} artists, "
            f"{stats['albums_enriched']} albums"
        )

        return stats

    async def repair_missing_artwork(self, limit: int = 50) -> dict[str, Any]:
        """Re-download artwork for artists that have Spotify URI but missing artwork.

        Hey future me - this is for fixing artists whose initial enrichment succeeded
        (got Spotify URI) but artwork download failed (network issues, rate limits).
        We fetch artist info from Spotify API and download their artwork.

        Args:
            limit: Maximum number of artists to process

        Returns:
            Stats dict with repaired count and errors
        """
        stats = {
            "processed": 0,
            "repaired": 0,
            "errors": [],
        }

        artists = await self._artist_repo.get_missing_artwork(limit=limit)
        logger.info(f"Found {len(artists)} artists with missing artwork")

        for artist in artists:
            if not artist.spotify_uri:
                continue

            stats["processed"] += 1

            try:
                # Extract Spotify ID from URI (spotify:artist:XXXXX -> XXXXX)
                spotify_id = artist.spotify_uri.value.split(":")[-1]

                # Hey future me - wir nutzen SpotifyPlugin statt SpotifyClient!
                # Plugin gibt ArtistDTO zurück, nicht dict.
                artist_dto = await self._spotify_plugin.get_artist(
                    artist_id=spotify_id,
                )

                if not artist_dto.image_url:
                    logger.debug(f"No images available for artist {artist.name}")
                    continue

                image_url = artist_dto.image_url

                # Download artwork
                local_path = await self._image_service.download_artist_image(
                    image_url=image_url,
                    artist_name=artist.name,
                )

                # Update artist in database
                stmt = (
                    select(ArtistModel)
                    .where(ArtistModel.id == str(artist.id.value))
                )
                result = await self._session.execute(stmt)
                model = result.scalar_one_or_none()

                if model:
                    model.image_url = image_url
                    model.image_path = str(local_path) if local_path else None
                    model.updated_at = datetime.now(UTC)
                    stats["repaired"] += 1
                    logger.info(f"Repaired artwork for artist: {artist.name}")

                # Rate limiting
                await asyncio.sleep(0.05)  # 50ms between API calls

            except Exception as e:
                logger.warning(f"Failed to repair artwork for {artist.name}: {e}")
                stats["errors"].append({"name": artist.name, "error": str(e)})

        await self._session.commit()
        logger.info(f"Artwork repair complete: {stats['repaired']} artists repaired")

        return stats

    # =========================================================================
    # FOLLOWED ARTISTS HINT (Dec 2025)
    # Hey future me - this is the killer feature for guaranteed matches!
    # If artist exists in Followed Artists with Spotify URI, we copy it directly.
    # No search needed = 100% match rate for followed artists.
    # =========================================================================

    async def _build_followed_artists_lookup(
        self,
    ) -> dict[str, tuple[str, str | None]]:
        """Build a lookup table of followed artists by name.

        Returns:
            Dict mapping lowercase artist name to (spotify_uri, image_url, image_path) tuple
        """
        from soulspot.infrastructure.persistence.models import SpotifyArtistModel

        # Hey future me - SpotifyArtistModel uses spotify_id (just the ID like "0OdUWJ0sBjDrqHygGUXeCF")
        # not spotify_uri (full URI like "spotify:artist:0OdUWJ0sBjDrqHygGUXeCF")!
        # We need to construct the URI from the ID.
        stmt = select(SpotifyArtistModel).where(
            SpotifyArtistModel.spotify_id.isnot(None)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        # Hey future me - normalize names to lowercase for case-insensitive matching!
        # "Pink Floyd" and "pink floyd" should both match the same followed artist.
        # ALSO store normalized version (without DJ/The/MC) for prefix-variant matching!
        # ALSO include image_path so we can REUSE already-downloaded artwork!
        lookup: dict[str, tuple[str, str | None, str | None]] = {}
        for model in models:
            if model.spotify_id:
                name_lower = model.name.lower().strip()
                # Construct full Spotify URI from ID
                spotify_uri = f"spotify:artist:{model.spotify_id}"
                # Store under original lowercase name - now with image_path!
                lookup[name_lower] = (spotify_uri, model.image_url, model.image_path)
                # Also store under normalized name (without DJ/The/MC prefixes)
                # This allows "DJ Paul Elstak" (local) to match "Paul Elstak" (Spotify)
                name_normalized = normalize_artist_name(model.name)
                if name_normalized != name_lower:
                    lookup[name_normalized] = (spotify_uri, model.image_url, model.image_path)

        return lookup

    async def _build_followed_albums_lookup(
        self,
    ) -> dict[str, tuple[str, str | None]]:
        """Build a lookup table of followed albums by "artist|album" key.

        Hey future me - this allows 100% match rate for albums from followed artists!
        Key format: "artist_name|album_title" (both normalized and lowercase)

        Returns:
            Dict mapping "artist|album" to (spotify_uri, image_url) tuple
        """
        from soulspot.infrastructure.persistence.models import (
            SpotifyAlbumModel,
            SpotifyArtistModel,
        )

        # Join albums with artists to get artist name
        stmt = (
            select(SpotifyAlbumModel, SpotifyArtistModel.name)
            .join(
                SpotifyArtistModel,
                SpotifyAlbumModel.artist_id == SpotifyArtistModel.spotify_id,
            )
            .where(SpotifyAlbumModel.spotify_id.isnot(None))
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        # Hey future me - now includes image_path for artwork reuse!
        lookup: dict[str, tuple[str, str | None, str | None]] = {}
        for album_model, artist_name in rows:
            # Build key: "artist|album" (lowercase)
            artist_lower = artist_name.lower().strip()
            album_lower = album_model.name.lower().strip()
            key_original = f"{artist_lower}|{album_lower}"

            # Construct full Spotify URI
            spotify_uri = f"spotify:album:{album_model.spotify_id}"

            # Store under original key - now with image_path!
            lookup[key_original] = (spotify_uri, album_model.image_url, album_model.image_path)

            # Also store under normalized artist name
            # "DJ Paul Elstak|Party Animals" should match "Paul Elstak|Party Animals"
            artist_normalized = normalize_artist_name(artist_name)
            if artist_normalized != artist_lower:
                key_normalized = f"{artist_normalized}|{album_lower}"
                lookup[key_normalized] = (spotify_uri, album_model.image_url, album_model.image_path)

        return lookup

    # =========================================================================
    # ARTIST ENRICHMENT
    # =========================================================================

    async def _enrich_artist(
        self,
        artist: Artist,
        confidence_threshold: float,
        download_artwork: bool,
        search_limit: int = 20,
        name_weight: float = 0.85,
        followed_artists_lookup: dict[str, tuple[str, str | None, str | None]] | None = None,
        assigned_uris: set[str] | None = None,
        use_deezer_fallback: bool = True,
    ) -> EnrichmentResult:
        """Enrich a single artist with Spotify data.

        Args:
            artist: Artist entity to enrich
            confidence_threshold: Minimum confidence for auto-apply
            download_artwork: Whether to download artwork
            search_limit: Number of Spotify search results to scan
            name_weight: Weight of name similarity vs popularity (0.0-1.0)
            followed_artists_lookup: Optional lookup table for followed artists hint
            assigned_uris: Set of URIs already assigned in this batch (prevents duplicates)
            use_deezer_fallback: Whether to try Deezer when Spotify fails (default True)

        Returns:
            EnrichmentResult with success/failure info
        """
        try:
            # Hey future me - FOLLOWED ARTISTS HINT! Check if artist exists in Followed Artists.
            # If yes, copy Spotify URI directly without searching. 100% match rate!
            if followed_artists_lookup:
                name_lower = artist.name.lower().strip()
                name_normalized = normalize_artist_name(artist.name)

                # Try exact match first, then normalized match
                # This handles "DJ Paul Elstak" (local) matching "Paul Elstak" (Spotify)
                matched_key = None
                if name_lower in followed_artists_lookup:
                    matched_key = name_lower
                elif name_normalized in followed_artists_lookup:
                    matched_key = name_normalized
                    logger.debug(
                        f"Artist '{artist.name}' matched via normalized name '{name_normalized}'"
                    )

                if matched_key:
                    spotify_uri, image_url, image_path = followed_artists_lookup[matched_key]

                    # Hey future me - CHECK if URI was already assigned in this batch!
                    # Prevents UNIQUE constraint error for duplicate artists.
                    if assigned_uris and spotify_uri in assigned_uris:
                        logger.warning(
                            f"Skipping artist '{artist.name}' - spotify_uri "
                            f"'{spotify_uri}' already assigned to another artist in this batch"
                        )
                        return EnrichmentResult(
                            entity_type="artist",
                            entity_id=str(artist.id.value),
                            entity_name=artist.name,
                            success=False,
                            error="Duplicate: URI already assigned in this batch",
                        )

                    logger.debug(
                        f"Artist '{artist.name}' matched via followed artists hint"
                    )

                    # Create a synthetic candidate from followed artist data
                    # Hey future me - include image_path so we can REUSE existing artwork!
                    candidate = EnrichmentCandidate(
                        spotify_uri=spotify_uri,
                        spotify_name=artist.name,  # Use local name
                        spotify_image_url=image_url,
                        confidence_score=1.0,  # 100% confidence for followed artists
                        extra_info={
                            "matched_via": "followed_artists_hint",
                            "existing_image_path": image_path,  # REUSE this if available!
                        },
                    )

                    result = await self._apply_artist_enrichment(
                        artist, candidate, download_artwork, assigned_uris
                    )
                    # Hey future me - mark this as matched via followed artists for stats!
                    result.error = "matched_via_followed_artists"
                    return result

            # Search Spotify for this artist
            # Hey future me - artist.name is CLEAN (no UUID/MusicBrainz ID from folder parsing)!
            # LibraryFolderParser strips disambiguation before creating Artist entity.
            # We send only the artist name to Spotify API, nothing else!
            # Hey future me - SpotifyPlugin gibt PaginatedResponse[ArtistDTO] zurück!
            search_response = await self._spotify_plugin.search_artist(
                query=artist.name,
                limit=search_limit,  # Configurable via settings (default 20)
            )

            artists_data = search_response.items  # Liste von ArtistDTOs

            # Hey future me - FALLBACK SEARCH with normalized name!
            # If original name (e.g., "DJ Paul Elstak") returns no results or only
            # low-quality matches, try searching with normalized name ("Paul Elstak").
            # This handles cases where Spotify uses a different name variant.
            normalized_name = normalize_artist_name(artist.name)
            if normalized_name != artist.name.lower().strip() and not artists_data:
                # Only do fallback if normalization actually changed something
                logger.debug(
                    f"No results for '{artist.name}', trying normalized: '{normalized_name}'"
                )
                fallback_response = await self._spotify_plugin.search_artist(
                    query=normalized_name,
                    limit=search_limit,
                )
                artists_data = fallback_response.items

            if not artists_data:
                # Hey future me - DEEZER FALLBACK! If Spotify finds nothing, try Deezer.
                # But ONLY if use_deezer_fallback is True (respects provider settings)
                if use_deezer_fallback:
                    logger.debug(
                        f"Spotify found no results for artist '{artist.name}', trying Deezer fallback"
                    )
                    deezer_candidate = await self._try_deezer_artist_fallback(artist)
                    if deezer_candidate:
                        deezer_result = await self._apply_artist_enrichment(
                            artist, deezer_candidate, download_artwork, assigned_uris
                        )
                        if deezer_result.success:
                            return deezer_result

                return EnrichmentResult(
                    entity_type="artist",
                    entity_id=str(artist.id.value),
                    entity_name=artist.name,
                    success=False,
                    error="No artists found" + (" (Deezer fallback disabled)" if not use_deezer_fallback else " (Spotify + Deezer fallback)"),
                )

            # Score candidates with configurable name weight
            # Hey future me - local_name is clean artist name (no UUID)! Candidate scoring
            # is based on name similarity and Spotify popularity, never on disambiguation.
            candidates = self._score_artist_candidates(
                artist.name, artists_data, name_weight=name_weight
            )

            # Hey future me - FALLBACK for no/low candidates!
            # If original name search (e.g., "DJ Paul Elstak") gave poor matches,
            # try with normalized name ("Paul Elstak"). The true artist might only
            # appear in search results when using their Spotify-listed name.
            if normalized_name != artist.name.lower().strip() and not candidates:
                logger.debug(
                    f"No candidates for '{artist.name}', searching with normalized: '{normalized_name}'"
                )
                fallback_response = await self._spotify_plugin.search_artist(
                    query=normalized_name,
                    limit=search_limit,
                )
                fallback_data = fallback_response.items  # Liste von ArtistDTOs
                if fallback_data:
                    candidates = self._score_artist_candidates(
                        artist.name, fallback_data, name_weight=name_weight
                    )

            if not candidates:
                # Hey future me - another chance for Deezer! Spotify found artists but
                # none matched well enough. Try Deezer as fallback.
                logger.debug(
                    f"Spotify candidates too low confidence for artist '{artist.name}', trying Deezer"
                )
                deezer_candidate = await self._try_deezer_artist_fallback(artist)
                if deezer_candidate:
                    deezer_result = await self._apply_artist_enrichment(
                        artist, deezer_candidate, download_artwork, assigned_uris
                    )
                    if deezer_result.success:
                        return deezer_result

                return EnrichmentResult(
                    entity_type="artist",
                    entity_id=str(artist.id.value),
                    entity_name=artist.name,
                    success=False,
                    error="No candidates above threshold (Spotify + Deezer fallback)",
                )

            # Check if top candidate is confident enough for auto-apply
            top_candidate = candidates[0]

            # Hey future me - CHECK if URI was already assigned in this batch!
            # Prevents UNIQUE constraint error for duplicate artists via search.
            if assigned_uris and top_candidate.spotify_uri in assigned_uris:
                logger.warning(
                    f"Skipping artist '{artist.name}' - best candidate's spotify_uri "
                    f"'{top_candidate.spotify_uri}' already assigned in this batch"
                )
                return EnrichmentResult(
                    entity_type="artist",
                    entity_id=str(artist.id.value),
                    entity_name=artist.name,
                    success=False,
                    error="Duplicate: Best candidate URI already assigned in this batch",
                )

            if top_candidate.confidence_score >= confidence_threshold:
                # Auto-apply the match
                return await self._apply_artist_enrichment(
                    artist, top_candidate, download_artwork, assigned_uris
                )
            else:
                # Store as candidates for user review
                stored = await self._store_artist_candidates(artist, candidates)
                return EnrichmentResult(
                    entity_type="artist",
                    entity_id=str(artist.id.value),
                    entity_name=artist.name,
                    success=False,
                    candidates_created=stored,
                )

        except Exception as e:
            logger.warning(f"Error enriching artist '{artist.name}': {e}")
            return EnrichmentResult(
                entity_type="artist",
                entity_id=str(artist.id.value),
                entity_name=artist.name,
                success=False,
                error=str(e),
            )

    def _score_artist_candidates(
        self,
        local_name: str,
        spotify_artists: list[ArtistDTO],
        name_weight: float = 0.85,
    ) -> list[EnrichmentCandidate]:
        """Score Spotify artist candidates against local artist name.

        Hey future me - jetzt mit ArtistDTOs statt dicts!
        SpotifyPlugin gibt DTOs zurück, also arbeiten wir direkt damit.

        Scoring factors:
        - Name similarity (fuzzy match) - configurable weight (default 85%)
        - Popularity (more popular = more likely correct) - remaining weight

        Args:
            local_name: Local artist name
            spotify_artists: List of ArtistDTO from SpotifyPlugin
            name_weight: Weight of name similarity (0.0-1.0, default 0.85)

        Returns:
            Sorted list of EnrichmentCandidate (highest score first)
        """
        candidates = []
        # Hey future me - popularity_weight is the remainder after name_weight
        popularity_weight = 1.0 - name_weight

        # Normalize local name for comparison (strips DJ, The, MC, etc.)
        local_normalized = normalize_artist_name(local_name)

        for sp_artist in spotify_artists:
            # Hey future me - DTOs haben Attribute, keine dicts!
            sp_name = sp_artist.name
            sp_uri = sp_artist.spotify_uri or ""
            sp_popularity = (sp_artist.popularity or 0) / 100.0  # Normalize to 0-1
            sp_followers = sp_artist.followers or 0
            sp_genres = sp_artist.genres or []
            sp_image_url = sp_artist.image_url

            # Normalize Spotify name for comparison
            sp_normalized = normalize_artist_name(sp_name)

            # Calculate name similarity using BOTH normalized and original names
            # Hey future me - we take the MAX of both comparisons!
            # This handles "DJ Paul Elstak" vs "Paul Elstak" (normalized = 100%)
            # but also "Tiësto" vs "Tiesto" (original = high match)
            normalized_score = fuzz.ratio(local_normalized, sp_normalized) / 100.0
            original_score = fuzz.ratio(local_name.lower(), sp_name.lower()) / 100.0
            name_score = max(normalized_score, original_score)

            # Combined score: configurable name_weight + popularity_weight
            # Hey future me - higher name_weight = better for niche artists!
            # Default 85% name + 15% popularity works well for underground artists.
            confidence = (name_score * name_weight) + (sp_popularity * popularity_weight)

            if confidence >= self.CANDIDATE_THRESHOLD:
                candidates.append(
                    EnrichmentCandidate(
                        spotify_uri=sp_uri,
                        spotify_name=sp_name,
                        spotify_image_url=sp_image_url,
                        confidence_score=confidence,
                        extra_info={
                            "popularity": sp_artist.popularity or 0,
                            "followers": sp_followers,
                            "genres": sp_genres,
                        },
                    )
                )

        # Sort by confidence (highest first)
        candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        return candidates

    async def _apply_artist_enrichment(
        self,
        artist: Artist,
        candidate: EnrichmentCandidate,
        download_artwork: bool,
        assigned_uris: set[str] | None = None,
    ) -> EnrichmentResult:
        """Apply enrichment from a candidate to an artist.

        Updates artist model with Spotify URI, image, genres.
        Uses no_autoflush block to prevent premature flushes during duplicate check.

        Args:
            artist: Artist entity to update
            candidate: Selected EnrichmentCandidate
            download_artwork: Whether to download artwork
            assigned_uris: Set of URIs already assigned in this batch (for tracking)

        Returns:
            EnrichmentResult with success info
        """
        # Hey future me - CRITICAL: Use no_autoflush block to prevent the
        # "Query-invoked autoflush" error! The duplicate check SELECT was
        # triggering autoflush of pending changes from previous artists,
        # causing UNIQUE constraint errors BEFORE our check could run.
        # NOTE: no_autoflush is a SYNC context manager, not async!
        with self._session.no_autoflush:
            # Hey future me - CHECK FOR DUPLICATE SPOTIFY URI FIRST!
            # Another artist might already have this spotify_uri (duplicate local artists
            # for same Spotify artist, or folder parsing created multiple entries).
            # We skip enrichment if URI is already claimed to avoid UNIQUE constraint errors.
            existing_uri_check = await self._session.execute(
                select(ArtistModel).where(
                    ArtistModel.spotify_uri == candidate.spotify_uri,
                    ArtistModel.id != str(artist.id.value),  # Exclude current artist
                )
            )
            existing_with_uri = existing_uri_check.scalar_one_or_none()

            if existing_with_uri:
                # Hey future me - URI already assigned to another artist (likely "Paul Elstak")
                # Instead of just skipping, COPY the artwork from the existing artist!
                # This handles "DJ Paul Elstak" (local) → "Paul Elstak" (Spotify) case.
                logger.info(
                    f"'{artist.name}' matches existing artist '{existing_with_uri.name}' "
                    f"(same Spotify URI). Copying artwork instead of re-downloading."
                )

                # Update current artist model with existing artist's data
                stmt = select(ArtistModel).where(ArtistModel.id == str(artist.id.value))
                result = await self._session.execute(stmt)
                model = result.scalar_one()

                # Copy image_url and image_path from existing artist
                if existing_with_uri.image_url and not model.image_url:
                    model.image_url = existing_with_uri.image_url
                if (
                    hasattr(existing_with_uri, "image_path")
                    and existing_with_uri.image_path
                    and not getattr(model, "image_path", None)
                ):
                    model.image_path = existing_with_uri.image_path
                model.updated_at = datetime.now(UTC)

                # Don't set spotify_uri - it would cause UNIQUE constraint error
                # Instead, mark this as a duplicate that should be merged
                await self._session.flush()

                return EnrichmentResult(
                    entity_type="artist",
                    entity_id=str(artist.id.value),
                    entity_name=artist.name,
                    success=True,
                    matched_name=existing_with_uri.name,
                    matched_uri=candidate.spotify_uri,
                    error=f"Artwork copied from '{existing_with_uri.name}'. Consider merging these artists.",
                )

            # Update artist model directly
            stmt = select(ArtistModel).where(ArtistModel.id == str(artist.id.value))
            result = await self._session.execute(stmt)
            model = result.scalar_one()

            model.spotify_uri = candidate.spotify_uri
            model.image_url = candidate.spotify_image_url

            # Update genres if we have them and artist doesn't
            if candidate.extra_info.get("genres") and not model.genres:
                import json

                model.genres = json.dumps(candidate.extra_info["genres"])

            model.updated_at = datetime.now(UTC)

        # Hey future me - FLUSH after each artist enrichment to ensure the UNIQUE
        # constraint is checked immediately! This prevents batch-accumulated
        # duplicates where two artists in the same batch get the same URI.
        # The no_autoflush block above prevents autoflush during our check,
        # but we flush explicitly here to catch issues early.
        await self._session.flush()

        # Download artwork if enabled - with detailed error tracking!
        # BUT first check if we can REUSE existing artwork from Followed Artists!
        image_downloaded = False
        image_error: str | None = None

        # Hey future me - REUSE ARTWORK from Followed Artists if available!
        # This is the key optimization: if the local artist matched a Followed Artist,
        # we already have the artwork downloaded. No need to download again!
        existing_image_path = candidate.extra_info.get("existing_image_path")
        if existing_image_path:
            # Followed Artist has this image already - no download needed!
            logger.debug(
                f"Reusing existing artwork for artist '{artist.name}' from Followed Artists: {existing_image_path}"
            )
            # The image_url is already set on the model, pointing to same file
            image_downloaded = True  # Mark as "downloaded" even though we reused
        elif download_artwork and candidate.spotify_image_url:
            # Hey future me - handle both Spotify and Deezer artwork downloads!
            # Deezer candidates have URIs like "deezer:12345" instead of "spotify:artist:xyz"
            source = candidate.extra_info.get("source", "spotify")

            if source == "deezer":
                # For Deezer, use the Deezer ID for the filename
                deezer_id = candidate.extra_info.get("deezer_id", "unknown")
                download_result = await self._image_service.download_artist_image_with_result(
                    f"deezer_{deezer_id}", candidate.spotify_image_url
                )
            else:
                # Standard Spotify download - Extract Spotify ID from URI (spotify:artist:XXXXX)
                spotify_id = candidate.spotify_uri.split(":")[-1]
                download_result = await self._image_service.download_artist_image_with_result(
                    spotify_id, candidate.spotify_image_url
                )

            if download_result.success:
                image_downloaded = True
            else:
                # Log detailed error for debugging
                image_error = download_result.error_message
                logger.warning(
                    f"Failed to download artwork for artist '{artist.name}': "
                    f"[{download_result.error_code.value if download_result.error_code else 'UNKNOWN'}] "
                    f"{download_result.error_message}"
                )

        logger.debug(
            f"Enriched artist '{artist.name}' with Spotify URI {candidate.spotify_uri}"
        )

        # Hey future me - track which service provided the enrichment!
        # Deezer candidates have "source": "deezer" in extra_info
        enrichment_source = candidate.extra_info.get("source", "spotify")

        return EnrichmentResult(
            entity_type="artist",
            entity_id=str(artist.id.value),
            entity_name=artist.name,
            success=True,
            spotify_uri=candidate.spotify_uri,
            image_downloaded=image_downloaded,
            error=image_error if not image_downloaded and download_artwork else None,
            source=enrichment_source,
        )

    async def _store_artist_candidates(
        self,
        artist: Artist,
        candidates: list[EnrichmentCandidate],
    ) -> int:
        """Store candidates for user review.

        Args:
            artist: Artist entity
            candidates: List of EnrichmentCandidate

        Returns:
            Number of candidates stored
        """
        from soulspot.infrastructure.persistence.models import EnrichmentCandidateModel

        stored = 0
        for candidate in candidates[:5]:  # Store top 5 max
            model = EnrichmentCandidateModel(
                id=str(uuid4()),
                entity_type="artist",
                entity_id=str(artist.id.value),
                spotify_uri=candidate.spotify_uri,
                spotify_name=candidate.spotify_name,
                spotify_image_url=candidate.spotify_image_url,
                confidence_score=candidate.confidence_score,
                extra_info=candidate.extra_info,
                is_selected=False,
                is_rejected=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self._session.add(model)
            stored += 1

        logger.debug(f"Stored {stored} candidates for artist '{artist.name}'")
        return stored

    # =========================================================================
    # ALBUM ENRICHMENT
    # =========================================================================

    async def _enrich_album(
        self,
        album: Album,
        confidence_threshold: float,
        download_artwork: bool,
        search_limit: int = 20,
        followed_albums_lookup: dict[str, tuple[str, str | None, str | None]] | None = None,
        assigned_uris: set[str] | None = None,
        use_deezer_fallback: bool = True,
    ) -> EnrichmentResult:
        """Enrich a single album with Spotify data.

        Args:
            album: Album entity to enrich
            confidence_threshold: Minimum confidence for auto-apply
            download_artwork: Whether to download artwork
            search_limit: Number of Spotify search results to scan
            followed_albums_lookup: Optional lookup table for followed albums hint
            assigned_uris: Set of URIs already assigned in this batch (prevents duplicates)
            use_deezer_fallback: Whether to try Deezer when Spotify fails (default True)

        Returns:
            EnrichmentResult with success/failure info
        """
        try:
            # Get artist name for search
            artist_model = await self._session.get(
                ArtistModel, str(album.artist_id.value)
            )
            artist_name = artist_model.name if artist_model else "Unknown"

            # Hey future me - FOLLOWED ALBUMS HINT! Check if album exists in Followed Albums.
            # Key format: "artist|album" (both lowercase)
            if followed_albums_lookup:
                artist_lower = artist_name.lower().strip()
                album_lower = album.title.lower().strip()
                key_original = f"{artist_lower}|{album_lower}"
                artist_normalized = normalize_artist_name(artist_name)
                key_normalized = f"{artist_normalized}|{album_lower}"

                # Try exact match first, then normalized match
                matched_key = None
                if key_original in followed_albums_lookup:
                    matched_key = key_original
                elif key_normalized in followed_albums_lookup:
                    matched_key = key_normalized
                    logger.debug(
                        f"Album '{album.title}' matched via normalized artist '{artist_normalized}'"
                    )

                if matched_key:
                    spotify_uri, image_url, image_path = followed_albums_lookup[matched_key]

                    # Hey future me - CHECK if URI was already assigned in this batch!
                    if assigned_uris and spotify_uri in assigned_uris:
                        logger.warning(
                            f"Skipping album '{album.title}' - spotify_uri "
                            f"'{spotify_uri}' already assigned in this batch"
                        )
                        return EnrichmentResult(
                            entity_type="album",
                            entity_id=str(album.id.value),
                            entity_name=album.title,
                            success=False,
                            error="Duplicate: URI already assigned in this batch",
                        )

                    logger.debug(
                        f"Album '{album.title}' by '{artist_name}' matched via followed albums hint"
                    )

                    # Create a synthetic candidate from followed album data
                    # Hey future me - include image_path so we can REUSE existing artwork!
                    candidate = EnrichmentCandidate(
                        spotify_uri=spotify_uri,
                        spotify_name=album.title,  # Use local name
                        spotify_image_url=image_url,
                        confidence_score=1.0,  # 100% confidence for followed albums
                        extra_info={
                            "matched_via": "followed_albums_hint",
                            "existing_image_path": image_path,  # REUSE this if available!
                        },
                    )

                    result = await self._apply_album_enrichment(
                        album, candidate, download_artwork, assigned_uris
                    )
                    # Hey future me - mark this as matched via followed albums for stats!
                    result.error = "matched_via_followed_albums"
                    return result

            # Hey future me - VARIOUS ARTISTS / COMPILATION DETECTION!
            # If artist is "Various Artists", "VA", etc., searching with artist name is useless.
            # Instead, search ONLY by album title (optionally with year).
            # Spotify has a "tag:compilation" filter but it's not always reliable.
            is_various_artists = self._is_various_artists_name(artist_name)

            # Search Spotify: "artist album [year]" (Lidarr-style matching!)
            # Hey future me - artist_name is CLEAN (no UUID/MusicBrainz ID)!
            # LibraryFolderParser and DB already handle disambiguation stripping.
            # Adding year to search narrows results to correct release edition!
            # Hey future me - wir nutzen jetzt search_album statt search_track!
            # Das gibt direkt AlbumDTOs zurück statt Tracks mit eingebetteten Albums.
            if is_various_artists:
                # For Various Artists: search by album title only!
                # Adding "tag:compilation" helps but isn't always accurate.
                logger.debug(
                    f"Album '{album.title}' has Various Artists - using title-only search"
                )
                if album.release_year:
                    search_query = f'album:"{album.title}" year:{album.release_year}'
                else:
                    search_query = f'album:"{album.title}"'
            elif album.release_year:
                search_query = (
                    f"artist:{artist_name} album:{album.title} year:{album.release_year}"
                )
            else:
                search_query = f"artist:{artist_name} album:{album.title}"

            search_response = await self._spotify_plugin.search_album(
                query=search_query,
                limit=search_limit,  # Configurable via settings (default 20)
            )

            albums_data = search_response.items  # Liste von AlbumDTOs

            # Hey future me - if year search yields nothing, retry WITHOUT year!
            # Some albums have different years across regions or releases.
            if not albums_data and album.release_year:
                logger.debug(
                    f"No results with year {album.release_year}, retrying without year"
                )
                search_query_no_year = f"artist:{artist_name} album:{album.title}"
                fallback_response = await self._spotify_plugin.search_album(
                    query=search_query_no_year,
                    limit=search_limit,
                )
                albums_data = fallback_response.items

            if not albums_data:
                # Hey future me - DEEZER FALLBACK! If Spotify finds nothing, try Deezer.
                # But ONLY if use_deezer_fallback is True (respects provider settings)
                # Deezer is especially good for Various Artists compilations because
                # we can search by title only and still get artwork.
                if use_deezer_fallback:
                    logger.debug(
                        f"Spotify found no results for '{album.title}', trying Deezer fallback"
                    )
                    deezer_candidate = await self._try_deezer_album_fallback(
                        album, is_various_artists, artist_name
                    )
                    if deezer_candidate:
                        # Apply enrichment from Deezer candidate
                        deezer_result = await self._apply_album_enrichment(
                            album, deezer_candidate, download_artwork, assigned_uris
                        )
                        if deezer_result.success:
                            return deezer_result

                return EnrichmentResult(
                    entity_type="album",
                    entity_id=str(album.id.value),
                    entity_name=album.title,
                    success=False,
                    error="No albums found" + (" (Deezer fallback disabled)" if not use_deezer_fallback else " (Spotify + Deezer fallback)"),
                )

            # Score candidates with name normalization + year matching (Lidarr-style!)
            # Hey future me - pass is_various_artists so scoring uses title-only for compilations!
            # albums_data ist jetzt eine Liste von AlbumDTOs
            candidates = self._score_album_candidates(
                album.title,
                artist_name,
                albums_data,  # Direkt AlbumDTOs, nicht mehr albums_seen.values()
                local_year=album.release_year,  # Pass year for Lidarr-style matching
                is_various_artists=is_various_artists,  # Skip artist match for compilations
            )

            if not candidates:
                # Hey future me - another chance for Deezer! Spotify found albums but
                # none matched well enough. Try Deezer as fallback.
                # But ONLY if use_deezer_fallback is True (respects provider settings)
                if use_deezer_fallback:
                    logger.debug(
                        f"Spotify candidates too low confidence for '{album.title}', trying Deezer"
                    )
                    deezer_candidate = await self._try_deezer_album_fallback(
                        album, is_various_artists, artist_name
                    )
                    if deezer_candidate:
                        # Apply enrichment from Deezer candidate
                        deezer_result = await self._apply_album_enrichment(
                            album, deezer_candidate, download_artwork, assigned_uris
                        )
                        if deezer_result.success:
                            return deezer_result

                return EnrichmentResult(
                    entity_type="album",
                    entity_id=str(album.id.value),
                    entity_name=album.title,
                    success=False,
                    error="No candidates above threshold (Spotify + Deezer fallback)",
                )

            # Check if top candidate is confident enough
            top_candidate = candidates[0]

            # Hey future me - CHECK if URI was already assigned in this batch!
            if assigned_uris and top_candidate.spotify_uri in assigned_uris:
                logger.warning(
                    f"Skipping album '{album.title}' - best candidate's spotify_uri "
                    f"'{top_candidate.spotify_uri}' already assigned in this batch"
                )
                return EnrichmentResult(
                    entity_type="album",
                    entity_id=str(album.id.value),
                    entity_name=album.title,
                    success=False,
                    error="Duplicate: Best candidate URI already assigned in this batch",
                )

            if top_candidate.confidence_score >= confidence_threshold:
                return await self._apply_album_enrichment(
                    album, top_candidate, download_artwork, assigned_uris
                )
            else:
                stored = await self._store_album_candidates(album, candidates)
                return EnrichmentResult(
                    entity_type="album",
                    entity_id=str(album.id.value),
                    entity_name=album.title,
                    success=False,
                    candidates_created=stored,
                )

        except Exception as e:
            logger.warning(f"Error enriching album '{album.title}': {e}")
            return EnrichmentResult(
                entity_type="album",
                entity_id=str(album.id.value),
                entity_name=album.title,
                success=False,
                error=str(e),
            )

    def _score_album_candidates(
        self,
        local_title: str,
        local_artist: str,
        spotify_albums: list[AlbumDTO],
        local_year: int | None = None,
        is_various_artists: bool = False,
    ) -> list[EnrichmentCandidate]:
        """Score Spotify album candidates with name normalization + year matching.

        Hey future me - jetzt mit AlbumDTOs statt dicts!
        SpotifyPlugin.search_album() gibt DTOs zurück, also arbeiten wir direkt damit.

        Lidarr-style scoring formula (normal albums):
        - Title similarity - 45%
        - Artist name match - 45%
        - Year match bonus - 10% (exact match = 10%, ±1 year = 5%, else 0%)

        Various Artists / Compilation scoring:
        - Title similarity - 80% (album title is the main identifier!)
        - Year match bonus - 20% (year helps distinguish "Bravo Hits 100" from "Bravo Hits 99")
        - Artist match - IGNORED (Various Artists means nothing)

        Args:
            local_title: Local album title
            local_artist: Local artist name
            spotify_albums: List of AlbumDTO from SpotifyPlugin
            local_year: Local album release year (optional, from folder name)
            is_various_artists: If True, use title-only scoring for compilations

        Returns:
            Sorted list of EnrichmentCandidate (highest score first)
        """
        candidates = []

        # Normalize local artist name for comparison
        local_artist_normalized = normalize_artist_name(local_artist)

        for sp_album in spotify_albums:
            # Hey future me - DTOs haben Attribute, keine dicts!
            sp_title = sp_album.title
            sp_uri = sp_album.spotify_uri or ""
            sp_artist_name = sp_album.artist_name
            sp_release_date = sp_album.release_date or ""
            sp_total_tracks = sp_album.total_tracks or 0
            sp_image_url = sp_album.artwork_url

            # Normalize Spotify artist name
            sp_artist_normalized = normalize_artist_name(sp_artist_name)

            # Calculate title score (straight fuzzy match)
            title_score = fuzz.ratio(local_title.lower(), sp_title.lower()) / 100.0

            # Calculate artist score using BOTH normalized and original names
            # Hey future me - we take the MAX of both comparisons!
            # This handles "DJ Paul Elstak" vs "Paul Elstak" (normalized = 100%)
            artist_original_score = (
                fuzz.ratio(local_artist.lower(), sp_artist_name.lower()) / 100.0
            )
            artist_normalized_score = (
                fuzz.ratio(local_artist_normalized, sp_artist_normalized) / 100.0
            )
            artist_score = max(artist_original_score, artist_normalized_score)

            # Calculate year score (Lidarr-style year matching!)
            # Hey future me - release_date can be "YYYY-MM-DD" or just "YYYY"
            year_score = 0.0
            sp_year: int | None = None
            if sp_release_date:
                try:
                    sp_year = int(sp_release_date[:4])  # Extract year from "YYYY-MM-DD"
                except (ValueError, IndexError):
                    sp_year = None

            if local_year and sp_year:
                year_diff = abs(local_year - sp_year)
                if year_diff == 0:
                    year_score = 1.0  # Exact match = full bonus
                elif year_diff == 1:
                    year_score = 0.5  # ±1 year = half bonus (releases can differ by region)
                # else: year_score stays 0.0

            # Combined score calculation - different formula for Various Artists!
            # Hey future me - year is a BONUS, not a penalty! Albums without year
            # still compete fairly, but year-matched ones get a boost.
            if is_various_artists:
                # Various Artists: 80% title + 20% year (ignore artist entirely!)
                # For compilations like "Bravo Hits 100", title match is everything.
                confidence = (title_score * 0.80) + (year_score * 0.20)
            else:
                # Normal albums: 45% title + 45% artist + 10% year (Lidarr-style!)
                confidence = (title_score * 0.45) + (artist_score * 0.45) + (year_score * 0.10)

            if confidence >= self.CANDIDATE_THRESHOLD:
                candidates.append(
                    EnrichmentCandidate(
                        spotify_uri=sp_uri,
                        spotify_name=sp_title,
                        spotify_image_url=sp_image_url,
                        confidence_score=confidence,
                        extra_info={
                            "artist_name": sp_artist_name,
                            "release_date": sp_release_date,
                            "total_tracks": sp_total_tracks,
                        },
                    )
                )

        candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        return candidates

    def _is_various_artists_name(self, name: str) -> bool:
        """Check if artist name indicates Various Artists / Compilation.

        Hey future me - this detects "Various Artists", "VA", "Verschiedene Künstler" etc.
        When true, we search Spotify by album title only (not artist+album).
        The patterns here match the VARIOUS_ARTISTS_PATTERNS in docs/features/local-library-enrichment.md

        Args:
            name: Artist name to check

        Returns:
            True if name indicates Various Artists / Compilation
        """
        name_lower = name.lower().strip()

        # Exact matches (case-insensitive)
        various_artists_names = {
            "various artists",
            "various",
            "va",
            "v.a.",
            "v/a",
            "v.a",
            "diverse",
            "verschiedene",
            "verschiedene künstler",
            "verschiedene interpreten",
            "varios artistas",
            "artistes divers",
            "artisti vari",
            "sampler",
            "compilation",
            "soundtrack",
            "ost",
            "unknown artist",
            "[unknown]",
            "unknown",
            "",  # Empty artist also treated as Various Artists
        }

        if name_lower in various_artists_names:
            return True

        # Partial matches (name contains these patterns)
        partial_patterns = [
            "various artist",  # "Various Artists", "Various Artist"
            "v.a. ",  # "V.A. - Album Name" (some naming conventions)
            " ost",  # "Movie OST", "Game OST"
            "soundtrack",
        ]

        return any(pattern in name_lower for pattern in partial_patterns)

    async def _try_deezer_album_fallback(
        self,
        album: Album,
        is_various_artists: bool,
        artist_name: str,
    ) -> EnrichmentCandidate | None:
        """Try Deezer as fallback when Spotify finds no matches.

        Hey future me - this is the Deezer fallback for albums. Deezer API is completely
        free (no OAuth needed!) so it's perfect as backup when Spotify has no match.
        We create a synthetic EnrichmentCandidate so it flows through the same
        _apply_album_enrichment path. The "source": "deezer" in extra_info lets us
        track where enrichment came from.

        Args:
            album: Album to find on Deezer
            is_various_artists: Whether this is a VA/compilation album
            artist_name: Artist name for search

        Returns:
            EnrichmentCandidate if Deezer found a match, None otherwise
        """
        if not self._deezer_client:
            return None

        try:
            logger.debug(
                f"Trying Deezer fallback for album: {album.title} "
                f"({'VA' if is_various_artists else artist_name})"
            )

            deezer_album = None

            if is_various_artists:
                # For VA albums, use the special artwork finder that searches by title
                deezer_album = await self._deezer_client.find_album_artwork(album.title)
            else:
                # For regular albums, search by artist + title
                results = await self._deezer_client.search_albums(
                    f"{artist_name} {album.title}", limit=5
                )
                if results:
                    # Simple best-match: first result (Deezer relevance sorting)
                    # Could add scoring like Spotify, but Deezer search is usually accurate
                    deezer_album = results[0]

            if not deezer_album:
                logger.debug(f"No Deezer match for album: {album.title}")
                return None

            # Create synthetic EnrichmentCandidate from Deezer result
            # This allows us to use the same _apply_album_enrichment logic
            candidate = EnrichmentCandidate(
                spotify_uri=f"deezer:{deezer_album.id}",  # Pseudo-URI for Deezer
                spotify_name=deezer_album.title,
                spotify_image_url=deezer_album.cover_xl or deezer_album.cover_big,
                confidence_score=0.80,  # Fixed score - we trust Deezer if it's our only match
                extra_info={
                    "source": "deezer",
                    "deezer_id": deezer_album.id,
                    "deezer_link": deezer_album.link,
                    "explicit": deezer_album.explicit_lyrics,
                    "artist_name": deezer_album.artist_name,
                    "release_date": deezer_album.release_date,
                    "total_tracks": deezer_album.nb_tracks,
                    "record_type": deezer_album.record_type,
                },
            )

            logger.info(
                f"Deezer fallback found album: {deezer_album.title} by {deezer_album.artist_name} "
                f"(Deezer ID: {deezer_album.id})"
            )

            return candidate

        except Exception as e:
            logger.warning(f"Deezer fallback failed for album {album.title}: {e}")
            return None

    async def _try_deezer_artist_fallback(
        self,
        artist: Artist,
    ) -> EnrichmentCandidate | None:
        """Try Deezer as fallback when Spotify finds no artist matches.

        Hey future me - this is the Deezer fallback for artists. Same idea as album
        fallback: Deezer API is free (no OAuth) so perfect as backup.
        We create a synthetic EnrichmentCandidate so it flows through the same
        _apply_artist_enrichment path. The "source": "deezer" in extra_info lets us
        track where enrichment came from.

        Args:
            artist: Artist to find on Deezer

        Returns:
            EnrichmentCandidate if Deezer found a match, None otherwise
        """
        if not self._deezer_client:
            return None

        try:
            logger.debug(f"Trying Deezer fallback for artist: {artist.name}")

            # Search Deezer for artist
            deezer_results = await self._deezer_client.search_artists(
                artist.name, limit=5
            )

            if not deezer_results:
                # Try normalized name fallback (same as Spotify)
                normalized_name = normalize_artist_name(artist.name)
                if normalized_name != artist.name.lower().strip():
                    logger.debug(
                        f"No Deezer results for '{artist.name}', "
                        f"trying normalized: '{normalized_name}'"
                    )
                    deezer_results = await self._deezer_client.search_artists(
                        normalized_name, limit=5
                    )

            if not deezer_results:
                logger.debug(f"No Deezer match for artist: {artist.name}")
                return None

            # Use first result (Deezer relevance sorting)
            deezer_artist = deezer_results[0]

            # Create synthetic EnrichmentCandidate from Deezer result
            candidate = EnrichmentCandidate(
                spotify_uri=f"deezer:{deezer_artist.id}",  # Pseudo-URI for Deezer
                spotify_name=deezer_artist.name,
                spotify_image_url=deezer_artist.picture_xl or deezer_artist.picture_big,
                confidence_score=0.75,  # Fixed score - we trust Deezer if it's our only match
                extra_info={
                    "source": "deezer",
                    "deezer_id": deezer_artist.id,
                    "deezer_link": deezer_artist.link,
                    "nb_album": deezer_artist.nb_album,
                    "nb_fan": deezer_artist.nb_fan,
                },
            )

            logger.info(
                f"Deezer fallback found artist: {deezer_artist.name} "
                f"(Deezer ID: {deezer_artist.id}, {deezer_artist.nb_fan} fans)"
            )

            return candidate

        except Exception as e:
            logger.warning(f"Deezer fallback failed for artist {artist.name}: {e}")
            return None

    # =========================================================================
    # COVERARTARCHIVE FALLBACK (MusicBrainz Artwork)
    # =========================================================================

    async def _try_coverartarchive_album_artwork(
        self,
        album_title: str,
        musicbrainz_release_id: str | None = None,
        musicbrainz_release_group_id: str | None = None,
    ) -> str | None:
        """Try CoverArtArchive for album artwork via MusicBrainz IDs.

        Hey future me - CoverArtArchive is the THIRD fallback for artwork!
        It uses MusicBrainz Release IDs to fetch 1000x1000+ cover art.
        CAA is completely FREE and has great coverage for popular releases.

        This is called when:
        1. Album has musicbrainz_id but no artwork_url
        2. Spotify AND Deezer both failed to provide artwork
        3. We have a Release Group ID from MB search

        Args:
            album_title: Album title (for logging)
            musicbrainz_release_id: MusicBrainz Release ID (specific edition)
            musicbrainz_release_group_id: MusicBrainz Release Group ID (album concept)

        Returns:
            Artwork URL (1000x1000 or 500px thumbnail) or None
        """
        if not self._caa_client:
            return None

        if not musicbrainz_release_id and not musicbrainz_release_group_id:
            return None

        try:
            # Prefer Release ID (specific edition) over Release Group
            if musicbrainz_release_id:
                logger.debug(
                    f"Trying CoverArtArchive for album '{album_title}' "
                    f"(MB Release: {musicbrainz_release_id})"
                )

                # Try to get full artwork info first (has multiple sizes)
                artwork = await self._caa_client.get_release_artwork(musicbrainz_release_id)
                if artwork and artwork.front_url:
                    logger.info(
                        f"CoverArtArchive found artwork for '{album_title}' "
                        f"via Release ID"
                    )
                    return artwork.front_url

                # Fallback to direct front cover URL
                front_url = await self._caa_client.get_front_cover_url(musicbrainz_release_id)
                if front_url:
                    logger.info(
                        f"CoverArtArchive found front cover for '{album_title}' "
                        f"via Release ID"
                    )
                    return front_url

            # Try Release Group ID (album concept - redirects to "best" release)
            if musicbrainz_release_group_id:
                logger.debug(
                    f"Trying CoverArtArchive for album '{album_title}' "
                    f"(MB Release Group: {musicbrainz_release_group_id})"
                )

                front_url = await self._caa_client.get_release_group_front_cover(
                    musicbrainz_release_group_id
                )
                if front_url:
                    logger.info(
                        f"CoverArtArchive found artwork for '{album_title}' "
                        f"via Release Group ID"
                    )
                    return front_url

            logger.debug(f"No CoverArtArchive artwork found for album '{album_title}'")
            return None

        except Exception as e:
            logger.warning(f"CoverArtArchive fallback failed for album '{album_title}': {e}")
            return None

    # =========================================================================
    # MUSICBRAINZ DISAMBIGUATION ENRICHMENT
    # Hey future me - this is CRITICAL for Lidarr-style naming templates!
    # When you have two artists with the same name (e.g. "Nirvana"), MusicBrainz
    # provides disambiguation strings like "(US rock band)" or "(UK 1960s band)"
    # that let you tell them apart. Same for albums with generic titles.
    # =========================================================================

    async def enrich_disambiguation_batch(self, limit: int = 50) -> dict[str, Any]:
        """Enrich artists and albums with MusicBrainz disambiguation data.

        Hey future me - this fills the disambiguation field on artists and albums!
        This is essential for Lidarr-style naming templates that use {ArtistDisambiguation}.

        Process:
        1. Find artists/albums without disambiguation but with existing metadata
        2. Search MusicBrainz by name/title
        3. Match by similarity score and store disambiguation string

        Args:
            limit: Maximum number of items to process per entity type

        Returns:
            Stats dict with enriched counts and errors
        """
        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "artists_processed": 0,
            "artists_enriched": 0,
            "albums_processed": 0,
            "albums_enriched": 0,
            "errors": [],
        }

        # Check if MusicBrainz provider is enabled
        musicbrainz_enabled = await self._settings_service.is_provider_enabled("musicbrainz")
        if not musicbrainz_enabled:
            logger.info("Disambiguation enrichment skipped: MusicBrainz provider disabled")
            stats["skipped"] = True
            stats["reason"] = "MusicBrainz provider disabled in settings"
            return stats

        # Enrich artists without disambiguation
        artists = await self._get_artists_without_disambiguation(limit=limit)
        for artist in artists:
            stats["artists_processed"] += 1
            try:
                result = await self._enrich_artist_disambiguation(artist)
                if result:
                    stats["artists_enriched"] += 1
            except Exception as e:
                logger.warning(f"Disambiguation failed for artist '{artist.name}': {e}")
                stats["errors"].append({
                    "type": "artist",
                    "name": artist.name,
                    "error": str(e),
                })

            # Rate limiting - MusicBrainz requires 1 req/sec
            await asyncio.sleep(1.0)

        # Enrich albums without disambiguation
        albums = await self._get_albums_without_disambiguation(limit=limit)
        for album in albums:
            stats["albums_processed"] += 1
            try:
                result = await self._enrich_album_disambiguation(album)
                if result:
                    stats["albums_enriched"] += 1
            except Exception as e:
                logger.warning(f"Disambiguation failed for album '{album.name}': {e}")
                stats["errors"].append({
                    "type": "album",
                    "name": album.name,
                    "error": str(e),
                })

            # Rate limiting
            await asyncio.sleep(1.0)

        await self._session.commit()
        stats["completed_at"] = datetime.now(UTC).isoformat()

        logger.info(
            f"Disambiguation enrichment complete: {stats['artists_enriched']} artists, "
            f"{stats['albums_enriched']} albums enriched"
        )

        return stats

    async def _get_artists_without_disambiguation(
        self, limit: int = 50
    ) -> list[ArtistModel]:
        """Get artists that don't have disambiguation but have names.

        Hey future me - we prioritize artists that have some existing enrichment
        (like spotify_uri) because they're more likely to be real, matched artists.
        """
        stmt = (
            select(ArtistModel)
            .where(
                (ArtistModel.disambiguation.is_(None) | (ArtistModel.disambiguation == "")),
                ArtistModel.name.isnot(None),
            )
            .order_by(
                # Prioritize artists with existing enrichment
                ArtistModel.spotify_uri.desc().nullslast()
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _get_albums_without_disambiguation(
        self, limit: int = 50
    ) -> list[AlbumModel]:
        """Get albums that don't have disambiguation but have titles."""
        stmt = (
            select(AlbumModel)
            .where(
                (AlbumModel.disambiguation.is_(None) | (AlbumModel.disambiguation == "")),
                AlbumModel.name.isnot(None),
            )
            .order_by(
                # Prioritize albums with existing enrichment
                AlbumModel.spotify_uri.desc().nullslast()
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

        Returns True if disambiguation was found and stored.
        """
        if not artist.name:
            return False

        try:
            # Search MusicBrainz for artist matches with disambiguation
            mb_results = await self._musicbrainz_client.search_artist_with_disambiguation(
                name=artist.name,
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
                score = fuzz.ratio(artist.name.lower(), mb_name.lower()) / 100.0

                if score > best_score:
                    best_score = score
                    best_match = mb_artist

            # Require decent match (>80% similarity)
            if best_match and best_score >= 0.80:
                disambiguation = best_match.get("disambiguation")

                if disambiguation:
                    artist.disambiguation = disambiguation
                    artist.updated_at = datetime.now(UTC)

                    # Also store MusicBrainz ID if we don't have one
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
            logger.warning(f"MusicBrainz disambiguation failed for artist '{artist.name}': {e}")
            return False

    async def _enrich_album_disambiguation(self, album: AlbumModel) -> bool:
        """Enrich a single album with MusicBrainz disambiguation.

        Hey future me - albums can also have disambiguation in MusicBrainz!
        For example "Greatest Hits (1998 compilation)" vs "Greatest Hits (2005 remaster)".
        This helps differentiate albums with generic titles.

        Returns True if disambiguation was found and stored.
        """
        if not album.name:
            return False

        try:
            # Search MusicBrainz for album matches with disambiguation
            # Use artist name if available for better matching
            artist_name = album.artist_name or None

            mb_results = await self._musicbrainz_client.search_album_with_disambiguation(
                title=album.name,
                artist=artist_name,
                limit=5,
            )

            if not mb_results:
                logger.debug(f"No MusicBrainz results for album '{album.name}'")
                return False

            # Find best match by title similarity
            best_match = None
            best_score = 0.0

            for mb_album in mb_results:
                mb_title = mb_album.get("title", "")
                score = fuzz.ratio(album.name.lower(), mb_title.lower()) / 100.0

                # Boost score if artist also matches
                if artist_name and mb_album.get("artist_credit"):
                    mb_artist = mb_album["artist_credit"]
                    if isinstance(mb_artist, list) and mb_artist:
                        mb_artist = mb_artist[0].get("name", "")
                    elif isinstance(mb_artist, str):
                        pass  # Use as-is
                    else:
                        mb_artist = ""

                    artist_score = fuzz.ratio(artist_name.lower(), str(mb_artist).lower()) / 100.0
                    score = (score + artist_score) / 2.0

                if score > best_score:
                    best_score = score
                    best_match = mb_album

            # Require decent match (>75% similarity for albums, slightly lower than artists)
            if best_match and best_score >= 0.75:
                disambiguation = best_match.get("disambiguation")

                if disambiguation:
                    album.disambiguation = disambiguation
                    album.updated_at = datetime.now(UTC)

                    # Also store MusicBrainz ID if we don't have one
                    if not album.musicbrainz_id and best_match.get("id"):
                        album.musicbrainz_id = best_match["id"]

                    logger.info(
                        f"Added disambiguation for album '{album.name}': "
                        f"'{disambiguation}' (score: {best_score:.2f})"
                    )
                    return True
                else:
                    logger.debug(
                        f"MusicBrainz has no disambiguation for album '{album.name}' "
                        f"(matched: {best_match.get('title')})"
                    )

            return False

        except Exception as e:
            logger.warning(f"MusicBrainz disambiguation failed for album '{album.name}': {e}")
            return False

    async def repair_missing_artwork_via_caa(self, limit: int = 50) -> dict[str, Any]:
        """Repair missing artwork using CoverArtArchive for albums with MusicBrainz IDs.

        Hey future me - this is for albums that have musicbrainz_id but no artwork!
        Maybe they were enriched via MusicBrainz but CAA wasn't available then,
        or the artwork download failed. Now we can fix them.

        Args:
            limit: Maximum number of albums to process

        Returns:
            Stats dict with repaired count and errors
        """
        stats: dict[str, Any] = {
            "processed": 0,
            "repaired": 0,
            "already_has_artwork": 0,
            "no_caa_artwork": 0,
            "errors": [],
        }

        # Find albums with musicbrainz_id but no artwork
        stmt = (
            select(AlbumModel)
            .where(
                AlbumModel.musicbrainz_id.isnot(None),
                (AlbumModel.artwork_url.is_(None) | (AlbumModel.artwork_url == "")),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        albums = result.scalars().all()

        logger.info(f"Found {len(albums)} albums with MB IDs but no artwork")

        for album in albums:
            stats["processed"] += 1

            if album.artwork_url:
                stats["already_has_artwork"] += 1
                continue

            try:
                artwork_url = await self._try_coverartarchive_album_artwork(
                    album_title=album.name,
                    musicbrainz_release_id=album.musicbrainz_id,
                )

                if artwork_url:
                    # Download artwork
                    local_path = await self._image_service.download_album_image(
                        image_url=artwork_url,
                        artist_name=album.artist_name or "Unknown Artist",
                        album_name=album.name,
                    )

                    album.artwork_url = artwork_url
                    album.artwork_path = local_path
                    album.updated_at = datetime.now(UTC)

                    stats["repaired"] += 1
                    logger.info(f"Repaired artwork for album '{album.name}' via CAA")
                else:
                    stats["no_caa_artwork"] += 1

            except Exception as e:
                stats["errors"].append({
                    "album": album.name,
                    "error": str(e),
                })

        await self._session.commit()

        logger.info(
            f"CAA artwork repair complete: {stats['repaired']} albums repaired, "
            f"{stats['no_caa_artwork']} had no CAA artwork"
        )

        return stats

    async def _apply_album_enrichment(
        self,
        album: Album,
        candidate: EnrichmentCandidate,
        download_artwork: bool,
        assigned_uris: set[str] | None = None,
    ) -> EnrichmentResult:
        """Apply enrichment from a candidate to an album.

        Uses no_autoflush block to prevent premature flushes during duplicate check.

        Args:
            album: Album entity to update
            candidate: Selected EnrichmentCandidate
            download_artwork: Whether to download artwork
            assigned_uris: Set of URIs already assigned in this batch (for tracking)
        """
        # Hey future me - CRITICAL: Use no_autoflush block to prevent the
        # "Query-invoked autoflush" error! Same issue as with artists.
        # NOTE: no_autoflush is a SYNC context manager, not async!
        with self._session.no_autoflush:
            # Hey future me - CHECK FOR DUPLICATE SPOTIFY URI FIRST!
            # Another album might already have this spotify_uri (duplicate local albums
            # for same Spotify album, or folder parsing created multiple entries).
            # We skip enrichment if URI is already claimed to avoid UNIQUE constraint errors.
            existing_uri_check = await self._session.execute(
                select(AlbumModel).where(
                    AlbumModel.spotify_uri == candidate.spotify_uri,
                    AlbumModel.id != str(album.id.value),  # Exclude current album
                )
            )
            existing_with_uri = existing_uri_check.scalar_one_or_none()

            if existing_with_uri:
                logger.warning(
                    f"Skipping enrichment for album '{album.title}' - spotify_uri "
                    f"'{candidate.spotify_uri}' already assigned to album "
                    f"'{existing_with_uri.name}' (id: {existing_with_uri.id}). "
                    f"Consider merging these duplicate albums."
                )
                return EnrichmentResult(
                    entity_type="album",
                    entity_id=str(album.id.value),
                    entity_name=album.title,
                    success=False,
                    error=f"Duplicate: spotify_uri already assigned to '{existing_with_uri.name}'",
                )

            stmt = select(AlbumModel).where(AlbumModel.id == str(album.id.value))
            result = await self._session.execute(stmt)
            model = result.scalar_one()

            model.spotify_uri = candidate.spotify_uri
            model.artwork_url = candidate.spotify_image_url
            model.updated_at = datetime.now(UTC)

        # Hey future me - FLUSH after each album enrichment to ensure the UNIQUE
        # constraint is checked immediately! Same as with artists.
        await self._session.flush()

        # Download artwork if enabled - with detailed error tracking!
        # BUT first check if we can REUSE existing artwork from Followed Albums!
        image_downloaded = False
        image_error: str | None = None

        # Hey future me - REUSE ARTWORK from Followed Albums if available!
        # Same optimization as for artists.
        existing_image_path = candidate.extra_info.get("existing_image_path")
        if existing_image_path:
            # Followed Album has this image already - no download needed!
            logger.debug(
                f"Reusing existing artwork for album '{album.title}' from Followed Albums: {existing_image_path}"
            )
            model.artwork_path = existing_image_path  # Use the existing path!
            image_downloaded = True  # Mark as "downloaded" even though we reused
        elif download_artwork and candidate.spotify_image_url:
            # Hey future me - handle both Spotify and Deezer artwork downloads!
            # Deezer candidates have URIs like "deezer:12345" instead of "spotify:album:xyz"
            source = candidate.extra_info.get("source", "spotify")

            if source == "deezer":
                # For Deezer, use the Deezer ID for the filename
                deezer_id = candidate.extra_info.get("deezer_id", "unknown")
                # Download using a generic approach (Deezer cover URL is in spotify_image_url)
                download_result = await self._image_service.download_album_image_with_result(
                    f"deezer_{deezer_id}", candidate.spotify_image_url
                )
            else:
                # Standard Spotify download
                spotify_id = candidate.spotify_uri.split(":")[-1]
                download_result = await self._image_service.download_album_image_with_result(
                    spotify_id, candidate.spotify_image_url
                )

            if download_result.success:
                model.artwork_path = download_result.path
                image_downloaded = True
            else:
                # Log detailed error for debugging
                image_error = download_result.error_message
                logger.warning(
                    f"Failed to download artwork for album '{album.title}': "
                    f"[{download_result.error_code.value if download_result.error_code else 'UNKNOWN'}] "
                    f"{download_result.error_message}"
                )

        logger.debug(
            f"Enriched album '{album.title}' with Spotify URI {candidate.spotify_uri}"
        )

        # Hey future me - track which service provided the enrichment!
        # Deezer candidates have "source": "deezer" in extra_info
        source = candidate.extra_info.get("source", "spotify")

        return EnrichmentResult(
            entity_type="album",
            entity_id=str(album.id.value),
            entity_name=album.title,
            success=True,
            spotify_uri=candidate.spotify_uri,
            image_downloaded=image_downloaded,
            error=image_error if not image_downloaded and download_artwork else None,
            source=source,
        )

    async def _store_album_candidates(
        self,
        album: Album,
        candidates: list[EnrichmentCandidate],
    ) -> int:
        """Store album candidates for user review."""
        from soulspot.infrastructure.persistence.models import EnrichmentCandidateModel

        stored = 0
        for candidate in candidates[:5]:
            model = EnrichmentCandidateModel(
                id=str(uuid4()),
                entity_type="album",
                entity_id=str(album.id.value),
                spotify_uri=candidate.spotify_uri,
                spotify_name=candidate.spotify_name,
                spotify_image_url=candidate.spotify_image_url,
                confidence_score=candidate.confidence_score,
                extra_info=candidate.extra_info,
                is_selected=False,
                is_rejected=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self._session.add(model)
            stored += 1

        logger.debug(f"Stored {stored} candidates for album '{album.title}'")
        return stored

    # =========================================================================
    # ENRICHMENT STATS
    # =========================================================================

    async def get_enrichment_status(self) -> dict[str, Any]:
        """Get current enrichment status (counts of unenriched items).

        Returns:
            Dict with unenriched counts and pending candidates
        """
        from sqlalchemy import func

        from soulspot.infrastructure.persistence.models import EnrichmentCandidateModel

        artists_unenriched = await self._artist_repo.count_unenriched()
        albums_unenriched = await self._album_repo.count_unenriched()

        # Count pending candidates
        stmt = select(func.count(EnrichmentCandidateModel.id)).where(
            EnrichmentCandidateModel.is_selected == False,  # noqa: E712
            EnrichmentCandidateModel.is_rejected == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        pending_candidates = result.scalar() or 0

        return {
            "artists_unenriched": artists_unenriched,
            "albums_unenriched": albums_unenriched,
            "pending_candidates": pending_candidates,
            "is_enrichment_needed": (artists_unenriched + albums_unenriched) > 0,
        }

    # =========================================================================
    # DUPLICATE ARTIST DETECTION & MERGE (Dec 2025)
    # Hey future me - this finds artists that are likely the same person/band!
    # Common causes: "Angerfist" vs "ANGERFIST", "The Beatles" vs "Beatles, The"
    # After detection, user can merge them (keeps one, transfers tracks/albums).
    # =========================================================================

    async def find_duplicate_artists(self) -> list[dict[str, Any]]:
        """Find potential duplicate artists by normalized name matching.

        Groups artists with identical normalized names (lowercase, stripped prefixes).
        Returns groups where >1 artist has the same normalized name.

        Returns:
            List of duplicate groups, each containing:
            - normalized_name: The matching key
            - artists: List of artist dicts in this group
            - suggested_primary_id: ID of suggested "keep" artist (most tracks/has spotify_uri)
        """
        from collections import defaultdict

        from sqlalchemy import func

        from soulspot.infrastructure.persistence.models import TrackModel

        # Get all artists
        stmt = select(ArtistModel)
        result = await self._session.execute(stmt)
        all_artists = result.scalars().all()

        # Group by normalized name
        groups: dict[str, list[ArtistModel]] = defaultdict(list)
        for artist in all_artists:
            normalized = normalize_artist_name(artist.name)
            groups[normalized].append(artist)

        # Filter to groups with duplicates (>1 artist)
        duplicate_groups: list[dict[str, Any]] = []

        for normalized_name, artists in groups.items():
            if len(artists) <= 1:
                continue

            # Get track counts for each artist to suggest primary
            artist_ids = [a.id for a in artists]
            track_counts_stmt = (
                select(TrackModel.artist_id, func.count(TrackModel.id))
                .where(TrackModel.artist_id.in_(artist_ids))
                .group_by(TrackModel.artist_id)
            )
            track_counts_result = await self._session.execute(track_counts_stmt)
            track_counts = dict(track_counts_result.all())

            # Build artist info list
            artist_infos = []
            for a in artists:
                artist_infos.append({
                    "id": a.id,
                    "name": a.name,
                    "spotify_uri": a.spotify_uri,
                    "image_url": a.image_url,
                    "track_count": track_counts.get(a.id, 0),
                    "has_spotify": a.spotify_uri is not None,
                })

            # Suggest primary: prefer one with spotify_uri, then most tracks
            sorted_artists = sorted(
                artist_infos,
                key=lambda x: (x["has_spotify"], x["track_count"]),
                reverse=True,
            )
            suggested_primary_id = sorted_artists[0]["id"]

            duplicate_groups.append({
                "normalized_name": normalized_name,
                "artists": artist_infos,
                "suggested_primary_id": suggested_primary_id,
                "total_tracks": sum(a["track_count"] for a in artist_infos),
            })

        # Sort by total tracks (most impactful duplicates first)
        duplicate_groups.sort(key=lambda g: g["total_tracks"], reverse=True)

        logger.info(f"Found {len(duplicate_groups)} potential duplicate artist groups")
        return duplicate_groups

    async def merge_artists(
        self, keep_id: str, merge_ids: list[str]
    ) -> dict[str, Any]:
        """Merge multiple artists into one, transferring all tracks and albums.

        The 'keep' artist absorbs all data from 'merge' artists:
        - All tracks are reassigned to keep_id
        - All albums are reassigned to keep_id
        - image_url is copied if keep artist doesn't have one
        - Merged artists are deleted

        Args:
            keep_id: ID of the artist to keep
            merge_ids: IDs of artists to merge into keep artist

        Returns:
            Dict with merge stats (tracks_moved, albums_moved, artists_deleted)

        Raises:
            ValueError: If keep_id is in merge_ids or artists don't exist
        """
        from sqlalchemy import update

        from soulspot.infrastructure.persistence.models import TrackModel

        if keep_id in merge_ids:
            raise ValueError("keep_id cannot be in merge_ids")

        if not merge_ids:
            raise ValueError("merge_ids cannot be empty")

        # Verify all artists exist
        keep_stmt = select(ArtistModel).where(ArtistModel.id == keep_id)
        keep_result = await self._session.execute(keep_stmt)
        keep_artist = keep_result.scalar_one_or_none()

        if not keep_artist:
            raise ValueError(f"Keep artist {keep_id} not found")

        merge_stmt = select(ArtistModel).where(ArtistModel.id.in_(merge_ids))
        merge_result = await self._session.execute(merge_stmt)
        merge_artists = list(merge_result.scalars().all())

        if len(merge_artists) != len(merge_ids):
            found_ids = {a.id for a in merge_artists}
            missing = set(merge_ids) - found_ids
            raise ValueError(f"Merge artists not found: {missing}")

        stats = {
            "tracks_moved": 0,
            "albums_moved": 0,
            "artists_deleted": 0,
            "keep_artist": keep_artist.name,
            "merged_artists": [a.name for a in merge_artists],
        }

        # Transfer image_url if keep artist doesn't have one
        if not keep_artist.image_url:
            for ma in merge_artists:
                if ma.image_url:
                    keep_artist.image_url = ma.image_url
                    logger.debug(
                        f"Transferred image_url from '{ma.name}' to '{keep_artist.name}'"
                    )
                    break

        # Transfer spotify_uri if keep artist doesn't have one
        if not keep_artist.spotify_uri:
            for ma in merge_artists:
                if ma.spotify_uri:
                    keep_artist.spotify_uri = ma.spotify_uri
                    logger.debug(
                        f"Transferred spotify_uri from '{ma.name}' to '{keep_artist.name}'"
                    )
                    break

        # Move all tracks from merge artists to keep artist
        track_update = (
            update(TrackModel)
            .where(TrackModel.artist_id.in_(merge_ids))
            .values(artist_id=keep_id, updated_at=datetime.now(UTC))
        )
        track_result = await self._session.execute(track_update)
        stats["tracks_moved"] = track_result.rowcount

        # Move all albums from merge artists to keep artist
        album_update = (
            update(AlbumModel)
            .where(AlbumModel.artist_id.in_(merge_ids))
            .values(artist_id=keep_id, updated_at=datetime.now(UTC))
        )
        album_result = await self._session.execute(album_update)
        stats["albums_moved"] = album_result.rowcount

        # Delete merged artists
        for ma in merge_artists:
            await self._session.delete(ma)
            stats["artists_deleted"] += 1

        keep_artist.updated_at = datetime.now(UTC)

        await self._session.commit()

        logger.info(
            f"Merged {stats['artists_deleted']} artists into '{keep_artist.name}': "
            f"{stats['tracks_moved']} tracks, {stats['albums_moved']} albums moved"
        )

        return stats

    async def find_duplicate_albums(self) -> list[dict[str, Any]]:
        """Find potential duplicate albums by normalized name + artist matching.

        Groups albums with identical normalized titles from the same artist.

        Returns:
            List of duplicate groups, each containing:
            - normalized_name: The matching key (artist + album title)
            - albums: List of album dicts in this group
            - suggested_primary_id: ID of suggested "keep" album
        """
        from collections import defaultdict

        from sqlalchemy import func

        from soulspot.infrastructure.persistence.models import TrackModel

        # Get all albums with artist info
        stmt = select(AlbumModel, ArtistModel.name.label("artist_name")).join(
            ArtistModel, AlbumModel.artist_id == ArtistModel.id
        )
        result = await self._session.execute(stmt)
        all_albums = result.all()

        # Group by normalized artist + album title
        # Hey future me - AlbumModel has 'title' not 'name'! ArtistModel has 'name'.
        groups: dict[str, list[tuple[AlbumModel, str]]] = defaultdict(list)
        for album, artist_name in all_albums:
            normalized_artist = normalize_artist_name(artist_name or "Unknown")
            normalized_album = normalize_artist_name(album.title or "Unknown")
            key = f"{normalized_artist}::{normalized_album}"
            groups[key].append((album, artist_name))

        # Filter to groups with duplicates
        duplicate_groups: list[dict[str, Any]] = []

        for normalized_key, albums_with_artist in groups.items():
            if len(albums_with_artist) <= 1:
                continue

            # Get track counts for each album
            album_ids = [a.id for a, _ in albums_with_artist]
            track_counts_stmt = (
                select(TrackModel.album_id, func.count(TrackModel.id))
                .where(TrackModel.album_id.in_(album_ids))
                .group_by(TrackModel.album_id)
            )
            track_counts_result = await self._session.execute(track_counts_stmt)
            track_counts = dict(track_counts_result.all())

            # Build album info list
            # Hey future me - AlbumModel has 'title' not 'name'!
            album_infos = []
            for album, artist_name in albums_with_artist:
                album_infos.append({
                    "id": album.id,
                    "title": album.title,
                    "artist_name": artist_name,
                    "spotify_uri": album.spotify_uri,
                    "artwork_url": album.artwork_url,
                    "track_count": track_counts.get(album.id, 0),
                    "has_spotify": album.spotify_uri is not None,
                })

            # Suggest primary: prefer one with spotify_uri, then most tracks
            sorted_albums = sorted(
                album_infos,
                key=lambda x: (x["has_spotify"], x["track_count"]),
                reverse=True,
            )
            suggested_primary_id = sorted_albums[0]["id"]

            duplicate_groups.append({
                "normalized_key": normalized_key,
                "albums": album_infos,
                "suggested_primary_id": suggested_primary_id,
                "total_tracks": sum(a["track_count"] for a in album_infos),
            })

        # Sort by total tracks
        duplicate_groups.sort(key=lambda g: g["total_tracks"], reverse=True)

        logger.info(f"Found {len(duplicate_groups)} potential duplicate album groups")
        return duplicate_groups

    async def merge_albums(
        self, keep_id: str, merge_ids: list[str]
    ) -> dict[str, Any]:
        """Merge multiple albums into one, transferring all tracks.

        Args:
            keep_id: ID of the album to keep
            merge_ids: IDs of albums to merge into keep album

        Returns:
            Dict with merge stats
        """
        from sqlalchemy import update

        from soulspot.infrastructure.persistence.models import TrackModel

        if keep_id in merge_ids:
            raise ValueError("keep_id cannot be in merge_ids")

        if not merge_ids:
            raise ValueError("merge_ids cannot be empty")

        # Verify albums exist
        keep_stmt = select(AlbumModel).where(AlbumModel.id == keep_id)
        keep_result = await self._session.execute(keep_stmt)
        keep_album = keep_result.scalar_one_or_none()

        if not keep_album:
            raise ValueError(f"Keep album {keep_id} not found")

        merge_stmt = select(AlbumModel).where(AlbumModel.id.in_(merge_ids))
        merge_result = await self._session.execute(merge_stmt)
        merge_albums = list(merge_result.scalars().all())

        if len(merge_albums) != len(merge_ids):
            found_ids = {a.id for a in merge_albums}
            missing = set(merge_ids) - found_ids
            raise ValueError(f"Merge albums not found: {missing}")

        stats = {
            "tracks_moved": 0,
            "albums_deleted": 0,
            "keep_album": keep_album.name,
            "merged_albums": [a.name for a in merge_albums],
        }

        # Transfer artwork if keep album doesn't have one
        if not keep_album.artwork_url:
            for ma in merge_albums:
                if ma.artwork_url:
                    keep_album.artwork_url = ma.artwork_url
                    keep_album.artwork_path = ma.artwork_path
                    logger.debug(
                        f"Transferred artwork from '{ma.name}' to '{keep_album.name}'"
                    )
                    break

        # Transfer spotify_uri if keep album doesn't have one
        if not keep_album.spotify_uri:
            for ma in merge_albums:
                if ma.spotify_uri:
                    keep_album.spotify_uri = ma.spotify_uri
                    logger.debug(
                        f"Transferred spotify_uri from '{ma.name}' to '{keep_album.name}'"
                    )
                    break

        # Move all tracks from merge albums to keep album
        track_update = (
            update(TrackModel)
            .where(TrackModel.album_id.in_(merge_ids))
            .values(album_id=keep_id, updated_at=datetime.now(UTC))
        )
        track_result = await self._session.execute(track_update)
        stats["tracks_moved"] = track_result.rowcount

        # Delete merged albums
        for ma in merge_albums:
            await self._session.delete(ma)
            stats["albums_deleted"] += 1

        keep_album.updated_at = datetime.now(UTC)

        await self._session.commit()

        logger.info(
            f"Merged {stats['albums_deleted']} albums into '{keep_album.name}': "
            f"{stats['tracks_moved']} tracks moved"
        )

        return stats
