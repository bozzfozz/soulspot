# Service Konsolidierungs-Plan (KOMPLETT + VALIDIERT)

> Erstellt: 3. Januar 2026  
> Validiert: 3. Januar 2026 (Industry Best Practices: Lidarr, beets, Jellyfin, MS DDD)  
> Ausführung: 3. Januar 2026
> Status: **✅ ABGESCHLOSSEN (Phase 2-4, 6-8) | ⏸️ Phase 5 übersprungen**  
> Basis: Lidarr/beets Architecture Research + DDD Best Practices  
> Ziel: Von 49 Services → ~35 Services mit klaren Domain-Grenzen
> Scope: **KOMPLETTER UMBAU**

---

## 📊 Ausführungs-Status (3. Januar 2026)

| Phase | Status | LOC Δ | Beschreibung |
|-------|--------|-------|--------------|
| Phase 2 | ✅ DONE | -1040 | ArtistService merged (3 Services) |
| Phase 3 | ✅ DONE | -645 | Deduplication split (Checker + Housekeeping) |
| Phase 4 | ✅ DONE | -1366 | BrowseService merged (Discover + NewReleases) |
| Phase 5 | ⏸️ SKIP | 0 | Event System (optional, später bei Bedarf) |
| Phase 6 | ✅ DONE | -861 | Library Subpackage + Scanner optimiert |
| Phase 7 | ✅ DONE | ±0 | Provider Subpackage erstellt |
| Phase 8 | ✅ DONE | ±0 | Sessions Subpackage erstellt |
| **TOTAL** | | **~-3900 LOC** | |

---

## 📋 Validierungs-Zusammenfassung

| Entscheidung | Bewertung | Aktion |
|--------------|-----------|--------|
| ✅ ArtistService (merged) | **GUT** | Behalten - Lidarr macht es genauso |
| ✅ Provider Separation | **GUT** | Behalten - Auth ≠ Sync |
| ⚠️ DeduplicationService | **GEÄNDERT** | Aufgeteilt: Checker + Housekeeping |
| ⚠️ AutomationService | **GEÄNDERT** | Watchlist + QualityUpgrade bleiben separat |
| ✅ Library Services | **GUT** | Behalten |
| ✅ BrowseService | **GUT** | Behalten |
| ⏸️ Event Bus | **ÜBERSPRUNGEN** | Optional - bei Bedarf später |

---

## 🎯 Ziel-Architektur (VALIDIERT)

Nach dem kompletten Umbau sieht die Service-Landschaft so aus:

```
src/soulspot/application/services/
├── __init__.py
│
├── # === CORE DOMAIN SERVICES (Aggregate Roots) ===
├── artist_service.py              # NEU: Unified Artist Operations
├── album_service.py               # NEU: Unified Album Operations  
├── track_service.py               # NEU: Unified Track Operations
├── playlist_service.py            # BEHALTEN
│
├── # === DEDUPLICATION (AUFGETEILT!) ===
├── deduplication_checker.py       # NEU: Import-Zeit Checks (schnell, <50ms)
├── deduplication_housekeeping.py  # NEU: Scheduled Cleanup (langsam, async)
│
├── # === CROSS-CUTTING SERVICES ===
├── enrichment_service.py          # NEU: Unified Metadata Enrichment
├── browse_service.py              # NEU: Unified Browse/Discovery
│
├── # === AUTOMATION (BEHALTEN SEPARAT!) ===
├── watchlist_service.py           # BEHALTEN: Monitoring ("Gibt es Neues?")
├── quality_upgrade_service.py     # BEHALTEN: Entscheidung ("Upgraden?")
├── automation_workflow_service.py # Orchestration ("Wenn X, dann Y")
│
├── # === EVENT SYSTEM (OPTIONAL - ÜBERSPRUNGEN) ===
├── # events/                      # NICHT IMPLEMENTIERT - bei Bedarf später
│   # ├── __init__.py
│   # ├── bus.py                   # EventBus für Decoupling
│   # ├── domain_events.py         # Event-Definitionen
│   # └── handlers/                # Event Handler
│   #     ├── release_handler.py   # Handles NewReleaseFoundEvent
│       └── download_handler.py    # Handles DownloadCompletedEvent
│
├── # === PROVIDER-SPECIFIC SERVICES ===
├── providers/
│   ├── __init__.py
│   ├── spotify_sync_service.py    # BEHALTEN (provider-spezifisch)
│   ├── deezer_sync_service.py     # BEHALTEN (provider-spezifisch)
│   ├── spotify_auth_service.py    # BEHALTEN (provider-spezifisch)
│   └── deezer_auth_service.py     # BEHALTEN (provider-spezifisch)
│
├── # === LIBRARY MANAGEMENT ===
├── library/
│   ├── __init__.py
│   ├── scanner_service.py         # MERGED: scanner + cleanup + file_discovery
│   ├── import_service.py          # NEU: Unified Import (auto_import + compilation)
│   └── view_service.py            # BEHALTEN
│
├── # === DOWNLOAD & POSTPROCESSING ===
├── download/
│   ├── __init__.py
│   ├── manager_service.py         # BEHALTEN
│   └── queue_service.py           # NEU: Queue Management
│
├── postprocessing/                # BEHALTEN (Pipeline Pattern)
│   ├── pipeline.py
│   ├── id3_tagging_service.py
│   ├── lyrics_service.py
│   ├── metadata_service.py
│   └── renaming_service.py
│
├── images/                        # BEHALTEN (Registry Pattern)
│   ├── image_service.py
│   ├── image_provider_registry.py
│   ├── queue.py
│   └── repair.py
│
├── # === INFRASTRUCTURE SERVICES ===
├── infrastructure/
│   ├── __init__.py
│   ├── settings_service.py        # RENAMED: app_settings_service
│   ├── credentials_service.py     # BEHALTEN
│   ├── notification_service.py    # BEHALTEN
│   └── session_service.py         # MERGED: token_manager + session_store
│
├── # === UTILITY SERVICES ===
├── utils/
│   ├── __init__.py
│   ├── search_service.py          # MERGED: advanced_search + filter + search_cache
│   ├── stats_service.py           # BEHALTEN
│   └── batch_processor.py         # BEHALTEN
│
└── # === DEPRECATED (zu löschen nach Migration) ===
    deprecated/
    ├── album_sync_service.py      # LEER - LÖSCHEN
    ├── library_merge_service.py   # → deduplication_housekeeping
    ├── entity_deduplicator.py     # → deduplication_checker
    ├── musicbrainz_enrichment_service.py  # → enrichment_service
    ├── artist_songs_service.py    # → artist_service
    ├── followed_artists_service.py # → artist_service
    ├── discover_service.py        # → browse_service
    ├── new_releases_service.py    # → browse_service
    ├── library_cleanup_service.py # → library/scanner_service
    ├── file_discovery_service.py  # → library/scanner_service
    ├── auto_import.py             # → library/import_service
    ├── compilation_analyzer_service.py # → library/import_service
    ├── album_completeness.py      # → album_service
    ├── auto_fetch_service.py      # → event handler (NewReleaseFoundEvent)
    ├── discography_service.py     # → artist_service
    ├── duplicate_service.py       # → deduplication_housekeeping
    ├── metadata_merger.py         # → enrichment_service
    ├── provider_mapping_service.py # → providers/__init__.py
    └── provider_sync_orchestrator.py # → providers/__init__.py
```

