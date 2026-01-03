# Automation Worker Konsolidierungs-Plan

> Erstellt: Januar 2026  
> Status: **✅ IMPLEMENTIERT**  
> Ziel: AutomationWorkerManager → UnifiedLibraryManager  
> Priorität: ~~Medium~~ **DONE**  
> Inspiriert von: **Lidarr Command Queue Architecture** (Jan 2026 Research)

## 🎉 Implementierung abgeschlossen!

**Änderungen:**
- `unified_library_worker.py`: +3 neue TaskTypes, +TASK_COOLDOWNS dict, +TaskDebouncer
- `lifecycle.py`: AutomationWorkerManager entfernt, UnifiedLibraryManager erweitert
- `automation_workers.py`: DEPRECATED Marker hinzugefügt (nicht gelöscht für Rollback)

**Neue Tasks:**
| Task | Cooldown | Beschreibung |
|------|----------|--------------|
| WATCHLIST_CHECK | 1h | Neue Releases für Watchlist-Artists |
| DISCOGRAPHY_SCAN | 24h | Fehlende Alben in Discographies |
| QUALITY_UPGRADE | 24h | Tracks mit Upgrade-Potential |

---

## 📚 Lidarr Best Practices (Research Summary)

### Erkenntnisse aus Lidarr-Codebase:

1. **Command Queue Pattern** - Lidarr nutzt eine zentrale CommandQueue mit:
   - Task-Deduplication (verhindert doppelte Ausführung)
   - Exclusivity (manche Tasks können nicht parallel laufen)
   - Event-Chain (Tasks triggern Folge-Tasks)

2. **Smart Refresh Rules** - Nicht alles jedes Mal refreshen:
   ```
   - Never synced? → ALWAYS refresh
   - Last sync < 12h ago? → SKIP (too recent)
   - Last sync > 30 days? → REFRESH (stale)
   - Recent release (< 30 days)? → REFRESH (active artist)
   - Inactive artist? → Refresh every 48h
   ```

3. **Debouncing** - Mehrere Events in kurzer Zeit → eine Ausführung nach 5s Cooldown

4. **Incremental Sync** - Nur Änderungen der letzten 14 Tage von MusicBrainz holen

### Anpassungen für unseren Plan:

| Lidarr Pattern | Unsere Implementierung |
|----------------|----------------------|
| Command Queue | TaskScheduler mit Priority + Cooldown |
| Exclusivity | `is_exclusive` Flag pro TaskType |
| Event Chain | Dependency-System (existiert bereits!) |
| Debouncing | NEU: Hinzufügen zu TaskScheduler |
| Smart Refresh | NEU: `should_refresh()` Logik |

## 📋 Übersicht

### Aktuelle Situation

```
┌─────────────────────────────────────────────────────────────────┐
│                   AutomationWorkerManager                        │
│                   (Separater Worker mit 3 Sub-Workern)           │
├─────────────────────────────────────────────────────────────────┤
│  WatchlistWorker        │ Neue Releases finden (1h)              │
│  DiscographyWorker      │ Fehlende Alben finden (24h)            │
│  QualityUpgradeWorker   │ Bessere Qualität finden (24h)          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedLibraryManager                         │
│                    (Zentrale Library-Orchestrierung)             │
├─────────────────────────────────────────────────────────────────┤
│  TaskType.ARTIST_SYNC   │ Sync followed artists                  │
│  TaskType.ALBUM_SYNC    │ Sync albums for artists                │
│  TaskType.TRACK_SYNC    │ Sync tracks for albums                 │
│  TaskType.ENRICHMENT    │ MusicBrainz metadata                   │
│  TaskType.IMAGE_SYNC    │ Download/cache images                  │
│  TaskType.DOWNLOAD      │ Coordinate with slskd                  │
│  TaskType.CLEANUP       │ Reset failed, remove orphans           │
└─────────────────────────────────────────────────────────────────┘

PROBLEME:
1. 2 separate Worker-Systeme mit überlappender Funktionalität
2. AutomationWorker nutzt gleiche Daten wie UnifiedLibraryManager
3. Redundante Token/Session-Handling
4. Separate Intervall-Konfiguration
```

