# Unified Library Worker - Migrations-Inventar

> **Letzte Aktualisierung:** 2025-01-XX
> **Status:** Planungsphase
> **Referenz:** `docs/architecture/UNIFIED_LIBRARY_WORKER.md`

---

## 📊 Übersicht

| Kategorie | Anzahl Dateien | Geschätzte Zeilen | Aktion |
|-----------|----------------|-------------------|--------|
| **LÖSCHEN** (Worker) | 10 | ~7.200 | Logik → ULM migrieren |
| **BEHALTEN** (Plugins) | 4 | ~2.800 | Unverändert |
| **BEHALTEN** (Infra Workers) | 9 | ~3.100 | Unverändert |
| **BEHALTEN** (Services) | ~45 | - | Meiste bleiben |
| **BEHALTEN** (Clients) | 9 | ~3.100 | Unverändert |

---

## ❌ ZU LÖSCHEN (nach Migration)

### Workers (11 Dateien → LÖSCHEN)

| Datei | Zeilen | Migriert zu | Priorität |
|-------|--------|-------------|-----------|
| `workers/spotify_sync_worker.py` | 1.180 | ULM Phase 1 (DISCOVER) | 🔴 Hoch |
| `workers/deezer_sync_worker.py` | 1.054 | ULM Phase 1 (DISCOVER) | 🔴 Hoch |
| `workers/library_discovery_worker.py` | 1.346 | ULM Phase 2-4 (IDENTIFY/ENRICH/EXPAND) | 🔴 Hoch |
| `workers/library_scan_worker.py` | 376 | ULM Phase 1 (Local Scan) | 🔴 Hoch |
| `workers/ImageWorker.py` | 286 | ULM Phase 5 (IMAGERY) | 🟡 Mittel |
| `workers/image_queue_worker.py` | 435 | ULM Phase 5 (IMAGERY) | 🟡 Mittel |
| `workers/cleanup_worker.py` | 366 | ULM Phase 6 (CLEANUP) | 🟡 Mittel |
| `workers/new_releases_sync_worker.py` | 618 | ULM (optional Task) | 🟢 Niedrig |
| `workers/duplicate_detector_worker.py` | 711 | ULM (optional Task) | 🟢 Niedrig |
| `workers/automation_workers.py` | 835 | ⚠️ EVALUIEREN | 🟢 Niedrig |
| **SUMME** | **~7.200** | - | - |

### Deprecated Services (nach Worker-Migration)

| Datei | Zeilen | Ersetzt durch | Wann löschen |
|-------|--------|---------------|--------------|
| `services/spotify_sync_service.py` | 2.350 | SpotifyPlugin + ULM | Nach Phase 1 |
| `services/deezer_sync_service.py` | 1.487 | DeezerPlugin + ULM | Nach Phase 1 |
| `services/provider_sync_orchestrator.py` | ~300 | ULM | Nach Phase 1 |

> **Hinweis:** Diese Services enthalten Sync-Logik die in den UnifiedLibraryManager migriert wird.
> Die Plugins (SpotifyPlugin, DeezerPlugin) bleiben bestehen!

---

## ✅ BEHALTEN (Unverändert)

### Plugins (4 Dateien → BEHALTEN)

| Datei | Zeilen | Funktion | Warum behalten? |
|-------|--------|----------|-----------------|
| `plugins/spotify_plugin.py` | 1.487 | API → DTO Adapter | Stabile Adapter-Schicht |
| `plugins/deezer_plugin.py` | ~1.000 | API → DTO Adapter | Stabile Adapter-Schicht |
| `plugins/tidal_plugin.py` | ~200 | API → DTO Adapter | Erweiterbarkeit |
| `plugins/registry.py` | ~100 | Plugin Registry | Infra |

### Clients (9 Dateien → BEHALTEN)

| Datei | Zeilen | Funktion | Warum behalten? |
|-------|--------|----------|-----------------|
| `integrations/spotify_client.py` | ~600 | Low-Level HTTP | Getestet, stabil |
| `integrations/deezer_client.py` | ~500 | Low-Level HTTP | Getestet, stabil |
| `integrations/tidal_client.py` | ~200 | Low-Level HTTP | Erweiterbarkeit |
| `integrations/musicbrainz_client.py` | ~400 | MusicBrainz API | Enrichment |
| `integrations/coverartarchive_client.py` | ~200 | Cover Art | Images |
| `integrations/lastfm_client.py` | ~200 | Last.fm API | Optional |
| `integrations/slskd_client.py` | ~600 | Soulseek Downloads | Downloads |
| `integrations/http_pool.py` | ~150 | HTTP Connection Pool | Shared Infra |
| `integrations/circuit_breaker_wrapper.py` | ~100 | Circuit Breaker | Resilience Pattern |

