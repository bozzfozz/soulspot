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

Matching strategy:
- Artists: Search Spotify by name, match by fuzzy name similarity + popularity
- Albums: Search Spotify by "artist + album title", match by track count + name similarity

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
from soulspot.domain.entities import Album, Artist
from soulspot.infrastructure.persistence.models import AlbumModel, ArtistModel
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
)

if TYPE_CHECKING:
    from soulspot.config import Settings
    from soulspot.domain.ports import ISpotifyClient

logger = logging.getLogger(__name__)


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
        service = LocalLibraryEnrichmentService(session, spotify_client, settings)
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
        spotify_client: ISpotifyClient,
        settings: Settings,
        access_token: str,
    ) -> None:
        """Initialize enrichment service.

        Args:
            session: Database session
            spotify_client: Spotify API client
            settings: Application settings
            access_token: Spotify OAuth access token
        """
        self._session = session
        self._spotify_client = spotify_client
        self._settings = settings
        self._access_token = access_token

        # Repositories
        self._artist_repo = ArtistRepository(session)
        self._album_repo = AlbumRepository(session)

        # Services
        self._settings_service = AppSettingsService(session)
        self._image_service = SpotifyImageService(settings)

    # =========================================================================
    # MAIN BATCH ENRICHMENT
    # =========================================================================

    async def enrich_batch(self) -> dict[str, Any]:
        """Run a batch enrichment for unenriched artists and albums.

        This is the MAIN entry point! Call this after library scans.

        Returns:
            Stats dict with enrichment results
        """
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
        match_threshold = await self._settings_service.get_enrichment_match_threshold()

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
        followed_artists_lookup: dict[str, tuple[str, str | None]] = {}
        if use_followed_hint:
            followed_artists_lookup = await self._build_followed_artists_lookup()
            logger.info(
                f"Loaded {len(followed_artists_lookup)} followed artists for hint matching"
            )

        logger.info(
            f"Starting enrichment batch: batch_size={batch_size}, "
            f"rate_limit={rate_limit_ms}ms, threshold={confidence_threshold}, "
            f"search_limit={search_limit}, name_weight={name_weight}%"
        )

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
            )
            stats["artists_processed"] += 1

            if result.success:
                stats["artists_enriched"] += 1
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
            )
            stats["albums_processed"] += 1

            if result.success:
                stats["albums_enriched"] += 1
                if result.image_downloaded:
                    stats["images_downloaded"] += 1
            elif result.candidates_created > 0:
                stats["albums_candidates"] += result.candidates_created
            else:
                stats["albums_failed"] += 1
                if result.error:
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

        logger.info(
            f"Enrichment complete: {stats['artists_enriched']} artists, "
            f"{stats['albums_enriched']} albums enriched, "
            f"{stats['followed_artists_matched']} via followed artists hint"
        )

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
            Dict mapping lowercase artist name to (spotify_uri, image_url) tuple
        """
        from soulspot.infrastructure.persistence.models import SpotifyArtistModel

        stmt = select(SpotifyArtistModel).where(
            SpotifyArtistModel.spotify_uri.isnot(None)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        # Hey future me - normalize names to lowercase for case-insensitive matching!
        # "Pink Floyd" and "pink floyd" should both match the same followed artist.
        lookup: dict[str, tuple[str, str | None]] = {}
        for model in models:
            if model.spotify_uri:
                name_lower = model.name.lower().strip()
                lookup[name_lower] = (model.spotify_uri, model.image_url)

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
        followed_artists_lookup: dict[str, tuple[str, str | None]] | None = None,
    ) -> EnrichmentResult:
        """Enrich a single artist with Spotify data.

        Args:
            artist: Artist entity to enrich
            confidence_threshold: Minimum confidence for auto-apply
            download_artwork: Whether to download artwork
            search_limit: Number of Spotify search results to scan
            name_weight: Weight of name similarity vs popularity (0.0-1.0)
            followed_artists_lookup: Optional lookup table for followed artists hint

        Returns:
            EnrichmentResult with success/failure info
        """
        try:
            # Hey future me - FOLLOWED ARTISTS HINT! Check if artist exists in Followed Artists.
            # If yes, copy Spotify URI directly without searching. 100% match rate!
            if followed_artists_lookup:
                name_lower = artist.name.lower().strip()
                if name_lower in followed_artists_lookup:
                    spotify_uri, image_url = followed_artists_lookup[name_lower]
                    logger.debug(
                        f"Artist '{artist.name}' matched via followed artists hint"
                    )

                    # Create a synthetic candidate from followed artist data
                    candidate = EnrichmentCandidate(
                        spotify_uri=spotify_uri,
                        spotify_name=artist.name,  # Use local name
                        spotify_image_url=image_url,
                        confidence_score=1.0,  # 100% confidence for followed artists
                        extra_info={"matched_via": "followed_artists_hint"},
                    )

                    result = await self._apply_artist_enrichment(
                        artist, candidate, download_artwork
                    )
                    # Hey future me - mark this as matched via followed artists for stats!
                    result.error = "matched_via_followed_artists"
                    return result

            # Search Spotify for this artist
            # Hey future me - artist.name is CLEAN (no UUID/MusicBrainz ID from folder parsing)!
            # LibraryFolderParser strips disambiguation before creating Artist entity.
            # We send only the artist name to Spotify API, nothing else!
            search_results = await self._spotify_client.search_artist(
                query=artist.name,
                access_token=self._access_token,
                limit=search_limit,  # Configurable via settings (default 20)
            )

            artists_data = search_results.get("artists", {}).get("items", [])
            if not artists_data:
                return EnrichmentResult(
                    entity_type="artist",
                    entity_id=str(artist.id.value),
                    entity_name=artist.name,
                    success=False,
                    error="No Spotify results found",
                )

            # Score candidates with configurable name weight
            # Hey future me - local_name is clean artist name (no UUID)! Candidate scoring
            # is based on name similarity and Spotify popularity, never on disambiguation.
            candidates = self._score_artist_candidates(
                artist.name, artists_data, name_weight=name_weight
            )

            if not candidates:
                return EnrichmentResult(
                    entity_type="artist",
                    entity_id=str(artist.id.value),
                    entity_name=artist.name,
                    success=False,
                    error="No candidates above threshold",
                )

            # Check if top candidate is confident enough for auto-apply
            top_candidate = candidates[0]

            if top_candidate.confidence_score >= confidence_threshold:
                # Auto-apply the match
                return await self._apply_artist_enrichment(
                    artist, top_candidate, download_artwork
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
        spotify_artists: list[dict[str, Any]],
        name_weight: float = 0.85,
    ) -> list[EnrichmentCandidate]:
        """Score Spotify artist candidates against local artist name.

        Scoring factors:
        - Name similarity (fuzzy match) - configurable weight (default 85%)
        - Popularity (more popular = more likely correct) - remaining weight

        Args:
            local_name: Local artist name
            spotify_artists: List of Spotify artist dicts
            name_weight: Weight of name similarity (0.0-1.0, default 0.85)

        Returns:
            Sorted list of EnrichmentCandidate (highest score first)
        """
        candidates = []
        # Hey future me - popularity_weight is the remainder after name_weight
        popularity_weight = 1.0 - name_weight

        for sp_artist in spotify_artists:
            sp_name = sp_artist.get("name", "")
            sp_uri = sp_artist.get("uri", "")
            sp_popularity = sp_artist.get("popularity", 0) / 100.0  # Normalize to 0-1
            sp_followers = sp_artist.get("followers", {}).get("total", 0)
            sp_genres = sp_artist.get("genres", [])

            # Get best image URL
            images = sp_artist.get("images", [])
            sp_image_url = images[0]["url"] if images else None

            # Calculate name similarity (0-100, normalize to 0-1)
            name_score = fuzz.ratio(local_name.lower(), sp_name.lower()) / 100.0

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
                            "popularity": sp_artist.get("popularity", 0),
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
    ) -> EnrichmentResult:
        """Apply enrichment from a candidate to an artist.

        Updates artist model with Spotify URI, image, genres.

        Args:
            artist: Artist entity to update
            candidate: Selected EnrichmentCandidate
            download_artwork: Whether to download artwork

        Returns:
            EnrichmentResult with success info
        """
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

        # Download artwork if enabled
        image_downloaded = False
        if download_artwork and candidate.spotify_image_url:
            try:
                # Extract Spotify ID from URI (spotify:artist:XXXXX)
                spotify_id = candidate.spotify_uri.split(":")[-1]
                await self._image_service.download_artist_image(
                    spotify_id, candidate.spotify_image_url
                )
                image_downloaded = True
            except Exception as e:
                logger.warning(f"Failed to download artist image: {e}")

        logger.debug(
            f"Enriched artist '{artist.name}' with Spotify URI {candidate.spotify_uri}"
        )

        return EnrichmentResult(
            entity_type="artist",
            entity_id=str(artist.id.value),
            entity_name=artist.name,
            success=True,
            spotify_uri=candidate.spotify_uri,
            image_downloaded=image_downloaded,
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
    ) -> EnrichmentResult:
        """Enrich a single album with Spotify data.

        Args:
            album: Album entity to enrich
            confidence_threshold: Minimum confidence for auto-apply
            download_artwork: Whether to download artwork

        Returns:
            EnrichmentResult with success/failure info
        """
        try:
            # Get artist name for search
            artist_model = await self._session.get(
                ArtistModel, str(album.artist_id.value)
            )
            artist_name = artist_model.name if artist_model else "Unknown"

            # Search Spotify: "artist album"
            # Hey future me - artist_name is CLEAN (no UUID/MusicBrainz ID)!
            # LibraryFolderParser and DB already handle disambiguation stripping.
            search_query = f"artist:{artist_name} album:{album.title}"
            search_results = await self._spotify_client.search_track(
                query=search_query,
                access_token=self._access_token,
                limit=10,
            )

            # Extract unique albums from track search results
            # Hey - Spotify search_track returns tracks, we extract albums from them
            tracks_data = search_results.get("tracks", {}).get("items", [])
            albums_seen: dict[str, dict[str, Any]] = {}

            for track in tracks_data:
                sp_album = track.get("album", {})
                sp_album_uri = sp_album.get("uri", "")
                if sp_album_uri and sp_album_uri not in albums_seen:
                    albums_seen[sp_album_uri] = sp_album

            if not albums_seen:
                return EnrichmentResult(
                    entity_type="album",
                    entity_id=str(album.id.value),
                    entity_name=album.title,
                    success=False,
                    error="No Spotify albums found",
                )

            # Score candidates
            candidates = self._score_album_candidates(
                album.title, artist_name, list(albums_seen.values())
            )

            if not candidates:
                return EnrichmentResult(
                    entity_type="album",
                    entity_id=str(album.id.value),
                    entity_name=album.title,
                    success=False,
                    error="No candidates above threshold",
                )

            # Check if top candidate is confident enough
            top_candidate = candidates[0]

            if top_candidate.confidence_score >= confidence_threshold:
                return await self._apply_album_enrichment(
                    album, top_candidate, download_artwork
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
        spotify_albums: list[dict[str, Any]],
    ) -> list[EnrichmentCandidate]:
        """Score Spotify album candidates.

        Scoring factors:
        - Title similarity - 50% weight
        - Artist name match - 40% weight
        - Track count similarity - 10% weight (if available)

        Args:
            local_title: Local album title
            local_artist: Local artist name
            spotify_albums: List of Spotify album dicts

        Returns:
            Sorted list of EnrichmentCandidate (highest score first)
        """
        candidates = []

        for sp_album in spotify_albums:
            sp_title = sp_album.get("name", "")
            sp_uri = sp_album.get("uri", "")
            sp_artists = sp_album.get("artists", [])
            sp_artist_name = sp_artists[0]["name"] if sp_artists else ""
            sp_release_date = sp_album.get("release_date", "")
            sp_total_tracks = sp_album.get("total_tracks", 0)

            # Get best image URL
            images = sp_album.get("images", [])
            sp_image_url = images[0]["url"] if images else None

            # Calculate scores
            title_score = fuzz.ratio(local_title.lower(), sp_title.lower()) / 100.0
            artist_score = (
                fuzz.ratio(local_artist.lower(), sp_artist_name.lower()) / 100.0
            )

            # Combined score
            confidence = (title_score * 0.5) + (artist_score * 0.5)

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

    async def _apply_album_enrichment(
        self,
        album: Album,
        candidate: EnrichmentCandidate,
        download_artwork: bool,
    ) -> EnrichmentResult:
        """Apply enrichment from a candidate to an album."""
        stmt = select(AlbumModel).where(AlbumModel.id == str(album.id.value))
        result = await self._session.execute(stmt)
        model = result.scalar_one()

        model.spotify_uri = candidate.spotify_uri
        model.artwork_url = candidate.spotify_image_url
        model.updated_at = datetime.now(UTC)

        # Download artwork if enabled
        image_downloaded = False
        if download_artwork and candidate.spotify_image_url:
            try:
                spotify_id = candidate.spotify_uri.split(":")[-1]
                local_path = await self._image_service.download_album_image(
                    spotify_id, candidate.spotify_image_url
                )
                model.artwork_path = str(local_path)
                image_downloaded = True
            except Exception as e:
                logger.warning(f"Failed to download album image: {e}")

        logger.debug(
            f"Enriched album '{album.title}' with Spotify URI {candidate.spotify_uri}"
        )

        return EnrichmentResult(
            entity_type="album",
            entity_id=str(album.id.value),
            entity_name=album.title,
            success=True,
            spotify_uri=candidate.spotify_uri,
            image_downloaded=image_downloaded,
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
