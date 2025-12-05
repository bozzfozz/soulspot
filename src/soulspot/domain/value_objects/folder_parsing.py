"""Regex patterns and parsers for Lidarr-style folder structure.

Hey future me - this parses existing Lidarr libraries! It extracts metadata from folder
and filenames using regex patterns that match Lidarr's naming conventions.

The key patterns:
1. ARTIST FOLDER: Just the artist name (e.g., "Michael Jackson")
2. ALBUM FOLDER: Title (Year) with optional disambiguation (e.g., "Thriller (1982)")
3. TRACK FILE: Track number - Title (e.g., "05 - Billie Jean.flac")
4. MULTI-DISC: Disc-Track - Title (e.g., "01-05 - Billie Jean.flac")
5. VARIOUS ARTISTS: Track - Artist - Title (e.g., "01 - Michael Jackson - Billie Jean.flac")

These patterns handle the most common Lidarr/Plex/Jellyfin naming conventions.
Edge cases (non-standard naming) fall back to simpler extraction.

Usage:
    from soulspot.domain.value_objects.folder_parsing import (
        parse_album_folder,
        parse_track_filename,
        LibraryFolderParser,
    )

    album_info = parse_album_folder("Thriller (1982)")
    track_info = parse_track_filename("05 - Billie Jean.flac")

    parser = LibraryFolderParser(root_path)
    scan_result = parser.scan()
"""

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# REGEX PATTERNS
# =============================================================================

# Artist folder pattern: "Artist Name" or "Artist Name (MusicBrainz UUID)" or "Artist Name (Disambiguation)"
# Examples:
#   "The Beatles" → name="The Beatles", uuid=None, disambiguation=None
#   "The Beatles (112944f7-8971-4b2b-b9d6-891e1dc2a7ff)" → name="The Beatles", uuid="112944f7...", disambiguation=None
#   "Genesis (English rock band)" → name="Genesis", uuid=None, disambiguation="English rock band"
#   "Genesis (b9df73c3-...)" → name="Genesis", uuid="b9df73c3-...", disambiguation=None
# Hey future me - Lidarr uses UUID OR text disambiguation in folder name to disambiguate artists.
# UUID is 36 chars (8-4-4-4-12 hex with hyphens). Anything else in parentheses is disambiguation.
# We extract the CLEAN name for display/search, and store UUID/disambiguation separately!
ARTIST_FOLDER_PATTERN = re.compile(
    r"^(?P<name>.+?)"  # Artist name (non-greedy)
    r"(?:\s*\((?P<paren_content>[^)]+)\))?"  # Optional content in parentheses
    r"$"
)

# UUID pattern to distinguish UUID from text disambiguation
UUID_PATTERN = re.compile(
    r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
)

# Album folder pattern: "Title (Year)" or "Title (Year) (Disambiguation)"
# Examples:
#   "Thriller (1982)" → title="Thriller", year=1982
#   "Bad (1987) (Deluxe Edition)" → title="Bad", year=1987, disambiguation="Deluxe Edition"
#   "Abbey Road" → title="Abbey Road", year=None (no year)
ALBUM_FOLDER_PATTERN = re.compile(
    r"^(?P<title>.+?)"  # Album title (non-greedy to not consume year)
    r"(?:\s*\((?P<year>\d{4})\))?"  # Optional year in parentheses
    r"(?:\s*\((?P<disambiguation>[^)]+)\))?"  # Optional disambiguation
    r"(?:\s*\[(?P<quality>[^\]]+)\])?"  # Optional quality tag [FLAC]
    r"$"
)

# Alternative album folder pattern: "Artist - Album - Year - Title" (Hardcore/Gabber scene style)
# Hey future me - some users have "Angerfist - Album - 2006 - Pissin Razorbladez" format!
# We extract ONLY the album title (last part) and year from this.
# Examples:
#   "Angerfist - Album - 2006 - Pissin Razorbladez" → title="Pissin Razorbladez", year=2006
#   "Neophyte - 2003 - Rockin Insane" → title="Rockin Insane", year=2003
#   "Korsakoff - Album - 2019 - Break Away" → title="Break Away", year=2019
ALBUM_ARTIST_YEAR_TITLE_PATTERN = re.compile(
    r"^.+?"  # Artist name (non-greedy, ignored)
    r"\s*-\s*"  # Separator
    r"(?:Album\s*-\s*)?"  # Optional "Album -" prefix
    r"(?P<year>\d{4})"  # Year (required in this format)
    r"\s*-\s*"  # Separator
    r"(?P<title>.+)"  # Album title (rest of string)
    r"$"
)

