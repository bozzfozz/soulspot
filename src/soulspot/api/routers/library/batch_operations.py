"""Library batch operations and cleanup endpoints.

Hey future me - this file handles destructive batch operations:
- Clear library (local only or everything)
- Batch rename files to match templates
- Cleanup orphaned data

These are DANGEROUS operations! Most have:
- DEBUG mode guards
- dry_run options
- Confirmation requirements

Always preview before executing destructive ops!
"""

import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session, get_settings
from soulspot.config.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["library-batch"])


# =============================================================================
# Request/Response Models
# =============================================================================


class BatchRenamePreviewRequest(BaseModel):
    """Request to preview batch rename operation."""

    limit: int = 100  # Max files to preview


class BatchRenamePreviewItem(BaseModel):
    """Single file rename preview."""

    track_id: str
    current_path: str
    new_path: str
    will_change: bool


class BatchRenamePreviewResponse(BaseModel):
    """Response with batch rename preview."""

    total_files: int
    files_to_rename: int
    preview: list[BatchRenamePreviewItem]


class BatchRenameRequest(BaseModel):
    """Request to execute batch rename."""

    dry_run: bool = True  # Safety: default to dry run
    limit: int | None = None  # Limit files to rename (None = all)


class BatchRenameResult(BaseModel):
    """Single file rename result."""

    track_id: str
    old_path: str
    new_path: str
    success: bool
    error: str | None = None


class BatchRenameResponse(BaseModel):
    """Response from batch rename operation."""

    dry_run: bool
    total_processed: int
    successful: int
    failed: int
    results: list[BatchRenameResult]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _track_model_to_entity(track_model: Any) -> Any:
    """Convert a TrackModel ORM object to a Track domain entity.

    Hey future me - this centralizes conversion logic.
    Used by batch-rename to get Track entities for renaming service.

    Args:
        track_model: The TrackModel ORM object

    Returns:
        Track domain entity
    """
    from soulspot.domain.entities import Track
    from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId

    return Track(
        id=TrackId.from_string(track_model.id),
        title=track_model.title,
        artist_id=ArtistId.from_string(track_model.artist_id),
        album_id=AlbumId.from_string(track_model.album_id)
        if track_model.album_id
        else None,
        track_number=track_model.track_number,
        disc_number=track_model.disc_number,
    )


# =============================================================================
# CLEAR LIBRARY ENDPOINTS
# =============================================================================


