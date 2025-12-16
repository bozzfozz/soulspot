# Service Separation Plan

**Erstellt:** 2025-01-XX
**Status:** PLAN (nicht implementiert)
**Priorität:** HIGH - Architektur-Konformität

---

## 1. PROBLEM-ANALYSE

### 1.1 Aktueller Zustand

```
SpotifySyncService (1839 Zeilen!)
├── Sync Followed Artists (Spotify-spezifisch, braucht OAuth)
├── Sync User Playlists (Spotify-spezifisch, braucht OAuth)
├── Sync Liked Songs (Spotify-spezifisch, braucht OAuth)
├── Sync Saved Albums (Spotify-spezifisch, braucht OAuth)
├── Sync Artist Albums (Multi-Provider, Spotify + Deezer Fallback)
├── Sync Album Tracks (Multi-Provider)
├── Get Artist/Album/Track (generisch - DB Queries)
├── get_album_detail_view (generisch - ViewModel)
└── Utility Methods (Duration calc, etc.)
```

### 1.2 Probleme

| Problem | Regel-Verstoß |
|---------|---------------|
| **God Class** | Single Responsibility Principle verletzt - 1839 Zeilen |
| **Mixed Concerns** | Spotify-spezifisch + generisch + ViewModels vermischt |
| **Fehlende DeezerSyncService** | Kein separater Service für Deezer-Sync |
| **ViewModels im SyncService** | ViewModels gehören in separaten ViewService |
| **DB-Queries im SyncService** | Repositories sollten DB-Queries machen |

---

## 2. ZIEL-ARCHITEKTUR

### 2.1 Service-Struktur (Clean Architecture)

```
src/soulspot/application/services/
│
├── SYNC SERVICES (Provider-spezifisch)
│   ├── spotify_sync_service.py      # NUR Spotify OAuth-basierter Sync
│   │   ├── sync_followed_artists()  # Braucht Spotify OAuth
│   │   ├── sync_user_playlists()    # Braucht Spotify OAuth
│   │   ├── sync_liked_songs()       # Braucht Spotify OAuth
│   │   └── sync_saved_albums()      # Braucht Spotify OAuth
│   │
│   ├── deezer_sync_service.py       # NUR Deezer-spezifischer Sync (NEU!)
│   │   ├── sync_charts()            # Deezer Charts (kein Auth nötig)
│   │   ├── sync_new_releases()      # Deezer New Releases
│   │   └── sync_artist_albums()     # Deezer Artist Albums (Fallback)
│   │
│   └── tidal_sync_service.py        # ZUKUNFT: Tidal Sync (wenn wir Tidal haben)
│
├── ORCHESTRATION SERVICES (Multi-Provider)
│   ├── provider_sync_orchestrator.py  # Koordiniert mehrere Provider (NEU!)
│   │   ├── sync_artist_albums()     # Versucht Spotify → Deezer Fallback
│   │   ├── sync_album_tracks()      # Versucht Spotify → Deezer Fallback
│   │   └── get_aggregated_new_releases()
│   │
│   └── followed_artists_service.py  # Bereits vorhanden! Multi-Provider Aggregation
│       ├── get_followed_artists()   # Spotify + Deezer + ...
│       └── sync_to_library()        # Unified Library
│
├── VIEW SERVICES (Template-ready ViewModels)
│   └── library_view_service.py      # ViewModels für UI (NEU!)
│       ├── get_album_detail_view()  # AlbumDetailView für Template
│       ├── get_artist_detail_view() # ArtistDetailView für Template
│       └── get_track_list_view()    # TrackListView für Template
│
└── BESTEHENDE SERVICES (unverändert)
    ├── new_releases_service.py      # Aggregiert New Releases
    ├── charts_service.py            # Aggregiert Charts
    ├── discover_service.py          # Discovery Recommendations
    └── ... (andere Services)
```