---

## 📚 Validierungs-Erkenntnisse (Research)

### Warum DeduplicationService aufteilen?

**Lidarr-Pattern:**
```
Housekeeping/                    # Scheduled cleanup
├── HousekeepingService.cs       # Orchestrator
└── Housekeepers/
    ├── CleanupOrphanedAlbums.cs
    └── ...

# Import-time checks sind INLINE in den jeweiligen Services
```

**Problem mit einem monolithischen Service:**

| Aspekt | Import-Zeit (Checker) | Housekeeping |
|--------|----------------------|--------------|
| Timing | Synchron | Asynchron |
| Geschwindigkeit | <50ms MUSS | Kann Minuten dauern |
| Transaction | Teil von Caller's TX | Eigene TX |
| Failure Mode | Blockiert Import | Kann retry |

### Warum Automation NICHT komplett mergen?

**Lidarr-Pattern:**
```
AutoTagging/       # Tagging automation
ImportLists/       # Import automation  
IndexerSearch/     # Search automation
Jobs/              # Scheduled jobs
```

**Nicht:** `AutomationService` mit allem drin!

| Service | Verantwortung | Trigger |
|---------|---------------|---------|
| WatchlistService | Monitoring: "Gibt es Neues?" | Scheduled |
| QualityUpgradeService | Entscheidung: "Upgraden?" | On-demand |
| AutomationWorkflow | Orchestration: "Wenn X → Y" | Events |

### ~~Warum Event Bus hinzufügen?~~ (ÜBERSPRUNGEN)

> **Status:** ⏸️ OPTIONAL - Direkte Service-Kopplung ist für aktuelle Projektgröße ausreichend.
> Bei steigender Workflow-Komplexität kann das Event System später nachgerüstet werden.

<details>
<summary>📚 Event Bus Konzept (zum Nachlesen)</summary>

**Problem (direkte Kopplung):**
```python
class WatchlistService:
    def __init__(self, download_service):  # 😬 Direkte Abhängigkeit!
        self._download = download_service
```

**Lösung (Event-basiert):**
```python
class WatchlistService:
    async def check_releases(self):
        await self._bus.publish(NewReleaseFoundEvent(release))

class AutoFetchHandler:  # Reagiert auf Event
    async def handle(self, event: NewReleaseFoundEvent):
        await self._download.queue(event.album)
```
</details>

---

## 📊 Migrations-Matrix (VALIDIERT)

### Phase 1: Quick Wins (Week 1)

| # | Aktion | Von | Nach | LOC | Aufwand | Status |
|---|--------|-----|------|-----|---------|--------|
| 1.1 | LÖSCHEN | `album_sync_service.py` | - | 0 | 5 min | ⏳ BEREIT |

> **Phase 1 Aktion:** `rm src/soulspot/application/services/album_sync_service.py`
> Datei ist leer (0 LOC), nicht exportiert in `__init__.py`, keine Usages im Codebase.

### Phase 2: Core Domain Services (Week 2-3)

