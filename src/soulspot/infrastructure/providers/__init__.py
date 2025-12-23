"""Provider Packages - Download + Image Providers.

Hey future me - das sind die IMPLEMENTIERUNGEN der Provider-Interfaces!

Download Providers (IDownloadProvider):
    - SlskdDownloadProvider → Soulseek via slskd
    - DownloadProviderRegistry → Multi-Provider Management

Image Providers (IImageProvider):
    - SpotifyImageProvider → Spotify Plugin Wrapper
    - DeezerImageProvider → Deezer Plugin Wrapper
    - ImageProviderRegistry → Multi-Provider Fallback

Architektur:
    domain/ports/download_provider.py  ← IDownloadProvider Interface
    domain/ports/image_provider.py     ← IImageProvider Interface
    infrastructure/providers/          ← Implementierungen
"""

# Download Providers
from soulspot.infrastructure.providers.deezer_image_provider import (
    DeezerImageProvider,
)
from soulspot.infrastructure.providers.image_registry import (
    ImageProviderRegistry,
)
from soulspot.infrastructure.providers.registry import DownloadProviderRegistry
from soulspot.infrastructure.providers.slskd_provider import SlskdDownloadProvider

# Image Providers
from soulspot.infrastructure.providers.spotify_image_provider import (
    SpotifyImageProvider,
)

__all__ = [
    # Download
    "DownloadProviderRegistry",
    "SlskdDownloadProvider",
    # Image
    "SpotifyImageProvider",
    "DeezerImageProvider",
    "ImageProviderRegistry",
]
