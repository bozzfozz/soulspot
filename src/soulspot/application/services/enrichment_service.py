"""Enrichment service for library metadata enhancement.

Hey future me - this service handles complex enrichment status queries,
candidate management, and applying enrichment matches. Centralizes logic
that was scattered across library.py routes.

Clean Architecture: Service → Repository → Domain
No direct Model access in this service.
"""

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import EnrichmentCandidate
from soulspot.domain.exceptions import EntityNotFoundError, InvalidOperationError
from soulspot.domain.ports import IEnrichmentCandidateRepository
from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)
from soulspot.infrastructure.persistence.repositories import (
    EnrichmentCandidateRepository,
)

logger = logging.getLogger(__name__)


class EnrichmentStatusDTO:
    """Data transfer object for enrichment status.

    Hey future me - this DTO returns all counts needed for UI:
    - artists_unenriched: Artists with local tracks but no Spotify URI
    - albums_unenriched: Albums with local tracks but no Spotify URI
    - pending_candidates: Candidates waiting for user review
    """

    def __init__(
        self,
        artists_unenriched: int,
        albums_unenriched: int,
        pending_candidates: int,
    ):
        self.artists_unenriched = artists_unenriched
        self.albums_unenriched = albums_unenriched
        self.pending_candidates = pending_candidates

    @property
    def is_enrichment_needed(self) -> bool:
        """Check if enrichment is needed."""
        return (self.artists_unenriched + self.albums_unenriched) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artists_unenriched": self.artists_unenriched,
            "albums_unenriched": self.albums_unenriched,
            "pending_candidates": self.pending_candidates,
            "is_enrichment_needed": self.is_enrichment_needed,
        }


class EnrichmentCandidateDTO:
    """Data transfer object for enrichment candidate with entity details.

    Hey future me - includes entity name (artist/album name) for display.
    Converts from EnrichmentCandidate domain entity.
    """

    def __init__(
        self,
        candidate: EnrichmentCandidate,
        entity_name: str,
    ):
        self.id = str(candidate.id)
        self.entity_type = candidate.entity_type.value
        self.entity_id = str(candidate.entity_id)
        self.entity_name = entity_name
        self.spotify_uri = candidate.spotify_uri
        self.spotify_name = candidate.spotify_name
        self.spotify_image_url = candidate.spotify_image_url
        self.confidence_score = candidate.confidence_score
        self.extra_info = candidate.extra_info or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "spotify_uri": self.spotify_uri,
            "spotify_name": self.spotify_name,
            "spotify_image_url": self.spotify_image_url,
            "confidence_score": self.confidence_score,
            "extra_info": self.extra_info,
        }


