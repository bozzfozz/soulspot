"""Post-processing services for downloaded music files."""

from soulspot.application.services.postprocessing.artwork_service import (
    ArtworkService,
)
from soulspot.application.services.postprocessing.id3_tagging_service import (
    ID3TaggingService,
)
from soulspot.application.services.postprocessing.lyrics_service import LyricsService
from soulspot.application.services.postprocessing.pipeline import (
    PostProcessingPipeline,
)
from soulspot.application.services.postprocessing.renaming_service import (
    RenamingService,
)

__all__ = [
    "ArtworkService",
    "ID3TaggingService",
    "LyricsService",
    "PostProcessingPipeline",
    "RenamingService",
]
