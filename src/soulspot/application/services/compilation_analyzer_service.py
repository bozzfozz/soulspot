# Hey future me - this service analyzes albums AFTER scan to detect compilations via track diversity!
#
# WHY separate service? During library scan, we process files one-by-one. The compilation detection
# based on "many different track artists" requires ALL tracks of an album to be known first.
# So we run this AFTER scan completes (or as periodic task) to catch compilations that weren't
# obvious from explicit flags or album_artist tags alone.
#
# USAGE:
#   analyzer = CompilationAnalyzerService(session)
#   results = await analyzer.analyze_all_albums()  # Re-check all albums
#   results = await analyzer.analyze_album(album_id)  # Check single album
#
# Phase 3: MusicBrainz verification for borderline cases:
#   analyzer = CompilationAnalyzerService(session, musicbrainz_client)
#   result = await analyzer.verify_with_musicbrainz(album_id)
#
# This implements Lidarr's TrackGroupingService.IsVariousArtists() logic for track diversity.
"""Post-scan compilation analyzer using track artist diversity."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.value_objects.album_types import (
    MIN_TRACKS_FOR_DIVERSITY,
    SecondaryAlbumType,
    detect_compilation,
)
from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)

if TYPE_CHECKING:
    from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient

logger = logging.getLogger(__name__)


@dataclass
class AlbumAnalysisResult:
    """Result of compilation analysis for a single album."""
    
    album_id: str
    album_title: str
    previous_is_compilation: bool
    new_is_compilation: bool
    detection_reason: str
    confidence: float
    track_count: int
    unique_artists: int
    changed: bool
    musicbrainz_verified: bool = False
    musicbrainz_mbid: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response."""
        return {
            "album_id": self.album_id,
            "album_title": self.album_title,
            "previous_is_compilation": self.previous_is_compilation,
            "new_is_compilation": self.new_is_compilation,
            "detection_reason": self.detection_reason,
            "confidence": round(self.confidence, 2),
            "track_count": self.track_count,
            "unique_artists": self.unique_artists,
            "changed": self.changed,
            "musicbrainz_verified": self.musicbrainz_verified,
            "musicbrainz_mbid": self.musicbrainz_mbid,
        }


