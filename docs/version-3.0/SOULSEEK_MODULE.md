# Soulseek Module - Complete Design Specification

**Module:** Soulseek Download Management  
**Version:** 1.0.0  
**Status:** Design Phase  
**Last Updated:** 2025-11-21

---

## 1. Module Overview

### 1.1 Purpose

The Soulseek module manages all functionality related to searching, downloading, and managing music files through the Soulseek P2P network via the slskd daemon. This module serves as the **reference implementation** for the modular architecture and demonstrates best practices for all other modules.

### 1.2 Core Responsibilities

**Primary Functions:**
- Search tracks on Soulseek network
- Queue and manage downloads
- Monitor download progress in real-time
- Handle download completion and errors
- Manage slskd connection and health
- Coordinate with other modules (metadata enrichment, library management)

**Boundaries:**
- **Owns**: Download queue, search results, slskd integration, download status
- **Uses**: Metadata module (track enrichment), Library module (file management)
- **Provides**: Download events, download API, search API

### 1.3 Key Features

1. **Search Management**
   - Search Soulseek network for tracks
   - Filter and rank search results by quality
   - Cache recent searches

2. **Download Queue**
   - Priority-based download queue
   - Concurrent download management
   - Automatic retry on failure
   - Pause/resume downloads

3. **Progress Monitoring**
   - Real-time progress updates via SSE
   - Download speed and ETA calculation
   - Status notifications

4. **File Management**
   - Download to temporary location
   - Validate downloaded files
   - Trigger post-processing pipeline

5. **slskd Integration**
   - Health monitoring
   - Connection management
   - API error handling with circuit breaker

---

## 2. Module Structure

### 2.1 Directory Layout

```
modules/soulseek/
├── README.md                              # ✅ Module overview & getting started
├── CHANGELOG.md                           # ✅ Module version history
├── __init__.py                            # Module interface
│
├── docs/                                  # ✅ Module documentation
│   ├── architecture.md                    # Architecture & design decisions
│   ├── api.md                             # API endpoints documentation
│   ├── events.md                          # Event schemas & contracts
│   ├── configuration.md                   # Configuration guide
│   └── development.md                     # Development guide
│
├── frontend/                              # Frontend layer
│   ├── __init__.py
│   ├── pages/
│   │   ├── downloads.html                # Main downloads page
│   │   ├── search.html                   # Search interface
│   │   └── settings.html                 # slskd settings
│   ├── widgets/
│   │   ├── download_queue.html           # Download queue widget
│   │   ├── download_stats.html           # Statistics widget
│   │   ├── search_results.html           # Search results widget
│   │   └── active_downloads.html         # Active downloads widget
│   ├── partials/
│   │   ├── download_item.html            # Single download item
│   │   ├── search_result_item.html       # Single search result
│   │   ├── progress_bar.html             # Progress indicator
│   │   └── download_actions.html         # Action buttons
│   ├── styles/
│   │   ├── soulseek.css                  # Module styles
│   │   └── components/
│   │       ├── download_card.css         # Card component
│   │       └── search_form.css           # Search form styles
│   └── scripts/
│       ├── downloads.js                  # Download management
│       ├── search.js                     # Search functionality
│       └── sse_handler.js                # SSE event handling
│
├── backend/                               # Backend layers
│   ├── __init__.py
│   │
│   ├── api/                              # API layer
│   │   ├── __init__.py
│   │   ├── routes.py                     # FastAPI router
│   │   ├── schemas.py                    # Request/Response schemas
│   │   └── dependencies.py               # DI dependencies
│   │
│   ├── application/                      # Application layer
│   │   ├── __init__.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── download_service.py       # Download orchestration
│   │   │   ├── search_service.py         # Search orchestration
│   │   │   └── queue_service.py          # Queue management
│   │   ├── use_cases/
│   │   │   ├── __init__.py
│   │   │   ├── commands/
│   │   │   │   ├── start_download_command.py
│   │   │   │   ├── cancel_download_command.py
│   │   │   │   └── update_priority_command.py
│   │   │   └── queries/
│   │   │       ├── get_downloads_query.py
│   │   │       ├── search_tracks_query.py
│   │   │       └── get_download_status_query.py
│   │   └── dto/
│   │       ├── __init__.py
│   │       ├── download_dto.py
│   │       └── search_result_dto.py
│   │
│   ├── domain/                           # Domain layer
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── __init__.py
│   │   │   ├── download.py               # Download entity
│   │   │   ├── search_result.py          # Search result entity
│   │   │   └── download_queue.py         # Queue aggregate
│   │   ├── value_objects/
│   │   │   ├── __init__.py
│   │   │   ├── download_id.py            # Download identifier
│   │   │   ├── download_status.py        # Status enum
│   │   │   ├── file_quality.py           # Quality value object
│   │   │   └── download_priority.py      # Priority value object
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── quality_ranker.py         # Rank search results
│   │   │   └── retry_strategy.py         # Retry logic
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── download_started.py
│   │   │   ├── download_completed.py
│   │   │   ├── download_failed.py
│   │   │   └── search_completed.py
│   │   ├── ports/
│   │   │   ├── __init__.py
│   │   │   ├── download_repository.py    # IDownloadRepository
│   │   │   ├── slskd_client.py           # ISlskdClient
│   │   │   └── progress_notifier.py      # IProgressNotifier
│   │   └── exceptions/
│   │       ├── __init__.py
│   │       ├── download_errors.py        # Download exceptions
│   │       └── slskd_errors.py           # slskd exceptions
│   │
│   ├── infrastructure/                   # Infrastructure layer
│   │   ├── __init__.py
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── models.py                 # SQLAlchemy models
│   │   │   └── repositories.py           # Repository implementations
│   │   ├── integrations/
│   │   │   ├── __init__.py
│   │   │   ├── slskd_client.py           # slskd HTTP client
│   │   │   └── circuit_breaker.py        # Circuit breaker wrapper
│   │   └── adapters/
│   │       ├── __init__.py
│   │       └── sse_notifier.py           # SSE progress notifier
│   │
│   └── config/                           # Configuration
│       ├── __init__.py
│       └── settings.py                   # Module settings
│
├── tests/                                # Tests
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_download_service.py
│   │   ├── test_search_service.py
│   │   ├── test_download_entity.py
│   │   ├── test_quality_ranker.py
│   │   └── test_repositories.py
│   ├── integration/
│   │   ├── test_slskd_integration.py
│   │   ├── test_download_flow.py
│   │   └── test_search_flow.py
│   └── fixtures/
│       ├── download_fixtures.py
│       ├── search_fixtures.py
│       └── slskd_mock_responses.py
│
└── contracts/                            # Module contracts
    ├── api.yaml                          # OpenAPI spec
    ├── events.yaml                       # Event schemas
    └── dependencies.yaml                 # Module dependencies
```

---

## 3. Domain Model

### 3.1 Core Entities