### Ziel-Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedLibraryManager                         │
│                    (ALLES an einem Ort!)                         │
├─────────────────────────────────────────────────────────────────┤
│  TaskType.ARTIST_SYNC     │ Sync followed artists                │
│  TaskType.ALBUM_SYNC      │ Sync albums for artists              │
│  TaskType.TRACK_SYNC      │ Sync tracks for albums               │
│  TaskType.ENRICHMENT      │ MusicBrainz metadata                 │
│  TaskType.IMAGE_SYNC      │ Download/cache images                │
│  TaskType.DOWNLOAD        │ Coordinate with slskd                │
│  TaskType.WATCHLIST_CHECK │ NEU: Neue Releases finden            │
│  TaskType.DISCOGRAPHY     │ NEU: Fehlende Alben finden           │
│  TaskType.QUALITY_UPGRADE │ NEU: Upgrade-Kandidaten finden       │
│  TaskType.CLEANUP         │ Reset failed, remove orphans         │
└─────────────────────────────────────────────────────────────────┘

VORTEILE:
1. EIN Worker für ALLE Library-Operationen
2. Einheitliches Cooldown-System
3. Dependency-basierte Task-Ordnung (Watchlist NACH Album-Sync!)
4. Weniger Code-Duplikation
5. Einfacheres Debugging
```

---

## 🎯 Feature-Mapping

### WatchlistWorker → TaskType.WATCHLIST_CHECK

| Feature | Alt (WatchlistWorker) | Neu (UnifiedLibraryManager) |
|---------|----------------------|----------------------------|
| Intervall | 3600s (1h) fest | Konfigurierbarer Cooldown |
| Token | Eigenes TokenManager | Shared via Plugin |
| Session | Eigene session_factory | Shared session_scope |
| Trigger | AutomationTrigger.NEW_RELEASE | Bleibt gleich |
| Datenquelle | spotify_albums (lokal) | spotify_albums (lokal) |

**Task-Dependencies:**
```python
TaskType.WATCHLIST_CHECK: [TaskType.ALBUM_SYNC]  # Braucht aktuelle Alben!
```

### DiscographyWorker → TaskType.DISCOGRAPHY

| Feature | Alt (DiscographyWorker) | Neu (UnifiedLibraryManager) |
|---------|------------------------|----------------------------|
| Intervall | 86400s (24h) fest | Konfigurierbarer Cooldown |
| Token | Eigenes TokenManager | Shared via Plugin |
| Session | Eigene session_factory | Shared session_scope |
| Trigger | AutomationTrigger.MISSING_ALBUM | Bleibt gleich |
| Datenquelle | Lokale + Spotify API | Lokale + Plugin |

**Task-Dependencies:**
```python
TaskType.DISCOGRAPHY: [TaskType.ALBUM_SYNC, TaskType.TRACK_SYNC]  # Braucht alle Daten!
```

### QualityUpgradeWorker → TaskType.QUALITY_UPGRADE

| Feature | Alt (QualityUpgradeWorker) | Neu (UnifiedLibraryManager) |
|---------|---------------------------|----------------------------|
| Intervall | 86400s (24h) fest | Konfigurierbarer Cooldown |
| Token | Nicht benötigt | Nicht benötigt |
| Session | Eigene session_factory | Shared session_scope |
| Trigger | AutomationTrigger.QUALITY_UPGRADE | Bleibt gleich |
| Datenquelle | Nur lokal | Nur lokal |

**Task-Dependencies:**
```python
TaskType.QUALITY_UPGRADE: [TaskType.TRACK_SYNC]  # Braucht Track-Qualitäts-Infos!
```

---

## 📊 Neue Task-Dependency-Grafik

```
ARTIST_SYNC ──────────────────────────────────────────────────────┐
     │                                                            │
     ▼                                                            │
ALBUM_SYNC  ─────────────────────────┬────────────────────────────┤
     │                               │                            │
     ▼                               ▼                            │
TRACK_SYNC                      ENRICHMENT                        │
     │                               │                            │
     ├───────────────────────────────┤                            │
     │                               │                            │
     ▼                               ▼                            │
WATCHLIST_CHECK              IMAGE_SYNC                           │
     │                               │                            │
     ▼                               ▼                            │
DISCOGRAPHY                    CLEANUP ◀──────────────────────────┘
     │
     ▼
QUALITY_UPGRADE
     │
     ▼