### Infrastructure Workers (7 Dateien → BEHALTEN)

| Datei | Zeilen | Funktion | Warum behalten? |
|-------|--------|----------|-----------------|
| `workers/download_worker.py` | 254 | Audio-Downloads | Separates Domain |
| `workers/download_monitor_worker.py` | 506 | slskd Progress | Download-Gruppe |
| `workers/download_status_sync_worker.py` | ~200 | Status Sync | Download-Gruppe |
| `workers/token_refresh_worker.py` | 217 | OAuth Tokens | Auth-spezifisch |
| `workers/orchestrator.py` | 846 | Worker Management | Infra |
| `workers/job_queue.py` | ~400 | Job Queue | Shared Infra |
| `workers/persistent_job_queue.py` | ~300 | Persistent Jobs | Shared Infra |
| `workers/queue_dispatcher_worker.py` | ~200 | Job Dispatch | Shared Infra |
| `workers/retry_scheduler_worker.py` | ~200 | Retry Logic | Shared Infra |

### Core Services (BEHALTEN)

| Service | Funktion | Warum behalten? |
|---------|----------|-----------------|
| `app_settings_service.py` | Settings aus DB | Core |
| `library_scanner_service.py` | Local Scan Logic | Wird von ULM genutzt |
| `musicbrainz_enrichment_service.py` | MBID/ISRC Lookup | Wird von ULM genutzt |
| `images/image_service.py` | Image Downloads | Wird von ULM genutzt |
| `images/repair.py` | Image Repair | Wird von ULM genutzt |
| `duplicate_service.py` | Duplicate Detection | Wird von ULM genutzt |
| `library_cleanup_service.py` | Cleanup Logic | Wird von ULM genutzt |
| `discography_service.py` | Discography Fetch | Wird von ULM genutzt |
| `token_manager.py` | Token Management | Auth |

---

## 🔄 ZU MIGRIEREN (Logik extrahieren)

### Phase 1: DISCOVER

**Aus SpotifySyncWorker extrahieren:**
```python
# Funktionen die in ULM wandern
_sync_followed_artists()       # → ULM._task_sync_spotify_likes
_sync_liked_songs()            # → ULM._task_sync_spotify_likes
_sync_saved_albums()           # → ULM._task_sync_spotify_likes
_sync_playlists()              # → ULM._task_sync_playlists
_gradual_artist_albums()       # → ULM._task_expand_discography
_gradual_album_tracks()        # → ULM._task_expand_discography
```

**Aus DeezerSyncWorker extrahieren:**
```python
_sync_followed_artists()       # → ULM._task_sync_deezer_favorites
_sync_saved_tracks()           # → ULM._task_sync_deezer_favorites
_sync_saved_albums()           # → ULM._task_sync_deezer_favorites
_sync_playlists()              # → ULM._task_sync_playlists
_gradual_artist_albums()       # → ULM._task_expand_discography
_gradual_album_tracks()        # → ULM._task_expand_discography
```

**Aus LibraryScanWorker extrahieren:**
```python
_handle_scan_job()             # → ULM._task_scan_local_library
_handle_cleanup_job()          # → ULM._task_cleanup_library
```

### Phase 2: IDENTIFY

**Aus LibraryDiscoveryWorker extrahieren:**
```python
_discover_artist_ids()         # → ULM._task_identify_artists
_discover_album_ids()          # → ULM._task_identify_albums
_discover_track_ids_by_isrc()  # → ULM._task_identify_tracks
```

### Phase 3: ENRICH

**Aus LibraryDiscoveryWorker extrahieren:**
```python
_fetch_artist_metadata()       # → ULM._task_enrich_metadata
_fetch_album_metadata()        # → ULM._task_enrich_metadata
_fetch_track_metadata()        # → ULM._task_enrich_metadata
```

### Phase 4: EXPAND

**Aus LibraryDiscoveryWorker extrahieren:**
```python
_fetch_artist_discography()    # → ULM._task_expand_discography
_update_is_owned_flags()       # → ULM._task_cleanup_library
```

### Phase 5: IMAGERY

**Aus ImageBackfillWorker + ImageQueueWorker extrahieren:**
```python
# ImageBackfillWorker
_run_cycle()                   # → ULM._task_enrich_images

# ImageQueueWorker
_process_loop()                # → ULM._task_enrich_images (inline)
_download_and_save()           # → ULM._download_image()
```

### Phase 6: CLEANUP