**Download Entity:**
```python
# modules/soulseek/backend/domain/entities/download.py

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..value_objects import (
    DownloadId,
    DownloadStatus,
    DownloadPriority,
    FileQuality,
)
from ..exceptions import DownloadValidationError

@dataclass
class Download:
    """
    Download domain entity.
    
    Hey future me, this represents a single download from Soulseek. The download
    goes through states: QUEUED → IN_PROGRESS → COMPLETED (or FAILED).
    Priority determines queue position (higher = first). Progress is 0-100 percent.
    Keep track of retry_count to prevent infinite loops!
    """
    
    # Identity
    id: DownloadId
    track_id: str  # Reference to track in other module
    
    # Download details
    username: str  # Soulseek username of source
    filename: str  # Original filename from search
    file_size: int  # Size in bytes
    quality: FileQuality
    
    # Status and progress
    status: DownloadStatus = DownloadStatus.QUEUED
    priority: DownloadPriority = field(
        default_factory=lambda: DownloadPriority(0)
    )
    progress_percent: float = 0.0
    bytes_downloaded: int = 0
    download_speed_kbps: float = 0.0
    
    # Paths
    target_path: Optional[Path] = None
    temp_path: Optional[Path] = None
    
    # Retry handling
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    
    # Timestamps
    queued_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def start(self, temp_path: Path) -> None:
        """
        Start the download.
        
        Args:
            temp_path: Temporary download location
            
        Raises:
            DownloadValidationError: If download cannot be started
        """
        if self.status != DownloadStatus.QUEUED:
            raise DownloadValidationError(
                f"Cannot start download in status {self.status}"
            )
        
        self.status = DownloadStatus.IN_PROGRESS
        self.temp_path = temp_path
        self.started_at = datetime.utcnow()
        self.progress_percent = 0.0
    
    def update_progress(
        self, bytes_downloaded: int, speed_kbps: float
    ) -> None:
        """Update download progress."""
        if self.status != DownloadStatus.IN_PROGRESS:
            return
        
        self.bytes_downloaded = bytes_downloaded
        self.download_speed_kbps = speed_kbps
        
        if self.file_size > 0:
            self.progress_percent = (bytes_downloaded / self.file_size) * 100
    
    def complete(self, final_path: Path) -> None:
        """
        Mark download as completed.
        
        Args:
            final_path: Final location of downloaded file
        """
        if self.status != DownloadStatus.IN_PROGRESS:
            raise DownloadValidationError(
                f"Cannot complete download in status {self.status}"
            )
        
        self.status = DownloadStatus.COMPLETED
        self.target_path = final_path
        self.completed_at = datetime.utcnow()
        self.progress_percent = 100.0
    
    def fail(self, error: str) -> None:
        """
        Mark download as failed.
        
        Args:
            error: Error message
        """
        self.status = DownloadStatus.FAILED
        self.last_error = error
        self.retry_count += 1
    
    def can_retry(self) -> bool:
        """Check if download can be retried."""
        return (
            self.status == DownloadStatus.FAILED
            and self.retry_count < self.max_retries
        )
    
    def retry(self) -> None:
        """Retry failed download."""
        if not self.can_retry():
            raise DownloadValidationError("Cannot retry this download")
        
        self.status = DownloadStatus.QUEUED
        self.progress_percent = 0.0
        self.bytes_downloaded = 0
        self.started_at = None
        self.temp_path = None
    
    def cancel(self) -> None:
        """Cancel the download."""
        if self.status in [DownloadStatus.COMPLETED, DownloadStatus.CANCELLED]:
            raise DownloadValidationError(
                f"Cannot cancel download in status {self.status}"
            )
        
        self.status = DownloadStatus.CANCELLED
    
    def calculate_eta_seconds(self) -> Optional[int]:
        """Calculate estimated time to completion."""
        if (
            self.status != DownloadStatus.IN_PROGRESS
            or self.download_speed_kbps == 0
        ):
            return None
        
        remaining_bytes = self.file_size - self.bytes_downloaded
        remaining_kb = remaining_bytes / 1024
        eta_seconds = remaining_kb / self.download_speed_kbps
        
        return int(eta_seconds)
```

**Search Result Entity:**
```python
# modules/soulseek/backend/domain/entities/search_result.py

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..value_objects import FileQuality

@dataclass
class SearchResult:
    """
    Soulseek search result entity.
    
    Hey future me, this represents a single file found in Soulseek search.
    The quality ranker uses bitrate, sample_rate, and file size to score results.
    Higher score = better quality. We keep upload_speed to prefer fast sources.
    """
    
    # Search context
    search_id: str
    query: str
    
    # File details
    username: str  # Soulseek user sharing the file
    filename: str
    file_path: str  # Full path on user's system
    file_size: int  # Bytes
    
    # Audio quality
    bitrate: Optional[int] = None  # kbps
    sample_rate: Optional[int] = None  # Hz
    length_seconds: Optional[int] = None
    quality: Optional[FileQuality] = None
    
    # Source info
    upload_speed: Optional[int] = None  # kbps
    queue_length: int = 0
    
    # Scoring
    quality_score: float = 0.0  # Calculated by QualityRanker
    
    # Timestamp
    found_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_downloadable(self) -> bool:
        """Check if result can be downloaded."""
        return (
            self.file_size > 0
            and len(self.filename) > 0
            and len(self.username) > 0
        )
    
    def get_extension(self) -> str:
        """Get file extension."""
        return Path(self.filename).suffix.lower()
    
    def is_audio_file(self) -> bool:
        """Check if file is audio format."""
        audio_extensions = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".opus"}
        return self.get_extension() in audio_extensions
```

### 3.2 Value Objects

**Download Status:**
```python
# modules/soulseek/backend/domain/value_objects/download_status.py

from enum import Enum

class DownloadStatus(str, Enum):
    """Download status value object."""
    
    QUEUED = "queued"           # Waiting in queue
    IN_PROGRESS = "in_progress" # Currently downloading
    COMPLETED = "completed"     # Successfully downloaded
    FAILED = "failed"           # Download failed
    CANCELLED = "cancelled"     # User cancelled
    PAUSED = "paused"          # Temporarily paused
```

**File Quality:**
```python
# modules/soulseek/backend/domain/value_objects/file_quality.py

from enum import Enum

class FileQuality(str, Enum):
    """File quality classification."""
    
    LOW = "low"         # < 128 kbps
    MEDIUM = "medium"   # 128-256 kbps
    HIGH = "high"       # 256-320 kbps
    LOSSLESS = "lossless"  # FLAC, WAV, etc.
    
    @classmethod
    def from_bitrate(cls, bitrate: int, is_lossless: bool = False) -> "FileQuality":
        """
        Determine quality from bitrate.
        
        Args:
            bitrate: Bitrate in kbps
            is_lossless: Whether format is lossless
            
        Returns:
            FileQuality classification
        """
        if is_lossless:
            return cls.LOSSLESS
        elif bitrate >= 256:
            return cls.HIGH
        elif bitrate >= 128:
            return cls.MEDIUM
        else:
            return cls.LOW
```

### 3.3 Domain Services

