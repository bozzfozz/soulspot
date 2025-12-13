"""Use case for queueing all tracks of an album for download.

Hey future me - this is the ALBUM DOWNLOAD feature! When user clicks "Download Album"
on new releases or album detail pages, this use case queues all tracks of that album
for download. Works with both:
- Spotify albums (spotify_id provided)
- Deezer albums (deezer_id provided)
- Local albums (album_id from our DB)

The flow:
1. Fetch album from Spotify/Deezer API (or our DB)
2. Get all tracks on that album
3. Create/update tracks in our DB if needed
4. Queue each track for download via JobQueue

This integrates with:
- DownloadStatusSyncWorker (syncs download progress from slskd)
- QueueDispatcherWorker (processes WAITING downloads)
- Download Manager UI (shows queue status)
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.use_cases import UseCase
from soulspot.application.workers.job_queue import JobQueue, JobType
from soulspot.domain.value_objects import SpotifyUri
from soulspot.infrastructure.persistence.models import AlbumModel, TrackModel
from soulspot.infrastructure.persistence.repositories import TrackRepository
from soulspot.infrastructure.plugins import DeezerPlugin, SpotifyPlugin

logger = logging.getLogger(__name__)


@dataclass
class QueueAlbumDownloadsRequest:
    """Request to queue all tracks of an album for download.

    Hey future me - provide ONE of these IDs:
    - spotify_id: Spotify album ID (e.g., "2noRn2Aes5aoNVsU6iWThc")
    - deezer_id: Deezer album ID (e.g., "123456")
    - album_id: Our local DB album ID (UUID string)

    quality_filter determines what audio quality to accept:
    - "flac": Only lossless (FLAC, ALAC)
    - "320": High quality MP3 (320kbps) or better
    - "any": Accept anything available
    """

    # Album identifiers (provide one)
    spotify_id: str | None = None
    deezer_id: str | None = None
    album_id: str | None = None

    # Optional metadata for display (useful when creating new album)
    title: str | None = None
    artist: str | None = None

    # Download options
    quality_filter: str | None = None  # "flac", "320", "any"
    auto_start: bool = True
    priority: int = 10  # Higher = more urgent


@dataclass
class QueueAlbumDownloadsResponse:
    """Response from queueing album tracks for download."""

    album_title: str
    artist_name: str
    total_tracks: int
    queued_count: int
    already_downloaded: int
    skipped_count: int
    failed_count: int
    job_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if any tracks were successfully queued."""
        return self.queued_count > 0 or self.already_downloaded > 0


