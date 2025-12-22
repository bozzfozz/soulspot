"""Library Merge Service - Duplicate detection and entity merging.

Hey future me - this service handles duplicate detection and merging for library entities!

Common duplicate causes:
- Case differences: "Angerfist" vs "ANGERFIST"
- Article variations: "The Beatles" vs "Beatles, The"
- Prefix differences: "DJ Paul Elstak" vs "Paul Elstak"
- Scanner artifacts: Same album imported from two folders

The service uses normalize_artist_name() for matching, which strips common
prefixes (DJ, The, MC) and normalizes case for comparison.

Usage:
    service = LibraryMergeService(session)
    
    # Find duplicates
    artist_duplicates = await service.find_duplicate_artists()
    album_duplicates = await service.find_duplicate_albums()
    
    # Merge (user picks which to keep)
    result = await service.merge_artists(keep_id="uuid1", merge_ids=["uuid2", "uuid3"])
    result = await service.merge_albums(keep_id="uuid1", merge_ids=["uuid2"])

Design decisions:
- User ALWAYS chooses which entity to keep (we suggest, but don't auto-merge)
- Merge transfers ALL related data (tracks, albums, metadata)
- Missing data (images, URIs) is backfilled from merged entities
- Merged entities are DELETED after data transfer
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from soulspot.domain.exceptions import BusinessRuleViolation, EntityNotFoundError
from soulspot.domain.value_objects.artist_normalization import normalize_artist_name
from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class LibraryMergeService:
    """Service for duplicate detection and entity merging.
    
    Hey future me - this is a CLEAN replacement for the duplicate/merge methods
    that were in LocalLibraryEnrichmentService! Uses the new artist_normalization
    module for consistent name matching.
    
    Key features:
    - Find duplicate artists by normalized name
    - Find duplicate albums by normalized artist+title
    - Merge artists (transfer tracks, albums, metadata)
    - Merge albums (transfer tracks, metadata)
    - Automatic metadata backfill (images, URIs)
    """

    def __init__(self, session: "AsyncSession") -> None:
        """Initialize merge service.
        
        Args:
            session: Database session for queries and updates
        """
        self._session = session

    # =========================================================================
    # DUPLICATE ARTIST DETECTION
    # =========================================================================

    async def find_duplicate_artists(self) -> list[dict[str, Any]]:
        """Find potential duplicate artists by normalized name matching.

        Hey future me - groups artists with identical normalized names!
        Uses normalize_artist_name() to strip DJ/The/MC prefixes and lowercase.
        
        Example: "DJ Paul Elstak" and "Paul Elstak" would be in same group.

        Returns:
            List of duplicate groups, each containing:
            - normalized_name: The matching key (lowercase, stripped)
            - artists: List of artist dicts with id, name, spotify_uri, track_count
            - suggested_primary_id: ID of suggested "keep" artist
            - total_tracks: Combined track count for the group
        """
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
                    "deezer_id": a.deezer_id,
                    "image_url": a.image_url,
                    "track_count": track_counts.get(a.id, 0),
                    "has_spotify": a.spotify_uri is not None,
                    "has_deezer": a.deezer_id is not None,
                })

            # Suggest primary: prefer one with spotify_uri, then deezer_id, then most tracks
            sorted_artists = sorted(
                artist_infos,
                key=lambda x: (x["has_spotify"], x["has_deezer"], x["track_count"]),
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

    # =========================================================================
    # DUPLICATE ALBUM DETECTION
    # =========================================================================

    async def find_duplicate_albums(self) -> list[dict[str, Any]]:
        """Find potential duplicate albums by normalized name + artist matching.

        Hey future me - groups albums with identical normalized titles from same artist!
        Uses normalize_artist_name() for both artist name AND album title.
        
        Example: "Greatest Hits" by "The Prodigy" and "Greatest Hits" by "Prodigy"
        would be in same group.

        Returns:
            List of duplicate groups, each containing:
            - normalized_key: The matching key (artist::album)
            - albums: List of album dicts with id, title, spotify_uri, track_count
            - suggested_primary_id: ID of suggested "keep" album
            - total_tracks: Combined track count for the group
        """
        # Get all albums with artist info
        stmt = select(AlbumModel, ArtistModel.name.label("artist_name")).join(
            ArtistModel, AlbumModel.artist_id == ArtistModel.id
        )
        result = await self._session.execute(stmt)
        all_albums = result.all()

        # Group by normalized artist + album title
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
            album_infos = []
            for album, artist_name in albums_with_artist:
                album_infos.append({
                    "id": album.id,
                    "title": album.title,
                    "artist_name": artist_name,
                    "spotify_uri": album.spotify_uri,
                    "deezer_id": album.deezer_id,
                    "cover_url": album.cover_url,
                    "track_count": track_counts.get(album.id, 0),
                    "has_spotify": album.spotify_uri is not None,
                    "has_deezer": album.deezer_id is not None,
                })

            # Suggest primary: prefer one with spotify_uri, then deezer_id, then most tracks
            sorted_albums = sorted(
                album_infos,
                key=lambda x: (x["has_spotify"], x["has_deezer"], x["track_count"]),
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

    # =========================================================================
    # ARTIST MERGE
    # =========================================================================

    async def merge_artists(
        self, keep_id: str, merge_ids: list[str]
    ) -> dict[str, Any]:
        """Merge multiple artists into one, transferring all tracks and albums.

        Hey future me - the 'keep' artist absorbs all data from 'merge' artists!
        
        What gets transferred:
        - All tracks are reassigned to keep_id
        - All albums are reassigned to keep_id
        - image_url is copied if keep artist doesn't have one
        - spotify_uri, deezer_id are copied if keep artist doesn't have them
        - Merged artists are DELETED after transfer

        Args:
            keep_id: ID of the artist to keep
            merge_ids: IDs of artists to merge into keep artist

        Returns:
            Dict with merge stats (tracks_moved, albums_moved, artists_deleted)

        Raises:
            BusinessRuleViolation: If keep_id is in merge_ids or merge_ids empty
            EntityNotFoundError: If any artist doesn't exist
        """
        if keep_id in merge_ids:
            raise BusinessRuleViolation("keep_id cannot be in merge_ids")

        if not merge_ids:
            raise BusinessRuleViolation("merge_ids cannot be empty")

        # Verify keep artist exists
        keep_stmt = select(ArtistModel).where(ArtistModel.id == keep_id)
        keep_result = await self._session.execute(keep_stmt)
        keep_artist = keep_result.scalar_one_or_none()

        if not keep_artist:
            raise EntityNotFoundError(f"Keep artist {keep_id} not found")

        # Verify merge artists exist
        merge_stmt = select(ArtistModel).where(ArtistModel.id.in_(merge_ids))
        merge_result = await self._session.execute(merge_stmt)
        merge_artists = list(merge_result.scalars().all())

        if len(merge_artists) != len(merge_ids):
            found_ids = {a.id for a in merge_artists}
            missing = set(merge_ids) - found_ids
            raise EntityNotFoundError(f"Merge artists not found: {missing}")

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
                    keep_artist.image_path = ma.image_path
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

        # Transfer deezer_id if keep artist doesn't have one
        if not keep_artist.deezer_id:
            for ma in merge_artists:
                if ma.deezer_id:
                    keep_artist.deezer_id = ma.deezer_id
                    logger.debug(
                        f"Transferred deezer_id from '{ma.name}' to '{keep_artist.name}'"
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

    # =========================================================================
    # ALBUM MERGE
    # =========================================================================

    async def merge_albums(
        self, keep_id: str, merge_ids: list[str]
    ) -> dict[str, Any]:
        """Merge multiple albums into one, transferring all tracks.

        Hey future me - the 'keep' album absorbs all data from 'merge' albums!
        
        What gets transferred:
        - All tracks are reassigned to keep_id
        - cover_url/cover_path is copied if keep album doesn't have one
        - spotify_uri, deezer_id are copied if keep album doesn't have them
        - Merged albums are DELETED after transfer

        Args:
            keep_id: ID of the album to keep
            merge_ids: IDs of albums to merge into keep album

        Returns:
            Dict with merge stats (tracks_moved, albums_deleted)

        Raises:
            BusinessRuleViolation: If keep_id is in merge_ids or merge_ids empty
            EntityNotFoundError: If any album doesn't exist
        """
        if keep_id in merge_ids:
            raise BusinessRuleViolation("keep_id cannot be in merge_ids")

        if not merge_ids:
            raise BusinessRuleViolation("merge_ids cannot be empty")

        # Verify keep album exists
        keep_stmt = select(AlbumModel).where(AlbumModel.id == keep_id)
        keep_result = await self._session.execute(keep_stmt)
        keep_album = keep_result.scalar_one_or_none()

        if not keep_album:
            raise EntityNotFoundError(f"Keep album {keep_id} not found")

        # Verify merge albums exist
        merge_stmt = select(AlbumModel).where(AlbumModel.id.in_(merge_ids))
        merge_result = await self._session.execute(merge_stmt)
        merge_albums = list(merge_result.scalars().all())

        if len(merge_albums) != len(merge_ids):
            found_ids = {a.id for a in merge_albums}
            missing = set(merge_ids) - found_ids
            raise EntityNotFoundError(f"Merge albums not found: {missing}")

        stats = {
            "tracks_moved": 0,
            "albums_deleted": 0,
            "keep_album": keep_album.title,
            "merged_albums": [a.title for a in merge_albums],
        }

        # Transfer artwork if keep album doesn't have one
        if not keep_album.cover_url:
            for ma in merge_albums:
                if ma.cover_url:
                    keep_album.cover_url = ma.cover_url
                    keep_album.cover_path = ma.cover_path
                    logger.debug(
                        f"Transferred artwork from '{ma.title}' to '{keep_album.title}'"
                    )
                    break

        # Transfer spotify_uri if keep album doesn't have one
        if not keep_album.spotify_uri:
            for ma in merge_albums:
                if ma.spotify_uri:
                    keep_album.spotify_uri = ma.spotify_uri
                    logger.debug(
                        f"Transferred spotify_uri from '{ma.title}' to '{keep_album.title}'"
                    )
                    break

        # Transfer deezer_id if keep album doesn't have one
        if not keep_album.deezer_id:
            for ma in merge_albums:
                if ma.deezer_id:
                    keep_album.deezer_id = ma.deezer_id
                    logger.debug(
                        f"Transferred deezer_id from '{ma.title}' to '{keep_album.title}'"
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
            f"Merged {stats['albums_deleted']} albums into '{keep_album.title}': "
            f"{stats['tracks_moved']} tracks moved"
        )

        return stats