| # | Aktion | Von | Nach | LOC | Aufwand |
|---|--------|-----|------|-----|---------|
| 2.1 | ERSTELLEN | - | `artist_service.py` | +800 | 8h |
| 2.2 | MERGE | `followed_artists_service.py` | `artist_service.py` | -1408 | merged |
| 2.3 | MERGE | `artist_songs_service.py` | `artist_service.py` | -566 | merged |
| 2.4 | MERGE | `discography_service.py` | `artist_service.py` | -300 | merged |
| 2.5 | ERSTELLEN | - | `album_service.py` | +400 | 4h |
| 2.6 | MERGE | `album_completeness.py` | `album_service.py` | -266 | merged |
| 2.7 | ERSTELLEN | - | `track_service.py` | +300 | 3h |

**Einsparung Phase 2:** ~2540 LOC → ~1500 LOC = **-1040 LOC**

### Phase 3: Deduplication Services (Week 4) - GEÄNDERT!

| # | Aktion | Von | Nach | LOC | Aufwand |
|---|--------|-----|------|-----|---------|
| 3.1 | ERSTELLEN | - | `deduplication_checker.py` | +250 | 3h |
| 3.2 | MIGRATE | `entity_deduplicator.py` | `deduplication_checker.py` | -494 | merged |
| 3.3 | ERSTELLEN | - | `deduplication_housekeeping.py` | +400 | 4h |
| 3.4 | MIGRATE | `library_merge_service.py` | `deduplication_housekeeping.py` | -492 | merged |
| 3.5 | MIGRATE | `duplicate_service.py` | `deduplication_housekeeping.py` | -309 | merged |

**Einsparung Phase 3:** ~1295 LOC → ~650 LOC = **-645 LOC**

### Phase 4: Enrichment + Browse (Week 5)

| # | Aktion | Von | Nach | LOC | Aufwand |
|---|--------|-----|------|-----|---------|
| 4.1 | REFACTOR | `enrichment_service.py` | `enrichment_service.py` | ±0 | 4h |
| 4.2 | MERGE | `musicbrainz_enrichment_service.py` | `enrichment_service.py` | -404 | merged |
| 4.3 | MERGE | `metadata_merger.py` | `enrichment_service.py` | -522 | merged |
| 4.4 | ERSTELLEN | - | `browse_service.py` | +400 | 4h |
| 4.5 | MERGE | `discover_service.py` | `browse_service.py` | -565 | merged |
| 4.6 | MERGE | `new_releases_service.py` | `browse_service.py` | -275 | merged |

**Einsparung Phase 4:** ~1766 LOC → ~400 LOC = **-1366 LOC**

### Phase 5: Event System (Week 6) - ⏸️ ÜBERSPRUNGEN

> **Status:** OPTIONAL - Implementierung bei Bedarf, wenn Workflows komplexer werden.
> **Begründung:** Für aktuelle Projektgröße ist direkte Service-Kopplung ausreichend.

| # | Aktion | Von | Nach | LOC | Aufwand | Status |
| 5.1 | ERSTELLEN | - | `events/bus.py` | +100 | 2h | ⏸️ SKIP |
| 5.2 | ERSTELLEN | - | `events/domain_events.py` | +80 | 1h | ⏸️ SKIP |
| 5.3 | ERSTELLEN | - | `events/handlers/release_handler.py` | +60 | 1h | ⏸️ SKIP |
| 5.4 | ERSTELLEN | - | `events/handlers/download_handler.py` | +60 | 1h | ⏸️ SKIP |
| 5.5 | REFACTOR | `auto_fetch_service.py` | Event handler | -200 | 2h | ⏸️ SKIP |
| 5.6 | REFACTOR | `watchlist_service.py` | Publish events | ±0 | 2h | ⏸️ SKIP |

**Phase 5 Status:** ⏸️ ÜBERSPRUNGEN - Event System ist optional, bei Bedarf später implementieren

### Phase 6: Library Services (Week 7)

| # | Aktion | Von | Nach | LOC | Aufwand |
|---|--------|-----|------|-----|---------|
| 6.1 | REFACTOR | `library_scanner_service.py` | `library/scanner_service.py` | ±0 | 2h |
| 6.2 | MERGE | `library_cleanup_service.py` | `library/scanner_service.py` | -191 | merged |
| 6.3 | MERGE | `file_discovery_service.py` | `library/scanner_service.py` | -200 | merged |
| 6.4 | ERSTELLEN | - | `library/import_service.py` | +500 | 6h |
| 6.5 | MERGE | `auto_import.py` | `library/import_service.py` | -800 | merged |
| 6.6 | MERGE | `compilation_analyzer_service.py` | `library/import_service.py` | -200 | merged |
| 6.7 | MOVE | `library_view_service.py` | `library/view_service.py` | ±0 | 30min |

**Einsparung Phase 6:** ~1391 LOC → ~500 LOC = **-891 LOC**

### Phase 7: Provider Services (Week 8)