DOWNLOAD (Auto-Queue wenn enabled)
```

---

## 🔧 Implementierungs-Plan

### Phase 1: TaskType Erweiterung

**Datei:** `src/soulspot/application/workers/unified_library_worker.py`

```python
class TaskType(str, Enum):
    # ... existing types ...
    
    # NEU: Automation Tasks (von AutomationWorkerManager)
    WATCHLIST_CHECK = "watchlist_check"  # Neue Releases für Watchlist-Artists
    DISCOGRAPHY = "discography"  # Fehlende Alben identifizieren
    QUALITY_UPGRADE = "quality_upgrade"  # Upgrade-Kandidaten finden
```

```python
# Neue Cooldowns (LIDARR-INSPIRIERT!)
# Warum diese Werte? Lidarr RefreshArtist = 12h, RSS = 10min, Housekeeping = 24h
TASK_COOLDOWNS: dict[TaskType, int] = {
    # Standard Tasks: 1 Minute (schnelle Reaktion)
    TaskType.ARTIST_SYNC: 60,
    TaskType.ALBUM_SYNC: 60,
    TaskType.TRACK_SYNC: 60,
    TaskType.ENRICHMENT: 60,
    TaskType.IMAGE_SYNC: 60,
    TaskType.DOWNLOAD: 60,
    TaskType.CLEANUP: 60,
    
    # Automation Tasks: längere Cooldowns (Lidarr-Pattern!)
    TaskType.WATCHLIST_CHECK: 900,    # 15 Minuten (wie Lidarr RSS Sync)
    TaskType.DISCOGRAPHY: 43200,      # 12 Stunden (wie Lidarr RefreshArtist)
    TaskType.QUALITY_UPGRADE: 86400,  # 24 Stunden (wie Lidarr Housekeeping)
}
```

### Phase 1.5: Smart Refresh Logik (LIDARR-PATTERN!)

```python
def should_refresh_artist(artist: Artist) -> bool:
    """Lidarr-inspired smart refresh decision.
    
    Hey future me - DON'T refresh everything every time!
    This saves API calls and DB writes.
    """
    if not artist.last_sync_at:
        return True  # Never synced → ALWAYS refresh
    
    hours_since_sync = (datetime.now(UTC) - artist.last_sync_at).total_seconds() / 3600
    
    # Too recent (< 12h) → Skip
    if hours_since_sync < 12:
        return False
    
    # Stale (> 30 days) → Refresh
    if hours_since_sync > 720:  # 30 * 24
        return True
    
    # Recent release activity? → Refresh
    if artist.last_release_date:
        days_since_release = (datetime.now(UTC) - artist.last_release_date).days
        if days_since_release < 30:
            return True  # Active artist
    
    # Default: Refresh after 48h
    return hours_since_sync > 48


def should_check_watchlist(watchlist: ArtistWatchlist) -> bool:
    """Lidarr-inspired watchlist check decision."""
    if not watchlist.last_checked_at:
        return True  # Never checked
    
    # Check more often for active artists (recent releases)
    if watchlist.artist and watchlist.artist.last_release_date:
        days_since_release = (datetime.now(UTC) - watchlist.artist.last_release_date).days
        if days_since_release < 7:
            # Very active → Check every 5 min
            return (datetime.now(UTC) - watchlist.last_checked_at).total_seconds() > 300
        elif days_since_release < 30:
            # Active → Check every 15 min
            return (datetime.now(UTC) - watchlist.last_checked_at).total_seconds() > 900
    
    # Default: Every hour
    return (datetime.now(UTC) - watchlist.last_checked_at).total_seconds() > 3600
```

### Phase 2: Task-Dependencies erweitern

```python
TASK_DEPENDENCIES: dict[TaskType, list[TaskType]] = {
    # ... existing dependencies ...
    
    # Automation Tasks brauchen frische Daten!
    TaskType.WATCHLIST_CHECK: [TaskType.ALBUM_SYNC],
    TaskType.DISCOGRAPHY: [TaskType.ALBUM_SYNC, TaskType.TRACK_SYNC],
    TaskType.QUALITY_UPGRADE: [TaskType.TRACK_SYNC],
}

