# Hey future me - this service scans the local music directory and imports files into the DB!
# Key features:
# 1. JOB QUEUE integration - runs as background job (use JobQueue for async scanning)
# 2. LIDARR FOLDER PARSING - Artist/Album/Track from folder structure (100% accurate!)
# 3. INCREMENTAL SCAN - only processes new/changed files based on mtime
# 4. COMPILATION DETECTION - from folder structure ("Various Artists" folder)
# The goal: import existing music collection, avoid re-downloading already owned tracks!
"""Library scanner service for importing local music files into database."""

import asyncio
import contextlib
import hashlib
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile  # type: ignore[attr-defined]
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.config import Settings
from soulspot.domain.entities import Album, Artist, ArtistSource, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, FilePath, TrackId
from soulspot.domain.value_objects.album_types import (
    SecondaryAlbumType,
    is_various_artists,
)
from soulspot.domain.value_objects.folder_parsing import (
    AUDIO_EXTENSIONS,
    LibraryFolderParser,
    LibraryScanResult,
    ScannedTrack,
    is_disc_folder,
    parse_album_folder,
    parse_track_filename,
)
from soulspot.infrastructure.observability.logger_template import (
    end_operation,
    start_operation,
)
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

logger = logging.getLogger(__name__)

# AUDIO_EXTENSIONS is now imported from folder_parsing module (single source of truth)

# Hey future me - Semaphore to limit concurrent background discography syncs!
# SQLite can only handle ONE writer at a time - parallel writes cause "database is locked".
# Limit to 2 concurrent syncs (one writing, one waiting for lock).
_DISCOGRAPHY_SYNC_SEMAPHORE = asyncio.Semaphore(2)


