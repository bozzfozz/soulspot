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
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile  # type: ignore[attr-defined]
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.config import Settings
from soulspot.domain.entities import Album, Artist, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, FilePath, TrackId
from soulspot.domain.value_objects.album_types import (
    SecondaryAlbumType,
    detect_compilation,
    is_various_artists,
)
from soulspot.domain.value_objects.folder_parsing import (
    AUDIO_EXTENSIONS,
    LibraryFolderParser,
    LibraryScanResult,
    ScannedAlbum,
    ScannedArtist,
    ScannedTrack,
    is_disc_folder,
    parse_album_folder,
    parse_track_filename,
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
        self.session = session
        self.settings = settings
        self.artist_repo = ArtistRepository(session)
        self.album_repo = AlbumRepository(session)
        self.track_repo = TrackRepository(session)
        self.music_path = settings.storage.music_path

        # Cache for exact name matching (avoid repeated DB queries)
        # Key: lowercase name, Value: entity ID
        self._artist_cache: dict[str, ArtistId] = {}
        self._album_cache: dict[str, AlbumId] = {}

        # Thread pool for CPU-intensive work (metadata extraction, hashing)
        # Hey future me - this runs metadata parsing and SHA256 in parallel threads
        # so the event loop stays responsive. DB work stays async/serial.
        self._executor = ThreadPoolExecutor(max_workers=min(8, max(2, os.cpu_count() or 4)))

    # =========================================================================
    # MAIN SCAN METHODS
    # =========================================================================

    async def scan_library(
        self,
        incremental: bool = True,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Scan the entire music library using Lidarr folder structure.

        This is the MAIN entry point! Call this from JobQueue handler.

        Hey future me - this now uses LibraryFolderParser for STRUCTURED scanning!
        Artist/Album/Track metadata comes from folder structure, not ID3 tags.
        Mutagen is only used for audio info (duration, bitrate, genre).

        Full Scan (incremental=False) does THREE things:
        1. Scans ALL files (not just changed ones)
        2. REMOVES tracks from DB whose files no longer exist
        3. CLEANS UP orphaned albums and artists

        Args:
            incremental: If True, only scan new/modified files.
                        If False, full rescan + cleanup of missing files!
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with scan statistics
        """
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
            # Cleanup stats (full scan only)
            "removed_tracks": 0,
            "removed_albums": 0,
            "removed_artists": 0,
            # Compilation stats
            "compilations_detected": 0,
        }

        try:
            # Validate music path
            if not self.music_path.exists():
                raise FileNotFoundError(f"Music path does not exist: {self.music_path}")

            # Log detailed path info for debugging
            music_root = self.music_path.resolve()
            logger.info(f"Scanning Lidarr-organized library at: {music_root}")
            logger.info(f"Scan mode: {'incremental' if incremental else 'FULL (with cleanup)'}")

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

            # For FULL scan: Remove tracks whose files no longer exist
            if not incremental:
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
            BATCH_SIZE = 100
            processed = 0
            total_tracks = scan_result.total_tracks

            for scanned_artist in scan_result.artists:
                # Get or create artist (exact name match, no fuzzy!)
                artist_id, is_new_artist = await self._get_or_create_artist_exact(
                    scanned_artist.name
                )
                if is_new_artist:
                    stats["new_artists"] += 1
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
                                existing = await self._get_track_by_file_path(scanned_track.path)
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
                                await self.session.commit()
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

            # Final commit
            await self.session.commit()
            stats["completed_at"] = datetime.now(UTC).isoformat()

            logger.info(
                f"Library scan complete: {stats['imported']} imported, "
                f"{stats['skipped']} skipped, {stats['errors']} errors, "
                f"{stats['new_artists']} new artists, {stats['new_albums']} new albums, "
                f"{stats['compilations_detected']} compilations"
            )

        except Exception as e:
            logger.error(f"Library scan failed: {e}", exc_info=True)
            stats["error"] = str(e)

        return stats

    def _discover_audio_files(self, directory: Path) -> list[Path]:
        """Recursively discover all audio files in directory.

        NOTE: This method is kept for backward compatibility but scan_library()
        now uses LibraryFolderParser which provides structured Artist→Album→Track data.

        Args:
            directory: Root directory to scan

        Returns:
            List of audio file paths
        """
        from collections import Counter

        audio_files: list[Path] = []
        skipped_dirs: list[str] = []
        all_extensions: Counter[str] = Counter()
        total_files_seen = 0

        for root, _dirs, files in os.walk(directory, followlinks=True):
            try:
                for filename in files:
                    total_files_seen += 1
                    ext = Path(filename).suffix.lower()
                    all_extensions[ext] += 1
                    if ext in AUDIO_EXTENSIONS:
                        audio_files.append(Path(root) / filename)
            except PermissionError as e:
                skipped_dirs.append(root)
                logger.warning(f"Permission denied: {root} - {e}")

        logger.debug(f"Total files seen: {total_files_seen}, audio files: {len(audio_files)}")
        return audio_files

    # =========================================================================
    # EXACT NAME MATCHING (Lidarr folder structure)
    # =========================================================================

    async def _get_or_create_artist_exact(self, name: str) -> tuple[ArtistId, bool]:
        """Get existing artist by exact name or create new.

        Hey future me - NO FUZZY MATCHING! Lidarr folder structure guarantees
        artist name is correct. If folder says "The Beatles", that's the name.

        Args:
            name: Artist name from folder structure

        Returns:
            Tuple of (artist_id, is_new)
        """
        name_lower = name.lower().strip()

        # Check cache first (exact match)
        if name_lower in self._artist_cache:
            return self._artist_cache[name_lower], False

        # Check database
        stmt = select(ArtistModel).where(func.lower(ArtistModel.name) == name_lower)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            artist_id = ArtistId.from_string(existing.id)
            self._artist_cache[name_lower] = artist_id
            return artist_id, False

        # Create new artist
        artist = Artist(
            id=ArtistId.generate(),
            name=name,  # Keep original casing from folder
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await self.artist_repo.add(artist)

        # Add to cache
        self._artist_cache[name_lower] = artist.id
        logger.debug(f"Created new artist: {name}")

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
        result = await self.session.execute(stmt)
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
        result = await self.session.execute(stmt)
        album_model = result.scalar_one()
        album_model.album_artist = album_artist
        album_model.secondary_types = secondary_types

        # Add to cache
        self._album_cache[cache_key] = album.id
        logger.debug(f"Created new album: {title} (year={release_year}, compilation={is_compilation})")

        return album.id, True

    async def _import_track_from_scan(
        self,
        scanned_track: ScannedTrack,
        artist_id: ArtistId,
        album_id: AlbumId,
        is_va_album: bool = False,
    ) -> dict[str, Any]:
        """Import a track from LibraryFolderParser scan result.

        Hey future me - this uses folder-based metadata (title, track_number, disc_number)
        and only calls Mutagen for audio info (duration, bitrate, genre).

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

        # For VA tracks, the actual track artist may be in the filename
        # (e.g., "01 - Michael Jackson - Billie Jean.flac")
        track_artist_id = artist_id
        if is_va_album and scanned_track.artist:
            # Get or create the actual track artist
            track_artist_id, _ = await self._get_or_create_artist_exact(scanned_track.artist)

        # Extract audio info only (duration, bitrate, sample_rate, genre)
        # NOT artist/album/title - those come from folder structure!
        audio_info = self._extract_audio_info(file_path)

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

        # Compute file hash and size
        file_hash = ""
        file_size = 0
        try:
            file_hash = self._compute_file_hash(file_path)
            file_size = file_path.stat().st_size
        except Exception as e:
            logger.warning(f"Could not compute hash/size for {file_path}: {e}")

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
            file_hash=file_hash,
            file_hash_algorithm="sha256",
            audio_bitrate=audio_info.get("bitrate"),
            audio_format=audio_info.get("format"),
            audio_sample_rate=audio_info.get("sample_rate"),
            last_scanned_at=datetime.now(UTC),
            is_broken=False,
            created_at=track.created_at,
            updated_at=track.updated_at,
        )
        self.session.add(model)

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
        result = await self.session.execute(stmt)
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

    # =========================================================================
    # FILE IMPORT (LEGACY - kept for backward compatibility)
    # =========================================================================
    # Hey future me - these methods are DEPRECATED since the refactoring to
    # folder-structure-first scanning. The new primary path uses:
    #   scan_library() -> LibraryFolderParser -> _import_track_from_scan()
    # These old methods used ID3 tags as primary source which caused:
    #   - 109 artists instead of 13 (fuzzy matching failures)
    #   - Slow scans (full tag extraction per file)
    # Keep them for now in case we need fallback, but plan to remove in v4.0.
    # =========================================================================

    def _prep_file_sync(self, file_path: Path) -> dict[str, Any]:
        """DEPRECATED: Synchronously prepare file metadata and hash.

        .. deprecated::
            Use _import_track_from_scan() with LibraryFolderParser instead.
            This method extracted full ID3 tags which was slow and unreliable.

        Hey future me - this runs in a ThreadPoolExecutor so CPU-intensive work
        doesn't block the async event loop. Only metadata extraction and hashing!

        Args:
            file_path: Path to audio file

        Returns:
            Dict with precomputed metadata and hash
        """
        try:
            metadata = self._extract_metadata(file_path)
        except Exception as e:
            logger.warning(f"Metadata extraction failed for {file_path}: {e}")
            metadata = {
                "format": file_path.suffix.lstrip(".").lower(),
                "duration_ms": 0,
            }

        try:
            file_hash = self._compute_file_hash(file_path)
        except Exception as e:
            logger.warning(f"Hash computation failed for {file_path}: {e}")
            file_hash = ""

        file_size = 0
        with contextlib.suppress(OSError):
            file_size = file_path.stat().st_size

        return {
            "metadata": metadata,
            "hash": file_hash,
            "size": file_size,
        }

    async def _import_file(
        self, file_path: Path, precomputed: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """DEPRECATED: Import a single audio file into the database.

        .. deprecated::
            Use _import_track_from_scan() with ScannedTrack from LibraryFolderParser.
            This method relied on ID3 tags for artist/album identification which
            caused duplicate artists (109 instead of 13) due to tag inconsistencies.

        Extracts metadata, finds/creates artist and album, creates track.
        If precomputed dict is provided, uses its metadata and hash instead of recomputing.

        Args:
            file_path: Path to audio file
            precomputed: Optional precomputed metadata, hash, and size

        Returns:
            Dict with import result (imported, new_artist, matched_artist, etc.)
        """
        result = {
            "imported": False,
            "new_artist": False,
            "matched_artist": False,
            "new_album": False,
            "matched_album": False,
            "new_track": False,
        }

        # Check if track already exists by file path
        existing = await self._get_track_by_file_path(file_path)
        if existing:
            # Update last_scanned_at
            existing.last_scanned_at = datetime.now(UTC)
            result["imported"] = True
            return result

        # Use precomputed metadata/hash if available, otherwise extract now
        if precomputed:
            metadata = precomputed.get("metadata", {})
            # Note: file_hash and file_size are used in _add_track_with_file_info
            # which extracts them from precomputed dict or computes them itself
        else:
            # Fallback: extract metadata synchronously (slower!)
            # Hash and size will be computed by _add_track_with_file_info
            metadata = self._extract_metadata(file_path)

        if not metadata:
            # Hey future me - fallback to minimal metadata if extraction fails completely!
            # This happens with corrupted files or unknown formats.
            # We can still import the track using folder/filename info.
            metadata = {
                "format": file_path.suffix.lstrip(".").lower(),
                "duration_ms": 0,
            }
            logger.info(
                f"Using fallback metadata for {file_path.name} "
                f"(tag extraction failed, will use filename)"
            )

        # Extract metadata from folder structure (Lidarr-style fallback)
        # Hey future me - this adds artist_from_folder, album_from_folder, etc.
        # to fill in gaps when ID3 tags are missing or incomplete!
        folder_metadata = self._extract_metadata_from_path(file_path)

        # Use tag-based metadata with folder-based fallback
        # Ensure proper types with explicit casting
        artist_name_raw = metadata.get("artist") or folder_metadata.get(
            "artist_from_folder"
        )
        artist_name: str = str(artist_name_raw) if artist_name_raw else "Unknown Artist"

        album_name_raw = metadata.get("album") or folder_metadata.get("album_from_folder")
        album_name: str | None = str(album_name_raw) if album_name_raw else None

        # Hey future me - if no title in tags, use filename without extension
        # This ensures we can import files without metadata tags at all!
        track_title_raw = (
            metadata.get("title")
            or folder_metadata.get("title_from_folder")
            or file_path.stem
        )
        track_title: str = str(track_title_raw) if track_title_raw else file_path.stem

        # Use year from tags, fallback to folder parsing
        release_year_raw = metadata.get("year") or folder_metadata.get("year_from_folder")
        release_year: int | None = int(release_year_raw) if release_year_raw else None

        # Track number: tags > folder parsing (track_number_from_folder)
        track_number_raw = metadata.get("track_number") or folder_metadata.get(
            "track_number_from_folder"
        )
        track_number: int | None = int(track_number_raw) if track_number_raw else None

        # Disc number: tags > folder parsing
        disc_number_raw = metadata.get("disc_number") or folder_metadata.get(
            "disc_number_from_folder", 1
        )
        disc_number: int = int(disc_number_raw) if disc_number_raw else 1

        # Hey future me - album_artist (TPE2) is crucial for compilation detection!
        # If TPE2 is "Various Artists" but artist is different, it's a compilation.
        album_artist = metadata.get("album_artist")
        is_compilation = metadata.get("compilation", False)

        # FOLDER NAME FALLBACK for album_artist!
        # Hey future me - Lidarr stores compilations in "Various Artists" folder.
        # If album_artist tag is missing, check if parent folder looks like a VA folder.
        # Common patterns: "Various Artists", "Various Artists (add compilations...)", "VA"
        if not album_artist:
            album_artist = self._detect_album_artist_from_path(file_path)
            if album_artist:
                logger.debug(
                    f"Detected album_artist from folder structure: {album_artist}"
                )
                # If we detected VA from folder, mark as compilation
                if is_various_artists(album_artist):
                    is_compilation = True

        # Find or create artist (fuzzy matching)
        artist_id, is_new_artist, is_matched = await self._find_or_create_artist(
            artist_name
        )
        result["new_artist"] = is_new_artist
        result["matched_artist"] = is_matched

        # Find or create album (if present)
        # Now passes album_artist and compilation flag for proper type detection!
        album_id = None
        if album_name:
            album_id, is_new_album, is_matched_album = await self._find_or_create_album(
                album_name,
                artist_id,
                release_year=release_year,
                album_artist=album_artist,
                is_compilation=is_compilation,
            )
            result["new_album"] = is_new_album
            result["matched_album"] = is_matched_album

        # Create track
        # Hey future me - ALWAYS store resolved absolute path!
        # Otherwise incremental scan won't find the track in DB.
        track = Track(
            id=TrackId.generate(),
            title=track_title,
            artist_id=artist_id,
            album_id=album_id,
            duration_ms=metadata.get("duration_ms", 0),
            track_number=track_number,
            disc_number=disc_number,
            file_path=FilePath.from_string(str(file_path.resolve())),
            genres=[metadata["genre"]] if metadata.get("genre") else [],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Add file metadata to track model directly
        await self._add_track_with_file_info(track, file_path, metadata, precomputed=precomputed)

        result["imported"] = True
        result["new_track"] = True
        return result

    async def _add_track_with_file_info(
        self,
        track: Track,
        file_path: Path,
        metadata: dict[str, Any],
        precomputed: dict[str, Any] | None = None,
    ) -> None:
        """Add track with additional file info (hash, size, format, etc.).

        If precomputed dict is provided, uses precomputed hash/size instead of computing.
        """
        primary_genre = track.genres[0] if track.genres else None

        # Use precomputed hash/size if available
        if precomputed:
            file_hash = precomputed.get("hash", "")
            file_size = precomputed.get("size", 0)
        else:
            # Fallback: compute now (slower, only if precomputed wasn't used)
            file_hash = self._compute_file_hash(file_path)
            file_size = file_path.stat().st_size

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
            # File info
            file_size=file_size,
            file_hash=file_hash,
            file_hash_algorithm="sha256",
            audio_bitrate=metadata.get("bitrate"),
            audio_format=metadata.get("format"),
            audio_sample_rate=metadata.get("sample_rate"),
            last_scanned_at=datetime.now(UTC),
            is_broken=False,
            created_at=track.created_at,
            updated_at=track.updated_at,
        )
        self.session.add(model)

    async def _get_track_by_file_path(self, file_path: Path) -> TrackModel | None:
        """Get track by file path.

        Hey future me - use resolved path for consistent DB lookup!
        """
        stmt = select(TrackModel).where(TrackModel.file_path == str(file_path.resolve()))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================================
    # METADATA EXTRACTION (LEGACY - used internally by deprecated methods)
    # =========================================================================
    # Hey future me - _extract_metadata() extracts ALL tags including artist/album/title.
    # This is still used by:
    #   - _prep_file_sync() (deprecated)
    #   - _import_file() (deprecated)  
    # The new primary path uses _extract_audio_info() which only extracts technical data:
    #   - duration_ms, bitrate, sample_rate, format, genre
    # Consider removing once all old import methods are removed.
    # =========================================================================

    def _extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract full audio metadata using mutagen (including ID3 tags).

        .. note::
            For the new folder-first scanning, use _extract_audio_info() instead
            which only extracts technical audio data (duration, bitrate, etc.)
            without parsing artist/album/title from tags.

        Hey future me - this now ALWAYS returns a dict, even if extraction fails!
        At minimum: {"format": ".mp3", "duration_ms": 0}
        This prevents tracks from being skipped due to metadata errors.

        Args:
            file_path: Path to audio file

        Returns:
            Dict with metadata (at least format and duration_ms)
        """
        metadata: dict[str, Any] = {
            "format": file_path.suffix.lstrip(".").lower(),
            "duration_ms": 0,
        }

        try:
            audio = MutagenFile(file_path)
            if audio is None:
                logger.debug(f"MutagenFile returned None for {file_path}")
                return metadata

            # Duration (most important info besides filename)
            if hasattr(audio.info, "length") and audio.info.length:
                metadata["duration_ms"] = int(audio.info.length * 1000)

            # Audio quality
            if hasattr(audio.info, "bitrate") and audio.info.bitrate:
                metadata["bitrate"] = audio.info.bitrate
            if hasattr(audio.info, "sample_rate") and audio.info.sample_rate:
                metadata["sample_rate"] = audio.info.sample_rate

            # Extract tags based on format
            if hasattr(audio, "tags") and audio.tags:
                tag_data = self._extract_tags(audio)
                metadata.update(tag_data)
                logger.debug(f"Extracted tags for {file_path.name}: {list(tag_data.keys())}")
            else:
                logger.debug(f"No tags found in {file_path.name} (format: {metadata['format']})")

            return metadata

        except Exception as e:
            logger.warning(
                f"Error extracting full metadata from {file_path}: {e}. "
                f"Using fallback: format={metadata['format']}"
            )
            return metadata

    def _extract_tags(self, audio: Any) -> dict[str, Any]:
        """Extract common tags from audio file.

        Handles different tag formats (ID3, Vorbis, MP4).
        Now also extracts album_artist (TPE2) for compilation detection!
        """
        tags: dict[str, Any] = {}

        # Hey future me - TPE2 (Album Artist) is crucial for compilation detection!
        # If TPE2 is "Various Artists" but TPE1 (track artist) is different, it's likely
        # a compilation. Common patterns:
        # - Various Artists / VA / V.A. -> compilation
        # - Same as album title (like "Soundtrack") -> compilation
        # Try common tag mappings
        tag_mappings = {
            # ID3 (MP3)
            "TIT2": "title",
            "TPE1": "artist",
            "TPE2": "album_artist",  # Album Artist - crucial for compilations!
            "TALB": "album",
            "TRCK": "track_number",
            "TPOS": "disc_number",
            "TYER": "year",
            "TDRC": "year",
            "TCON": "genre",
            "TCMP": "compilation",  # iTunes compilation flag (1 = compilation)
            # Vorbis (FLAC, OGG)
            "title": "title",
            "artist": "artist",
            "albumartist": "album_artist",  # Album artist for Vorbis
            "album artist": "album_artist",  # Alternative spelling
            "album": "album",
            "tracknumber": "track_number",
            "discnumber": "disc_number",
            "date": "year",
            "genre": "genre",
            "compilation": "compilation",  # Vorbis compilation flag
            # MP4 (M4A)
            "©nam": "title",
            "©ART": "artist",
            "aART": "album_artist",  # MP4 Album Artist
            "©alb": "album",
            "©day": "year",
            "©gen": "genre",
            "trkn": "track_number",
            "disk": "disc_number",
            "cpil": "compilation",  # MP4 compilation flag
        }

        audio_tags = audio.tags
        if not audio_tags:
            return tags

        for tag_key, field_name in tag_mappings.items():
            if tag_key in audio_tags:
                value = audio_tags[tag_key]

                # Handle different value types
                if isinstance(value, list) and value:
                    value = value[0]
                if hasattr(value, "text"):
                    value = (
                        value.text[0] if isinstance(value.text, list) else value.text
                    )

                # Parse track/disc numbers (might be "1/12" format)
                if field_name in ("track_number", "disc_number"):
                    if isinstance(value, tuple):
                        value = value[0]
                    elif isinstance(value, str) and "/" in value:
                        value = value.split("/")[0]
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        value = None

                # Parse year
                if field_name == "year" and value:
                    try:
                        value = int(str(value)[:4])
                    except (ValueError, TypeError):
                        value = None

                # Parse compilation flag (can be "1", "true", True, etc.)
                if field_name == "compilation" and value:
                    if isinstance(value, bool):
                        value = value
                    elif isinstance(value, int | float):
                        value = bool(value)
                    elif isinstance(value, str):
                        value = value.lower() in ("1", "true", "yes")
                    else:
                        value = False

                if value is not None:
                    tags[field_name] = value

        return tags

    def _compute_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Compute SHA256 hash of file for deduplication."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

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
            logger.warning(f"Error extracting audio info from {file_path}: {e}")
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
                    value = value.text[0] if isinstance(value.text, list) else value.text
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
        result = await self.session.execute(artist_stmt)
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
        result = await self.session.execute(album_stmt)
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
        from soulspot.domain.value_objects.folder_parsing import (
            is_disc_folder,
            parse_album_folder,
            parse_track_filename,
        )

        metadata: dict[str, str | int | None] = {}

        # Parse track filename
        parsed_track = parse_track_filename(file_path.name)
        if parsed_track.title:
            metadata["title_from_folder"] = parsed_track.title
        if parsed_track.track_number > 0:
            metadata["track_number_from_folder"] = parsed_track.track_number
        if parsed_track.disc_number > 1:
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
            metadata["artist_from_folder"] = current.name

        return metadata

    async def _cleanup_missing_files(self, existing_file_paths: set[str]) -> dict[str, int]:
        """Remove tracks from DB whose files no longer exist on disk.

        Hey future me - this is the CLEANUP phase of full scan!
        Called ONLY during full scan (incremental=False).

        Also removes orphaned albums (no tracks) and artists (no albums/tracks).

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

        # Step 1: Find tracks with file_path that no longer exist
        logger.info("Checking for tracks with missing files...")

        stmt = select(TrackModel.id, TrackModel.file_path, TrackModel.title).where(
            TrackModel.file_path.isnot(None)
        )
        result = await self.session.execute(stmt)
        db_tracks = result.all()

        tracks_to_remove: list[str] = []
        for track_id, file_path, title in db_tracks:
            if file_path not in existing_file_paths:
                tracks_to_remove.append(track_id)
                logger.debug(f"Track file missing: {title} ({file_path})")

        if tracks_to_remove:
            logger.info(f"Removing {len(tracks_to_remove)} tracks with missing files...")

            # Delete tracks in batches
            for i in range(0, len(tracks_to_remove), 100):
                batch = tracks_to_remove[i:i + 100]
                delete_stmt = delete(TrackModel).where(TrackModel.id.in_(batch))
                await self.session.execute(delete_stmt)

            stats["removed_tracks"] = len(tracks_to_remove)
            logger.info(f"Removed {len(tracks_to_remove)} tracks")
        else:
            logger.info("No tracks with missing files found")

        # Step 2: Remove orphaned albums (albums with no tracks)
        logger.info("Checking for orphaned albums...")

        orphan_albums_stmt = (
            select(AlbumModel.id, AlbumModel.title)
            .outerjoin(TrackModel, AlbumModel.id == TrackModel.album_id)
            .group_by(AlbumModel.id)
            .having(func.count(TrackModel.id) == 0)
        )
        orphan_albums_result = await self.session.execute(orphan_albums_stmt)
        orphan_albums = orphan_albums_result.all()

        if orphan_albums:
            album_ids = [album_id for album_id, _ in orphan_albums]
            logger.info(f"Removing {len(album_ids)} orphaned albums...")

            for _album_id, title in orphan_albums:
                logger.debug(f"Removing orphaned album: {title}")

            delete_albums_stmt = delete(AlbumModel).where(AlbumModel.id.in_(album_ids))
            await self.session.execute(delete_albums_stmt)
            stats["removed_albums"] = len(album_ids)
            logger.info(f"Removed {len(album_ids)} orphaned albums")
        else:
            logger.info("No orphaned albums found")

        # Step 3: Remove orphaned artists (artists with no tracks AND no albums)
        logger.info("Checking for orphaned artists...")

        # Artists that have neither tracks nor albums
        orphan_artists_stmt = (
            select(ArtistModel.id, ArtistModel.name)
            .outerjoin(TrackModel, ArtistModel.id == TrackModel.artist_id)
            .outerjoin(AlbumModel, ArtistModel.id == AlbumModel.artist_id)
            .group_by(ArtistModel.id)
            .having(
                (func.count(TrackModel.id) == 0) &
                (func.count(AlbumModel.id) == 0)
            )
        )
        orphan_artists_result = await self.session.execute(orphan_artists_stmt)
        orphan_artists = orphan_artists_result.all()

        if orphan_artists:
            artist_ids = [artist_id for artist_id, _ in orphan_artists]
            logger.info(f"Removing {len(artist_ids)} orphaned artists...")

            for _artist_id, name in orphan_artists:
                logger.debug(f"Removing orphaned artist: {name}")

            delete_artists_stmt = delete(ArtistModel).where(ArtistModel.id.in_(artist_ids))
            await self.session.execute(delete_artists_stmt)
            stats["removed_artists"] = len(artist_ids)
            logger.info(f"Removed {len(artist_ids)} orphaned artists")
        else:
            logger.info("No orphaned artists found")

        # Commit cleanup changes
        await self.session.commit()

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
        albums_stmt = (
            select(
                AlbumModel.id,
                AlbumModel.title,
                AlbumModel.album_artist,
                AlbumModel.secondary_types,
            )
        )
        albums_result = await self.session.execute(albums_stmt)
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
            tracks_result = await self.session.execute(tracks_stmt)
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
                update_stmt = (
                    select(AlbumModel).where(AlbumModel.id == album_id)
                )
                update_result = await self.session.execute(update_stmt)
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
        album_result = await self.session.execute(album_count_stmt)
        album_count = album_result.scalar() or 0

        track_count_stmt = select(func.count(TrackModel.id))
        track_result = await self.session.execute(track_count_stmt)
        track_count = track_result.scalar() or 0

        # Count files with file_path
        local_count_stmt = select(func.count(TrackModel.id)).where(
            TrackModel.file_path.isnot(None)
        )
        local_result = await self.session.execute(local_count_stmt)
        local_count = local_result.scalar() or 0

        return {
            "total_artists": artist_count,
            "total_albums": album_count,
            "total_tracks": track_count,
            "local_files": local_count,
            "music_path": str(self.music_path),
        }