| # | Aktion | Von | Nach | LOC | Aufwand |
|---|--------|-----|------|-----|---------|
| 7.1 | MOVE | `spotify_sync_service.py` | `providers/spotify_sync_service.py` | ±0 | 30min |
| 7.2 | MOVE | `deezer_sync_service.py` | `providers/deezer_sync_service.py` | ±0 | 30min |
| 7.3 | MOVE | `spotify_auth_service.py` | `providers/spotify_auth_service.py` | ±0 | 30min |
| 7.4 | MOVE | `deezer_auth_service.py` | `providers/deezer_auth_service.py` | ±0 | 30min |
| 7.5 | MERGE | `provider_mapping_service.py` | `providers/__init__.py` | -491 | 2h |
| 7.6 | MERGE | `provider_sync_orchestrator.py` | `providers/__init__.py` | -505 | 2h |

**Einsparung Phase 7:** ~996 LOC → ~0 LOC (in __init__) = **-996 LOC**

### Phase 8: Infrastructure & Utils (Week 9)

| # | Aktion | Von | Nach | LOC | Aufwand |
|---|--------|-----|------|-----|---------|
| 8.1 | RENAME | `app_settings_service.py` | `infrastructure/settings_service.py` | ±0 | 30min |
| 8.2 | MOVE | `credentials_service.py` | `infrastructure/credentials_service.py` | ±0 | 30min |
| 8.3 | MOVE | `notification_service.py` | `infrastructure/notification_service.py` | ±0 | 30min |
| 8.4 | ERSTELLEN | - | `infrastructure/session_service.py` | +400 | 4h |
| 8.5 | MERGE | `token_manager.py` | `infrastructure/session_service.py` | -709 | merged |
| 8.6 | MERGE | `session_store.py` | `infrastructure/session_service.py` | -605 | merged |
| 8.7 | ERSTELLEN | - | `utils/search_service.py` | +300 | 3h |
| 8.8 | MERGE | `advanced_search.py` | `utils/search_service.py` | -350 | merged |
| 8.9 | MERGE | `filter_service.py` | `utils/search_service.py` | -200 | merged |
| 8.10 | MERGE | `search_cache.py` | `utils/search_service.py` | -200 | merged |
| 8.11 | MOVE | `stats_service.py` | `utils/stats_service.py` | ±0 | 30min |
| 8.12 | MOVE | `batch_processor.py` | `utils/batch_processor.py` | ±0 | 30min |

**Einsparung Phase 8:** ~2064 LOC → ~700 LOC = **-1364 LOC**

---

## 📈 Gesamt-Statistik (VALIDIERT)

| Phase | Services vorher | Services nachher | LOC Δ |
|-------|----------------|------------------|-------|
| Phase 1 | 1 | 0 | 0 |
| Phase 2 | 5 | 3 | -1040 |
| Phase 3 | 3 | 2 | -645 |
| Phase 4 | 4 | 2 | -1366 |
| Phase 5 | ⏸️ SKIP | ⏸️ SKIP | 0 (übersprungen) |
| Phase 6 | 5 | 3 | -891 |
| Phase 7 | 6 | 4 | -996 |
| Phase 8 | 8 | 6 | -1364 |
| **TOTAL** | **34 merged** | **24 new** | **-6202** |

**Finale Zahlen:**
- **Vorher:** 49 Service-Dateien, ~18.000 LOC
- **Nachher:** ~35 Service-Dateien, ~11.800 LOC
- **Einsparung:** **-14 Dateien (-29%), -6.200 LOC (-34%)**

---

## 🏗️ Detaillierte Service-Spezifikationen

### 2.1 ArtistService (Unified Artist Operations)