### 2.2 Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                          API Routes                                  │
│  /spotify/artists/{id}/albums/{album_id}                            │
│  /library/artists                                                   │
│  /discover/new-releases                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
┌──────────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
│ LibraryViewService   │ │ProviderSyncOrch.│ │ NewReleasesService   │
│ (ViewModels)         │ │ (Orchestration) │ │ (Aggregation)        │
└──────────────────────┘ └─────────────────┘ └──────────────────────┘
          │                       │                      │
          │           ┌───────────┼───────────┐          │
          │           ▼           ▼           ▼          │
          │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
          │  │SpotifySync  │ │DeezerSync   │ │TidalSync    │
          │  │Service      │ │Service      │ │Service      │
          │  └─────────────┘ └─────────────┘ └─────────────┘
          │           │           │           │
          │           ▼           ▼           ▼
          │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
          │  │SpotifyPlugin│ │DeezerPlugin │ │TidalPlugin  │
          │  └─────────────┘ └─────────────┘ └─────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      REPOSITORIES                                    │
│  ArtistRepository, AlbumRepository, TrackRepository                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. MIGRATIONS-SCHRITTE

### Phase 1: ViewModels extrahieren (LOW RISK) ✅ DONE
**Status:** COMPLETED (Session 2025-01-XX)

**Ziel:** ViewModels aus SpotifySyncService in eigenen Service verschieben

**Erledigte Schritte:**
1. ✅ **Erstellt** `library_view_service.py` mit `get_album_detail_view()`
2. ✅ **Exportiert** in `services/__init__.py` 
3. ✅ **Dependency** `get_library_view_service()` in `dependencies.py`
4. ✅ **Route** `/spotify/artists/{artist_id}/albums/{album_id}` nutzt jetzt `LibraryViewService`
5. ✅ **Graceful Degradation** - zeigt cached Daten wenn kein Spotify Auth

**Dateien geändert:**
- CREATE: `src/soulspot/application/services/library_view_service.py`
- MODIFY: `src/soulspot/application/services/__init__.py` (Export hinzugefügt)
- MODIFY: `src/soulspot/api/dependencies.py` (DI für LibraryViewService)
- MODIFY: `src/soulspot/api/routers/ui.py` (Route Dependency geändert)

**Backward-Compatibility:**
- `SpotifySyncService.get_album_detail_view()` bleibt vorerst (für andere Routes)
- Wird in Phase 4 entfernt

### Phase 2: DeezerSyncService erstellen (MEDIUM RISK)
**Status:** TODO

**Ziel:** Deezer-spezifische Sync-Logik in eigenen Service

1. **Erstelle** `deezer_sync_service.py`
2. **Extrahiere** Deezer-Logik aus `followed_artists_service.py` (falls vorhanden)
3. **Implementiere** `sync_artist_albums()`, `sync_charts()`
4. **Nutze** DeezerPlugin für API-Calls

**Dateien:**
- CREATE: `src/soulspot/application/services/deezer_sync_service.py`
- MODIFY: `src/soulspot/api/dependencies.py` (DI für DeezerSyncService)

### Phase 2: DeezerSyncService erstellen (MEDIUM RISK) ✅ DONE
**Status:** COMPLETED (Session 2025-01-XX)

**Ziel:** Deezer-spezifische Sync-Logik in eigenen Service

**Erledigte Schritte:**
1. ✅ **Erstellt** `deezer_sync_service.py` mit ALLEN Methoden:
   - `sync_charts()` - Charts zu DB (NO AUTH!)
   - `sync_new_releases()` - Editorial + Chart Albums (NO AUTH!)
   - `sync_artist_albums()` - Artist Discographie (NO AUTH!)
   - `sync_artist_top_tracks()` - Top Tracks (NO AUTH!)
   - `sync_album_tracks()` - Album Tracks (NO AUTH!)
   - `sync_followed_artists()` - Gefolgte Artists (OAuth!)
   - `sync_user_playlists()` - User Playlists (OAuth!)
   - `sync_saved_albums()` - Gespeicherte Alben (OAuth!)
   - `sync_saved_tracks()` - Favoriten (OAuth!) - Equivalent zu Spotify's sync_liked_songs
