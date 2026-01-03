# Hey future me – this is the ASYNC part of deduplication. Unlike deduplication_checker.py
# which must be fast (<50ms) for import-time, this service can take its sweet time.
# Runs scheduled (nightly/weekly) to find and merge duplicates across the entire library.
# The reason we split this out: finding ALL duplicates across 100k tracks takes minutes,
# but we can't block imports waiting for that. So checker is sync+fast, this is async+thorough.
"""
DeduplicationHousekeepingService: Async scheduled duplicate detection and resolution.

This service handles library-wide duplicate scanning that runs in the background:
- Periodic full-library scans (nightly/weekly)
- UI-triggered duplicate resolution
- Bulk merge operations with FK transfer
- File deletion for resolved duplicates

Split from:
- library_merge_service.py: find_duplicate_*, merge_* methods
- duplicate_service.py: list_candidates, resolve_candidate, get_counts

Performance: Can take minutes for large libraries - runs async only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from soulspot.domain.entities import Album, Artist, Track
from soulspot.domain.value_objects import normalize_artist_name

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.infrastructure.persistence.repositories import (
        AlbumRepository,
        ArtistRepository,
        TrackRepository,
    )


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DuplicateGroup:
    """
    Group of duplicate entities with a canonical (keep) and duplicates (merge/delete).

    Hey future me – the 'canonical' is the one we keep based on priority:
    - Most complete metadata wins
    - Oldest created_at wins (tie-breaker)
    - Manual selection can override via resolve_candidate()
    """

    entity_type: str  # 'artist', 'album', 'track'
    canonical: Artist | Album | Track
    duplicates: list[Artist | Album | Track] = field(default_factory=list)
    match_reason: str = ""  # e.g., "ISRC match", "name+duration match"

    @property
    def total_count(self) -> int:
        return 1 + len(self.duplicates)


@dataclass
class DuplicateCounts:
    """Summary counts for UI display."""

    artist_groups: int = 0
    album_groups: int = 0
    track_groups: int = 0

    @property
    def total_groups(self) -> int:
        return self.artist_groups + self.album_groups + self.track_groups


@dataclass
class MergeResult:
    """Result of a merge operation."""

    success: bool
    kept_id: int
    merged_ids: list[int]
    files_deleted: list[str] = field(default_factory=list)
    error: str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# HOUSEKEEPING SERVICE
# ═══════════════════════════════════════════════════════════════════════════════


class DeduplicationHousekeepingService:
    """
    Async service for scheduled duplicate detection and resolution.

    This runs in the background (nightly/weekly) to find and clean up duplicates
    across the entire library. Unlike DeduplicationChecker which is fast for imports,
    this can take minutes and runs async.

    Usage:
        service = DeduplicationHousekeepingService(session, artist_repo, album_repo, track_repo)
        counts = await service.get_duplicate_counts()
        groups = await service.find_duplicate_artists()
        result = await service.merge_artist_group(group)
    """

    def __init__(
        self,
        session: AsyncSession,
        artist_repository: ArtistRepository,
        album_repository: AlbumRepository,
        track_repository: TrackRepository,
    ) -> None:
        self._session = session
        self._artist_repo = artist_repository
        self._album_repo = album_repository
        self._track_repo = track_repository

    # ───────────────────────────────────────────────────────────────────────────
    # COUNTS (for UI dashboard)
    # ───────────────────────────────────────────────────────────────────────────

    async def get_duplicate_counts(self) -> DuplicateCounts:
        """
        Get summary counts of duplicate groups.

        Hey future me – this is intentionally a quick count query, not a full scan.
        For the full scan, use find_duplicate_* methods.
        """
        # Count artist duplicates (same normalized name)
        all_artists = await self._artist_repo.get_all()
        artist_groups = self._count_duplicate_groups_by_name(
            [(a.id, a.name) for a in all_artists]
        )

        # Count album duplicates (same artist + title)
        all_albums = await self._album_repo.get_all()
        album_groups = self._count_duplicate_groups_by_key(
            [(a.id, f"{a.artist_id}:{self._normalize(a.title)}") for a in all_albums]
        )

        # Count track duplicates (by ISRC or name+duration)
        all_tracks = await self._track_repo.get_all()
        track_groups = self._count_track_duplicate_groups(all_tracks)

        return DuplicateCounts(
            artist_groups=artist_groups,
            album_groups=album_groups,
            track_groups=track_groups,
        )

    def _count_duplicate_groups_by_name(
        self, items: list[tuple[int, str]]
    ) -> int:
        """Count groups where normalized name matches multiple items."""
        name_to_ids: dict[str, list[int]] = {}
        for item_id, name in items:
            normalized = self._normalize(name)
            if normalized not in name_to_ids:
                name_to_ids[normalized] = []
            name_to_ids[normalized].append(item_id)

        return sum(1 for ids in name_to_ids.values() if len(ids) > 1)

    def _count_duplicate_groups_by_key(
        self, items: list[tuple[int, str]]
    ) -> int:
        """Count groups where key matches multiple items."""
        key_to_ids: dict[str, list[int]] = {}
        for item_id, key in items:
            if key not in key_to_ids:
                key_to_ids[key] = []
            key_to_ids[key].append(item_id)

        return sum(1 for ids in key_to_ids.values() if len(ids) > 1)

    def _count_track_duplicate_groups(self, tracks: list[Track]) -> int:
        """
        Count track duplicate groups by ISRC or name+duration.

        Hey future me – tracks are trickier because we have multiple match strategies:
        1. ISRC match (most reliable)
        2. Same album + title + duration (±3 sec)
        We count both but avoid double-counting.
        """
        seen_ids: set[int] = set()
        group_count = 0

        # First pass: ISRC matches
        isrc_to_tracks: dict[str, list[Track]] = {}
        for track in tracks:
            if track.isrc:
                if track.isrc not in isrc_to_tracks:
                    isrc_to_tracks[track.isrc] = []
                isrc_to_tracks[track.isrc].append(track)

        for isrc_tracks in isrc_to_tracks.values():
            if len(isrc_tracks) > 1:
                group_count += 1
                for t in isrc_tracks:
                    seen_ids.add(t.id)

        # Second pass: name+album+duration matches (excluding already counted)
        key_to_tracks: dict[str, list[Track]] = {}
        for track in tracks:
            if track.id in seen_ids:
                continue
            key = f"{track.album_id}:{self._normalize(track.title)}:{track.duration_ms // 3000}"
            if key not in key_to_tracks:
                key_to_tracks[key] = []
            key_to_tracks[key].append(track)

        for key_tracks in key_to_tracks.values():
            if len(key_tracks) > 1:
                group_count += 1

        return group_count

    # ───────────────────────────────────────────────────────────────────────────
    # FIND DUPLICATES (full library scan)
    # ───────────────────────────────────────────────────────────────────────────

    async def find_duplicate_artists(self) -> list[DuplicateGroup]:
        """
        Find all duplicate artist groups in the library.

        Returns groups where multiple artists have the same normalized name.
        The artist with most albums/tracks becomes canonical.
        """
        all_artists = await self._artist_repo.get_all()

        # Group by normalized name
        name_to_artists: dict[str, list[Artist]] = {}
        for artist in all_artists:
            normalized = self._normalize(artist.name)
            if normalized not in name_to_artists:
                name_to_artists[normalized] = []
            name_to_artists[normalized].append(artist)

        groups: list[DuplicateGroup] = []
        for name, artists in name_to_artists.items():
            if len(artists) < 2:
                continue

            # Sort by completeness: most external IDs first, then oldest
            sorted_artists = sorted(
                artists,
                key=lambda a: (
                    -self._artist_completeness_score(a),
                    a.created_at or datetime.min.replace(tzinfo=timezone.utc),
                ),
            )

            canonical = sorted_artists[0]
            duplicates = sorted_artists[1:]

            groups.append(
                DuplicateGroup(
                    entity_type="artist",
                    canonical=canonical,
                    duplicates=duplicates,
                    match_reason=f"normalized name: {name}",
                )
            )

        logger.info(f"Found {len(groups)} duplicate artist groups")
        return groups

    async def find_duplicate_albums(self) -> list[DuplicateGroup]:
        """
        Find all duplicate album groups in the library.

        Returns groups where multiple albums have same artist + normalized title.
        The album with most tracks becomes canonical.
        """
        all_albums = await self._album_repo.get_all()

        # Group by artist_id + normalized title
        key_to_albums: dict[str, list[Album]] = {}
        for album in all_albums:
            key = f"{album.artist_id}:{self._normalize(album.title)}"
            if key not in key_to_albums:
                key_to_albums[key] = []
            key_to_albums[key].append(album)

        groups: list[DuplicateGroup] = []
        for key, albums in key_to_albums.items():
            if len(albums) < 2:
                continue

            # Sort by completeness: most tracks, most metadata, oldest
            sorted_albums = sorted(
                albums,
                key=lambda a: (
                    -self._album_completeness_score(a),
                    a.created_at or datetime.min.replace(tzinfo=timezone.utc),
                ),
            )

            canonical = sorted_albums[0]
            duplicates = sorted_albums[1:]

            groups.append(
                DuplicateGroup(
                    entity_type="album",
                    canonical=canonical,
                    duplicates=duplicates,
                    match_reason=f"artist+title: {key}",
                )
            )

        logger.info(f"Found {len(groups)} duplicate album groups")
        return groups

    async def find_duplicate_tracks(self) -> list[DuplicateGroup]:
        """
        Find all duplicate track groups in the library.

        Match strategies:
        1. ISRC match (highest confidence)
        2. Same album + title + duration (±3 sec)
        """
        all_tracks = await self._track_repo.get_all()
        groups: list[DuplicateGroup] = []
        seen_ids: set[int] = set()

        # Pass 1: ISRC matches
        isrc_to_tracks: dict[str, list[Track]] = {}
        for track in all_tracks:
            if track.isrc:
                if track.isrc not in isrc_to_tracks:
                    isrc_to_tracks[track.isrc] = []
                isrc_to_tracks[track.isrc].append(track)

        for isrc, isrc_tracks in isrc_to_tracks.items():
            if len(isrc_tracks) < 2:
                continue

            sorted_tracks = sorted(
                isrc_tracks,
                key=lambda t: (
                    -self._track_completeness_score(t),
                    t.created_at or datetime.min.replace(tzinfo=timezone.utc),
                ),
            )

            canonical = sorted_tracks[0]
            duplicates = sorted_tracks[1:]

            groups.append(
                DuplicateGroup(
                    entity_type="track",
                    canonical=canonical,
                    duplicates=duplicates,
                    match_reason=f"ISRC: {isrc}",
                )
            )

            for t in isrc_tracks:
                seen_ids.add(t.id)

        # Pass 2: name+album+duration matches
        key_to_tracks: dict[str, list[Track]] = {}
        for track in all_tracks:
            if track.id in seen_ids:
                continue
            # Duration bucket: ±3 seconds (3000ms)
            duration_bucket = (track.duration_ms or 0) // 3000
            key = f"{track.album_id}:{self._normalize(track.title)}:{duration_bucket}"
            if key not in key_to_tracks:
                key_to_tracks[key] = []
            key_to_tracks[key].append(track)

        for key, key_tracks in key_to_tracks.items():
            if len(key_tracks) < 2:
                continue

            sorted_tracks = sorted(
                key_tracks,
                key=lambda t: (
                    -self._track_completeness_score(t),
                    t.created_at or datetime.min.replace(tzinfo=timezone.utc),
                ),
            )

            canonical = sorted_tracks[0]
            duplicates = sorted_tracks[1:]

            groups.append(
                DuplicateGroup(
                    entity_type="track",
                    canonical=canonical,
                    duplicates=duplicates,
                    match_reason=f"album+title+duration: {key}",
                )
            )

        logger.info(f"Found {len(groups)} duplicate track groups")
        return groups

    # ───────────────────────────────────────────────────────────────────────────
    # MERGE OPERATIONS (resolve duplicates)
    # ───────────────────────────────────────────────────────────────────────────

    async def merge_artist_group(
        self,
        group: DuplicateGroup,
        *,
        canonical_override: Artist | None = None,
    ) -> MergeResult:
        """
        Merge a duplicate artist group into a single artist.

        Steps:
        1. Transfer all albums from duplicates to canonical
        2. Merge metadata (fill gaps in canonical)
        3. Delete duplicate artist records

        Hey future me – we DON'T delete files here because artists don't have files.
        Files are only at track level.
        """
        if group.entity_type != "artist":
            return MergeResult(
                success=False,
                kept_id=0,
                merged_ids=[],
                error=f"Expected artist group, got {group.entity_type}",
            )

        canonical = canonical_override or group.canonical
        if not isinstance(canonical, Artist):
            return MergeResult(
                success=False,
                kept_id=0,
                merged_ids=[],
                error="Canonical is not an Artist",
            )

        merged_ids: list[int] = []

        try:
            for dup in group.duplicates:
                if not isinstance(dup, Artist):
                    continue
                if canonical_override and dup.id == canonical.id:
                    continue

                # Transfer albums from duplicate to canonical
                albums = await self._album_repo.get_by_artist_id(dup.id)
                for album in albums:
                    album.artist_id = canonical.id
                    await self._album_repo.update(album)

                # Merge metadata into canonical
                canonical = self._merge_artist_metadata(canonical, dup)

                # Delete duplicate
                await self._artist_repo.delete(dup.id)
                merged_ids.append(dup.id)

            # Update canonical with merged metadata
            await self._artist_repo.update(canonical)
            await self._session.commit()

            logger.info(
                f"Merged {len(merged_ids)} artists into {canonical.id} ({canonical.name})"
            )

            return MergeResult(
                success=True,
                kept_id=canonical.id,
                merged_ids=merged_ids,
            )

        except Exception as e:
            await self._session.rollback()
            logger.error(f"Failed to merge artist group: {e}")
            return MergeResult(
                success=False,
                kept_id=canonical.id,
                merged_ids=merged_ids,
                error=str(e),
            )

    async def merge_album_group(
        self,
        group: DuplicateGroup,
        *,
        canonical_override: Album | None = None,
    ) -> MergeResult:
        """
        Merge a duplicate album group into a single album.

        Steps:
        1. Transfer all tracks from duplicates to canonical
        2. Merge metadata (fill gaps in canonical)
        3. Delete duplicate album records
        """
        if group.entity_type != "album":
            return MergeResult(
                success=False,
                kept_id=0,
                merged_ids=[],
                error=f"Expected album group, got {group.entity_type}",
            )

        canonical = canonical_override or group.canonical
        if not isinstance(canonical, Album):
            return MergeResult(
                success=False,
                kept_id=0,
                merged_ids=[],
                error="Canonical is not an Album",
            )

        merged_ids: list[int] = []

        try:
            for dup in group.duplicates:
                if not isinstance(dup, Album):
                    continue
                if canonical_override and dup.id == canonical.id:
                    continue

                # Transfer tracks from duplicate to canonical
                tracks = await self._track_repo.get_by_album_id(dup.id)
                for track in tracks:
                    track.album_id = canonical.id
                    await self._track_repo.update(track)

                # Merge metadata into canonical
                canonical = self._merge_album_metadata(canonical, dup)

                # Delete duplicate
                await self._album_repo.delete(dup.id)
                merged_ids.append(dup.id)

            # Update canonical with merged metadata
            await self._album_repo.update(canonical)
            await self._session.commit()

            logger.info(
                f"Merged {len(merged_ids)} albums into {canonical.id} ({canonical.title})"
            )

            return MergeResult(
                success=True,
                kept_id=canonical.id,
                merged_ids=merged_ids,
            )

        except Exception as e:
            await self._session.rollback()
            logger.error(f"Failed to merge album group: {e}")
            return MergeResult(
                success=False,
                kept_id=canonical.id,
                merged_ids=merged_ids,
                error=str(e),
            )

    async def merge_track_group(
        self,
        group: DuplicateGroup,
        *,
        canonical_override: Track | None = None,
        delete_files: bool = True,
    ) -> MergeResult:
        """
        Merge a duplicate track group into a single track.

        Steps:
        1. Keep canonical track's file
        2. Optionally delete duplicate files from disk
        3. Merge metadata (fill gaps in canonical)
        4. Delete duplicate track records

        Hey future me – file deletion is the tricky part. We use Path.unlink()
        but only if delete_files=True (user can preview first).
        """
        if group.entity_type != "track":
            return MergeResult(
                success=False,
                kept_id=0,
                merged_ids=[],
                error=f"Expected track group, got {group.entity_type}",
            )

        canonical = canonical_override or group.canonical
        if not isinstance(canonical, Track):
            return MergeResult(
                success=False,
                kept_id=0,
                merged_ids=[],
                error="Canonical is not a Track",
            )

        merged_ids: list[int] = []
        files_deleted: list[str] = []

        try:
            for dup in group.duplicates:
                if not isinstance(dup, Track):
                    continue
                if canonical_override and dup.id == canonical.id:
                    continue

                # Delete file if requested
                if delete_files and dup.file_path:
                    deleted = self._delete_track_file(dup.file_path)
                    if deleted:
                        files_deleted.append(dup.file_path)

                # Merge metadata into canonical
                canonical = self._merge_track_metadata(canonical, dup)

                # Delete duplicate
                await self._track_repo.delete(dup.id)
                merged_ids.append(dup.id)

            # Update canonical with merged metadata
            await self._track_repo.update(canonical)
            await self._session.commit()

            logger.info(
                f"Merged {len(merged_ids)} tracks into {canonical.id} ({canonical.title}), "
                f"deleted {len(files_deleted)} files"
            )

            return MergeResult(
                success=True,
                kept_id=canonical.id,
                merged_ids=merged_ids,
                files_deleted=files_deleted,
            )

        except Exception as e:
            await self._session.rollback()
            logger.error(f"Failed to merge track group: {e}")
            return MergeResult(
                success=False,
                kept_id=canonical.id,
                merged_ids=merged_ids,
                files_deleted=files_deleted,
                error=str(e),
            )

    async def resolve_track_candidate(
        self,
        keep_track_id: int,
        delete_track_id: int,
        *,
        delete_file: bool = True,
    ) -> MergeResult:
        """
        Resolve a specific track duplicate pair by keeping one and deleting the other.

        This is the UI-facing method for manual duplicate resolution.
        """
        keep_track = await self._track_repo.get_by_id(keep_track_id)
        delete_track = await self._track_repo.get_by_id(delete_track_id)

        if not keep_track:
            return MergeResult(
                success=False,
                kept_id=keep_track_id,
                merged_ids=[],
                error=f"Track {keep_track_id} not found",
            )

        if not delete_track:
            return MergeResult(
                success=False,
                kept_id=keep_track_id,
                merged_ids=[],
                error=f"Track {delete_track_id} not found",
            )

        # Create a synthetic group for the merge
        group = DuplicateGroup(
            entity_type="track",
            canonical=keep_track,
            duplicates=[delete_track],
            match_reason="manual resolution",
        )

        return await self.merge_track_group(
            group,
            canonical_override=keep_track,
            delete_files=delete_file,
        )

    # ───────────────────────────────────────────────────────────────────────────
    # BATCH OPERATIONS (for scheduled cleanup)
    # ───────────────────────────────────────────────────────────────────────────

    async def auto_merge_all_duplicates(
        self,
        *,
        dry_run: bool = False,
        delete_files: bool = True,
    ) -> dict[str, list[MergeResult]]:
        """
        Automatically merge all detected duplicates.

        Use dry_run=True to preview what would be merged without making changes.

        Hey future me – this is the big nightly job. It can take a while for large
        libraries. Consider adding progress callbacks for the UI.
        """
        results: dict[str, list[MergeResult]] = {
            "artists": [],
            "albums": [],
            "tracks": [],
        }

        # Artists first (albums depend on them)
        artist_groups = await self.find_duplicate_artists()
        for group in artist_groups:
            if dry_run:
                results["artists"].append(
                    MergeResult(
                        success=True,
                        kept_id=group.canonical.id,
                        merged_ids=[d.id for d in group.duplicates],
                    )
                )
            else:
                result = await self.merge_artist_group(group)
                results["artists"].append(result)

        # Albums second (tracks depend on them)
        album_groups = await self.find_duplicate_albums()
        for group in album_groups:
            if dry_run:
                results["albums"].append(
                    MergeResult(
                        success=True,
                        kept_id=group.canonical.id,
                        merged_ids=[d.id for d in group.duplicates],
                    )
                )
            else:
                result = await self.merge_album_group(group)
                results["albums"].append(result)

        # Tracks last
        track_groups = await self.find_duplicate_tracks()
        for group in track_groups:
            if dry_run:
                results["tracks"].append(
                    MergeResult(
                        success=True,
                        kept_id=group.canonical.id,
                        merged_ids=[d.id for d in group.duplicates],
                        files_deleted=[
                            d.file_path
                            for d in group.duplicates
                            if isinstance(d, Track) and d.file_path
                        ],
                    )
                )
            else:
                result = await self.merge_track_group(group, delete_files=delete_files)
                results["tracks"].append(result)

        total = sum(len(r) for r in results.values())
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Auto-merged {total} duplicate groups")

        return results

    # ───────────────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ───────────────────────────────────────────────────────────────────────────

    def _normalize(self, text: str | None) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        return normalize_artist_name(text)

    def _artist_completeness_score(self, artist: Artist) -> int:
        """
        Score artist by metadata completeness.

        Hey future me – higher score = more complete = better canonical candidate.
        We prefer artists with more external IDs because they're easier to re-link.
        """
        score = 0
        if artist.musicbrainz_id:
            score += 10  # MBID is gold
        if artist.spotify_uri:
            score += 5
        if artist.deezer_id:
            score += 5
        if artist.image_url:
            score += 2
        if artist.genres:
            score += 1
        return score

    def _album_completeness_score(self, album: Album) -> int:
        """Score album by metadata completeness."""
        score = 0
        if album.musicbrainz_id:
            score += 10
        if album.spotify_uri:
            score += 5
        if album.deezer_id:
            score += 5
        if album.artwork_url:
            score += 2
        if album.release_date:
            score += 1
        if album.total_tracks and album.total_tracks > 0:
            score += 1
        return score

    def _track_completeness_score(self, track: Track) -> int:
        """Score track by metadata completeness."""
        score = 0
        if track.isrc:
            score += 10  # ISRC is gold for tracks
        if track.musicbrainz_id:
            score += 8
        if track.spotify_uri:
            score += 5
        if track.deezer_id:
            score += 5
        if track.file_path:
            score += 3  # Has actual file
        if track.duration_ms:
            score += 1
        if track.track_number:
            score += 1
        return score

    def _merge_artist_metadata(self, canonical: Artist, source: Artist) -> Artist:
        """
        Merge metadata from source into canonical (fill gaps only).

        Hey future me – we NEVER overwrite existing data, only fill gaps.
        This prevents losing the "better" canonical data.
        """
        if not canonical.musicbrainz_id and source.musicbrainz_id:
            canonical.musicbrainz_id = source.musicbrainz_id
        if not canonical.spotify_uri and source.spotify_uri:
            canonical.spotify_uri = source.spotify_uri
        if not canonical.deezer_id and source.deezer_id:
            canonical.deezer_id = source.deezer_id
        if not canonical.image_url and source.image_url:
            canonical.image_url = source.image_url
        if not canonical.genres and source.genres:
            canonical.genres = source.genres
        return canonical

    def _merge_album_metadata(self, canonical: Album, source: Album) -> Album:
        """Merge metadata from source into canonical (fill gaps only)."""
        if not canonical.musicbrainz_id and source.musicbrainz_id:
            canonical.musicbrainz_id = source.musicbrainz_id
        if not canonical.spotify_uri and source.spotify_uri:
            canonical.spotify_uri = source.spotify_uri
        if not canonical.deezer_id and source.deezer_id:
            canonical.deezer_id = source.deezer_id
        if not canonical.artwork_url and source.artwork_url:
            canonical.artwork_url = source.artwork_url
        if not canonical.release_date and source.release_date:
            canonical.release_date = source.release_date
        if not canonical.total_tracks and source.total_tracks:
            canonical.total_tracks = source.total_tracks
        return canonical

    def _merge_track_metadata(self, canonical: Track, source: Track) -> Track:
        """Merge metadata from source into canonical (fill gaps only)."""
        if not canonical.isrc and source.isrc:
            canonical.isrc = source.isrc
        if not canonical.musicbrainz_id and source.musicbrainz_id:
            canonical.musicbrainz_id = source.musicbrainz_id
        if not canonical.spotify_uri and source.spotify_uri:
            canonical.spotify_uri = source.spotify_uri
        if not canonical.deezer_id and source.deezer_id:
            canonical.deezer_id = source.deezer_id
        if not canonical.duration_ms is None and source.duration_ms:
            canonical.duration_ms = source.duration_ms
        if not canonical.track_number and source.track_number:
            canonical.track_number = source.track_number
        if not canonical.disc_number and source.disc_number:
            canonical.disc_number = source.disc_number
        # DON'T merge file_path – we keep canonical's file
        return canonical

    def _delete_track_file(self, file_path: str) -> bool:
        """
        Delete a track file from disk.

        Hey future me – this is the scary part. We log before AND after deletion.
        If deletion fails, we log but don't raise – the DB record still gets deleted,
        leaving an orphan file (better than failing the whole merge).
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.debug(f"File already deleted or missing: {file_path}")
                return False

            logger.info(f"Deleting duplicate file: {file_path}")
            path.unlink()
            logger.info(f"Successfully deleted: {file_path}")
            return True

        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {e}")
            return False