**Aus CleanupWorker extrahieren:**
```python
_handle_cleanup_job()          # → ULM._task_cleanup_library
_cleanup_orphaned_files()      # Separate utility bleiben
_cleanup_temp_files()          # Separate utility bleiben
```

---

## 📂 Neue Dateien (zu erstellen)

| Datei | Funktion | Phase |
|-------|----------|-------|
| `workers/unified_library_worker.py` | UnifiedLibraryManager | Woche 1 |
| `workers/task_scheduler.py` | TaskScheduler mit Dependencies | Woche 1 |
| `domain/entities/ownership.py` | OwnershipState, DownloadState | Woche 1 |
| `application/sources/import_source.py` | ImportSource Protocol | Woche 2 |
| `application/sources/spotify_source.py` | SpotifyImportSource | Woche 2 |
| `application/sources/deezer_source.py` | DeezerImportSource | Woche 2 |
| `application/sources/local_source.py` | LocalImportSource | Woche 2 |
| `application/services/entity_deduplicator.py` | EntityDeduplicator | Woche 3 |

---

## 🚦 Feature Flags (für schrittweise Migration)

```python
# In app_settings (Datenbank)
"library.use_unified_manager": false     # Master Switch
"library.ulm_phase1_enabled": false      # Local Scan
"library.ulm_phase1_cloud_enabled": false # Cloud Sync
"library.ulm_phase2_enabled": false      # ID Discovery
"library.ulm_phase3_enabled": false      # Enrichment
"library.ulm_phase4_enabled": false      # Discography
"library.ulm_phase5_enabled": false      # Images
"library.ulm_phase6_enabled": false      # Cleanup
```

---

## 📅 Migrations-Timeline

| Woche | Aufgabe | Zu löschen nach Erfolg |
|-------|---------|------------------------|
| 1 | TaskScheduler + Phase 1 (Local Scan) | - |
| 2 | Phase 1 (Cloud Sync - Spotify) | - |
| 3 | Phase 1 (Cloud Sync - Deezer) + Phase 2 | `library_scan_worker.py` |
| 4 | Phase 3-4 (Enrich + Expand) | `library_discovery_worker.py` |
| 5 | Phase 5 (Imagery) | `ImageWorker.py`, `image_queue_worker.py` |
| 6 | Phase 6 (Cleanup) | `cleanup_worker.py` |
| 7 | Feature Flag Rollout | `spotify_sync_worker.py`, `deezer_sync_worker.py` |

---

## ⚠️ Risiken & Mitigations

| Risiko | Mitigation |
|--------|------------|
| Datenbankkonflikte während Migration | Feature Flags für schrittweise Aktivierung |
| Performance-Regression | Benchmark vor/nach jeder Phase |
| Sync-Logik-Unterschiede | Unit Tests für kritische Pfade |
| Token-Management-Fehler | TokenRefreshWorker bleibt separat |
| Bilddownload-Timeout | Semaphore + Retry-Logik übernehmen |

---

## 📋 Checkliste pro Phase

### Vor Migration einer Phase

- [ ] Alle Tests für alte Worker dokumentiert
- [ ] Benchmark für Performance-Vergleich erstellt
- [ ] Feature Flag in app_settings angelegt
- [ ] Rollback-Plan dokumentiert

### Nach Migration einer Phase

- [ ] Neue Tasks getestet (Unit + Integration)
- [ ] Performance-Vergleich OK
- [ ] Feature Flag aktiviert (Testumgebung)
- [ ] 1 Woche Beobachtung ohne Fehler
- [ ] Alte Worker-Dateien gelöscht
- [ ] Dokumentation aktualisiert

---

## 🔍 Abhängigkeiten-Graph

```
TokenRefreshWorker (BLEIBT)
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│              UNIFIED LIBRARY MANAGER (NEU)                     │
│                                                                │
│   Phase 1: DISCOVER ──► Phase 2: IDENTIFY ──► Phase 3: ENRICH │
│        │                      │                     │         │
│        ▼                      ▼                     ▼         │
│   Phase 4: EXPAND ──────────────────────► Phase 5: IMAGERY    │
│        │                                       │              │
│        └──────────────► Phase 6: CLEANUP ◄─────┘              │
│                                                                │
└───────────────────────────────────────────────────────────────┘
        │
        ▼ (setzt download_state=PENDING)
DownloadWorker (BLEIBT)
        │
        ▼
DownloadMonitorWorker (BLEIBT)
```

---

## 📚 Referenzen

- `docs/architecture/UNIFIED_LIBRARY_WORKER.md` - Hauptdokumentation
- `docs/architecture/DATA_LAYER_PATTERNS.md` - Entity/Repository Patterns
- `.github/instructions/architecture.instructions.md` - Code Patterns
