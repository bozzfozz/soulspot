# Unified Library Worker Architecture

> Inspiriert von der *arr-Familie (Lidarr/Sonarr/Radarr) Task-Architektur

## 🏠 Ownership Model (KERNKONZEPT)

### Was bedeutet "Owned"?

**Owned = "Das gehört zu meiner Bibliothek"**

```
┌───────────────────────────────────────────────────────────────────────┐
│                        OWNERSHIP LIFECYCLE                             │
├───────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  1. LOCAL FILES (Scan)                                                 │
│  ─────────────────────                                                 │
│  ┌───────────┐                                                         │
│  │ MP3/FLAC  │ → owned=true, downloaded=true, source="local"           │
│  │ auf Disk  │   (bereits vorhanden, kein Download nötig)              │
│  └───────────┘                                                         │
│                                                                        │
│  2. CLOUD LIKED/FOLLOWED (Sync)                                        │
│  ──────────────────────────────                                        │
│  ┌───────────┐                                                         │
│  │ Spotify   │ → owned=true, downloaded=false, source="spotify"        │
│  │ Followed  │   → SOFORT in Library + Queue für Download              │
│  └───────────┘                                                         │
│                                                                        │
│  ┌───────────┐                                                         │
│  │ Deezer    │ → owned=true, downloaded=false, source="deezer"         │
│  │ Favorites │   → SOFORT in Library + Queue für Download              │
│  └───────────┘                                                         │
│                                                                        │
│  ┌───────────┐                                                         │
│  │ Tidal     │ → owned=true, downloaded=false, source="tidal"          │
│  │ Liked     │   → SOFORT in Library + Queue für Download              │
│  └───────────┘                                                         │
│                                                                        │
│  3. DOWNLOAD PIPELINE (Automatisch)                                    │
│  ───────────────────────────────────                                   │
│  Track (owned=true, downloaded=false)                                  │
│       │                                                                │
│       ▼                                                                │
│  DownloadQueue → DownloadSource (slskd/sabnzbd/...)                    │
│       │                                                                │
│       ▼                                                                │
│  Track (downloaded=true, local_path="/music/Artist/Album/track.flac") │
│                                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

### Entity States

```python
class OwnershipState(str, Enum):
    """Ownership-Status eines Tracks/Albums/Artists."""
    OWNED = "owned"           # In meiner Library, wird verwaltet
    DISCOVERED = "discovered" # Bekannt (z.B. durch Browse), aber nicht owned
    IGNORED = "ignored"       # Explizit ignoriert


class DownloadState(str, Enum):
    """Download-Status eines Tracks.
    
    WICHTIG: Default ist NOT_NEEDED, nicht PENDING!
    Auto-Queue nur wenn library.auto_queue_downloads=true.
    """
    NOT_NEEDED = "not_needed"   # Kein Download nötig/gewollt (default!)
    PENDING = "pending"         # In Download-Queue (nur bei auto_queue=true)
    DOWNLOADING = "downloading" # Wird gerade heruntergeladen
    DOWNLOADED = "downloaded"   # Erfolgreich heruntergeladen
    FAILED = "failed"           # Download fehlgeschlagen
```

### Download-State Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DOWNLOAD STATE MACHINE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LOCAL FILE SCAN                                                     │
│  ───────────────                                                     │
│  Datei gefunden → download_state = DOWNLOADED                        │
│                   local_path = "/music/..."                          │
│                                                                      │
│  CLOUD SYNC (auto_queue=FALSE, default!)                             │
│  ───────────────────────────────────────                             │
│  Liked Track → download_state = NOT_NEEDED                           │
│                (Benutzer kann manuell downloaden)                    │
│                                                                      │
│  CLOUD SYNC (auto_queue=TRUE)                                        │
│  ─────────────────────────────                                       │
│  Liked Track → download_state = PENDING                              │
│                → automatisch in Download-Queue                       │
│                                                                      │
│  MANUELLER DOWNLOAD (Button in UI)                                   │
│  ─────────────────────────────────                                   │
│  User klickt "Download" → download_state = PENDING                   │
│                                                                      │
│  DOWNLOAD PROZESS                                                    │
│  ────────────────                                                    │
│  PENDING → DOWNLOADING → DOWNLOADED                                  │
│              ↓                                                       │
│            FAILED (bei Fehler, kann retry)                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Track Entity (erweitert)

```python
@dataclass
class Track:
    """Track mit vollständigem Ownership-Model."""
    id: int
    title: str
    artist_id: int
    album_id: int | None
    
    # === IDs für Matching ===
    isrc: str | None = None
    spotify_uri: str | None = None
    deezer_id: str | None = None
    tidal_id: str | None = None
    musicbrainz_id: str | None = None
    
    # === OWNERSHIP MODEL ===
    ownership_state: OwnershipState = OwnershipState.DISCOVERED
    primary_source: str | None = None  # "local", "spotify", "deezer", "tidal"
    
    # === DOWNLOAD STATE ===
    # DEFAULT = NOT_NEEDED (User muss explizit downloaden, außer auto_queue=true)
    download_state: DownloadState = DownloadState.NOT_NEEDED
    local_path: str | None = None  # Pfad zur lokalen Datei (wenn downloaded)
    
    # === Metadata ===
    duration_ms: int | None = None
    track_number: int | None = None
    genre: str | None = None
    
    @property
    def is_owned(self) -> bool:
        """Gehört zur Library (unabhängig ob downloaded)."""
        return self.ownership_state == OwnershipState.OWNED
    
    @property
    def is_downloaded(self) -> bool:
        """Ist lokal verfügbar."""
        return self.download_state == DownloadState.DOWNLOADED or self.local_path is not None
    
    @property
    def needs_download(self) -> bool:
        """Muss noch heruntergeladen werden."""
        return (
            self.is_owned and 
            self.download_state == DownloadState.PENDING
        )
