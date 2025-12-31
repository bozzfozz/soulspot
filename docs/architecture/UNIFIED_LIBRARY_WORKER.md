# Unified Library Worker Architecture

> Inspiriert von der *arr-Familie (Lidarr/Sonarr/Radarr) Task-Architektur

## 📋 Problem Statement

### Aktuelle Situation

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRAGMENTIERTE WORKER                          │
├─────────────────────────────────────────────────────────────────┤
│  SpotifySyncWorker      │ Spotify-only, eigene Loop             │
│  DeezerSyncWorker       │ Deezer-only, Code-Duplizierung        │
│  LibraryScanWorker      │ Nur lokale Files                      │
│  LibraryDiscoveryWorker │ Enrichment, 8 Phasen, wächst ständig  │
│  NewReleasesSyncWorker  │ Warum eigener Worker?                 │
│  TokenRefreshWorker     │ Spotify-spezifisch                    │
│  ImageQueueWorker       │ Bild-Downloads                        │
└─────────────────────────────────────────────────────────────────┘
```

### Konkrete Probleme

| Problem | Symptom | Auswirkung |
|---------|---------|------------|
| **Code-Duplizierung** | SpotifySyncWorker ≈ DeezerSyncWorker (70% identisch) | Bugs fixen doppelt |
| **Keine einheitliche Queue** | Jeder Worker eigene Timing-Logik | Race Conditions |
| **Service-Kopplung** | Worker hart an Provider gebunden | Tidal/Apple Music = neuer Worker |
| **8 Phasen in Discovery** | `_phase1..._phase8` wächst unkontrolliert | Wartbarkeit sinkt |
| **Kein Deduplication** | Spotify + Deezer synct gleichen Artist doppelt | DB-Bloat |

### Lidarr-Vergleich: Wie machen es die Profis?

**Lidarr's Task-System:**
```
System → Tasks → Scheduled
├── Application Check Update (nach Schedule)
├── Backup (nach Schedule)
├── Check Health (nach Schedule)
├── Housekeeping (nach Schedule)
├── Import List Sync (nach Schedule)
├── Refresh Monitored Downloads
├── Refresh Artist (für ALLE Artists)
└── RSS Sync
```

**Kernkonzepte:**
1. **Eine zentrale Task-Queue** - nicht viele Worker
2. **Scheduled Tasks** - mit konfigurierbaren Intervallen
3. **Entity-basierte Refresh** - "Refresh Artist" für alle, nicht pro Provider
4. **Health Checks** - zentrale Status-Überwachung
5. **Import Lists** - generischer Mechanismus für externe Quellen

## 🎯 Goal: Single Unified Library Worker

Inspiriert von Lidarr: **EIN Worker** der **Tasks ausführt**, nicht viele parallele Worker.

**Was verwaltet wird:**
- **Artists** (local + Spotify + Deezer + Tidal + ...)
- **Albums** (local + cloud)
- **Tracks** (local + cloud)
- **Playlists** (cloud only, per service)
- **Covers/Images** (any source)

## 🏗️ Proposed Architecture

### Lidarr-inspiriertes Task-basiertes Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedLibraryManager                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Scheduled Tasks (wie Lidarr)                                 ││
│  │ ───────────────────────────────────────────────────────────  ││
│  │ ● Refresh Library    - Scan lokale Files (1h Intervall)     ││
│  │ ● Sync Cloud Sources - Import von allen Providern (30min)   ││
│  │ ● Refresh Artists    - Metadata für alle Artists (6h)       ││
│  │ ● Refresh Albums     - Metadata für alle Albums (6h)        ││
│  │ ● Enrich Metadata    - IDs, Covers, Tags (2h)               ││
│  │ ● Cleanup Library    - Orphans entfernen (24h)              ││
│  │ ● Health Check       - System-Status (5min)                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Import Sources (generisch, nicht provider-spezifisch)       ││
│  │ ───────────────────────────────────────────────────────────  ││
│  │ ● LocalFileScanner      - Scannt Dateisystem                ││
│  │ ● SpotifyImport         - Followed Artists, Playlists       ││
│  │ ● DeezerImport          - Favorites, Playlists              ││
│  │ ● TidalImport           - (zukünftig)                       ││
│  │ ● MusicBrainzLookup     - Metadata-Enrichment               ││
│  │ ● CoverArtArchiveLookup - Cover-Enrichment                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Unified Entity Store (Single Source of Truth)               ││
│  │ ───────────────────────────────────────────────────────────  ││
│  │ Artists: id, name, spotify_id, deezer_id, mbid, image_url   ││
│  │ Albums:  id, title, artist_id, spotify_uri, deezer_id, mbid ││
│  │ Tracks:  id, title, album_id, isrc, spotify_uri, deezer_id  ││
│  │                                                              ││
│  │ → Deduplication über MBID > ISRC > Provider-IDs > Name      ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Vergleich: Alt vs. Neu

```
ALT (viele Worker):                   NEU (ein Manager + Tasks):
┌─────────────────────┐               ┌─────────────────────┐
│ SpotifySyncWorker   │               │ UnifiedLibraryMgr   │
│ DeezerSyncWorker    │               │ ├── TaskScheduler   │
│ LibraryScanWorker   │      →        │ ├── ImportSources[] │
│ LibraryDiscovery    │               │ ├── EntityStore     │
│ NewReleasesSyncWkr  │               │ └── HealthChecker   │
│ TokenRefreshWorker  │               └─────────────────────┘
│ ImageQueueWorker    │               
└─────────────────────┘               Worker-Anzahl: 7 → 1
```

## 📦 Key Components

### 1. Task Scheduler (wie Lidarr's Scheduled Tasks)

```python
@dataclass
class ScheduledTask:
    """Eine geplante Aufgabe mit Intervall und letzter Ausführung."""
    name: str
    interval: timedelta
    handler: Callable[[], Awaitable[TaskResult]]
    last_run: datetime | None = None
    enabled: bool = True
    
    @property
    def is_due(self) -> bool:
        """Prüft ob Task ausgeführt werden sollte."""
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        return datetime.now(UTC) - self.last_run >= self.interval


