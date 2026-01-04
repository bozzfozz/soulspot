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
    """Clear LOCAL library data (files with file_path) - MANUAL DEVELOPMENT RESET.

    Hey future me - MANUAL USE ONLY (no automatic workers)!

    Use when:
    1. Testing local file imports - want clean slate
    2. Corrupted file_path assignments need cleanup
    3. Development: reset local files without re-syncing streaming data

    Deletes:
    - Tracks with file_path (downloaded/imported files)
    - Albums with NO tracks (true orphans)
    - Artists with NO albums AND NO tracks (true orphans)

    KEEPS:
    - ✅ Streaming tracks (file_path=NULL from Spotify/Deezer)
    - ✅ Albums with streaming tracks
    - ✅ Artists with streaming data

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
        "message": "Local files cleared (streaming data kept)",
        **stats,
    }


@router.post("/cleanup-orphans")
async def cleanup_orphaned_entities(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Clean up orphaned albums and artists.

    Hey future me - use this to manually clean up orphans after bulk operations!
    The UnifiedLibraryWorker runs this automatically, but you can trigger it manually.

    Orphans are:
    - Albums with NO tracks linked
    - Artists with NO albums AND NO tracks linked

    These can occur from:
    - Deleting artists with featured artists/collaborators
    - Track deletions leaving empty albums
    - Discography sync creating "discovered" entities

    Returns:
        Statistics about deleted orphans
    """
    from soulspot.application.services.library_cleanup_service import (
        LibraryCleanupService,
    )

    service = LibraryCleanupService(session)
    stats = await service.cleanup_orphaned_entities()

    return {
        "success": True,
        "message": f"Cleaned up {stats['albums']} orphan albums, {stats['artists']} orphan artists",
        "deleted_albums": stats["albums"],
        "deleted_artists": stats["artists"],
    }


@router.delete("/clear-all")
async def clear_entire_library(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """⚠️ DEV ONLY: Complete reset - MANUAL DEVELOPMENT RESET.

    Hey future me - ULTRA NUCLEAR OPTION! MANUAL USE ONLY!

    DELETES:
    ✅ Database: ALL tracks, albums, artists (local + streaming)
    ✅ Image cache: ALL artist/album artwork (.webp/.jpg/.png)
    ✅ Temp files: ALL temporary processing files

    KEEPS:
    ❌ /downloads - NOT touched (Soulseek downloads)

    ❌ /music - NOT touched (organized library)

    ⚠️ PROTECTED: Only available when DEBUG mode is enabled!
    ⚠️ MANUAL ONLY: NO automatic workers trigger this!

    Use when:
    - Complete fresh start during development
    - Testing sync from scratch
    - Database corrupted, need clean slate

    Returns:
        Statistics about deleted entities + files
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

    # Step 1: Nuclear option - DELETE ALL DATABASE ENTITIES (CASCADE will handle relationships)
    await session.execute(delete(TrackModel))
    await session.execute(delete(AlbumModel))
    await session.execute(delete(ArtistModel))
    await session.commit()

    logger.info(
        "Database cleared: %d tracks, %d albums, %d artists",
        tracks_count or 0,
        albums_count or 0,
        artists_count or 0,
    )

    # Step 2: DELETE IMAGE CACHE (artist/album artwork)
    # Hey future me - settings.storage.image_path points to cached images!
    # Deletes ALL .webp/.jpg/.png files but keeps directory structure.
    image_path = settings.storage.image_path
    deleted_images = 0
    if image_path.exists():
        for image_file in image_path.rglob("*"):
            if image_file.is_file() and image_file.suffix.lower() in [
                ".webp",
                ".jpg",
                ".jpeg",
                ".png",
            ]:
                try:
                    image_file.unlink()
                    deleted_images += 1
                except Exception as e:
                    logger.warning(f"Failed to delete image {image_file}: {e}")

    logger.info("Image cache cleared: %d files", deleted_images)

    # Step 3: DELETE TEMP FILES
    # Hey future me - settings.storage.temp_path is for temporary processing files.
    # SAFE to delete everything here (not user data).
    temp_path = settings.storage.temp_path
    deleted_temp_files = 0
    if temp_path.exists():
        for temp_file in temp_path.rglob("*"):
            if temp_file.is_file():
                try:
                    temp_file.unlink()
                    deleted_temp_files += 1
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file}: {e}")
        # Clean empty directories
        for dir_path in sorted(
            temp_path.rglob("*"), key=lambda p: len(p.parts), reverse=True
        ):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                try:
                    dir_path.rmdir()
                except Exception:
                    pass

    logger.info("Temp files cleared: %d files", deleted_temp_files)

    return {
        "success": True,
        "message": "⚠️ COMPLETE reset: database + image cache + temp files cleared",
        "deleted_artists": artists_count or 0,
        "deleted_albums": albums_count or 0,
        "deleted_tracks": tracks_count or 0,
        "deleted_images": deleted_images,
        "deleted_temp_files": deleted_temp_files,
        "warning": "Complete wipe (DB + cache). Sync from providers to restore data.",
        "kept": "Downloads and music files untouched",
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