```

### Sync-Logik: Cloud → Library (KEINE Downloads!)

```python
async def sync_cloud_liked(self, source: ImportSource) -> SyncResult:
    """Synct Liked/Followed von Cloud-Provider zur Library.
    
    Ablauf:
    1. Hole Liked Artists/Albums/Tracks von Provider
    2. Markiere als owned=true
    3. Setze download_state (aber führe KEINE Downloads aus!)
    
    Downloads werden vom separaten DownloadWorker verarbeitet!
    """
    result = SyncResult()
    
    # Setting prüfen: Auto-Queue aktiviert?
    auto_queue = await self._settings.get_bool(
        "library.auto_queue_downloads", 
        default=False  # 🚨 DEFAULT: AUS (während Entwicklung)
    )
    
    # 1. Liked Artists holen
    liked_artists = await source.get_followed_artists()
    for artist_dto in liked_artists:
        # 2. In Library übernehmen
        artist = await self._upsert_artist(artist_dto)
        artist.ownership_state = OwnershipState.OWNED
        artist.primary_source = source.name  # "spotify", "deezer", etc.
        result.artists_synced += 1
        
        # 3. Discography holen und als owned markieren
        albums = await source.get_artist_albums(artist_dto.provider_id)
        for album_dto in albums:
            album = await self._upsert_album(album_dto, artist.id)
            album.ownership_state = OwnershipState.OWNED
            result.albums_synced += 1
            
            # 4. Tracks als owned markieren + download_state setzen
            tracks = await source.get_album_tracks(album_dto.provider_id)
            for track_dto in tracks:
                track = await self._upsert_track(track_dto, album.id)
                track.ownership_state = OwnershipState.OWNED
                
                # 5. Download-State setzen (aber NICHT downloaden!)
                if auto_queue:
                    # DownloadWorker wird diesen Track finden und downloaden
                    track.download_state = DownloadState.PENDING
                else:
                    # Kein automatischer Download - User muss manuell starten
                    track.download_state = DownloadState.NOT_NEEDED
                    
                result.tracks_synced += 1
                # ❌ KEIN: await self._queue_for_download(track)
                # Downloads macht der DownloadWorker!
    
    return result
```

### Konfiguration: Auto-Download Queue

**Settings-Key:** `library.auto_queue_downloads`

| Wert | Verhalten | Wann nutzen? |
|------|-----------|--------------|
| `false` (default) | Liked Tracks werden als owned markiert, aber NICHT automatisch heruntergeladen | Entwicklung, Testing, manueller Betrieb |
| `true` | Liked Tracks werden automatisch in Download-Queue eingereiht | Produktions-Betrieb, "Fire & Forget" |

**UI-Integration:**
```
Settings → Library → Automation
┌────────────────────────────────────────────────────────────┐
│  ☐ Automatically download liked tracks                     │
│    When enabled, tracks you like on Spotify/Deezer/Tidal   │
│    will automatically be queued for download via slskd.    │
│                                                            │
│    ⚠️ This can use significant bandwidth and storage!      │
└────────────────────────────────────────────────────────────┘
```

**Manueller Download (wenn Auto-Queue aus):**
```
Library → Album → Track → "Download" Button
       oder
Library → Album → "Download All" Button
       oder
Library → Artist → "Download Discography" Button
```

### Download Sources (SEPARATER WORKER!)

> **HINWEIS:** Die Download-Logik gehört NICHT zum UnifiedLibraryManager!
> Sie bleibt beim existierenden `DownloadWorker`.

Der UnifiedLibraryManager setzt nur `download_state=PENDING`.  
Der DownloadWorker findet diese Tracks und verarbeitet sie.

Siehe: `src/soulspot/application/workers/download_worker.py`

---

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
| **KEINE REIHENFOLGE** | Enrichment läuft bevor Entities existieren | Inkomplette Daten |

---

## 🔢 Task-Reihenfolge (KRITISCH!)

### Das Problem: Chaotische Ausführung

```
AKTUELL (falsch!):
┌──────────────────────────────────────────────────────────────────┐
│  SpotifySyncWorker (30 min) ─┬─ LibraryDiscovery (2h) ─┬─ ???   │
│  DeezerSyncWorker  (30 min) ─┘  ImageBackfill (30min) ─┘        │
│                                                                  │
│  PROBLEM: Alles läuft parallel ohne Abhängigkeiten!              │
│  → Enrichment findet keine Artists (noch nicht gesynct)          │
│  → Images werden geholt bevor MusicBrainz IDs da sind            │
│  → Discography wird gesucht bevor Artist vollständig             │
└──────────────────────────────────────────────────────────────────┘
```

### Die Lösung: Abhängigkeitsbasierte Reihenfolge

```
PERFEKTE REIHENFOLGE (nach Abhängigkeiten):
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  PHASE 1: DISCOVER (Was gehört zu meiner Library?)               │
│  ════════════════════════════════════════════════                │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐             │
│  │ Local Scan  │   │ Spotify     │   │ Deezer      │             │
│  │ (Files)     │   │ Likes/Foll. │   │ Favorites   │             │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘             │
│         │                 │                 │                    │
│         └─────────────────┴─────────────────┘                    │
│                           │                                      │
│                           ▼                                      │
│            ┌─────────────────────────────┐                       │
│            │     DEDUPLICATION           │                       │
│            │  (Merge by MBID/ISRC/Name)  │                       │
│            └──────────────┬──────────────┘                       │
│                           │                                      │
│                           ▼                                      │
│            Artists (owned=true, incomplete)                      │
│            Albums  (owned=true, incomplete)                      │
│            Tracks  (owned=true, incomplete)                      │
│                                                                  │
│  PHASE 2: IDENTIFY (Universal IDs für Matching)                  │
│  ════════════════════════════════════════════                    │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Artists ohne MusicBrainz ID                 │                 │
│  │ → MusicBrainz Lookup → Set MBID             │                 │
│  └─────────────────────────────────────────────┘                 │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Tracks ohne ISRC                            │                 │
│  │ → Spotify/Deezer Lookup → Set ISRC          │                 │
│  └─────────────────────────────────────────────┘                 │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Albums ohne MusicBrainz ID                  │                 │
│  │ → MusicBrainz Lookup → Set MBID             │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                  │
│  PHASE 3: ENRICH (Metadata vervollständigen)                     │
│  ════════════════════════════════════════════                    │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Artists mit MBID aber fehlenden Daten       │                 │
│  │ → MusicBrainz Details → Genres, Tags, etc.  │                 │
│  └─────────────────────────────────────────────┘                 │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Albums mit MBID aber fehlenden Daten        │                 │
│  │ → MusicBrainz Details → Release Date, etc.  │                 │
│  └─────────────────────────────────────────────┘                 │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Tracks mit ISRC aber fehlenden Daten        │                 │
│  │ → Provider Details → Duration, etc.         │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                  │
│  PHASE 4: EXPAND (Discography erweitern)                         │
│  ════════════════════════════════════════                        │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Owned Artists mit bekannter Discography     │                 │
│  │ → Check: Fehlen Albums in Library?          │                 │
│  │ → Auto-Add wenn gewünscht                   │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                  │
│  PHASE 5: IMAGERY (Cover & Artist Images)                        │
│  ════════════════════════════════════════                        │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Entities mit MBID aber ohne image_url       │                 │
│  │ → CoverArtArchive → Get URL                 │                 │
│  │ → Queue Download Job für ImageDownloadWorker│                 │
│  └─────────────────────────────────────────────┘                 │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Entities ohne MBID → Fallback               │                 │
│  │ → Spotify API → images[0].url               │                 │
│  │ → Deezer API → picture_xl                   │                 │
│  │ → Queue Download Job für ImageDownloadWorker│                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                  │
│  PHASE 6: CLEANUP (Housekeeping)                                 │
│  ════════════════════════════════                                │
│            │                                                     │
│            ▼                                                     │
│  ┌─────────────────────────────────────────────┐                 │
│  │ Orphaned Entities entfernen                 │                 │
│  │ Stale Downloads bereinigen                  │                 │
│  │ Duplicate Detection & Merge                 │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Task-Definitionen mit Abhängigkeiten