```python
# src/soulspot/application/services/artist_service.py

"""Unified Artist Domain Service.

Hey future me - dies ist DER Service für alle Artist-Operationen!

Merged aus:
- followed_artists_service.py (Spotify/Deezer Sync)
- artist_songs_service.py (Top Tracks)
- discography_service.py (Discography Completeness)

Pattern: Aggregate Root Service (DDD)
Lidarr-Vorbild: ArtistService + RefreshArtistService kombiniert
"""

from typing import TYPE_CHECKING
from soulspot.domain.entities import Artist, Album, Track
from soulspot.domain.ports import IArtistRepository, IAlbumRepository

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins import SpotifyPlugin, DeezerPlugin

class ArtistService:
    """Unified service for all Artist operations.
    
    Responsibilities:
    - CRUD operations for Artists
    - Sync followed artists from providers
    - Top tracks retrieval
    - Discography analysis & completeness
    """
    
    def __init__(
        self,
        session: AsyncSession,
        artist_repo: IArtistRepository,
        album_repo: IAlbumRepository,
        track_repo: ITrackRepository,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
        dedup_service: "DeduplicationService | None" = None,
    ):
        self._session = session
        self._artist_repo = artist_repo
        self._album_repo = album_repo
        self._track_repo = track_repo
        self._spotify = spotify_plugin
        self._deezer = deezer_plugin
        self._dedup = dedup_service

    # === CRUD ===
    
    async def get_by_id(self, artist_id: int) -> Artist | None:
        return await self._artist_repo.get_by_id(artist_id)
    
    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Artist]:
        return await self._artist_repo.get_all(limit=limit, offset=offset)
    
    async def create(self, artist_dto: ArtistDTO) -> Artist:
        # Dedup check
        if self._dedup:
            existing = await self._dedup.find_existing_artist(artist_dto)
            if existing:
                return existing
        
        artist = Artist.from_dto(artist_dto)
        return await self._artist_repo.add(artist)
    
    async def update(self, artist_id: int, updates: dict) -> Artist:
        artist = await self._artist_repo.get_by_id(artist_id)
        for key, value in updates.items():
            setattr(artist, key, value)
        return await self._artist_repo.update(artist)
    
    async def delete(self, artist_id: int) -> bool:
        return await self._artist_repo.delete(artist_id)

    # === SYNC (von followed_artists_service) ===
    
    async def sync_followed_artists(
        self,
        providers: list[str] | None = None,  # ["spotify", "deezer"]
    ) -> SyncResult:
        """Sync followed artists from all enabled providers."""
        all_artists = []
        
        if (providers is None or "spotify" in providers) and self._spotify:
            if self._spotify.is_authenticated:
                spotify_artists = await self._spotify.get_followed_artists()
                all_artists.extend(spotify_artists)
        
        if (providers is None or "deezer" in providers) and self._deezer:
            deezer_artists = await self._deezer.get_favorite_artists()
            all_artists.extend(deezer_artists)
        
        # Deduplicate across providers
        unique_artists = await self._deduplicate_artists(all_artists)
        
        # Save to DB
        synced = 0
        for artist_dto in unique_artists:
            await self.create(artist_dto)
            synced += 1
        
        return SyncResult(synced=synced, total=len(all_artists))

    # === TOP TRACKS (von artist_songs_service) ===
    
    async def get_top_tracks(
        self,
        artist_id: int,
        limit: int = 10,
    ) -> list[Track]:
        """Get top tracks for an artist from all providers."""
        artist = await self._artist_repo.get_by_id(artist_id)
        if not artist:
            return []
        
        tracks = []
        
        # Spotify
        if self._spotify and self._spotify.is_authenticated and artist.spotify_id:
            spotify_tracks = await self._spotify.get_artist_top_tracks(
                artist.spotify_id, limit=limit
            )
            tracks.extend(spotify_tracks)
        
        # Deezer
        if self._deezer and artist.deezer_id:
            deezer_tracks = await self._deezer.get_artist_top_tracks(
                artist.deezer_id, limit=limit
            )
            tracks.extend(deezer_tracks)
        
        # Deduplicate by ISRC
        return self._deduplicate_tracks(tracks)[:limit]
    
    async def sync_top_tracks(self, artist_id: int, limit: int = 10) -> SyncResult:
        """Sync top tracks to database."""
        tracks = await self.get_top_tracks(artist_id, limit)
        
        synced = 0
        for track_dto in tracks:
            if self._dedup:
                existing = await self._dedup.find_existing_track(track_dto)
                if existing:
                    continue
            
            track = Track.from_dto(track_dto)
            await self._track_repo.add(track)
            synced += 1
        
        return SyncResult(synced=synced, total=len(tracks))

    # === DISCOGRAPHY (von discography_service) ===
    
    async def get_discography(
        self,
        artist_id: int,
        include_types: list[str] | None = None,  # ["album", "single", "compilation"]
    ) -> list[Album]:
        """Get complete discography from providers."""
        artist = await self._artist_repo.get_by_id(artist_id)
        if not artist:
            return []
        
        albums = []
        
        # Spotify
        if self._spotify and self._spotify.is_authenticated and artist.spotify_id:
            spotify_albums = await self._spotify.get_artist_albums(
                artist.spotify_id, include_groups=include_types
            )
            albums.extend(spotify_albums)
        
        # Deezer
        if self._deezer and artist.deezer_id:
            deezer_albums = await self._deezer.get_artist_albums(artist.deezer_id)
            albums.extend(deezer_albums)
        
        return self._deduplicate_albums(albums)
    
    async def check_discography_completeness(
        self,
        artist_id: int,
    ) -> DiscographyReport:
        """Check how complete our local discography is."""
        # Get provider discography
        provider_albums = await self.get_discography(artist_id)
        
        # Get local albums
        local_albums = await self._album_repo.get_by_artist(artist_id)
        
        # Find missing
        local_ids = {a.spotify_uri or a.deezer_id for a in local_albums}
        missing = [a for a in provider_albums if a.id not in local_ids]
        
        return DiscographyReport(
            total_provider=len(provider_albums),
            total_local=len(local_albums),
            missing=missing,
            completeness_pct=len(local_albums) / len(provider_albums) * 100 if provider_albums else 100,
        )
    
    # === PRIVATE HELPERS ===
    
    async def _deduplicate_artists(self, artists: list[ArtistDTO]) -> list[ArtistDTO]:
        """Deduplicate artists by MBID > Spotify URI > Deezer ID > Name."""
        seen = {}
        unique = []
        
        for artist in artists:
            # Key hierarchy
            key = (
                artist.musicbrainz_id or
                artist.spotify_uri or
                artist.deezer_id or
                self._normalize_name(artist.name)
            )
            
            if key not in seen:
                seen[key] = artist
                unique.append(artist)
            else:
                # Merge metadata
                existing = seen[key]
                existing.merge_from(artist)
        
        return unique
    
    def _deduplicate_tracks(self, tracks: list[TrackDTO]) -> list[TrackDTO]:
        """Deduplicate tracks by ISRC."""
        seen_isrc = set()
        unique = []
        
        for track in tracks:
            if track.isrc and track.isrc in seen_isrc:
                continue
            if track.isrc:
                seen_isrc.add(track.isrc)
            unique.append(track)
        
        return unique
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        return name.lower().strip()
```

