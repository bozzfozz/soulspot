"""DEPRECATED: This file is deprecated and should be deleted.

Hey future me - Jan 2025 REFACTORING:
ArtworkService → MetadataService (renamed for clarity)

WARUM DIE UMBENENNUNG?
- ID3-Tags sind ein Metadaten-Container (Titel, Artist, Album, Genre, Jahr, Cover)
- "Artwork" war zu spezifisch - der Service macht mehr als nur Cover
- MetadataService ist der korrekte Name für ID3/FLAC Tag Embedding

NEUER CODE:
- Import von: soulspot.application.services.postprocessing.metadata_service
- Klasse: MetadataService

MIGRATION:
# ALT (deprecated):
from soulspot.application.services.postprocessing.artwork_service import ArtworkService

# NEU (use this):
from soulspot.application.services.postprocessing import MetadataService

DIESE DATEI KANN GELÖSCHT WERDEN!
Sie existiert nur noch für Rückwärtskompatibilität bei alten Imports.

DELETE THIS FILE:
git rm src/soulspot/application/services/postprocessing/artwork_service.py
"""

import warnings

# Emit deprecation warning on import
warnings.warn(
    "artwork_service.py is deprecated. Use metadata_service.py instead. "
    "Import MetadataService from soulspot.application.services.postprocessing",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from new location for backward compatibility
from soulspot.application.services.postprocessing.metadata_service import (
    MetadataService as ArtworkService,
)

__all__ = ["ArtworkService"]