```python
@dataclass
class ScheduledTask:
    """Scheduled Task mit Abhängigkeiten."""
    name: str
    interval: timedelta
    handler: Callable[[], Awaitable[TaskResult]]
    depends_on: list[str] = field(default_factory=list)  # NEU!
    last_run: datetime | None = None
    last_success: datetime | None = None  # NEU!
    enabled: bool = True
    
    @property
    def dependencies_satisfied(self, completed_tasks: set[str]) -> bool:
        """Prüft ob alle Abhängigkeiten erfüllt sind."""
        return all(dep in completed_tasks for dep in self.depends_on)


# Task-Registrierung mit Reihenfolge
tasks = [
    # PHASE 1: DISCOVER (keine Abhängigkeiten)
    ScheduledTask(
        name="scan_local_library",
        interval=timedelta(hours=1),
        handler=self._task_scan_local,
        depends_on=[],  # Läuft immer zuerst
    ),
    ScheduledTask(
        name="sync_spotify_likes",
        interval=timedelta(minutes=30),
        handler=self._task_sync_spotify,
        depends_on=[],  # Parallel zu local_scan
    ),
    ScheduledTask(
        name="sync_deezer_favorites",
        interval=timedelta(minutes=30),
        handler=self._task_sync_deezer,
        depends_on=[],  # Parallel zu local_scan
    ),
    
    # PHASE 2: IDENTIFY (nach Discover)
    ScheduledTask(
        name="identify_artists",
        interval=timedelta(hours=2),
        handler=self._task_identify_artists,
        depends_on=["scan_local_library", "sync_spotify_likes", "sync_deezer_favorites"],
    ),
    ScheduledTask(
        name="identify_albums",
        interval=timedelta(hours=2),
        handler=self._task_identify_albums,
        depends_on=["identify_artists"],  # Artists müssen IDs haben!
    ),
    ScheduledTask(
        name="identify_tracks",
        interval=timedelta(hours=2),
        handler=self._task_identify_tracks,
        depends_on=["identify_albums"],  # Albums müssen IDs haben!
    ),
    
    # PHASE 3: ENRICH (nach Identify)
    ScheduledTask(
        name="enrich_metadata",
        interval=timedelta(hours=3),
        handler=self._task_enrich_metadata,
        depends_on=["identify_artists", "identify_albums", "identify_tracks"],
    ),
    
    # PHASE 4: EXPAND (nach Enrich)
    ScheduledTask(
        name="expand_discography",
        interval=timedelta(hours=6),
        handler=self._task_expand_discography,
        depends_on=["enrich_metadata"],  # Braucht vollständige Artist-Daten
    ),
    
    # PHASE 5: IMAGERY (nach Identify, braucht MBIDs!)
    ScheduledTask(
        name="enrich_images",
        interval=timedelta(hours=2),
        handler=self._task_enrich_images,
        depends_on=["identify_artists", "identify_albums"],  # Braucht MBIDs!
    ),
    
    # PHASE 6: CLEANUP (ganz am Ende)
    ScheduledTask(
        name="cleanup_library",
        interval=timedelta(hours=24),
        handler=self._task_cleanup,
        depends_on=["enrich_metadata", "enrich_images"],  # Nach allem anderen
    ),
]
```

### Scheduler mit Abhängigkeitsauflösung

```python
class TaskScheduler:
    """Task-Scheduler mit Abhängigkeitsauflösung."""
    
    async def run_cycle(self) -> None:
        """Führt einen kompletten Task-Cycle mit Reihenfolge aus."""
        completed_this_cycle: set[str] = set()
        
        # Tasks nach Abhängigkeitstiefe sortieren
        sorted_tasks = self._topological_sort(self._tasks.values())
        
        for task in sorted_tasks:
            if not task.is_due:
                continue
            if not task.dependencies_satisfied(completed_this_cycle):
                logger.debug(f"Skipping {task.name}: dependencies not met")
                continue
            
            result = await self._execute_task(task)
            if result.success:
                completed_this_cycle.add(task.name)
                task.last_success = datetime.now(UTC)
    
    def _topological_sort(self, tasks: Iterable[ScheduledTask]) -> list[ScheduledTask]:
        """Sortiert Tasks nach Abhängigkeiten (Kahn's Algorithm)."""
        # ... Topologische Sortierung ...
        pass
```

### 6-Phasen Zusammenfassung

| Phase | Name | Was passiert | Abhängig von | Intervall |
|-------|------|--------------|--------------|-----------|
| 1 | **DISCOVER** | Local scan, Cloud sync (Likes/Follows) | – | 30-60 min |
| 2 | **IDENTIFY** | MBID für Artists, MBID für Albums, ISRC für Tracks | Phase 1 | 2h |
| 3 | **ENRICH** | Genres, Tags, Release Dates, Duration | Phase 2 | 3h |
| 4 | **EXPAND** | Missing albums from discography | Phase 3 | 6h |
| 5 | **IMAGERY** | Cover URLs + Queue Download Jobs | Phase 2 | 2h |
| 6 | **CLEANUP** | Orphans, Duplicates, Stale data | Phase 3+5 | 24h |

### Warum diese Reihenfolge?

```
1. DISCOVER zuerst:
   - Ohne Entities gibt es nichts zu enrichen
   - Basis für alles andere
   
2. IDENTIFY vor ENRICH:
   - MusicBrainz braucht MBID für detaillierte Daten
   - ISRC ist Matching-Key für Tracks
   - Ohne IDs nur Name-basiertes Matching (fehleranfällig)
   
3. ENRICH vor EXPAND:
   - Discography-Lookup braucht MBID
   - Ohne vollständige Artist-Daten → falsche Albums
   
4. IMAGERY nach IDENTIFY:
   - CoverArtArchive braucht MBID!
   - Ohne MBID nur Provider-Fallback (schlechtere Qualität)
   
5. CLEANUP ganz am Ende:
   - Kann nur Orphans finden wenn alles gesynct ist
   - Duplicate Detection braucht alle IDs
```

---

## 🧹 Cleanup-Logik (Präzise Aufräumung)

### Was Cleanup NICHT tut

```
❌ FALSCH: Wildes Löschen von allem was "unvollständig" aussieht
❌ FALSCH: Tracks löschen die keine Provider-IDs haben
❌ FALSCH: Artists löschen die keine MBID haben
❌ FALSCH: Albums löschen die keine Covers haben
```

### Was Cleanup TUT (nur kaskadierende Orphans)

```
✓ RICHTIG: Lösche nur was WIRKLICH verwaist ist
✓ RICHTIG: Kaskadierende Löschung bei expliziten User-Aktionen
✓ RICHTIG: Bereinige nur Referenzen zu nicht mehr existierenden Entities
```