# Standard track filename pattern: "NN - Title.ext"
# Examples:
#   "05 - Billie Jean.flac" → track=5, title="Billie Jean"
#   "1 - Track One.mp3" → track=1, title="Track One"
STANDARD_TRACK_PATTERN = re.compile(
    r"^(?P<track>\d{1,3})"  # Track number (1-3 digits)
    r"\s*[-–—]\s*"  # Separator (dash, en-dash, or em-dash)
    r"(?P<title>.+)"  # Track title (rest of filename)
    r"\.(?P<ext>\w+)$"  # File extension
)

# Multi-disc track pattern: "DD-TT - Title.ext" or "DD-TT Title.ext"
# Examples:
#   "01-05 - Billie Jean.flac" → disc=1, track=5, title="Billie Jean"
#   "2-01 - Track One.mp3" → disc=2, track=1, title="Track One"
MULTI_DISC_TRACK_PATTERN = re.compile(
    r"^(?P<disc>\d{1,2})"  # Disc number (1-2 digits)
    r"[-–—]"  # Separator
    r"(?P<track>\d{1,3})"  # Track number (1-3 digits)
    r"\s*[-–—]?\s*"  # Optional separator before title
    r"(?P<title>.+)"  # Track title
    r"\.(?P<ext>\w+)$"  # File extension
)

# Various Artists track pattern: "NN - Artist - Title.ext"
# Examples:
#   "01 - Michael Jackson - Billie Jean.flac" → track=1, artist="Michael Jackson", title="Billie Jean"
#   "05 - Prince - Kiss.mp3" → track=5, artist="Prince", title="Kiss"
VARIOUS_ARTISTS_TRACK_PATTERN = re.compile(
    r"^(?P<track>\d{1,3})"  # Track number
    r"\s*[-–—]\s*"  # First separator
    r"(?P<artist>.+?)"  # Artist name (non-greedy)
    r"\s*[-–—]\s*"  # Second separator
    r"(?P<title>.+)"  # Track title
    r"\.(?P<ext>\w+)$"  # Extension
)

# Disc folder pattern: "Disc N", "CD N", "Disc N: Title"
# Examples:
#   "Disc 1" → disc=1
#   "CD 2" → disc=2
#   "Disc 1 - The Early Years" → disc=1, title="The Early Years"
DISC_FOLDER_PATTERN = re.compile(
    r"^(?:Disc|CD|Disk)\s*(?P<disc>\d{1,2})"  # Disc indicator and number
    r"(?:\s*[-–—:]\s*(?P<title>.+))?$",  # Optional title
    re.IGNORECASE,
)

# Supported audio file extensions (lowercase)
AUDIO_EXTENSIONS = frozenset(
    {
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
        ".wv",
        ".tta",
        # High-resolution
        ".dsf",
        ".dff",
        ".dsd",
        # Other
        ".mpc",
        ".mp4",
        ".webm",
    }
)


# =============================================================================
# PARSED RESULT DATACLASSES
# =============================================================================


@dataclass
class ParsedArtistFolder:
    """Result of parsing an artist folder name.

    Hey future me - artist names come from folder structure like "The Beatles (4d3nxxxx)"
    or "Genesis (English rock band)". We extract:
    - name: Clean artist name without UUID/disambiguation (for display and Spotify search!)
    - uuid: MusicBrainz UUID if present (36-char hex with hyphens)
    - disambiguation: Text disambiguation if present (e.g., "English rock band")
    - raw_name: Original folder name for debugging

    CRITICAL (Dec 2025): Use `name` for Spotify API searches, NOT raw_name!
    """

    name: str
    """Artist name extracted from folder name (without UUID or disambiguation)."""

    uuid: str | None = None
    """Lidarr artist UUID if found in folder name (36-char MusicBrainz format)."""

    disambiguation: str | None = None
    """Text disambiguation if found (e.g., 'English rock band', 'UK band', 'rapper')."""

    raw_name: str = ""
    """Original folder name before parsing."""

    def __post_init__(self) -> None:
        if not self.raw_name:
            self.raw_name = self.name


