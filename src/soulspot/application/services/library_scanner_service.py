# Hey future me - this service scans the local music directory and imports files into the DB!
# Key features:
# 1. JOB QUEUE integration - runs as background job (use JobQueue for async scanning)
# 2. FUZZY MATCHING - finds existing artists/albums with 85% similarity (rapidfuzz)
# 3. INCREMENTAL SCAN - only processes new/changed files based on mtime
# 4. COMPILATION DETECTION - reads TPE2 (Album Artist) tag, detects "Various Artists"
# The goal: import existing music collection, avoid re-downloading already owned tracks!
"""Library scanner service for importing local music files into database."""

import hashlib
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile  # type: ignore[attr-defined]
from rapidfuzz import fuzz
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

# Supported audio file extensions
# Hey future me - alle gängigen Formate! Mutagen unterstützt die meisten davon.
AUDIO_EXTENSIONS = {
    # Lossy
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    # Lossless
    ".flac",
    ".wav",
    ".aiff",
    ".aif",
    ".alac",
    ".ape",
    ".wv",      # WavPack
    ".tta",     # True Audio
    ".dsd",     # DSD Audio
    ".dsf",     # DSD Stream File
    ".dff",     # DSDIFF
    # Other
    ".mpc",     # Musepack
    ".mp4",     # Can contain audio
    ".webm",    # Can contain audio (Opus/Vorbis)
}