class EnrichmentService:
    """Service for library enrichment operations.

    Hey future me - centralizes complex enrichment queries that were
    in library.py routes. Uses EnrichmentCandidateRepository for domain
    operations, but pragmatically queries Models for unenriched counts
    (complex EXISTS subqueries).
    """

    def __init__(self, session: AsyncSession):
        """Initialize enrichment service.

        Args:
            session: Database session
        """
        self._session = session
        self._repo: IEnrichmentCandidateRepository = EnrichmentCandidateRepository(
            session
        )

    async def get_enrichment_status(self) -> EnrichmentStatusDTO:
        """Get enrichment status with unenriched counts.

        Hey future me - counts artists/albums with local tracks but no Spotify URI.
        Uses EXISTS subqueries to check for local tracks (file_path not null).
        Pending candidates are from repository.

        Returns:
            EnrichmentStatusDTO with counts
        """
        # Count unenriched artists (have local tracks, no Spotify URI)
        has_local_artist_tracks = (
            select(TrackModel.id)
            .where(TrackModel.artist_id == ArtistModel.id)
            .where(TrackModel.file_path.isnot(None))
            .exists()
        )
        artists_stmt = (
            select(func.count(ArtistModel.id))
            .where(ArtistModel.spotify_uri.is_(None))
            .where(has_local_artist_tracks)
        )
        artists_result = await self._session.execute(artists_stmt)
        artists_unenriched = artists_result.scalar() or 0

        # Count unenriched albums (have local tracks, no Spotify URI)
        has_local_album_tracks = (
            select(TrackModel.id)
            .where(TrackModel.album_id == AlbumModel.id)
            .where(TrackModel.file_path.isnot(None))
            .exists()
        )
        albums_stmt = (
            select(func.count(AlbumModel.id))
            .where(AlbumModel.spotify_uri.is_(None))
            .where(has_local_album_tracks)
        )
        albums_result = await self._session.execute(albums_stmt)
        albums_unenriched = albums_result.scalar() or 0

        # Count pending candidates (via repository)
        pending_candidates = await self._repo.count_pending()

        return EnrichmentStatusDTO(
            artists_unenriched=artists_unenriched,
            albums_unenriched=albums_unenriched,
            pending_candidates=pending_candidates,
        )

    async def list_candidates(
        self,
        entity_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EnrichmentCandidateDTO], int]:
        """List enrichment candidates for user review.

        Hey future me - returns pending candidates with entity names for display.
        Uses repository for candidates, queries Models for entity names.

        Args:
            entity_type: Filter by 'artist' or 'album' (optional)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (candidate DTOs, total count)
        """
        # Get candidates from repository
        candidates = await self._repo.list_pending(
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )

        # Count total
        total = await self._repo.count_pending(entity_type=entity_type)

        # Build DTOs with entity names
        dtos: list[EnrichmentCandidateDTO] = []
        for candidate in candidates:
            # Get entity name from Model (pragmatic approach)
            if candidate.entity_type.value == "artist":
                entity_stmt = select(ArtistModel.name).where(
                    ArtistModel.id == str(candidate.entity_id)
                )
            else:
                entity_stmt = select(AlbumModel.title).where(
                    AlbumModel.id == str(candidate.entity_id)
                )

            entity_result = await self._session.execute(entity_stmt)
            entity_name = entity_result.scalar() or "Unknown"

            dtos.append(EnrichmentCandidateDTO(candidate, entity_name))

        return dtos, total

    async def apply_candidate(
        self,
        candidate_id: str,
        spotify_image_service: Any,  # ImageService - avoid circular import
    ) -> dict[str, Any]:
        """Apply a user-selected enrichment candidate.

        Hey future me - marks candidate as selected, updates entity with Spotify URI/image,
        rejects other candidates for same entity. Uses repository + Models pragmatically.

        CRITICAL: Includes transaction rollback on errors to prevent DB corruption!

        Args:
            candidate_id: Candidate UUID
            spotify_image_service: ImageService for downloading images

        Returns:
            Result dictionary with entity_type, entity_id, spotify_uri

        Raises:
            ValueError: If candidate not found or already processed
        """
        try:
            logger.info(
                f"🎯 Apply Enrichment Candidate\n"
                f"└─ Candidate ID: {candidate_id}"
            )

            # Get candidate
            candidate = await self._repo.get_by_id(candidate_id)
            if not candidate:
                raise EntityNotFoundError(f"Enrichment candidate {candidate_id} not found")

            if candidate.is_selected or candidate.is_rejected:
                raise InvalidOperationError(
                    f"Candidate {candidate_id} already processed (selected={candidate.is_selected}, rejected={candidate.is_rejected})"
                )

            # Update entity with Spotify metadata (pragmatic Model access)
            entity_updated = False
            if candidate.entity_type.value == "artist":
                artist = await self._session.get(ArtistModel, str(candidate.entity_id))
                if artist:
                    artist.spotify_uri = candidate.spotify_uri

                    # Hey future me - keep URL vs local cache separate.
                    # image_url is the provider CDN URL; image_path is our local cache path.
                    if candidate.spotify_image_url:
                        artist.image_url = candidate.spotify_image_url

                    # Download image if URL provided
                    if candidate.spotify_image_url:
                        image_path = await spotify_image_service.download_artist_image(
                            str(artist.id),
                            candidate.spotify_image_url,
                        )
                        if image_path:
                            artist.image_path = image_path

                    entity_updated = True
            else:  # album
                album = await self._session.get(AlbumModel, str(candidate.entity_id))
                if album:
                    album.spotify_uri = candidate.spotify_uri

                    # Hey future me - cover_url is CDN URL; cover_path is our local cache path.
                    if candidate.spotify_image_url:
                        album.cover_url = candidate.spotify_image_url

                    # Download image if URL provided
                    if candidate.spotify_image_url:
                        image_path = await spotify_image_service.download_album_artwork(
                            str(album.id),
                            candidate.spotify_image_url,
                        )
                        if image_path:
                            album.cover_path = image_path

                    entity_updated = True

            if not entity_updated:
                raise EntityNotFoundError(
                    f"{candidate.entity_type.value.capitalize()} {candidate.entity_id} not found"
                )

            # Mark candidate as selected (also rejects others for same entity)
            selected_candidate = await self._repo.mark_selected(candidate_id)

            # Hey future me - we only log AFTER mark_selected() so we can show final URI reliably.
            logger.info(
                "✅ Enrichment Applied\n"
                "├─ Entity Type: %s\n"
                "├─ Entity ID: %s\n"
                "├─ Candidate ID: %s\n"
                "└─ Spotify URI: %s",
                selected_candidate.entity_type.value,
                str(selected_candidate.entity_id),
                candidate_id,
                selected_candidate.spotify_uri,
            )

            await self._session.commit()

            return {
                "entity_type": selected_candidate.entity_type.value,
                "entity_id": str(selected_candidate.entity_id),
                "spotify_uri": selected_candidate.spotify_uri,
                "message": "Candidate applied successfully",
            }
        except Exception as e:
            await self._session.rollback()
            logger.error(f"Failed to apply enrichment candidate {candidate_id}: {e}")
            raise

    async def reject_candidate(self, candidate_id: str) -> dict[str, Any]:
        """Reject an enrichment candidate.

        CRITICAL: Includes transaction rollback on errors!

        Args:
            candidate_id: Candidate UUID

        Returns:
            Result dictionary

        Raises:
            ValueError: If candidate not found
        """
        try:
            candidate = await self._repo.mark_rejected(candidate_id)
            await self._session.commit()

            return {
                "entity_type": candidate.entity_type.value,
                "entity_id": str(candidate.entity_id),
                "message": "Candidate rejected successfully",
            }
        except Exception as e:
            await self._session.rollback()
            logger.error(f"Failed to reject enrichment candidate {candidate_id}: {e}")
            raise
