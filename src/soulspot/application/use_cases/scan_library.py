"""Use case for library scanning operations."""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.library_scanner import (
    FileInfo,
    LibraryScannerService,
)
from soulspot.domain.entities import LibraryScan, ScanStatus
from soulspot.infrastructure.persistence.models import (
    FileDuplicateModel,
    LibraryScanModel,
    TrackModel,
)
from soulspot.infrastructure.security import validate_safe_path

logger = logging.getLogger(__name__)


class ScanLibraryUseCase:
    """Use case for scanning music library."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Any,
        scanner_service: LibraryScannerService | None = None,
    ) -> None:
        """Initialize use case.

        Args:
            session: Database session
            settings: Application settings for allowed directories
            scanner_service: Library scanner service
        """
        self.session = session
        self.settings = settings
        self.scanner_service = scanner_service or LibraryScannerService()

    # Hey future me: Library scanning - the file system crawler that builds our music database
    # WHY validate_safe_path? CRITICAL security check - users could pass "../../../etc/passwd"
    # We MUST ensure scan path is inside allowed directories (download_path or music_path)
    # GOTCHA: This uses OS-level path resolution - symlinks could escape the jail if not careful
    async def execute(self, scan_path: str) -> LibraryScan:
        """Execute library scan.

        Args:
            scan_path: Path to scan

        Returns:
            LibraryScan entity with scan results

        Raises:
            ValueError: If scan_path is outside allowed directories
        """
        # Validate scan path is within allowed directories
        allowed_dirs = [
            self.settings.storage.download_path,
            self.settings.storage.music_path,
        ]

        path = Path(scan_path)
        validated_path: Path | None = None

        for base_dir in allowed_dirs:
            try:
                validated_path = validate_safe_path(path, base_dir, resolve=True)
                break  # Path is valid for this base directory
            except ValueError:
                continue  # Try next directory

        if validated_path is None:
            logger.error(
                "Scan path validation failed for %s. Not in allowed directories: %s",
                scan_path,
                allowed_dirs,
            )
            raise ValueError(
                f"Scan path {scan_path} is not in allowed directories. "
                f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
            )

        # Use validated path
        scan_path_validated = str(validated_path)

        # Create scan record
        scan = LibraryScan(
            id=str(uuid.uuid4()),
            status=ScanStatus.PENDING,
            scan_path=scan_path_validated,
        )

        # Save initial scan record
        scan_model = LibraryScanModel(
            id=scan.id,
            status=scan.status.value,
            scan_path=scan.scan_path,
            started_at=datetime.now(UTC),
        )
        self.session.add(scan_model)
        await self.session.commit()

        try:
            # Start scan
            scan.start()
            scan_model.status = scan.status.value
            await self.session.commit()

            # Discover files
            path = Path(scan_path_validated)
            audio_files = self.scanner_service.discover_audio_files(path)
            scan.total_files = len(audio_files)
            scan_model.total_files = scan.total_files
            await self.session.commit()

            logger.info(
                f"Found {len(audio_files)} audio files in {scan_path_validated}"
            )

            # Scan each file
            file_infos: list[FileInfo] = []
            # Hey future me: Progress checkpoints every 100 files
            # WHY 100? Balance between DB writes and showing progress to user
            # If we commit every file, we kill the DB with transactions
            # If we only commit at the end, user sees nothing for minutes on big scans
            # 100 files ≈ every few seconds on modern hardware
            for i, file_path in enumerate(audio_files):
                try:
                    file_info = self.scanner_service.scan_file(file_path)
                    file_infos.append(file_info)

                    # Update track in database if it exists
                    await self._update_track_from_scan(file_info)

                    # Track progress
                    scan.update_progress(
                        scanned_files=i + 1,
                        broken_files=1 if not file_info.is_valid else 0,
                    )

                    # Periodically save progress
                    if (i + 1) % 100 == 0:
                        scan_model.scanned_files = scan.scanned_files
                        scan_model.broken_files = scan.broken_files
                        await self.session.commit()
                        logger.info(
                            f"Scan progress: {scan.scanned_files}/{scan.total_files}"
                        )

                except Exception as e:
                    logger.error(f"Error scanning file {file_path}: {e}")
                    continue

            # Detect duplicates
            duplicates = self.scanner_service.detect_duplicates(file_infos)
            scan.duplicate_files = len(duplicates)

            # Save duplicate information
            await self._save_duplicates(duplicates)

            # Complete scan
            scan.complete()
            scan_model.status = scan.status.value
            scan_model.scanned_files = scan.scanned_files
            scan_model.broken_files = scan.broken_files
            scan_model.duplicate_files = scan.duplicate_files
            scan_model.completed_at = scan.completed_at
            await self.session.commit()

            logger.info(
                f"Scan completed: {scan.scanned_files} files, "
                f"{scan.broken_files} broken, {scan.duplicate_files} duplicate groups"
            )

            return scan

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            scan.fail(str(e))
            scan_model.status = scan.status.value
            scan_model.error_message = scan.error_message
            scan_model.completed_at = scan.completed_at
            await self.session.commit()
            raise

    async def _update_track_from_scan(self, file_info: FileInfo) -> None:
        """Update track record with scan information.

        Args:
            file_info: Scanned file information
        """
        try:
            # Try to find existing track by file path
            stmt = select(TrackModel).where(TrackModel.file_path == str(file_info.path))
            result = await self.session.execute(stmt)
            track = result.scalar_one_or_none()

            if track:
                # Update track with scan info
                track.file_size = file_info.size
                track.file_hash = file_info.hash_value
                track.file_hash_algorithm = file_info.hash_algorithm
                track.last_scanned_at = datetime.now(UTC)
                track.is_broken = not file_info.is_valid
                track.audio_bitrate = file_info.bitrate
                track.audio_format = file_info.format
                track.audio_sample_rate = file_info.sample_rate

                # Update duration if we extracted it and track doesn't have one
                if file_info.duration_ms and track.duration_ms == 0:
                    track.duration_ms = file_info.duration_ms

        except Exception as e:
            logger.warning(f"Error updating track from scan: {e}")

    # Hey future me: Duplicate detection - finds files with same hash but different paths
    # WHY save this? User might have "/music/album/song.mp3" and "/downloads/song.mp3" - same file, wasting space
    # GOTCHA: We create/update FileDuplicateModel records here but don't DELETE files
    # The user/admin decides which duplicate to keep - we just report them
    async def _save_duplicates(self, duplicates: dict[str, list[FileInfo]]) -> None:
        """Save duplicate file information.

        Args:
            duplicates: Dictionary of hash to duplicate files
        """
        for file_hash, files in duplicates.items():
            try:
                # Check if duplicate record already exists
                stmt = select(FileDuplicateModel).where(
                    FileDuplicateModel.file_hash == file_hash
                )
                result = await self.session.execute(stmt)
                duplicate = result.scalar_one_or_none()

                total_size = sum(f.size for f in files)

                if duplicate:
                    # Update existing record
                    duplicate.duplicate_count = len(files)
                    duplicate.total_size_bytes = total_size
                    duplicate.updated_at = datetime.now(UTC)
                else:
                    # Create new record
                    duplicate = FileDuplicateModel(
                        id=str(uuid.uuid4()),
                        file_hash=file_hash,
                        file_hash_algorithm=files[0].hash_algorithm,
                        duplicate_count=len(files),
                        total_size_bytes=total_size,
                    )
                    self.session.add(duplicate)

            except Exception as e:
                logger.warning(f"Error saving duplicate info for {file_hash}: {e}")

    async def get_scan_status(self, scan_id: str) -> LibraryScan | None:
        """Get scan status.

        Args:
            scan_id: Scan ID

        Returns:
            LibraryScan entity or None if not found
        """
        stmt = select(LibraryScanModel).where(LibraryScanModel.id == scan_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return LibraryScan(
            id=model.id,
            status=ScanStatus(model.status),
            scan_path=model.scan_path,
            total_files=model.total_files,
            scanned_files=model.scanned_files,
            new_files=model.new_files,
            updated_files=model.updated_files,
            broken_files=model.broken_files,
            duplicate_files=model.duplicate_files,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class GetDuplicatesUseCase:
    """Use case for retrieving duplicate files."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize use case.

        Args:
            session: Database session
        """
        self.session = session

    async def execute(self, resolved: bool | None = None) -> list[dict]:
        """Get duplicate files.

        Args:
            resolved: Filter by resolved status (None = all)

        Returns:
            List of duplicate file information
        """
        stmt = select(FileDuplicateModel)
        if resolved is not None:
            stmt = stmt.where(FileDuplicateModel.resolved == resolved)
        stmt = stmt.order_by(FileDuplicateModel.duplicate_count.desc())

        result = await self.session.execute(stmt)
        duplicates = result.scalars().all()

        duplicate_list = []
        for dup in duplicates:
            # Find all tracks with this hash
            track_stmt = select(TrackModel).where(TrackModel.file_hash == dup.file_hash)
            track_result = await self.session.execute(track_stmt)
            tracks = track_result.scalars().all()

            duplicate_list.append(
                {
                    "id": dup.id,
                    "file_hash": dup.file_hash,
                    "duplicate_count": dup.duplicate_count,
                    "total_size_bytes": dup.total_size_bytes,
                    "resolved": dup.resolved,
                    "primary_track_id": dup.primary_track_id,
                    "tracks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "file_path": t.file_path,
                            "file_size": t.file_size,
                            "is_broken": t.is_broken,
                        }
                        for t in tracks
                    ],
                }
            )

        return duplicate_list


class GetBrokenFilesUseCase:
    """Use case for retrieving broken files."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize use case.

        Args:
            session: Database session
        """
        self.session = session

    async def execute(self) -> list[dict]:
        """Get broken files.

        Returns:
            List of broken file information
        """
        stmt = select(TrackModel).where(TrackModel.is_broken == True)  # noqa: E712
        result = await self.session.execute(stmt)
        tracks = result.scalars().all()

        return [
            {
                "id": t.id,
                "title": t.title,
                "artist_id": t.artist_id,
                "album_id": t.album_id,
                "file_path": t.file_path,
                "file_size": t.file_size,
                "last_scanned_at": t.last_scanned_at,
            }
            for t in tracks
        ]
