"""
⚠️ DEPRECATED - DO NOT USE ⚠️

This file has been replaced by images.py (December 2025).
The artwork.py name was confusing - "artwork" is used for other purposes.

Use instead: soulspot.api.routers.images

This file will be removed in a future version.
"""

import warnings

warnings.warn(
    "artwork.py is deprecated. Use images.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backwards compatibility
from soulspot.api.routers.images import router, serve_image

__all__ = ["router", "serve_image"]