### Cleanup-Szenarien

```
┌──────────────────────────────────────────────────────────────────┐
│                      CLEANUP SCENARIOS                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SZENARIO 1: User löscht Artist                                   │
│  ─────────────────────────────────                                │
│                                                                   │
│    User: "Delete Artist 'Pink Floyd'"                             │
│         │                                                         │
│         ▼                                                         │
│    ┌─────────────────────────────────────────┐                    │
│    │ Artist löschen                          │                    │
│    │ → owned=false setzen (nicht hart löschen!)                   │
│    │                                         │                    │
│    │ Kaskadierende Prüfung:                  │                    │
│    │ - Hat dieser Artist noch owned Albums?  │                    │
│    │ - Falls NEIN → Albums auch owned=false  │                    │
│    │ - Hat Album noch owned Tracks?          │                    │
│    │ - Falls NEIN → Tracks auch owned=false  │                    │
│    └─────────────────────────────────────────┘                    │
│                                                                   │
│    WICHTIG: Entities bleiben in DB (für zukünftiges Re-Add)!      │
│    Nur ownership_state ändert sich.                               │
│                                                                   │
│  SZENARIO 2: User löscht Album                                    │
│  ──────────────────────────────                                   │
│                                                                   │
│    User: "Delete Album 'The Wall'"                                │
│         │                                                         │
│         ▼                                                         │
│    ┌─────────────────────────────────────────┐                    │
│    │ Album owned=false setzen                │                    │
│    │ → Tracks des Albums: owned=false        │                    │
│    │                                         │                    │
│    │ Prüfung: Hat Artist noch owned Albums?  │                    │
│    │ - Falls JA → Artist bleibt owned        │                    │
│    │ - Falls NEIN → Artist owned=false       │                    │
│    └─────────────────────────────────────────┘                    │
│                                                                   │
│  SZENARIO 3: User entfernt Track aus Cloud-Likes                  │
│  ───────────────────────────────────────────────                  │
│                                                                   │
│    Spotify: User unliked Track                                    │
│         │                                                         │
│         ▼                                                         │
│    ┌─────────────────────────────────────────┐                    │
│    │ Sync erkennt: Track nicht mehr in Likes │                    │
│    │ → Track.ownership_state = DISCOVERED    │                    │
│    │   (nicht mehr owned, aber bekannt)      │                    │
│    │                                         │                    │
│    │ Prüfung: Hat Album noch owned Tracks?   │                    │
│    │ - Falls JA → Album bleibt owned         │                    │
│    │ - Falls NEIN → Album ownership prüfen   │                    │
│    └─────────────────────────────────────────┘                    │
│                                                                   │
│  SZENARIO 4: Echter Orphan (DB-Inkonsistenz)                      │
│  ───────────────────────────────────────────                      │
│                                                                   │
│    Track existiert aber artist_id zeigt auf gelöschten Artist     │
│         │                                                         │
│         ▼                                                         │
│    ┌─────────────────────────────────────────┐                    │
│    │ CLEANUP findet referenzielle Orphans:   │                    │
│    │ - Track.artist_id → Artist existiert    │                    │
│    │   nicht mehr                            │                    │
│    │ → Track.artist_id = NULL setzen         │                    │
│    │ → Track als "orphaned" markieren        │                    │
│    │ → Optional: Versuche Artist neu zuzuordnen│                  │
│    └─────────────────────────────────────────┘                    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Cleanup-Tasks im Detail

```python
async def _task_cleanup(self) -> TaskResult:
    """Phase 6: Präzise Cleanup-Logik.
    
    NUR aufräumen was WIRKLICH verwaist ist!
    """
    stats = {"orphaned_tracks": 0, "orphaned_albums": 0, "stale_downloads": 0}
    
    async with self._db.session_scope() as session:
        # 1. Referenzielle Orphans (DB-Inkonsistenzen)
        stats["orphaned_tracks"] = await self._cleanup_orphaned_tracks(session)
        stats["orphaned_albums"] = await self._cleanup_orphaned_albums(session)
        
        # 2. Stale Downloads (FAILED seit > 7 Tagen)
        stats["stale_downloads"] = await self._cleanup_stale_downloads(session)
        
        # 3. NICHT: Artists ohne Albums löschen (könnten gewollt sein!)
        # 3. NICHT: Tracks ohne ISRC löschen (ist Enrichment-Job!)
        # 3. NICHT: Albums ohne Cover löschen (ist Imagery-Job!)
        
        await session.commit()
    
    return TaskResult(success=True, stats=stats)


async def _cleanup_orphaned_tracks(self, session: AsyncSession) -> int:
    """Findet Tracks deren Artist nicht mehr existiert."""
    # SELECT t.* FROM tracks t
    # LEFT JOIN artists a ON t.artist_id = a.id
    # WHERE t.artist_id IS NOT NULL AND a.id IS NULL
    query = (
        select(TrackModel)
        .outerjoin(ArtistModel, TrackModel.artist_id == ArtistModel.id)
        .where(TrackModel.artist_id.isnot(None))
        .where(ArtistModel.id.is_(None))
    )
    orphans = (await session.execute(query)).scalars().all()
    
    for track in orphans:
        # Option A: artist_id auf NULL setzen
        track.artist_id = None
        # Option B: Versuche neu zuzuordnen über Name/ISRC
    
    return len(orphans)


async def _cleanup_stale_downloads(self, session: AsyncSession) -> int:
    """Bereinigt Downloads die seit > 7 Tagen FAILED sind."""
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)
    
    query = (
        update(TrackModel)
        .where(TrackModel.download_state == DownloadState.FAILED)
        .where(TrackModel.download_updated_at < seven_days_ago)
        .values(download_state=DownloadState.NOT_NEEDED)
    )
    result = await session.execute(query)
    return result.rowcount
```

### Was Cleanup NICHT tut (mit Begründung)

| Was NICHT löschen | Warum |
|-------------------|-------|
| Artists ohne MBID | Enrichment-Job, nicht Cleanup |
| Albums ohne Cover | Imagery-Job, nicht Cleanup |
| Tracks ohne ISRC | Enrichment-Job, nicht Cleanup |
| Artists ohne Albums | Könnte gewollt sein (Watchlist) |
| Nicht-owned Entities | Bleiben für zukünftiges Re-Add |
| Incomplete Downloads | Retry-Logic, nicht Cleanup |

### Ownership vs. Deletion

```
WICHTIG: "Löschen" bedeutet ownership_state ändern, NICHT aus DB entfernen!

owned=true   → In meiner Library
owned=false  → Nicht mehr in Library, aber Entity bleibt (für Re-Add)