@dataclass
class ParsedAlbumFolder:
    """Result of parsing an album folder name.

    Hey future me - all fields except title are optional because album folders
    might not include year or disambiguation. title is always set (worst case
    it's the raw folder name).
    """

    title: str
    """Album title extracted from folder name."""

    year: int | None = None
    """Release year (4 digits) if found in folder name."""

    disambiguation: str | None = None
    """Disambiguation text (e.g., "Deluxe Edition") if found."""

    quality: str | None = None
    """Quality tag (e.g., "FLAC") if found in brackets."""

    raw_name: str = ""
    """Original folder name before parsing."""

    def __post_init__(self) -> None:
        if not self.raw_name:
            self.raw_name = self.title


@dataclass
class ParsedTrackFilename:
    """Result of parsing a track filename.

    Hey future me - track_number is always set (defaults to 0 if not parsed).
    title is always set (fallback to filename stem). disc_number defaults to 1.
    artist is only set for VA compilation tracks.
    """

    title: str
    """Track title extracted from filename."""

    track_number: int = 0
    """Track number on the disc (0 if couldn't parse)."""

    disc_number: int = 1
    """Disc number (1 if single disc or couldn't parse)."""

    artist: str | None = None
    """Track artist (only for Various Artists compilations)."""

    extension: str = ""
    """File extension including dot (e.g., ".flac")."""

    raw_name: str = ""
    """Original filename before parsing."""

    @property
    def is_various_artists_format(self) -> bool:
        """Check if this was parsed as a VA track (has artist)."""
        return self.artist is not None


@dataclass
class ScannedArtist:
    """Artist discovered during library scan."""

    name: str
    """Artist name from folder (clean, without UUID or disambiguation text)."""

    path: Path
    """Full path to artist folder."""

    musicbrainz_id: str | None = None
    """MusicBrainz UUID extracted from Lidarr folder name (e.g., from 'Artist (UUID)')."""

    disambiguation: str | None = None
    """Text disambiguation from folder name (e.g., 'English rock band' from 'Genesis (English rock band)')."""

    albums: list["ScannedAlbum"] = field(default_factory=list)
    """Albums found under this artist."""


@dataclass
class ScannedAlbum:
    """Album discovered during library scan."""

    title: str
    """Album title from folder."""

    year: int | None
    """Release year if found."""

    path: Path
    """Full path to album folder."""

    disambiguation: str | None = None
    """Edition/disambiguation info if found."""

    tracks: list["ScannedTrack"] = field(default_factory=list)
    """Tracks found in this album."""

    @property
    def is_multi_disc(self) -> bool:
        """Check if album has tracks from multiple discs."""
        disc_numbers = {t.disc_number for t in self.tracks}
        return len(disc_numbers) > 1


@dataclass
class ScannedTrack:
    """Track discovered during library scan."""

    title: str
    """Track title from filename."""

    track_number: int
    """Track number on disc."""

    disc_number: int
    """Disc number."""

    path: Path
    """Full path to track file."""

    artist: str | None = None
    """Track artist (for VA compilations)."""

    extension: str = ""
    """File extension."""


@dataclass
class LibraryScanResult:
    """Complete result of scanning a Lidarr-organized library."""

    artists: list[ScannedArtist] = field(default_factory=list)
    """All artists found."""

    total_artists: int = 0
    total_albums: int = 0
    total_tracks: int = 0
    skipped_files: int = 0
    parse_errors: list[str] = field(default_factory=list)


# =============================================================================
# PARSING FUNCTIONS
# =============================================================================


