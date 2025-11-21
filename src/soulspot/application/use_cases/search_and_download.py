"""Search and download track use case."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from soulspot.application.services.advanced_search import (
    AdvancedSearchService,
    SearchFilters,
)
from soulspot.application.use_cases import UseCase
from soulspot.domain.entities import Download, DownloadStatus, Track
from soulspot.domain.ports import IDownloadRepository, ISlskdClient, ITrackRepository
from soulspot.domain.value_objects import DownloadId, TrackId


@dataclass
class SearchAndDownloadTrackRequest:
    """Request to search and download a track."""

    track_id: TrackId
    search_query: str | None = None
    max_results: int = 10
    timeout_seconds: int = 30
    quality_preference: str = "best"  # best, good, any
    # Advanced search options
    min_bitrate: int | None = None  # Minimum bitrate in kbps
    formats: list[str] | None = None  # Allowed formats (e.g., ["flac", "mp3"])
    exclusion_keywords: list[str] | None = None  # Keywords to exclude
    fuzzy_threshold: int = 80  # Fuzzy match threshold (0-100)
    use_advanced_search: bool = True  # Enable advanced search features


@dataclass
class SearchAndDownloadTrackResponse:
    """Response from searching and downloading a track."""

    download: Download
    search_results_count: int
    selected_file: dict[str, str] | None
    status: DownloadStatus
    slskd_download_id: str | None = None
    error_message: str | None = None


class SearchAndDownloadTrackUseCase(
    UseCase[SearchAndDownloadTrackRequest, SearchAndDownloadTrackResponse]
):
    """Use case for searching and downloading a track from Soulseek.

    This use case:
    1. Retrieves track metadata from repository
    2. Constructs search query
    3. Searches for files on Soulseek
    4. Selects best quality file
    5. Initiates download via slskd
    6. Creates download entity to track progress
    """

    def __init__(
        self,
        slskd_client: ISlskdClient,
        track_repository: ITrackRepository,
        download_repository: IDownloadRepository,
        advanced_search_service: AdvancedSearchService | None = None,
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            slskd_client: Client for Soulseek operations via slskd
            track_repository: Repository for track persistence
            download_repository: Repository for download persistence
            advanced_search_service: Optional advanced search service
        """
        self._slskd_client = slskd_client
        self._track_repository = track_repository
        self._download_repository = download_repository
        self._advanced_search_service = (
            advanced_search_service or AdvancedSearchService()
        )

    def _build_search_query(self, track: Track) -> str:
        """Build a search query from track metadata.

        Args:
            track: Track entity with metadata

        Returns:
            Search query string
        """
        # Just use track title - artist lookup would require repository injection
        return track.title

    # Hey future me: The "best file" selection - this is where the magic happens
    # WHY use_advanced_search? Because "best" means different things:
    # - Fuzzy matching: "Bohemian Rhapsody" vs "Bohemian Rhapsody (2011 Remaster).flac"
    # - Quality: 320kbps MP3 vs 1411kbps FLAC vs 128kbps MP3
    # - Exclusions: Not live, not remix, not karaoke versions
    # GOTCHA: If advanced search returns nothing, we fall back to legacy logic (simpler but dumber)
    def _select_best_file(
        self,
        results: list[dict[str, Any]],
        request: SearchAndDownloadTrackRequest,
        search_query: str,
    ) -> dict[str, Any] | None:
        """Select the best quality file from search results.

        Args:
            results: List of search results from slskd
            request: Search request with preferences
            search_query: The search query used

        Returns:
            Best file match or None
        """
        if not results:
            return None

        # Use advanced search if enabled
        if request.use_advanced_search:
            filters = SearchFilters(
                min_bitrate=request.min_bitrate,
                formats=request.formats,
                exclusion_keywords=request.exclusion_keywords,
                fuzzy_threshold=request.fuzzy_threshold,
            )

            best_match = self._advanced_search_service.select_best_match(
                search_query, results, filters
            )

            if best_match:
                # Convert SearchResult back to dict format
                return {
                    "username": best_match.username,
                    "filename": best_match.filename,
                    "size": best_match.size,
                    "bitrate": best_match.bitrate,
                    "length": best_match.length,
                    "quality": best_match.quality,
                }

            return None

        # Fallback to original logic for backward compatibility
        return self._select_best_file_legacy(results, request.quality_preference)

    def _select_best_file_legacy(
        self,
        results: list[dict[str, Any]],
        quality_preference: str,
    ) -> dict[str, Any] | None:
        """Legacy file selection logic (kept for backward compatibility).

        Args:
            results: List of search results from slskd
            quality_preference: Quality preference (best, good, any)

        Returns:
            Best file match or None
        """
        if not results:
            return None

        # Filter for audio files (MP3, FLAC, etc.)
        audio_extensions = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav"}
        audio_files = [
            r
            for r in results
            if any(
                r.get("filename", "").lower().endswith(ext) for ext in audio_extensions
            )
        ]

        if not audio_files:
            return None

        # Sort by bitrate (higher is better) and file size
        # Prefer FLAC > 320kbps MP3 > lower quality
        # Hey future me: Quality scoring logic - FLAC gets 1000 point bonus, then bitrate matters
        # WHY 1000 bonus? Makes FLAC always win over even 320kbps MP3 (which gets ~0-600 points from bitrate/size)
        # GOTCHA: This is a heuristic - a corrupted FLAC will score higher than perfect MP3
        # Consider adding file integrity checks later (mutagen can detect some issues)
        def quality_score(file: dict[str, Any]) -> tuple[int, int, int]:
            """Calculate quality score for ranking search results.

            Scoring hierarchy:
            1. Format bonus: FLAC gets 1000 bonus points
            2. Bitrate: Higher bitrate is better
            3. File size: Larger files often indicate better quality

            Args:
                file: Search result file dict with filename, bitrate, size

            Returns:
                Tuple of (format_bonus, bitrate, size) for sorting
            """
            filename = file.get("filename", "").lower()
            bitrate = file.get("bitrate", 0)
            size = file.get("size", 0)

            # Bonus for FLAC
            format_bonus = 1000 if filename.endswith(".flac") else 0

            return (format_bonus, bitrate, size)

        if quality_preference == "best":
            # Return highest quality
            return max(audio_files, key=quality_score)
        elif quality_preference == "good":
            # Return files with at least 256kbps or FLAC
            good_files = [
                f
                for f in audio_files
                if f.get("bitrate", 0) >= 256
                or f.get("filename", "").lower().endswith(".flac")
            ]
            return max(good_files, key=quality_score) if good_files else None
        else:  # any
            # Return any available file
            return audio_files[0] if audio_files else None

    # Hey future me: Search and download - the BIG ONE that ties together search, ranking, and download initiation
    # WHY advanced_search_service? Fuzzy matching + quality filters + smart scoring
    # Without it, we'd just take the first result (which might be a 96kbps live recording from 1987)
    # GOTCHA: This creates a Download entity but doesn't wait for completion
    # The download happens ASYNC via slskd - use DownloadRepository to track status
    async def execute(
        self, request: SearchAndDownloadTrackRequest
    ) -> SearchAndDownloadTrackResponse:
        """Execute the search and download use case.

        Args:
            request: Request containing track ID and download preferences

        Returns:
            Response with download entity and status
        """
        # 1. Retrieve track metadata
        track = await self._track_repository.get_by_id(request.track_id)
        if not track:
            return SearchAndDownloadTrackResponse(
                download=None,  # type: ignore
                search_results_count=0,
                selected_file=None,
                status=DownloadStatus.FAILED,
                error_message=f"Track not found: {request.track_id}",
            )

        # 2. Build search query
        search_query = request.search_query or self._build_search_query(track)

        # 3. Search for files on Soulseek
        try:
            search_results = await self._slskd_client.search(
                query=search_query,
                timeout=request.timeout_seconds,
            )
        except Exception as e:
            return SearchAndDownloadTrackResponse(
                download=None,  # type: ignore
                search_results_count=0,
                selected_file=None,
                status=DownloadStatus.FAILED,
                error_message=f"Search failed: {e}",
            )

        # 4. Select best quality file
        selected_file = self._select_best_file(
            search_results.get("results", [])
            if isinstance(search_results, dict)
            else search_results,
            request,
            search_query,
        )

        if not selected_file:
            return SearchAndDownloadTrackResponse(
                download=None,  # type: ignore
                search_results_count=len(search_results) if search_results else 0,
                selected_file=None,
                status=DownloadStatus.FAILED,
                error_message="No suitable files found in search results",
            )

        # 5. Initiate download via slskd
        try:
            download_id_str = await self._slskd_client.download(
                username=selected_file["username"],
                filename=selected_file["filename"],
            )
        except Exception as e:
            return SearchAndDownloadTrackResponse(
                download=None,  # type: ignore
                search_results_count=len(search_results) if search_results else 0,
                selected_file=selected_file,
                status=DownloadStatus.FAILED,
                slskd_download_id=None,
                error_message=f"Failed to initiate download: {e}",
            )

        # 6. Create download entity
        download_id = DownloadId.generate()
        download = Download(
            id=download_id,
            track_id=request.track_id,
            status=DownloadStatus.QUEUED,
            source_url=f"slskd://{selected_file['username']}/{selected_file['filename']}",
            progress_percent=0.0,
            created_at=datetime.now(UTC),
        )

        await self._download_repository.add(download)

        return SearchAndDownloadTrackResponse(
            download=download,
            search_results_count=len(search_results) if search_results else 0,
            selected_file=selected_file,
            status=DownloadStatus.QUEUED,
            slskd_download_id=download_id_str,
        )