Warum?
- User liked Artist erneut → Alle Daten noch da, kein erneutes Enrichment
- Prevents data loss bei versehentlichem Unlike
- History bleibt erhalten
```

---

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
        """Registriert die Standard Scheduled Tasks.
        
        WICHTIG: Download-Verwaltung ist NICHT hier!
        Downloads werden von einem separaten DownloadWorker verwaltet.
        """
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
        """Synct von allen Cloud-Quellen (Spotify, Deezer, etc.).
        
        Markiert Liked/Followed als owned=true.
        Download-State wird gesetzt, aber Downloads sind Sache des DownloadWorkers!
        """
        async with self._db.session_scope() as session:
            result = await self._sources.import_from_all()
            
            # Deduplicate und merge
            for artist_dto in result.artists:
                key = self._deduplicator.find_match_key(artist_dto)
                existing = await self._find_artist_by_key(session, key)
                merged = await self._deduplicator.merge_artist(existing, artist_dto)
                
                # Als OWNED markieren (aus Cloud-Liked)
                merged.ownership_state = OwnershipState.OWNED
                await self._save_artist(session, merged)
            
            await session.commit()
        
        return TaskResult(
            success=len(result.errors) == 0,
            stats={"imported": len(result.artists), "errors": len(result.errors)},
        )
    
    # HINWEIS: Kein _task_process_downloads hier!
    # Downloads werden vom separaten DownloadWorker verwaltet.
    # UnifiedLibraryManager setzt nur download_state=PENDING,
    # der DownloadWorker verarbeitet die Queue.
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
├── library/                          # NEUES Modul (nur Library-Management!)
│   ├── __init__.py
│   ├── task_scheduler.py             # ScheduledTask, TaskScheduler
│   ├── task_result.py                # TaskResult, TaskStats
│   ├── import_source.py              # ImportSource Protocol
│   ├── entity_deduplicator.py        # Merge-Logik
│   ├── ownership.py                  # OwnershipState, DownloadState Enums
│   └── unified_library_manager.py    # DER zentrale Library-Worker
│
├── library/sources/                  # Import Sources (Cloud → Library)
│   ├── __init__.py
│   ├── local_import_source.py        # Lokale Files (owned + downloaded)
│   ├── spotify_import_source.py      # Spotify API (wraps Plugin)
│   ├── deezer_import_source.py       # Deezer API (wraps Plugin)
│   ├── tidal_import_source.py        # Tidal API (zukünftig)
│   └── registry.py                   # ImportSourceRegistry
│
└── workers/                          # Existierend - wird stark vereinfacht!
    ├── orchestrator.py               # Registriert alle Worker
    ├── unified_library_worker.py     # DER Library Worker (inkl. Images!)
    ├── download_worker.py            # BLEIBT! Audio-Downloads
    └── token_refresh_worker.py       # BLEIBT! Auth-spezifisch

# ZU LÖSCHEN nach Migration (7 Worker → 3 Worker):
# ├── SpotifySyncWorker.py           # → UnifiedLibraryManager
# ├── DeezerSyncWorker.py            # → UnifiedLibraryManager  
# ├── LibraryScanWorker.py           # → UnifiedLibraryManager
# ├── library_discovery_worker.py    # → UnifiedLibraryManager
# ├── new_releases_sync_worker.py    # → UnifiedLibraryManager
# ├── ImageWorker.py (Backfill)      # → UnifiedLibraryManager.enrich_images
# └── image_queue_worker.py          # → UnifiedLibraryManager.enrich_images
```

### Worker-Verantwortlichkeiten (Separation of Concerns)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WORKER RESPONSIBILITIES                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  UnifiedLibraryManager (NEU)                                         │
│  ──────────────────────────                                          │
│  ✓ Artist/Album/Track Management                                     │
│  ✓ Cloud Sync (Spotify, Deezer, Tidal Likes/Follows)                │
│  ✓ Local Library Scan                                                │
│  ✓ Metadata Enrichment (MusicBrainz)                                 │
│  ✓ Entity Deduplication                                              │
│  ✓ Image URL Enrichment (holt URLs, nicht die Bilder selbst!)        │
│  ✓ Setzt download_state=PENDING wenn nötig                           │
│  ✓ Queued Image-Jobs für ImageDownloadWorker                         │
│  ✗ KEINE Audio-Download-Logik!                                       │
│  ✗ KEINE Image-Download-Logik (nur URLs sammeln!)                    │
│                                                                      │
│  DownloadWorker (EXISTIEREND, bleibt!)                               │
│  ──────────────────────────────────────                              │
│  ✓ Sucht Tracks mit download_state=PENDING                           │
│  ✓ Sucht Download-Kandidaten (slskd, sabnzbd, ...)                   │
│  ✓ Startet Audio-Downloads                                           │
│  ✓ Setzt download_state=DOWNLOADED nach Erfolg                       │
│  ✗ KEINE Library-Logik!                                              │
│  ✗ KEINE Image-Logik!                                                │
│                                                                      │
│  ImageDownloadWorker (ehemals ImageQueueWorker)                      │
│  ───────────────────────────────────────────────                     │
│  ✓ Prozessiert Image-Download-Queue                                  │
│  ✓ Lädt Bilder von URLs herunter                                     │
│  ✓ Speichert Bilder lokal (/images/artists/, /images/albums/)        │
│  ✓ Aktualisiert image_path in DB nach Download                       │
│  ✗ KEINE URL-Ermittlung (macht UnifiedLibraryManager!)               │
│                                                                      │
│  ImageBackfillWorker → WIRD GELÖSCHT!                                │
│  ─────────────────────────────────────                               │
│  ✗ Logik wird Teil von UnifiedLibraryManager.enrich_images           │
│                                                                      │
│  ImageQueueWorker → WIRD AUCH GELÖSCHT!                              │
│  ──────────────────────────────────────                              │
│  ✗ Logik wird Teil von UnifiedLibraryManager.enrich_images           │
│  (Image Download jetzt integriert für bessere Prozess-Steuerung)     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Image-Verarbeitung: Integriert in IMAGERY Phase