# NEU: Task Exclusivity (LIDARR-PATTERN!)
# Manche Tasks sollten nicht parallel laufen
TASK_EXCLUSIVE: dict[TaskType, bool] = {
    TaskType.ARTIST_SYNC: True,   # Nur einer zur Zeit
    TaskType.DISCOGRAPHY: True,   # CPU-intensiv
    TaskType.CLEANUP: True,       # DB-Write-intensiv
}
```

### Phase 2.5: Debouncing (LIDARR-PATTERN!)

```python
class DebouncedTask:
    """Lidarr-inspired debouncer for frequent events.
    
    Hey future me - wenn 10 NewReleaseEvents in 1 Sekunde kommen,
    führe WATCHLIST_CHECK nur EINMAL aus (nach 5s Cooldown).
    """
    def __init__(self, task_type: TaskType, cooldown_seconds: int = 5):
        self._task_type = task_type
        self._cooldown = cooldown_seconds
        self._pending = False
        self._last_trigger: datetime | None = None
    
    async def trigger(self, executor_fn) -> None:
        self._pending = True
        now = datetime.now(UTC)
        
        if self._last_trigger:
            elapsed = (now - self._last_trigger).total_seconds()
            if elapsed < self._cooldown:
                # Zu früh → warte
                await asyncio.sleep(self._cooldown - elapsed)
        
        if self._pending:  # Noch pending nach Warten?
            self._pending = False
            self._last_trigger = datetime.now(UTC)
            await executor_fn()
```

### Phase 3: Task-Implementierung migrieren

**WatchlistWorker._check_watchlists() → UnifiedLibraryManager._sync_watchlist_check()**

```python
async def _sync_watchlist_check(self) -> None:
    """Check watchlists for new releases.
    
    Hey future me - moved from WatchlistWorker!
    Uses local spotify_albums data (no API calls).
    Triggers AutomationTrigger.NEW_RELEASE for new albums.
    
    LIDARR-PATTERN: Uses should_check_watchlist() for smart decisions!
    """
    async with self._session_scope() as session:
        watchlist_service = WatchlistService(session, self._spotify_plugin)
        workflow_service = AutomationWorkflowService(session)
        
        # Get ALL watchlists, filter with smart logic
        all_watchlists = await watchlist_service.list_all(limit=1000)
        due_watchlists = [w for w in all_watchlists if should_check_watchlist(w)]
        
        logger.info(f"Checking {len(due_watchlists)}/{len(all_watchlists)} due watchlists")
        
        for watchlist in due_watchlists:
            # ... existing logic from WatchlistWorker._check_watchlists() ...
```

**DiscographyWorker._check_discographies() → UnifiedLibraryManager._sync_discography()**

```python
async def _sync_discography(self) -> None:
    """Check discography completeness for artists.
    
    Hey future me - moved from DiscographyWorker!
    Compares local albums with Spotify discography.
    Triggers AutomationTrigger.MISSING_ALBUM for missing albums.
    """
    # ... existing logic from DiscographyWorker._check_discographies() ...
```

**QualityUpgradeWorker._identify_upgrades() → UnifiedLibraryManager._sync_quality_upgrade()**

```python
async def _sync_quality_upgrade(self) -> None:
    """Identify quality upgrade opportunities.
    
    Hey future me - moved from QualityUpgradeWorker!
    Scans local tracks for low-bitrate files.
    Triggers AutomationTrigger.QUALITY_UPGRADE for upgrade candidates.
    """
    # ... existing logic from QualityUpgradeWorker._identify_upgrades() ...
```

### Phase 4: lifecycle.py aktualisieren

```python
# ENTFERNEN:
from soulspot.application.workers.automation_workers import AutomationWorkerManager

# ENTFERNEN: AutomationWorkerManager Erstellung und Start
# automation_manager = AutomationWorkerManager(...)
# await automation_manager.start_all()

