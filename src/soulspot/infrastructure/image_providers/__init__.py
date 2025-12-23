"""⚠️ DEPRECATED PACKAGE - DO NOT USE! ⚠️

This entire directory is DEPRECATED and scheduled for removal.

REASON: This package duplicates functionality from infrastructure/providers/.
The active implementations live in:
    src/soulspot/infrastructure/providers/

USE INSTEAD:
    from soulspot.infrastructure.providers import (
        SpotifyImageProvider,
        DeezerImageProvider,
        ImageProviderRegistry,
    )

This package was created as an alternative location but is NOT used anywhere
in the codebase. All actual imports use infrastructure/providers/.

DELETE THIS DIRECTORY when cleaning up:
    git rm -r src/soulspot/infrastructure/image_providers/

Files in this deprecated directory:
- __init__.py (this file)
- spotify_image_provider.py → Use providers/spotify_image_provider.py
- deezer_image_provider.py → Use providers/deezer_image_provider.py
- caa_image_provider.py → NOT in providers/ (feature not actively used)
"""

import warnings

# Emit deprecation warning on import
warnings.warn(
    "soulspot.infrastructure.image_providers is DEPRECATED. "
    "Use soulspot.infrastructure.providers instead. "
    "This package will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from soulspot.infrastructure.image_providers.caa_image_provider import (
    CoverArtArchiveImageProvider,
)
from soulspot.infrastructure.image_providers.deezer_image_provider import (
    DeezerImageProvider,
)
from soulspot.infrastructure.image_providers.spotify_image_provider import (
    SpotifyImageProvider,
)

__all__ = [
    "SpotifyImageProvider",
    "DeezerImageProvider",
    "CoverArtArchiveImageProvider",
]