> **Entscheidung (Task #10):** Image-Downloads werden in Phase 5 (IMAGERY) integriert.
> Kein separater ImageDownloadWorker mehr für bessere Prozess-Steuerung.

```
┌──────────────────────────────────────────────────────────────────┐
│         PHASE 5: IMAGERY (URL Enrichment + Download)             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SCHRITT 1: URL Enrichment                                        │
│  ─────────────────────────                                        │
│                                                                   │
│    Entities ohne image_url                                        │
│         │                                                         │
│         ▼                                                         │
│    Für jeden Entity:                                              │
│    1. CoverArtArchive (wenn MBID vorhanden) → Beste Qualität      │
│    2. Fallback: Spotify API → images[0].url                       │
│    3. Fallback: Deezer API → picture_xl                           │
│         │                                                         │
│         ▼                                                         │
│    Entity.image_url = "https://..."                               │
│                                                                   │
│  SCHRITT 2: Image Download (INTEGRIERT!)                          │
│  ───────────────────────────────────────                          │
│                                                                   │
│    Entities mit image_url aber ohne image_path                    │
│         │                                                         │
│         ▼                                                         │
│    ┌─────────────────────────────────────────┐                    │
│    │ Batch Download mit Concurrency Limit    │                    │
│    │ - Max 5 parallel Downloads              │                    │
│    │ - 100ms zwischen Batches                │                    │
│    │ - Error Handling pro Image              │                    │
│    │                                         │                    │
│    │ Für jedes Image:                        │                    │
│    │ 1. Download von image_url               │                    │
│    │ 2. Speichern: /images/{type}/{id}.jpg   │                    │
│    │ 3. DB Update: image_path setzen         │                    │
│    └─────────────────────────────────────────┘                    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Warum Integration statt separater Worker?

| Aspekt | Separater Worker | Integriert (gewählt) |
|--------|------------------|---------------------|
| **Prozess-Steuerung** | ❌ Asynchron, schwer koordinierbar | ✅ Direkte Kontrolle |
| **Reihenfolge** | ❌ Kann parallel laufen | ✅ Garantiert nach IDENTIFY |
| **MBIDs verfügbar?** | ⚠️ Nicht garantiert | ✅ Ja, Phase 2 ist fertig |
| **Fehler-Handling** | ❌ Separate Logik | ✅ Teil des Task-Flows |
| **Debugging** | ❌ Zwei Logs checken | ✅ Ein Log, ein Flow |

### Image Download Sub-Task Code

```python
async def _task_enrich_images(self) -> TaskResult:
    """Phase 5: Image Enrichment + Download (integriert).
    
    Zwei Schritte in einem Task:
    1. URL Enrichment (von APIs holen)
    2. Image Download (lokal speichern)
    """
    stats = {
        "urls_found": 0, 
        "downloaded": 0, 
        "failed": 0,
        "skipped_existing": 0
    }
    
    # Konfigurierbare Concurrency (default: 5)
    max_concurrent = await self._settings.get_int(
        "library.image_download_concurrency",
        default=5  # Max 5 parallel Downloads
    )
    
    async with self._db.session_scope() as session:
        # SCHRITT 1: URL Enrichment
        entities_needing_url = await self._get_entities_without_image_url(session)
        for entity in entities_needing_url:
            url = await self._find_image_url(entity)  # CAA → Spotify → Deezer
            if url:
                entity.image_url = url
                stats["urls_found"] += 1
        
        # SCHRITT 2: Image Download (NACH URL Enrichment!)
        entities_needing_download = await self._get_entities_needing_download(session)
        
        # Semaphore = "Ampel" die max N gleichzeitig durchlässt
        # Verhindert: Server-Überlastung, Memory-Explosion, Rate Limits
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_limit(entity):
            async with semaphore:  # Warte bis Platz frei
                return await self._download_image(entity)
        
        tasks = [download_with_limit(e) for e in entities_needing_download]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for entity, result in zip(entities_needing_download, results):
            if isinstance(result, Exception):
                stats["failed"] += 1
                entity.image_state = ImageState.FAILED
            elif result:
                stats["downloaded"] += 1
                entity.image_path = result
                entity.image_state = ImageState.DOWNLOADED
        
        await session.commit()
    
    return TaskResult(success=True, stats=stats)
```

### Concurrency-Erklärung

```
Was bedeutet "Max 5 parallel Downloads"?
════════════════════════════════════════

OHNE LIMIT (❌ schlecht):
  100 Images → 100 gleichzeitige HTTP-Requests
  → Server überlastet (Rate Limit 429)
  → Netzwerk blockiert
  → 100 Bilder im RAM = Memory-Explosion
  → Timeouts, Fehlschläge

MIT SEMAPHORE(5) (✅ kontrolliert):
  100 Images → Max 5 gleichzeitige Requests
  
  Zeit 0: Start Download 1, 2, 3, 4, 5
  Zeit 1: Download 1 fertig → Start Download 6
  Zeit 2: Download 3 fertig → Start Download 7
  ...bis alle 100 fertig

SETTING:
  library.image_download_concurrency = 5  (default)
  
  Wert 1:  Sequenziell, langsam aber sicher
  Wert 3:  Konservativ, für schwache Server
  Wert 5:  Guter Kompromiss (Standard)
  Wert 10: Schneller, mehr Last
```

### Worker-Konsolidierung (aktualisiert)

| Alter Worker | Aktion | Neuer Zuständiger |
|--------------|--------|-------------------|
| `SpotifySyncWorker` | → DELETE | `UnifiedLibraryManager.sync_cloud_sources` |
| `DeezerSyncWorker` | → DELETE | `UnifiedLibraryManager.sync_cloud_sources` |
| `LibraryScanWorker` | → DELETE | `UnifiedLibraryManager.refresh_library` |
| `LibraryDiscoveryWorker` | → DELETE | `UnifiedLibraryManager.enrich_metadata` |
| `NewReleasesSyncWorker` | → DELETE | `UnifiedLibraryManager` (optional Task) |
| `ImageBackfillWorker` | → DELETE | `UnifiedLibraryManager.enrich_images` |
| `ImageQueueWorker` | → DELETE | `UnifiedLibraryManager.enrich_images` |
| `DownloadWorker` | → KEEP | Bleibt für Audio-Downloads |
| `TokenRefreshWorker` | → KEEP | Bleibt separat (Auth-spezifisch) |

**Nach Migration: Nur noch 3 Worker!**
```
workers/
├── orchestrator.py               # Registriert Worker
├── unified_library_worker.py     # ALLES Library (inkl. Images!)
├── download_worker.py            # Audio-Downloads
└── token_refresh_worker.py       # OAuth Token Refresh
```

### Datenfluss-Übersicht (korrigiert)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED LIBRARY MANAGER (Library only!)               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  IMPORT SOURCES (Cloud/Local → Database)                                 │
│  ───────────────────────────────────────                                 │
│                                                                          │
│    ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐        │
│    │  Local    │   │  Spotify  │   │  Deezer   │   │  Tidal    │        │
│    │  Scanner  │   │  Plugin   │   │  Plugin   │   │  Plugin   │        │
│    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘        │
│          │               │               │               │               │
│          └───────────────┴───────────────┴───────────────┘               │
│                                  │                                       │
│                                  ▼                                       │
│                     ┌─────────────────────────┐                          │
│                     │   Entity Deduplicator   │                          │
│                     │   (MBID/ISRC/ID/Name)   │                          │
│                     └───────────┬─────────────┘                          │
│                                 │                                        │
│                                 ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      DATABASE (Single Source of Truth)            │   │
│  │  ┌──────────────────────────────────────────────────────────────┐│   │
│  │  │ Track: id, title, isrc, spotify_uri, deezer_id,             ││   │
│  │  │        ownership_state, download_state, local_path           ││   │
│  │  └──────────────────────────────────────────────────────────────┘│   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  UnifiedLibraryManager ENDET HIER!                                       │
│  (Setzt download_state=PENDING, aber führt keine Downloads aus)          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ download_state=PENDING
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DOWNLOAD WORKER (Separater Worker!)              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Liest Tracks mit download_state=PENDING aus Database                 │
│  2. Sucht Kandidaten bei Download-Quellen                                │
│  3. Startet Downloads                                                    │
│  4. Setzt download_state=DOWNLOADED nach Erfolg                          │
│                                                                          │
│    ┌───────────┐   ┌───────────┐   ┌───────────┐                        │
│    │   slskd   │   │  SABnzbd  │   │  ...      │                        │
│    │ (Soulseek)│   │  (Usenet) │   │  (future) │                        │
│    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘                        │
│          │               │               │                               │
│          └───────────────┴───────────────┘                               │
│                          │                                               │
│                          ▼                                               │
│            /music/Artist/Album/track.flac                                │
│            (download_state=DOWNLOADED, local_path set)                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
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

---

## ⚠️ Error Handling & Retry-Logik

### Fehler-Szenarien

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ERROR HANDLING STRATEGY                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SZENARIO 1: Einzelner API-Call fehlschlägt                          │
│  ─────────────────────────────────────────────                       │
│                                                                      │
│    Spotify API: 429 Too Many Requests                                │
│         │                                                            │
│         ▼                                                            │
│    ┌─────────────────────────────────────────┐                       │
│    │ Aktion:                                 │                       │
│    │ - Exponential Backoff (1s, 2s, 4s, 8s)  │                       │
│    │ - Max 3 Retries                         │                       │
│    │ - Bei dauerhaftem Fehler: Skip Entity   │                       │
│    │ - Entity.last_error = "429: Rate Limit" │                       │
│    │ - Weiter mit nächster Entity            │                       │
│    └─────────────────────────────────────────┘                       │
│                                                                      │
│  SZENARIO 2: Provider komplett down                                  │
│  ─────────────────────────────────                                   │
│                                                                      │
│    Spotify API: Connection Refused                                   │
│         │                                                            │
│         ▼                                                            │
│    ┌─────────────────────────────────────────┐                       │
│    │ Aktion:                                 │                       │
│    │ - Circuit Breaker öffnet nach 5 Fehlern │                       │
│    │ - Provider als "unavailable" markieren  │                       │
│    │ - Andere Provider weiter nutzen         │                       │
│    │ - Nach 5 Min: Circuit Breaker reset     │                       │
│    └─────────────────────────────────────────┘                       │
│                                                                      │
│  SZENARIO 3: Phase fehlschlägt komplett                              │
│  ─────────────────────────────────────                               │
│                                                                      │
│    Phase 2 (IDENTIFY): MusicBrainz down                              │
│         │                                                            │
│         ▼                                                            │
│    ┌─────────────────────────────────────────┐                       │
│    │ Frage: Läuft Phase 3 trotzdem?          │                       │
│    │                                         │                       │
│    │ ANTWORT: NEIN, Abhängigkeiten gelten!   │                       │
│    │ - Phase 3 (ENRICH) braucht MBIDs        │                       │
│    │ - Ohne Phase 2 → Phase 3 überspringen   │                       │
│    │ - Nächster Cycle versucht erneut        │                       │
│    └─────────────────────────────────────────┘                       │
│                                                                      │
│  SZENARIO 4: DB-Fehler                                               │
│  ─────────────────────                                               │
│                                                                      │
│    SQLite: Database locked                                           │
│         │                                                            │
│         ▼                                                            │
│    ┌─────────────────────────────────────────┐                       │
│    │ Aktion:                                 │                       │
│    │ - Rollback aktuelle Transaktion         │                       │
│    │ - Retry nach 1s                         │                       │
│    │ - Max 3 Retries                         │                       │
│    │ - Bei dauerhaftem Fehler: Task abbrechen│                       │
│    │ - Health Status: DEGRADED               │                       │
│    └─────────────────────────────────────────┘                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Retry-Strategie Code

```python
@dataclass
class RetryConfig:
    """Retry-Konfiguration."""
    max_retries: int = 3
    initial_delay: float = 1.0  # Sekunden
    max_delay: float = 30.0
    exponential_base: float = 2.0


async def with_retry(
    func: Callable,
    config: RetryConfig = RetryConfig(),
) -> Any:
    """Führt Funktion mit Retry-Logik aus."""
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            
            if attempt == config.max_retries:
                raise  # Letzte Chance vorbei
            
            # Exponential Backoff
            delay = min(
                config.initial_delay * (config.exponential_base ** attempt),
                config.max_delay
            )
            
            logger.warning(f"Retry {attempt + 1}/{config.max_retries} after {delay}s: {e}")
            await asyncio.sleep(delay)
    
    raise last_exception
```

### Phase-Fehler-Handling

```python
async def run_cycle(self) -> CycleResult:
    """Führt einen Task-Cycle mit Fehler-Handling aus."""
    result = CycleResult()
    completed_this_cycle: set[str] = set()
    
    for task in self._topological_sort(self._tasks.values()):
        if not task.is_due:
            result.skipped.append((task.name, "not_due"))
            continue
        
        if not task.dependencies_satisfied(completed_this_cycle):
            result.skipped.append((task.name, "dependencies_not_met"))
            logger.info(f"Skipping {task.name}: dependencies {task.depends_on} not satisfied")
            continue
        
        try:
            task_result = await self._execute_task(task)
            
            if task_result.success:
                completed_this_cycle.add(task.name)
                result.completed.append(task.name)
            else:
                result.failed.append((task.name, task_result.error))
                # Phase fehlgeschlagen → abhängige Phasen werden übersprungen
                
        except Exception as e:
            result.failed.append((task.name, str(e)))
            logger.exception(f"Task {task.name} failed with exception")
    
    return result
```

---

## 📊 Status API

### Endpoints

```
GET /api/library/status
→ Gesamtstatus des UnifiedLibraryManager

GET /api/library/tasks
→ Liste aller Tasks mit Status

GET /api/library/tasks/{task_name}
→ Details zu einem Task

POST /api/library/tasks/{task_name}/run
→ Task manuell ausführen (wie Lidarr's "Run Now")
```

### Response-Modelle

```python
@dataclass
class TaskStatus:
    """Status eines einzelnen Tasks."""
    name: str
    enabled: bool
    interval_minutes: int
    last_run: datetime | None
    last_success: datetime | None
    last_error: str | None
    next_run: datetime | None
    is_running: bool
    stats: dict[str, Any]  # Letzte Ausführungs-Stats


@dataclass
class LibraryStatus:
    """Gesamtstatus der Library."""
    state: Literal["healthy", "degraded", "error"]
    uptime_seconds: int
    tasks: list[TaskStatus]
    providers: dict[str, ProviderStatus]
    last_cycle: CycleResult | None
    
    # Aggregierte Stats
    total_artists: int
    total_albums: int
    total_tracks: int
    owned_artists: int
    owned_albums: int
    owned_tracks: int
    pending_downloads: int


@dataclass
class ProviderStatus:
    """Status eines Providers (Spotify, Deezer, etc.)."""
    name: str
    enabled: bool
    authenticated: bool
    circuit_breaker_open: bool
    last_successful_call: datetime | None
    error_count_24h: int
```

### Status API Implementierung

```python
@router.get("/library/status")
async def get_library_status(
    library_manager: UnifiedLibraryManager = Depends(get_library_manager),
) -> LibraryStatus:
    """Gibt den aktuellen Status der Library zurück."""
    return await library_manager.get_status()


@router.post("/library/tasks/{task_name}/run")
async def run_task_now(
    task_name: str,
    library_manager: UnifiedLibraryManager = Depends(get_library_manager),
) -> TaskResult:
    """Führt einen Task sofort aus (wie Lidarr's Run Now Button)."""
    return await library_manager.run_task_now(task_name)
```

### UI Integration

```
Settings → Library → Tasks
┌────────────────────────────────────────────────────────────────┐
│  Task                  │ Last Run    │ Next Run   │ Status     │
│  ────────────────────────────────────────────────────────────  │
│  scan_local_library    │ 5 min ago   │ in 55 min  │ ✓ Success  │
│  sync_spotify_likes    │ 2 min ago   │ in 28 min  │ ✓ Success  │
│  sync_deezer_favorites │ 2 min ago   │ in 28 min  │ ⚠ Degraded │
│  identify_artists      │ 1h ago      │ in 1h      │ ✓ Success  │
│  enrich_metadata       │ 2h ago      │ in 1h      │ ✓ Success  │
│  enrich_images         │ 2h ago      │ in 0 min   │ ⏳ Running  │
│  cleanup_library       │ 23h ago     │ in 1h      │ ✓ Success  │
│                                                   │ [Run Now]  │
└────────────────────────────────────────────────────────────────┘
```

---

## 🎵 Playlist-Handling

### Playlists vs. Library

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PLAYLIST KONZEPT                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  WICHTIG: Playlists sind NICHT Teil der "Owned" Library!             │
│  ─────────────────────────────────────────────────────               │
│                                                                      │
│  Warum?                                                              │
│  - Playlist = Referenz-Liste, nicht Besitz                           │
│  - Tracks in Playlist können auch "nicht-owned" sein                 │
│  - Playlist-Sync ≠ Library-Sync                                      │
│                                                                      │
│  BEISPIEL:                                                           │
│  ┌─────────────────────────────────────────────┐                     │
│  │ Spotify Playlist "Summer Hits 2024"         │                     │
│  │                                             │                     │
│  │ Track 1: "Espresso" - Sabrina Carpenter     │ ← Owned (geliked)   │
│  │ Track 2: "Birds of a Feather" - B. Eilish   │ ← Owned (geliked)   │
│  │ Track 3: "Random Song" - Unknown            │ ← NOT owned         │
│  │ Track 4: "Another Hit" - Some Artist        │ ← NOT owned         │
│  └─────────────────────────────────────────────┘                     │
│                                                                      │
│  Die Playlist selbst ist "followed", aber nur Track 1 & 2            │
│  sind "owned" (weil separat geliked).                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Playlist-Sync Optionen

```python
class PlaylistSyncMode(str, Enum):
    """Wie werden Playlists behandelt?"""
    
    REFERENCE_ONLY = "reference_only"
    # Playlist wird gespeichert, aber Tracks nicht automatisch owned
    # Default! Playlist ist nur eine "Leseliste"
    
    AUTO_OWN_TRACKS = "auto_own_tracks"
    # Alle Tracks in Playlist werden automatisch owned
    # Vorsicht: Kann viele Tracks markieren!
    
    DISABLED = "disabled"
    # Playlists werden nicht gesynct
```

### Playlist Entity

```python
@dataclass
class Playlist:
    """Playlist (pro Provider)."""
    id: int
    name: str
    provider: str  # "spotify", "deezer", "tidal"
    provider_id: str  # z.B. "spotify:playlist:37i9..."
    
    # Ownership
    is_followed: bool  # User folgt dieser Playlist
    is_owner: bool     # User hat diese Playlist erstellt
    
    # Sync Settings
    sync_mode: PlaylistSyncMode = PlaylistSyncMode.REFERENCE_ONLY
    
    # Metadata
    cover_url: str | None = None
    cover_path: str | None = None
    track_count: int = 0
    last_synced: datetime | None = None
```

### Playlist-Sync Task

```python
ScheduledTask(
    name="sync_playlists",
    interval=timedelta(hours=1),
    handler=self._task_sync_playlists,
    depends_on=["sync_spotify_likes", "sync_deezer_favorites"],  # Nach Library-Sync!
)

async def _task_sync_playlists(self) -> TaskResult:
    """Synct Playlists von allen Providern.
    
    WICHTIG: Tracks in Playlists werden NICHT automatisch owned!
    Es sei denn sync_mode == AUTO_OWN_TRACKS.
    """
    stats = {"playlists_synced": 0, "tracks_referenced": 0}
    
    for source in self._sources.get_available_sources():
        playlists = await source.import_playlists()
        
        for playlist_dto in playlists:
            playlist = await self._upsert_playlist(playlist_dto)
            stats["playlists_synced"] += 1
            
            # Tracks holen (als Referenzen, nicht owned!)
            tracks = await source.get_playlist_tracks(playlist_dto.provider_id)
            
            for track_dto in tracks:
                # Track in DB speichern (falls nicht existiert)
                track = await self._upsert_track(track_dto)
                
                # Playlist-Track Zuordnung
                await self._link_track_to_playlist(playlist.id, track.id)
                stats["tracks_referenced"] += 1
                
                # NICHT automatisch owned! Es sei denn...
                if playlist.sync_mode == PlaylistSyncMode.AUTO_OWN_TRACKS:
                    track.ownership_state = OwnershipState.OWNED
    
    return TaskResult(success=True, stats=stats)
```

### Playlist UI-Optionen

```
Library → Playlists → "Summer Hits 2024"
┌────────────────────────────────────────────────────────────────┐
│  Summer Hits 2024                               [Sync Settings]│
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Sync Mode: ○ Reference Only (default)                         │
│             ○ Auto-Own Tracks                                   │
│             ○ Don't Sync                                        │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  Track                    │ Artist              │ Owned?        │
│  ─────────────────────────────────────────────────────────────  │
│  Espresso                 │ Sabrina Carpenter   │ ✓ Yes         │
│  Birds of a Feather       │ Billie Eilish       │ ✓ Yes         │
│  Random Song              │ Unknown Artist      │ ✗ No [Add]    │
│  Another Hit              │ Some Artist         │ ✗ No [Add]    │
│                                                                 │
│                          [Own All Tracks] [Download Owned Only] │
└────────────────────────────────────────────────────────────────┘
```

---

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