# HINZUFÜGEN: Automation-Features in UnifiedLibraryManager aktivieren
unified_manager = UnifiedLibraryManager(
    session_scope=db.session_scope,
    spotify_plugin=spotify_plugin,
    deezer_plugin=deezer_plugin,
    # NEU: Automation Features
    watchlist_enabled=await settings.is_watchlist_enabled(),
    discography_enabled=await settings.is_discography_enabled(),
    quality_upgrade_enabled=await settings.is_quality_upgrade_enabled(),
)
```

### Phase 5: Cleanup

Nach erfolgreicher Migration:

| Datei | Aktion |
|-------|--------|
| `automation_workers.py` | ⚠️ DEPRECATE (nicht löschen für Rollback) |
| `__init__.py` | Imports aktualisieren |
| `workers/routers.py` | Status-Funktionen aktualisieren |

---

## ✅ Feature-Checklist

### Von WatchlistWorker (~200 Zeilen):

- [ ] list_due_for_check() Query
- [ ] get_new_albums_since() für jeden Artist
- [ ] AutomationTrigger.NEW_RELEASE triggern
- [ ] watchlist.update_check() aufrufen
- [ ] Graceful degradation bei fehlendem Token

### Von DiscographyWorker (~150 Zeilen):

- [ ] list_active() Watchlists Query
- [ ] DiscographyService.check_discography()
- [ ] AutomationTrigger.MISSING_ALBUM triggern
- [ ] Graceful degradation bei fehlendem Token

### Von QualityUpgradeWorker (~150 Zeilen):

- [ ] get_low_quality_tracks() Query
- [ ] QualityUpgradeService.identify_upgrade_opportunities()
- [ ] AutomationTrigger.QUALITY_UPGRADE triggern
- [ ] improvement_score Schwellwert (20.0)

### Neue Features (in UnifiedLibraryManager):

- [ ] Task-spezifische Cooldowns (TASK_COOLDOWNS dict)
- [ ] Feature-Flags per Task (enabled/disabled)
- [ ] Unified Status API für alle Tasks

---

## 📊 Ergebnis nach Konsolidierung

```
VORHER (8 Worker):                 NACHHER (7 Worker):
├── TokenRefreshWorker       ───→  TokenRefreshWorker (bleibt)
├── UnifiedLibraryManager    ┐     
│                            ├──→  UnifiedLibraryManager (erweitert)
├── AutomationWorkerManager  ┘     (inkl. Watchlist, Discography, Quality)
├── DownloadWorker           ───→  DownloadWorker (bleibt)
├── DownloadStatusWorker     ───→  DownloadStatusWorker (bleibt)
├── DownloadQueueWorker      ───→  DownloadQueueWorker (bleibt)
├── DuplicateDetectorWorker  ───→  DuplicateDetectorWorker (bleibt)
└── CleanupWorker            ───→  CleanupWorker (bleibt)