class TaskScheduler:
    """Zentraler Task-Scheduler (wie Lidarr's System → Tasks)."""
    
    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
    
    def register_task(self, task: ScheduledTask) -> None:
        """Registriert einen Scheduled Task."""
        self._tasks[task.name] = task
    
    async def run_loop(self) -> None:
        """Haupt-Loop: Prüft Tasks und führt fällige aus."""
        self._running = True
        while self._running:
            for task in self._tasks.values():
                if task.is_due:
                    await self._execute_task(task)
            await asyncio.sleep(60)  # Check every minute
    
    async def run_task_now(self, task_name: str) -> TaskResult:
        """Manuelle Ausführung (wie Lidarr's 'Run Now' Button)."""
        task = self._tasks.get(task_name)
        if not task:
            raise ValueError(f"Unknown task: {task_name}")
        return await self._execute_task(task)
```

### 2. Import Sources (generische Provider-Abstraktion)

```python
class ImportSource(Protocol):
    """Generische Import-Quelle (Local, Spotify, Deezer, etc.)."""
    
    @property
    def name(self) -> str: ...
    
    @property  
    def is_available(self) -> bool:
        """True wenn Source nutzbar (enabled + authenticated)."""
        ...
    
    async def import_artists(self) -> list[ArtistDTO]: ...
    async def import_albums(self, artist_id: str) -> list[AlbumDTO]: ...
    async def import_tracks(self, album_id: str) -> list[TrackDTO]: ...
    async def import_playlists(self) -> list[PlaylistDTO]: ...