class CompilationAnalyzerService:
    """Service for analyzing albums to detect compilations via track diversity.
    
    Hey future me - this is the POST-SCAN analyzer! The library scanner detects compilations
    from explicit flags (TCMP/cpil) and album_artist patterns. But what about albums where:
    - No explicit flag was set
    - Album artist is the first track's artist (not "Various Artists")
    - But actually 10 different artists contributed tracks!
    
    This service fills that gap by checking track-level artist diversity AFTER all tracks
    are imported. Run it:
    1. After full library scan completes
    2. Periodically as background task
    3. On-demand for specific albums
    
    Phase 3 (optional): MusicBrainz verification for borderline cases (50-75% diversity).
    Pass a MusicBrainzClient to enable this feature.
    """
    
    def __init__(
        self, 
        session: AsyncSession,
        musicbrainz_client: "MusicBrainzClient | None" = None,
    ) -> None:
        """Initialize analyzer.
        
        Args:
            session: Database session for queries and updates.
            musicbrainz_client: Optional MusicBrainz client for Phase 3 verification.
        """
        self.session = session
        self.musicbrainz_client = musicbrainz_client
    
    async def analyze_album(self, album_id: str) -> AlbumAnalysisResult | None:
        """Analyze a single album for compilation status.
        
        Hey future me - this is the single-album entry point!
        
        Args:
            album_id: UUID of the album to analyze.
            
        Returns:
            AlbumAnalysisResult with detection details, or None if album not found.
        """
        # Get album with artist
        stmt = (
            select(AlbumModel, ArtistModel)
            .outerjoin(ArtistModel, AlbumModel.artist_id == ArtistModel.id)
            .where(AlbumModel.id == album_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        
        if not row:
            logger.warning(f"Album not found: {album_id}")
            return None
        
        album, artist = row
        
        # Get all track artists for this album
        # Hey - we want track-level artists, not the album's assigned artist!
        track_artists_stmt = (
            select(ArtistModel.name)
            .join(TrackModel, TrackModel.artist_id == ArtistModel.id)
            .where(TrackModel.album_id == album_id)
        )
        track_artists_result = await self.session.execute(track_artists_stmt)
        track_artists = [row[0] for row in track_artists_result.all()]
        
        # Current compilation status
        current_secondary_types = album.secondary_types or []
        was_compilation = SecondaryAlbumType.COMPILATION.value in current_secondary_types
        
        # Run detection with full data (now we have track_artists!)
        # Hey - the explicit_flag would come from metadata, but post-scan we don't have it
        # We can check if album was ALREADY marked as compilation (from scan-time detection)
        detection = detect_compilation(
            album_artist=album.album_artist,
            track_artists=track_artists,
            explicit_flag=was_compilation if was_compilation else None,  # Preserve prior detection
        )
        
        # Determine if we should update
        changed = detection.is_compilation != was_compilation
        
        if changed:
            # Update secondary_types
            new_secondary_types = list(current_secondary_types)
            if detection.is_compilation and SecondaryAlbumType.COMPILATION.value not in new_secondary_types:
                new_secondary_types.append(SecondaryAlbumType.COMPILATION.value)
            elif not detection.is_compilation and SecondaryAlbumType.COMPILATION.value in new_secondary_types:
                new_secondary_types.remove(SecondaryAlbumType.COMPILATION.value)
            
            # Apply update
            update_stmt = (
                update(AlbumModel)
                .where(AlbumModel.id == album_id)
                .values(secondary_types=new_secondary_types)
            )
            await self.session.execute(update_stmt)
            
            logger.info(
                f"Album '{album.title}' compilation status changed: "
                f"{was_compilation} → {detection.is_compilation} "
                f"(reason: {detection.reason}, confidence: {detection.confidence:.0%})"
            )
        
        # Build result
        unique_artists = len(set(a.lower().strip() for a in track_artists if a))
        
        return AlbumAnalysisResult(
            album_id=album_id,
            album_title=album.title,
            previous_is_compilation=was_compilation,
            new_is_compilation=detection.is_compilation,
            detection_reason=detection.reason,
            confidence=detection.confidence,
            track_count=len(track_artists),
            unique_artists=unique_artists,
            changed=changed,
        )
    
    async def analyze_all_albums(
        self,
        only_undetected: bool = True,
        min_tracks: int = MIN_TRACKS_FOR_DIVERSITY,
    ) -> list[AlbumAnalysisResult]:
        """Analyze all albums for compilation status.
        
        Hey future me - this is the bulk analysis entry point!
        Use after full library scan or as periodic cleanup task.
        
        Args:
            only_undetected: If True, only analyze albums NOT already marked as compilations.
                            This saves time by skipping albums where detection already worked.
            min_tracks: Minimum track count to analyze (diversity needs data!).
            
        Returns:
            List of AlbumAnalysisResult for each analyzed album.
        """
        # Get albums with track counts
        # Hey - we subquery to filter by track count BEFORE loading
        track_count_subq = (
            select(TrackModel.album_id, func.count(TrackModel.id).label("track_count"))
            .group_by(TrackModel.album_id)
            .having(func.count(TrackModel.id) >= min_tracks)
            .subquery()
        )
        
        stmt = (
            select(AlbumModel.id)
            .join(track_count_subq, AlbumModel.id == track_count_subq.c.album_id)
        )
        
        if only_undetected:
            # Only albums where secondary_types doesn't contain 'compilation'
            # Hey - JSON contains check varies by DB. For SQLite, this works:
            stmt = stmt.where(
                ~AlbumModel.secondary_types.contains([SecondaryAlbumType.COMPILATION.value])
            )
        
        result = await self.session.execute(stmt)
        album_ids = [row[0] for row in result.all()]
        
        logger.info(f"Analyzing {len(album_ids)} albums for compilation status")
        
        results: list[AlbumAnalysisResult] = []
        changed_count = 0
        
        for album_id in album_ids:
            analysis = await self.analyze_album(album_id)
            if analysis:
                results.append(analysis)
                if analysis.changed:
                    changed_count += 1
        
        # Commit all changes
        await self.session.commit()
        
        logger.info(
            f"Compilation analysis complete: {len(results)} albums analyzed, "
            f"{changed_count} status changes"
        )
        
        return results
    
    async def get_compilation_stats(self) -> dict[str, Any]:
        """Get statistics about compilations in the library.
        
        Returns:
            Dict with compilation counts and percentages.
        """
        # Total albums
        total_stmt = select(func.count(AlbumModel.id))
        total_result = await self.session.execute(total_stmt)
        total_albums = total_result.scalar() or 0
        
        # Albums marked as compilation
        # Hey - checking JSON array containment varies by DB. This is SQLite-compatible.
        compilation_stmt = select(func.count(AlbumModel.id)).where(
            AlbumModel.secondary_types.contains([SecondaryAlbumType.COMPILATION.value])
        )
        compilation_result = await self.session.execute(compilation_stmt)
        compilation_albums = compilation_result.scalar() or 0
        
        # Albums with "Various Artists" album_artist
        va_stmt = select(func.count(AlbumModel.id)).where(
            func.lower(AlbumModel.album_artist).in_([
                "various artists", "various", "va", "v.a."
            ])
        )
        va_result = await self.session.execute(va_stmt)
        va_albums = va_result.scalar() or 0
        
        return {
            "total_albums": total_albums,
            "compilation_albums": compilation_albums,
            "various_artists_albums": va_albums,
            "compilation_percent": round(
                (compilation_albums / total_albums * 100) if total_albums > 0 else 0, 1
            ),
        }

    # =========================================================================
    # PHASE 3: MusicBrainz Verification
    # =========================================================================

    async def verify_with_musicbrainz(
        self, 
        album_id: str,
        update_if_confirmed: bool = True,
    ) -> dict[str, Any]:
        """Verify compilation status via MusicBrainz API.
        
        Hey future me - this is Phase 3! Use for borderline cases where local heuristics
        aren't sure (50-75% diversity). MusicBrainz has authoritative data on whether
        an album is a compilation.
        
        Args:
            album_id: UUID of album to verify.
            update_if_confirmed: If True and MB confirms/denies, update DB.
            
        Returns:
            Dict with verification result:
            - verified: bool (True if MB lookup succeeded)
            - is_compilation: bool (MB's answer)
            - reason: str (mb_various_artists, mb_compilation_type, etc.)
            - confidence: float
            - mbid: str | None (MusicBrainz release group ID)
            - updated: bool (True if DB was updated)
        """
        result: dict[str, Any] = {
            "verified": False,
            "is_compilation": False,
            "reason": "not_verified",
            "confidence": 0.0,
            "mbid": None,
            "updated": False,
        }
        
        if not self.musicbrainz_client:
            result["reason"] = "musicbrainz_client_not_configured"
            return result
        
        # Get album info
        stmt = (
            select(AlbumModel, ArtistModel)
            .outerjoin(ArtistModel, AlbumModel.artist_id == ArtistModel.id)
            .where(AlbumModel.id == album_id)
        )
        db_result = await self.session.execute(stmt)
        row = db_result.first()
        
        if not row:
            result["reason"] = "album_not_found"
            return result
        
        album, artist = row
        artist_name = album.album_artist or (artist.name if artist else None)
        
        # Call MusicBrainz
        mb_result = await self.musicbrainz_client.verify_compilation(
            album_title=album.title,
            album_artist=artist_name,
        )
        
        result["verified"] = mb_result.get("reason", "").startswith("mb_")
        result["is_compilation"] = mb_result.get("is_compilation", False)
        result["reason"] = mb_result.get("reason", "unknown")
        result["confidence"] = mb_result.get("confidence", 0.0)
        result["mbid"] = mb_result.get("mbid")
        
        # Update DB if requested and MB gave confident answer
        if update_if_confirmed and result["verified"] and result["confidence"] >= 0.7:
            current_secondary_types = album.secondary_types or []
            was_compilation = SecondaryAlbumType.COMPILATION.value in current_secondary_types
            
            if result["is_compilation"] != was_compilation:
                new_secondary_types = list(current_secondary_types)
                
                if result["is_compilation"]:
                    if SecondaryAlbumType.COMPILATION.value not in new_secondary_types:
                        new_secondary_types.append(SecondaryAlbumType.COMPILATION.value)
                else:
                    if SecondaryAlbumType.COMPILATION.value in new_secondary_types:
                        new_secondary_types.remove(SecondaryAlbumType.COMPILATION.value)
                
                # Update album
                update_stmt = (
                    update(AlbumModel)
                    .where(AlbumModel.id == album_id)
                    .values(
                        secondary_types=new_secondary_types,
                        musicbrainz_id=result["mbid"],  # Store MBID for future reference
                    )
                )
                await self.session.execute(update_stmt)
                await self.session.commit()
                
                result["updated"] = True
                logger.info(
                    f"Album '{album.title}' compilation status updated via MusicBrainz: "
                    f"{was_compilation} → {result['is_compilation']} "
                    f"(reason: {result['reason']}, mbid: {result['mbid']})"
                )
        
        return result

    async def verify_borderline_albums(
        self,
        diversity_min: float = 0.5,
        diversity_max: float = 0.75,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Verify borderline albums (50-75% diversity) via MusicBrainz.
        
        Hey future me - this is the batch MusicBrainz verification!
        Finds albums where local heuristics are uncertain and asks MusicBrainz.
        
        CAUTION: MusicBrainz has strict rate limits (1 req/sec). With limit=50,
        this takes at least 50 seconds. Run during off-peak or as background task!
        
        Args:
            diversity_min: Minimum diversity ratio to consider borderline (default 0.5).
            diversity_max: Maximum diversity ratio (above this, local detection works).
            limit: Max albums to verify (respect MusicBrainz rate limits!).
            
        Returns:
            List of verification results.
        """
        if not self.musicbrainz_client:
            logger.warning("MusicBrainz client not configured, skipping verification")
            return []
        
        # Find albums with borderline diversity
        # Hey future me - we need to:
        # 1. Get albums NOT marked as compilation with enough tracks
        # 2. Calculate diversity per album
        # 3. Filter to diversity_min <= diversity <= diversity_max
        
        # Step 1: Get candidate albums with track counts
        track_count_subq = (
            select(
                TrackModel.album_id,
                func.count(TrackModel.id).label("track_count"),
            )
            .group_by(TrackModel.album_id)
            .having(func.count(TrackModel.id) >= MIN_TRACKS_FOR_DIVERSITY)
            .subquery()
        )
        
        stmt = (
            select(AlbumModel.id, AlbumModel.title, track_count_subq.c.track_count)
            .join(track_count_subq, AlbumModel.id == track_count_subq.c.album_id)
            .where(
                ~AlbumModel.secondary_types.contains([SecondaryAlbumType.COMPILATION.value])
            )
        )
        
        db_result = await self.session.execute(stmt)
        candidate_albums = db_result.all()
        
        # Step 2 & 3: Calculate diversity and filter to borderline range
        # Hey - we need to get unique artist count per album to compute diversity
        borderline_albums: list[tuple[str, str, float]] = []
        
        for album_id, album_title, track_count in candidate_albums:
            # Get unique artists for this album
            unique_artists_stmt = (
                select(func.count(func.distinct(TrackModel.artist_id)))
                .where(TrackModel.album_id == album_id)
            )
            unique_result = await self.session.execute(unique_artists_stmt)
            unique_count = unique_result.scalar() or 0
            
            # Calculate diversity ratio
            diversity = unique_count / track_count if track_count > 0 else 0
            
            # Filter to borderline range
            if diversity_min <= diversity <= diversity_max:
                borderline_albums.append((album_id, album_title, diversity))
                
                # Respect limit
                if len(borderline_albums) >= limit:
                    break
        
        logger.info(
            f"Found {len(borderline_albums)} borderline albums "
            f"(diversity {diversity_min:.0%}-{diversity_max:.0%}) for MusicBrainz verification"
        )
        
        results: list[dict[str, Any]] = []
        for album_id, album_title, diversity in borderline_albums:
            try:
                verification = await self.verify_with_musicbrainz(
                    album_id=album_id,
                    update_if_confirmed=True,
                )
                verification["album_id"] = album_id
                verification["album_title"] = album_title
                verification["diversity_ratio"] = diversity
                results.append(verification)
                
            except Exception as e:
                logger.warning(f"MusicBrainz verification failed for '{album_title}': {e}")
                results.append({
                    "album_id": album_id,
                    "album_title": album_title,
                    "verified": False,
                    "reason": f"error: {type(e).__name__}",
                })
        
        verified_count = sum(1 for r in results if r.get("verified"))
        updated_count = sum(1 for r in results if r.get("updated"))
        
        logger.info(
            f"MusicBrainz verification complete: {verified_count}/{len(results)} verified, "
            f"{updated_count} updated"
        )
        
        return results

    async def set_compilation_status(
        self,
        album_id: str,
        is_compilation: bool,
        reason: str = "manual_override",
    ) -> bool:
        """Manually set compilation status for an album.
        
        Hey future me - this is the manual override! User says "this IS/ISN'T a compilation"
        and we respect that. Sets a special detection reason so we know it was manual.
        
        Args:
            album_id: UUID of album.
            is_compilation: True = mark as compilation, False = remove compilation status.
            reason: Reason for override (shown in UI).
            
        Returns:
            True if update succeeded, False if album not found.
        """
        # Get album
        stmt = select(AlbumModel).where(AlbumModel.id == album_id)
        result = await self.session.execute(stmt)
        album = result.scalar_one_or_none()
        
        if not album:
            logger.warning(f"Album not found for manual override: {album_id}")
            return False
        
        current_secondary_types = album.secondary_types or []
        was_compilation = SecondaryAlbumType.COMPILATION.value in current_secondary_types
        
        if is_compilation == was_compilation:
            logger.debug(f"Album '{album.title}' already has compilation={is_compilation}")
            return True  # No change needed
        
        new_secondary_types = list(current_secondary_types)
        
        if is_compilation:
            if SecondaryAlbumType.COMPILATION.value not in new_secondary_types:
                new_secondary_types.append(SecondaryAlbumType.COMPILATION.value)
        else:
            if SecondaryAlbumType.COMPILATION.value in new_secondary_types:
                new_secondary_types.remove(SecondaryAlbumType.COMPILATION.value)
        
        # Update album
        update_stmt = (
            update(AlbumModel)
            .where(AlbumModel.id == album_id)
            .values(secondary_types=new_secondary_types)
        )
        await self.session.execute(update_stmt)
        await self.session.commit()
        
        logger.info(
            f"Album '{album.title}' compilation status manually set: "
            f"{was_compilation} → {is_compilation} (reason: {reason})"
        )
        
        return True