class QueueAlbumDownloadsUseCase(
    UseCase[QueueAlbumDownloadsRequest, QueueAlbumDownloadsResponse]
):
    """Queue all tracks of an album for download.

    Hey future me - this is the heart of album downloading! The tricky part is
    that albums can come from different sources:
    1. Spotify: Need to call Spotify API to get tracks, then import them
    2. Deezer: Need to call Deezer API to get tracks, then import them
    3. Local DB: Album already exists, just queue its tracks

    IMPORTANT: We DON'T download the album in one go. We queue each track
    individually, so they appear in the Download Manager and can be
    paused/cancelled/prioritized separately.
    """

    def __init__(
        self,
        session: AsyncSession,
        job_queue: JobQueue,
        track_repository: TrackRepository,
        spotify_plugin: SpotifyPlugin | None = None,
        deezer_plugin: DeezerPlugin | None = None,
    ) -> None:
        """Initialize the use case.

        Args:
            session: Database session
            job_queue: Job queue for download operations
            track_repository: Track repository for track operations
            spotify_plugin: Spotify plugin for fetching album tracks
            deezer_plugin: Deezer plugin for fetching album tracks
        """
        self._session = session
        self._job_queue = job_queue
        self._track_repository = track_repository
        self._spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin

    async def execute(
        self, request: QueueAlbumDownloadsRequest
    ) -> QueueAlbumDownloadsResponse:
        """Execute the album download use case.

        Args:
            request: Request with album ID and options

        Returns:
            Response with queue statistics
        """
        # Validate request - need at least one identifier
        if not request.spotify_id and not request.deezer_id and not request.album_id:
            return QueueAlbumDownloadsResponse(
                album_title=request.title or "Unknown",
                artist_name=request.artist or "Unknown",
                total_tracks=0,
                queued_count=0,
                already_downloaded=0,
                skipped_count=0,
                failed_count=1,
                errors=["Must provide spotify_id, deezer_id, or album_id"],
            )

        # Route to appropriate handler based on source
        if request.spotify_id:
            return await self._queue_spotify_album(request)
        elif request.deezer_id:
            return await self._queue_deezer_album(request)
        else:
            return await self._queue_local_album(request)

    async def _queue_spotify_album(
        self, request: QueueAlbumDownloadsRequest
    ) -> QueueAlbumDownloadsResponse:
        """Queue tracks from a Spotify album.

        Hey future me - this fetches album tracks from Spotify API, creates
        Track entities in our DB if they don't exist, then queues each for download.
        SpotifyPlugin.get_album() returns AlbumDTO with tracks included.
        """
        if not self._spotify_plugin:
            return QueueAlbumDownloadsResponse(
                album_title=request.title or "Unknown",
                artist_name=request.artist or "Unknown",
                total_tracks=0,
                queued_count=0,
                already_downloaded=0,
                skipped_count=0,
                failed_count=1,
                errors=["Spotify plugin not configured"],
            )

        try:
            # Fetch album details and tracks from Spotify
            # Returns AlbumDTO with tracks list
            album_dto = await self._spotify_plugin.get_album(request.spotify_id)

            if not album_dto:
                return QueueAlbumDownloadsResponse(
                    album_title=request.title or "Unknown",
                    artist_name=request.artist or "Unknown",
                    total_tracks=0,
                    queued_count=0,
                    already_downloaded=0,
                    skipped_count=0,
                    failed_count=1,
                    errors=[f"Album not found on Spotify: {request.spotify_id}"],
                )

            return await self._process_tracks_from_dto(
                tracks=album_dto.tracks,
                album_title=album_dto.title,
                artist_name=album_dto.artist_name,
                source="spotify",
                request=request,
            )

        except Exception as e:
            logger.exception(f"Failed to queue Spotify album: {e}")
            return QueueAlbumDownloadsResponse(
                album_title=request.title or "Unknown",
                artist_name=request.artist or "Unknown",
                total_tracks=0,
                queued_count=0,
                already_downloaded=0,
                skipped_count=0,
                failed_count=1,
                errors=[f"Failed to fetch Spotify album: {str(e)}"],
            )

    async def _queue_deezer_album(
        self, request: QueueAlbumDownloadsRequest
    ) -> QueueAlbumDownloadsResponse:
        """Queue tracks from a Deezer album.

        Hey future me - similar to Spotify, but uses Deezer API.
        Deezer album IDs are numeric strings.
        DeezerPlugin.get_album() returns AlbumDTO with tracks included.
        """
        if not self._deezer_plugin:
            return QueueAlbumDownloadsResponse(
                album_title=request.title or "Unknown",
                artist_name=request.artist or "Unknown",
                total_tracks=0,
                queued_count=0,
                already_downloaded=0,
                skipped_count=0,
                failed_count=1,
                errors=["Deezer plugin not configured"],
            )

        try:
            # Fetch album details and tracks from Deezer
            # Returns AlbumDTO with tracks list
            album_dto = await self._deezer_plugin.get_album(request.deezer_id)

            if not album_dto:
                return QueueAlbumDownloadsResponse(
                    album_title=request.title or "Unknown",
                    artist_name=request.artist or "Unknown",
                    total_tracks=0,
                    queued_count=0,
                    already_downloaded=0,
                    skipped_count=0,
                    failed_count=1,
                    errors=[f"Album not found on Deezer: {request.deezer_id}"],
                )

            return await self._process_tracks_from_dto(
                tracks=album_dto.tracks,
                album_title=album_dto.title,
                artist_name=album_dto.artist_name,
                source="deezer",
                request=request,
            )

        except Exception as e:
            logger.exception(f"Failed to queue Deezer album: {e}")
            return QueueAlbumDownloadsResponse(
                album_title=request.title or "Unknown",
                artist_name=request.artist or "Unknown",
                total_tracks=0,
                queued_count=0,
                already_downloaded=0,
                skipped_count=0,
                failed_count=1,
                errors=[f"Failed to fetch Deezer album: {str(e)}"],
            )

    async def _queue_local_album(
        self, request: QueueAlbumDownloadsRequest
    ) -> QueueAlbumDownloadsResponse:
        """Queue tracks from a local album (already in our DB).

        Hey future me - this is the simplest case! Album and tracks already
        exist in our DB, we just need to find tracks without file_path and
        queue them for download.
        """
        try:
            # Fetch album from our DB
            stmt = select(AlbumModel).where(AlbumModel.id == request.album_id)
            result = await self._session.execute(stmt)
            album = result.scalar_one_or_none()

            if not album:
                return QueueAlbumDownloadsResponse(
                    album_title=request.title or "Unknown",
                    artist_name=request.artist or "Unknown",
                    total_tracks=0,
                    queued_count=0,
                    already_downloaded=0,
                    skipped_count=0,
                    failed_count=1,
                    errors=[f"Album not found in database: {request.album_id}"],
                )

            # Fetch all tracks for this album
            tracks_stmt = select(TrackModel).where(TrackModel.album_id == album.id)
            tracks_result = await self._session.execute(tracks_stmt)
            tracks = tracks_result.scalars().all()

            # Queue each track
            job_ids: list[str] = []
            errors: list[str] = []
            queued = 0
            already_downloaded = 0
            skipped = 0
            failed = 0

            for track in tracks:
                if track.file_path:
                    already_downloaded += 1
                    continue

                try:
                    job_id = await self._job_queue.enqueue(
                        job_type=JobType.DOWNLOAD,
                        payload={
                            "track_id": str(track.id),
                            "quality_preference": request.quality_filter or "any",
                        },
                        priority=request.priority,
                    )
                    job_ids.append(job_id)
                    queued += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"Failed to queue '{track.title}': {e}")

            return QueueAlbumDownloadsResponse(
                album_title=album.title,
                artist_name=request.artist or "Unknown",
                total_tracks=len(tracks),
                queued_count=queued,
                already_downloaded=already_downloaded,
                skipped_count=skipped,
                failed_count=failed,
                job_ids=job_ids,
                errors=errors,
            )

        except Exception as e:
            logger.exception(f"Failed to queue local album: {e}")
            return QueueAlbumDownloadsResponse(
                album_title=request.title or "Unknown",
                artist_name=request.artist or "Unknown",
                total_tracks=0,
                queued_count=0,
                already_downloaded=0,
                skipped_count=0,
                failed_count=1,
                errors=[f"Database error: {str(e)}"],
            )

    async def _process_tracks_from_dto(
        self,
        tracks: list,
        album_title: str,
        artist_name: str,
        source: str,
        request: QueueAlbumDownloadsRequest,
    ) -> QueueAlbumDownloadsResponse:
        """Process and queue tracks from TrackDTO list.

        Hey future me - this handles tracks from AlbumDTO.tracks!
        TrackDTO already has normalized fields, no need to parse raw dicts.

        Steps:
        1. For each TrackDTO, check if it exists in our DB (by spotify_uri or isrc)
        2. If not, create a new Track entity
        3. Queue the track for download
        """
        from soulspot.domain.dtos import TrackDTO

        job_ids: list[str] = []
        errors: list[str] = []
        queued = 0
        already_downloaded = 0
        skipped = 0
        failed = 0

        for track in tracks:
            try:
                # Type check - tracks should be TrackDTO
                if not isinstance(track, TrackDTO):
                    logger.warning(f"Unexpected track type: {type(track)}")
                    failed += 1
                    continue

                # Extract IDs from TrackDTO
                spotify_uri = track.spotify_uri
                isrc = track.isrc
                track_title = track.title
                track_artist = track.artist_name

                # Try to find existing track in our DB
                existing_track = await self._find_existing_track(
                    spotify_uri=spotify_uri,
                    isrc=isrc,
                    title=track_title,
                    artist=track_artist,
                )

                if existing_track:
                    # Track exists - check if already downloaded
                    if existing_track.file_path:
                        already_downloaded += 1
                        continue

                    track_id = str(existing_track.id)
                else:
                    # Create new track in DB
                    new_track = await self._create_track(
                        title=track_title,
                        artist=track_artist,
                        album=album_title,
                        spotify_uri=spotify_uri,
                        isrc=isrc,
                        source=source,
                    )
                    track_id = str(new_track.id)

                # Queue for download
                job_id = await self._job_queue.enqueue(
                    job_type=JobType.DOWNLOAD,
                    payload={
                        "track_id": track_id,
                        "quality_preference": request.quality_filter or "any",
                    },
                    priority=request.priority,
                )
                job_ids.append(job_id)
                queued += 1

            except Exception as e:
                failed += 1
                track_name = getattr(track, "title", "Unknown")
                errors.append(f"Failed to queue '{track_name}': {e}")
                logger.debug(f"Track queue error: {e}")

        return QueueAlbumDownloadsResponse(
            album_title=album_title,
            artist_name=artist_name,
            total_tracks=len(tracks),
            queued_count=queued,
            already_downloaded=already_downloaded,
            skipped_count=skipped,
            failed_count=failed,
            job_ids=job_ids,
            errors=errors,
        )

    async def _find_existing_track(
        self,
        spotify_uri: str | None,
        isrc: str | None,
        title: str,
        artist: str,
    ) -> TrackModel | None:
        """Find existing track in DB by various identifiers.

        Hey future me - order of lookups matters for performance:
        1. spotify_uri - exact, fast (indexed)
        2. isrc - exact, cross-platform (indexed)
        3. title + artist - slow, fuzzy (avoid if possible)

        We return first match found.
        """
        # Try spotify_uri first
        if spotify_uri:
            try:
                uri = SpotifyUri.from_string(spotify_uri)
                track = await self._track_repository.get_by_spotify_uri(uri)
                if track:
                    return track  # type: ignore
            except Exception:
                pass

        # Try ISRC
        if isrc:
            stmt = select(TrackModel).where(TrackModel.isrc == isrc).limit(1)
            result = await self._session.execute(stmt)
            track = result.scalar_one_or_none()
            if track:
                return track

        # Could add fuzzy title+artist matching here, but it's slow and error-prone
        # For now, if we don't find by URI or ISRC, we'll create a new track
        return None

    async def _create_track(
        self,
        title: str,
        artist: str,
        album: str,
        spotify_uri: str | None,
        isrc: str | None,
        source: str,
    ) -> TrackModel:
        """Create a new track in the database.

        Hey future me - this creates a minimal track record so we can
        queue it for download. Full metadata (duration, album_id, etc.)
        can be enriched later via the metadata enrichment service.
        """
        import uuid

        track = TrackModel(
            id=uuid.uuid4(),
            title=title,
            artist_name=artist,
            album_title=album,
            spotify_uri=spotify_uri,
            isrc=isrc,
            # source field indicates origin
        )

        self._session.add(track)
        await self._session.flush()  # Get the ID without committing

        logger.debug(f"Created track: {title} by {artist} (source: {source})")
        return track
