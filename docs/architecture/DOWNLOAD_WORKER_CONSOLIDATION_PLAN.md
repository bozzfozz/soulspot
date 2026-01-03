# Download Worker Konsolidierungs-Plan

> Erstellt: Januar 2026  
> Status: **✅ IMPLEMENTIERT**  
> Implementiert: Januar 2026  
> Ziel: 4 Download-Worker → 2 konsolidierte Worker  
> Inspiriert von: Lidarr Download Client Architecture

## 📋 Übersicht

### Aktuelle Situation

```
┌─────────────────────────────────────────────────────────────────┐
│                    4 DOWNLOAD-WORKER (zu viel!)                  │
├─────────────────────────────────────────────────────────────────┤
│  DownloadMonitorWorker      │ slskd → JobQueue Status (10s)     │
│  DownloadStatusSyncWorker   │ slskd → DB Status (5s)            │
│  QueueDispatcherWorker      │ WAITING → PENDING → enqueue (30s) │
│  RetrySchedulerWorker       │ FAILED → WAITING (30s)            │
└─────────────────────────────────────────────────────────────────┘

PROBLEME:
1. DownloadMonitorWorker + DownloadStatusSyncWorker pollen BEIDE slskd!
   → Doppelte API-Calls, doppelter Code
2. QueueDispatcherWorker + RetrySchedulerWorker verwalten BEIDE die Queue!
   → Gleiche DB-Tabelle, ähnliche Logik
3. 4 Worker = 4 Sessions = mehr SQLite-Lock-Potenzial
```

### Ziel-Architektur (Lidarr-inspiriert)

```
┌─────────────────────────────────────────────────────────────────┐
│                    2 KONSOLIDIERTE WORKER                        │
├─────────────────────────────────────────────────────────────────┤
│  SlskdMonitorWorker         │ slskd → JobQueue + DB (5s)        │
│  (merged: Monitor + Sync)   │ EIN Poll, ZWEI Updates            │
│                             │ + Completed Download Handling     │
├─────────────────────────────────────────────────────────────────┤
│  DownloadQueueManager       │ Queue-Management (30s)            │
│  (merged: Dispatch + Retry) │ WAITING↔FAILED↔PENDING           │
│                             │ + Blocklist für permanente Fehler │
└─────────────────────────────────────────────────────────────────┘

VORTEILE:
1. slskd wird nur 1x gepollt (statt 2x) - wie Lidarr!
2. Queue-Logik an EINEM Ort - wie Lidarr's Download Client Handler
3. Weniger Worker = weniger DB-Sessions = weniger Locks
4. Einfacheres Debugging
5. Lidarr-konformes "Completed Download Handling"
6. Blocklist-Pattern für permanente Fehler (nicht endlos retry)
```

---

## 🎯 Lidarr Best Practices (angewandt)

### 1. Single Download Client Contact Point
**Lidarr:** Pollt Download-Client EINMAL und handlet alles
**Wir:** `SlskdMonitorWorker` pollt slskd EINMAL und updated JobQueue + DB

### 2. Completed Download Handling
**Lidarr:** `Scan location → Match to media → Move/Rename`
**Wir:** `SlskdMonitorWorker._handle_completed()` → Update Track.file_path → Trigger AutoImport

### 3. Failed Download Handling mit Blocklist
**Lidarr:** Blocklisted permanently failed downloads
**Wir:** `DownloadQueueManager` mit `BLOCKLIST_ERRORS` für `file_not_found`, `user_blocked`, etc.

---

## 🔧 Phase 1: Design

### Worker A: `SlskdMonitorWorker`

**Datei:** `src/soulspot/application/workers/slskd_monitor_worker.py`

**Merged aus:**
- `download_monitor_worker.py` (506 Zeilen)
- `download_status_sync_worker.py` (665 Zeilen)

**Verantwortlichkeiten:**

| Feature | Quelle | Beschreibung |
|---------|--------|--------------|
| slskd Polling | Beide | 1x alle 5s (statt 2x: 10s + 5s) |
| JobQueue Update | Monitor | Progress, bytes_downloaded, percent |
| DB Status Update | StatusSync | DownloadModel.status, progress |
| **Completed Handling** | **NEU** | Track.file_path + AutoImport trigger |
| Stale Detection | Monitor | Downloads > 12h ohne Progress |
| Circuit Breaker | StatusSync | Bei slskd-Ausfall |
| Completed History | StatusSync | Tracking für 24h |