### 3.1 DeduplicationService (Unified Dedup)

```python
# src/soulspot/application/services/deduplication_service.py

"""Unified Deduplication Service.

Hey future me - EINE Quelle für alle Deduplizierungs-Logik!

Merged aus:
- library_merge_service.py (UI-triggered merge)
- entity_deduplicator.py (Import-time check)
- duplicate_service.py (Track duplicates)

Zwei Modi:
1. PREVENT (Import-Zeit): Prüft VOR dem Insert
2. FIX (Housekeeping): Findet und merged existierende

Lidarr-Pattern: HousekeepingTask + Import-Check
beets-Pattern: find_duplicates() + duplicate_action config
"""

class DeduplicationStrategy(str, Enum):
    SKIP_NEW = "skip"       # Skip new, keep old
    KEEP_BOTH = "keep"      # Keep both
    REPLACE_OLD = "replace" # Replace old with new
    MERGE = "merge"         # Merge metadata
    ASK = "ask"             # Prompt user

class DeduplicationService:
    """Unified deduplication for all entity types."""
    
    def __init__(
        self,
        session: AsyncSession,
        artist_repo: IArtistRepository,
        album_repo: IAlbumRepository,
        track_repo: ITrackRepository,
    ):
        self._session = session
        self._artist_repo = artist_repo
        self._album_repo = album_repo
        self._track_repo = track_repo
        self._normalizer = NameNormalizer()
        self._scorer = SimilarityScorer()

    # === PREVENT MODE (Import-Zeit) ===
    
    async def find_existing_artist(
        self,
        artist_dto: ArtistDTO,
        threshold: float = 0.85,
    ) -> Artist | None:
        """Find existing artist matching DTO.
        
        Check order (Lidarr-style):
        1. MusicBrainz ID (exact)
        2. Spotify/Deezer URI (exact)
        3. Name + Similarity Score
        """
        # 1. MBID
        if artist_dto.musicbrainz_id:
            existing = await self._artist_repo.get_by_mbid(artist_dto.musicbrainz_id)
            if existing:
                return existing
        
        # 2. Provider URIs
        if artist_dto.spotify_uri:
            existing = await self._artist_repo.get_by_spotify_uri(artist_dto.spotify_uri)
            if existing:
                return existing
        
        if artist_dto.deezer_id:
            existing = await self._artist_repo.get_by_deezer_id(str(artist_dto.deezer_id))
            if existing:
                return existing
        
        # 3. Fuzzy name match
        normalized = self._normalizer.normalize(artist_dto.name)
        candidates = await self._artist_repo.search_by_normalized_name(normalized)
        
        for candidate in candidates:
            score = self._scorer.calculate(artist_dto.name, candidate.name)
            if score >= threshold:
                return candidate
        
        return None

    async def find_existing_album(
        self,
        album_dto: AlbumDTO,
        artist_id: int,
        threshold: float = 0.85,
    ) -> Album | None:
        """Find existing album matching DTO."""
        # Similar logic...
        pass

    async def find_existing_track(
        self,
        track_dto: TrackDTO,
        album_id: int | None = None,
        threshold: float = 0.90,
    ) -> Track | None:
        """Find existing track matching DTO.
        
        Check order:
        1. ISRC (exact)
        2. Spotify/Deezer URI (exact)
        3. Title + Duration + Album
        """
        # 1. ISRC (most reliable)
        if track_dto.isrc:
            existing = await self._track_repo.get_by_isrc(track_dto.isrc)
            if existing:
                return existing
        
        # 2. Provider URIs
        if track_dto.spotify_uri:
            existing = await self._track_repo.get_by_spotify_uri(track_dto.spotify_uri)
            if existing:
                return existing
        
        # 3. Fuzzy match
        candidates = await self._track_repo.search_by_title(
            track_dto.title, album_id=album_id
        )
        
        for candidate in candidates:
            if self._is_same_track(track_dto, candidate, threshold):
                return candidate
        
        return None

    # === FIX MODE (Housekeeping) ===
    
    async def find_duplicate_artists(
        self,
        min_similarity: float = 0.90,
        limit: int = 100,
    ) -> list[DuplicateCandidate]:
        """Find potential duplicate artists in DB.
        
        Uses SQL-based detection (Lidarr pattern).
        """
        # SQL for finding potential duplicates
        query = text("""
            SELECT a1.id as id1, a2.id as id2, a1.name as name1, a2.name as name2
            FROM artists a1
            JOIN artists a2 ON a1.id < a2.id
            WHERE LOWER(REPLACE(a1.name, ' ', '')) = LOWER(REPLACE(a2.name, ' ', ''))
            LIMIT :limit
        """)
        
        result = await self._session.execute(query, {"limit": limit})
        
        candidates = []
        for row in result:
            score = self._scorer.calculate(row.name1, row.name2)
            if score >= min_similarity:
                candidates.append(DuplicateCandidate(
                    entity_type="artist",
                    entity1_id=row.id1,
                    entity2_id=row.id2,
                    similarity=score,
                ))
        
        return candidates

    async def merge_artists(
        self,
        keep_id: int,
        remove_id: int,
        strategy: DeduplicationStrategy = DeduplicationStrategy.MERGE,
    ) -> MergeResult:
        """Merge two artists.
        
        1. Transfer all albums/tracks from remove → keep
        2. Merge metadata (best of both)
        3. Update foreign keys
        4. Delete remove
        """
        keep_artist = await self._artist_repo.get_by_id(keep_id)
        remove_artist = await self._artist_repo.get_by_id(remove_id)
        
        if not keep_artist or not remove_artist:
            raise ValueError("Artist not found")
        
        changes = []
        
        # 1. Transfer albums
        albums = await self._album_repo.get_by_artist(remove_id)
        for album in albums:
            album.artist_id = keep_id
            await self._album_repo.update(album)
            changes.append(f"Moved album {album.title}")
        
        # 2. Merge metadata
        if strategy == DeduplicationStrategy.MERGE:
            # Keep best metadata from both
            if remove_artist.musicbrainz_id and not keep_artist.musicbrainz_id:
                keep_artist.musicbrainz_id = remove_artist.musicbrainz_id
                changes.append("Merged MBID")
            
            if remove_artist.image_url and not keep_artist.image_url:
                keep_artist.image_url = remove_artist.image_url
                changes.append("Merged image")
            
            # etc.
        
        # 3. Delete remove
        await self._artist_repo.delete(remove_id)
        changes.append(f"Deleted artist {remove_artist.name}")
        
        await self._session.commit()
        
        return MergeResult(
            kept_entity=keep_artist,
            removed_entity_id=remove_id,
            changes=changes,
        )

    # === HOUSEKEEPING TASK (für Worker) ===
    
    async def run_housekeeping(
        self,
        entity_types: list[str] = ["artist", "album", "track"],
        dry_run: bool = True,
        auto_merge_threshold: float = 0.95,
    ) -> HousekeepingResult:
        """Periodic cleanup task (called by worker).
        
        dry_run=True shows what would happen.
        auto_merge_threshold: auto-merge if similarity >= this.
        """
        results = HousekeepingResult()
        
        if "artist" in entity_types:
            duplicates = await self.find_duplicate_artists()
            for dup in duplicates:
                if dry_run:
                    results.would_merge.append(dup)
                elif dup.similarity >= auto_merge_threshold:
                    await self.merge_artists(dup.entity1_id, dup.entity2_id)
                    results.merged.append(dup)
                else:
                    results.needs_review.append(dup)
        
        # Similar for albums and tracks...
        
        return results


class NameNormalizer:
    """Unified name normalization (SINGLE SOURCE OF TRUTH)."""
    
    def normalize(self, name: str) -> str:
        if not name:
            return ""
        
        normalized = name.lower()
        # Remove "the", "a", "an" prefix
        normalized = re.sub(r"^(the|a|an)\s+", "", normalized)
        # Remove special chars
        normalized = re.sub(r"[^\w\s]", "", normalized)
        # Collapse whitespace
        normalized = " ".join(normalized.split())
        
        return normalized


class SimilarityScorer:
    """Unified similarity scoring (SINGLE SOURCE OF TRUTH)."""
    
    def calculate(self, name1: str, name2: str) -> float:
        from difflib import SequenceMatcher
        
        normalizer = NameNormalizer()
        n1 = normalizer.normalize(name1)
        n2 = normalizer.normalize(name2)
        
        return SequenceMatcher(None, n1, n2).ratio()
```

