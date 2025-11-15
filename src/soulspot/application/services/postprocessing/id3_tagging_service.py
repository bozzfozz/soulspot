"""ID3 tagging service using mutagen."""

import logging
from pathlib import Path
from typing import Any

from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, USLT, ID3NoHeaderError
from mutagen.mp3 import MP3

from soulspot.config import Settings
from soulspot.domain.entities import Album, Artist, Track

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
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        # Only process MP3 files for now
        if file_path.suffix.lower() not in [".mp3"]:
            logger.warning("ID3 tagging only supports MP3 files: %s", file_path)
            return

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

    def _create_text_frame(self, frame_id: str, data: bytes) -> Any:
        """Create a text frame for ID3 tag.

        Args:
            frame_id: Frame ID
            data: Frame data

        Returns:
            ID3 frame object
        """
        # This is a placeholder for creating custom frames
        # In practice, we'd use mutagen's frame classes
        pass

    async def read_tags(self, file_path: Path) -> dict[str, Any]:
        """Read ID3 tags from an audio file.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary of tag values
        """
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