**Pseudo-Code:**
```python
class SlskdMonitorWorker:
    """Unified slskd monitoring worker - Lidarr-inspired.
    
    Hey future me - THIS IS THE ONE slskd poller!
    Like Lidarr monitors its download client, we monitor slskd.
    
    Single Responsibility: slskd status → SoulSpot (JobQueue + DB)
    NEW: Completed Download Handling (like Lidarr)
    """
    
    async def _poll_cycle(self) -> None:
        # 1. Poll slskd EINMAL (wie Lidarr!)
        downloads = await self._slskd_client.get_all_downloads()
        
        # 2. Update JobQueue (von Monitor)
        for download in downloads:
            self._update_job_queue_status(download)
        
        # 3. Update DB (von StatusSync)
        async with self._session_factory() as session:
            for download in downloads:
                was_completed = await self._update_db_status(session, download)
                
                # 4. Completed Download Handling (NEU - wie Lidarr!)
                if was_completed:
                    await self._handle_completed(session, download)
            
            await session.commit()
        
        # 5. Stale Detection (von Monitor, alle N Polls)
        if self._poll_count % STALE_CHECK_INTERVAL == 0:
            await self._check_stale_downloads()
    
    async def _handle_completed(self, session, download) -> None:
        """Lidarr-style Completed Download Handling.
        
        1. Get final file path from slskd
        2. Update Track.file_path in DB
        3. Trigger AutoImport if enabled
        """
        # Get file path from slskd completion data
        file_path = download.get("filename") or download.get("file_path")
        if not file_path:
            return
        
        # Update Track.file_path
        await self._update_track_file_path(session, download, file_path)
        
        # Optional: Trigger AutoImport
        # (AutoImportService already polls for new files, so this is optional)
```

---

### Worker B: `DownloadQueueManager`

**Datei:** `src/soulspot/application/workers/download_queue_manager.py`

**Merged aus:**
- `queue_dispatcher_worker.py` (352 Zeilen)
- `retry_scheduler_worker.py` (214 Zeilen)

**Verantwortlichkeiten:**

| Feature | Quelle | Beschreibung |
|---------|--------|--------------|
| slskd Health Check | Dispatcher | Vor Dispatch prüfen |
| WAITING → PENDING | Dispatcher | Status-Transition |
| Job Enqueue | Dispatcher | In JobQueue einstellen |
| Priority Ordering | Dispatcher | Älteste/höchste Prio zuerst |
| Dispatch Delay | Dispatcher | 2s zwischen Dispatches |
| Max per Cycle | Beide | Limit pro Durchlauf |
| FAILED → WAITING | Retry | Nach Backoff-Zeit |
| Backoff Berechnung | Retry | 1min → 5min → 15min |
| **Blocklist Handling** | **NEU** | Permanent failed → BLOCKLISTED |

**NEU: Blocklist-Pattern (Lidarr-inspiriert)**

```python
# Errors die NIEMALS retried werden - analog zu Lidarr's Blocklist
BLOCKLIST_ERRORS = {
    "file_not_found",      # Datei existiert nicht auf Soulseek
    "user_blocked",        # User hat uns geblockt
    "corrupted_file",      # Heruntergeladene Datei ist korrupt
    "invalid_format",      # Kein gültiges Audio-Format
}

# Nach max_retries → Status wird BLOCKLISTED statt FAILED
# User kann über UI manuell de-blocklisten
```

**Pseudo-Code:**
```python
class DownloadQueueManager:
    """Unified download queue management - Lidarr-inspired.
    
    Hey future me - THIS MANAGES THE DOWNLOAD QUEUE!
    Like Lidarr's Download Client Handler, we manage dispatch + retry.
    
    NEW: Blocklist for permanently failed downloads (like Lidarr)
    """
    
    async def _poll_cycle(self) -> None:
        # 1. Check slskd availability (von Dispatcher)
        slskd_available = await self._check_slskd_health()
        
        async with self._session_factory() as session:
            # 2. Retry failed downloads (von Retry)
            # Das passiert IMMER, auch wenn slskd offline
            await self._process_retries(session)
            
            # 3. Dispatch waiting downloads (von Dispatcher)
            # Nur wenn slskd verfügbar!
            if slskd_available:
                await self._dispatch_waiting(session)
            
            await session.commit()
    
    async def _process_retries(self, session) -> None:
        """Process retry-eligible and blocklist downloads."""
        repo = DownloadRepository(session)
        
        # 1. Find retry-eligible downloads
        eligible = await repo.find_retry_eligible(
            max_retries=3,
            exclude_errors=BLOCKLIST_ERRORS,  # Skip blocklist errors!
        )
        
        for download in eligible:
            if download.error_type in BLOCKLIST_ERRORS:
                # Permanent failure → Blocklist (NEU!)
                download.status = DownloadStatus.BLOCKLISTED
                logger.info(f"Blocklisted: {download.track_title} ({download.error_type})")
            elif download.retry_count >= MAX_RETRIES:
                # Max retries reached → Blocklist
                download.status = DownloadStatus.BLOCKLISTED
                logger.info(f"Blocklisted after {MAX_RETRIES} retries: {download.track_title}")
            else:
                # Retry eligible → Activate
                download.activate_for_retry()
```

