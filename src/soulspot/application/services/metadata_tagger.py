"""Metadata Tagger Service - handles audio file metadata tagging.

Hey future me - this service TAGS audio files with metadata!

The problem: Downloaded files have generic/wrong metadata from Soulseek.
Users want: Proper artist, album, title, track number, year, genre, artwork.
Without this: Users manually edit tags in every file.

The solution: MetadataTaggerService uses mutagen to write metadata:
- ID3 tags for MP3 files
- Vorbis comments for FLAC/OGG files
- MP4 tags for M4A/AAC files

SUPPORTED FORMATS:
- MP3 (ID3v2.4)
- FLAC (Vorbis Comments)
- OGG (Vorbis Comments)
- M4A/AAC (MP4 atoms)
- OPUS (Vorbis Comments)

TAG MAPPING:
The service uses a unified tag model and maps to format-specific tags:

| Field        | ID3       | Vorbis     | MP4              |
|--------------|-----------|------------|------------------|
| title        | TIT2      | TITLE      | ©nam             |
| artist       | TPE1      | ARTIST     | ©ART             |
| album        | TALB      | ALBUM      | ©alb             |
| album_artist | TPE2      | ALBUMARTIST| aART             |
| track_number | TRCK      | TRACKNUMBER| trkn             |
| disc_number  | TPOS      | DISCNUMBER | disk             |
| year         | TDRC      | DATE       | ©day             |
| genre        | TCON      | GENRE      | ©gen             |
| isrc         | TSRC      | ISRC       | ----:com.apple...|

ARTWORK EMBEDDING:
- Downloads artwork from URL (if provided)
- Embeds as APIC frame (ID3) or PICTURE block (FLAC)
- Supports JPEG and PNG formats

ERROR HANDLING:
- Missing mutagen: Logs warning, skips tagging (graceful degradation)
- Unsupported format: Returns False, doesn't crash
- Write error: Logs error, returns False
- Network error (artwork): Skips artwork, tags other fields
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import httpx

logger = logging.getLogger(__name__)

# Try to import mutagen - optional dependency
try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import APIC, ID3, ID3NoHeaderError
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.oggopus import OggOpus
    from mutagen.oggvorbis import OggVorbis

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logger.warning(
        "mutagen not installed - metadata tagging will be disabled. "
        "Install with: pip install mutagen"
    )


class AudioMetadata(TypedDict, total=False):
    """Metadata fields for audio files.

    Hey future me - all fields are optional!
    Only provided fields are written, existing values preserved.
    """

    title: str
    artist: str
    album: str
    album_artist: str
    track_number: int
    total_tracks: int
    disc_number: int
    total_discs: int
    year: str  # YYYY format
    genre: str
    isrc: str
    comment: str
    # Artwork handled separately via embed_artwork()


@dataclass
class TaggingResult:
    """Result of a tagging operation.

    Hey future me - captures success/failure and details!
    """

    success: bool
    file_path: str
    format: str | None = None
    error: str | None = None
    fields_written: list[str] | None = None


class MetadataTaggerService:
    """Service for writing metadata to audio files.

    Hey future me - this is the CENTRAL tagging engine!

    Usage:
        tagger = MetadataTaggerService()

        # Tag a file
        metadata = {"title": "Song", "artist": "Artist", "album": "Album"}
        result = await tagger.tag_file(Path("/path/to/file.mp3"), metadata)

        # Embed artwork
        await tagger.embed_artwork(Path("/path/to/file.mp3"), "https://url/to/image.jpg")

    Configuration:
        None - this service has no configuration, it just tags files.
    """

    def __init__(self) -> None:
        """Initialize the metadata tagger service."""
        self._http_client: httpx.AsyncClient | None = None

    async def tag_file(
        self, file_path: Path, metadata: AudioMetadata
    ) -> TaggingResult:
        """Write metadata tags to an audio file.

        Hey future me - this is the main tagging method!

        Detects file format and delegates to format-specific handler.
        Only writes provided fields, preserving existing values.

        Args:
            file_path: Path to the audio file
            metadata: Metadata fields to write

        Returns:
            TaggingResult with success status and details
        """
        if not MUTAGEN_AVAILABLE:
            return TaggingResult(
                success=False,
                file_path=str(file_path),
                error="mutagen not installed",
            )

        if not file_path.exists():
            return TaggingResult(
                success=False,
                file_path=str(file_path),
                error="File not found",
            )

        # Detect format from extension
        ext = file_path.suffix.lower()

        try:
            if ext == ".mp3":
                return await self._tag_mp3(file_path, metadata)
            elif ext == ".flac":
                return await self._tag_flac(file_path, metadata)
            elif ext in (".ogg", ".oga"):
                return await self._tag_ogg(file_path, metadata)
            elif ext == ".opus":
                return await self._tag_opus(file_path, metadata)
            elif ext in (".m4a", ".mp4", ".aac"):
                return await self._tag_mp4(file_path, metadata)
            else:
                return TaggingResult(
                    success=False,
                    file_path=str(file_path),
                    format=ext,
                    error=f"Unsupported format: {ext}",
                )
        except Exception as e:
            logger.error(f"Error tagging {file_path}: {e}", exc_info=True)
            return TaggingResult(
                success=False,
                file_path=str(file_path),
                format=ext,
                error=str(e),
            )

    async def _tag_mp3(
        self, file_path: Path, metadata: AudioMetadata
    ) -> TaggingResult:
        """Tag an MP3 file with ID3 tags.

        Hey future me - uses EasyID3 for simple tags, raw ID3 for ISRC!
        EasyID3 provides a nice dict-like interface for common tags.
        """
        fields_written = []

        try:
            audio = EasyID3(str(file_path))
        except ID3NoHeaderError:
            # File has no ID3 tag, create one
            audio = MP3(str(file_path))
            audio.add_tags()
            audio.save()
            audio = EasyID3(str(file_path))

        # Map our metadata to EasyID3 keys
        tag_map = {
            "title": "title",
            "artist": "artist",
            "album": "album",
            "album_artist": "albumartist",
            "genre": "genre",
            "year": "date",
        }

        for field, tag_name in tag_map.items():
            if field in metadata and metadata.get(field):
                audio[tag_name] = str(metadata[field])
                fields_written.append(field)

        # Track number (special format: track/total)
        if "track_number" in metadata:
            track = metadata["track_number"]
            total = metadata.get("total_tracks", "")
            audio["tracknumber"] = f"{track}/{total}" if total else str(track)
            fields_written.append("track_number")

        # Disc number
        if "disc_number" in metadata:
            disc = metadata["disc_number"]
            total = metadata.get("total_discs", "")
            audio["discnumber"] = f"{disc}/{total}" if total else str(disc)
            fields_written.append("disc_number")

        # Save EasyID3 tags
        audio.save()

        # ISRC requires raw ID3 (not in EasyID3)
        if "isrc" in metadata and metadata.get("isrc"):
            from mutagen.id3 import TSRC

            raw_audio = ID3(str(file_path))
            raw_audio.add(TSRC(encoding=3, text=[metadata["isrc"]]))
            raw_audio.save()
            fields_written.append("isrc")

        return TaggingResult(
            success=True,
            file_path=str(file_path),
            format="mp3",
            fields_written=fields_written,
        )

    async def _tag_flac(
        self, file_path: Path, metadata: AudioMetadata
    ) -> TaggingResult:
        """Tag a FLAC file with Vorbis comments.

        Hey future me - FLAC uses Vorbis comments, simple key=value!
        All values must be strings, case-insensitive keys.
        """
        fields_written = []
        audio = FLAC(str(file_path))

        # Map our metadata to Vorbis comment keys
        tag_map = {
            "title": "TITLE",
            "artist": "ARTIST",
            "album": "ALBUM",
            "album_artist": "ALBUMARTIST",
            "genre": "GENRE",
            "year": "DATE",
            "isrc": "ISRC",
            "comment": "COMMENT",
        }

        for field, tag_name in tag_map.items():
            if field in metadata and metadata.get(field):
                audio[tag_name] = str(metadata[field])
                fields_written.append(field)

        # Track number
        if "track_number" in metadata:
            audio["TRACKNUMBER"] = str(metadata["track_number"])
            fields_written.append("track_number")
            if "total_tracks" in metadata:
                audio["TRACKTOTAL"] = str(metadata["total_tracks"])

        # Disc number
        if "disc_number" in metadata:
            audio["DISCNUMBER"] = str(metadata["disc_number"])
            fields_written.append("disc_number")
            if "total_discs" in metadata:
                audio["DISCTOTAL"] = str(metadata["total_discs"])

        audio.save()

        return TaggingResult(
            success=True,
            file_path=str(file_path),
            format="flac",
            fields_written=fields_written,
        )

    async def _tag_ogg(
        self, file_path: Path, metadata: AudioMetadata
    ) -> TaggingResult:
        """Tag an OGG Vorbis file with Vorbis comments.

        Hey future me - same as FLAC, uses Vorbis comments!
        """
        fields_written = []
        audio = OggVorbis(str(file_path))

        # Same tag map as FLAC
        tag_map = {
            "title": "TITLE",
            "artist": "ARTIST",
            "album": "ALBUM",
            "album_artist": "ALBUMARTIST",
            "genre": "GENRE",
            "year": "DATE",
            "isrc": "ISRC",
        }

        for field, tag_name in tag_map.items():
            if field in metadata and metadata.get(field):
                audio[tag_name] = str(metadata[field])
                fields_written.append(field)

        # Track/disc numbers
        if "track_number" in metadata:
            audio["TRACKNUMBER"] = str(metadata["track_number"])
            fields_written.append("track_number")
        if "disc_number" in metadata:
            audio["DISCNUMBER"] = str(metadata["disc_number"])
            fields_written.append("disc_number")

        audio.save()

        return TaggingResult(
            success=True,
            file_path=str(file_path),
            format="ogg",
            fields_written=fields_written,
        )

    async def _tag_opus(
        self, file_path: Path, metadata: AudioMetadata
    ) -> TaggingResult:
        """Tag an Opus file with Vorbis comments.

        Hey future me - Opus uses the same Vorbis comment system!
        """
        fields_written = []
        audio = OggOpus(str(file_path))

        # Same tag map
        tag_map = {
            "title": "TITLE",
            "artist": "ARTIST",
            "album": "ALBUM",
            "album_artist": "ALBUMARTIST",
            "genre": "GENRE",
            "year": "DATE",
            "isrc": "ISRC",
        }

        for field, tag_name in tag_map.items():
            if field in metadata and metadata.get(field):
                audio[tag_name] = str(metadata[field])
                fields_written.append(field)

        if "track_number" in metadata:
            audio["TRACKNUMBER"] = str(metadata["track_number"])
            fields_written.append("track_number")
        if "disc_number" in metadata:
            audio["DISCNUMBER"] = str(metadata["disc_number"])
            fields_written.append("disc_number")

        audio.save()

        return TaggingResult(
            success=True,
            file_path=str(file_path),
            format="opus",
            fields_written=fields_written,
        )

    async def _tag_mp4(
        self, file_path: Path, metadata: AudioMetadata
    ) -> TaggingResult:
        """Tag an MP4/M4A/AAC file with MP4 atoms.

        Hey future me - MP4 uses atoms with weird names like ©nam!
        Track numbers are tuples: (track, total).
        """
        fields_written = []
        audio = MP4(str(file_path))

        # Map our metadata to MP4 atom keys
        tag_map = {
            "title": "©nam",
            "artist": "©ART",
            "album": "©alb",
            "album_artist": "aART",
            "genre": "©gen",
            "year": "©day",
            "comment": "©cmt",
        }

        for field, tag_name in tag_map.items():
            if field in metadata and metadata.get(field):
                audio[tag_name] = [str(metadata[field])]
                fields_written.append(field)

        # Track number (tuple format)
        if "track_number" in metadata:
            track = int(metadata["track_number"])
            total = int(metadata.get("total_tracks", 0))
            audio["trkn"] = [(track, total)]
            fields_written.append("track_number")

        # Disc number (tuple format)
        if "disc_number" in metadata:
            disc = int(metadata["disc_number"])
            total = int(metadata.get("total_discs", 0))
            audio["disk"] = [(disc, total)]
            fields_written.append("disc_number")

        audio.save()

        return TaggingResult(
            success=True,
            file_path=str(file_path),
            format="mp4",
            fields_written=fields_written,
        )

    async def embed_artwork(
        self, file_path: Path, artwork_url: str | None = None, artwork_data: bytes | None = None
    ) -> bool:
        """Embed album artwork into an audio file.

        Hey future me - downloads artwork from URL and embeds it!

        Args:
            file_path: Path to the audio file
            artwork_url: URL to download artwork from (optional)
            artwork_data: Raw artwork bytes (optional, alternative to URL)

        Returns:
            True if artwork was embedded successfully
        """
        if not MUTAGEN_AVAILABLE:
            logger.warning("mutagen not installed - cannot embed artwork")
            return False

        # Get artwork data
        if artwork_data is None and artwork_url:
            artwork_data = await self._download_artwork(artwork_url)

        if not artwork_data:
            logger.debug(f"No artwork data for {file_path}")
            return False

        # Detect image format
        mime_type = self._detect_image_mime(artwork_data)

        # Embed based on file format
        ext = file_path.suffix.lower()

        try:
            if ext == ".mp3":
                return await self._embed_artwork_mp3(file_path, artwork_data, mime_type)
            elif ext == ".flac":
                return await self._embed_artwork_flac(file_path, artwork_data, mime_type)
            elif ext in (".m4a", ".mp4", ".aac"):
                return await self._embed_artwork_mp4(file_path, artwork_data, mime_type)
            elif ext in (".ogg", ".oga", ".opus"):
                # OGG/Opus artwork embedding is complex and often not supported
                logger.debug(f"Artwork embedding not supported for {ext}")
                return False
            else:
                logger.debug(f"Unsupported format for artwork: {ext}")
                return False
        except Exception as e:
            logger.error(f"Error embedding artwork in {file_path}: {e}")
            return False

    async def _download_artwork(self, url: str) -> bytes | None:
        """Download artwork from URL.

        Hey future me - uses httpx for async HTTP!
        Has timeout and error handling.
        """
        try:
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(timeout=30.0)

            response = await self._http_client.get(url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.warning(f"Failed to download artwork from {url}: {e}")
            return None

    def _detect_image_mime(self, data: bytes) -> str:
        """Detect image MIME type from data.

        Hey future me - checks magic bytes for JPEG/PNG!
        """
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        elif data[:2] == b"\xff\xd8":
            return "image/jpeg"
        else:
            return "image/jpeg"  # Default to JPEG

    async def _embed_artwork_mp3(
        self, file_path: Path, artwork_data: bytes, mime_type: str
    ) -> bool:
        """Embed artwork in MP3 file using APIC frame.

        Hey future me - APIC is the ID3 frame for pictures!
        Type 3 = Front cover.
        """
        audio = ID3(str(file_path))

        # Remove existing artwork
        audio.delall("APIC")

        # Add new artwork
        audio.add(
            APIC(
                encoding=3,  # UTF-8
                mime=mime_type,
                type=3,  # Front cover
                desc="Cover",
                data=artwork_data,
            )
        )

        audio.save()
        return True

    async def _embed_artwork_flac(
        self, file_path: Path, artwork_data: bytes, mime_type: str
    ) -> bool:
        """Embed artwork in FLAC file using PICTURE block.

        Hey future me - FLAC uses a special PICTURE metadata block!
        """
        audio = FLAC(str(file_path))

        # Clear existing pictures
        audio.clear_pictures()

        # Create picture
        picture = Picture()
        picture.type = 3  # Front cover
        picture.mime = mime_type
        picture.desc = "Cover"
        picture.data = artwork_data

        audio.add_picture(picture)
        audio.save()
        return True

    async def _embed_artwork_mp4(
        self, file_path: Path, artwork_data: bytes, mime_type: str
    ) -> bool:
        """Embed artwork in MP4/M4A file using covr atom.

        Hey future me - MP4 uses the covr atom for cover art!
        """
        audio = MP4(str(file_path))

        # Determine format
        if mime_type == "image/png":
            cover_format = MP4Cover.FORMAT_PNG
        else:
            cover_format = MP4Cover.FORMAT_JPEG

        audio["covr"] = [MP4Cover(artwork_data, imageformat=cover_format)]
        audio.save()
        return True

    async def read_metadata(self, file_path: Path) -> AudioMetadata | None:
        """Read metadata from an audio file.

        Hey future me - useful for checking existing tags!

        Args:
            file_path: Path to the audio file

        Returns:
            AudioMetadata dict or None if file can't be read
        """
        if not MUTAGEN_AVAILABLE:
            return None

        if not file_path.exists():
            return None

        try:
            audio = mutagen.File(str(file_path), easy=True)
            if audio is None:
                return None

            metadata: AudioMetadata = {}

            # Common easy tags
            if "title" in audio:
                metadata["title"] = str(audio["title"][0])
            if "artist" in audio:
                metadata["artist"] = str(audio["artist"][0])
            if "album" in audio:
                metadata["album"] = str(audio["album"][0])
            if "albumartist" in audio:
                metadata["album_artist"] = str(audio["albumartist"][0])
            if "genre" in audio:
                metadata["genre"] = str(audio["genre"][0])
            if "date" in audio:
                metadata["year"] = str(audio["date"][0])
            if "tracknumber" in audio:
                track_str = str(audio["tracknumber"][0])
                if "/" in track_str:
                    track, total = track_str.split("/")
                    metadata["track_number"] = int(track)
                    metadata["total_tracks"] = int(total)
                else:
                    metadata["track_number"] = int(track_str)

            return metadata
        except Exception as e:
            logger.warning(f"Failed to read metadata from {file_path}: {e}")
            return None

    async def close(self) -> None:
        """Close HTTP client.

        Hey future me - call this on shutdown to clean up!
        """
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
