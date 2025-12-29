"""Shared utilities for UI routers.

Hey future me - this module contains shared configuration and helpers used by all UI sub-routers:
- Templates configuration (Jinja2)
- ImageService lazy initialization
- Template helper functions (get_display_url, get_placeholder)

All UI sub-routers should import from this module to avoid duplication.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.templating import Jinja2Templates

from soulspot.config import get_settings

if TYPE_CHECKING:
    from soulspot.application.services.images import ImageService

logger = logging.getLogger(__name__)

# Hey future me - compute templates directory relative to THIS file so it works both in
# development (source tree) and production (installed package). The old hardcoded
# "src/soulspot/templates" breaks when package is installed because that path doesn't exist!
# Path(__file__).parent goes up to ui/, then .parent.parent.parent goes to soulspot/,
# then / "templates" gets us to soulspot/templates/. This works whether code runs from
# source or site-packages. Don't change back to string literal path or it'll break again!
_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Hey future me - ImageService provides centralized image URL resolution!
# We add get_display_url as a global template function so templates can call:
#   {{ get_display_url(artist.image_url, artist.image_path, 'artist') }}
# This replaces scattered inline logic with a single source of truth.
# See: docs/architecture/IMAGE_SERVICE_DETAILED_PLAN.md
#
# NOTE: Using lazy-loaded instance for SYNC template methods (get_display_url).
# Hey future me - DO NOT use module-level get_settings()! In Docker, the settings
# are set via environment variables by docker-entrypoint.sh, which happens AFTER
# Python modules are imported. If we call get_settings() at import time, we get
# wrong paths (./images instead of /config/images). This lazy getter ensures we
# get the correct settings when the function is actually called.
_image_service: "ImageService | None" = None


def _get_image_service_lazy() -> "ImageService":
    """Lazy-load ImageService to ensure settings are loaded at runtime, not import time.

    Hey future me - this fixes the Docker path issue!
    Before: _image_service = get_image_service(get_settings())  # At import time = wrong path!
    Now: _get_image_service_lazy() called at runtime = correct /config/images path.
    """
    global _image_service
    if _image_service is None:
        from soulspot.application.services.images import ImageService

        settings = get_settings()
        _image_service = ImageService(
            cache_base_path=str(settings.storage.image_path),
            local_serve_prefix="/api/images",
        )
        logger.info(
            f"ImageService initialized with cache_base_path: {_image_service.cache_base_path}"
        )
    return _image_service


def get_display_url(
    source_url: str | None,
    local_path: str | None,
    entity_type: str = "album",
) -> str:
    """Template helper for image URL resolution.

    Hey future me - now uses lazy-loaded ImageService to ensure correct Docker paths!

    Usage in Jinja2:
        {{ get_display_url(album.cover_url, album.cover_path, 'album') }}
        {{ get_display_url(artist.image_url, artist.image_path, 'artist') }}
        {{ get_display_url(playlist.cover_url, playlist.cover_path, 'playlist') }}
    """
    return _get_image_service_lazy().get_display_url(
        source_url, local_path, entity_type
    )  # type: ignore[arg-type]


def get_placeholder(entity_type: str = "album") -> str:
    """Template helper for placeholder image URL.

    Hey future me - also lazy-loaded for consistent Docker path behavior.
    """
    return _get_image_service_lazy().get_placeholder(entity_type)  # type: ignore[arg-type]


# Register as global template functions
templates.env.globals["get_display_url"] = get_display_url
templates.env.globals["get_placeholder"] = get_placeholder