class LibraryScannerService:
    """Service for scanning Lidarr-organized music library and importing to database.

    Hey future me - this is now LIDARR-FIRST! Artist/Album/Track come from folder structure,
    not from ID3 tags. Mutagen is only used for audio info (duration, bitrate, genre).

    This service handles:
    1. Parsing Lidarr folder structure: /Artist/Album (Year)/NN - Title.ext
    2. Extracting audio info via mutagen (duration, bitrate, sample_rate, genre)
    3. Exact name matching for artists/albums (no fuzzy matching needed!)
    4. Incremental scanning (only new/modified files)
    5. Compilation detection via "Various Artists" folder

    Works with JobQueue for background processing!
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize scanner service.

        Args:
            session: Database session
            settings: Application settings (for music_path)
        """
        self._session = session
        self.settings = settings
        self.artist_repo = ArtistRepository(session)
        self.album_repo = AlbumRepository(session)
        self.track_repo = TrackRepository(session)
        self.music_path = settings.storage.music_path

        # Cache for exact name matching (avoid repeated DB queries)
        # Key: lowercase name, Value: entity ID
        self._artist_cache: dict[str, ArtistId] = {}
        self._album_cache: dict[str, AlbumId] = {}

        # Thread pool for CPU-intensive work (metadata extraction)
        # Hey future me - this runs metadata parsing in parallel threads
        # so the event loop stays responsive. DB work stays async/serial.
        # SHA256 hashing is NOT done here - it runs in a separate nightly DUPLICATE_SCAN job!
        self._executor = ThreadPoolExecutor(
            max_workers=min(8, max(2, os.cpu_count() or 4))
        )

    # =========================================================================
    # AUTO-DISCOGRAPHY SYNC (for LOCAL artists after scan)
    # =========================================================================

    async def _background_discography_sync(
        self, artist_id: str, artist_name: str
    ) -> None:
        """Background task to sync discography for a newly scanned LOCAL artist.

        Hey future me - SAME LOGIC as artists.py _background_discography_sync!
        When local folder is scanned, new artists should get their FULL discography
        from providers (Spotify/Deezer). This ensures LOCAL artists are treated
        the same as "Add to Library" button artists.

        GOTCHA: Must create own DB session! The scan session may be busy/committed.
        Create fresh Database instance with settings and use session_scope().

        CRITICAL: Uses semaphore to limit concurrent writes to SQLite!
        SQLite can only handle ONE writer at a time - parallel writes cause
        "database is locked" errors. Semaphore ensures max 2 tasks (1 writing, 1 waiting).

        Args:
            artist_id: The artist UUID (string format)
            artist_name: Artist name for logging
        """
        # Acquire semaphore to limit concurrent database writes
        async with _DISCOGRAPHY_SYNC_SEMAPHORE:
            from soulspot.application.services.artist_service import ArtistService
            from soulspot.config import get_settings
            from soulspot.infrastructure.persistence.database import Database
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
            from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

            logger.info(f"🎵 Background discography sync starting for LOCAL artist: {artist_name}")

            try:
                # Create fresh Database instance for background task
                db = Database(get_settings())
                async with db.session_scope() as session:
                    # Create plugins - DeezerPlugin doesn't need auth for album lookup
                    # SpotifyPlugin will be None if user not authenticated
                    deezer_plugin = DeezerPlugin()

                    # Try to create SpotifyPlugin from stored session tokens
                    spotify_plugin = None
                    try:
                        spotify_plugin = SpotifyPlugin()
                    except Exception:
                        # No Spotify auth available, Deezer fallback will be used
                        pass

                    service = ArtistService(
                        session=session,
                        spotify_plugin=spotify_plugin,
                        deezer_plugin=deezer_plugin,
                    )

                    stats = await service.sync_artist_discography_complete(
                        artist_id=artist_id,
                        include_tracks=True,
                    )

                    await session.commit()

                    logger.info(
                        f"✅ Background discography sync complete for {artist_name}: "
                        f"albums={stats['albums_added']}/{stats['albums_total']}, "
                        f"tracks={stats['tracks_added']}/{stats['tracks_total']} "
                        f"(source: {stats['source']})"
                    )

            except Exception as e:
                # Log but don't fail - this is a background task
                logger.error(
                    f"❌ Background discography sync failed for {artist_name}: {e}",
                    exc_info=True,
                )

    # =========================================================================
    # MAIN SCAN METHODS
    # =========================================================================

    async def scan_library(
        self,
        incremental: bool | None = None,  # None = auto-detect!
        defer_cleanup: bool = True,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Scan the entire music library using Lidarr folder structure.

        This is the MAIN entry point! Call this from JobQueue handler.

        Hey future me - SMART AUTO-DETECT MODE (Dec 2025)!
        - If incremental=None (default): Auto-detect based on existing data
          - Empty DB → Full scan (process all files)
          - Has tracks → Incremental (only new/modified files)
        - Explicit True/False still works for manual override

        Args:
            incremental: Scan mode:
                        - None (default): Auto-detect (recommended!)
                        - True: Only scan new/modified files
                        - False: Full rescan (process all files)
            defer_cleanup: If True, return cleanup_needed flag (caller queues cleanup job).
                          If False, run cleanup immediately (old behavior).
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with scan statistics including cleanup_needed flag
        """
        start_time, operation_id = start_operation(
            logger,
            "library_scanner.scan_library",
            incremental=incremental,
            defer_cleanup=defer_cleanup,
            music_path=str(self.music_path),
        )
        
        # Auto-detect scan mode if not specified
        if incremental is None:
            track_count = await self._count_tracks()
            incremental = track_count > 0  # Incremental if we have existing tracks
            logger.info(
                f"Auto-detected scan mode: {'incremental' if incremental else 'full'} "
                f"(existing tracks: {track_count})"
            )

        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "total_files": 0,
            "scanned": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "error_files": [],
            "new_artists": 0,
            "new_albums": 0,
            "new_tracks": 0,
            "existing_artists": 0,
            "existing_albums": 0,
            # Cleanup stats (only populated if defer_cleanup=False)
            "removed_tracks": 0,
            "removed_albums": 0,
            "removed_artists": 0,
            # Compilation stats
            "compilations_detected": 0,
            # Deferred cleanup flag (caller should queue LIBRARY_SCAN_CLEANUP job)
            "cleanup_needed": False,
            "cleanup_file_paths": None,  # Serialized for cleanup job payload
            # Auto-discography sync stats (Jan 2025)
            "discography_sync_queued": 0,
        }

        # Hey future me - track newly created artists for AUTO-DISCOGRAPHY SYNC!
        # After scan completes, we queue discography sync for these artists.
        # This ensures LOCAL artists get their FULL discography from providers.
        newly_created_artist_ids: list[tuple[str, str]] = []  # [(artist_id, artist_name), ...]

        try:
            # Validate music path
            if not self.music_path.exists():
                raise FileNotFoundError(f"Music path does not exist: {self.music_path}")

            # Log detailed path info for debugging
            music_root = self.music_path.resolve()
            logger.info(f"Scanning Lidarr-organized library at: {music_root}")
            logger.info(
                f"Scan mode: {'incremental' if incremental else 'full'}, "
                f"cleanup: {'deferred' if defer_cleanup else 'immediate'}"
            )

            # Use LibraryFolderParser for structured discovery
            # Hey future me - this parses the entire Artist→Album→Track hierarchy ONCE!
            # Much faster than parsing each file's path separately.
            parser = LibraryFolderParser(music_root)
            scan_result: LibraryScanResult = parser.scan()

            logger.info(
                f"LibraryFolderParser found: {scan_result.total_artists} artists, "
                f"{scan_result.total_albums} albums, {scan_result.total_tracks} tracks"
            )

            # Collect all file paths for cleanup check
            all_file_paths: set[str] = set()
            for artist in scan_result.artists:
                for album in artist.albums:
                    for track in album.tracks:
                        all_file_paths.add(str(track.path.resolve()))

            stats["total_files"] = len(all_file_paths)

            # For FULL scan: Handle cleanup (immediate or deferred)
            if not incremental:
                if defer_cleanup:
                    # Fast check: are there any tracks to clean up?
                    cleanup_count = await self._count_missing_tracks(all_file_paths)
                    if cleanup_count > 0:
                        stats["cleanup_needed"] = True
                        # Store file paths for cleanup job (as list for JSON serialization)
                        stats["cleanup_file_paths"] = list(all_file_paths)
                        logger.info(
                            f"Cleanup deferred: ~{cleanup_count} tracks to remove "
                            "(will run as separate job)"
                        )
                else:
                    # Immediate cleanup (old behavior, blocks UI longer)
                    cleanup_stats = await self._cleanup_missing_files(all_file_paths)
                    stats["removed_tracks"] = cleanup_stats["removed_tracks"]
                    stats["removed_albums"] = cleanup_stats["removed_albums"]
                    stats["removed_artists"] = cleanup_stats["removed_artists"]

                    # Clear caches after cleanup
                    self._artist_cache.clear()
                    self._album_cache.clear()

            # Pre-load artist/album caches for exact name matching
            await self._load_caches()

            # Process structured data: Artist → Album → Tracks
            # Hey future me - this is the BIG CHANGE! We iterate by structure, not by file.
            # Artist/Album are created ONCE per folder, then tracks are added.
            #
            # LOCK OPTIMIZATION (Dec 2025):
            # Reduced BATCH_SIZE from 250 to 10 to minimize SQLite lock contention!
            # Also commit after EACH ALBUM (natural transaction boundary).
            # Why: SQLite locks entire DB during writes. With 250 tracks per commit,
            # other workers (downloads, enrichment) get "database is locked" errors.
            # With smaller batches + album commits, lock is released frequently.
            BATCH_SIZE = 10  # Small batches to release DB lock frequently
            processed = 0
            total_tracks = scan_result.total_tracks

            for scanned_artist in scan_result.artists:
                # Get or create artist (exact name match, no fuzzy!)
                # Hey future me - we pass musicbrainz_id AND disambiguation from folder!
                # Name is CLEAN (no UUID/disambiguation), perfect for Spotify search.
                # Disambiguation is stored separately for UI display.
                artist_id, is_new_artist = await self._get_or_create_artist_exact(
                    scanned_artist.name,
                    musicbrainz_id=scanned_artist.musicbrainz_id,
                    disambiguation=scanned_artist.disambiguation,
                )
                if is_new_artist:
                    stats["new_artists"] += 1
                    # Hey future me - track for auto-discography sync!
                    # Skip "Various Artists" - they're compilations, not real artists.
                    if not is_various_artists(scanned_artist.name):
                        newly_created_artist_ids.append(
                            (str(artist_id.value), scanned_artist.name)
                        )
                else:
                    stats["existing_artists"] += 1

                # Check if this is a VA artist (for compilation detection)
                is_va_artist = is_various_artists(scanned_artist.name)

                for scanned_album in scanned_artist.albums:
                    # Get or create album (exact name match)
                    album_id, is_new_album = await self._get_or_create_album_exact(
                        title=scanned_album.title,
                        artist_id=artist_id,
                        release_year=scanned_album.year,
                        is_compilation=is_va_artist,
                        album_artist=scanned_artist.name if is_va_artist else None,
                    )
                    if is_new_album:
                        stats["new_albums"] += 1
                        if is_va_artist:
                            stats["compilations_detected"] += 1
                    else:
                        stats["existing_albums"] += 1

                    # Process tracks in this album
                    for scanned_track in scanned_album.tracks:
                        try:
                            # Check if file changed (incremental mode)
                            if incremental:
                                existing = await self._get_track_by_file_path(
                                    scanned_track.path
                                )
                                if existing:
                                    # Update last_scanned_at
                                    existing.last_scanned_at = datetime.now(UTC)
                                    stats["skipped"] += 1
                                    processed += 1
                                    continue

                            # Import track with folder-based metadata
                            result = await self._import_track_from_scan(
                                scanned_track=scanned_track,
                                artist_id=artist_id,
                                album_id=album_id,
                                is_va_album=is_va_artist,
                            )

                            stats["scanned"] += 1
                            if result["imported"]:
                                stats["imported"] += 1
                                stats["new_tracks"] += 1

                            processed += 1

                            # Batch commit
                            if processed % BATCH_SIZE == 0:
                                await self._session.commit()
                                logger.debug(f"Committed batch ({processed} tracks)")

                            # Progress callback
                            if progress_callback and total_tracks > 0:
                                progress = processed / total_tracks * 100
                                await progress_callback(progress, stats)

                        except Exception as e:
                            stats["errors"] += 1
                            stats["error_files"].append(
                                {"path": str(scanned_track.path), "error": str(e)}
                            )
                            logger.warning(
                                f"Error importing {scanned_track.path.name}: {e}",
                                exc_info=False,
                            )
                            processed += 1

                    # LOCK OPTIMIZATION: Commit after EACH album!
                    # This is a natural transaction boundary - all tracks for one album.
                    # Releases SQLite lock so other workers can proceed.
                    await self._session.commit()
                    logger.debug(
                        f"Committed album '{scanned_album.title}' "
                        f"({len(scanned_album.tracks)} tracks)"
                    )

            # Final commit
            await self._session.commit()
            stats["completed_at"] = datetime.now(UTC).isoformat()

            logger.info(
                f"Library scan complete: {stats['imported']} imported, "
                f"{stats['skipped']} skipped, {stats['errors']} errors, "
                f"{stats['new_artists']} new artists, {stats['new_albums']} new albums, "
                f"{stats['compilations_detected']} compilations"
            )

            # ================================================================
            # AUTO-DISCOGRAPHY SYNC for newly created LOCAL artists!
            # Hey future me - this is THE KEY to unified library behavior!
            # When user scans local folder, new artists should get their FULL
            # discography from providers (just like "Add to Library" button).
            # This runs as background tasks so scan returns immediately.
            # ================================================================
            if newly_created_artist_ids:
                logger.info(
                    f"🎵 Queuing auto-discography sync for {len(newly_created_artist_ids)} "
                    "new LOCAL artists..."
                )
                for artist_id_str, artist_name in newly_created_artist_ids:
                    try:
                        # Create background task for discography sync
                        # Uses same method as "Add to Library" button!
                        asyncio.create_task(
                            self._background_discography_sync(
                                artist_id=artist_id_str,
                                artist_name=artist_name,
                            )
                        )
                        stats["discography_sync_queued"] += 1
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed to queue discography sync for {artist_name}: {e}"
                        )

                logger.info(
                    f"✅ Queued {stats['discography_sync_queued']} discography syncs "
                    "(running in background)"
                )
            
            end_operation(
                logger,
                "library_scanner.scan_library",
                start_time,
                operation_id,
                success=True,
                scan_mode="incremental" if incremental else "full",
                total_files=stats["total_files"],
                imported=stats["imported"],
                skipped=stats["skipped"],
                errors=stats["errors"],
                new_artists=stats["new_artists"],
                new_albums=stats["new_albums"],
                new_tracks=stats["new_tracks"],
                compilations_detected=stats["compilations_detected"],
                cleanup_needed=stats.get("cleanup_needed", False),
            )

        except Exception as e:
            logger.error(
                "Library scan failed",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "music_path": str(self.music_path),
                    "incremental": incremental,
                },
            )
            stats["error"] = str(e)
            end_operation(
                logger,
                "library_scanner.scan_library",
                start_time,
                operation_id,
                success=False,
                error=e,
            )

        return stats

    # =========================================================================
    # EXACT NAME MATCHING (Lidarr folder structure)
    # =========================================================================

    async def _get_or_create_artist_exact(
        self,
        name: str,
        musicbrainz_id: str | None = None,
        disambiguation: str | None = None,
    ) -> tuple[ArtistId, bool]:
        """Get existing artist by exact name or create new.

        Hey future me - NO FUZZY MATCHING! Lidarr folder structure guarantees
        artist name is correct. If folder says "The Beatles", that's the name.

        Args:
            name: Artist name from folder structure (clean, without UUID/disambiguation!)
            musicbrainz_id: Optional MusicBrainz UUID from Lidarr folder name
            disambiguation: Optional text disambiguation (e.g., "English rock band")

        Returns:
            Tuple of (artist_id, is_new)
        """
        name_lower = name.lower().strip()

        # Check cache first (exact match)
        if name_lower in self._artist_cache:
            return self._artist_cache[name_lower], False

        # Check database
        stmt = select(ArtistModel).where(func.lower(ArtistModel.name) == name_lower)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            artist_id = ArtistId.from_string(existing.id)
            self._artist_cache[name_lower] = artist_id

            # Hey future me - UPGRADE source to HYBRID if Spotify artist found in local files!
            # If artist was followed on Spotify (source='spotify') and is now found in local
            # file scan, upgrade to source='hybrid' (both Spotify + local files).
            # This is the reverse of FollowedArtistsService upgrading LOCAL → HYBRID!
            if existing.source == "spotify":
                existing.source = "hybrid"
                logger.info(
                    f"Upgraded artist '{name}' from SPOTIFY to HYBRID (local files + Spotify)"
                )

            # Update musicbrainz_id if we have it now and DB doesn't
            # Hey future me - this ensures re-scans populate missing UUIDs!
            if musicbrainz_id and not existing.musicbrainz_id:
                existing.musicbrainz_id = musicbrainz_id
                logger.debug(
                    f"Updated artist '{name}' with MusicBrainz ID: {musicbrainz_id}"
                )

            # Update disambiguation if we have it now and DB doesn't
            # Hey future me - disambiguation helps display "Genesis (English rock band)" in UI
            if disambiguation and not existing.disambiguation:
                existing.disambiguation = disambiguation
                logger.debug(
                    f"Updated artist '{name}' with disambiguation: {disambiguation}"
                )

            return artist_id, False

        # Create new artist from local folder
        # Hey future me - we log new artists at INFO level so you can see what's being imported
        # from which folder. This helps catch folder naming issues (like "Ava MaxDance").
        logger.info(f"📁 New artist from folder: '{name}'")

        artist = Artist(
            id=ArtistId.generate(),
            name=name,  # Keep original casing from folder
            disambiguation=disambiguation,  # Text disambiguation for UI display
            source=ArtistSource.LOCAL,  # Artists from local file scans are LOCAL
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await self.artist_repo.add(artist)

        # Set musicbrainz_id on the model (not in domain entity)
        # Hey future me - this UUID is needed for Lidarr folder naming when moving files!
        if musicbrainz_id:
            stmt = select(ArtistModel).where(ArtistModel.id == str(artist.id.value))
            result = await self._session.execute(stmt)
            artist_model = result.scalar_one()
            artist_model.musicbrainz_id = musicbrainz_id
            logger.debug(
                f"Created artist '{name}' (source=LOCAL) with MusicBrainz ID: {musicbrainz_id}"
            )

        # Add to cache
        self._artist_cache[name_lower] = artist.id
        logger.debug(f"Created new artist: {name} (source=LOCAL)")

        return artist.id, True

    async def _get_or_create_album_exact(
        self,
        title: str,
        artist_id: ArtistId,
        release_year: int | None = None,
        is_compilation: bool = False,
        album_artist: str | None = None,
    ) -> tuple[AlbumId, bool]:
        """Get existing album by exact title+artist or create new.

        Hey future me - NO FUZZY MATCHING! Lidarr folder structure guarantees
        album title is correct. "Thriller (1982)" folder → title="Thriller", year=1982.

        Args:
            title: Album title from folder structure
            artist_id: Parent artist ID
            release_year: Year parsed from folder (if present)
            is_compilation: True if under "Various Artists" folder
            album_artist: Album artist name (for compilations)

        Returns:
            Tuple of (album_id, is_new)
        """
        title_lower = title.lower().strip()
        artist_id_str = str(artist_id.value)

        # For compilations, use album_artist as key instead of track artist
        album_key = album_artist.lower() if album_artist else artist_id_str
        cache_key = f"{title_lower}|{album_key}"

        # Check cache first
        if cache_key in self._album_cache:
            return self._album_cache[cache_key], False

        # Check database (exact match on title + artist_id)
        stmt = select(AlbumModel).where(
            func.lower(AlbumModel.title) == title_lower,
            AlbumModel.artist_id == artist_id_str,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            album_id = AlbumId.from_string(existing.id)
            self._album_cache[cache_key] = album_id
            return album_id, False

        # Determine secondary_types
        secondary_types: list[str] = []
        if is_compilation:
            secondary_types.append(SecondaryAlbumType.COMPILATION.value)

        # Create new album
        album = Album(
            id=AlbumId.generate(),
            title=title,  # Keep original casing from folder
            artist_id=artist_id,
            release_year=release_year,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await self.album_repo.add(album)

        # Update model with extra fields (album_artist, secondary_types)
        stmt = select(AlbumModel).where(AlbumModel.id == str(album.id.value))
        result = await self._session.execute(stmt)
        album_model = result.scalar_one()
        album_model.album_artist = album_artist
        album_model.secondary_types = secondary_types

        # Add to cache
        self._album_cache[cache_key] = album.id
        logger.debug(
            f"Created new album: {title} (year={release_year}, compilation={is_compilation})"
        )

        return album.id, True

    async def _find_or_create_artist(self, name: str) -> tuple[ArtistId, bool, bool]:
        """Find or create artist with fuzzy matching.

        Hey future me - this is a wrapper around _get_or_create_artist_exact
        that provides the 3-tuple return value expected by callers.
        The third value (is_matched) indicates if fuzzy matching was used,
        but we're using exact matching for now.

        Args:
            name: Artist name

        Returns:
            Tuple of (artist_id, is_new, is_matched)
        """
        artist_id, is_new = await self._get_or_create_artist_exact(name)
        # is_matched=True means exact match was found (not fuzzy)
        is_matched = not is_new
        return artist_id, is_new, is_matched

    async def _find_or_create_album(
        self,
        title: str,
        artist_id: ArtistId,
        release_year: int | None = None,
        album_artist: str | None = None,
        is_compilation: bool = False,
    ) -> tuple[AlbumId, bool, bool]:
        """Find or create album with fuzzy matching.

        Hey future me - this is a wrapper around _get_or_create_album_exact
        that provides the 3-tuple return value expected by callers.
        The third value (is_matched) indicates if fuzzy matching was used,
        but we're using exact matching for now.

        Args:
            title: Album title
            artist_id: Artist ID
            release_year: Optional release year
            album_artist: Album artist name (for compilations)
            is_compilation: True if compilation album

        Returns:
            Tuple of (album_id, is_new, is_matched)
        """
        album_id, is_new = await self._get_or_create_album_exact(
            title,
            artist_id,
            release_year=release_year,
            is_compilation=is_compilation,
            album_artist=album_artist,
        )
        # is_matched=True means exact match was found (not fuzzy)
        is_matched = not is_new
        return album_id, is_new, is_matched

    async def _import_track_from_scan(
        self,
        scanned_track: ScannedTrack,
        artist_id: ArtistId,
        album_id: AlbumId,
        is_va_album: bool = False,
    ) -> dict[str, Any]:
        """Import a track from LibraryFolderParser scan result.

        Hey future me - this uses folder-based metadata (title, track_number, disc_number)
        and calls Mutagen for audio info (duration, bitrate, genre) IN THREAD POOL!
        This prevents blocking the event loop during I/O-heavy metadata extraction.

        Args:
            scanned_track: Track info from folder parser
            artist_id: Parent artist ID (from folder)
            album_id: Parent album ID (from folder)
            is_va_album: True if this is a VA compilation

        Returns:
            Dict with import result
        """
        result = {"imported": False, "new_track": False}

        file_path = scanned_track.path

        # Hey future me - ALWAYS check if track exists FIRST to prevent duplicates!
        # This is critical for full scan (incremental=False) which doesn't pre-filter.
        # Without this check, full scan creates duplicate tracks in albums.
        existing = await self._get_track_by_file_path(file_path)
        if existing:
            # Update last_scanned_at and return early (no duplicate!)
            existing.last_scanned_at = datetime.now(UTC)
            result["imported"] = True
            return result

        # For VA tracks, the actual track artist may be in the filename
        # (e.g., "01 - Michael Jackson - Billie Jean.flac")
        track_artist_id = artist_id
        if is_va_album and scanned_track.artist:
            # Get or create the actual track artist
            track_artist_id, _ = await self._get_or_create_artist_exact(
                scanned_track.artist
            )

        # Extract audio info and compute hash IN THREAD POOL to avoid blocking event loop
        # Hey future me - this is the BIG PERFORMANCE WIN! Mutagen + SHA256 are CPU-bound,
        # running them in executor keeps the event loop responsive for UI requests.
        loop = asyncio.get_running_loop()
        audio_info, file_hash, file_size = await loop.run_in_executor(
            self._executor,
            self._extract_audio_and_hash_sync,
            file_path,
        )

        # Create track entity
        track = Track(
            id=TrackId.generate(),
            title=scanned_track.title,  # From folder parsing!
            artist_id=track_artist_id,
            album_id=album_id,
            duration_ms=audio_info.get("duration_ms", 0),
            track_number=scanned_track.track_number,  # From folder parsing!
            disc_number=scanned_track.disc_number,  # From folder parsing!
            file_path=FilePath.from_string(str(file_path.resolve())),
            genres=[audio_info["genre"]] if audio_info.get("genre") else [],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Create track model with file info
        primary_genre = track.genres[0] if track.genres else None
        model = TrackModel(
            id=str(track.id.value),
            title=track.title,
            artist_id=str(track.artist_id.value),
            album_id=str(track.album_id.value) if track.album_id else None,
            duration_ms=track.duration_ms,
            track_number=track.track_number,
            disc_number=track.disc_number,
            file_path=str(track.file_path) if track.file_path else None,
            genre=primary_genre,
            file_size=file_size,
            file_hash=file_hash
            if file_hash
            else None,  # Empty = computed later by nightly job
            file_hash_algorithm="sha256" if file_hash else None,
            audio_bitrate=audio_info.get("bitrate"),
            audio_format=audio_info.get("format"),
            audio_sample_rate=audio_info.get("sample_rate"),
            last_scanned_at=datetime.now(UTC),
            is_broken=False,
            created_at=track.created_at,
            updated_at=track.updated_at,
        )
        self._session.add(model)

        result["imported"] = True
        result["new_track"] = True
        return result

    async def _filter_changed_files(self, files: list[Path]) -> list[Path]:
        """Filter to only new or modified files (incremental scan).

        Compares file mtime with last_scanned_at in database.

        Args:
            files: List of all audio file paths

        Returns:
            List of files that are new or modified since last scan
        """
        # Get all known file paths with their last_scanned_at
        stmt = select(TrackModel.file_path, TrackModel.last_scanned_at).where(
            TrackModel.file_path.isnot(None)
        )
        result = await self._session.execute(stmt)
        known_files = {row[0]: row[1] for row in result.all()}

        changed_files = []
        for file_path in files:
            # Hey future me - ALWAYS resolve to absolute path for DB comparison!
            # DB stores absolute paths, so ./music/x.mp3 won't match /music/x.mp3
            path_str = str(file_path.resolve())

            # New file (not in DB)
            if path_str not in known_files:
                changed_files.append(file_path)
                continue

            # Check if modified since last scan
            last_scanned = known_files[path_str]
            if last_scanned:
                # Handle timezone-naive datetimes from SQLite
                if last_scanned.tzinfo is None:
                    last_scanned = last_scanned.replace(tzinfo=UTC)
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
                if file_mtime > last_scanned:
                    changed_files.append(file_path)

        return changed_files

    async def _count_tracks(self) -> int:
        """Count total tracks in database.

        Hey future me - used for auto-detect scan mode!
        If we have tracks, use incremental. If empty, use full scan.
        """
        stmt = select(func.count(TrackModel.id))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def _get_track_by_file_path(self, file_path: Path) -> TrackModel | None:
        """Get track by file path.

        Hey future me - use resolved path for consistent DB lookup!
        """
        stmt = select(TrackModel).where(
            TrackModel.file_path == str(file_path.resolve())
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _compute_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Compute SHA256 hash of file for deduplication."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _extract_audio_and_hash_sync(
        self, file_path: Path
    ) -> tuple[dict[str, Any], str, int]:
        """Extract audio info in ThreadPool (non-blocking).

        Hey future me - this is called via run_in_executor() to avoid blocking
        the event loop! Combines Mutagen extraction + file size into one call.

        PERFORMANCE NOTE (Dec 2025): SHA256 hash is NEVER computed during scan!
        Hash computation reads the entire file (~55% of scan time!). Instead,
        duplicate detection runs as a separate nightly DUPLICATE_SCAN job that
        computes hashes for tracks without file_hash. This keeps scans fast!

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (audio_info dict, file_hash (always empty), file_size)
        """
        # Extract audio info (always needed for duration, bitrate, genre)
        audio_info = self._extract_audio_info(file_path)

        # SHA256 hash is NEVER computed during scan - runs in nightly DUPLICATE_SCAN job!
        # Hey future me - this was the BIG PERFORMANCE WIN! Scans are ~2x faster
        # because we don't read entire files for SHA256. The nightly job handles it.
        file_hash = ""
        file_size = 0
        try:
            file_size = file_path.stat().st_size
        except Exception as e:
            logger.warning(f"Could not get file size for {file_path}: {e}")

        return audio_info, file_hash, file_size

    def _extract_audio_info(self, file_path: Path) -> dict[str, Any]:
        """Extract ONLY audio technical info from file (NOT artist/album/title!).

        Hey future me - this is the NEW simplified extraction for Lidarr-based scanning!
        We ONLY extract:
        - duration_ms (from audio stream)
        - bitrate (from audio stream)
        - sample_rate (from audio stream)
        - format (from file extension)
        - genre (from ID3 tag - this is the ONLY tag we read!)

        Artist, album, title come from FOLDER STRUCTURE, not from tags!

        Args:
            file_path: Path to audio file

        Returns:
            Dict with audio info (duration_ms, bitrate, sample_rate, format, genre)
        """
        audio_info: dict[str, Any] = {
            "format": file_path.suffix.lstrip(".").lower(),
            "duration_ms": 0,
        }

        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return audio_info

            # Duration from audio stream
            if hasattr(audio.info, "length") and audio.info.length:
                audio_info["duration_ms"] = int(audio.info.length * 1000)

            # Bitrate from audio stream
            if hasattr(audio.info, "bitrate") and audio.info.bitrate:
                audio_info["bitrate"] = audio.info.bitrate

            # Sample rate from audio stream
            if hasattr(audio.info, "sample_rate") and audio.info.sample_rate:
                audio_info["sample_rate"] = audio.info.sample_rate

            # Genre is the ONLY tag we extract (not in folder structure)
            if hasattr(audio, "tags") and audio.tags:
                genre = self._extract_genre_tag(audio.tags)
                if genre:
                    audio_info["genre"] = genre

            return audio_info

        except Exception as e:
            # Hey future me - some exceptions (especially from FLAC parsing) have empty str(e)!
            # We log exception TYPE + message to actually debug these issues.
            exc_type = type(e).__name__
            exc_msg = str(e) if str(e) else "(no message)"
            logger.warning(
                f"Error extracting audio info from {file_path.name}: "
                f"[{exc_type}] {exc_msg}"
            )
            return audio_info

    def _extract_genre_tag(self, tags: Any) -> str | None:
        """Extract genre from audio tags.

        Hey future me - genre is the ONLY tag we need from ID3/Vorbis/MP4!
        Everything else (artist, album, title) comes from folder structure.

        Args:
            tags: Audio tags from mutagen

        Returns:
            Genre string or None
        """
        # Genre tag mappings for different formats
        genre_tags = ["TCON", "genre", "©gen"]

        for tag_key in genre_tags:
            if tag_key in tags:
                value = tags[tag_key]
                if isinstance(value, list) and value:
                    value = value[0]
                if hasattr(value, "text"):
                    value = (
                        value.text[0] if isinstance(value.text, list) else value.text
                    )
                if value:
                    return str(value)
        return None

    # =========================================================================
    # CACHE LOADING (for exact name matching)
    # =========================================================================

    async def _load_caches(self) -> None:
        """Pre-load artist and album names for exact matching.

        Hey future me - NO FUZZY MATCHING anymore! Just lowercase exact match.
        Lidarr folder structure guarantees correct names.
        """
        # Load all artists (key = lowercase name)
        artist_stmt = select(ArtistModel.id, ArtistModel.name)
        result = await self._session.execute(artist_stmt)
        for row in result.all():
            artist_id = ArtistId.from_string(row[0])
            name_lower = row[1].lower().strip()
            self._artist_cache[name_lower] = artist_id

        # Load all albums (key = "title_lower|artist_key")
        album_stmt = select(
            AlbumModel.id,
            AlbumModel.title,
            AlbumModel.artist_id,
            AlbumModel.album_artist,
        )
        result = await self._session.execute(album_stmt)
        for row in result.all():
            album_id = AlbumId.from_string(row[0])
            # Use album_artist if present (for compilations), otherwise artist_id
            album_key = row[3].lower() if row[3] else row[2]
            cache_key = f"{row[1].lower()}|{album_key}"
            self._album_cache[cache_key] = album_id

        logger.debug(
            f"Loaded caches: {len(self._artist_cache)} artists, "
            f"{len(self._album_cache)} albums"
        )

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _detect_album_artist_from_path(self, file_path: Path) -> str | None:
        """Detect album_artist from folder structure (Lidarr/Plex/Jellyfin-style).

        Hey future me - this NOW walks UP the ENTIRE directory tree!
        Handles NESTED structures like CD1, CD2, Disc1, etc.

        Supported structures:
        - /music/Various Artists/Album/track.mp3 (standard Lidarr)
        - /music/Various Artists/Album/CD1/track.mp3 (multi-CD)
        - /music/Various Artists/Album/CD1/CD2/track.mp3 (deep nesting)
        - /music/VA/Album/Disc 1/track.mp3 (abbreviated + disc folders)
        - /music/Compilations/Album/track.mp3 (alternative naming)

        Args:
            file_path: Path to the audio file

        Returns:
            Detected album_artist (e.g., "Various Artists") or None
        """
        # Walk UP the directory tree from the track location
        # Stop at music_path root to avoid going outside the library
        current = file_path.parent  # Start from track's directory
        music_root = self.music_path.resolve()

        while current != music_root and current != current.parent:
            folder_name = current.name

            if folder_name and is_various_artists(folder_name):
                # Extract clean name (remove Lidarr suffixes like "(add compilations...)")
                clean_name = folder_name
                if "(" in clean_name:
                    clean_name = clean_name[: clean_name.index("(")].strip()

                logger.debug(
                    f"Detected VA folder '{folder_name}' for track: {file_path.name}"
                )
                return clean_name if clean_name else "Various Artists"

            # Move up one level
            current = current.parent

        return None

    def _extract_metadata_from_path(
        self, file_path: Path
    ) -> dict[str, str | int | None]:
        """Extract metadata from Lidarr-style folder/file structure.

        Hey future me - this is the FALLBACK when ID3 tags are missing!
        Uses our new folder parsing module to extract artist, album, track info
        from the folder structure: /Artist/Album (Year)/NN - Title.ext

        Args:
            file_path: Path to the audio file

        Returns:
            Dict with extracted metadata (artist, album, album_year, track_number, title)
        """

        metadata: dict[str, str | int | None] = {}

        # Parse track filename
        parsed_track = parse_track_filename(file_path.name)
        if parsed_track.title:
            metadata["title_from_folder"] = parsed_track.title
        if parsed_track.track_number > 0:
            metadata["track_number_from_folder"] = parsed_track.track_number
        # Hey future me - disc_number > 0 (not > 1!) because 0102 format has disc=1!
        # Disc 1 is valid and should be stored from DDTT format like "0102 - Track.flac"
        if parsed_track.disc_number > 0:
            metadata["disc_number_from_folder"] = parsed_track.disc_number
        if parsed_track.artist:
            # VA track with artist in filename
            metadata["track_artist_from_folder"] = parsed_track.artist

        # Navigate up to find album and artist folders
        # Expected structure: /music/Artist/Album (Year)/[Disc N/]Track.ext
        current = file_path.parent
        music_root = self.music_path.resolve()

        # Check if we're in a disc subfolder
        is_disc, disc_num = is_disc_folder(current.name)
        if is_disc and disc_num is not None:
            metadata["disc_number_from_folder"] = disc_num
            current = current.parent  # Move up past disc folder

        # Current should be album folder
        if current != music_root and current.name:
            parsed_album = parse_album_folder(current.name)
            metadata["album_from_folder"] = parsed_album.title
            if parsed_album.year:
                metadata["year_from_folder"] = parsed_album.year
            current = current.parent

        # Current should be artist folder
        if current != music_root and current.name:
            from soulspot.domain.value_objects.folder_parsing import parse_artist_folder

            parsed_artist = parse_artist_folder(current.name)
            metadata["artist_from_folder"] = parsed_artist.name
            # Hey future me - Lidarr stores UUID in folder name, store it for later enrichment!
            if parsed_artist.uuid:
                metadata["musicbrainz_id_from_folder"] = parsed_artist.uuid

        return metadata

    async def _count_missing_tracks(self, existing_file_paths: set[str]) -> int:
        """Fast check: count tracks whose files no longer exist.

        Hey future me - this is a FAST pre-check for deferred cleanup!
        Instead of loading all tracks, we just count how many would be removed.
        Used to decide if cleanup job is needed (cleanup_needed flag).

        Args:
            existing_file_paths: Set of file paths that currently exist on disk

        Returns:
            Approximate count of tracks to remove (0 = no cleanup needed)
        """
        # Get count of tracks with file_path
        total_stmt = select(func.count(TrackModel.id)).where(
            TrackModel.file_path.isnot(None)
        )
        total_result = await self._session.execute(total_stmt)
        total_in_db = total_result.scalar() or 0

        # If we have more files on disk than in DB, no cleanup needed
        # (new files will be added, not removed)
        if len(existing_file_paths) >= total_in_db:
            return 0

        # Rough estimate: difference between DB count and file count
        # This is faster than loading all paths and comparing
        return total_in_db - len(existing_file_paths)

    async def _cleanup_missing_files(
        self, existing_file_paths: set[str]
    ) -> dict[str, int]:
        """Remove tracks from DB whose files no longer exist on disk.

        Hey future me - OPTIMIZED VERSION (Dec 2025)!
        - Processes tracks in chunks to avoid memory spikes
        - Uses yielding pattern for large libraries (100k+ tracks)
        - Orphan cleanup uses efficient NOT EXISTS subqueries

        Called during full scan (incremental=False) or by LIBRARY_SCAN_CLEANUP job.

        Args:
            existing_file_paths: Set of file paths that currently exist on disk

        Returns:
            Dict with cleanup statistics
        """
        stats = {
            "removed_tracks": 0,
            "removed_albums": 0,
            "removed_artists": 0,
        }

        # Step 1: Find and remove tracks with missing files (chunked processing)
        logger.info("Checking for tracks with missing files...")

        CHUNK_SIZE = 5000  # Process in chunks to limit memory usage
        offset = 0
        tracks_to_remove: list[str] = []

        while True:
            # Fetch a chunk of track file paths
            stmt = (
                select(TrackModel.id, TrackModel.file_path)
                .where(TrackModel.file_path.isnot(None))
                .offset(offset)
                .limit(CHUNK_SIZE)
            )
            result = await self._session.execute(stmt)
            chunk = result.all()

            if not chunk:
                break  # No more tracks

            # Check which tracks in this chunk have missing files
            for track_id, file_path in chunk:
                if file_path not in existing_file_paths:
                    tracks_to_remove.append(track_id)

            offset += CHUNK_SIZE

            # Yield control to event loop periodically (keeps UI responsive)
            if offset % (CHUNK_SIZE * 5) == 0:
                await asyncio.sleep(0)

        if tracks_to_remove:
            logger.info(
                f"Removing {len(tracks_to_remove)} tracks with missing files..."
            )

            # Delete tracks in batches with COMMITS after each batch
            # Hey future me - LOCK OPTIMIZATION! Commit after each batch to release lock.
            # This allows other workers to proceed during large cleanup operations.
            for i in range(0, len(tracks_to_remove), 500):
                batch = tracks_to_remove[i : i + 500]
                delete_stmt = delete(TrackModel).where(TrackModel.id.in_(batch))
                await self._session.execute(delete_stmt)
                await self._session.commit()  # Commit each batch to release lock
                logger.debug(f"Deleted batch {i // 500 + 1} ({len(batch)} tracks)")

                # Yield to event loop every few batches
                if i % 2000 == 0 and i > 0:
                    await asyncio.sleep(0)

            stats["removed_tracks"] = len(tracks_to_remove)
            logger.info(f"Removed {len(tracks_to_remove)} tracks")
        else:
            logger.info("No tracks with missing files found")

        # Step 2: Remove orphaned albums using efficient NOT EXISTS subquery
        logger.info("Checking for orphaned albums...")

        # Count orphaned albums first (for logging)
        orphan_count_stmt = select(func.count(AlbumModel.id)).where(
            ~AlbumModel.id.in_(
                select(TrackModel.album_id)
                .where(TrackModel.album_id.isnot(None))
                .distinct()
            )
        )
        orphan_count_result = await self._session.execute(orphan_count_stmt)
        orphan_album_count = orphan_count_result.scalar() or 0

        if orphan_album_count > 0:
            logger.info(f"Removing {orphan_album_count} orphaned albums...")

            # Delete orphaned albums (set-based, no Python loops!)
            delete_albums_stmt = delete(AlbumModel).where(
                ~AlbumModel.id.in_(
                    select(TrackModel.album_id)
                    .where(TrackModel.album_id.isnot(None))
                    .distinct()
                )
            )
            await self._session.execute(delete_albums_stmt)
            await self._session.commit()  # Commit after album cleanup to release lock
            stats["removed_albums"] = orphan_album_count
            logger.info(f"Removed {orphan_album_count} orphaned albums")
        else:
            logger.info("No orphaned albums found")

        # Step 3: Remove orphaned artists (no tracks AND no albums)
        logger.info("Checking for orphaned artists...")

        # Artists that have neither tracks nor albums (using NOT EXISTS)
        orphan_count_stmt = (
            select(func.count(ArtistModel.id))
            .where(~ArtistModel.id.in_(select(TrackModel.artist_id).distinct()))
            .where(
                ~ArtistModel.id.in_(
                    select(AlbumModel.artist_id)
                    .where(AlbumModel.artist_id.isnot(None))
                    .distinct()
                )
            )
        )
        orphan_count_result = await self._session.execute(orphan_count_stmt)
        orphan_artist_count = orphan_count_result.scalar() or 0

        if orphan_artist_count > 0:
            logger.info(f"Removing {orphan_artist_count} orphaned artists...")

            # Delete orphaned artists (set-based)
            delete_artists_stmt = (
                delete(ArtistModel)
                .where(~ArtistModel.id.in_(select(TrackModel.artist_id).distinct()))
                .where(
                    ~ArtistModel.id.in_(
                        select(AlbumModel.artist_id)
                        .where(AlbumModel.artist_id.isnot(None))
                        .distinct()
                    )
                )
            )
            await self._session.execute(delete_artists_stmt)
            await self._session.commit()  # Commit after artist cleanup to release lock
            stats["removed_artists"] = orphan_artist_count
            logger.info(f"Removed {orphan_artist_count} orphaned artists")
        else:
            logger.info("No orphaned artists found")

        # Note: No final commit needed - each operation commits immediately
        # (LOCK OPTIMIZATION: shorter transactions, fewer lock conflicts)

        logger.info(
            f"Cleanup complete: {stats['removed_tracks']} tracks, "
            f"{stats['removed_albums']} albums, {stats['removed_artists']} artists removed"
        )

        return stats

    async def _analyze_album_diversity(self) -> dict[str, int]:
        """Post-scan analysis: Detect compilations via track artist diversity.

        Hey future me - this is the SPOTIFY/LIDARR/PLEX logic!
        If an album has >4 unique track artists AND no album_artist set,
        it's automatically a compilation.

        This runs AFTER all tracks are imported, because we need ALL tracks
        to calculate diversity properly.

        Returns:
            Dict with statistics about detected compilations
        """
        from soulspot.domain.value_objects.album_types import (
            calculate_track_diversity,
        )

        stats = {"compilations_detected": 0, "albums_analyzed": 0}

        # Find albums that:
        # 1. Have local files (file_path is not null on tracks)
        # 2. Don't have album_artist set (no VA pattern detected from tags/folders)
        # 3. Don't already have "compilation" in secondary_types
        logger.info("Analyzing album diversity for compilation detection...")

        # Get all albums with their track artists
        albums_stmt = select(
            AlbumModel.id,
            AlbumModel.title,
            AlbumModel.album_artist,
            AlbumModel.secondary_types,
        )
        albums_result = await self._session.execute(albums_stmt)
        albums = albums_result.all()

        for album_id, album_title, album_artist, secondary_types in albums:
            # Skip albums that already have album_artist or are already compilations
            if album_artist and is_various_artists(album_artist):
                continue
            if secondary_types and "compilation" in secondary_types:
                continue

            # Get all track artists for this album
            tracks_stmt = (
                select(ArtistModel.name)
                .join(TrackModel, ArtistModel.id == TrackModel.artist_id)
                .where(TrackModel.album_id == album_id)
                .where(TrackModel.file_path.isnot(None))  # Only local files
            )
            tracks_result = await self._session.execute(tracks_stmt)
            track_artists = [row[0] for row in tracks_result.all()]

            if len(track_artists) < 3:
                # Not enough tracks to analyze
                continue

            stats["albums_analyzed"] += 1

            # Calculate diversity
            diversity_ratio, details = calculate_track_diversity(track_artists)
            unique_artists = details.get("unique_artists", 0)

            # SPOTIFY LOGIC: >4 unique artists = compilation
            # Also check diversity ratio (>75% unique = compilation)
            if unique_artists > 4 or diversity_ratio >= 0.75:
                # Update album to be a compilation
                current_types = secondary_types or []
                if "compilation" not in current_types:
                    current_types.append("compilation")

                # Update the album model
                update_stmt = select(AlbumModel).where(AlbumModel.id == album_id)
                update_result = await self._session.execute(update_stmt)
                album_model = update_result.scalar_one()
                album_model.secondary_types = current_types
                album_model.album_artist = "Various Artists"

                stats["compilations_detected"] += 1
                logger.info(
                    f"Detected compilation via diversity: '{album_title}' "
                    f"({unique_artists} unique artists, {diversity_ratio:.0%} diversity)"
                )

        logger.info(
            f"Diversity analysis complete: {stats['albums_analyzed']} albums analyzed, "
            f"{stats['compilations_detected']} compilations detected"
        )
        return stats

    async def get_scan_summary(self) -> dict[str, Any]:
        """Get summary of current library state."""
        artist_count = await self.artist_repo.count_all()
        album_count_stmt = select(func.count(AlbumModel.id))
        album_result = await self._session.execute(album_count_stmt)
        album_count = album_result.scalar() or 0

        track_count_stmt = select(func.count(TrackModel.id))
        track_result = await self._session.execute(track_count_stmt)
        track_count = track_result.scalar() or 0

        # Count files with file_path
        local_count_stmt = select(func.count(TrackModel.id)).where(
            TrackModel.file_path.isnot(None)
        )
        local_result = await self._session.execute(local_count_stmt)
        local_count = local_result.scalar() or 0

        return {
            "total_artists": artist_count,
            "total_albums": album_count,
            "total_tracks": track_count,
            "local_files": local_count,
            "music_path": str(self.music_path),
        }