class ImportSourceRegistry:
    """Registry für alle Import-Quellen."""
    
    def __init__(self) -> None:
        self._sources: dict[str, ImportSource] = {}
    
    def register(self, source: ImportSource) -> None:
        self._sources[source.name] = source
    
    def get_available_sources(self) -> list[ImportSource]:
        """Nur enabled + authenticated Sources."""
        return [s for s in self._sources.values() if s.is_available]
    
    async def import_from_all(self) -> ImportResult:
        """Importiert von allen verfügbaren Quellen."""
        result = ImportResult()
        for source in self.get_available_sources():
            try:
                artists = await source.import_artists()
                result.artists.extend(artists)
            except Exception as e:
                result.errors.append(f"{source.name}: {e}")
        return result
```

### 3. Entity Deduplication (Kernproblem lösen!)

```python
class EntityDeduplicator:
    """Dedupliziert Entities über verschiedene Quellen.
    
    Priorität für Matching:
    1. MusicBrainz ID (MBID) - universeller Standard
    2. ISRC (für Tracks) - ISO-Standard
    3. Provider-IDs - wenn gleiche ID bei Spotify/Deezer
    4. Normalized Name + Artist - Fallback
    """
    
    async def merge_artist(
        self, 
        existing: Artist | None, 
        incoming: ArtistDTO
    ) -> Artist:
        """Merged incoming DTO in bestehenden Artist."""
        if existing is None:
            # Neuer Artist
            return Artist.from_dto(incoming)
        
        # Merge Provider-IDs
        if incoming.spotify_id and not existing.spotify_id:
            existing.spotify_id = incoming.spotify_id
        if incoming.deezer_id and not existing.deezer_id:
            existing.deezer_id = incoming.deezer_id
        if incoming.musicbrainz_id and not existing.musicbrainz_id:
            existing.musicbrainz_id = incoming.musicbrainz_id
        
        # Merge Image (bevorzuge höhere Qualität)
        if incoming.image_url and not existing.image_url:
            existing.image_url = incoming.image_url
            
        return existing
    
    def find_match_key(self, dto: ArtistDTO) -> str:
        """Generiert Matching-Key für Deduplication."""
        # Priorität: MBID > Spotify > Deezer > Name
        if dto.musicbrainz_id:
            return f"mbid:{dto.musicbrainz_id}"
        if dto.spotify_id:
            return f"spotify:{dto.spotify_id}"
        if dto.deezer_id:
            return f"deezer:{dto.deezer_id}"
        return f"name:{self._normalize_name(dto.name)}"
```

### 4. Unified Library Manager (der EINE Worker)

```python
class UnifiedLibraryManager:
    """DER zentrale Library-Manager (ersetzt alle fragmentierten Worker).
    
    Inspiriert von Lidarr:
    - Scheduled Tasks statt hardcodierte Loops
    - Import Sources statt provider-spezifische Worker
    - Entity Store mit Deduplication
    - Health Checks für Monitoring
    """
    
    def __init__(
        self,
        db: Database,
        import_sources: ImportSourceRegistry,
        scheduler: TaskScheduler,
    ) -> None:
        self._db = db
        self._sources = import_sources
        self._scheduler = scheduler
        self._deduplicator = EntityDeduplicator()
        
        # Registriere Standard-Tasks
        self._register_default_tasks()
    
    def _register_default_tasks(self) -> None:
        """Registriert die Standard Scheduled Tasks."""
        tasks = [
            ScheduledTask(
                name="refresh_library",
                interval=timedelta(hours=1),
                handler=self._task_refresh_library,
            ),
            ScheduledTask(
                name="sync_cloud_sources", 
                interval=timedelta(minutes=30),
                handler=self._task_sync_cloud,
            ),
            ScheduledTask(
                name="enrich_metadata",
                interval=timedelta(hours=2),
                handler=self._task_enrich_metadata,
            ),
            ScheduledTask(
                name="refresh_discography",
                interval=timedelta(hours=6),
                handler=self._task_refresh_discography,
            ),
            ScheduledTask(
                name="cleanup_library",
                interval=timedelta(hours=24),
                handler=self._task_cleanup,
            ),
            ScheduledTask(
                name="health_check",
                interval=timedelta(minutes=5),
                handler=self._task_health_check,
            ),
        ]
        for task in tasks:
            self._scheduler.register_task(task)
    
    async def start(self) -> None:
        """Startet den Library Manager."""
        logger.info("UnifiedLibraryManager starting...")
        await self._scheduler.run_loop()
    
    # === TASK HANDLERS ===
    
    async def _task_refresh_library(self) -> TaskResult:
        """Scannt lokale Library (wie Lidarr's Refresh Artist)."""
        stats = {"scanned": 0, "added": 0, "updated": 0}
        # ... scan local files ...
        return TaskResult(success=True, stats=stats)
    
    async def _task_sync_cloud(self) -> TaskResult:
        """Synct von allen Cloud-Quellen (Spotify, Deezer, etc.)."""
        async with self._db.session_scope() as session:
            result = await self._sources.import_from_all()
            
            # Deduplicate und merge
            for artist_dto in result.artists:
                key = self._deduplicator.find_match_key(artist_dto)
                existing = await self._find_artist_by_key(session, key)
                merged = await self._deduplicator.merge_artist(existing, artist_dto)
                await self._save_artist(session, merged)
            
            await session.commit()
        
        return TaskResult(
            success=len(result.errors) == 0,
            stats={"imported": len(result.artists), "errors": len(result.errors)},
        )