2. ✅ **Cooldown-System** implementiert (verhindert API-Spam)
3. ✅ **Exportiert** in `services/__init__.py`
4. ✅ **Dependency** `get_deezer_sync_service()` in `dependencies.py`
5. ✅ **SpotifySyncService erweitert** um `sync_new_releases()` für Konsistenz

**Dateien geändert:**
- CREATE: `src/soulspot/application/services/deezer_sync_service.py`
- MODIFY: `src/soulspot/application/services/__init__.py` (Export hinzugefügt)
- MODIFY: `src/soulspot/api/dependencies.py` (DI für DeezerSyncService)
- MODIFY: `src/soulspot/application/services/spotify_sync_service.py` (sync_new_releases hinzugefügt)

**Service-Konsistenz erreicht:**

| Methode | SpotifySync | DeezerSync |
|---------|-------------|------------|
| `sync_followed_artists()` | ✅ OAuth | ✅ OAuth |
| `sync_user_playlists()` | ✅ OAuth | ✅ OAuth |
| `sync_saved_albums()` | ✅ OAuth | ✅ OAuth |
| `sync_new_releases()` | ✅ OAuth | ✅ NO AUTH! |
| `sync_artist_albums()` | ✅ OAuth | ✅ NO AUTH! |
| `sync_album_tracks()` | ✅ OAuth | ✅ NO AUTH! |
| `sync_liked_songs`/`sync_saved_tracks` | ✅ OAuth | ✅ OAuth |
| `sync_charts()` | ❌ keine API | ✅ NO AUTH! |

### Phase 3: ProviderSyncOrchestrator erstellen (MEDIUM RISK)
**Status:** TODO

**Ziel:** Multi-Provider Fallback-Logik zentralisieren

1. **Erstelle** `provider_sync_orchestrator.py`
2. **Verschiebe** Multi-Provider Logik aus SpotifySyncService
3. **Implementiere** `sync_artist_albums()` mit Spotify → Deezer Fallback
4. **Update** alle Routes die Multi-Provider Sync brauchen

**Dateien:**
- CREATE: `src/soulspot/application/services/provider_sync_orchestrator.py`
- MODIFY: `src/soulspot/application/services/spotify_sync_service.py` (entfernen)
- MODIFY: `src/soulspot/api/dependencies.py`

### Phase 4: SpotifySyncService aufräumen (HIGH RISK)
**Ziel:** SpotifySyncService auf Spotify OAuth-Sync reduzieren

1. **Entferne** ViewModels (bereits in Phase 1 verschoben)
2. **Entferne** Multi-Provider Logik (bereits in Phase 3 verschoben)
3. **Behalte** NUR Spotify OAuth-basierte Methoden:
   - `sync_followed_artists()`
   - `sync_user_playlists()`
   - `sync_liked_songs()`
   - `sync_saved_albums()`

**Ergebnis:** SpotifySyncService von 1839 → ~500 Zeilen

---

## 4. NEUE SERVICE INTERFACES

### 4.1 LibraryViewService ✅ IMPLEMENTED

```python
# library_view_service.py
class LibraryViewService:
    """ViewModels für Template-Rendering.
    
    Hey future me - dieser Service liefert FERTIGE ViewModels!
    Routes rufen diesen Service auf und geben ViewModels an Templates.
    KEINE Model-Details in Routes!
    """
    
    def __init__(
        self,
        session: AsyncSession,
        spotify_sync: SpotifySyncService,  # Für Sync-on-demand
        deezer_sync: DeezerSyncService,    # Für Fallback
    ):
        ...
    
    async def get_album_detail_view(
        self, artist_id: str, album_id: str
    ) -> AlbumDetailView | None:
        """Album-Detail ViewModel für Template."""
        ...
    
    async def get_artist_detail_view(
        self, artist_id: str
    ) -> ArtistDetailView | None:
        """Artist-Detail ViewModel für Template."""
        ...
```

