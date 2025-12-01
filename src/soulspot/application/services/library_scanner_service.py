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
from sqlalchemy import select
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
AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".ogg",
    ".opus",
    ".wav",
    ".aac",
    ".wma",
    ".ape",
    ".alac",
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

        Args:
            incremental: If True, only scan new/modified files
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
        }

        try:
            # Validate music path
            if not self.music_path.exists():
                raise FileNotFoundError(f"Music path does not exist: {self.music_path}")

            # Discover all audio files
            all_files = self._discover_audio_files(self.music_path)
            stats["total_files"] = len(all_files)

            logger.info(f"Found {len(all_files)} audio files in {self.music_path}")

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

            # Pre-load artist/album caches for faster fuzzy matching
            await self._load_caches()

            # Process each file
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

                    # Progress callback
                    if progress_callback:
                        progress = (i + 1) / len(files_to_scan) * 100
                        await progress_callback(progress, stats)

                except Exception as e:
                    stats["errors"] += 1
                    stats["error_files"].append(
                        {"path": str(file_path), "error": str(e)}
                    )
                    logger.warning(f"Error importing {file_path}: {e}")

            await self.session.commit()
            stats["completed_at"] = datetime.now(UTC).isoformat()

            logger.info(
                f"Library scan complete: {stats['imported']} imported, "
                f"{stats['skipped']} skipped, {stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Library scan failed: {e}")
            stats["error"] = str(e)

        return stats

    def _discover_audio_files(self, directory: Path) -> list[Path]:
        """Recursively discover all audio files in directory.

        Args:
            directory: Root directory to scan

        Returns:
            List of audio file paths
        """
        audio_files: list[Path] = []
        for root, _, files in os.walk(directory):
            for filename in files:
                if Path(filename).suffix.lower() in AUDIO_EXTENSIONS:
                    audio_files.append(Path(root) / filename)
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
            path_str = str(file_path)

            # New file (not in DB)
            if path_str not in known_files:
                changed_files.append(file_path)
                continue

            # Check if modified since last scan
            last_scanned = known_files[path_str]
            if last_scanned:
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

        # Extract metadata
        metadata = self._extract_metadata(file_path)
        if not metadata:
            raise ValueError(f"Could not extract metadata from {file_path}")

        artist_name = metadata.get("artist", "Unknown Artist")
        album_name = metadata.get("album")
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
        track = Track(
            id=TrackId.generate(),
            title=track_title,
            artist_id=artist_id,
            album_id=album_id,
            duration_ms=metadata.get("duration_ms", 0),
            track_number=metadata.get("track_number"),
            disc_number=metadata.get("disc_number", 1),
            file_path=FilePath.from_string(str(file_path)),
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
        """Get track by file path."""
        stmt = select(TrackModel).where(TrackModel.file_path == str(file_path))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================================
    # METADATA EXTRACTION
    # =========================================================================

    def _extract_metadata(self, file_path: Path) -> dict[str, Any] | None:
        """Extract audio metadata using mutagen.

        Args:
            file_path: Path to audio file

        Returns:
            Dict with metadata or None if extraction failed
        """
        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return None

            metadata: dict[str, Any] = {
                "format": file_path.suffix.lstrip(".").lower(),
            }

            # Duration
            if hasattr(audio.info, "length"):
                metadata["duration_ms"] = int(audio.info.length * 1000)

            # Audio quality
            if hasattr(audio.info, "bitrate"):
                metadata["bitrate"] = audio.info.bitrate
            if hasattr(audio.info, "sample_rate"):
                metadata["sample_rate"] = audio.info.sample_rate

            # Extract tags based on format
            if hasattr(audio, "tags") and audio.tags:
                metadata.update(self._extract_tags(audio))

            return metadata

        except Exception as e:
            logger.warning(f"Error extracting metadata from {file_path}: {e}")
            return None

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
        """Detect album_artist from folder structure (Lidarr-style organization).

        Hey future me - this handles Lidarr's folder convention!
        Lidarr stores music as: /music/Artist Name/Album Name/track.mp3
        For compilations: /music/Various Artists (add compilations...)/Album Name/track.mp3

        We look at parent directories and check if any match VA patterns.

        Args:
            file_path: Path to the audio file

        Returns:
            Detected album_artist or None if no VA pattern found
        """
        # Check grandparent folder (artist folder in Lidarr structure)
        # file_path = /music/Various Artists/Album Name/01 - Track.mp3
        #                   ^^^^^^^^^^^^^^^^ this is grandparent
        try:
            grandparent = file_path.parent.parent.name
            if grandparent and is_various_artists(grandparent):
                # Extract clean name (remove Lidarr suffixes like "(add compilations...)")
                clean_name = grandparent
                # Remove parenthetical suffixes like "(add compilations to this artist)"
                if "(" in clean_name:
                    clean_name = clean_name[: clean_name.index("(")].strip()
                # Normalize to "Various Artists" if it matches VA pattern
                return clean_name if clean_name else "Various Artists"
        except (ValueError, IndexError):
            pass

        # Also check parent folder (album folder) - some setups use:
        # /music/Various Artists/01 - Track.mp3 (flat structure)
        try:
            parent = file_path.parent.name
            if parent and is_various_artists(parent):
                return "Various Artists"
        except (ValueError, IndexError):
            pass

        return None

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


# Import func for count queries
from sqlalchemy import func  # noqa: E402
