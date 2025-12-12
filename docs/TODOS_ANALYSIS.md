# TODOs & Unvollständige Implementierungen

**Generated:** 2025-12-12  
**Total TODOs:** 35  
**Status:** Kategorisiert nach Kritikalität

---

## 🔴 CRITICAL (Funktionalität fehlt / Bug-Risiko)

### 1. Metadata Conflict Detection (metadata.py:88)
**Issue:** `# TODO - conflict detection isn't implemented! That's a pretty critical feature`

**Location:** `src/soulspot/api/routers/metadata.py:88`

**Problem:** Kein Konflikt-Handling bei widersprüchlichen Metadaten aus verschiedenen Quellen (Spotify vs. MusicBrainz).

**Impact:** 🔴 HIGH - Kann zu falschen Metadaten führen, Datenintegrität gefährdet.

**Fix Required:**
```python
# Implement conflict resolution strategy:
# 1. Authority hierarchy (MusicBrainz > Spotify > Last.fm)
# 2. Confidence scoring per field
# 3. Manual review queue for critical conflicts
```

---

### 2. Spotify Token Extraction (metadata.py:126)
**Issue:** `# TODO: Get from auth context - requires session/JWT token extraction`

**Location:** `src/soulspot/api/routers/metadata.py:126`

**Problem:** Spotify-Token wird nicht korrekt aus Session/Auth-Context extrahiert.

**Impact:** 🟡 MEDIUM - Metadata-Enrichment könnte 401 Errors bekommen.

**Fix Required:**
```python
# Extract from session:
spotify_access_token = await get_spotify_token_shared(request)
```

---

### 3. Settings Reset Not Implemented (settings.py:294)
**Issue:** `# TODO: Implement reset functionality`

**Location:** `src/soulspot/api/routers/settings.py:294`

**Problem:** POST /api/settings/reset funktioniert nicht.

**Impact:** 🟢 LOW - Feature fehlt, aber nicht kritisch.

**Fix Required:**
```python
# Load defaults from AppSettingsService
defaults = await settings_service.get_defaults()
await settings_service.reset_to_defaults()
```

---

## 🟡 MEDIUM (Feature-Lücken / Verbesserungen)

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

### 6. Track Lookup by Spotify ID (downloads.py:142)
**Issue:** `# TODO: Look up track by spotify_id or create placeholder`

**Location:** `src/soulspot/api/routers/downloads.py:142`

**Problem:** Download ohne existierenden Track erstellt keinen Placeholder.

**Impact:** 🟡 MEDIUM - Downloads könnten ohne Track-Referenz bleiben.

**Fix Required:**
```python
# Create placeholder track if not found:
track = await track_repo.get_by_spotify_uri(spotify_uri)
if not track:
    track = Track(title="Unknown", artist_id=ArtistId(...))
    await track_repo.add(track)
```

---

### 7. Deezer ID Field Missing (local_library_enrichment_service.py:552)
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