**Quality Ranker:**
```python
# modules/soulseek/backend/domain/services/quality_ranker.py

from typing import List
from ..entities import SearchResult
from ..value_objects import FileQuality

class QualityRanker:
    """
    Ranks search results by quality.
    
    Hey future me, this scores search results to find the best file to download.
    We prefer: higher bitrate, lossless formats, faster upload speeds, shorter queues.
    The scoring is weighted: quality matters most, then speed, then queue.
    Don't over-engineer this - simple heuristics work fine!
    """
    
    # Weights for scoring
    BITRATE_WEIGHT = 0.4
    FORMAT_WEIGHT = 0.3
    SPEED_WEIGHT = 0.2
    QUEUE_WEIGHT = 0.1
    
    def rank_results(
        self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Rank search results by quality.
        
        Args:
            results: List of search results
            
        Returns:
            Sorted list (best first)
        """
        # Calculate scores
        for result in results:
            result.quality_score = self._calculate_score(result)
        
        # Sort by score (descending)
        return sorted(
            results,
            key=lambda r: r.quality_score,
            reverse=True
        )
    
    def _calculate_score(self, result: SearchResult) -> float:
        """Calculate quality score for result."""
        score = 0.0
        
        # Bitrate score (0-1)
        if result.bitrate:
            bitrate_score = min(result.bitrate / 320, 1.0)
            score += bitrate_score * self.BITRATE_WEIGHT
        
        # Format score (0-1)
        format_score = self._get_format_score(result)
        score += format_score * self.FORMAT_WEIGHT
        
        # Upload speed score (0-1)
        if result.upload_speed:
            speed_score = min(result.upload_speed / 10000, 1.0)
            score += speed_score * self.SPEED_WEIGHT
        
        # Queue score (0-1, inverted - shorter queue is better)
        queue_score = max(0, 1.0 - (result.queue_length / 100))
        score += queue_score * self.QUEUE_WEIGHT
        
        return score
    
    def _get_format_score(self, result: SearchResult) -> float:
        """Get score for file format."""
        ext = result.get_extension()
        
        # Lossless formats
        if ext in {".flac", ".wav", ".ape"}:
            return 1.0
        # High quality lossy
        elif ext in {".mp3", ".m4a", ".opus"}:
            return 0.7
        # Lower quality
        elif ext in {".ogg", ".wma"}:
            return 0.5
        # Unknown
        else:
            return 0.3
```

---

## 4. Application Layer

### 4.1 Download Service

```python
# modules/soulseek/backend/application/services/download_service.py

from typing import List, Optional
from pathlib import Path
from ...domain.entities import Download
from ...domain.value_objects import DownloadId, DownloadStatus
from ...domain.ports import IDownloadRepository, ISlskdClient, IProgressNotifier
from ...domain.events import (
    DownloadStartedEvent,
    DownloadCompletedEvent,
    DownloadFailedEvent,
)
from core.events import EventBus

class DownloadService:
    """
    Download orchestration service.
    
    Hey future me, this service coordinates the entire download lifecycle:
    1. Create download entity from search result
    2. Queue it (repository saves with QUEUED status)
    3. Worker picks it up and calls start_download()
    4. We monitor progress via slskd client
    5. On completion, publish event for metadata/library modules
    
    IMPORTANT: Don't block here - downloads happen async in background!
    We just manage the queue and state transitions.
    """
    
    def __init__(
        self,
        repository: IDownloadRepository,
        slskd_client: ISlskdClient,
        event_bus: EventBus,
        progress_notifier: IProgressNotifier,
        download_dir: Path,
    ):
        self._repository = repository
        self._slskd = slskd_client
        self._event_bus = event_bus
        self._progress_notifier = progress_notifier
        self._download_dir = download_dir
    
    async def queue_download(
        self,
        track_id: str,
        username: str,
        filename: str,
        file_size: int,
        quality: FileQuality,
        priority: int = 0,
    ) -> Download:
        """
        Queue a new download.
        
        Args:
            track_id: Track identifier
            username: Soulseek username
            filename: File to download
            file_size: File size in bytes
            quality: File quality
            priority: Download priority (higher = first)
            
        Returns:
            Created download entity
        """
        # Create download entity
        download = Download(
            id=DownloadId.generate(),
            track_id=track_id,
            username=username,
            filename=filename,
            file_size=file_size,
            quality=quality,
            priority=DownloadPriority(priority),
        )
        
        # Validate
        download.validate()
        
        # Save to queue
        await self._repository.save(download)
        
        return download
    
    async def start_download(self, download_id: DownloadId) -> None:
        """
        Start downloading a queued download.
        
        Args:
            download_id: Download to start
        """
        # Load download
        download = await self._repository.get(download_id)
        if not download:
            raise DownloadNotFoundError(f"Download {download_id} not found")
        
        # Start download entity
        temp_path = self._download_dir / f"temp_{download.id.value}"
        download.start(temp_path)
        await self._repository.save(download)
        
        # Start actual download via slskd
        try:
            await self._slskd.start_download(
                username=download.username,
                filename=download.filename,
                destination=str(temp_path),
            )
            
            # Publish event
            await self._event_bus.publish(
                DownloadStartedEvent(
                    download_id=download.id.value,
                    track_id=download.track_id,
                    filename=download.filename,
                )
            )
            
        except Exception as e:
            download.fail(str(e))
            await self._repository.save(download)
            raise
    
    async def update_progress(
        self,
        download_id: DownloadId,
        bytes_downloaded: int,
        speed_kbps: float,
    ) -> None:
        """
        Update download progress.
        
        Args:
            download_id: Download ID
            bytes_downloaded: Bytes downloaded so far
            speed_kbps: Current download speed
        """
        download = await self._repository.get(download_id)
        if not download:
            return
        
        # Update progress
        download.update_progress(bytes_downloaded, speed_kbps)
        await self._repository.save(download)
        
        # Notify clients via SSE
        await self._progress_notifier.notify(
            download_id=download.id.value,
            progress=download.progress_percent,
            speed=speed_kbps,
            eta_seconds=download.calculate_eta_seconds(),
        )
    
    async def complete_download(
        self,
        download_id: DownloadId,
        final_path: Path,
    ) -> None:
        """
        Mark download as completed.
        
        Args:
            download_id: Download ID
            final_path: Final file location
        """
        download = await self._repository.get(download_id)
        if not download:
            return
        
        # Complete download
        download.complete(final_path)
        await self._repository.save(download)
        
        # Publish completion event
        await self._event_bus.publish(
            DownloadCompletedEvent(
                download_id=download.id.value,
                track_id=download.track_id,
                file_path=str(final_path),
                file_size=download.file_size,
            )
        )
    
    async def handle_download_failure(
        self,
        download_id: DownloadId,
        error: str,
    ) -> None:
        """
        Handle download failure.
        
        Args:
            download_id: Download ID
            error: Error message
        """
        download = await self._repository.get(download_id)
        if not download:
            return
        
        # Mark as failed
        download.fail(error)
        await self._repository.save(download)
        
        # Publish failure event
        await self._event_bus.publish(
            DownloadFailedEvent(
                download_id=download.id.value,
                track_id=download.track_id,
                error=error,
                can_retry=download.can_retry(),
            )
        )
        
        # Auto-retry if possible
        if download.can_retry():
            download.retry()
            await self._repository.save(download)
            # Re-queue for retry
            await self.start_download(download.id)
    
    async def get_active_downloads(self) -> List[Download]:
        """Get all active downloads."""
        return await self._repository.list_by_status(
            [DownloadStatus.QUEUED, DownloadStatus.IN_PROGRESS]
        )
    
    async def cancel_download(self, download_id: DownloadId) -> bool:
        """
        Cancel a download.
        
        Args:
            download_id: Download to cancel
            
        Returns:
            True if cancelled successfully
        """
        download = await self._repository.get(download_id)
        if not download:
            return False
        
        # Cancel in slskd if in progress
        if download.status == DownloadStatus.IN_PROGRESS:
            try:
                await self._slskd.cancel_download(download.filename)
            except Exception:
                pass  # Best effort
        
        # Update entity
        download.cancel()
        await self._repository.save(download)
        
        return True
```

