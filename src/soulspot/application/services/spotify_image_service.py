"""DEPRECATED: This file is deprecated and should be deleted.

Hey future me - Jan 2025 REFACTORING:
SpotifyImageService → ArtworkService (renamed for clarity)

WARUM DIE UMBENENNUNG?
- "SpotifyImageService" war irreführend - der Service nutzt MULTI-PROVIDER
  (Spotify, Deezer, CoverArtArchive)
- "Artwork" ist präziser für UI-Bilder (WebP, lokale Speicherung)
- Klare Trennung von MetadataService (ID3-Tag Embedding)

NEUER CODE:
- Import von: soulspot.application.services.artwork_service
- Klasse: ArtworkService

NEUE ARCHITEKTUR:
- ArtworkService (services/) = UI-Bilder für Browser-Anzeige
- MetadataService (postprocessing/) = ID3/FLAC Tag Embedding

MIGRATION:
# ALT (deprecated):
from soulspot.application.services.spotify_image_service import SpotifyImageService

# NEU (use this):
from soulspot.application.services.artwork_service import ArtworkService

# ODER via __init__.py (backward compatible):
from soulspot.application.services import ArtworkService, SpotifyImageService

DIESE DATEI KANN GELÖSCHT WERDEN!
Sie existiert nur noch für Rückwärtskompatibilität bei alten Imports.

DELETE THIS FILE:
git rm src/soulspot/application/services/spotify_image_service.py
"""

import warnings

# Emit deprecation warning on import
warnings.warn(
    "spotify_image_service.py is deprecated. Use artwork_service.py instead. "
    "Import ArtworkService from soulspot.application.services.artwork_service",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from new location for backward compatibility
from soulspot.application.services.artwork_service import (
    ArtworkService,
    ArtworkService as SpotifyImageService,  # Alias for backward compat
    ImageDownloadErrorCode,
    ImageDownloadResult,
    IMAGE_SIZES,
    WEBP_QUALITY,
    ImageType,
)

__all__ = [
    "ArtworkService",
    "SpotifyImageService",  # Deprecated alias
    "ImageDownloadErrorCode",
    "ImageDownloadResult",
    "IMAGE_SIZES",
    "WEBP_QUALITY",
    "ImageType",
]
