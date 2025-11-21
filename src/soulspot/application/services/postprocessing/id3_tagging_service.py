"""ID3 tagging service using mutagen."""

import logging
from pathlib import Path
from typing import Any

from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, USLT, ID3NoHeaderError  # type: ignore[attr-defined]
from mutagen.mp3 import MP3

from soulspot.config import Settings
from soulspot.domain.entities import Album, Artist, Track
from soulspot.infrastructure.security import PathValidator

logger = logging.getLogger(__name__)


class ID3TaggingService:
    """Service for writing ID3v2.4 tags to audio files.

    This service:
    1. Writes comprehensive metadata to audio files
    2. Embeds artwork
    3. Adds lyrics
    4. Supports ID3v2.4 standard
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize ID3 tagging service.

        Args:
            settings: Application settings
        """
        self._settings = settings

    # Hey future me: ID3 tag writing - the metadata embedding into MP3 files
    # WHY only MP3? Mutagen's EasyID3 is MP3-specific. For FLAC/M4A we'd need different libraries
    # WHY validate path? SECURITY - user could pass path to system files
    # WHY ID3v2.4? It's the modern standard - v2.3 has charset issues, v1 is ancient
    # GOTCHA: We remove ALL existing artwork before adding new - prevents duplicate APIC frames
    async def write_tags(
        self,
        file_path: Path,
        track: Track,
        artist: Artist,
        album: Album | None = None,
        artwork_data: bytes | None = None,
        lyrics: str | None = None,
    ) -> None:
        """Write ID3 tags to an audio file.

        Args:
            file_path: Path to audio file
            track: Track entity
            artist: Artist entity
            album: Optional album entity
            artwork_data: Optional artwork image data
            lyrics: Optional lyrics text

        Raises:
            ValueError: If path is outside allowed directories or invalid
            FileNotFoundError: If audio file does not exist
        """
        # Validate file path is within allowed music directories
        allowed_dirs = [
            self._settings.storage.download_path,
            self._settings.storage.music_path,
        ]

        validated_path: Path | None = None
        for base_dir in allowed_dirs:
            try:
                validated_path = PathValidator.validate_audio_file_path(
                    file_path, base_dir
                )
                break  # Path is valid for this base directory
            except ValueError:
                continue  # Try next directory

        if validated_path is None:
            logger.error(
                "Path validation failed for %s. Not in allowed directories: %s",
                file_path,
                allowed_dirs,
            )
            raise ValueError(
                f"File path {file_path} is not in allowed directories"
            )

        # Use validated path for all subsequent operations
        file_path = validated_path

        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        # Only process MP3 files for now
        if file_path.suffix.lower() not in [".mp3"]:
            logger.warning("ID3 tagging only supports MP3 files: %s", file_path)
            return

        # Hey future me: The two-pass approach - EasyID3 for simple tags, then full ID3 for complex stuff
        # WHY two passes? EasyID3 is user-friendly but limited (no artwork, lyrics, custom frames)
        # WHY MP3(file_path, ID3=ID3)? This loads the file WITH ID3 support for advanced tags
        # GOTCHA: If file has no ID3 header, we add_tags() which creates an empty v2.4 tag
        try:
            # Try to load existing tags or create new
            try:
                audio = MP3(file_path, ID3=ID3)
            except ID3NoHeaderError:
                # No ID3 tag exists, create one
                audio = MP3(file_path)
                audio.add_tags()  # type: ignore[no-untyped-call]

            # Write basic tags using EasyID3
            easy_tags = EasyID3(file_path)  # type: ignore[no-untyped-call]

            # Artist and title (required)
            easy_tags["artist"] = artist.name
            easy_tags["title"] = track.title

            # Album information
            if album:
                easy_tags["album"] = album.title
                if album.release_year:
                    easy_tags["date"] = str(album.release_year)

            # Track number and disc number
            if track.track_number is not None:
                if album:
                    # Try to get total tracks from album
                    easy_tags["tracknumber"] = str(track.track_number)
                else:
                    easy_tags["tracknumber"] = str(track.track_number)

            # Disc number
            if track.disc_number > 1:
                easy_tags["discnumber"] = str(track.disc_number)

            # Genre (use first genre if available)
            if track.genres:
                easy_tags["genre"] = track.genres[0]
            elif album and album.genres:
                easy_tags["genre"] = album.genres[0]
            elif artist.genres:
                easy_tags["genre"] = artist.genres[0]

            # Save easy tags
            easy_tags.save()

            # Now add advanced tags (artwork, lyrics) using full ID3
            audio = MP3(file_path, ID3=ID3)

            # Embed artwork
            if artwork_data:
                self._embed_artwork(audio, artwork_data)

            # Embed lyrics
            if lyrics:
                self._embed_lyrics(audio, lyrics)

            # Add MusicBrainz IDs if available
            if track.musicbrainz_id:
                audio.tags.add(
                    self._create_text_frame("UFID", track.musicbrainz_id.encode())
                )

            # Save all tags
            audio.save(v2_version=4)
            logger.info("Successfully wrote ID3 tags to: %s", file_path)

        except Exception as e:
            logger.exception("Error writing ID3 tags to %s: %s", file_path, e)
            raise

    # Hey, artwork embedding - removes old APIC frames then adds new one
    # WHY delall first? Prevents duplicate artwork frames (wastes space, confuses players)
    # encoding=3 means UTF-8, type=3 means "Cover (front)" per ID3v2.4 spec
    # APIC = Attached Picture frame
    def _embed_artwork(self, audio: MP3, artwork_data: bytes) -> None:
        """Embed artwork into audio file.

        Args:
            audio: MP3 audio file object
            artwork_data: Image data to embed
        """
        try:
            # Remove existing artwork
            audio.tags.delall("APIC")

            # Add new artwork
            audio.tags.add(
                APIC(  # type: ignore[no-untyped-call]
                    encoding=3,  # UTF-8
                    mime="image/jpeg",
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=artwork_data,
                )
            )
            logger.debug("Embedded artwork into audio file")

        except Exception as e:
            logger.exception("Error embedding artwork: %s", e)

    # Yo lyrics embedding - USLT frame (Unsynchronised Lyrics/Text)
    # WHY lang="eng"? ISO 639-2 language code, required by spec
    # desc="" means no description (could be "chorus", "verse 1", etc)
    # delall removes old lyrics first
    def _embed_lyrics(self, audio: MP3, lyrics: str) -> None:
        """Embed lyrics into audio file.

        Args:
            audio: MP3 audio file object
            lyrics: Lyrics text
        """
        try:
            # Remove existing lyrics
            audio.tags.delall("USLT")

            # Add new lyrics
            audio.tags.add(
                USLT(  # type: ignore[no-untyped-call]
                    encoding=3,  # UTF-8
                    lang="eng",
                    desc="",
                    text=lyrics,
                )
            )
            logger.debug("Embedded lyrics into audio file")

        except Exception as e:
            logger.exception("Error embedding lyrics: %s", e)

    # Listen, stub for custom ID3 frames - NOT IMPLEMENTED
    # WHY stub? UFID (Unique File ID) and TXXX (user text) need special handling
    # TODO: Implement proper frame creation using Mutagen's frame classes
    def _create_text_frame(self, frame_id: str, data: bytes) -> Any:
        """Create a text frame for ID3 tag.

        This is a placeholder for creating custom ID3 frames.
        Currently not fully implemented - would use mutagen's specific frame
        classes like TXXX (user-defined text), UFID (unique file identifier), etc.

        Args:
            frame_id: ID3 frame identifier (e.g., 'TXXX', 'UFID')
            data: Raw frame data bytes

        Returns:
            ID3 frame object (implementation pending)

        Note:
            For MusicBrainz IDs, use mutagen's UFID frame directly.
            For custom text fields, use TXXX frames.
        """
        # TODO: Implement custom frame creation using mutagen's frame classes
        # Example: TXXX(encoding=3, desc='custom_field', text=['value'])
        pass

    # Hey tag reader - extracts ID3 tags from MP3 file
    # Returns dict for easy API serialization
    # Path validation same as write_tags - security critical
    # EasyID3 returns lists for multi-value tags (artists, genres) - we flatten single values
    async def read_tags(self, file_path: Path) -> dict[str, Any]:
        """Read ID3 tags from an audio file.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary of tag values

        Raises:
            ValueError: If path is outside allowed directories or invalid
            FileNotFoundError: If audio file does not exist
        """
        # Validate file path is within allowed music directories
        allowed_dirs = [
            self._settings.storage.download_path,
            self._settings.storage.music_path,
        ]

        validated_path: Path | None = None
        for base_dir in allowed_dirs:
            try:
                validated_path = PathValidator.validate_audio_file_path(
                    file_path, base_dir
                )
                break
            except ValueError:
                continue

        if validated_path is None:
            logger.error(
                "Path validation failed for %s. Not in allowed directories: %s",
                file_path,
                allowed_dirs,
            )
            raise ValueError(
                f"File path {file_path} is not in allowed directories"
            )

        # Use validated path
        file_path = validated_path

        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        try:
            easy_tags = EasyID3(file_path)  # type: ignore[no-untyped-call]
            tags: dict[str, Any] = {}

            # Extract common tags
            for key in easy_tags:
                value = easy_tags.get(key)  # type: ignore[no-untyped-call]
                if value:
                    tags[key] = value[0] if len(value) == 1 else value

            return tags

        except Exception as e:
            logger.exception("Error reading ID3 tags from %s: %s", file_path, e)
            return {}