class LibraryScannerService:
    """Service for scanning local music directory and importing to database.

    This service handles:
    1. Discovering audio files in the music directory
    2. Extracting metadata via mutagen (title, artist, album, etc.)
    3. Fuzzy-matching artists and albums (85% threshold)
    4. Incremental scanning (only new/modified files)
    5. Tracking scan progress for UI feedback

    Works with JobQueue for background processing!
    """

    # Fuzzy matching threshold (0-100). Higher = stricter matching.
    # 85% works well for "Pink Floyd" vs "The Pink Floyd" or typos
    FUZZY_THRESHOLD = 85

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

        # Cache for fuzzy matching (avoid repeated DB queries)
        self._artist_cache: dict[str, ArtistId] = {}
        self._album_cache: dict[str, AlbumId] = {}

    # =========================================================================
    # MAIN SCAN METHODS
    # =========================================================================

    async def scan_library(
        self,
        incremental: bool = True,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Scan the entire music library.

        This is the MAIN entry point! Call this from JobQueue handler.

        Hey future me - Full Scan (incremental=False) does THREE things:
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
            "matched_artists": 0,
            "matched_albums": 0,
            # New stats for cleanup
            "removed_tracks": 0,
            "removed_albums": 0,
            "removed_artists": 0,
            # New stats for diversity analysis
            "compilations_detected": 0,
        }

        try:
            # Validate music path
            if not self.music_path.exists():
                raise FileNotFoundError(f"Music path does not exist: {self.music_path}")

            # Log detailed path info for debugging
            logger.info(f"Scanning music library at: {self.music_path}")
            logger.info(f"Music path is absolute: {self.music_path.is_absolute()}")
            logger.info(f"Music path resolved: {self.music_path.resolve()}")
            logger.info(f"Scan mode: {'incremental' if incremental else 'FULL (with cleanup)'}")
            
            # Count subdirectories for debugging
            try:
                subdirs = [d for d in self.music_path.iterdir() if d.is_dir()]
                logger.info(f"Found {len(subdirs)} top-level subdirectories in music path")
                if subdirs[:5]:
                    logger.info(f"First 5 subdirs: {[d.name for d in subdirs[:5]]}")
            except Exception as e:
                logger.warning(f"Could not list subdirectories: {e}")

            # Discover all audio files
            # Hey future me - ALWAYS use resolved absolute paths for consistency!
            # Otherwise ./music/track.mp3 vs /music/track.mp3 won't match in DB lookups.
            all_files = self._discover_audio_files(self.music_path.resolve())
            all_file_paths = {str(f.resolve()) for f in all_files}
            stats["total_files"] = len(all_files)

            logger.info(f"Found {len(all_files)} audio files in {self.music_path}")

            # For FULL scan: Remove tracks whose files no longer exist
            if not incremental:
                cleanup_stats = await self._cleanup_missing_files(all_file_paths)
                stats["removed_tracks"] = cleanup_stats["removed_tracks"]
                stats["removed_albums"] = cleanup_stats["removed_albums"]
                stats["removed_artists"] = cleanup_stats["removed_artists"]
                
                # Clear caches after cleanup (they may reference deleted entities)
                self._artist_cache.clear()
                self._album_cache.clear()

            # Filter to only new/modified files if incremental
            if incremental:
                files_to_scan = await self._filter_changed_files(all_files)
                stats["skipped"] = len(all_files) - len(files_to_scan)
                logger.info(
                    f"Incremental scan: {len(files_to_scan)} new/modified, "
                    f"{stats['skipped']} unchanged"
                )
            else:
                files_to_scan = all_files
                logger.info(f"Full scan: processing all {len(files_to_scan)} files")

            # Pre-load artist/album caches for faster fuzzy matching
            await self._load_caches()

            # Process each file with batch commits for stability
            # Hey future me - commit every 100 files to:
            # 1. Prevent memory issues with 5000+ tracks
            # 2. Not lose everything if something fails at file 4999
            BATCH_SIZE = 100
            
            for i, file_path in enumerate(files_to_scan):
                try:
                    result = await self._import_file(file_path)
                    stats["scanned"] += 1

                    if result["imported"]:
                        stats["imported"] += 1
                        if result.get("new_artist"):
                            stats["new_artists"] += 1
                        if result.get("matched_artist"):
                            stats["matched_artists"] += 1
                        if result.get("new_album"):
                            stats["new_albums"] += 1
                        if result.get("matched_album"):
                            stats["matched_albums"] += 1
                        if result.get("new_track"):
                            stats["new_tracks"] += 1

                    # Batch commit every BATCH_SIZE files
                    if (i + 1) % BATCH_SIZE == 0:
                        await self.session.commit()
                        logger.debug(f"Committed batch {(i + 1) // BATCH_SIZE} ({i + 1} files)")

                    # Progress callback
                    if progress_callback:
                        progress = (i + 1) / len(files_to_scan) * 100
                        await progress_callback(progress, stats)

                except Exception as e:
                    stats["errors"] += 1
                    error_msg = str(e)
                    stats["error_files"].append(
                        {"path": str(file_path), "error": error_msg}
                    )
                    # Log with traceback for debugging metadata issues
                    logger.warning(
                        f"Error importing {file_path.name}: {error_msg} "
                        f"(format: {file_path.suffix})",
                        exc_info=False,  # Don't spam with full traceback, just the message
                    )
                    # Continue with next file instead of crashing
                    continue

            # Final commit for remaining files
            await self.session.commit()
            
            # POST-SCAN: Diversity analysis for albums without album_artist tag
            # Hey future me - this is the SPOTIFY/LIDARR logic:
            # If album has >4 unique track artists AND no album_artist set → Compilation!
            diversity_stats = await self._analyze_album_diversity()
            stats["compilations_detected"] = diversity_stats["compilations_detected"]
            
            await self.session.commit()
            stats["completed_at"] = datetime.now(UTC).isoformat()

            logger.info(
                f"Library scan complete: {stats['imported']} imported, "
                f"{stats['skipped']} skipped, {stats['errors']} errors, "
                f"{stats['compilations_detected']} compilations detected via diversity"
            )

        except Exception as e:
            logger.error(f"Library scan failed: {e}")
            stats["error"] = str(e)

        return stats

    def _discover_audio_files(self, directory: Path) -> list[Path]:
        """Recursively discover all audio files in directory.

        Hey future me - followlinks=True ist wichtig für Symlink-Ordner!
        Viele Setups haben /music als Symlink zu einer externen Platte.

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
        
        # followlinks=True folgt Symlinks zu anderen Ordnern
        for root, dirs, files in os.walk(directory, followlinks=True):
            # Log wenn wir Zugriffsprobleme haben
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
        
        # Log extension statistics for debugging
        logger.info(f"Total files seen: {total_files_seen}")
        logger.info(f"Audio files matched: {len(audio_files)}")
        
        # Show top 10 extensions found
        top_extensions = all_extensions.most_common(15)
        logger.info(f"Top file extensions found: {top_extensions}")
        
        # Show which audio extensions were found
        audio_ext_counts = {ext: all_extensions[ext] for ext in AUDIO_EXTENSIONS if all_extensions[ext] > 0}
        logger.info(f"Audio extensions found: {audio_ext_counts}")
        
        if skipped_dirs:
            logger.warning(
                f"Skipped {len(skipped_dirs)} directories due to permissions: "
                f"{skipped_dirs[:5]}{'...' if len(skipped_dirs) > 5 else ''}"
            )
        
        return audio_files

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
    # FILE IMPORT
    # =========================================================================

    async def _import_file(self, file_path: Path) -> dict[str, Any]:
        """Import a single audio file into the database.

        Extracts metadata, finds/creates artist and album, creates track.

        Args:
            file_path: Path to audio file

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

        # Extract metadata - try to get as much as possible, use fallbacks for missing data
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

        artist_name = metadata.get("artist", "Unknown Artist")
        album_name = metadata.get("album")
        # Hey future me - if no title in tags, use filename without extension
        # This ensures we can import files without metadata tags at all!
        track_title = metadata.get("title") or file_path.stem

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
                release_year=metadata.get("year"),
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
            track_number=metadata.get("track_number"),
            disc_number=metadata.get("disc_number", 1),
            file_path=FilePath.from_string(str(file_path.resolve())),
            genres=[metadata["genre"]] if metadata.get("genre") else [],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Add file metadata to track model directly
        await self._add_track_with_file_info(track, file_path, metadata)

        result["imported"] = True
        result["new_track"] = True
        return result

    async def _add_track_with_file_info(
        self,
        track: Track,
        file_path: Path,
        metadata: dict[str, Any],
    ) -> None:
        """Add track with additional file info (hash, size, format, etc.)."""
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
            # File info
            file_size=file_path.stat().st_size,
            file_hash=self._compute_file_hash(file_path),
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
    # METADATA EXTRACTION
    # =========================================================================

    def _extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract audio metadata using mutagen.

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

    # =========================================================================
    # FUZZY MATCHING
    # =========================================================================

    async def _load_caches(self) -> None:
        """Pre-load artist and album names for fuzzy matching."""
        # Load all artists
        artist_stmt = select(ArtistModel.id, ArtistModel.name)
        result = await self.session.execute(artist_stmt)
        for row in result.all():
            artist_id = ArtistId.from_string(row[0])
            self._artist_cache[row[1].lower()] = artist_id

        # Load all albums
        # Hey future me - nutze album_artist für Cache-Key bei Kompilationen!
        # Sonst werden Tracks verschiedener Künstler zu verschiedenen Alben zugeordnet.
        album_stmt = select(
            AlbumModel.id,
            AlbumModel.title,
            AlbumModel.artist_id,
            AlbumModel.album_artist,
        )
        result = await self.session.execute(album_stmt)
        for row in result.all():
            album_id = AlbumId.from_string(row[0])
            # Nutze album_artist wenn vorhanden (für Kompilationen), sonst artist_id
            album_key = row[3].lower() if row[3] else row[2]
            cache_key = f"{row[1].lower()}|{album_key}"
            self._album_cache[cache_key] = album_id

        logger.debug(
            f"Loaded caches: {len(self._artist_cache)} artists, "
            f"{len(self._album_cache)} albums"
        )

    async def _find_or_create_artist(self, name: str) -> tuple[ArtistId, bool, bool]:
        """Find existing artist by fuzzy matching or create new.

        Args:
            name: Artist name from metadata

        Returns:
            Tuple of (artist_id, is_new, is_fuzzy_matched)
        """
        name_lower = name.lower()

        # Exact match first
        if name_lower in self._artist_cache:
            return self._artist_cache[name_lower], False, False

        # Fuzzy match
        best_match: str | None = None
        best_score: float = 0.0

        for cached_name in self._artist_cache:
            score = fuzz.ratio(name_lower, cached_name)
            if score > best_score:
                best_score = score
                best_match = cached_name

        # Use fuzzy match if above threshold
        if best_match and best_score >= self.FUZZY_THRESHOLD:
            logger.debug(
                f"Fuzzy matched artist '{name}' to '{best_match}' (score: {best_score})"
            )
            return self._artist_cache[best_match], False, True

        # Create new artist
        artist = Artist(
            id=ArtistId.generate(),
            name=name,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await self.artist_repo.add(artist)

        # Add to cache
        self._artist_cache[name_lower] = artist.id
        logger.debug(f"Created new artist: {name}")

        return artist.id, True, False

    async def _find_or_create_album(
        self,
        title: str,
        artist_id: ArtistId,
        release_year: int | None = None,
        album_artist: str | None = None,
        is_compilation: bool = False,
    ) -> tuple[AlbumId, bool, bool]:
        """Find existing album by fuzzy matching or create new.

        Now supports album_artist (TPE2) and compilation detection!

        Args:
            title: Album title from metadata
            artist_id: Artist ID (track-level artist)
            release_year: Optional release year
            album_artist: Album-level artist (TPE2 tag) - often "Various Artists" for compilations
            is_compilation: True if compilation flag is set in metadata

        Returns:
            Tuple of (album_id, is_new, is_fuzzy_matched)
        """
        title_lower = title.lower()
        artist_id_str = str(artist_id.value)

        # Hey future me - für Kompilationen nutze album_artist statt track artist!
        # Sonst wird jeder Track-Künstler ein neues Album erstellen.
        # Beispiel: "Greatest Hits" mit 30 Künstlern = 30 Alben ohne diesen Fix!
        album_key = album_artist.lower() if album_artist else artist_id_str

        # Exact match first
        cache_key = f"{title_lower}|{album_key}"
        if cache_key in self._album_cache:
            return self._album_cache[cache_key], False, False

        # Fuzzy match (only for same album_artist/artist)
        best_match_key: str | None = None
        best_score: float = 0.0

        for cached_key, _cached_album_id in self._album_cache.items():
            cached_title, cached_artist = cached_key.rsplit("|", 1)
            if cached_artist != album_key:
                continue

            score = fuzz.ratio(title_lower, cached_title)
            if score > best_score:
                best_score = score
                best_match_key = cached_key

        # Use fuzzy match if above threshold
        if best_match_key and best_score >= self.FUZZY_THRESHOLD:
            logger.debug(f"Fuzzy matched album '{title}' (score: {best_score})")
            return self._album_cache[best_match_key], False, True

        # Determine secondary_types using Lidarr-style compilation detection
        # Hey future me - this uses the new detect_compilation() with full heuristics!
        # We pass explicit_flag (from TCMP/cpil) and album_artist, track_artists come later
        # via post-scan analysis (when we have all tracks for diversity calculation).
        detection_result = detect_compilation(
            album_artist=album_artist,
            track_artists=None,  # Not available yet at single-file scan time
            explicit_flag=is_compilation if is_compilation else None,
        )

        secondary_types: list[str] = []
        if detection_result.is_compilation:
            secondary_types.append(SecondaryAlbumType.COMPILATION.value)
            logger.debug(
                f"Album '{title}' detected as compilation: "
                f"reason={detection_result.reason}, confidence={detection_result.confidence:.0%}"
            )

        # Create new album
        album = Album(
            id=AlbumId.generate(),
            title=title,
            artist_id=artist_id,
            release_year=release_year,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Add album via repository, then update model directly for new fields
        await self.album_repo.add(album)

        # Get the model and set the new fields (album_artist, secondary_types)
        # Hey - we need to update the model directly because Album entity doesn't have these yet
        stmt = select(AlbumModel).where(AlbumModel.id == str(album.id.value))
        result = await self.session.execute(stmt)
        album_model = result.scalar_one()
        album_model.album_artist = album_artist
        album_model.secondary_types = secondary_types

        # Add to cache
        self._album_cache[cache_key] = album.id
        logger.debug(f"Created new album: {title}")

        return album.id, True, False

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
            
            for album_id, title in orphan_albums:
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
            
            for artist_id, name in orphan_artists:
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