@router.delete("/clear")
async def clear_local_library(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Clear all LOCAL library data (tracks, albums, artists with file_path).

    Hey future me - this is the NUCLEAR OPTION! Use when you want to:
    1. Start fresh with a clean library scan
    2. Fix corrupted/fragmented album assignments
    3. Remove all imported local files without touching Spotify data

    This ONLY deletes entities that were imported from local files (have file_path).
    Spotify-synced data (playlists, spotify_* tables) is NOT affected!

    Returns:
        Statistics about deleted entities
    """
    from soulspot.application.services.library_cleanup_service import (
        LibraryCleanupService,
    )

    service = LibraryCleanupService(session)
    stats = await service.clear_local_library()

    return {
        "success": True,
        "message": "Local library cleared successfully",
        **stats,
    }


@router.delete("/clear-all")
async def clear_entire_library(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """⚠️ DEV ONLY: Clear ENTIRE library (local + Spotify + Deezer + Tidal).

    Hey future me - this is the ULTRA NUCLEAR OPTION! Only for development/testing!
    DELETES EVERYTHING:
    - ALL artists (local + Spotify + Deezer + hybrid)
    - ALL albums (local + Spotify + Deezer + hybrid)
    - ALL tracks (local + Spotify + Deezer + hybrid)

    ⚠️ PROTECTED: Only available when DEBUG mode is enabled!

    Returns:
        Statistics about deleted entities
    """
    if not settings.debug:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in DEBUG mode. "
                   "Set DEBUG=true in your configuration to enable it.",
        )

    from sqlalchemy import delete, func, select

    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel,
        TrackModel,
    )

    # Count before deletion
    artists_count = await session.scalar(select(func.count(ArtistModel.id)))
    albums_count = await session.scalar(select(func.count(AlbumModel.id)))
    tracks_count = await session.scalar(select(func.count(TrackModel.id)))

    # Nuclear option: DELETE EVERYTHING (CASCADE will handle relationships)
    await session.execute(delete(TrackModel))
    await session.execute(delete(AlbumModel))
    await session.execute(delete(ArtistModel))
    await session.commit()

    return {
        "success": True,
        "message": "⚠️ ENTIRE library cleared (local + Spotify + Deezer + Tidal)",
        "deleted_artists": artists_count or 0,
        "deleted_albums": albums_count or 0,
        "deleted_tracks": tracks_count or 0,
        "warning": "This was a COMPLETE wipe. Sync from providers to restore data.",
    }


# =============================================================================
# BATCH RENAME ENDPOINTS
# =============================================================================


@router.post("/batch-rename/preview", response_model=BatchRenamePreviewResponse)
async def preview_batch_rename(
    request: BatchRenamePreviewRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BatchRenamePreviewResponse:
    """Preview batch rename operation.

    Hey future me – zeigt was passieren würde, ohne tatsächlich umzubenennen.
    Lädt die aktuellen Naming-Templates aus der DB und berechnet die neuen
    Pfade für alle Tracks mit file_path. Vergleicht alt vs neu und zeigt
    nur die Dateien die sich ändern würden.

    Args:
        request: Preview request with limit
        session: Database session
        settings: Application settings

    Returns:
        Preview of files that would be renamed
    """
    from sqlalchemy import select

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.postprocessing.renaming_service import (
        RenamingService,
    )
    from soulspot.domain.value_objects import AlbumId as DomainAlbumId
    from soulspot.domain.value_objects import ArtistId as DomainArtistId
    from soulspot.infrastructure.persistence.models import TrackModel
    from soulspot.infrastructure.persistence.repositories import (
        AlbumRepository,
        ArtistRepository,
    )

    # Initialize services
    app_settings_service = AppSettingsService(session)
    renaming_service = RenamingService(settings)
    renaming_service.set_app_settings_service(app_settings_service)

    # Check if renaming is enabled
    rename_enabled = await app_settings_service.is_rename_tracks_enabled()
    if not rename_enabled:
        return BatchRenamePreviewResponse(
            total_files=0,
            files_to_rename=0,
            preview=[],
        )

    # Get tracks with file paths
    stmt = (
        select(TrackModel).where(TrackModel.file_path.isnot(None)).limit(request.limit)
    )
    result = await session.execute(stmt)
    tracks = result.scalars().all()

    artist_repo = ArtistRepository(session)
    album_repo = AlbumRepository(session)

    preview_items: list[BatchRenamePreviewItem] = []
    files_to_rename = 0

    for track_model in tracks:
        if not track_model.file_path:
            continue

        # Get artist
        artist = await artist_repo.get_by_id(
            DomainArtistId.from_string(track_model.artist_id)
        )
        if not artist:
            continue

        # Get album (optional)
        album = None
        if track_model.album_id:
            album = await album_repo.get_by_id(
                DomainAlbumId.from_string(track_model.album_id)
            )

        # Get current path
        current_path = str(track_model.file_path)
        extension = current_path.rsplit(".", 1)[-1] if "." in current_path else "mp3"

        # Generate new filename using async method (uses DB templates)
        track = _track_model_to_entity(track_model)

        try:
            new_relative_path = await renaming_service.generate_filename_async(
                track, artist, album, f".{extension}"
            )
            new_path = str(settings.storage.music_path / new_relative_path)
        except (ValueError, OSError, KeyError) as e:
            logger.debug(
                "Skipping track %s in batch rename preview: %s", track_model.id, e
            )
            continue

        # Check if path would change
        will_change = current_path != new_path

        preview_items.append(
            BatchRenamePreviewItem(
                track_id=str(track_model.id),
                current_path=current_path,
                new_path=new_path,
                will_change=will_change,
            )
        )

        if will_change:
            files_to_rename += 1

    return BatchRenamePreviewResponse(
        total_files=len(preview_items),
        files_to_rename=files_to_rename,
        preview=preview_items,
    )


@router.post("/batch-rename", response_model=BatchRenameResponse)
async def execute_batch_rename(
    request: BatchRenameRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BatchRenameResponse:
    """Execute batch rename operation.

    Hey future me – ACHTUNG: Mit dry_run=False werden TATSÄCHLICH Dateien umbenannt!
    Das ist destruktiv. Stelle sicher dass Lidarr nicht gleichzeitig scannt.
    Der Endpoint:
    1. Lädt Naming-Templates aus DB
    2. Iteriert über Tracks mit file_path
    3. Berechnet neue Pfade
    4. Benennt Dateien um (wenn dry_run=False)
    5. Updated Track.file_path in DB

    Bei dry_run=True wird nur simuliert, keine Änderungen.

    Args:
        request: Rename request with dry_run flag
        session: Database session
        settings: Application settings

    Returns:
        Results of rename operation
    """
    from sqlalchemy import select

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.postprocessing.renaming_service import (
        RenamingService,
    )
    from soulspot.domain.value_objects import AlbumId as DomainAlbumId
    from soulspot.domain.value_objects import ArtistId as DomainArtistId
    from soulspot.infrastructure.persistence.models import TrackModel
    from soulspot.infrastructure.persistence.repositories import (
        AlbumRepository,
        ArtistRepository,
    )

    # Initialize services
    app_settings_service = AppSettingsService(session)
    renaming_service = RenamingService(settings)
    renaming_service.set_app_settings_service(app_settings_service)

    # Check if renaming is enabled
    rename_enabled = await app_settings_service.is_rename_tracks_enabled()
    if not rename_enabled:
        return BatchRenameResponse(
            dry_run=request.dry_run,
            total_processed=0,
            successful=0,
            failed=0,
            results=[],
        )

    # Get tracks with file paths
    stmt = select(TrackModel).where(TrackModel.file_path.isnot(None))
    if request.limit:
        stmt = stmt.limit(request.limit)

    result = await session.execute(stmt)
    tracks = result.scalars().all()

    artist_repo = ArtistRepository(session)
    album_repo = AlbumRepository(session)

    results: list[BatchRenameResult] = []
    successful = 0
    failed = 0

    for track_model in tracks:
        if not track_model.file_path:
            continue

        current_path = Path(str(track_model.file_path))
        if not current_path.exists() and not request.dry_run:
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path="",
                    success=False,
                    error="File not found",
                )
            )
            failed += 1
            continue

        # Get artist
        artist = await artist_repo.get_by_id(
            DomainArtistId.from_string(track_model.artist_id)
        )
        if not artist:
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path="",
                    success=False,
                    error="Artist not found",
                )
            )
            failed += 1
            continue

        # Get album (optional)
        album = None
        if track_model.album_id:
            album = await album_repo.get_by_id(
                DomainAlbumId.from_string(track_model.album_id)
            )

        # Create track entity for renaming service
        track = _track_model_to_entity(track_model)

        # Generate new filename
        try:
            extension = current_path.suffix
            new_relative_path = await renaming_service.generate_filename_async(
                track, artist, album, extension
            )
            new_path = settings.storage.music_path / new_relative_path
        except Exception as e:
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path="",
                    success=False,
                    error=f"Template error: {e}",
                )
            )
            failed += 1
            continue

        # Skip if path unchanged
        if current_path == new_path:
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path=str(new_path),
                    success=True,
                    error=None,
                )
            )
            successful += 1
            continue

        # Execute rename (if not dry run)
        if not request.dry_run:
            try:
                # Create target directory
                new_path.parent.mkdir(parents=True, exist_ok=True)

                # Move file
                shutil.move(str(current_path), str(new_path))

                # Update track in database
                track_model.file_path = str(new_path)
                await session.commit()

                results.append(
                    BatchRenameResult(
                        track_id=str(track_model.id),
                        old_path=str(current_path),
                        new_path=str(new_path),
                        success=True,
                        error=None,
                    )
                )
                successful += 1
            except Exception as e:
                await session.rollback()
                results.append(
                    BatchRenameResult(
                        track_id=str(track_model.id),
                        old_path=str(current_path),
                        new_path=str(new_path),
                        success=False,
                        error=str(e),
                    )
                )
                failed += 1
        else:
            # Dry run - just report what would happen
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path=str(new_path),
                    success=True,
                    error=None,
                )
            )
            successful += 1

    return BatchRenameResponse(
        dry_run=request.dry_run,
        total_processed=len(results),
        successful=successful,
        failed=failed,
        results=results,
    )