---

## 5. API Layer

### 5.1 Routes

```python
# modules/soulseek/backend/api/routes.py

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from .schemas import (
    DownloadResponse,
    DownloadListResponse,
    SearchRequest,
    SearchResponse,
    StartDownloadRequest,
    UpdatePriorityRequest,
)
from ..application.services import DownloadService, SearchService
from .dependencies import get_download_service, get_search_service

router = APIRouter(
    prefix="/soulseek",
    tags=["soulseek"],
)

# Health check
@router.get("/health")
async def health_check() -> dict:
    """Module health check."""
    return {
        "status": "healthy",
        "module": "soulseek",
        "version": "1.0.0",
    }

# Search endpoints
@router.post("/search", response_model=SearchResponse)
async def search_tracks(
    request: SearchRequest,
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """
    Search for tracks on Soulseek network.
    
    Args:
        request: Search parameters
        service: Search service
        
    Returns:
        Search results ranked by quality
    """
    results = await service.search(
        query=request.query,
        min_bitrate=request.min_bitrate,
        max_results=request.max_results,
    )
    
    return SearchResponse(
        search_id=results.search_id,
        query=request.query,
        results=[
            SearchResultSchema.from_entity(r) for r in results.items
        ],
        total=len(results.items),
    )

# Download endpoints
@router.post("/downloads", response_model=DownloadResponse, status_code=201)
async def start_download(
    request: StartDownloadRequest,
    service: DownloadService = Depends(get_download_service),
) -> DownloadResponse:
    """
    Start a new download.
    
    Args:
        request: Download parameters
        service: Download service
        
    Returns:
        Created download
    """
    download = await service.queue_download(
        track_id=request.track_id,
        username=request.username,
        filename=request.filename,
        file_size=request.file_size,
        quality=request.quality,
        priority=request.priority,
    )
    
    # Start download async (don't wait)
    await service.start_download(download.id)
    
    return DownloadResponse.from_entity(download)

@router.get("/downloads", response_model=DownloadListResponse)
async def list_downloads(
    status: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    service: DownloadService = Depends(get_download_service),
) -> DownloadListResponse:
    """
    List downloads with optional filters.
    
    Args:
        status: Filter by status
        limit: Max results
        offset: Pagination offset
        service: Download service
        
    Returns:
        List of downloads
    """
    downloads = await service.get_downloads(
        status=status,
        limit=limit,
        offset=offset,
    )
    total = await service.count_downloads(status=status)
    
    return DownloadListResponse(
        items=[DownloadResponse.from_entity(d) for d in downloads],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.get("/downloads/{download_id}", response_model=DownloadResponse)
async def get_download(
    download_id: str,
    service: DownloadService = Depends(get_download_service),
) -> DownloadResponse:
    """
    Get download by ID.
    
    Args:
        download_id: Download ID
        service: Download service
        
    Returns:
        Download details
    """
    download = await service.get_download(download_id)
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
    
    return DownloadResponse.from_entity(download)

@router.delete("/downloads/{download_id}", status_code=204)
async def cancel_download(
    download_id: str,
    service: DownloadService = Depends(get_download_service),
) -> None:
    """
    Cancel a download.
    
    Args:
        download_id: Download ID
        service: Download service
    """
    success = await service.cancel_download(download_id)
    if not success:
        raise HTTPException(status_code=404, detail="Download not found")

@router.patch("/downloads/{download_id}/priority")
async def update_priority(
    download_id: str,
    request: UpdatePriorityRequest,
    service: DownloadService = Depends(get_download_service),
) -> DownloadResponse:
    """
    Update download priority.
    
    Args:
        download_id: Download ID
        request: New priority
        service: Download service
        
    Returns:
        Updated download
    """
    download = await service.update_priority(
        download_id, request.priority
    )
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
    
    return DownloadResponse.from_entity(download)
```

---

## 6. Events and Integration

### 6.1 Events Published

```yaml
# modules/soulseek/contracts/events.yaml

events:
  download.started:
    version: 1.0.0
    description: "Triggered when a download starts"
    producer: soulseek
    consumers: [dashboard, notifications]
    schema:
      download_id: string
      track_id: string
      filename: string
      timestamp: datetime
  
  download.progress:
    version: 1.0.0
    description: "Periodic progress updates"
    producer: soulseek
    consumers: [dashboard]
    schema:
      download_id: string
      progress_percent: float
      speed_kbps: float
      eta_seconds: integer
      timestamp: datetime
  
  download.completed:
    version: 1.0.0
    description: "Triggered when download completes successfully"
    producer: soulseek
    consumers: [metadata, library, dashboard, notifications]
    schema:
      download_id: string
      track_id: string
      file_path: string
      file_size: integer
      timestamp: datetime
  
  download.failed:
    version: 1.0.0
    description: "Triggered when download fails"
    producer: soulseek
    consumers: [dashboard, notifications]
    schema:
      download_id: string
      track_id: string
      error: string
      can_retry: boolean
      retry_count: integer
      timestamp: datetime
```

### 6.2 Events Consumed

```yaml
# Events from other modules
consumes:
  track.metadata_enriched:
    version: 1.0.0
    producer: metadata
    description: "Track metadata has been enriched"
    handler: "on_track_metadata_enriched"
    action: "Update track info in download records"
  
  library.file_moved:
    version: 1.0.0
    producer: library
    description: "Downloaded file has been moved to library"
    handler: "on_file_moved"
    action: "Update download record with final path"
```

---

## 7. Configuration