```

## 🔄 Migration Plan

### Phase 1: Task Scheduler erstellen (Woche 1)
1. `task_scheduler.py` mit ScheduledTask, TaskScheduler
2. `task_result.py` mit TaskResult, TaskStats
3. Unit Tests für Scheduler-Logik
4. **Parallel zu alten Workern** - noch kein Ersatz

### Phase 2: Import Sources erstellen (Woche 2)
1. `import_source.py` mit ImportSource Protocol
2. `local_import_source.py` - wrapped LibraryScannerService
3. `spotify_import_source.py` - wrapped SpotifyPlugin
4. `deezer_import_source.py` - wrapped DeezerPlugin
5. `import_source_registry.py` mit Registry
6. **Adapter-Pattern** - nutzt existierende Plugins!

### Phase 3: Entity Deduplicator (Woche 3)
1. `entity_deduplicator.py` mit Merge-Logik
2. Matching-Algorithmus: MBID → ISRC → Provider-ID → Name
3. Tests für Edge-Cases (gleicher Name, verschiedene Artists)
4. **Kritisch für Datenintegrität!**

### Phase 4: UnifiedLibraryManager (Woche 4)
1. `unified_library_manager.py` - der EINE Worker
2. Default Tasks registrieren
3. Integration mit Orchestrator
4. **Alte Worker NOCH aktiv** - parallel testen

### Phase 5: Migration & Deprecation (Woche 5-6)
1. Feature-Flag: `use_unified_library_manager: bool`
2. A/B Testing: Alt vs. Neu
3. Alte Worker deprecaten (nicht löschen!)
4. Dokumentation aktualisieren

### Phase 6: Cleanup (Woche 7)
1. Alte Worker-Dateien löschen
2. Orchestrator-Registrierung vereinfachen  
3. API-Endpoints konsolidieren
4. **Nach 2 Wochen stabiler Produktion!**

## 📊 Benefits

| Aspect | Before | After |
|--------|--------|-------|
| Workers | 5+ separate workers | 1 unified worker |
| Code | Duplicated per service | Shared via plugins |
| New services | Add new worker file | Register plugin |
| Debugging | Check multiple workers | Single status endpoint |
| Configuration | Per-worker settings | Unified config |
| Dependencies | Complex inter-worker deps | Single worker phases |

## 🚨 Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Worker too complex | Clear phase separation, good logging |
| Migration breaks sync | Run parallel during migration |
| Performance impact | Profile phases, async where possible |
| Single point of failure | Robust error handling per phase |

## 📝 Implementation Notes

### Rate Limiting
Each provider has its own rate limiter:
```python
rate_limits = {
    "spotify": 0.1,     # 10 req/sec
    "deezer": 0.05,     # 20 req/sec  
    "musicbrainz": 1.0, # 1 req/sec (strict!)
    "caa": 0.1,         # No limit, but be nice
}
```

### Cooldowns
Per-phase cooldowns to avoid over-syncing:
```python
cooldowns = {
    "local_scan": timedelta(hours=1),
    "cloud_sync": timedelta(minutes=30),
    "enrichment": timedelta(hours=2),
    "discography": timedelta(hours=6),
    "cleanup": timedelta(hours=24),
}
```

### Priorities
Which phases run first:
```python
priorities = {
    "local_scan": 1,      # First - user's own files
    "cloud_sync": 2,      # Second - user's cloud libraries
    "enrichment": 3,      # Third - add metadata
    "discography": 4,     # Fourth - discover new albums
    "cleanup": 5,         # Last - maintenance
}
```

## 📁 File Structure (Neue Dateien)

```
src/soulspot/application/
├── library/                          # NEUES Modul
│   ├── __init__.py
│   ├── task_scheduler.py             # ScheduledTask, TaskScheduler
│   ├── task_result.py                # TaskResult, TaskStats
│   ├── import_source.py              # ImportSource Protocol
│   ├── entity_deduplicator.py        # Merge-Logik
│   └── unified_library_manager.py    # DER zentrale Worker
│
├── library/sources/                  # Import Sources
│   ├── __init__.py
│   ├── local_import_source.py        # Lokale Files
│   ├── spotify_import_source.py      # Spotify API (wraps Plugin)
│   ├── deezer_import_source.py       # Deezer API (wraps Plugin)
│   └── registry.py                   # ImportSourceRegistry
│
└── workers/                          # Existierend, wird vereinfacht
    ├── orchestrator.py               # Bleibt, registriert nur UnifiedLibraryManager
    └── unified_library_worker.py     # Thin wrapper für Orchestrator-Kompatibilität
