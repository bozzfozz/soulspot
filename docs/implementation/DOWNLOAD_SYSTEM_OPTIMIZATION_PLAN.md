# 📋 Download System - Vollständiger Optimierungsplan

> **Erstellt:** 2025-12-22  
> **Status:** Planung abgeschlossen - Ready for Implementation  
> **Priorität:** HIGH (Core Feature)

---

## 📑 Inhaltsverzeichnis

1. [Executive Summary](#executive-summary)
2. [Aktueller Stand (IST-Analyse)](#aktueller-stand-ist-analyse)
3. [Zielarchitektur (SOLL)](#zielarchitektur-soll)
4. [Implementierungsphasen](#implementierungsphasen)
5. [Phase 1: Core Robustheit](#phase-1-core-robustheit)
6. [Phase 2: Queue Management](#phase-2-queue-management)
7. [Phase 3: Quality & Post-Processing](#phase-3-quality--post-processing)
8. [Phase 4: UX & Monitoring](#phase-4-ux--monitoring)
9. [Phase 5: Advanced Features](#phase-5-advanced-features)
10. [Datenbank-Migrationen](#datenbank-migrationen)
11. [Testing-Strategie](#testing-strategie)
12. [Rollout-Plan](#rollout-plan)
13. [Risiken & Mitigationen](#risiken--mitigationen)

---

## Executive Summary

### Projektziel
Transformation des SoulSpot Download-Systems von einem funktionalen MVP zu einem robusten, skalierbaren Download-Manager auf Produktions-Niveau.

### Hauptziele
1. **Robustheit** - Auto-Retry, Blocklist, Circuit Breaker Verbesserungen
2. **Persistenz** - Jobs überleben Neustarts
3. **Skalierbarkeit** - Concurrent Limits, Queue Management
4. **UX** - Batch Operations, Statistiken, Notifications
5. **Qualität** - Quality Profiles, Post-Processing

### Geschätzter Aufwand
- **Phase 1-2:** 2-3 Wochen (Core Features)
- **Phase 3-4:** 2-3 Wochen (Enhancement)
- **Phase 5:** 2-4 Wochen (Advanced, optional)
- **Gesamt:** 6-10 Wochen

---

## Aktueller Stand (IST-Analyse)

### ✅ Bereits implementiert

| Feature | Status | Datei(en) |
|---------|--------|-----------|
| Download Entity & Status | ✅ | `domain/entities/__init__.py` |
| JobQueue (In-Memory) | ✅ | `application/workers/job_queue.py` |
| slskd Client | ✅ | `infrastructure/integrations/slskd_client.py` |
| QueueDispatcherWorker | ✅ | `application/workers/queue_dispatcher_worker.py` |
| DownloadWorker | ✅ | `application/workers/download_worker.py` |
| DownloadStatusSyncWorker | ✅ | `application/workers/download_status_sync_worker.py` |
| Circuit Breaker | ✅ | In StatusSyncWorker integriert |
| SSE Live Updates | ✅ | `api/routers/download_manager.py` |
| Basic REST API | ✅ | `api/routers/downloads.py` |
| Priority System | ✅ | `Download.priority` (0-2) |

### ⚠️ Teilweise implementiert

| Feature | Status | Problem |
|---------|--------|---------|
| Retry Logic | ⚠️ | `Job.max_retries` existiert, aber kein Exponential Backoff in Download |
| Pause/Resume | ⚠️ | Pause Global ja, Resume einzelner Downloads fehlt |
| Statistics | ⚠️ | Basic Stats, aber keine Historie/Charts |

### ❌ Nicht implementiert

| Feature | Priorität | Beschreibung |
|---------|-----------|--------------|
| Job Persistenz | P0 | Jobs gehen bei Restart verloren |
| Auto-Retry für Downloads | P0 | Download-Entity hat kein retry_count |
| Blocklist | P1 | Keine Möglichkeit, fehlgeschlagene Quellen zu blocken |
| Batch Operations | P1 | Keine Multi-Select Aktionen |
| Quality Profiles | P2 | Nur "best/good/any" |
| Post-Processing | P2 | Kein Auto-Move, Rename, Tagging |
| Notifications | P2 | Keine Benachrichtigungen |
| Concurrent Limits | P1 | Existiert, aber keine Config im Settings UI |

---

## Zielarchitektur (SOLL)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ Downloads API   │  │ Batch API       │  │ Settings API    │                  │
│  │ POST/GET/DELETE │  │ POST /batch     │  │ Quality Profiles│                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                      │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         DownloadManagerService                            │   │
│  │  • queue_download()     • get_active_downloads()    • batch_action()     │   │
│  │  • cancel_download()    • get_stats()               • update_settings()   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ QueueDispatcher│  │ DownloadWorker │  │ StatusSync     │  │ PostProcess  │  │
│  │ Worker         │  │                │  │ Worker         │  │ Worker (NEU) │  │
│  │ WAITING→PENDING│  │ PENDING→QUEUED │  │ slskd→DB Sync  │  │ Move/Tag/... │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  └──────────────┘  │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    PersistentJobQueue (NEU)                               │   │
│  │  • SQLite/PostgreSQL Backend       • Jobs überleben Restart              │   │
│  │  • Exponential Backoff             • Concurrent Limits                   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DOMAIN LAYER                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ Download Entity │  │ QualityProfile  │  │ Blocklist Entry │                  │
│  │ + retry_count   │  │ (NEU)           │  │ (NEU)           │                  │
│  │ + next_retry_at │  │                 │  │                 │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                            Domain Ports                                    │   │
│  │  IDownloadRepository  │  IBlocklistRepository  │  INotificationProvider  │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ slskd Client   │  │ PostgreSQL     │  │ Mutagen        │  │ Notification │  │
│  │ (existiert)    │  │ Repositories   │  │ (ID3 Tagging)  │  │ Providers    │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementierungsphasen

```
Woche 1-2:  ████████████████░░░░ Phase 1: Core Robustheit
Woche 3-4:  ░░░░████████████████ Phase 2: Queue Management
Woche 5-6:  ░░░░░░░░████████████ Phase 3: Quality & Post-Processing
Woche 7-8:  ░░░░░░░░░░░░████████ Phase 4: UX & Monitoring
Woche 9+:   ░░░░░░░░░░░░░░░░████ Phase 5: Advanced (Optional)
```

---

## Phase 1: Core Robustheit

**Zeitrahmen:** Woche 1-2  
**Priorität:** P0 - KRITISCH

### 1.1 Auto-Retry mit Exponential Backoff

**Problem:** Fehlgeschlagene Downloads bleiben im FAILED Status

**Lösung:**

#### A) Download Entity erweitern

```python
# src/soulspot/domain/entities/__init__.py

@dataclass
class Download:
    # ... bestehende Felder ...
    
    # NEU: Retry-Management
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: datetime | None = None
    last_error_code: str | None = None  # z.B. "SOURCE_OFFLINE", "TIMEOUT", "RATE_LIMITED"
    
    def should_retry(self) -> bool:
        """Check if download should be retried."""
        if self.status != DownloadStatus.FAILED:
            return False
        if self.retry_count >= self.max_retries:
            return False
        # Bestimmte Fehler nicht retrien
        non_retryable = ["FILE_NOT_FOUND", "USER_BLOCKED"]
        if self.last_error_code in non_retryable:
            return False
        return True
    
    def schedule_retry(self) -> None:
        """Schedule next retry with exponential backoff."""
        if not self.should_retry():
            raise ValueError("Download should not be retried")
        
        # Backoff: 1min, 5min, 15min
        backoff_minutes = [1, 5, 15]
        delay_minutes = backoff_minutes[min(self.retry_count, len(backoff_minutes) - 1)]
        
        self.retry_count += 1
        self.next_retry_at = datetime.now(UTC) + timedelta(minutes=delay_minutes)
        self.status = DownloadStatus.WAITING  # Zurück in Queue
        self.updated_at = datetime.now(UTC)
```

#### B) DownloadModel erweitern

```python
# src/soulspot/infrastructure/persistence/models.py

class DownloadModel(Base):
    # ... bestehende Felder ...
    
    # NEU
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

#### C) RetrySchedulerWorker (NEU)

```python
# src/soulspot/application/workers/retry_scheduler_worker.py

class RetrySchedulerWorker:
    """Schedules retries for failed downloads.
    
    Hey future me - dieser Worker wacht über FAILED Downloads!
    Alle X Sekunden schaut er nach Downloads die:
    1. Status = FAILED
    2. retry_count < max_retries  
    3. next_retry_at <= now
    
    Dann: Status → WAITING, QueueDispatcher holt sie wieder ab.
    """
    
    def __init__(
        self,
        session_factory: async_sessionmaker,
        check_interval: int = 30,
    ):
        self._session_factory = session_factory
        self._check_interval = check_interval
        self._running = False
    
    async def start(self) -> None:
        self._running = True
        while self._running:
            await self._process_retries()
            await asyncio.sleep(self._check_interval)
    
    async def _process_retries(self) -> None:
        async with self._session_factory() as session:
            # Hole alle retry-fähigen Downloads
            result = await session.execute(
                select(DownloadModel)
                .where(
                    DownloadModel.status == DownloadStatus.FAILED.value,
                    DownloadModel.retry_count < DownloadModel.max_retries,
                    DownloadModel.next_retry_at <= datetime.now(UTC),
                )
                .order_by(DownloadModel.next_retry_at)
                .limit(10)
            )
            downloads = result.scalars().all()
            
            for dm in downloads:
                dm.status = DownloadStatus.WAITING.value
                logger.info(f"Retry scheduled for download {dm.id} (attempt {dm.retry_count + 1})")
            
            await session.commit()
```

#### D) Alembic Migration

```python
# alembic/versions/xxx_add_download_retry_fields.py

def upgrade():
    op.add_column('downloads', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('downloads', sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('downloads', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('downloads', sa.Column('last_error_code', sa.String(50), nullable=True))
    
    # Index für effiziente Retry-Abfragen
    op.create_index('ix_downloads_retry', 'downloads', ['status', 'retry_count', 'next_retry_at'])

def downgrade():
    op.drop_index('ix_downloads_retry')
    op.drop_column('downloads', 'last_error_code')
    op.drop_column('downloads', 'next_retry_at')
    op.drop_column('downloads', 'max_retries')
    op.drop_column('downloads', 'retry_count')
```

### 1.2 Blocklist für fehlgeschlagene Quellen

**Problem:** Schlechte Quellen werden immer wieder probiert

**Lösung:**

#### A) Domain Entity

```python
# src/soulspot/domain/entities/blocklist.py

@dataclass
class BlocklistEntry:
    """Blocked download source."""
    
    id: BlocklistId
    username: str  # slskd Username
    filename: str | None = None  # None = gesamter User blocked
    reason: str = "download_failed"
    failure_count: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None  # None = permanent
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at
```

#### B) Repository Interface

```python
# src/soulspot/domain/ports/__init__.py

class IBlocklistRepository(ABC):
    @abstractmethod
    async def add(self, entry: BlocklistEntry) -> None: ...
    
    @abstractmethod
    async def is_blocked(self, username: str, filename: str | None = None) -> bool: ...
    
    @abstractmethod
    async def get_by_username(self, username: str) -> list[BlocklistEntry]: ...
    
    @abstractmethod
    async def remove(self, entry_id: BlocklistId) -> None: ...
    
    @abstractmethod
    async def cleanup_expired(self) -> int: ...
```

#### C) Database Model

```python
# src/soulspot/infrastructure/persistence/models.py

class BlocklistModel(Base):
    __tablename__ = "download_blocklist"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filename: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    __table_args__ = (
        Index("ix_blocklist_username_filename", "username", "filename"),
    )
```

#### D) Integration in SearchAndDownloadUseCase

```python
# src/soulspot/application/use_cases/search_and_download.py

class SearchAndDownloadTrackUseCase:
    def __init__(
        self,
        slskd_client: ISlskdClient,
        track_repository: ITrackRepository,
        download_repository: IDownloadRepository,
        blocklist_repository: IBlocklistRepository,  # NEU
    ):
        self._blocklist_repository = blocklist_repository
    
    async def _filter_blocked_sources(
        self, 
        results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter out blocked sources from search results."""
        filtered = []
        for result in results:
            username = result.get("username", "")
            filename = result.get("filename", "")
            
            if not await self._blocklist_repository.is_blocked(username, filename):
                filtered.append(result)
        
        return filtered
```

### 1.3 Error Classification

**Problem:** Alle Fehler werden gleich behandelt

**Lösung:** Error-Codes für intelligentes Retry-Verhalten

```python
# src/soulspot/domain/entities/error_codes.py

class DownloadErrorCode(str, Enum):
    """Classification of download errors."""
    
    # Retryable - transiente Fehler
    TIMEOUT = "timeout"                    # Retry nach Backoff
    SOURCE_OFFLINE = "source_offline"      # User offline, Retry später
    NETWORK_ERROR = "network_error"        # Netzwerk-Problem
    RATE_LIMITED = "rate_limited"          # Zu viele Anfragen
    SLSKD_UNAVAILABLE = "slskd_unavailable"  # slskd down
    
    # Retryable mit Alternative - andere Quelle suchen
    TRANSFER_REJECTED = "transfer_rejected"  # User hat abgelehnt
    TRANSFER_FAILED = "transfer_failed"      # Transfer abgebrochen
    
    # Non-Retryable - permanente Fehler
    FILE_NOT_FOUND = "file_not_found"      # Datei existiert nicht
    USER_BLOCKED = "user_blocked"          # Wir sind blocked
    INVALID_FILE = "invalid_file"          # Korrupte Datei
    
    @property
    def is_retryable(self) -> bool:
        non_retryable = {
            self.FILE_NOT_FOUND,
            self.USER_BLOCKED,
            self.INVALID_FILE,
        }
        return self not in non_retryable
    
    @property
    def should_try_alternative(self) -> bool:
        """Should we search for alternative source?"""
        return self in {
            self.TRANSFER_REJECTED,
            self.TRANSFER_FAILED,
            self.USER_BLOCKED,
        }
```

---

## Phase 2: Queue Management

**Zeitrahmen:** Woche 3-4  
**Priorität:** P1 - WICHTIG

### 2.1 Job Persistenz (SQLite Backend)

**Problem:** In-Memory Queue verliert Jobs bei Restart

**Lösung:** Persistente Job-Queue mit SQLite/PostgreSQL

#### A) JobModel

```python
# src/soulspot/infrastructure/persistence/models.py

class JobModel(Base):
    """Persistent job storage for background workers."""
    
    __tablename__ = "background_jobs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Worker ID
    locked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    __table_args__ = (
        Index("ix_jobs_pending", "status", "priority", "created_at"),
        Index("ix_jobs_locked", "locked_by", "locked_at"),
    )
```

#### B) PersistentJobQueue

```python
# src/soulspot/application/workers/persistent_job_queue.py

class PersistentJobQueue:
    """Database-backed job queue with worker locking.
    
    Hey future me - warum DB statt Redis?
    1. Keine extra Dependency (PostgreSQL haben wir schon)
    2. Jobs überleben Restart
    3. Transaktional sicher (kein Job geht verloren)
    
    Worker-Locking verhindert, dass zwei Worker denselben Job verarbeiten.
    Stale Lock Detection: Wenn locked_at > 5min und Job noch RUNNING, ist Worker gecrasht.
    """
    
    def __init__(
        self,
        session_factory: async_sessionmaker,
        worker_id: str | None = None,
        lock_timeout_seconds: int = 300,  # 5 min
    ):
        self._session_factory = session_factory
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._lock_timeout = lock_timeout_seconds
    
    async def enqueue(
        self,
        job_type: JobType,
        payload: dict[str, Any],
        priority: int = 0,
        max_retries: int = 3,
    ) -> str:
        """Add job to persistent queue."""
        job_id = str(uuid.uuid4())
        
        async with self._session_factory() as session:
            job = JobModel(
                id=job_id,
                job_type=job_type.value,
                status=JobStatus.PENDING.value,
                priority=priority,
                payload=json.dumps(payload),
                max_retries=max_retries,
            )
            session.add(job)
            await session.commit()
        
        return job_id
    
    async def dequeue(self) -> Job | None:
        """Get next job and lock it for processing."""
        async with self._session_factory() as session:
            # Atomarer Lock mit SELECT FOR UPDATE
            result = await session.execute(
                select(JobModel)
                .where(
                    JobModel.status == JobStatus.PENDING.value,
                    JobModel.locked_by.is_(None),
                )
                .order_by(JobModel.priority.desc(), JobModel.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job_model = result.scalar_one_or_none()
            
            if not job_model:
                return None
            
            # Lock für diesen Worker
            job_model.locked_by = self._worker_id
            job_model.locked_at = datetime.now(UTC)
            job_model.status = JobStatus.RUNNING.value
            job_model.started_at = datetime.now(UTC)
            await session.commit()
            
            return self._model_to_job(job_model)
    
    async def complete(self, job_id: str, result: Any = None) -> None:
        """Mark job as completed."""
        async with self._session_factory() as session:
            await session.execute(
                update(JobModel)
                .where(JobModel.id == job_id)
                .values(
                    status=JobStatus.COMPLETED.value,
                    result=json.dumps(result) if result else None,
                    completed_at=datetime.now(UTC),
                    locked_by=None,
                    locked_at=None,
                )
            )
            await session.commit()
    
    async def fail(self, job_id: str, error: str) -> None:
        """Mark job as failed, schedule retry if applicable."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(JobModel).where(JobModel.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                return
            
            job.retries += 1
            job.error = error
            job.locked_by = None
            job.locked_at = None
            
            if job.retries < job.max_retries:
                # Schedule retry mit Backoff
                job.status = JobStatus.PENDING.value
                # Backoff wird durch created_at Manipulation simuliert
                # Oder: next_run_at Feld hinzufügen
            else:
                job.status = JobStatus.FAILED.value
                job.completed_at = datetime.now(UTC)
            
            await session.commit()
    
    async def recover_stale_jobs(self) -> int:
        """Recover jobs from crashed workers."""
        stale_threshold = datetime.now(UTC) - timedelta(seconds=self._lock_timeout)
        
        async with self._session_factory() as session:
            result = await session.execute(
                update(JobModel)
                .where(
                    JobModel.status == JobStatus.RUNNING.value,
                    JobModel.locked_at < stale_threshold,
                )
                .values(
                    status=JobStatus.PENDING.value,
                    locked_by=None,
                    locked_at=None,
                )
            )
            await session.commit()
            return result.rowcount
```

### 2.2 Batch Operations API

**Problem:** Keine Multi-Select Aktionen möglich

**Lösung:**

```python
# src/soulspot/api/routers/downloads.py

class BatchActionRequest(BaseModel):
    ids: list[str]
    action: Literal["cancel", "retry", "set_priority", "pause", "resume"]
    priority: int | None = None  # Nur für set_priority

class BatchActionResponse(BaseModel):
    success_count: int
    failed_count: int
    errors: list[str]

@router.post("/batch")
async def batch_action(
    request: BatchActionRequest,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> BatchActionResponse:
    """Perform action on multiple downloads.
    
    Actions:
    - cancel: Cancel selected downloads
    - retry: Retry failed downloads
    - set_priority: Set priority for selected downloads
    - pause: Pause selected downloads (sets status to WAITING)
    - resume: Resume paused downloads
    """
    success_count = 0
    errors = []
    
    for download_id in request.ids:
        try:
            download = await download_repository.get_by_id(DownloadId(download_id))
            if not download:
                errors.append(f"{download_id}: Not found")
                continue
            
            if request.action == "cancel":
                download.cancel()
            elif request.action == "retry":
                if download.status != DownloadStatus.FAILED:
                    errors.append(f"{download_id}: Not in FAILED status")
                    continue
                download.schedule_retry()
            elif request.action == "set_priority":
                download.update_priority(request.priority)
            elif request.action == "pause":
                # Custom pause logic
                pass
            elif request.action == "resume":
                # Custom resume logic
                pass
            
            await download_repository.update(download)
            success_count += 1
            
        except Exception as e:
            errors.append(f"{download_id}: {str(e)}")
    
    return BatchActionResponse(
        success_count=success_count,
        failed_count=len(errors),
        errors=errors,
    )
```

### 2.3 Concurrent Download Limits

**Problem:** Keine Konfiguration für max. parallele Downloads

**Lösung:**

```python
# Settings in app_settings Tabelle
download.max_concurrent = 3          # Global
download.max_concurrent_per_user = 1 # Pro slskd User (verhindert Throttling)
download.max_queue_size = 100        # Max. Downloads in Queue

# API zum Ändern
@router.patch("/settings")
async def update_download_settings(
    max_concurrent: int | None = None,
    max_concurrent_per_user: int | None = None,
    settings_service: AppSettingsService = Depends(get_settings_service),
) -> dict:
    if max_concurrent is not None:
        await settings_service.set_int("download.max_concurrent", max_concurrent)
    if max_concurrent_per_user is not None:
        await settings_service.set_int("download.max_concurrent_per_user", max_concurrent_per_user)
    
    return {"message": "Settings updated"}
```

### 2.4 Queue Reordering (Drag & Drop)

**Problem:** Keine Möglichkeit, Queue-Reihenfolge zu ändern

**Lösung:**

#### A) queue_position Feld

```python
# Download Entity erweitern
queue_position: int = 0  # Niedrigere Zahl = weiter vorne
```

#### B) Reorder API

```python
@router.patch("/reorder")
async def reorder_queue(
    order: list[str],  # Liste von Download-IDs in gewünschter Reihenfolge
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict:
    """Reorder download queue.
    
    Args:
        order: List of download IDs in desired order
    """
    for position, download_id in enumerate(order):
        await download_repository.update_position(download_id, position)
    
    return {"message": f"Reordered {len(order)} downloads"}
```

#### C) Frontend (SortableJS)

```html
<!-- templates/partials/download_queue.html -->
<div id="download-queue" class="sortable-list">
    {% for download in downloads %}
    <div class="download-item" data-id="{{ download.id }}">
        <!-- Download content -->
    </div>
    {% endfor %}
</div>

<script>
new Sortable(document.getElementById('download-queue'), {
    animation: 150,
    onEnd: async function(evt) {
        const order = Array.from(evt.target.children).map(el => el.dataset.id);
        await fetch('/api/downloads/reorder', {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({order}),
        });
    }
});
</script>
```

---

## Phase 3: Quality & Post-Processing

**Zeitrahmen:** Woche 5-6  
**Priorität:** P2 - ENHANCEMENT

### 3.1 Quality Profiles

**Problem:** Nur "best/good/any" als Qualitätswahl

**Lösung:**

#### A) Domain Entity

```python
# src/soulspot/domain/entities/quality_profile.py

@dataclass
class QualityProfile:
    """Quality profile for download preferences."""
    
    id: QualityProfileId
    name: str
    description: str | None = None
    
    # Format-Präferenzen (Reihenfolge = Priorität)
    preferred_formats: list[str] = field(default_factory=lambda: ["flac", "mp3"])
    
    # Qualitätsfilter
    min_bitrate: int | None = None  # kbps
    max_bitrate: int | None = None
    
    # Größenlimits
    min_file_size_mb: float | None = None
    max_file_size_mb: float | None = None
    
    # Ausschlüsse
    exclude_keywords: list[str] = field(default_factory=lambda: ["live", "remix", "karaoke"])
    exclude_users: list[str] = field(default_factory=list)
    
    # Flags
    prefer_lossless: bool = True
    allow_lossy: bool = True
    
    is_default: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

# Vordefinierte Profile
QUALITY_PROFILES = {
    "audiophile": QualityProfile(
        id=QualityProfileId("audiophile"),
        name="Audiophile",
        description="Nur verlustfreie Formate (FLAC, ALAC)",
        preferred_formats=["flac", "alac", "wav"],
        min_bitrate=1000,
        prefer_lossless=True,
        allow_lossy=False,
    ),
    "balanced": QualityProfile(
        id=QualityProfileId("balanced"),
        name="Balanced",
        description="Gute Qualität mit vernünftiger Dateigröße",
        preferred_formats=["flac", "mp3"],
        min_bitrate=256,
        max_file_size_mb=50,
    ),
    "space_saver": QualityProfile(
        id=QualityProfileId("space_saver"),
        name="Space Saver",
        description="Kompakte Dateien für mobiles Hören",
        preferred_formats=["mp3", "aac", "ogg"],
        min_bitrate=192,
        max_bitrate=320,
        max_file_size_mb=15,
        prefer_lossless=False,
    ),
}
```

#### B) Integration in Search

```python
# src/soulspot/application/services/advanced_search.py

class QualityMatcher:
    def __init__(self, profile: QualityProfile):
        self.profile = profile
    
    def matches(self, file_info: dict) -> tuple[bool, int]:
        """Check if file matches profile and return score.
        
        Returns:
            (matches, score) - matches=True if acceptable, score for ranking
        """
        filename = file_info.get("filename", "").lower()
        bitrate = file_info.get("bitrate", 0)
        size_mb = file_info.get("size", 0) / (1024 * 1024)
        
        # Check format
        file_format = self._detect_format(filename)
        if file_format not in self.profile.preferred_formats:
            if self.profile.prefer_lossless and file_format in ["mp3", "aac", "ogg"]:
                if not self.profile.allow_lossy:
                    return False, 0
        
        # Check bitrate
        if self.profile.min_bitrate and bitrate < self.profile.min_bitrate:
            return False, 0
        if self.profile.max_bitrate and bitrate > self.profile.max_bitrate:
            return False, 0
        
        # Check size
        if self.profile.max_file_size_mb and size_mb > self.profile.max_file_size_mb:
            return False, 0
        
        # Check exclusions
        for keyword in self.profile.exclude_keywords:
            if keyword.lower() in filename:
                return False, 0
        
        # Calculate score (higher = better)
        score = 0
        format_priority = self.profile.preferred_formats.index(file_format) if file_format in self.profile.preferred_formats else 100
        score -= format_priority * 1000  # Format is most important
        score += bitrate  # Higher bitrate = better
        
        return True, score
```

### 3.2 Post-Processing Worker

**Problem:** Keine automatische Nachbearbeitung nach Download

**Lösung:**

```python
# src/soulspot/application/workers/post_processing_worker.py

class PostProcessingWorker:
    """Post-processes completed downloads.
    
    Hey future me - dieser Worker wird nach JEDEM erfolgreichen Download getriggert!
    Er macht:
    1. Auto-Move: Datei in organisierte Struktur verschieben
    2. Auto-Rename: Nach Pattern umbenennen
    3. Metadata Tagging: ID3 Tags setzen
    4. Cover Art: Album-Cover einbetten
    5. Notification: User benachrichtigen
    """
    
    def __init__(
        self,
        session_factory: async_sessionmaker,
        settings_service: AppSettingsService,
        image_service: IImageService,
        notification_service: NotificationService | None = None,
    ):
        self._session_factory = session_factory
        self._settings_service = settings_service
        self._image_service = image_service
        self._notification_service = notification_service
    
    async def process(self, download_id: str) -> None:
        """Process a completed download."""
        async with self._session_factory() as session:
            download = await self._get_download(session, download_id)
            track = await self._get_track(session, download.track_id)
            
            if not download.target_path:
                logger.warning(f"Download {download_id} has no target_path")
                return
            
            source_path = Path(download.target_path)
            
            # 1. Auto-Move
            if await self._settings_service.get_bool("download.auto_move"):
                destination = await self._build_destination_path(track)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(source_path, destination)
                source_path = destination
                download.target_path = str(destination)
            
            # 2. Auto-Rename
            if await self._settings_service.get_bool("download.auto_rename"):
                pattern = await self._settings_service.get_string("download.rename_pattern")
                new_name = self._apply_pattern(pattern, track)
                new_path = source_path.parent / new_name
                source_path.rename(new_path)
                source_path = new_path
                download.target_path = str(new_path)
            
            # 3. Metadata Tagging
            if await self._settings_service.get_bool("download.auto_tag"):
                await self._tag_file(source_path, track)
            
            # 4. Cover Art
            if await self._settings_service.get_bool("download.embed_cover"):
                await self._embed_cover(source_path, track)
            
            # 5. Update Track file_path
            track.file_path = FilePath(str(source_path))
            await session.commit()
            
            # 6. Notification
            if self._notification_service:
                await self._notification_service.send(
                    Notification(
                        type=NotificationType.DOWNLOAD_COMPLETE,
                        title="Download Complete",
                        message=f"{track.artist_name} - {track.title}",
                    )
                )
    
    async def _tag_file(self, path: Path, track: Track) -> None:
        """Tag file with ID3 metadata using mutagen."""
        from mutagen.easyid3 import EasyID3
        from mutagen.flac import FLAC
        
        if path.suffix.lower() == ".mp3":
            audio = EasyID3(path)
        elif path.suffix.lower() == ".flac":
            audio = FLAC(path)
        else:
            return
        
        audio["title"] = track.title
        audio["artist"] = track.artist_name or ""
        audio["album"] = track.album_title or ""
        audio["tracknumber"] = str(track.track_number) if track.track_number else ""
        audio["date"] = str(track.release_date.year) if track.release_date else ""
        audio["genre"] = track.genre or ""
        
        audio.save()
    
    def _apply_pattern(self, pattern: str, track: Track) -> str:
        """Apply naming pattern to track.
        
        Patterns:
        - {artist} - Artist name
        - {album} - Album name
        - {title} - Track title
        - {track_number} - Track number (zero-padded)
        - {year} - Release year
        - {ext} - File extension
        """
        replacements = {
            "{artist}": track.artist_name or "Unknown Artist",
            "{album}": track.album_title or "Unknown Album",
            "{title}": track.title,
            "{track_number}": f"{track.track_number:02d}" if track.track_number else "00",
            "{year}": str(track.release_date.year) if track.release_date else "",
        }
        
        result = pattern
        for key, value in replacements.items():
            result = result.replace(key, self._sanitize_filename(value))
        
        return result
```

### 3.3 Metadata Tagging Service

**Problem:** Keine automatischen ID3 Tags

**Lösung:**

```python
# src/soulspot/application/services/metadata_tagger.py

class MetadataTaggerService:
    """Tags audio files with metadata.
    
    Hey future me - nutzt mutagen Library für ID3/FLAC Tags!
    Unterstützt: MP3 (ID3v2.4), FLAC, M4A (MP4), OGG Vorbis
    """
    
    SUPPORTED_FORMATS = {".mp3", ".flac", ".m4a", ".ogg"}
    
    async def tag_file(
        self,
        file_path: Path,
        metadata: TrackMetadata,
        cover_image: bytes | None = None,
    ) -> bool:
        """Tag audio file with metadata.
        
        Args:
            file_path: Path to audio file
            metadata: Track metadata to apply
            cover_image: Optional cover art (JPEG bytes)
        
        Returns:
            True if successful
        """
        if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            logger.warning(f"Unsupported format: {file_path.suffix}")
            return False
        
        try:
            if file_path.suffix.lower() == ".mp3":
                return await self._tag_mp3(file_path, metadata, cover_image)
            elif file_path.suffix.lower() == ".flac":
                return await self._tag_flac(file_path, metadata, cover_image)
            elif file_path.suffix.lower() == ".m4a":
                return await self._tag_m4a(file_path, metadata, cover_image)
            elif file_path.suffix.lower() == ".ogg":
                return await self._tag_ogg(file_path, metadata)
        except Exception as e:
            logger.error(f"Failed to tag {file_path}: {e}")
            return False
        
        return False
    
    async def _tag_mp3(
        self, path: Path, metadata: TrackMetadata, cover: bytes | None
    ) -> bool:
        """Tag MP3 file with ID3v2.4."""
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TYER, TCON, APIC
        
        try:
            audio = ID3(path)
        except Exception:
            audio = ID3()
        
        audio.add(TIT2(encoding=3, text=metadata.title))
        audio.add(TPE1(encoding=3, text=metadata.artist))
        audio.add(TALB(encoding=3, text=metadata.album or ""))
        if metadata.track_number:
            audio.add(TRCK(encoding=3, text=str(metadata.track_number)))
        if metadata.year:
            audio.add(TYER(encoding=3, text=str(metadata.year)))
        if metadata.genre:
            audio.add(TCON(encoding=3, text=metadata.genre))
        
        if cover:
            audio.add(APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # Front cover
                desc="Cover",
                data=cover,
            ))
        
        audio.save(path)
        return True
```

---

## Phase 4: UX & Monitoring

**Zeitrahmen:** Woche 7-8  
**Priorität:** P2 - ENHANCEMENT

### 4.1 Download Statistics Dashboard

```python
# src/soulspot/api/routers/download_stats.py

@router.get("/stats")
async def get_download_statistics(
    period: Literal["day", "week", "month", "all"] = "week",
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> DownloadStatsResponse:
    """Get comprehensive download statistics."""
    
    stats = await download_repository.get_statistics(period)
    
    return DownloadStatsResponse(
        total_downloads=stats.total,
        total_size_bytes=stats.total_bytes,
        total_size_formatted=format_bytes(stats.total_bytes),
        
        by_status={
            "completed": stats.completed,
            "failed": stats.failed,
            "cancelled": stats.cancelled,
            "in_progress": stats.in_progress,
        },
        
        by_format={
            "flac": stats.flac_count,
            "mp3": stats.mp3_count,
            "other": stats.other_count,
        },
        
        avg_download_time_seconds=stats.avg_download_time,
        avg_file_size_mb=stats.avg_file_size / (1024 * 1024),
        
        history=[
            {"date": entry.date.isoformat(), "count": entry.count}
            for entry in stats.daily_history
        ],
        
        top_artists=[
            {"name": a.name, "count": a.download_count}
            for a in stats.top_artists[:10]
        ],
    )
```

### 4.2 Notification System

```python
# src/soulspot/domain/ports/notification.py

class NotificationType(str, Enum):
    DOWNLOAD_COMPLETE = "download_complete"
    DOWNLOAD_FAILED = "download_failed"
    ALBUM_COMPLETE = "album_complete"
    BATCH_COMPLETE = "batch_complete"
    SLSKD_OFFLINE = "slskd_offline"
    SLSKD_ONLINE = "slskd_online"

@dataclass
class Notification:
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: dict[str, Any] | None = None

class INotificationProvider(ABC):
    @abstractmethod
    async def send(self, notification: Notification) -> NotificationResult: ...

# Implementierungen
class WebhookNotificationProvider(INotificationProvider):
    """Send notifications via webhook (Discord, Slack, etc.)."""
    
    async def send(self, notification: Notification) -> NotificationResult:
        payload = {
            "type": notification.type.value,
            "title": notification.title,
            "message": notification.message,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        
        return NotificationResult(success=response.status_code < 400)

class ToastNotificationProvider(INotificationProvider):
    """In-app toast notifications via SSE."""
    
    async def send(self, notification: Notification) -> NotificationResult:
        # Sendet Event über SSE stream
        await self._sse_manager.broadcast({
            "type": "notification",
            "data": {
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
            }
        })
        return NotificationResult(success=True)
```

### 4.3 Download History Export

```python
@router.get("/export")
async def export_downloads(
    format: Literal["csv", "json"] = "csv",
    status: DownloadStatus | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> Response:
    """Export download history."""
    
    downloads = await download_repository.get_for_export(
        status=status,
        start_date=start_date,
        end_date=end_date,
    )
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Track", "Artist", "Status", "Size", "Date"])
        for d in downloads:
            writer.writerow([d.id, d.track_title, d.artist_name, d.status, d.size, d.completed_at])
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=downloads.csv"},
        )
    
    elif format == "json":
        return Response(
            content=json.dumps([d.to_dict() for d in downloads], indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=downloads.json"},
        )
```

---

## Phase 5: Advanced Features

**Zeitrahmen:** Woche 9+  
**Priorität:** P3 - OPTIONAL

### 5.1 Multi-Provider Support

```python
# Erweiterung des bestehenden Provider-Systems

class UsenetDownloadProvider(IDownloadProvider):
    """Download via Usenet (SABnzbd/NZBGet)."""
    pass

class TorrentDownloadProvider(IDownloadProvider):
    """Download via Torrent (qBittorrent)."""
    pass

class ProviderFallbackStrategy:
    """Try providers in order until success."""
    
    def __init__(self, providers: list[IDownloadProvider]):
        self.providers = providers
    
    async def download(self, track: Track) -> Download:
        for provider in self.providers:
            if not await provider.is_available():
                continue
            
            try:
                return await provider.search_and_download(track)
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue
        
        raise DownloadError("All providers failed")
```

### 5.2 RSS Feed Monitoring

```python
class RSSMonitorWorker:
    """Monitor RSS feeds for new releases."""
    
    async def check_feeds(self) -> list[NewRelease]:
        feeds = await self._get_configured_feeds()
        new_releases = []
        
        for feed in feeds:
            entries = await self._fetch_feed(feed.url)
            for entry in entries:
                if await self._matches_watchlist(entry):
                    new_releases.append(NewRelease(
                        title=entry.title,
                        artist=entry.artist,
                        source_feed=feed.id,
                    ))
        
        return new_releases
```

### 5.3 Scheduler (Time-based Downloads)

```python
class DownloadScheduler:
    """Schedule downloads for specific times."""
    
    async def schedule_download(
        self,
        download_id: str,
        scheduled_start: datetime,
    ) -> None:
        download = await self._repository.get_by_id(download_id)
        download.scheduled_start = scheduled_start
        download.status = DownloadStatus.SCHEDULED
        await self._repository.update(download)
    
    async def check_scheduled(self) -> None:
        """Check and start scheduled downloads."""
        now = datetime.now(UTC)
        scheduled = await self._repository.get_scheduled_before(now)
        
        for download in scheduled:
            download.status = DownloadStatus.WAITING
            await self._repository.update(download)
```

---

## Datenbank-Migrationen

### Migrations-Übersicht

| Migration | Phase | Beschreibung |
|-----------|-------|--------------|
| `add_download_retry_fields` | 1 | retry_count, max_retries, next_retry_at, last_error_code |
| `add_blocklist_table` | 1 | download_blocklist Tabelle |
| `add_background_jobs_table` | 2 | Persistente Job Queue |
| `add_download_queue_position` | 2 | queue_position für Reordering |
| `add_quality_profiles_table` | 3 | Quality Profiles |
| `add_download_statistics` | 4 | Statistik-Views/Materialized Views |

### Migration Template

```python
# alembic/versions/xxx_add_download_retry_fields.py

"""Add download retry fields.

Revision ID: xxx
Revises: previous_revision
Create Date: 2025-12-22
"""

from alembic import op
import sqlalchemy as sa

revision = 'xxx'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None

def upgrade():
    # Download retry fields
    op.add_column('downloads', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('downloads', sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('downloads', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('downloads', sa.Column('last_error_code', sa.String(50), nullable=True))
    
    # Performance index for retry queries
    op.create_index('ix_downloads_retry_scheduling', 'downloads', 
                    ['status', 'retry_count', 'next_retry_at'],
                    postgresql_where=sa.text("status = 'failed'"))

def downgrade():
    op.drop_index('ix_downloads_retry_scheduling')
    op.drop_column('downloads', 'last_error_code')
    op.drop_column('downloads', 'next_retry_at')
    op.drop_column('downloads', 'max_retries')
    op.drop_column('downloads', 'retry_count')
```

---

## Testing-Strategie

### Live-Testing Checkliste

> ⚠️ **Hinweis:** SoulSpot verwendet KEIN automatisiertes Testing (pytest). Alle Tests werden manuell in Docker durchgeführt.

#### Phase 1: Core Robustheit
- [ ] Download fehlschlagen lassen → Automatischer Retry nach X Minuten
- [ ] 3x fehlschlagen → FAILED Status, kein weiterer Retry
- [ ] User zur Blocklist hinzufügen → Wird in Suche ignoriert
- [ ] slskd stoppen → Downloads gehen zu WAITING
- [ ] slskd starten → Downloads werden automatisch fortgesetzt

#### Phase 2: Queue Management
- [ ] App neustarten → Jobs sind noch da
- [ ] Batch-Cancel von 5 Downloads → Alle gecancelt
- [ ] Batch-Retry von 3 failed Downloads → Alle neu gequeued
- [ ] Max concurrent auf 2 setzen → Nur 2 parallel

#### Phase 3: Quality & Post-Processing
- [ ] Quality Profile "Audiophile" → Nur FLAC Downloads
- [ ] Download abgeschlossen → Datei automatisch verschoben
- [ ] ID3 Tags → Korrekt in Datei geschrieben
- [ ] Cover Art → In Datei eingebettet

#### Phase 4: UX & Monitoring
- [ ] Statistik-Dashboard → Zeigt korrekte Zahlen
- [ ] Notification bei Completion → Toast erscheint
- [ ] Export als CSV → Datei korrekt formatiert

---

## Rollout-Plan

### Phase 1 Rollout (Woche 2)
1. Migration durchführen
2. RetrySchedulerWorker aktivieren
3. Blocklist UI hinzufügen
4. Dokumentation aktualisieren
5. User-Feedback sammeln

### Phase 2 Rollout (Woche 4)
1. PersistentJobQueue aktivieren (Feature Flag)
2. Alte In-Memory Queue parallel laufen lassen
3. Batch Operations API freischalten
4. UI für Settings aktualisieren

### Phase 3-4 Rollout (Woche 6-8)
1. Quality Profiles als "Beta" Feature
2. Post-Processing Worker aktivieren
3. Notification System ausrollen
4. Statistik-Dashboard launchen

---

## Risiken & Mitigationen

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| Job Queue Migration fehlschlägt | Mittel | Hoch | Dual-Write Strategie, Rollback-Plan |
| slskd API Änderungen | Niedrig | Mittel | API Version pinnen, Adapter Pattern |
| Performance-Probleme bei großer Queue | Mittel | Mittel | Indexe, Pagination, Lazy Loading |
| Mutagen Bugs bei exotischen Formaten | Mittel | Niedrig | Format-Whitelist, Graceful Degradation |
| User verwirrt durch neue Features | Mittel | Niedrig | Schrittweises Rollout, Dokumentation |

---

## Nächste Schritte

1. **Immediate (Tag 1):** 
   - [ ] Diesen Plan reviewen und priorisieren
   - [ ] Migrations-Branch erstellen

2. **Woche 1:**
   - [ ] Download Entity erweitern (retry_count etc.)
   - [ ] Migration schreiben und testen
   - [ ] RetrySchedulerWorker implementieren

3. **Woche 2:**
   - [ ] Blocklist implementieren
   - [ ] Error Classification integrieren
   - [ ] Live-Testing Phase 1

---

## Verwandte Dokumente

- [Download Management Docs](../features/download-management.md)
- [Download Manager Features Roadmap](../features/DOWNLOAD_MANAGER_FEATURES.md)
- [Architecture Overview](../architecture/README.md)
- [API Documentation](../api/download-management.md)