```python
# modules/soulseek/backend/config/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class SoulseekSettings(BaseSettings):
    """
    Soulseek module configuration.
    
    Hey future me, these settings control slskd integration and download behavior.
    SLSKD_URL and SLSKD_API_KEY are REQUIRED - the app won't work without them!
    Adjust MAX_CONCURRENT based on your network speed and slskd capacity.
    """
    
    # slskd connection
    slskd_url: str = "http://localhost:5030"
    slskd_api_key: str  # REQUIRED
    slskd_timeout_seconds: int = 30
    
    # Download settings
    download_dir: Path = Path("/mnt/downloads")
    max_concurrent_downloads: int = 3
    max_retries: int = 3
    
    # Search settings
    search_timeout_seconds: int = 10
    max_search_results: int = 50
    min_bitrate_kbps: int = 128
    
    # Quality preferences
    prefer_lossless: bool = True
    prefer_high_quality: bool = True
    
    # Performance
    progress_update_interval_seconds: int = 2
    health_check_interval_seconds: int = 60
    
    model_config = SettingsConfigDict(
        env_prefix="SLSKD_",
        env_file=".env",
        case_sensitive=False,
    )

settings = SoulseekSettings()
```

---

## 8. Frontend Components

### 8.1 Downloads Page

```html
<!-- modules/soulseek/frontend/pages/downloads.html -->
{% extends "layouts/base.html" %}

{% block title %}Downloads - SoulSpot{% endblock %}

{% block extra_css %}
    <link rel="stylesheet" href="/soulseek/static/styles/soulseek.css">
{% endblock %}

{% block content %}
<div class="container mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold">Downloads</h1>
        
        <div class="flex gap-4">
            <button hx-get="/soulseek/downloads/queue"
                    hx-target="#download-list"
                    hx-swap="innerHTML"
                    class="btn btn-primary">
                Refresh
            </button>
            
            <a href="/soulseek/search" class="btn btn-secondary">
                Search Tracks
            </a>
        </div>
    </div>
    
    <!-- Statistics Widget -->
    {% include "modules/soulseek/frontend/widgets/download_stats.html" %}
    
    <!-- Active Downloads Widget -->
    <div class="mt-6">
        {% include "modules/soulseek/frontend/widgets/active_downloads.html" %}
    </div>
    
    <!-- Download Queue Widget -->
    <div class="mt-6">
        {% include "modules/soulseek/frontend/widgets/download_queue.html" %}
    </div>
</div>
{% endblock %}

{% block extra_js %}
    <script src="/soulseek/static/scripts/downloads.js"></script>
    <script src="/soulseek/static/scripts/sse_handler.js"></script>
{% endblock %}
```

### 8.2 Download Queue Widget

```html
<!-- modules/soulseek/frontend/widgets/download_queue.html -->
<div class="download-queue-widget card">
    <div class="card-header">
        <h2 class="text-xl font-semibold">Download Queue</h2>
        <span class="badge">{{ downloads|length }} items</span>
    </div>
    
    <div class="card-body">
        <div id="download-list"
             hx-get="/soulseek/downloads?status=queued"
             hx-trigger="load, every 5s"
             hx-swap="innerHTML">
            Loading...
        </div>
    </div>
</div>
```

### 8.3 Download Item Partial

```html
<!-- modules/soulseek/frontend/partials/download_item.html -->
<div class="download-item" data-download-id="{{ download.id }}">
    <div class="download-info">
        <div class="filename">{{ download.filename }}</div>
        <div class="metadata text-sm text-gray-600">
            {{ download.file_size|filesizeformat }} •
            {{ download.quality }} •
            {{ download.username }}
        </div>
    </div>
    
    <div class="download-progress">
        {% include "modules/soulseek/frontend/partials/progress_bar.html" %}
        
        <div class="progress-details text-sm">
            {{ download.progress_percent|round(1) }}% •
            {{ download.download_speed_kbps|round(0) }} KB/s •
            ETA: {{ download.calculate_eta_seconds()|format_duration }}
        </div>
    </div>
    
    <div class="download-actions">
        {% if download.status == "in_progress" %}
            <button hx-post="/soulseek/downloads/{{ download.id }}/pause"
                    hx-swap="outerHTML"
                    class="btn btn-sm">
                Pause
            </button>
        {% elif download.status == "paused" %}
            <button hx-post="/soulseek/downloads/{{ download.id }}/resume"
                    hx-swap="outerHTML"
                    class="btn btn-sm">
                Resume
            </button>
        {% endif %}
        
        <button hx-delete="/soulseek/downloads/{{ download.id }}"
                hx-confirm="Cancel this download?"
                hx-target="closest .download-item"
                hx-swap="outerHTML swap:1s"
                class="btn btn-sm btn-danger">
            Cancel
        </button>
    </div>
</div>
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# modules/soulseek/tests/unit/test_download_entity.py

import pytest
from datetime import datetime
from pathlib import Path
from ...backend.domain.entities import Download
from ...backend.domain.value_objects import (
    DownloadId,
    DownloadStatus,
    DownloadPriority,
    FileQuality,
)
from ...backend.domain.exceptions import DownloadValidationError

class TestDownloadEntity:
    """Tests for Download entity."""
    
    def test_create_download(self):
        """Test download creation."""
        download = Download(
            id=DownloadId("dl-123"),
            track_id="track-456",
            username="testuser",
            filename="test.mp3",
            file_size=5000000,
            quality=FileQuality.HIGH,
        )
        
        assert download.status == DownloadStatus.QUEUED
        assert download.progress_percent == 0.0
        assert download.retry_count == 0
    
    def test_start_download(self):
        """Test starting a download."""
        download = Download(
            id=DownloadId("dl-123"),
            track_id="track-456",
            username="testuser",
            filename="test.mp3",
            file_size=5000000,
            quality=FileQuality.HIGH,
        )
        
        temp_path = Path("/tmp/dl-123")
        download.start(temp_path)
        
        assert download.status == DownloadStatus.IN_PROGRESS
        assert download.temp_path == temp_path
        assert download.started_at is not None
    
    def test_cannot_start_non_queued_download(self):
        """Test that non-queued downloads cannot be started."""
        download = Download(
            id=DownloadId("dl-123"),
            track_id="track-456",
            username="testuser",
            filename="test.mp3",
            file_size=5000000,
            quality=FileQuality.HIGH,
            status=DownloadStatus.COMPLETED,
        )
        
        with pytest.raises(DownloadValidationError):
            download.start(Path("/tmp/test"))
    
    def test_update_progress(self):
        """Test progress updates."""
        download = Download(
            id=DownloadId("dl-123"),
            track_id="track-456",
            username="testuser",
            filename="test.mp3",
            file_size=10000000,  # 10 MB
            quality=FileQuality.HIGH,
            status=DownloadStatus.IN_PROGRESS,
        )
        
        # Update to 50% downloaded
        download.update_progress(
            bytes_downloaded=5000000,
            speed_kbps=500.0
        )
        
        assert download.progress_percent == pytest.approx(50.0)
        assert download.bytes_downloaded == 5000000
        assert download.download_speed_kbps == 500.0
    
    def test_complete_download(self):
        """Test completing a download."""
        download = Download(
            id=DownloadId("dl-123"),
            track_id="track-456",
            username="testuser",
            filename="test.mp3",
            file_size=5000000,
            quality=FileQuality.HIGH,
            status=DownloadStatus.IN_PROGRESS,
        )
        
        final_path = Path("/music/test.mp3")
        download.complete(final_path)
        
        assert download.status == DownloadStatus.COMPLETED
        assert download.target_path == final_path
        assert download.progress_percent == 100.0
        assert download.completed_at is not None
    
    def test_retry_failed_download(self):
        """Test retrying a failed download."""
        download = Download(
            id=DownloadId("dl-123"),
            track_id="track-456",
            username="testuser",
            filename="test.mp3",
            file_size=5000000,
            quality=FileQuality.HIGH,
            status=DownloadStatus.FAILED,
            retry_count=1,
            max_retries=3,
        )
        
        assert download.can_retry() is True
        
        download.retry()
        
        assert download.status == DownloadStatus.QUEUED
        assert download.progress_percent == 0.0
        assert download.retry_count == 1  # Doesn't reset
    
    def test_cannot_retry_after_max_retries(self):
        """Test that downloads cannot be retried indefinitely."""
        download = Download(
            id=DownloadId("dl-123"),
            track_id="track-456",
            username="testuser",
            filename="test.mp3",
            file_size=5000000,
            quality=FileQuality.HIGH,
            status=DownloadStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )
        
        assert download.can_retry() is False
        
        with pytest.raises(DownloadValidationError):
            download.retry()
```