def parse_artist_folder(folder_name: str) -> ParsedArtistFolder:
    """Parse artist folder name to extract metadata.

    Handles Lidarr naming: "Artist Name", "Artist Name (UUID)", or "Artist Name (Disambiguation)".
    Hey future me - we extract CLEAN name for Spotify search! UUID/disambiguation stored separately.

    Args:
        folder_name: The artist folder name (not full path).

    Returns:
        ParsedArtistFolder with extracted metadata.

    Examples:
        >>> parse_artist_folder("The Beatles")
        ParsedArtistFolder(name="The Beatles", uuid=None, disambiguation=None, ...)

        >>> parse_artist_folder("The Beatles (112944f7-8971-4b2b-b9d6-891e1dc2a7ff)")
        ParsedArtistFolder(name="The Beatles", uuid="112944f7...", disambiguation=None, ...)

        >>> parse_artist_folder("Genesis (English rock band)")
        ParsedArtistFolder(name="Genesis", uuid=None, disambiguation="English rock band", ...)
    """
    match = ARTIST_FOLDER_PATTERN.match(folder_name.strip())

    if match:
        name = match.group("name").strip()
        paren_content = match.group("paren_content")

        # Determine if parentheses content is UUID or text disambiguation
        uuid = None
        disambiguation = None

        if paren_content:
            if UUID_PATTERN.match(paren_content):
                uuid = paren_content
            else:
                disambiguation = paren_content

        return ParsedArtistFolder(
            name=name,
            uuid=uuid,
            disambiguation=disambiguation,
            raw_name=folder_name,
        )

    # Fallback: use entire folder name as artist name
    return ParsedArtistFolder(
        name=folder_name.strip(),
        raw_name=folder_name,
    )


def parse_album_folder(folder_name: str) -> ParsedAlbumFolder:
    """Parse album folder name to extract metadata.

    Handles multiple naming conventions:
    1. Standard Lidarr: "Title (Year)" with optional disambiguation
    2. Hardcore/Gabber style: "Artist - Album - Year - Title" (extracts only title + year)

    Args:
        folder_name: The album folder name (not full path).

    Returns:
        ParsedAlbumFolder with extracted metadata.

    Examples:
        >>> parse_album_folder("Thriller (1982)")
        ParsedAlbumFolder(title="Thriller", year=1982, ...)

        >>> parse_album_folder("Bad (1987) (Deluxe Edition)")
        ParsedAlbumFolder(title="Bad", year=1987, disambiguation="Deluxe Edition", ...)

        >>> parse_album_folder("Angerfist - Album - 2006 - Pissin Razorbladez")
        ParsedAlbumFolder(title="Pissin Razorbladez", year=2006, ...)

        >>> parse_album_folder("Some Album [FLAC]")
        ParsedAlbumFolder(title="Some Album", quality="FLAC", ...)
    """
    folder_name = folder_name.strip()

    # Hey future me - try the "Artist - [Album -] Year - Title" pattern FIRST!
    # This handles "Angerfist - Album - 2006 - Pissin Razorbladez" style naming.
    # We detect this by checking for "- YYYY -" anywhere in the string.
    alt_match = ALBUM_ARTIST_YEAR_TITLE_PATTERN.match(folder_name)
    if alt_match:
        return ParsedAlbumFolder(
            title=alt_match.group("title").strip(),
            year=int(alt_match.group("year")),
            raw_name=folder_name,
        )

    # Try standard Lidarr pattern: "Title (Year)"
    match = ALBUM_FOLDER_PATTERN.match(folder_name)

    if match:
        year_str = match.group("year")
        return ParsedAlbumFolder(
            title=match.group("title").strip(),
            year=int(year_str) if year_str else None,
            disambiguation=match.group("disambiguation"),
            quality=match.group("quality"),
            raw_name=folder_name,
        )

    # Fallback: use entire folder name as title
    return ParsedAlbumFolder(
        title=folder_name.strip(),
        raw_name=folder_name,
    )


