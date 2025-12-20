"""Image Providers - Implementations of IImageProvider interface.

Hey future me - hier leben die Provider-Implementierungen!

Jeder Provider wrapped einen Plugin/Client und implementiert IImageProvider:
- SpotifyImageProvider → SpotifyPlugin
- DeezerImageProvider → DeezerPlugin (oder DeezerClient)
- CoverArtArchiveImageProvider → MusicBrainzClient + CoverArtArchiveClient

Die Providers werden vom ImageProviderRegistry verwaltet und
nach Priorität abgefragt.
"""

from soulspot.infrastructure.image_providers.spotify_image_provider import (
    SpotifyImageProvider,
)
from soulspot.infrastructure.image_providers.deezer_image_provider import (
    DeezerImageProvider,
)
from soulspot.infrastructure.image_providers.caa_image_provider import (
    CoverArtArchiveImageProvider,
)

__all__ = [
    "SpotifyImageProvider",
    "DeezerImageProvider",
    "CoverArtArchiveImageProvider",
]
