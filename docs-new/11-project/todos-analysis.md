# TODOs Analysis & Resolution Status

**Category:** Project Management / Technical Debt  
**Generated:** 2025-12-12  
**Last Updated:** 2025-12-30  
**Total TODOs:** 35 → **5 remaining**  
**Status:** ✅ ALL CRITICAL/MEDIUM TODOs resolved, only interface stubs remain

---

## 🟢 STATUS: CRITICAL TODOs RESOLVED

The following critical issues were resolved in backend modernization:

### ✅ 1. Metadata Conflict Detection - COMPLETE
**Issue:** `metadata.py:88` - Conflict detection not implemented  
**Fix:** MetadataMerger._detect_conflicts() finds discrepancies between sources  
**Date:** 2025-12-12

**Implementation:**
```python
def _detect_conflicts(self, mb_data: dict, spotify_data: dict) -> list:
    conflicts = []
    
    # Title mismatch
    if mb_data["title"] != spotify_data["title"]:
        conflicts.append({
            "field": "title",
            "musicbrainz": mb_data["title"],
            "spotify": spotify_data["title"]
        })
    
    # Artist mismatch
    # Duration difference >5 seconds
    # Album mismatch
    ...
```

### ✅ 2. Spotify Token Extraction - COMPLETE
**Issue:** `metadata.py:126` - Token extraction from session missing  
**Fix:** get_spotify_token_shared() with auto-refresh implemented  
**Date:** 2025-12-12

**Implementation:**
```python
async def get_spotify_token_shared(session_id: str) -> str | None:
    spotify_session = await session_repo.get_by_session_id(session_id)
    if not spotify_session:
        return None
    
    # Auto-refresh if expired
    if spotify_session.is_expired():
        await token_service.refresh_token(spotify_session)
    
    return spotify_session.access_token
```

### ✅ 3. Settings Reset - COMPLETE
**Issue:** `settings.py:294` - Reset function missing  
**Fix:** AppSettingsService.reset_all(category) implemented  
**Date:** 2025-12-12

**Implementation:**
```python
async def reset_all(self, category: str | None = None):
    if category:
        await self.repo.delete_by_prefix(f"{category}.")
    else:
        await self.repo.delete_all()
```

### ✅ 4. Album Search - COMPLETE
**Issue:** `search.py:267` - Album search missing  
**Fix:** SpotifyClient.search_album() + Interface added  
**Date:** 2025-12-12

**Interface:**
```python
class ISpotifyClient(Protocol):
    async def search_album(self, query: str, access_token: str, limit: int = 20) -> list[AlbumDTO]: ...
```

### ✅ 5. Deezer ID Field - COMPLETE
**Issue:** `local_library_enrichment_service.py:552` - deezer_id field missing  
**Fix:** deezer_id + tidal_id added to TrackModel/AlbumModel/ArtistModel  
**Date:** 2025-12-12

**Migration:**
```python
# alembic/versions/xxx_add_multi_service_ids.py
op.add_column('tracks', sa.Column('deezer_id', sa.String(), nullable=True))
op.add_column('tracks', sa.Column('tidal_id', sa.String(), nullable=True))
op.create_index('ix_tracks_deezer_id', 'tracks', ['deezer_id'])
op.create_index('ix_tracks_tidal_id', 'tracks', ['tidal_id'])
```

---

## 🟡 MEDIUM: Resolved Feature Gaps

### ✅ 6. Duplicate Track Deletion Queue - COMPLETE
**Issue:** `library.py:1086-1090` - Automatic deletion of duplicates  
**Fix:** resolve_duplicate() deletes files via os.remove() + sets file_path=None  
**Status:** Was already implemented, TODO was outdated

**Implementation:**
```python
async def resolve_duplicate(track_id_to_keep: str, track_id_to_delete: str):
    track_to_delete = await track_repo.get_by_id(track_id_to_delete)
    
    # Delete file from filesystem
    if track_to_delete.file_path and os.path.exists(track_to_delete.file_path):
        os.remove(track_to_delete.file_path)
    
    # Mark as deleted in database
    track_to_delete.file_path = None
    await track_repo.update(track_to_delete)
```

### ✅ 7. Track Lookup by Spotify ID - COMPLETE
**Issue:** `downloads.py:142` - Download without track lookup  
**Fix:** Implemented track_repository.get_by_spotify_uri() lookup. Returns 404 if track not in DB (must import first).  
**Date:** 2025-12-12

**Implementation:**
```python
@router.post("/tracks/{spotify_uri}/download")
async def download_track(spotify_uri: str):
    # Lookup track in database
    track = await track_repo.get_by_spotify_uri(spotify_uri)
    if not track:
        raise HTTPException(404, "Track not in database. Import playlist/artist first.")
    
    # Queue download
    await download_service.queue_track(track.id)
```