---

## 📝 Phase 2: Implementierung

### Schritt 2.1: `DownloadStatusWorker` erstellen

```
Datei: src/soulspot/application/workers/download_status_worker.py
Zeilen: ~600 (merged aus 506 + 665, minus Duplikation)

Imports:
- Von download_monitor_worker.py:
  - SLSKD_COMPLETED_STATES, SLSKD_FAILED_STATES, SLSKD_ACTIVE_STATES
  - STALE_TIMEOUT_HOURS, STALE_CHECK_INTERVAL_POLLS
- Von download_status_sync_worker.py:
  - SLSKD_STATUS_TO_SOULSPOT mapping
  - Circuit Breaker Logik

Dependencies:
- SlskdClient (für API-Calls)
- JobQueue (für Job-Status)
- session_factory (für DB-Zugriff)
```

### Schritt 2.2: `DownloadQueueWorker` erstellen

```
Datei: src/soulspot/application/workers/download_queue_worker.py
Zeilen: ~350 (merged aus 352 + 214, minus Duplikation)

Imports:
- Von queue_dispatcher_worker.py:
  - Health Check Logik
  - Dispatch Logik
- Von retry_scheduler_worker.py:
  - Retry Activation Logik
  - Backoff Constants

Dependencies:
- SlskdClient (für Health Check)
- JobQueue (für Job Enqueue)
- session_factory (für DB-Zugriff)
- DownloadRepository (für Queries)
```

### Schritt 2.3: `lifecycle.py` aktualisieren

```python
# ENTFERNEN:
from soulspot.application.workers.download_monitor_worker import DownloadMonitorWorker
from soulspot.application.workers.download_status_sync_worker import DownloadStatusSyncWorker
from soulspot.application.workers.queue_dispatcher_worker import QueueDispatcherWorker
from soulspot.application.workers.retry_scheduler_worker import RetrySchedulerWorker

# HINZUFÜGEN:
from soulspot.application.workers.download_status_worker import DownloadStatusWorker
from soulspot.application.workers.download_queue_worker import DownloadQueueWorker

# REGISTRIEREN:
download_status_worker = DownloadStatusWorker(
    session_factory=db.get_session_factory(),
    slskd_client=slskd_client,
    job_queue=job_queue,
    sync_interval=5,  # Poll every 5 seconds
)
orchestrator.register(
    name="download_status",
    worker=download_status_worker,
    category="download",
    priority=30,
    required=False,
)

download_queue_worker = DownloadQueueWorker(
    session_factory=db.get_session_factory(),
    slskd_client=slskd_client,
    job_queue=job_queue,
    check_interval=30,
)
orchestrator.register(
    name="download_queue",
    worker=download_queue_worker,
    category="download",
    priority=31,
    required=False,
)
```

### Schritt 2.4: Validierung

```bash
# Syntax-Check
python3 -m py_compile src/soulspot/application/workers/download_status_worker.py
python3 -m py_compile src/soulspot/application/workers/download_queue_worker.py

# Import-Check
python3 -c "from soulspot.application.workers.download_status_worker import DownloadStatusWorker"
python3 -c "from soulspot.application.workers.download_queue_worker import DownloadQueueWorker"

# Vollständiger App-Start (im Docker)
make docker-up
# Prüfen ob Worker starten ohne Fehler
```

---

## 🧹 Phase 3: Cleanup

### Alte Worker (DEPRECATED, nicht mehr in lifecycle.py):

| Datei | Zeilen | Status |
|-------|--------|--------|
| `download_monitor_worker.py` | 506 | ⚠️ DEPRECATED |
| `download_status_sync_worker.py` | 665 | ⚠️ DEPRECATED |
| `queue_dispatcher_worker.py` | 352 | ⚠️ DEPRECATED |
| `retry_scheduler_worker.py` | 214 | ⚠️ DEPRECATED |
| **Total deprecated:** | **1737** | |

### Neue Dateien (aktiv in lifecycle.py):

| Datei | Zeilen | Status |
|-------|--------|--------|
| `download_status_worker.py` | ~550 | ✅ AKTIV |
| `download_queue_worker.py` | ~330 | ✅ AKTIV |
| **Total neu:** | **~880** | |

**Netto-Reduktion:** ~857 Zeilen (-49%)

---

## ✅ Feature-Checklist

### Von `DownloadMonitorWorker` (506 Zeilen):

