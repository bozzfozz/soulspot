# TODOs & Unvollständige Implementierungen

**Generated:** 2025-12-12  
**Last Updated:** 2025-12-13  
**Total TODOs:** 35 → **5 remaining**  
**Status:** ✅ ALL CRITICAL/MEDIUM TODOs behoben, nur Interface-Stubs verbleiben

---

## 🟢 STATUS: KRITISCHE TODOs BEHOBEN

Die folgenden kritischen Issues wurden in der Backend-Modernisierung behoben:

### ✅ 1. Metadata Conflict Detection - ERLEDIGT
**Was:** `metadata.py:88` - Conflict detection implementiert  
**Fix:** MetadataMerger._detect_conflicts() findet Widersprüche zwischen Quellen  
**Datum:** 2025-12-12

### ✅ 2. Spotify Token Extraction - ERLEDIGT
**Was:** `metadata.py:126` - Token aus Session extrahieren  
**Fix:** get_spotify_token_shared() mit auto-refresh implementiert  
**Datum:** 2025-12-12

### ✅ 3. Settings Reset - ERLEDIGT
**Was:** `settings.py:294` - Reset-Funktion fehlte  
**Fix:** AppSettingsService.reset_all(category) implementiert  
**Datum:** 2025-12-12

### ✅ 4. Album Search - ERLEDIGT
**Was:** `search.py:267` - Album-Suche fehlte  
**Fix:** SpotifyClient.search_album() + Interface hinzugefügt  
**Datum:** 2025-12-12

### ✅ 5. Deezer ID Field - ERLEDIGT
**Was:** `local_library_enrichment_service.py:552` - deezer_id Feld fehlte  
**Fix:** deezer_id + tidal_id zu TrackModel/AlbumModel/ArtistModel hinzugefügt  
**Datum:** 2025-12-12

---

## 🟡 MEDIUM (Verbleibende Feature-Lücken)

### ✅ 6. Duplicate Track Deletion Queue - ERLEDIGT
**Was:** `library.py:1086-1090` - Automatisches Löschen von Duplikaten  
**Fix:** resolve_duplicate() löscht Dateien via os.remove() + setzt file_path=None  
**Datum:** War bereits implementiert, TODO veraltet

### 4. Duplicate Track Deletion Queue (library.py:1086-1090)
**Issue:** 
```python
# TODO: Queue deletion of track 2
# TODO: Queue deletion of track 1
```

**Location:** `src/soulspot/api/routers/library.py:1086-1090`

**Problem:** Automatisches Löschen von Duplikaten nicht implementiert.

**Impact:** 🟡 MEDIUM - Manuelle Löschung erforderlich.

**Fix Required:**
```python
# Queue deletion via DownloadService
await download_service.queue_deletion(track_id)
```

---

### 5. Album Search Missing (search.py:267)
**Issue:** `# TODO: Add search_album to SpotifyClient for proper album search`

**Location:** `src/soulspot/api/routers/search.py:267`

**Problem:** Keine dedizierte Album-Suche in SpotifyClient.

**Impact:** 🟡 MEDIUM - Workaround existiert (Track-Suche).

**Fix Required:**
```python
# Add to SpotifyClient:
async def search_album(self, query: str, access_token: str, limit: int = 20):
    ...
```

---

### ✅ 7. Track Lookup by Spotify ID - ERLEDIGT
**Was:** `downloads.py:142` - Download ohne Track-Lookup  
**Fix:** Implementiert track_repository.get_by_spotify_uri() lookup. Gibt 404 zurück wenn Track nicht in DB (muss erst importiert werden).  
**Datum:** 2025-12-12

---

### ✅ 8. Deezer ID Field Missing - ERLEDIGT (Week 5)
**Issue:** `# TODO: Consider adding deezer_id field to TrackModel`

**Location:** `src/soulspot/application/services/local_library_enrichment_service.py:552`

**Problem:** Kein Deezer-ID-Feld für Multi-Service-Support.

**Impact:** 🟢 LOW - Zukünftige Feature-Erweiterung.

**Fix Required:**
```python
# Add to TrackModel:
deezer_id: str | None = Column(String, nullable=True, index=True)
```

---

### ✅ 8. Deezer Fuzzy Matching - BEREITS IMPLEMENTIERT
**Was:** `deezer_client.py` - Fuzzy-Matching für Track-Suche

**Location:** `src/soulspot/infrastructure/integrations/deezer_client.py:1082-1106`

**Status:** WAR BEREITS IMPLEMENTIERT - Verifiziert 2025-12-13

**Implementierung:**
```python
def _match_score(self, search_result: dict, artist: str, title: str) -> float:
    """Calculate fuzzy match score for search results."""
    # Uses fuzz.ratio() and fuzz.partial_ratio() for title/artist matching
    # Applies duration tolerance bonus
    # Returns weighted score 0.0-1.0
```

**Methode:** 
- `_match_score()` nutzt rapidfuzz für Title/Artist-Vergleich
- `_find_best_match()` wählt besten Treffer über Threshold
- Integration in `download_track()` mit Confidence-Scoring