### ✅ 8. Deezer Fuzzy Matching - IMPLEMENTED
**Issue:** `deezer_client.py` - Fuzzy matching for track search  
**Status:** WAS ALREADY IMPLEMENTED - Verified 2025-12-13

**Implementation:**
```python
def _match_score(self, search_result: dict, artist: str, title: str) -> float:
    """Calculate fuzzy match score for search results."""
    # Uses fuzz.ratio() and fuzz.partial_ratio() for title/artist matching
    # Applies duration tolerance bonus
    # Returns weighted score 0.0-1.0
    ...

def _find_best_match(self, results: list, artist: str, title: str, threshold=0.75) -> dict | None:
    best_match = None
    best_score = 0.0
    
    for result in results:
        score = self._match_score(result, artist, title)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = result
    
    return best_match
```

**Integration:**
```python
async def download_track(self, artist: str, title: str, duration: int):
    results = await self.search(f"{artist} {title}")
    best_match = self._find_best_match(results, artist, title)
    
    if not best_match:
        raise TrackNotFoundError(f"No match found for {artist} - {title}")
    
    return best_match["download_url"]
```

### ✅ 9. Metadata Confidence Scoring - COMPLETE
**Issue:** `enrich_metadata.py:125` - Confidence scoring missing  
**Fix:** Implemented `_calculate_match_confidence()` using rapidfuzz  
**Date:** 2025-12-13

**Implementation:**
```python
def _calculate_match_confidence(self, track: Track, mb_result: dict) -> float:
    """
    Calculate match confidence between local track and MusicBrainz result.
    
    Returns: 0.0-1.0 score (threshold: 0.75)
    """
    from rapidfuzz import fuzz
    
    # Title similarity (60% weight)
    title_score = fuzz.token_sort_ratio(
        track.title.lower(),
        mb_result["title"].lower()
    ) / 100.0
    
    # Artist similarity (40% weight)
    artist_score = fuzz.partial_ratio(
        track.artist.lower(),
        mb_result["artist"].lower()
    ) / 100.0
    
    # Duration bonus/penalty
    duration_diff = abs(track.duration - mb_result["duration"])
    duration_bonus = max(0, 1.0 - (duration_diff / 10))  # -0.1 per 10s difference
    
    # Weighted score
    confidence = (title_score * 0.6 + artist_score * 0.4) * duration_bonus
    
    return confidence

async def enrich_from_musicbrainz(self, track: Track):
    results = await mb_client.search_recording(track.artist, track.title)
    
    # Find best match above threshold
    best_match = None
    best_confidence = 0.0
    
    for result in results:
        confidence = self._calculate_match_confidence(track, result)
        if confidence > best_confidence and confidence >= 0.75:
            best_confidence = confidence
            best_match = result
    
    if not best_match:
        raise MetadataNotFoundError("No confident match found")
    
    return best_match
```

---

## 🟢 LOW: Interface Stubs Remaining (5)

### Acceptable Interface Placeholders

These are intentional placeholders for future service expansion:

#### 1. Tidal Client Interface (3 methods)
**File:** `infrastructure/integrations/tidal_client.py`

```python
class ITidalClient(Protocol):
    async def search_track(self, query: str) -> list[TrackDTO]: 
        raise NotImplementedError("Tidal integration planned for v2.1")
    
    async def get_track_url(self, track_id: str) -> str:
        raise NotImplementedError("Tidal integration planned for v2.1")
    
    async def authenticate(self, username: str, password: str) -> str:
        raise NotImplementedError("Tidal integration planned for v2.1")
```

**Status:** 🟢 ACCEPTABLE - Tidal integration planned for future release

#### 2. Apple Music Client Interface (2 methods)
**File:** `infrastructure/integrations/apple_music_client.py`

```python
class IAppleMusicClient(Protocol):
    async def search_track(self, query: str) -> list[TrackDTO]:
        raise NotImplementedError("Apple Music integration planned for v2.2")
    
    async def get_track_url(self, track_id: str) -> str:
        raise NotImplementedError("Apple Music integration planned for v2.2")
```

**Status:** 🟢 ACCEPTABLE - Apple Music integration planned for future release

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| **Critical (Fixed)** | 5 | ✅ COMPLETE |
| **Medium (Fixed)** | 4 | ✅ COMPLETE |
| **Low (Interface Stubs)** | 5 | 🟢 ACCEPTABLE |
| **Total Resolved** | 30/35 | **86% Complete** |

**Conclusion:** All critical and medium TODOs resolved. Remaining 5 are intentional interface placeholders for future service integrations (Tidal, Apple Music).

---

## Related Documentation

- [TODO List](./todo.md) - Current roadmap
- [Action Plan](./action-plan.md) - Implementation timeline
- [Changelog](./changelog.md) - Version history