- [x] Poll slskd API für aktive Downloads
- [x] Update JobQueue mit Progress (bytes_downloaded, percent)
- [x] Mark Jobs as COMPLETED when download finishes
- [x] Mark Jobs as FAILED when download errors
- [x] Stale Download Detection (> 1h ohne Progress)
- [x] Restart Stale Downloads
- [x] Log worker health via log_worker_health()

### Von `DownloadStatusSyncWorker` (665 Zeilen):

- [x] Poll slskd API für alle Downloads
- [x] Match slskd downloads zu DownloadModel via source_url/external_id
- [x] Update DownloadModel.status
- [x] Update DownloadModel.progress
- [x] Update DownloadModel.bytes_downloaded
- [x] Update TrackModel.file_path on Completion
- [x] Circuit Breaker (STATE_CLOSED/OPEN/HALF_OPEN)
- [x] Exponential Backoff bei Failures
- [x] Completed History Tracking (24h)
- [x] Log worker health via log_worker_health()

### Von `QueueDispatcherWorker` (352 Zeilen):

- [x] Check slskd health via test_connection
- [x] Query WAITING downloads (oldest first, priority order)
- [x] Transition WAITING → PENDING
- [x] Enqueue DOWNLOAD job in JobQueue
- [x] Max dispatch per cycle (default: 5)
- [x] Dispatch delay between downloads (default: 2s)
- [x] Track availability state changes
- [x] Graceful shutdown handling
- [x] Log worker health via log_worker_health()

### Von `RetrySchedulerWorker` (214 Zeilen):

- [x] Query retry-eligible downloads (FAILED + retry_count < max + next_retry_at <= now)
- [x] Check non-retryable errors (file_not_found, user_blocked, invalid_file)
- [x] Activate for retry (FAILED → WAITING)
- [x] Max retries per cycle (default: 10)
- [x] Graceful shutdown handling
- [x] Log worker health via log_worker_health()

---

## 📊 Ergebnis nach Konsolidierung

```
VORHER (8 Worker):                 NACHHER (6 Worker):
├── DownloadMonitorWorker   ┐
│                           ├──→  DownloadStatusWorker
├── DownloadStatusSyncWorker┘
│
├── QueueDispatcherWorker   ┐
│                           ├──→  DownloadQueueWorker
├── RetrySchedulerWorker    ┘
│
├── DownloadWorker          ───→  DownloadWorker (bleibt)
├── UnifiedLibraryManager   ───→  UnifiedLibraryManager (bleibt)
├── TokenRefreshWorker      ───→  TokenRefreshWorker (bleibt)
└── AutomationWorkerManager ───→  AutomationWorkerManager (bleibt)

Reduzierung: 8 → 6 Worker (-25%)
Code: ~1737 → ~950 Zeilen (-45%)
slskd Polls: 2x → 1x (-50% API-Calls)
```

---

## 🚨 Risiken & Mitigationen

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Feature-Verlust beim Merge | Mittel | Feature-Checklist oben vollständig abarbeiten |
| Logik-Fehler | Mittel | Beide Original-Worker parallel lesen beim Merge |
| DB-Lock bei mehr Updates | Niedrig | Bleibt bei 1 Session pro Worker |
| Circuit Breaker Konflikte | Niedrig | State aus StatusSync übernehmen |
| Race Conditions | Niedrig | Sequentielle Verarbeitung beibehalten |

---

## 📅 Timeline

| Phase | Dauer | Status |
|-------|-------|--------|
| Phase 1: Design | ✅ Fertig | Dieses Dokument |
| Phase 2: Implementierung | ✅ ~2h | Fertig - Januar 2026 |
| Phase 3: Cleanup | ✅ Fertig | Alte Worker deprecated, nicht gelöscht |

### Implementierungs-Details (Januar 2026):

**Neue Worker erstellt:**
- `src/soulspot/application/workers/download_status_worker.py` (~550 Zeilen)
- `src/soulspot/application/workers/download_queue_worker.py` (~330 Zeilen)

**lifecycle.py aktualisiert:**
- Alte Worker-Imports entfernt
- Neue Worker-Registrierung hinzugefügt
- Orchestrator.register_running_task() für task-basierte Worker

**Alte Worker mit Deprecation-Header versehen:**
- Jede Datei hat prominent `⚠️ DEPRECATED` Kommentar
- Verweis auf neue Worker und Migration
- Docstring mit `.. deprecated::` Sphinx directive

---

## 🔗 Verwandte Dokumente

- `docs/architecture/UNIFIED_LIBRARY_WORKER.md` - Library Worker Konsolidierung
- `docs/architecture/DEPRECATED_WORKERS.md` - Liste der bereits deprecaten Worker
