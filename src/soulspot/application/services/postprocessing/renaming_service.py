"""File renaming service with template-based naming."""

import errno
import logging
import re
import shutil
from pathlib import Path
from string import Formatter
from typing import TYPE_CHECKING

from soulspot.config import Settings
from soulspot.domain.entities import Album, Artist, Track

if TYPE_CHECKING:
    from soulspot.application.services.app_settings_service import AppSettingsService

logger = logging.getLogger(__name__)


class RenamingService:
    """Service for renaming files based on templates.

    Hey future me - this service was updated to support DYNAMIC templates from DB!
    The old behavior loaded template from Settings (env vars) at startup.
    Now we support two modes:
    1. Static mode (default): Uses template from Settings (backward compatible)
    2. Dynamic mode: Loads templates from AppSettingsService (DB) at runtime

    To use dynamic mode, call set_app_settings_service() after init.
    The generate_filename_async() method will then use DB settings.
    The sync generate_filename() falls back to static settings for compatibility.

    This service:
    1. Generates file names from templates
    2. Sanitizes file names for filesystem compatibility
    3. Handles naming collisions
    4. Organizes files into directory structures
    """

    # Characters not allowed in filenames
    ILLEGAL_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

    # Default templates (Lidarr-compatible)
    # Hey future me - Python's str.format uses :02d for zero-padding, not :00
    # Lidarr uses :00 but that's a custom parser. We use Python's standard format.
    DEFAULT_ARTIST_FOLDER = "{Artist Name}"
    DEFAULT_ALBUM_FOLDER = "{Album Title} ({Release Year})"
    DEFAULT_TRACK_FORMAT = "{Track Number:02d} - {Track Title}"
    DEFAULT_MULTI_DISC_FORMAT = "{Medium:02d}-{Track Number:02d} - {Track Title}"

    def __init__(self, settings: Settings) -> None:
        """Initialize renaming service.

        Args:
            settings: Application settings
        """
        self._settings = settings
        self._template = settings.postprocessing.file_naming_template
        self._app_settings_service: AppSettingsService | None = None

        # Cache for dynamic settings (refreshed on each call)
        self._cached_artist_folder: str | None = None
        self._cached_album_folder: str | None = None
        self._cached_track_format: str | None = None
        self._cached_multi_disc_format: str | None = None
        self._cached_colon_replacement: str | None = None
        self._cached_slash_replacement: str | None = None

    def set_app_settings_service(
        self, app_settings_service: "AppSettingsService"
    ) -> None:
        """Set the app settings service for dynamic template loading.

        Call this to enable dynamic templates from DB instead of static env vars.

        Args:
            app_settings_service: The settings service to use
        """
        self._app_settings_service = app_settings_service

    async def load_naming_settings(self) -> None:
        """Load naming settings from DB into cache.

        Call this before using generate_filename_async() to ensure
        the latest settings are used.
        """
        if self._app_settings_service is None:
            return

        self._cached_artist_folder = (
            await self._app_settings_service.get_artist_folder_format()
        )
        self._cached_album_folder = (
            await self._app_settings_service.get_album_folder_format()
        )
        self._cached_track_format = (
            await self._app_settings_service.get_standard_track_format()
        )
        self._cached_multi_disc_format = (
            await self._app_settings_service.get_multi_disc_track_format()
        )
        self._cached_colon_replacement = (
            await self._app_settings_service.get_colon_replacement()
        )
        self._cached_slash_replacement = (
            await self._app_settings_service.get_slash_replacement()
        )

    def _get_artist_folder_template(self) -> str:
        """Get artist folder template (cached or default)."""
        return self._cached_artist_folder or self.DEFAULT_ARTIST_FOLDER

    def _get_album_folder_template(self) -> str:
        """Get album folder template (cached or default)."""
        return self._cached_album_folder or self.DEFAULT_ALBUM_FOLDER

    def _get_track_format_template(self, is_multi_disc: bool = False) -> str:
        """Get track filename template (cached or default)."""
        if is_multi_disc:
            return self._cached_multi_disc_format or self.DEFAULT_MULTI_DISC_FORMAT
        return self._cached_track_format or self.DEFAULT_TRACK_FORMAT

    # Hey future me: Template-based file renaming - like a mail merge for file paths
    # Template example: "{Artist CleanName}/{Album CleanTitle}/{track:02d} - {Track CleanTitle}"
    # Result: "Pink Floyd/The Dark Side of the Moon/01 - Speak to Me.mp3"
    # WHY support both old and new variable names? Backward compatibility with user templates
    # GOTCHA: Illegal chars in artist/album names (e.g., "AC/DC") need sanitization or paths break
    def generate_filename(
        self,
        track: Track,
        artist: Artist,
        album: Album | None = None,
        extension: str = ".mp3",
    ) -> str:
        """Generate a filename from template.

        Args:
            track: Track entity
            artist: Artist entity
            album: Optional album entity
            extension: File extension (with dot)

        Returns:
            Generated filename (including path components)
        """
        # Hey future me - Album Type now uses the album_type_display property!
        album_type = "Album"
        if album and hasattr(album, "album_type_display"):
            album_type = album.album_type_display
        elif album and hasattr(album, "primary_type") and album.primary_type:
            album_type = album.primary_type.title()

        # Hey future me - Disambiguation is now sourced from Artist/Album entities!
        artist_disambiguation = ""
        if hasattr(artist, "disambiguation") and artist.disambiguation:
            artist_disambiguation = artist.disambiguation

        album_disambiguation = ""
        if album and hasattr(album, "disambiguation") and album.disambiguation:
            album_disambiguation = album.disambiguation

        # Prepare template variables with both old and new naming conventions
        variables = {
            # Legacy variables (for backward compatibility)
            "artist": artist.name,
            "title": track.title,
            "album": album.title if album else "Unknown Album",
            "track_number": track.track_number or 0,
            "disc_number": track.disc_number,
            "year": album.release_year if album else "",
            # New standardized variables
            "Artist CleanName": self._clean_name(artist.name),
            "Artist Disambiguation": artist_disambiguation,
            "Track CleanTitle": self._clean_name(track.title),
            "Album CleanTitle": self._clean_name(album.title)
            if album
            else "Unknown Album",
            "Album Disambiguation": album_disambiguation,
            "Album Type": album_type,
            "Release Year": str(album.release_year)
            if album and album.release_year
            else "",
            "medium": track.disc_number,
            "track": track.track_number or 0,
        }

        # Format template
        try:
            filename = self._template.format(**variables)
        except KeyError as e:
            logger.warning("Invalid template variable: %s, using fallback", e)
            # Fallback to simple naming
            filename = f"{artist.name}/{track.title}"

        # Add extension
        filename = filename + extension

        # Sanitize filename
        filename = self._sanitize_filename(filename)

        return filename

    async def generate_filename_async(
        self,
        track: Track,
        artist: Artist,
        album: Album | None = None,
        extension: str = ".mp3",
    ) -> str:
        """Generate a filename using dynamic templates from DB.

        Hey future me - this is the NEW async method that uses DB settings!
        It builds the path from three separate templates:
        1. Artist folder: {Artist Name}/
        2. Album folder: {Album Title} ({Release Year})/
        3. Track filename: {Track Number:00} - {Track Title}.ext

        This matches Lidarr's structure for compatibility.

        Args:
            track: Track entity
            artist: Artist entity
            album: Optional album entity
            extension: File extension (with dot)

        Returns:
            Generated filename (including path components)
        """
        # Load latest settings from DB
        await self.load_naming_settings()

        # Determine if multi-disc album (check track disc_number > 1)
        is_multi_disc = bool(track.disc_number and track.disc_number > 1)

        # Prepare template variables
        variables = self._build_template_variables(track, artist, album)

        # Build path from separate templates
        try:
            artist_folder = self._get_artist_folder_template().format(**variables)
            album_folder = self._get_album_folder_template().format(**variables)
            track_filename = self._get_track_format_template(is_multi_disc).format(
                **variables
            )
        except KeyError as e:
            logger.warning("Invalid template variable: %s, using fallback", e)
            # Fallback to simple naming
            artist_folder = artist.name
            album_folder = album.title if album else "Unknown Album"
            track_filename = track.title

        # Build full path
        filename = f"{artist_folder}/{album_folder}/{track_filename}{extension}"

        # Sanitize filename
        filename = self._sanitize_filename(filename)

        return filename

    def _build_template_variables(
        self,
        track: Track,
        artist: Artist,
        album: Album | None = None,
    ) -> dict[str, str | int]:
        """Build template variables dict for formatting.

        Hey future me - centralizes variable building for both sync and async methods.
        All variables are typed as str|int so format() can handle them.
        Zero-padded versions like {Track Number:00} are handled by format spec.

        Args:
            track: Track entity
            artist: Artist entity
            album: Optional album entity

        Returns:
            Dict of template variables
        """
        # Get character replacements
        colon_replacement = self._cached_colon_replacement or " -"
        slash_replacement = self._cached_slash_replacement or "-"

        # Hey future me - Album Type now uses the album_type_display property!
        # This combines primary_type and secondary_types into a Lidarr-compatible string.
        # Examples: "Album", "EP", "Live Album", "Compilation", "Remix EP"
        album_type = "Album"
        if album and hasattr(album, "album_type_display"):
            album_type = album.album_type_display
        elif album and hasattr(album, "primary_type") and album.primary_type:
            album_type = album.primary_type.title()

        # Hey future me - Disambiguation is now sourced from Artist/Album entities!
        # Format: Empty string if None, otherwise the disambiguation text (without parentheses).
        # The template itself handles the parentheses via { (Album Disambiguation)} syntax.
        artist_disambiguation = ""
        if hasattr(artist, "disambiguation") and artist.disambiguation:
            artist_disambiguation = artist.disambiguation

        album_disambiguation = ""
        if album and hasattr(album, "disambiguation") and album.disambiguation:
            album_disambiguation = album.disambiguation

        return {
            # Legacy variables (for backward compatibility)
            "artist": artist.name,
            "title": track.title,
            "album": album.title if album else "Unknown Album",
            "track_number": track.track_number or 0,
            "disc_number": track.disc_number or 1,
            "year": str(album.release_year) if album and album.release_year else "",
            # New standardized variables (Lidarr-compatible)
            "Artist Name": artist.name,
            "Artist CleanName": self._clean_name(
                artist.name, colon_replacement, slash_replacement
            ),
            "Artist Disambiguation": artist_disambiguation,
            "Track Title": track.title,
            "Track CleanTitle": self._clean_name(
                track.title, colon_replacement, slash_replacement
            ),
            "Track Number": track.track_number or 0,
            "Track Number:00": f"{track.track_number or 0:02d}",
            "Album Title": album.title if album else "Unknown Album",
            "Album CleanTitle": self._clean_name(
                album.title if album else "Unknown Album",
                colon_replacement,
                slash_replacement,
            ),
            "Album Disambiguation": album_disambiguation,
            "Album Type": album_type,
            "Release Year": str(album.release_year)
            if album and album.release_year
            else "",
            "Medium": track.disc_number or 1,
            "Medium:00": f"{track.disc_number or 1:02d}",
            # Legacy short names
            "medium": track.disc_number or 1,
            "track": track.track_number or 0,
            "track:02d": f"{track.track_number or 0:02d}",
            "disc": track.disc_number or 1,
        }

    # Hey name cleaning - replaces problematic chars with safe alternatives
    # WHY these replacements? Filesystem compatibility across Windows/Mac/Linux
    # "/" -> "-" because "/" is directory separator on Unix
    # ":" -> " -" because ":" is reserved on Windows
    # Multiple spaces collapsed to one for cleaner look
    def _clean_name(
        self,
        name: str,
        colon_replacement: str = " -",
        slash_replacement: str = "-",
    ) -> str:
        """Clean a name for use in filenames.

        Removes or replaces characters that are problematic in filenames
        while keeping the name readable.

        Args:
            name: Name to clean
            colon_replacement: What to replace : with
            slash_replacement: What to replace / with

        Returns:
            Cleaned name
        """
        # Replace problematic characters with safe alternatives
        cleaned = name.replace("/", slash_replacement)
        cleaned = cleaned.replace("\\", slash_replacement)
        cleaned = cleaned.replace(":", colon_replacement)
        cleaned = cleaned.replace("?", "")
        cleaned = cleaned.replace("*", "")
        cleaned = cleaned.replace('"', "'")
        cleaned = cleaned.replace("<", "(")
        cleaned = cleaned.replace(">", ")")
        cleaned = cleaned.replace("|", "-")

        # Remove control characters
        cleaned = re.sub(r"[\x00-\x1f]", "", cleaned)

        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Trim whitespace
        cleaned = cleaned.strip()

        return cleaned

    # Hey future me: File system sanitization - WHY so paranoid about characters?
    # Windows: Can't use < > : " / \ | ? * or chars 0x00-0x1f (control chars)
    # macOS/Linux: Can't use / and NUL, but we sanitize more for cross-platform compatibility
    # Example: "Artist: The Band" becomes "Artist - The Band" so Windows doesn't crash
    # GOTCHA: We split on "/" first to handle path components separately - don't want to sanitize directory separators
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility.

        Args:
            filename: Raw filename

        Returns:
            Sanitized filename
        """
        # Split into path components to handle directories
        parts = filename.split("/")

        # Sanitize each part separately
        sanitized_parts = []
        for part in parts:
            # Replace illegal characters with underscore (except /)
            sanitized = re.sub(self.ILLEGAL_CHARS, "_", part)

            # Replace multiple underscores with single
            sanitized = re.sub(r"_+", "_", sanitized)

            # Remove leading/trailing spaces and dots
            sanitized = sanitized.strip(" .")

            sanitized_parts.append(sanitized)

        # Rejoin with /
        filename = "/".join(sanitized_parts)

        return filename

    # Hey future me: The actual file move operation
    # WHY mkdir with parents=True? Template might create deep paths like "Artist/2023/Album/Disc 1/"
    # WHY handle existing files? Race condition - another process might have created same file
    # CROSS-FS SUPPORT: We now handle EXDEV errors with shutil.move() fallback!
    # rename() is atomic and fast for same-filesystem, but fails across filesystems.
    # shutil.move() does copy+delete which works across filesystems but is slower.
    # UPDATED: Now uses dynamic DB templates if app_settings_service is available!
    async def rename_file(
        self,
        source_path: Path,
        track: Track,
        artist: Artist,
        album: Album | None = None,
    ) -> Path:
        """Rename and move a file based on template.

        Hey future me - this now uses DB templates when AppSettingsService is available!
        If set_app_settings_service() was called, we use generate_filename_async()
        which loads templates from DB. Otherwise falls back to static templates.

        Args:
            source_path: Current file path
            track: Track entity
            artist: Artist entity
            album: Optional album entity

        Returns:
            New file path
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        # Generate new filename - use async method if DB templates available
        extension = source_path.suffix
        if self._app_settings_service is not None:
            relative_path = await self.generate_filename_async(
                track, artist, album, extension
            )
        else:
            relative_path = self.generate_filename(track, artist, album, extension)

        # Construct full destination path
        dest_path = self._settings.storage.music_path / relative_path

        # Create parent directories
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Handle existing file
        if dest_path.exists():
            logger.warning("File already exists: %s", dest_path)
            # Add numeric suffix
            dest_path = self._get_unique_path(dest_path)

        # Move file with cross-filesystem fallback
        # Hey future me - rename() fails with EXDEV error when source and dest are on
        # different filesystems (e.g., Docker volumes, network mounts, different partitions).
        # The fallback uses shutil.move() which does copy+delete automatically for cross-fs.
        # We try rename() first because it's atomic and faster for same-filesystem moves.
        try:
            source_path.rename(dest_path)
        except OSError as e:
            from soulspot.infrastructure.observability.error_formatting import (
                format_oserror_message,
            )

            if e.errno == errno.EXDEV:
                # Cross-filesystem move - fallback to copy+delete via shutil
                logger.info(
                    "Cross-filesystem move detected, using copy+delete fallback: "
                    "%s -> %s",
                    source_path,
                    dest_path,
                )
                shutil.move(str(source_path), str(dest_path))
            else:
                # Re-raise with better error message
                msg = format_oserror_message(
                    e, "move/rename file", source_path, {"destination": str(dest_path)}
                )
                logger.error(msg, exc_info=True)
                raise
        logger.info("Renamed file: %s -> %s", source_path, dest_path)

        return dest_path

    # Yo unique path generator - adds _1, _2, _3 suffix until path is unique
    # WHY needed? Race conditions or multiple downloads of same track
    # Infinite loop protection: unlikely but counter could overflow after 2^31 iterations
    # stem = filename without extension, suffix = extension with dot
    def _get_unique_path(self, path: Path) -> Path:
        """Get a unique path by adding numeric suffix.

        Args:
            path: Desired path

        Returns:
            Unique path
        """
        counter = 1
        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        while path.exists():
            new_name = f"{stem}_{counter}{suffix}"
            path = parent / new_name
            counter += 1

        return path

    # Listen, template validator - checks if all variables in template are supported
    # WHY validate? User typos like "{Arist}" instead of "{Artist}" cause crashes at runtime
    # Formatter.parse() extracts all placeholders from template string
    # field.split(":")[0] handles format specs like "{track:02d}" - takes only variable name
    # Returns False on ANY unsupported variable - fail fast and clear
    def validate_template(self, template: str) -> tuple[bool, list[str]]:
        """Validate a naming template.

        Hey future me - extended to return list of invalid variables!
        This enables better error messages in UI.

        Args:
            template: Template string

        Returns:
            Tuple of (is_valid, list_of_invalid_variables)
        """
        invalid_vars: list[str] = []
        try:
            # Check if all variables in template are supported
            formatter = Formatter()
            field_names = [
                field_name
                for _, field_name, _, _ in formatter.parse(template)
                if field_name is not None
            ]

            # Supported variables (both old and new naming conventions)
            # Aligned with NAMING_VARIABLES in AppSettingsService
            supported = {
                # Legacy variables (backward compatibility)
                "artist",
                "title",
                "album",
                "track_number",
                "disc_number",
                "year",
                "medium",
                "track",
                "track:02d",
                "disc",
                # New standardized variables (Lidarr-compatible)
                "Artist Name",
                "Artist CleanName",
                "Artist Disambiguation",
                "Track Title",
                "Track CleanTitle",
                "Track Number",
                "Track Number:00",
                "Album Title",
                "Album CleanTitle",
                "Album Disambiguation",
                "Album Type",
                "Release Year",
                "Medium",
                "Medium:00",
            }

            for field in field_names:
                # Handle format specs (e.g., track:02d)
                # Keep format spec for special pre-formatted variables like "Track Number:00"
                if field not in supported:
                    # Try without format spec
                    field_base = field.split(":")[0]
                    if field_base not in supported:
                        logger.warning("Unsupported template variable: %s", field)
                        invalid_vars.append(field)

            return len(invalid_vars) == 0, invalid_vars

        except Exception as e:
            logger.exception("Error validating template: %s", e)
            return False, [f"Parse error: {e}"]
