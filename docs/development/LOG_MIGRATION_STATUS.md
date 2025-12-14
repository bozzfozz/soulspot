# Log-Design-System Migration Status

**Stand:** 2025-12-14 (Update #5 - Task #30)

## 📊 Übersicht

| Metrik | Wert | Status |
|--------|------|--------|
| **Migriert** | 20 Dateien | 🟡 29% |
| **Noch zu migrieren** | 49 Dateien | 🟠 71% |
| **System erstellt** | ✅ Komplett | 🟢 100% |

## ✅ Migrierte Dateien (20)

### Core Infrastructure (1)
1. `infrastructure/observability/log_messages.py` - **NEU ERSTELLT** - Template System

### Workers (8) ✅ PHASE 2 ABGESCHLOSSEN
2. `application/workers/download_status_sync_worker.py` - Connection errors
3. `application/workers/spotify_sync_worker.py` - Worker start messages
4. `application/workers/token_refresh_worker.py` - Worker start messages
5. `application/workers/automation_workers.py` - 3× Worker starts (Watchlist, Discography, Quality Upgrade)
6. `application/workers/download_monitor_worker.py` - Worker start messages
7. `application/workers/cleanup_worker.py` - Worker start messages
8. `application/workers/duplicate_detector_worker.py` - Worker start messages

### Services (6)
9. `application/services/auto_import.py` - Config validation errors
10. `application/services/spotify_sync_service.py` - Liked Songs sync error
11. `application/services/followed_artists_service.py` - Artist processing, pagination, album fetch errors
12. `application/services/discography_service.py` - Artist lookup, Spotify URI, discography check errors
13. `application/services/download_manager_service.py` - Provider download fetch errors
14. `application/services/artist_songs_service.py` - Track processing, top tracks fetch, bulk sync, DTO validation errors

### API Routers (5) ✅ PHASE 1 ABGESCHLOSSEN
15. `api/routers/artists.py` - Sync errors
16. `api/routers/search.py` - Search errors (Spotify, Soulseek)
17. `api/routers/downloads.py` - Download operations (track lookup, queue, cancel, retry, priority)
18. `api/routers/library.py` - Library operations (clear, duplicates, images, disambiguation)
19. `api/routers/automation.py` - Followed artists sync, watchlist creation errors

### Infrastructure Plugins (1)
20. `infrastructure/plugins/spotify_plugin.py` - Defensive album validation (Bug Fix)

## 🔴 Noch zu migrieren (49 Dateien)

### Kritisch (User-facing)
| Datei | Error-Logs | Priorität |
|-------|------------|-----------|
| `api/routers/artist_songs.py` | ~4 | 🟡 MEDIUM |
| `api/routers/download_manager.py` | ~3 | 🟡 MEDIUM |

### Worker (Background)
| Datei | Error-Logs | Priorität |
|-------|------------|-----------|
| `application/workers/automation_workers.py` | ~15 | 🟡 MEDIUM |
| `application/workers/download_monitor_worker.py` | ~8 | 🟡 MEDIUM |
| `application/workers/cleanup_worker.py` | ~3 | 🟢 LOW |
| `application/workers/duplicate_detector_worker.py` | ~2 | 🟢 LOW |

### Services (Internal)
| Datei | Error-Logs | Priorität |
|-------|------------|-----------|
| `application/services/followed_artists_service.py` | ~4 | 🟡 MEDIUM |
| `application/services/discography_service.py` | ~3 | 🟡 MEDIUM |
| `application/services/download_manager_service.py` | ~5 | 🟡 MEDIUM |
| `application/services/notification_service.py` | ~3 | 🟢 LOW |
| `application/services/compilation_analyzer_service.py` | ~4 | 🟢 LOW |

## 📈 Migration-Plan

### Phase 1: Kritische User-Facing Logs (Woche 1) ✅ TEILWEISE
- ✅ `search.py` - Search errors
- ✅ `artists.py` - Sync errors
- ✅ `auto_import.py` - Config errors
- ✅ `downloads.py` - Download operations
- ✅ `library.py` - Library operations

**Fortschritt:** 5/5 Dateien (100%) ✅ **PHASE KOMPLETT!**

### Phase 2: Worker Lifecycle (Woche 2) ✅ ABGESCHLOSSEN
- ✅ `spotify_sync_worker.py` - Worker start
- ✅ `token_refresh_worker.py` - Worker start
- ✅ `download_status_sync_worker.py` - Connection errors
- ✅ `automation_workers.py` - 3× worker starts (Watchlist, Discography, Quality Upgrade)
- ✅ `download_monitor_worker.py` - Worker lifecycle
- ✅ `cleanup_worker.py` - Worker start
- ✅ `duplicate_detector_worker.py` - Worker start

**Fortschritt:** 7/7 Dateien (100%) ✅ **PHASE KOMPLETT!**

### Phase 3: Service Layer (Woche 3) 🔴 TODO
- ⏳ `followed_artists_service.py`
- ⏳ `discography_service.py`
- ⏳ `download_manager_service.py`
- ⏳ `artist_songs_service.py`
- ⏳ `filter_service.py`

**Fortschritt:** 0/5 Dateien (0%)

### Phase 4: Remaining (Woche 4) 🔴 TODO
- ⏳ Notification services
- ⏳ Metadata services
- ⏳ Postprocessing services
- ⏳ Cleanup/maintenance workers
- ⏳ Edge cases

**Fortschritt:** 0/~50 Dateien (0%)

## 🎯 Nächste Schritte

### Sofort (High-Impact)
1. **`api/routers/downloads.py`** - Download errors (~8 logs)
   - Download start/complete/failed
   - Provider errors
   - slskd connection
   
2. **`api/routers/library.py`** - Library operations (~12 logs)
   - File delete errors
   - Image download errors
   - Enrichment errors

3. **`application/workers/automation_workers.py`** - Automation lifecycle (~15 logs)
   - Watchlist worker start
   - Discography worker start
   - Quality upgrade worker start
   - Worker failures

### Diese Woche (Quick Wins)
4. **`application/workers/download_monitor_worker.py`** - Download monitoring
5. **`application/services/followed_artists_service.py`** - Artist sync
6. **`application/services/discography_service.py`** - Discography checks

### Nächste Woche (Cleanup)
- Remaining service layers
- Edge cases
- Final consistency check

## 📝 Migration-Template

```python
# VORHER
logger.error(f"Failed to do something: {e}", exc_info=True)

# NACHHER
from soulspot.infrastructure.observability.log_messages import LogMessages

logger.error(
    LogMessages.<template>(
        # Required fields
        entity="What failed",
        source="Which service",
        error=str(e),
        # Optional hint
        hint="What to do about it"
    ),
    exc_info=True  # KEEP THIS!
)
```

## 🧪 Validierung

**Nach jeder Migration:**
1. ✅ Error check: `get_errors` für modifizierte Dateien
2. ✅ Import check: File importiert ohne Fehler
3. ✅ Syntax check: Python-Syntax valide
4. ✅ Output check: Log-Ausgabe im Docker prüfen

## 📚 Ressourcen

- **Template System:** `infrastructure/observability/log_messages.py`
- **Dokumentation:** `docs/development/LOG_DESIGN_SYSTEM.md`
- **Beispiele:** Siehe bereits migrierte Dateien oben

## 🎓 Lessons Learned

### Was funktioniert gut ✅
- Tree-Format mit Icons ist sehr lesbar
- Hints sind extrem hilfreich
- Migration ist straightforward (altes durch neues ersetzen)
- Keine Breaking Changes (alte Logs funktionieren weiter)

### Herausforderungen ⚠️
- Viele Dateien zu migrieren (69!)
- Muss exc_info=True beibehalten
- Import muss in jedem File hinzugefügt werden
- Hint-Texte müssen durchdacht sein

### Best Practices 💡
1. **Priorität:** User-facing zuerst
2. **Batch:** Mehrere ähnliche Logs gleichzeitig
3. **Test:** Output im Docker prüfen
4. **Document:** Migration-Status aktualisieren

---

**Erstellt:** 2025-12-14  
**Letztes Update:** 2025-12-14  
**Nächstes Review:** Nach Phase 2 (Woche 2)
