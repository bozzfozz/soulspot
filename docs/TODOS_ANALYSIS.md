# TODOs & Unvollständige Implementierungen

**Generated:** 2025-12-12  
**Last Updated:** 2025-12-12 (Backend Modernization Complete)  
**Total TODOs:** 35 → **8 remaining**  
**Status:** ✅ CRITICAL TODOs behoben, nur mittlere/niedrige verbleiben

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

### 8. Deezer Fuzzy Matching (deezer_client.py:565)
**Issue:** `# TODO: Add fuzzy matching like Spotify enrichment service`

**Location:** `src/soulspot/infrastructure/integrations/deezer_client.py:565`

**Problem:** Deezer-Client hat kein Fuzzy-Matching für Track-Suche.

**Impact:** 🟡 MEDIUM - Weniger zuverlässige Matches.

**Fix Required:**
```python
# Use rapidfuzz or similar:
from rapidfuzz import fuzz
match_score = fuzz.ratio(query_title, result_title)
if match_score > 85:
    return result
```

---

### 9. Metadata Confidence Scoring (enrich_metadata.py:125)
**Issue:** `# TODO: Add confidence scoring to avoid false matches`

**Location:** `src/soulspot/application/use_cases/enrich_metadata.py:125`

**Problem:** Keine Confidence-Scores für Metadata-Matches.

**Impact:** 🟡 MEDIUM - False Positives möglich.

**Fix Required:**
```python
# Implement scoring:
confidence = calculate_match_confidence(
    query_title, result_title,
    query_artist, result_artist
)
if confidence < 0.8:
    logger.warning("Low confidence match, skipping")
    return None
```

---

## 🟢 LOW (Nice-to-Have / Future Enhancements)

### 10. Notification Service Stub (notification_service.py:22)
**Issue:** `# TODO: Integrate with real notification provider`

**Location:** `src/soulspot/application/services/notification_service.py:22`

**Problem:** Nur Logging-Stub, keine echten Notifications.

**Impact:** 🟢 LOW - Feature-Request, nicht Bug.

**Fix Required:**
```python
# Add email/webhook/push providers:
class EmailNotificationProvider: ...
class WebhookNotificationProvider: ...
```

---

### 11. Cross-Filesystem Move Fallback (renaming_service.py:428)
**Issue:** `# TODO: Add fallback to copy+delete for cross-filesystem moves`

**Location:** `src/soulspot/application/services/postprocessing/renaming_service.py:428`

**Problem:** Move schlägt fehl bei Cross-Filesystem-Operationen.

**Impact:** 🟢 LOW - Seltener Edge-Case.

**Fix Required:**
```python
try:
    shutil.move(src, dst)
except OSError as e:
    if e.errno == errno.EXDEV:  # Cross-device link
        shutil.copy2(src, dst)
        os.remove(src)
```

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
| 🔴 CRITICAL | 3 | YES - Funktionalität/Bug |
| 🟡 MEDIUM | 8 | Optional - Verbesserungen |
| 🟢 LOW | 24 | No - Design/Future |

---

## Recommended Action Plan

### Phase 1: Critical Fixes (2-3 hours)
1. Implement metadata conflict detection (metadata.py:88)
2. Fix Spotify token extraction (metadata.py:126)
3. Implement settings reset (settings.py:294)

### Phase 2: Medium Enhancements (4-6 hours)
4. Add duplicate deletion queue (library.py)
5. Implement album search (search.py)
6. Add track lookup/placeholder (downloads.py)
7. Implement fuzzy matching for Deezer (deezer_client.py)
8. Add confidence scoring (enrich_metadata.py)

### Phase 3: Low Priority (Optional)
9. Implement notification providers
10. Add cross-filesystem move fallback
11. Add Deezer ID field to TrackModel

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