def parse_track_filename(filename: str) -> ParsedTrackFilename:
    """Parse track filename to extract metadata.

    Tries patterns in order: multi-disc → VA → standard → fallback.

    Args:
        filename: The track filename (with extension, without path).

    Returns:
        ParsedTrackFilename with extracted metadata.

    Examples:
        >>> parse_track_filename("05 - Billie Jean.flac")
        ParsedTrackFilename(title="Billie Jean", track_number=5, ...)

        >>> parse_track_filename("01-05 - Track.mp3")
        ParsedTrackFilename(title="Track", track_number=5, disc_number=1, ...)

        >>> parse_track_filename("01 - Artist - Title.flac")
        ParsedTrackFilename(title="Title", artist="Artist", track_number=1, ...)
    """
    filename = filename.strip()

    # Try multi-disc pattern first (most specific)
    match = MULTI_DISC_TRACK_PATTERN.match(filename)
    if match:
        return ParsedTrackFilename(
            title=match.group("title").strip(),
            track_number=int(match.group("track")),
            disc_number=int(match.group("disc")),
            extension=f".{match.group('ext').lower()}",
            raw_name=filename,
        )

    # Try Various Artists pattern (has two separators)
    match = VARIOUS_ARTISTS_TRACK_PATTERN.match(filename)
    if match:
        return ParsedTrackFilename(
            title=match.group("title").strip(),
            track_number=int(match.group("track")),
            artist=match.group("artist").strip(),
            extension=f".{match.group('ext').lower()}",
            raw_name=filename,
        )

    # Try standard pattern
    match = STANDARD_TRACK_PATTERN.match(filename)
    if match:
        return ParsedTrackFilename(
            title=match.group("title").strip(),
            track_number=int(match.group("track")),
            extension=f".{match.group('ext').lower()}",
            raw_name=filename,
        )

    # Fallback: extract what we can from filename
    path = Path(filename)
    ext = path.suffix.lower() if path.suffix else ""
    stem = path.stem

    # Try to extract track number from start of filename
    track_match = re.match(r"^(\d{1,3})", stem)
    track_num = int(track_match.group(1)) if track_match else 0

    # Remove track number and separators from title
    title = stem
    if track_match:
        title = stem[len(track_match.group(0)) :].lstrip(" -–—.")

    return ParsedTrackFilename(
        title=title if title else stem,
        track_number=track_num,
        extension=ext,
        raw_name=filename,
    )


def is_disc_folder(folder_name: str) -> tuple[bool, int | None]:
    """Check if a folder name indicates a disc subfolder.

    Args:
        folder_name: The folder name to check.

    Returns:
        Tuple of (is_disc_folder, disc_number_or_none).

    Examples:
        >>> is_disc_folder("Disc 1")
        (True, 1)
        >>> is_disc_folder("CD 2")
        (True, 2)
        >>> is_disc_folder("Songs")
        (False, None)
    """
    match = DISC_FOLDER_PATTERN.match(folder_name.strip())
    if match:
        return True, int(match.group("disc"))
    return False, None


def is_audio_file(filename: str) -> bool:
    """Check if a filename has a supported audio extension.

    Args:
        filename: Filename to check.

    Returns:
        True if the file has a supported audio extension.
    """
    ext = Path(filename).suffix.lower()
    return ext in AUDIO_EXTENSIONS


# =============================================================================
# LIBRARY FOLDER PARSER
# =============================================================================


