"""Import sources for UnifiedLibraryManager.

Hey future me - THIS IS THE ABSTRACTION LAYER!
Instead of hardcoding Spotify/Deezer calls in the worker,
we define a Protocol that any source can implement.

Benefits:
- Easy to add new sources (Tidal, Apple Music, etc.)
- Consistent interface across providers
- Testable with mock sources

Usage:
    from soulspot.application.sources import (
        ImportSourceRegistry,
        SpotifyImportSource,
        DeezerImportSource,
    )
    
    registry = ImportSourceRegistry()
    registry.register(SpotifyImportSource(spotify_plugin))
    registry.register(DeezerImportSource(deezer_plugin))
    
    result = await registry.import_artists_from_all()
"""

from soulspot.application.sources.deezer_source import DeezerImportSource
from soulspot.application.sources.import_source import (
    ImportResult,
    ImportSource,
    ImportSourceRegistry,
)
from soulspot.application.sources.spotify_source import SpotifyImportSource

__all__ = [
    "ImportSource",
    "ImportResult",
    "ImportSourceRegistry",
    "SpotifyImportSource",
    "DeezerImportSource",
]
