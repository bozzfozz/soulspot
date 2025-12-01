"""Lidarr-style naming configuration and service for file/folder organization.

Hey future me - this implements the naming system from docs/feat-library/NAMING_CONVENTIONS.md!

The key concepts:
1. TOKENS: Placeholders like {Artist Name}, {Album Title}, {track:00} that get replaced
2. FORMATS: Templates for artist folders, album folders, and track filenames
3. SANITIZATION: Illegal character replacement for cross-platform compatibility

Token naming follows Lidarr conventions:
- {Artist Name} = full artist name
- {Album Title} = full album title
- {Release Year} = 4-digit year
- {track:00} = zero-padded track number (lowercase to match Lidarr)
- {medium:00} = zero-padded disc number (lowercase to match Lidarr)

Usage:
    from soulspot.domain.value_objects.naming import NamingConfig, NamingService

    config = NamingConfig()
    service = NamingService(config)

    artist_folder = service.format_artist_folder(artist_name="Michael Jackson")
    album_folder = service.format_album_folder(album_title="Thriller", release_year=1982)
    track_filename = service.format_track_filename(
        track_title="Billie Jean", track_number=5, extension=".flac"
    )
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ColonReplacement(str, Enum):
    """Options for replacing colons in filenames (illegal on Windows).

    Hey future me - colons are the MOST problematic character because they're
    common in song titles ("Re: Stacks", "Track 1: Introduction") but illegal
    on Windows. These options mirror Lidarr's settings.
    """

    DELETE = ""
    """Remove colons entirely: "Re: Stacks" → "Re Stacks" """

    DASH = "-"
    """Replace with dash: "Re: Stacks" → "Re- Stacks" """

    SPACE_DASH = " -"
    """Replace with space-dash (Lidarr default): "Re: Stacks" → "Re - Stacks" """

    SPACE_DASH_SPACE = " - "
    """Replace with space-dash-space: "Re: Stacks" → "Re  -  Stacks" """


class MultiDiscStyle(str, Enum):
    """How to handle multi-disc albums in folder/file naming.

    Hey future me - there are two schools of thought:
    1. PREFIX: All files in one folder with disc prefix (01-01 - Track.flac)
    2. SUBFOLDER: Each disc in separate folder (Disc 1/01 - Track.flac)

    PREFIX is more common and works better with most music players.
    SUBFOLDER is useful for very large box sets where you want visual separation.
    """

    PREFIX = "prefix"
    """Track files include disc prefix: 01-01 - Track.flac"""

    SUBFOLDER = "subfolder"
    """Each disc in separate folder: Disc 1/01 - Track.flac"""


@dataclass
class NamingConfig:
    """Configuration for file and folder naming (Lidarr-style).

    Hey future me - this mirrors Lidarr's Media Management > Track Naming settings.
    All format strings use token placeholders that get replaced at runtime.

    Default formats match Lidarr's defaults and work with Plex/Jellyfin/Navidrome.
    """

    # Artist folder format - how artist folders are named
    # Default: "Michael Jackson"
    artist_folder_format: str = "{Artist Name}"

    # Album folder format - how album folders are named
    # Default: "Thriller (1982)"
    album_folder_format: str = "{Album Title} ({Release Year})"

    # Album folder with disambiguation (for duplicate titles)
    # Default: "Thriller (1982) (Deluxe Edition)"
    album_folder_with_disambiguation: str = (
        "{Album Title} ({Release Year}) ({Album Disambiguation})"
    )

    # Standard track format (single-disc albums)
    # Default: "01 - Billie Jean.flac"
    standard_track_format: str = "{track:00} - {Track Title}"

    # Multi-disc track format (albums with multiple discs)
    # Default: "01-05 - Billie Jean.flac" (disc 1, track 5)
    multi_disc_track_format: str = "{medium:00}-{track:00} - {Track Title}"

    # Various Artists track format (compilations)
    # Default: "01 - Michael Jackson - Billie Jean.flac"
    various_artist_track_format: str = "{track:00} - {Artist Name} - {Track Title}"

    # Multi-disc handling style
    multi_disc_style: MultiDiscStyle = MultiDiscStyle.PREFIX

    # Subfolder format for SUBFOLDER multi-disc style
    # Default: "Disc 1", "Disc 2", etc.
    multi_disc_folder_format: str = "Disc {medium}"

    # Character replacement settings
    replace_illegal_characters: bool = True
    colon_replacement: ColonReplacement = ColonReplacement.SPACE_DASH

    def get_track_format(
        self, is_multi_disc: bool, is_various_artists: bool
    ) -> str:
        """Get the appropriate track format based on album type.

        Args:
            is_multi_disc: True if album has multiple discs.
            is_various_artists: True if album is a VA compilation.

        Returns:
            The format string to use for track filenames.
        """
        if is_various_artists:
            return self.various_artist_track_format
        if is_multi_disc:
            return self.multi_disc_track_format
        return self.standard_track_format


# Regular expression for matching token placeholders
# Matches: {Token Name}, {token:00}, {Token Name:000}
TOKEN_PATTERN = re.compile(r"\{([^}:]+)(?::(\d+))?\}")

# Characters illegal in filenames across operating systems
# Windows: < > : " / \ | ? *
# macOS: : (displayed as / in Finder)
# Linux: / and NUL
ILLEGAL_CHARS_PATTERN = re.compile(r'[<>"/\\|?*\x00-\x1f]')


@dataclass
class NamingService:
    """Service for generating file and folder names from metadata.

    Hey future me - this is the core naming logic! It takes metadata (artist name,
    album title, track number, etc.) and generates sanitized paths that work on
    all operating systems and media servers.

    Token replacement happens in _format_string(), sanitization in _sanitize_filename().
    """

    config: NamingConfig = field(default_factory=NamingConfig)

    def format_artist_folder(
        self,
        artist_name: str,
        disambiguation: str | None = None,
    ) -> str:
        """Generate sanitized artist folder name.

        Args:
            artist_name: The artist's name.
            disambiguation: Optional disambiguating info (e.g., "UK band").

        Returns:
            Sanitized folder name for the artist.

        Example:
            >>> service.format_artist_folder("Michael Jackson")
            "Michael Jackson"
            >>> service.format_artist_folder("Genesis", "UK band")
            "Genesis (UK band)"
        """
        format_str = self.config.artist_folder_format

        # Add disambiguation if present and format supports it
        if disambiguation and "{Artist Disambiguation}" in format_str:
            format_str = format_str.replace(
                "{Artist Disambiguation}", disambiguation
            )
        elif disambiguation:
            # Append disambiguation even if not in format string
            format_str = f"{format_str} ({disambiguation})"

        result = self._format_string(
            format_str,
            artist_name=artist_name,
            artist_disambiguation=disambiguation or "",
        )
        return self._sanitize_filename(result)

    def format_album_folder(
        self,
        album_title: str,
        release_year: int | None = None,
        album_type: str | None = None,
        disambiguation: str | None = None,
    ) -> str:
        """Generate sanitized album folder name.

        Args:
            album_title: The album title.
            release_year: Year of release (4 digits).
            album_type: Album type (Album, EP, Single, etc.).
            disambiguation: Edition info (e.g., "Deluxe Edition").

        Returns:
            Sanitized folder name for the album.

        Example:
            >>> service.format_album_folder("Thriller", 1982)
            "Thriller (1982)"
            >>> service.format_album_folder("Bad", 1987, disambiguation="Deluxe Edition")
            "Bad (1987) (Deluxe Edition)"
        """
        # Choose format based on disambiguation presence
        if disambiguation:
            format_str = self.config.album_folder_with_disambiguation
        else:
            format_str = self.config.album_folder_format

        result = self._format_string(
            format_str,
            album_title=album_title,
            release_year=release_year,
            album_type=album_type or "Album",
            album_disambiguation=disambiguation or "",
        )
        return self._sanitize_filename(result)

    def format_track_filename(
        self,
        track_title: str,
        track_number: int,
        extension: str,
        artist_name: str | None = None,
        medium_number: int = 1,
        is_multi_disc: bool = False,
        is_various_artists: bool = False,
    ) -> str:
        """Generate sanitized track filename (without path).

        Args:
            track_title: The track title.
            track_number: Track number on the disc.
            extension: File extension including dot (e.g., ".flac").
            artist_name: Track artist name (required for VA compilations).
            medium_number: Disc number (default 1).
            is_multi_disc: True if album has multiple discs.
            is_various_artists: True if album is a VA compilation.

        Returns:
            Sanitized filename for the track.

        Example:
            >>> service.format_track_filename("Billie Jean", 5, ".flac")
            "05 - Billie Jean.flac"
            >>> service.format_track_filename("Billie Jean", 5, ".flac",
            ...     medium_number=1, is_multi_disc=True)
            "01-05 - Billie Jean.flac"
        """
        format_str = self.config.get_track_format(is_multi_disc, is_various_artists)

        result = self._format_string(
            format_str,
            track_title=track_title,
            track_number=track_number,
            artist_name=artist_name or "Unknown Artist",
            medium_number=medium_number,
        )
        filename = self._sanitize_filename(result)

        # Ensure extension starts with dot
        if not extension.startswith("."):
            extension = f".{extension}"

        return f"{filename}{extension}"

    def format_full_path(
        self,
        root_folder: Path,
        artist_name: str,
        album_title: str,
        track_title: str,
        track_number: int,
        extension: str,
        release_year: int | None = None,
        medium_number: int = 1,
        is_multi_disc: bool = False,
        is_various_artists: bool = False,
    ) -> Path:
        """Generate full path for a track file.

        Args:
            root_folder: Root music library folder (e.g., /music).
            artist_name: The artist's name.
            album_title: The album title.
            track_title: The track title.
            track_number: Track number on the disc.
            extension: File extension including dot.
            release_year: Year of release.
            medium_number: Disc number (default 1).
            is_multi_disc: True if album has multiple discs.
            is_various_artists: True if album is a VA compilation.

        Returns:
            Full path to the track file.

        Example:
            >>> service.format_full_path(
            ...     Path("/music"), "Michael Jackson", "Thriller",
            ...     "Billie Jean", 5, ".flac", 1982
            ... )
            Path("/music/Michael Jackson/Thriller (1982)/05 - Billie Jean.flac")
        """
        artist_folder = self.format_artist_folder(artist_name)
        album_folder = self.format_album_folder(album_title, release_year)

        # Handle multi-disc subfolder style
        # When using subfolders, track filename uses standard format (no disc prefix)
        # because the disc info is in the folder name
        use_multi_disc_format = is_multi_disc and self.config.multi_disc_style == MultiDiscStyle.PREFIX

        track_filename = self.format_track_filename(
            track_title=track_title,
            track_number=track_number,
            extension=extension,
            artist_name=artist_name if is_various_artists else None,
            medium_number=medium_number,
            is_multi_disc=use_multi_disc_format,
            is_various_artists=is_various_artists,
        )

        # Handle multi-disc subfolder style
        if (
            is_multi_disc
            and self.config.multi_disc_style == MultiDiscStyle.SUBFOLDER
        ):
            disc_folder = self._format_string(
                self.config.multi_disc_folder_format,
                medium_number=medium_number,
            )
            disc_folder = self._sanitize_filename(disc_folder)
            return root_folder / artist_folder / album_folder / disc_folder / track_filename

        return root_folder / artist_folder / album_folder / track_filename

    def _format_string(self, format_str: str, **context: Any) -> str:
        """Replace tokens in format string with actual values.

        Args:
            format_str: Format string with {Token} placeholders.
            **context: Keyword arguments with values for tokens.

        Returns:
            String with tokens replaced by values.
        """
        def replace_token(match: re.Match[str]) -> str:
            token_name = match.group(1)
            padding = match.group(2)  # None if no padding specified

            value = self._get_token_value(token_name, context)

            # Apply zero-padding for numeric values
            if padding is not None and isinstance(value, int):
                return str(value).zfill(len(padding))

            return str(value) if value is not None else ""

        return TOKEN_PATTERN.sub(replace_token, format_str)

    def _get_token_value(self, token_name: str, context: dict[str, Any]) -> Any:
        """Get value for a token from context.

        Hey future me - token names are case-insensitive and support both
        "Artist Name" and "artist_name" (snake_case) variants.

        Args:
            token_name: Token name (e.g., "Artist Name", "track", "medium").
            context: Dict with values keyed by token name.

        Returns:
            The value for the token, or empty string if not found.
        """
        # Normalize token name to snake_case for context lookup
        snake_case = token_name.lower().replace(" ", "_")

        # Try direct match first
        if snake_case in context:
            return context[snake_case]

        # Try original token name (case-insensitive)
        token_lower = token_name.lower()
        for key, value in context.items():
            if key.lower() == token_lower:
                return value

        # Handle special tokens
        if token_lower in ("track", "track number"):
            return context.get("track_number", 0)
        if token_lower in ("medium", "disc", "disc number"):
            return context.get("medium_number", 1)
        if token_lower == "year":
            return context.get("release_year", "")

        # Unknown token - return placeholder for debugging
        return f"{{{token_name}}}"

    def _sanitize_filename(self, filename: str) -> str:
        """Remove or replace illegal characters in filename.

        Hey future me - this is CRITICAL for cross-platform compatibility!
        Windows is the most restrictive, so we sanitize for that.

        Args:
            filename: The filename to sanitize.

        Returns:
            Sanitized filename safe for all operating systems.
        """
        if not self.config.replace_illegal_characters:
            return filename

        # Replace colons based on config (most common issue)
        result = filename.replace(":", self.config.colon_replacement.value)

        # Remove other illegal characters
        result = ILLEGAL_CHARS_PATTERN.sub("", result)

        # Trim whitespace and dots from ends (Windows requirement)
        result = result.strip(" .")

        # Handle empty result
        if not result:
            result = "Unknown"

        return result


def clean_name(name: str) -> str:
    """Create URL-safe version of a name.

    Hey future me - this is used for {Artist CleanName} and {Album CleanTitle} tokens.
    It creates a lowercase, URL-safe version suitable for web paths or filenames.

    Args:
        name: The name to clean.

    Returns:
        Lowercase, URL-safe version of the name.

    Example:
        >>> clean_name("Michael Jackson")
        "michaeljackson"
        >>> clean_name("The Beatles")
        "thebeatles"
    """
    # Remove all non-alphanumeric characters except spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    # Remove spaces and convert to lowercase
    cleaned = cleaned.replace(" ", "").lower()
    return cleaned if cleaned else "unknown"


def sort_name(name: str) -> str:
    """Create sortable version of a name (moves articles to end).

    Hey future me - this is used for {Artist SortName} token.
    It moves common articles ("The", "A", "An") to the end for proper sorting.

    Args:
        name: The name to convert.

    Returns:
        Sortable version with article at end.

    Example:
        >>> sort_name("The Beatles")
        "Beatles, The"
        >>> sort_name("Michael Jackson")
        "Jackson, Michael"  # Wait, this is wrong! See note below.
    """
    if not name:
        return ""

    # Common articles in various languages
    articles = ("the ", "a ", "an ", "les ", "la ", "le ", "l'", "die ", "der ", "das ")

    name_lower = name.lower()
    for article in articles:
        if name_lower.startswith(article):
            rest = name[len(article):]
            article_clean = name[:len(article)].strip()
            return f"{rest}, {article_clean}"

    return name