### 9.2 Integration Tests

```python
# modules/soulseek/tests/integration/test_download_flow.py

import pytest
from pathlib import Path
from ...backend.application.services import DownloadService
from ...backend.domain.value_objects import FileQuality

@pytest.mark.asyncio
class TestDownloadFlow:
    """Integration tests for download flow."""
    
    async def test_complete_download_flow(
        self,
        download_service: DownloadService,
        mock_slskd_client,
        mock_event_bus,
    ):
        """Test complete download flow from queue to completion."""
        # Queue download
        download = await download_service.queue_download(
            track_id="track-123",
            username="testuser",
            filename="test.mp3",
            file_size=5000000,
            quality=FileQuality.HIGH,
            priority=10,
        )
        
        assert download.status == "queued"
        
        # Start download
        await download_service.start_download(download.id)
        
        # Verify slskd was called
        mock_slskd_client.start_download.assert_called_once()
        
        # Verify event was published
        events = mock_event_bus.get_published_events()
        assert len(events) == 1
        assert events[0]["type"] == "download.started"
        
        # Simulate progress updates
        await download_service.update_progress(
            download.id,
            bytes_downloaded=2500000,
            speed_kbps=500.0
        )
        
        # Complete download
        final_path = Path("/music/test.mp3")
        await download_service.complete_download(
            download.id,
            final_path
        )
        
        # Verify completion event
        events = mock_event_bus.get_published_events()
        completion_events = [
            e for e in events if e["type"] == "download.completed"
        ]
        assert len(completion_events) == 1
        assert completion_events[0]["data"]["file_path"] == str(final_path)
```

---

## 10. Module Documentation & Changelog

### 10.1 CHANGELOG.md

**Location:** `modules/soulseek/CHANGELOG.md`

```markdown
# Changelog - Soulseek Module

All notable changes to the Soulseek module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this module adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- BitRate filtering in search results
- Download history export
- Batch download support

## [1.0.0] - 2025-12-01

### Added
- Initial module implementation
- Search functionality with quality ranking
- Download queue management with priority support
- Real-time progress monitoring via SSE
- Circuit breaker pattern for slskd API calls
- Automatic retry mechanism for failed downloads
- Integration with Module Router for coordinated downloads
- Event-based notifications (download.started, download.completed, download.failed)
- Health monitoring for slskd connection
- Download statistics and reporting
- HTMX-based frontend (search interface, download queue widget, progress display)

### Architecture
- Domain-driven design with clean architecture
- Separation: Domain → Application → Infrastructure → API
- Repository pattern for data access
- Event sourcing for download state changes
- Circuit breaker for external API resilience

### Events Published
- `soulseek.download.started` - When download begins
- `soulseek.download.progress` - Progress updates (every 5 seconds)
- `soulseek.download.completed` - Download successful
- `soulseek.download.failed` - Download failed

### Events Subscribed
- None (standalone module)

### Dependencies
- slskd >= 0.18.0
- Module Router (for coordinated flows)
- Core module (shared utilities)

### Breaking Changes
- N/A (initial release)

### Migration Guide
- Fresh installation - no migration required
- Database tables created automatically on first run
```

### 10.2 Module Documentation (docs/)

#### docs/architecture.md

**Location:** `modules/soulseek/docs/architecture.md`

```markdown
# Soulseek Module - Architecture Documentation

## Overview

The Soulseek module manages all Soulseek P2P network interactions for music downloads.
It demonstrates the reference architecture for SoulSpot Version 3.0 modules.

## Architecture Diagram

```
┌──────────────────────────────────────────────────┐
│              Frontend (HTMX)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Search  │  │ Download │  │ Progress │      │
│  │  Page    │  │  Queue   │  │  Widget  │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└────────────────────┬─────────────────────────────┘
                     │ HTTP / SSE
┌────────────────────┴─────────────────────────────┐
│              API Layer (FastAPI)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Search   │  │ Download │  │  Health  │      │
│  │ Routes   │  │  Routes  │  │  Routes  │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────┴─────────────────────────────┐
│         Application Layer (Services)             │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ Download     │  │  Search      │             │
│  │ Service      │  │  Service     │             │
│  └──────────────┘  └──────────────┘             │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────┴─────────────────────────────┐
│            Domain Layer (Entities)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Download │  │  Search  │  │  slskd   │      │
│  │ Entity   │  │  Result  │  │  Client  │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────┴─────────────────────────────┐
│       Infrastructure (Persistence & APIs)        │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ Download     │  │  slskd API   │             │
│  │ Repository   │  │  Client      │             │
│  └──────────────┘  └──────────────┘             │
└──────────────────────────────────────────────────┘
```

## Design Decisions

### 1. Separation of Download and SearchResult

**Decision:** Keep Download and SearchResult as separate entities.

**Rationale:**
- SearchResult is ephemeral (cached for minutes)
- Download is persistent (stored for lifetime)
- Different state machines and lifecycles
- SearchResult can have hundreds of results, Download only stores initiated ones

**Alternatives Considered:**
- Single entity with optional download_id - rejected due to lifecycle mismatch
- Embedded SearchResult in Download - rejected to avoid data duplication

### 2. Circuit Breaker for slskd API

**Decision:** Wrap all slskd API calls with circuit breaker pattern.

**Rationale:**
- slskd can become temporarily unresponsive (network issues, overload)
- Prevents cascading failures in our application
- Allows graceful degradation (show cached data, queue requests)
- Improves user experience (fast failures vs. timeouts)

**Implementation:**
- 5 failures threshold
- 30-second recovery time
- Fallback: show last known status, queue actions

### 3. Event-Driven Post-Processing

**Decision:** Publish events on download completion rather than direct calls.

**Rationale:**
- Loose coupling with metadata/library modules
- Modules can be added/removed without code changes
- Retry/recovery easier with event queue
- Enables future features (webhooks, notifications)

**Events:**
- `download.completed` → Metadata module enriches file
- `download.completed` → Library module imports file
- `download.completed` → Notification module alerts user

### 4. Repository Pattern

**Decision:** Use repository pattern for data access.

**Rationale:**
- Isolates domain from infrastructure concerns
- Easy to mock for testing
- Future-proof (can swap SQLAlchemy for other ORMs)
- Clean architecture principle

## State Machine

### Download State Transitions

```
PENDING
  │
  ├──> QUEUED ──────> DOWNLOADING ──────> COMPLETED
  │      │               │                    
  │      │               │                    
  │      └──> PAUSED ────┘                    
  │                                           
  └──────────────────────────────────────> FAILED
                                              │
                                              └──> RETRYING ──> PENDING
