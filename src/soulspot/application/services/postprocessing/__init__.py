"""Post-processing services for downloaded music files."""

from soulspot.application.services.postprocessing.id3_tagging_service import (
    ID3TaggingService,
)
from soulspot.application.services.postprocessing.lyrics_service import LyricsService
from soulspot.application.services.postprocessing.metadata_service import (
    ArtworkService,  # Backward compatibility alias
    MetadataService,
)
from soulspot.application.services.postprocessing.pipeline import (
    PostProcessingPipeline,
)
from soulspot.application.services.postprocessing.renaming_service import (
    RenamingService,
)

__all__ = [
    "ArtworkService",  # Backward compat - alias for MetadataService
    "ID3TaggingService",
    "LyricsService",
    "MetadataService",
    "PostProcessingPipeline",
    "RenamingService",
]