### 3.8 BrowseService (Unified Browse/Discovery)

```python
# src/soulspot/application/services/browse_service.py

"""Unified Browse & Discovery Service.

Hey future me - EINE Quelle für alle Browse-Operationen!

Merged aus:
- discover_service.py (Multi-provider artist discovery)
- new_releases_service.py (Multi-provider new releases)

Pattern: Multi-provider aggregation + deduplication
"""

class BrowseService:
    """Unified service for browsing and discovery."""
    
    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: SpotifyPlugin | None = None,
        deezer_plugin: DeezerPlugin | None = None,
        dedup_service: DeduplicationService | None = None,
    ):
        self._session = session
        self._spotify = spotify_plugin
        self._deezer = deezer_plugin
        self._dedup = dedup_service

    # === NEW RELEASES ===
    
    async def get_new_releases(
        self,
        limit: int = 20,
        providers: list[str] | None = None,
    ) -> list[AlbumDTO]:
        """Get new releases from all enabled providers."""
        all_releases = []
        
        # Spotify
        if self._should_use_provider("spotify", providers):
            if self._spotify and self._spotify.is_authenticated:
                releases = await self._spotify.get_new_releases(limit=limit)
                for r in releases:
                    r.source = "spotify"
                all_releases.extend(releases)
        
        # Deezer (no auth needed)
        if self._should_use_provider("deezer", providers):
            if self._deezer:
                releases = await self._deezer.get_chart_albums(limit=limit)
                for r in releases:
                    r.source = "deezer"
                all_releases.extend(releases)
        
        # Deduplicate
        return self._deduplicate_albums(all_releases)[:limit]

    # === DISCOVER ===
    
    async def discover_artists(
        self,
        seed_artist_id: int | None = None,
        seed_genre: str | None = None,
        limit: int = 20,
        providers: list[str] | None = None,
    ) -> list[ArtistDTO]:
        """Discover new artists based on seeds."""
        all_artists = []
        
        # Spotify recommendations
        if self._should_use_provider("spotify", providers):
            if self._spotify and self._spotify.is_authenticated:
                artists = await self._spotify.get_recommendations(
                    seed_artist_id=seed_artist_id,
                    seed_genre=seed_genre,
                    limit=limit,
                )
                for a in artists:
                    a.source = "spotify"
                all_artists.extend(artists)
        
        # Deezer similar artists
        if self._should_use_provider("deezer", providers):
            if self._deezer and seed_artist_id:
                artists = await self._deezer.get_related_artists(
                    artist_id=seed_artist_id, limit=limit
                )
                for a in artists:
                    a.source = "deezer"
                all_artists.extend(artists)
        
        return self._deduplicate_artists(all_artists)[:limit]

    async def get_genre_releases(
        self,
        genre: str,
        limit: int = 20,
    ) -> list[AlbumDTO]:
        """Get releases for a specific genre."""
        # Deezer has better genre support
        if self._deezer:
            return await self._deezer.get_genre_albums(genre, limit=limit)
        return []

    async def get_charts(
        self,
        chart_type: str = "top_artists",
        limit: int = 50,
    ) -> list[ArtistDTO | AlbumDTO | TrackDTO]:
        """Get charts from providers."""
        if self._deezer:
            if chart_type == "top_artists":
                return await self._deezer.get_chart_artists(limit=limit)
            elif chart_type == "top_albums":
                return await self._deezer.get_chart_albums(limit=limit)
            elif chart_type == "top_tracks":
                return await self._deezer.get_chart_tracks(limit=limit)
        return []

    # === PRIVATE HELPERS ===
    
    def _should_use_provider(
        self, 
        provider: str, 
        allowed: list[str] | None
    ) -> bool:
        return allowed is None or provider in allowed
    
    def _deduplicate_albums(self, albums: list[AlbumDTO]) -> list[AlbumDTO]:
        seen = set()
        unique = []
        
        for album in albums:
            # Key: artist_name + album_title (normalized)
            key = f"{album.artist_name.lower()}:{album.title.lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(album)
        
        return unique
```