class LibraryFolderParser:
    """Parser for scanning Lidarr-organized music libraries.

    Hey future me - this walks the folder structure and extracts metadata using
    the regex patterns above. It handles:
    - Standard structure: /Artist/Album (Year)/Track.flac
    - Multi-disc with prefix: /Artist/Album (Year)/01-01 - Track.flac
    - Multi-disc with subfolders: /Artist/Album (Year)/Disc 1/01 - Track.flac
    - Various Artists: /Various Artists/Compilation/01 - Artist - Track.flac

    Usage:
        parser = LibraryFolderParser(Path("/music"))
        result = parser.scan()
        for artist in result.artists:
            print(f"Found artist: {artist.name}")
    """

    def __init__(self, root_path: Path) -> None:
        """Initialize parser with root library path.

        Args:
            root_path: Path to the root of the music library.
        """
        self.root_path = root_path.resolve()

    def scan(self) -> LibraryScanResult:
        """Scan the library and extract metadata.

        Returns:
            LibraryScanResult with all discovered artists, albums, and tracks.
        """
        result = LibraryScanResult()

        if not self.root_path.exists():
            logger.warning(f"Library path does not exist: {self.root_path}")
            return result

        if not self.root_path.is_dir():
            logger.warning(f"Library path is not a directory: {self.root_path}")
            return result

        # Scan artist folders (top level)
        for artist_path in self._iter_artist_folders():
            try:
                artist = self._scan_artist(artist_path)
                result.artists.append(artist)
                result.total_artists += 1
                result.total_albums += len(artist.albums)
                result.total_tracks += sum(len(a.tracks) for a in artist.albums)
            except Exception as e:
                logger.warning(f"Error scanning artist folder {artist_path}: {e}")
                result.parse_errors.append(f"{artist_path}: {e}")

        logger.info(
            f"Library scan complete: {result.total_artists} artists, "
            f"{result.total_albums} albums, {result.total_tracks} tracks"
        )
        return result

    def _iter_artist_folders(self) -> Iterator[Path]:
        """Iterate over artist folders (top-level directories).

        Yields:
            Path to each artist folder.
        """
        try:
            for item in self.root_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    yield item
        except PermissionError as e:
            logger.warning(f"Permission denied accessing {self.root_path}: {e}")

    def _scan_artist(self, artist_path: Path) -> ScannedArtist:
        """Scan an artist folder and its albums.

        Hey future me - use parse_artist_folder() to extract clean name
        from folder (which might be "Artist Name (UUID)" or "Artist Name (Disambiguation)").
        Clean name is used for Spotify search, disambiguation is stored for display!

        Args:
            artist_path: Path to the artist folder.

        Returns:
            ScannedArtist with discovered albums.
        """
        parsed = parse_artist_folder(artist_path.name)

        artist = ScannedArtist(
            name=parsed.name,  # Clean name without UUID/disambiguation for Spotify search!
            path=artist_path,
            musicbrainz_id=parsed.uuid,  # Preserve UUID for Lidarr compatibility
            disambiguation=parsed.disambiguation,  # Text disambiguation for display
        )

        # Scan album folders (second level)
        try:
            for item in artist_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    album = self._scan_album(item)
                    if album.tracks:  # Only add albums with tracks
                        artist.albums.append(album)
        except PermissionError as e:
            logger.warning(f"Permission denied accessing {artist_path}: {e}")

        return artist

    def _scan_album(self, album_path: Path) -> ScannedAlbum:
        """Scan an album folder and its tracks.

        Handles both flat structure and disc subfolders.

        Args:
            album_path: Path to the album folder.

        Returns:
            ScannedAlbum with discovered tracks.
        """
        parsed = parse_album_folder(album_path.name)

        album = ScannedAlbum(
            title=parsed.title,
            year=parsed.year,
            path=album_path,
            disambiguation=parsed.disambiguation,
        )

        # Scan for tracks - both direct files and disc subfolders
        try:
            for item in album_path.iterdir():
                if item.is_file() and is_audio_file(item.name):
                    # Direct track file
                    track = self._parse_track_file(item, disc_number=1)
                    album.tracks.append(track)

                elif item.is_dir():
                    # Check if it's a disc subfolder
                    is_disc, disc_num = is_disc_folder(item.name)
                    if is_disc and disc_num is not None:
                        # Scan disc subfolder
                        for track_file in item.iterdir():
                            if track_file.is_file() and is_audio_file(track_file.name):
                                track = self._parse_track_file(
                                    track_file, disc_number=disc_num
                                )
                                album.tracks.append(track)

        except PermissionError as e:
            logger.warning(f"Permission denied accessing {album_path}: {e}")

        # Sort tracks by disc and track number
        album.tracks.sort(key=lambda t: (t.disc_number, t.track_number))

        return album

    def _parse_track_file(self, track_path: Path, disc_number: int = 1) -> ScannedTrack:
        """Parse a track file and create ScannedTrack.

        Args:
            track_path: Path to the track file.
            disc_number: Disc number (overridden if parsed from filename).

        Returns:
            ScannedTrack with extracted metadata.
        """
        parsed = parse_track_filename(track_path.name)

        # Use parsed disc number if found, otherwise use provided
        actual_disc = parsed.disc_number if parsed.disc_number > 1 else disc_number

        return ScannedTrack(
            title=parsed.title,
            track_number=parsed.track_number,
            disc_number=actual_disc,
            path=track_path,
            artist=parsed.artist,
            extension=parsed.extension,
        )