**Datum:** War bereits implementiert vor 2025-12-12

---

### 9. Metadata Confidence Scoring (enrich_metadata.py:125) ✅ ERLEDIGT
**Issue:** `# TODO: Add confidence scoring to avoid false matches`

**Location:** `src/soulspot/application/use_cases/enrich_metadata.py:125`

**Fix:** Implemented `_calculate_match_confidence()` method using rapidfuzz:
- Title similarity (token_sort_ratio) with 60% weight
- Artist similarity (partial_ratio) with 40% weight
- Duration bonus/penalty for validation
- Minimum threshold of 0.75 to accept matches
- All MusicBrainz results are scored, best above threshold is selected

**Datum:** 2025-12-13

---

## 🟢 LOW (Nice-to-Have / Future Enhancements)

### ✅ 10. Notification Service - IMPLEMENTIERT
**Was:** `notification_service.py:22` - Echte Notification-Provider  

**Status:** VOLLSTÄNDIG IMPLEMENTIERT am 2025-12-13

**Implementierte Komponenten:**
- `domain/ports/notification.py` - Interface + Dataclasses (INotificationProvider, Notification, NotificationType, etc.)
- `infrastructure/notifications/email_provider.py` - SMTP Email-Versand
- `infrastructure/notifications/webhook_provider.py` - Discord/Slack/Gotify/Generic Webhooks
- `infrastructure/notifications/inapp_provider.py` - DB-basierte In-App Notifications
- `application/services/notification_service.py` - Orchestriert alle Provider
- `api/routers/notifications.py` - REST API für In-App Notifications
- `alembic/versions/vv33018xxz66_add_notifications_table.py` - DB Migration

**Features:**
- Multi-Provider Support (Email, Webhook, In-App parallel)
- Rich Discord/Slack Embeds
- Gotify Push Notifications
- Persistent In-App Notifications mit Read/Unread Status
- HTMX Badge Support
- Backward-compatible API (logging-only mode ohne Session)

**Config via app_settings:**
- `notification.email.*` - SMTP Settings
- `notification.webhook.*` - Webhook Settings  
- `notification.inapp.*` - In-App Settings

---

### 11. Cross-Filesystem Move Fallback (renaming_service.py:428) ✅ ERLEDIGT
**Issue:** `# TODO: Add fallback to copy+delete for cross-filesystem moves`

**Location:** `src/soulspot/application/services/postprocessing/renaming_service.py:428`

**Fix:** Implemented try/except block with errno.EXDEV detection. 
- First attempts atomic `rename()` for same-filesystem moves
- Falls back to `shutil.move()` for cross-filesystem moves (EXDEV error)
- Re-raises other OSError types (permission denied, disk full)

**Datum:** 2025-12-13

---

### 12-35. Interface/Exception/Cache Stubs
**Issue:** `pass` in Abstract Base Classes, Exceptions, Cache-Interface

**Locations:**
- `application/cache/base_cache.py` (5x `pass` - Interface-Definition OK)
- `domain/exceptions/__init__.py` (2x `pass` - Exception-Stubs OK)
- `application/workers/*.py` (3x `pass` - Worker-Stubs OK)

**Impact:** 🟢 NONE - Normale Interface-Definitionen, kein Bug.

**Action:** None required (design pattern).

---

## Summary by Priority

| Priority | Count | Requires Action |
|----------|-------|-----------------|
| 🔴 CRITICAL | 0 | ✅ ALL FIXED |
| 🟡 MEDIUM | 0 | ✅ ALL FIXED |
| 🟢 LOW | 5 | No - Design/Interface stubs |

**Completed TODOs (2025-12-12 to 2025-12-13):**
- ✅ Metadata Conflict Detection
- ✅ Spotify Token Extraction  
- ✅ Settings Reset
- ✅ Album Search
- ✅ Deezer ID Field
- ✅ Duplicate Track Deletion
- ✅ Track Lookup by Spotify ID
- ✅ Deezer Fuzzy Matching (was already implemented)
- ✅ Metadata Confidence Scoring
- ✅ Cross-Filesystem Move Fallback
- ✅ **Notification Service** (full multi-provider implementation)

---

## Recommended Action Plan

### ✅ Phase 1: Critical Fixes - COMPLETE
All critical issues have been resolved.

### ✅ Phase 2: Medium Enhancements - COMPLETE
All medium priority issues have been resolved.

### Phase 3: Low Priority (Optional - No Action Required)
- Notification Service: Still logging stub (acceptable for MVP)
- Interface/Cache stubs: Design pattern, intentional `pass` statements

---

## Testing Requirements

**After each fix:**
- [ ] Unit test for new functionality
- [ ] Integration test if API-related
- [ ] Manual testing with real data
- [ ] Update API documentation if behavior changes

---

## Notes

- Most `pass` statements are legitimate interface definitions (ABC, Protocol)
- Exception stubs are placeholders for future specific exceptions
- Worker `pass` statements are in error handlers (acceptable)
- **Real issues:** 3 critical, 8 medium priority TODOs needing implementation