Reduzierung: 8 → 7 Worker (-12.5%)
Code: ~835 Zeilen (automation_workers.py) → ~200 Zeilen (in ULM)
Session-Handling: 4 separate → 1 shared
```

---

## 🚨 Risiken & Mitigationen

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Feature-Verlust beim Merge | Niedrig | Feature-Checklist vollständig abarbeiten |
| Intervall-Konflikte | Mittel | TASK_COOLDOWNS dict für separate Intervalle |
| DB-Lock bei langen Tasks | Niedrig | Async with session_scope pattern |
| Watchlist braucht aktulle Alben | Mittel | Dependency: WATCHLIST_CHECK nach ALBUM_SYNC |

---

## 📅 Timeline (Aktualisiert mit Lidarr-Patterns)

| Phase | Dauer | Status | Details |
|-------|-------|--------|---------|
| Phase 1: TaskType & Cooldowns | 45min | ⏳ Geplant | Enum + TASK_COOLDOWNS + Smart Refresh |
| Phase 2: Debouncer & Rate Limiter | 1h | ⏳ Geplant | TaskDebouncer Klasse + RateLimiter |
| Phase 3: Task-Dependencies | 30min | ⏳ Geplant | TASK_DEPENDENCIES erweitern |
| Phase 4: Task-Implementierung | 3-4h | ⏳ Geplant | 3 Tasks mit allen Lidarr-Patterns |
| Phase 5: lifecycle.py Update | 30min | ⏳ Geplant | AutomationWorkerManager entfernen |
| Phase 6: Testing & Validation | 1h | ⏳ Geplant | Live-Test aller Tasks |
| Phase 7: Cleanup | 15min | ⏳ Nach Validierung | Deprecation-Marker setzen |

**Geschätzte Gesamtzeit:** ~7-8 Stunden (erhöht wegen Lidarr-Qualitätsverbesserungen)

### Phase-Details mit Lidarr-Inspirationen:

**Phase 1 - TaskType & Smart Cooldowns:**
- TaskType Enum erweitern (WATCHLIST_CHECK, DISCOGRAPHY_SCAN, QUALITY_UPGRADE)
- TASK_COOLDOWNS Dict mit variablen Intervallen
- `should_execute_task()` Logik mit Smart Refresh (wie Lidarr RefreshArtist)

**Phase 2 - Debouncer & Rate Limiter:**
- `TaskDebouncer` Klasse (5-10s window wie Lidarr)
- Verhindert doppelte Tasks bei rapid events
- Rate Limiter für API-Calls (Spotify/Deezer)

**Phase 3 - Dependencies:**
- WATCHLIST_CHECK → depends on ALBUM_SYNC
- QUALITY_UPGRADE → depends on TRACK_SYNC
- Exclusive Lock: Nur 1 automation Task gleichzeitig

**Phase 4 - Task-Implementierung:**
- Jeder Task: try/except mit graceful degradation
- Circuit Breaker für externe APIs
- Detailliertes Logging (Lidarr-Style)

---

## 🔗 Verwandte Dokumente

- `docs/architecture/UNIFIED_LIBRARY_WORKER.md` - UnifiedLibraryManager Architektur
- `docs/architecture/DOWNLOAD_WORKER_CONSOLIDATION_PLAN.md` - Abgeschlossene Download-Konsolidierung
- [Lidarr Commands.cs](https://github.com/Lidarr/Lidarr/blob/develop/src/NzbDrone.Core/Queue/CommandQueue.cs) - Command Queue Pattern
- [Lidarr RefreshArtistService](https://github.com/Lidarr/Lidarr/blob/develop/src/NzbDrone.Core/Music/RefreshArtistService.cs) - Smart Refresh Logic

---

## ⚠️ Offene Fragen (Beantwortet)

1. **Sollen Automation-Tasks dieselbe Priority wie Standard-Tasks haben?**
   - ✅ **Entscheidung:** MAINTENANCE Priority (100) damit sie nach Sync laufen
   - Lidarr-Inspiration: Scheduled Tasks haben niedrigere Priority als User-Requests

2. **Sollen die Feature-Flags in UnifiedLibraryManager oder AppSettings leben?**
   - ✅ **Entscheidung:** AppSettings wie bisher, ULM liest sie beim Task-Start
   - Vorteil: User kann Tasks zur Laufzeit aktivieren/deaktivieren

3. **Was passiert wenn Watchlist-Check während Album-Sync läuft?**
   - ✅ **Entscheidung:** Dependency-System verhindert das
   - TASK_DEPENDENCIES["WATCHLIST_CHECK"] = ["ALBUM_SYNC"]

4. **Wie verhindern wir doppelte Tasks bei vielen Events?**
   - ✅ **Entscheidung:** TaskDebouncer mit 5-10s Window
   - Lidarr-Inspiration: RefreshArtist Debouncing

5. **Smart Refresh: Wann Artist wirklich prüfen?**
   - ✅ **Entscheidung:** should_refresh_artist() Logik implementieren
   - Skip wenn <1h seit letztem Check, Force wenn >30d oder neues Release

---

## 📊 Zusammenfassung

### Vorteile der Konsolidierung:

| Aspekt | Vorher | Nachher |
|--------|--------|---------|
| Worker-Anzahl | 8 | 7 (-12.5%) |
| DB Sessions | 4 separate | 1 shared |
| Code-Zeilen | ~835 | ~350 (-58%) |
| Task-Koordination | Keine | TASK_DEPENDENCIES |
| Debouncing | Keine | TaskDebouncer |
| Smart Refresh | Keine | should_refresh_artist() |
| Rate Limiting | Keine | Integriert |

### Qualitätsverbesserungen (Lidarr-inspiriert):

1. **Command Queue Pattern:** Tasks werden priorisiert abgearbeitet
2. **Smart Cooldowns:** Variable Intervalle je nach Task-Typ
3. **Debouncing:** Verhindert doppelte Arbeit bei rapid events
4. **Dependency Graph:** Garantiert korrekte Ausführungsreihenfolge
5. **Graceful Degradation:** Ein fehlender Token blockt nicht alles
6. **Detailed Logging:** Lidarr-Style "Artist X: 2 new albums, 5 missing"

### Risiko-Assessment:

| Risiko | Status | Mitigation |
|--------|--------|------------|
| Feature-Verlust | 🟢 Niedrig | Feature-Checklist |
| Intervall-Konflikte | 🟢 Gelöst | TASK_COOLDOWNS |
| Race Conditions | 🟢 Gelöst | TaskDebouncer + Dependencies |
| API Rate Limits | 🟢 Gelöst | Rate Limiter |
| Rollback nötig | 🟢 Möglich | automation_workers.py bleibt (DEPRECATED) |

---

**Plan Status:** ✅ FERTIG - Bereit zur Implementierung
