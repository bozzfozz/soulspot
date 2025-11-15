"""Post-processing pipeline orchestrator."""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from soulspot.application.services.postprocessing.artwork_service import ArtworkService
from soulspot.application.services.postprocessing.id3_tagging_service import (
    ID3TaggingService,
)
from soulspot.application.services.postprocessing.lyrics_service import LyricsService
from soulspot.application.services.postprocessing.renaming_service import (
    RenamingService,
)
from soulspot.config import Settings
from soulspot.domain.entities import Track
from soulspot.domain.ports import IAlbumRepository, IArtistRepository

logger = logging.getLogger(__name__)


class ProcessingStep(str, Enum):
    """Post-processing steps."""

    ARTWORK = "artwork"
    LYRICS = "lyrics"
    ID3_TAGGING = "id3_tagging"
    RENAMING = "renaming"


@dataclass
class ProcessingResult:
    """Result of post-processing pipeline."""

    success: bool
    final_path: Path | None
    completed_steps: list[ProcessingStep]
    errors: list[str]


class PostProcessingPipeline:
    """Orchestrates all post-processing steps after download.

    This pipeline:
    1. Downloads and embeds artwork
    2. Fetches and embeds lyrics
    3. Writes comprehensive ID3 tags
    4. Renames file based on template
    5. Provides detailed error handling and logging
    """

    def __init__(
        self,
        settings: Settings,
        artist_repository: IArtistRepository,
        album_repository: IAlbumRepository,
        artwork_service: ArtworkService | None = None,
        lyrics_service: LyricsService | None = None,
        id3_tagging_service: ID3TaggingService | None = None,
        renaming_service: RenamingService | None = None,
    ) -> None:
        """Initialize post-processing pipeline.

        Args:
            settings: Application settings
            artist_repository: Repository for artist data
            album_repository: Repository for album data
            artwork_service: Optional artwork service (created if not provided)
            lyrics_service: Optional lyrics service (created if not provided)
            id3_tagging_service: Optional ID3 tagging service (created if not provided)
            renaming_service: Optional renaming service (created if not provided)
        """
        self._settings = settings
        self._artist_repository = artist_repository
        self._album_repository = album_repository

        # Initialize services
        self._artwork_service = artwork_service or ArtworkService(settings)
        self._lyrics_service = lyrics_service or LyricsService(settings)
        self._id3_tagging_service = id3_tagging_service or ID3TaggingService(settings)
        self._renaming_service = renaming_service or RenamingService(settings)

    async def process(
        self,
        file_path: Path,
        track: Track,
    ) -> ProcessingResult:
        """Run post-processing pipeline on a downloaded file.

        Args:
            file_path: Path to downloaded audio file
            track: Track entity

        Returns:
            Processing result with success status and errors
        """
        if not self._settings.postprocessing.enabled:
            logger.info("Post-processing disabled, skipping")
            return ProcessingResult(
                success=True,
                final_path=file_path,
                completed_steps=[],
                errors=[],
            )

        completed_steps: list[ProcessingStep] = []
        errors: list[str] = []
        current_path = file_path

        logger.info("Starting post-processing for track: %s", track.title)

        try:
            # Fetch related entities
            artist = await self._artist_repository.get_by_id(track.artist_id)
            if not artist:
                error_msg = f"Artist not found: {track.artist_id}"
                logger.error(error_msg)
                errors.append(error_msg)
                return ProcessingResult(
                    success=False,
                    final_path=current_path,
                    completed_steps=completed_steps,
                    errors=errors,
                )

            album = None
            if track.album_id:
                album = await self._album_repository.get_by_id(track.album_id)

            # Step 1: Download artwork
            artwork_data = None
            if self._settings.postprocessing.artwork_enabled:
                try:
                    artwork_data = await self._artwork_service.download_artwork(
                        track, album
                    )
                    if artwork_data:
                        completed_steps.append(ProcessingStep.ARTWORK)
                        logger.info("✓ Artwork downloaded")
                    else:
                        logger.warning("No artwork found")
                except Exception as e:
                    error_msg = f"Artwork download failed: {e}"
                    logger.exception(error_msg)
                    errors.append(error_msg)

            # Step 2: Fetch lyrics
            lyrics = None
            if self._settings.postprocessing.lyrics_enabled:
                try:
                    lyrics, is_synced = await self._lyrics_service.fetch_lyrics(
                        track, artist.name, album.title if album else None
                    )
                    if lyrics:
                        completed_steps.append(ProcessingStep.LYRICS)
                        logger.info("✓ Lyrics fetched (synced: %s)", is_synced)
                    else:
                        logger.warning("No lyrics found")
                except Exception as e:
                    error_msg = f"Lyrics fetch failed: {e}"
                    logger.exception(error_msg)
                    errors.append(error_msg)

            # Step 3: Write ID3 tags
            if self._settings.postprocessing.id3_tagging_enabled:
                try:
                    await self._id3_tagging_service.write_tags(
                        current_path,
                        track,
                        artist,
                        album,
                        artwork_data,
                        lyrics,
                    )
                    completed_steps.append(ProcessingStep.ID3_TAGGING)
                    logger.info("✓ ID3 tags written")
                except Exception as e:
                    error_msg = f"ID3 tagging failed: {e}"
                    logger.exception(error_msg)
                    errors.append(error_msg)

            # Step 4: Rename and organize file
            if self._settings.postprocessing.file_renaming_enabled:
                try:
                    new_path = await self._renaming_service.rename_file(
                        current_path,
                        track,
                        artist,
                        album,
                    )
                    current_path = new_path
                    completed_steps.append(ProcessingStep.RENAMING)
                    logger.info("✓ File renamed to: %s", new_path)
                except Exception as e:
                    error_msg = f"File renaming failed: {e}"
                    logger.exception(error_msg)
                    errors.append(error_msg)

            # Update track with final file path
            from soulspot.domain.value_objects import FilePath

            track.update_file_path(FilePath(current_path))

            success = len(errors) == 0
            logger.info(
                "Post-processing completed (success: %s, steps: %d, errors: %d)",
                success,
                len(completed_steps),
                len(errors),
            )

            return ProcessingResult(
                success=success,
                final_path=current_path,
                completed_steps=completed_steps,
                errors=errors,
            )

        except Exception as e:
            error_msg = f"Post-processing pipeline failed: {e}"
            logger.exception(error_msg)
            errors.append(error_msg)
            return ProcessingResult(
                success=False,
                final_path=current_path,
                completed_steps=completed_steps,
                errors=errors,
            )