```

## ❓ Entscheidungsmatrix

### Sollte ich einen neuen Worker erstellen?

```
Frage: Braucht mein Feature einen eigenen Worker?
                    │
                    ▼
      ┌────────────────────────┐
      │ Ist es ein NEUER       │
      │ Provider (Tidal, etc)? │
      └─────────┬──────────────┘
                │
          JA    │    NEIN
           │    │      │
           ▼    │      ▼
  ┌──────────────┐  ┌────────────────────────┐
  │ Erstelle     │  │ Ist es ein neuer       │
  │ ImportSource │  │ periodischer Task?     │
  │ + registriere│  └───────────┬────────────┘
  └──────────────┘              │
                          JA    │    NEIN
                           │    │      │
                           ▼    │      ▼
                  ┌──────────────┐  ┌────────────────────┐
                  │ Erstelle     │  │ Füge zur           │
                  │ ScheduledTask│  │ existierenden Task │
                  │ im Manager   │  │ hinzu (kein neuer) │
                  └──────────────┘  └────────────────────┘
```

### Wann KEINEN neuen Worker erstellen?

| Situation | Stattdessen |
|-----------|-------------|
| Neuer Provider (Tidal) | `TidalImportSource` erstellen, registrieren |
| Neuer Enrichment-Step | Zu `enrich_metadata` Task hinzufügen |
| Neuer Cleanup-Task | Zu `cleanup_library` Task hinzufügen |
| Neuer Background-Job | Als `ScheduledTask` registrieren |
| Neuer API-Sync | Bestehenden `sync_cloud_sources` erweitern |

## 🎯 Success Criteria

- [ ] Single worker manages all library operations
- [ ] No duplicate sync of same entity from different workers
- [ ] Easy to add new providers (just register plugin)
- [ ] Clear logging per phase
- [ ] Configurable cooldowns/priorities
- [ ] Graceful degradation if one provider fails
- [ ] Status API shows unified health

## 📚 Referenzen

- [Lidarr Wiki - System](https://wiki.servarr.com/lidarr/system)
- [Sonarr Wiki - Activity](https://wiki.servarr.com/sonarr/activity)
- [SoulSpot Architecture Instructions](.github/instructions/architecture.instructions.md)
