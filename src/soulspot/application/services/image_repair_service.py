# ⚠️ DEPRECATED - ImageRepairService (Dec 2025)
#
# This service has been REPLACED by:
#   from soulspot.application.services.images import repair_artist_images, repair_album_images
#
# The repair operations are now part of the unified ImageService package.
# This file is kept for backwards compatibility only.
#
# Migration guide:
#   OLD: ImageRepairService(session, image_service).repair_artist_images(limit=50)
#   NEW: from soulspot.application.services.images import repair_artist_images
#        await repair_artist_images(session, image_service, limit=50)
#
# This file will be removed in a future version.
"""⚠️ DEPRECATED - Use soulspot.application.services.images.repair instead."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

# Import from new location for backwards compatibility
from soulspot.application.services.images.repair import (
    repair_album_images as _repair_album_images,
)
from soulspot.application.services.images.repair import (
    repair_artist_images as _repair_artist_images,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.application.services.images.image_provider_registry import (
        ImageProviderRegistry,
    )
    from soulspot.application.services.images.image_service import ImageService
    from soulspot.infrastructure.persistence.repositories import ArtistRepository
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin


class ImageRepairService:
    """⚠️ DEPRECATED - Use soulspot.application.services.images.repair instead.

    This class is kept for backwards compatibility only.
    It delegates to the new repair functions.
    """

    def __init__(
        self,
        session: "AsyncSession",
        image_service: "ImageService",
        image_provider_registry: "ImageProviderRegistry | None" = None,
        spotify_plugin: "SpotifyPlugin | None" = None,
        artist_repository: "ArtistRepository | None" = None,
    ) -> None:
        """Initialize deprecated ImageRepairService."""
        warnings.warn(
            "ImageRepairService is deprecated. Use "
            "'from soulspot.application.services.images import repair_artist_images' "
            "instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._session = session
        self._image_service = image_service
        self._image_provider_registry = image_provider_registry
        self._spotify_plugin = spotify_plugin

    async def repair_artist_images(self, limit: int = 50) -> dict[str, Any]:
        """⚠️ DEPRECATED - Use repair_artist_images() from images module."""
        return await _repair_artist_images(
            session=self._session,
            image_service=self._image_service,
            image_provider_registry=self._image_provider_registry,
            spotify_plugin=self._spotify_plugin,
            limit=limit,
        )

    async def repair_album_images(self, limit: int = 50) -> dict[str, Any]:
        """⚠️ DEPRECATED - Use repair_album_images() from images module."""
        return await _repair_album_images(
            session=self._session,
            image_service=self._image_service,
            image_provider_registry=self._image_provider_registry,
            limit=limit,
        )

    # Backward compatibility aliases
    repair_missing_artwork = repair_artist_images
    repair_missing_album_artwork = repair_album_images