```

**States:**
- PENDING: Download requested, not yet queued
- QUEUED: In queue, waiting for slot
- DOWNLOADING: Actively downloading
- PAUSED: User paused download
- COMPLETED: Successfully completed
- FAILED: Failed (network error, file not found)
- RETRYING: Automatic retry in progress

## Error Handling Strategy

1. **Network Errors**: Retry with exponential backoff (3 attempts)
2. **File Not Found**: Mark failed immediately, log event
3. **slskd Unreachable**: Circuit breaker triggers, queue requests
4. **Disk Full**: Pause all downloads, alert user
5. **Validation Failure**: Mark failed, publish event for cleanup

## Performance Considerations

1. **Concurrent Downloads**: Max 5 simultaneous downloads (configurable)
2. **Search Result Caching**: 5 minutes (memory cache)
3. **Database Queries**: Indexed on status, created_at, track_id
4. **SSE Updates**: Throttled to 1 update per 5 seconds per download
5. **Event Publishing**: Async, non-blocking

## Security Considerations

1. **slskd API Key**: Stored encrypted, never logged
2. **File Path Validation**: Prevent directory traversal attacks
3. **Rate Limiting**: Max 100 searches per hour per user
4. **Download Limits**: Max 1000 pending downloads per user

## Testing Strategy

1. **Unit Tests**: 80%+ coverage requirement
2. **Integration Tests**: Repository + slskd client mocked
3. **E2E Tests**: Full flow with test slskd instance
4. **Performance Tests**: Load testing with 100 concurrent downloads
```

#### docs/api.md

**Location:** `modules/soulseek/docs/api.md`

```markdown
# Soulseek Module - API Documentation

## Base URL

`/api/soulseek`

## Authentication

All endpoints require authentication via session cookie or API key.

## Endpoints

### Search Tracks

**POST** `/search`

Search for tracks on the Soulseek network.

**Request Body:**
```json
{
  "query": "The Beatles - Let It Be",
  "max_results": 50
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "result-123",
      "username": "musiclover",
      "filename": "The Beatles - Let It Be.mp3",
      "size_bytes": 8421376,
      "bitrate": 320,
      "sample_rate": 44100,
      "duration_seconds": 243,
      "quality_score": 95
    }
  ],
  "total": 142,
  "cached": false
}
```

**Quality Score:**
- 90-100: Excellent (320kbps+, complete metadata)
- 70-89: Good (256-320kbps, good metadata)
- 50-69: Fair (192-255kbps, partial metadata)
- 0-49: Poor (<192kbps or missing metadata)

### Start Download

**POST** `/downloads`

Start a new download.

**Request Body:**
```json
{
  "result_id": "result-123",
  "track_id": "spotify:track:abc123",
  "priority": 5
}
```

**Response:**
```json
{
  "download_id": "dl-456",
  "status": "queued",
  "position_in_queue": 3
}
```

### Get Download Status

**GET** `/downloads/{download_id}`

**Response:**
```json
{
  "download_id": "dl-456",
  "status": "downloading",
  "progress_percent": 45,
  "bytes_downloaded": 3789312,
  "bytes_total": 8421376,
  "speed_bytes_per_sec": 524288,
  "eta_seconds": 8,
  "file_path": null
}
```

### List Downloads

**GET** `/downloads`

**Query Parameters:**
- `status` (optional): Filter by status (pending, queued, downloading, completed, failed)
- `limit` (optional): Max results (default 50, max 100)
- `offset` (optional): Pagination offset

**Response:**
```json
{
  "downloads": [...],
  "total": 123,
  "limit": 50,
  "offset": 0
}
```

### Pause Download

**POST** `/downloads/{download_id}/pause`

**Response:**
```json
{
  "download_id": "dl-456",
  "status": "paused"
}
```

### Resume Download

**POST** `/downloads/{download_id}/resume`

**Response:**
```json
{
  "download_id": "dl-456",
  "status": "downloading"
}
```

### Cancel Download

**DELETE** `/downloads/{download_id}`

**Response:**
```json
{
  "download_id": "dl-456",
  "status": "cancelled"
}
```

### Health Check

**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "module": "soulseek",
  "version": "1.0.0",
  "slskd": {
    "connected": true,
    "version": "0.18.0",
    "uptime_seconds": 86400
  }
}
```

### Progress Stream (SSE)

**GET** `/downloads/{download_id}/stream`

Server-Sent Events stream for real-time progress updates.

**Event Format:**
```
event: progress
data: {"download_id": "dl-456", "progress_percent": 47, "speed_bytes_per_sec": 524288}

event: completed
data: {"download_id": "dl-456", "file_path": "/music/beatles.mp3"}

event: failed
data: {"download_id": "dl-456", "error": "File not found"}
```

## Error Responses

All endpoints return standardized error responses:

```json
{
  "error": {
    "code": "DOWNLOAD_NOT_FOUND",
    "message": "Download dl-999 not found",
    "details": {}
  }
}
```

**Error Codes:**
- `DOWNLOAD_NOT_FOUND`: Download ID doesn't exist
- `SEARCH_FAILED`: Search request failed
- `SLSKD_UNREACHABLE`: Cannot connect to slskd
- `QUEUE_FULL`: Download queue is full
- `INVALID_REQUEST`: Request validation failed
```

#### docs/events.md

**Location:** `modules/soulseek/docs/events.md`

```markdown
# Soulseek Module - Event Schemas

## Published Events

### soulseek.download.started

Published when a download begins.

**Schema:**
```json
{
  "event_type": "soulseek.download.started",
  "event_version": "1.0",
  "timestamp": "2025-11-21T10:30:00Z",
  "data": {
    "download_id": "dl-456",
    "track_id": "spotify:track:abc123",
    "filename": "The Beatles - Let It Be.mp3",
    "size_bytes": 8421376,
    "user_id": "user-789"
  }
}
```

### soulseek.download.progress

Published every 5 seconds during download.