---

## 📅 Implementierungs-Timeline (8 Wochen)

```
Week 1: Phase 1 - Quick Wins
├── Day 1: Löschen album_sync_service.py
└── Day 2-5: Dokumentation vorbereiten

Week 2-3: Phase 2 - Core Domain Services
├── Week 2: ArtistService erstellen + merge
└── Week 3: AlbumService + TrackService erstellen

Week 4-5: Phase 3 - Cross-Cutting Services
├── Week 4: DeduplicationService + EnrichmentService
└── Week 5: BrowseService + AutomationService

Week 6: Phase 4 - Library Services
├── Day 1-3: library/scanner_service merge
└── Day 4-5: library/import_service erstellen

Week 7: Phase 5 - Provider Services
├── Day 1-2: Move provider services
└── Day 3-5: Merge orchestrator logic

Week 8: Phase 6 - Infrastructure & Utils
├── Day 1-3: Infrastructure services
└── Day 4-5: Utils services + Final cleanup
```

---

## ✅ Akzeptanzkriterien (Gesamtprojekt)

### Code Quality
- [ ] Alle Services haben Type Hints
- [ ] Alle Services haben Docstrings
- [ ] Keine zirkulären Dependencies
- [ ] Single Responsibility eingehalten

### Funktionalität
- [ ] Alle bestehenden Tests bestehen
- [ ] Alle API Endpoints funktionieren
- [ ] Worker integrieren neue Services
- [ ] UI funktioniert unverändert

### Performance
- [ ] Keine Regression in Response Times
- [ ] Keine neuen N+1 Queries
- [ ] DB-Transaktionen korrekt

### Dokumentation
- [ ] Alle neuen Services dokumentiert
- [ ] Migration Guide vorhanden
- [ ] API Docs aktualisiert

---

## 🚨 Risiken & Mitigationen

| Risiko | Schwere | Wahrscheinlichkeit | Mitigation |
|--------|---------|-------------------|------------|
| Breaking Changes | Hoch | Mittel | API-Wrapper für Übergang |
| Performance-Regression | Mittel | Niedrig | Benchmarks vor/nach |
| Circular Dependencies | Mittel | Niedrig | Interface-basierte Injection |
| Verlust von Edge-Cases | Hoch | Mittel | Alle Tests migrieren |
| Lange Merge-Konflikte | Mittel | Hoch | Feature Branches, kleine PRs |

---

## 📊 Erwartetes Endergebnis

| Metrik | Vorher | Nachher | Änderung |
|--------|--------|---------|----------|
| Service-Dateien | 49 | ~31 | -37% |
| LOC in Services | ~18.000 | ~10.800 | -40% |
| Doppelte Logik | Viel | Minimal | -80% |
| Test Coverage | ? | Gleich+ | ≥0% |
| Import Statements | Viele | Weniger | -30% |

---

**Plan Status:** ✅ FERTIG - Kompletter Umbau-Plan

**Nächster Schritt:** Phase 1 starten (album_sync_service.py löschen)