### 4.2 DeezerSyncService

```python
# deezer_sync_service.py
class DeezerSyncService:
    """Deezer-spezifischer Sync Service.
    
    Hey future me - Deezer braucht KEIN OAuth für die meisten Operationen!
    Nur User-Favoriten brauchen Auth, aber Charts/New Releases sind public.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        deezer_plugin: DeezerPlugin,
    ):
        ...
    
    async def sync_artist_albums(
        self, deezer_artist_id: str
    ) -> SyncResult:
        """Sync artist albums from Deezer to DB."""
        ...
    
    async def sync_charts(
        self, country: str = "de"
    ) -> SyncResult:
        """Sync Deezer charts to DB."""
        ...
```

### 4.3 ProviderSyncOrchestrator

```python
# provider_sync_orchestrator.py
class ProviderSyncOrchestrator:
    """Koordiniert Sync über mehrere Provider mit Fallback.
    
    Hey future me - das ist der ORCHESTRATOR!
    Er entscheidet welchen Provider zu nutzen und macht Fallback.
    """
    
    def __init__(
        self,
        spotify_sync: SpotifySyncService,
        deezer_sync: DeezerSyncService,
        settings: AppSettingsService,
    ):
        ...
    
    async def sync_artist_albums(
        self, artist_id: str
    ) -> SyncResult:
        """Sync artist albums - Spotify first, Deezer fallback.
        
        1. Check if Spotify authenticated → Use SpotifySync
        2. If not authenticated or failed → Use DeezerSync (no auth needed!)
        3. Return combined result
        """
        ...
```

---

## 5. RISIKOANALYSE

| Phase | Risiko | Mitigation |
|-------|--------|------------|
| 1 (ViewModels) | LOW | Backward-Compat Wrapper, Tests |
| 2 (DeezerSync) | MEDIUM | Neuer Service, keine Breaking Changes |
| 3 (Orchestrator) | MEDIUM | Routes müssen angepasst werden |
| 4 (Cleanup) | HIGH | Viele Abhängigkeiten, genau prüfen |

---

## 6. TESTS-STRATEGIE

Da wir KEINE automatisierten Tests haben (nur Live-Testing):

1. **Nach jeder Phase:** Docker starten, manuell testen
2. **Kritische Flows testen:**
   - Followed Artists Sync
   - Album Detail Page
   - New Releases Page
   - Search (nutzt Multi-Provider)
3. **Fallback testen:** Spotify-Token entfernen, Deezer-Fallback prüfen

---

## 7. TIMELINE VORSCHLAG

| Phase | Geschätzte Zeit | Abhängigkeiten |
|-------|-----------------|----------------|
| Phase 1 (ViewModels) | 1-2 Stunden | Keine |
| Phase 2 (DeezerSync) | 2-3 Stunden | Keine |
| Phase 3 (Orchestrator) | 2-3 Stunden | Phase 1+2 |
| Phase 4 (Cleanup) | 1-2 Stunden | Phase 1-3 |

**Gesamt:** ~8-10 Stunden Arbeit

---

## 8. ENTSCHEIDUNGSFRAGEN

Vor dem Start benötigen wir Entscheidungen:

1. **Phase 1 sofort starten?** ViewModels extrahieren ist LOW RISK
2. **DeezerSyncService - welche Methoden?** Charts, NewReleases, ArtistAlbums?
3. **Orchestrator-Name?** `ProviderSyncOrchestrator` oder `MultiProviderSyncService`?
4. **Backward-Compat?** Wie lange Wrapper in SpotifySyncService behalten?

---

## 9. NÄCHSTE AKTION

**Empfohlen:** Phase 1 starten (LibraryViewService)

Grund: 
- Niedrigstes Risiko
- Sofortiger Architektur-Gewinn
- Unabhängig von anderen Phasen
- `get_album_detail_view()` bereits implementiert, nur verschieben

Soll ich mit Phase 1 beginnen?