**Schema:**
```json
{
  "event_type": "soulseek.download.progress",
  "event_version": "1.0",
  "timestamp": "2025-11-21T10:30:15Z",
  "data": {
    "download_id": "dl-456",
    "progress_percent": 45,
    "bytes_downloaded": 3789312,
    "speed_bytes_per_sec": 524288,
    "eta_seconds": 8
  }
}
```

### soulseek.download.completed

Published when download completes successfully.

**Schema:**
```json
{
  "event_type": "soulseek.download.completed",
  "event_version": "1.0",
  "timestamp": "2025-11-21T10:35:00Z",
  "data": {
    "download_id": "dl-456",
    "track_id": "spotify:track:abc123",
    "file_path": "/music/downloads/The Beatles - Let It Be.mp3",
    "size_bytes": 8421376,
    "duration_seconds": 243,
    "user_id": "user-789"
  }
}
```

**Subscribers:**
- **Metadata Module**: Enriches file with MusicBrainz/CoverArt data
- **Library Module**: Imports file into user library
- **Notification Module**: Sends completion notification to user
- **Router**: Coordinates post-processing pipeline

### soulseek.download.failed

Published when download fails.

**Schema:**
```json
{
  "event_type": "soulseek.download.failed",
  "event_version": "1.0",
  "timestamp": "2025-11-21T10:35:00Z",
  "data": {
    "download_id": "dl-456",
    "track_id": "spotify:track:abc123",
    "error_code": "FILE_NOT_FOUND",
    "error_message": "File no longer available from user",
    "retry_count": 2,
    "user_id": "user-789"
  }
}
```

## Subscribed Events

This module does not currently subscribe to any events. It operates independently.

## Event Versioning

Events follow semantic versioning:
- **Major version** change: Breaking schema changes (field removals, type changes)
- **Minor version** change: New optional fields
- **Patch version** change: Documentation updates only

Current version: `1.0`
```

## 11. Deployment and Migration

### 10.1 Database Migration

```python
# alembic/versions/xxx_add_soulseek_tables.py

"""Add Soulseek module tables

Revision ID: xxx
Revises: yyy
Create Date: 2025-11-21
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    """Add Soulseek downloads table."""
    op.create_table(
        'soulseek_downloads',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('track_id', sa.String(100), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('file_size', sa.BigInteger, nullable=False),
        sa.Column('quality', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('progress_percent', sa.Float, default=0.0),
        sa.Column('bytes_downloaded', sa.BigInteger, default=0),
        sa.Column('download_speed_kbps', sa.Float, default=0.0),
        sa.Column('target_path', sa.String(1000), nullable=True),
        sa.Column('temp_path', sa.String(1000), nullable=True),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('max_retries', sa.Integer, default=3),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for common queries
    op.create_index(
        'idx_downloads_status',
        'soulseek_downloads',
        ['status']
    )
    op.create_index(
        'idx_downloads_track',
        'soulseek_downloads',
        ['track_id']
    )

def downgrade():
    """Remove Soulseek downloads table."""
    op.drop_index('idx_downloads_track')
    op.drop_index('idx_downloads_status')
    op.drop_table('soulseek_downloads')
```

### 10.2 Module Registration

```python
# src/soulspot/main.py

from fastapi import FastAPI
from modules.soulseek import Module as SoulseekModule

app = FastAPI(title="SoulSpot")

# Register Soulseek module
app.include_router(
    SoulseekModule.router,
    prefix="/api",  # Soulseek router already has /soulseek prefix
)

# Mount static files
app.mount(
    "/soulseek/static",
    StaticFiles(directory="modules/soulseek/frontend"),
    name="soulseek_static"
)
```

---

## 11. Monitoring and Metrics

### 11.1 Key Metrics

- **Download Queue Length**: Number of queued downloads
- **Active Downloads**: Number of in-progress downloads
- **Success Rate**: Completed / (Completed + Failed)
- **Average Download Time**: Mean time from queue to completion
- **Retry Rate**: Number of retries / Total downloads
- **slskd Health**: Circuit breaker status, response times

### 11.2 Health Checks

```python
@router.get("/health")
async def health_check(
    service: DownloadService = Depends(get_download_service)
) -> dict:
    """Module health check."""
    try:
        # Check slskd connection
        await service.check_slskd_health()
        
        # Get queue stats
        stats = await service.get_queue_stats()
        
        return {
            "status": "healthy",
            "module": "soulseek",
            "version": "1.0.0",
            "details": {
                "slskd_connected": True,
                "active_downloads": stats.active,
                "queued_downloads": stats.queued,
                "failed_downloads": stats.failed,
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "module": "soulseek",
            "error": str(e)
        }
```

---

## 12. Security Considerations

### 12.1 Input Validation

- Validate all search queries (prevent injection)
- Sanitize filenames (prevent path traversal)
- Validate file sizes (prevent resource exhaustion)
- Rate limit search requests

### 12.2 File Safety

- Scan downloaded files for malware
- Validate audio file formats
- Check file extensions match content
- Limit file sizes

### 12.3 Network Security

- Use HTTPS for slskd connection
- Validate SSL certificates
- Store API keys securely (env vars)
- Implement circuit breaker for rate limiting

---

## 13. Performance Optimization

### 13.1 Database Queries

- Index on status and track_id
- Batch update progress (every 2s, not every packet)
- Use database triggers for updated_at
- Archive completed downloads periodically

### 13.2 Caching

- Cache search results (5 minutes)
- Cache slskd health status (1 minute)
- Cache active downloads count

### 13.3 Concurrency

- Limit concurrent downloads (configured)
- Use connection pooling for database
- Async I/O for all network calls
- Background workers for heavy operations

---

## 14. Future Enhancements

### 14.1 Planned Features

- **Download Scheduling**: Schedule downloads for off-peak hours
- **Bandwidth Limiting**: Limit download speed
- **Source Selection**: Prefer specific users or servers
- **Advanced Filters**: Filter by file format, bitrate range
- **Batch Operations**: Download entire albums/playlists
- **Download History**: Track historical downloads

### 14.2 Integration Points

- **Metadata Module**: Auto-enrich on download completion
- **Library Module**: Auto-import to library
- **Notification Module**: Push notifications for completions
- **Analytics Module**: Track download statistics

---

## 15. Summary

The Soulseek module demonstrates:

✅ **Complete modular architecture** with all layers  
✅ **Clean separation** of concerns (domain, application, infrastructure)  
✅ **Event-driven** communication with other modules  
✅ **Comprehensive testing** strategy  
✅ **Production-ready** error handling and monitoring  
✅ **Developer-friendly** documentation and examples  
✅ **Security-conscious** design patterns  
✅ **Performance-optimized** database and caching  

This module serves as the **blueprint** for all future modules in the system.

---

**Related Documents:**
- [Roadmap](./ROADMAP.md)
- [Architecture](./ARCHITECTURE.md)
- [Module Specification](./MODULE_SPECIFICATION.md)
- [Module Communication](./MODULE_COMMUNICATION.md)

**Status:** ✅ Complete - Design Phase
