# Compilations API Reference

> **Version:** 2.0  
> **Last Updated:** 9. Dezember 2025  
> **Status:** ✅ Active  
> **Related Router:** `src/soulspot/api/routers/compilations.py`

---

## Overview

The Compilations API provides **automatic compilation detection** for albums in your library. It uses **Lidarr-style heuristics** to identify compilation albums ("Various Artists" albums, soundtracks, tribute albums, etc.) and update metadata accordingly.

**Key Features:**
- 🎯 **3-Tier Detection** - Explicit flags → Album artist patterns → Track diversity analysis
- 🔍 **MusicBrainz Verification** - Authoritative data for borderline cases
- 📊 **Statistics** - Track compilation counts and percentages
- ✏️ **Manual Override** - User can override automatic detection

**Why Compilations Matter:**
- Proper sorting in music libraries (don't clutter artist views with "Various Artists")
- Correct metadata for streaming services (Plex, Jellyfin, Navidrome)
- Better organization in file explorers

---

## Endpoints

### 1. POST `/api/library/compilations/analyze`

**Purpose:** Analyze a **single album** for compilation status.

**Request:**
```json
{
  "album_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "album_id": "550e8400-e29b-41d4-a716-446655440000",
  "album_title": "Now That's What I Call Music! 50",
  "previous_is_compilation": false,
  "new_is_compilation": true,
  "detection_reason": "track_diversity",
  "confidence": 0.95,
  "track_count": 20,
  "unique_artists": 18,
  "changed": true,
  "musicbrainz_verified": false,
  "musicbrainz_mbid": null
}
```

**Detection Reasons:**
- `explicit_flag` - TCMP/cpil tag found (highest confidence)
- `album_artist_pattern` - Matches "Various Artists", "VA", "Diverse Künstler", etc.
- `track_diversity` - ≥75% unique artists OR <25% dominant artist
- `no_dominant_artist` - No single artist has >50% of tracks
- `borderline_diversity` - 50-75% diversity (uncertain, consider MusicBrainz verification)
- `no_indicators` - Not a compilation

**Code Reference:**
```python
# src/soulspot/api/routers/compilations.py (lines 113-135)
@router.post("/analyze")
async def analyze_album(request: AnalyzeAlbumRequest, ...) -> dict[str, Any]:
    """Analyze a single album for compilation status."""
    ...
```

---

### 2. POST `/api/library/compilations/analyze-all`

**Purpose:** Bulk analyze **all albums** in library.

**Query Parameters:**
- `only_undetected` (bool, default: `false`) - Skip albums already marked as compilations
- `min_tracks` (int, default: `2`) - Minimum track count for diversity analysis

**Request:** (empty body)

**Response:**
```json
{
  "analyzed_count": 1234,
  "changed_count": 42,
  "results": [
    {
      "album_id": "...",
      "album_title": "...",
      "changed": true,
      "detection_reason": "track_diversity",
      "confidence": 0.87
    }
  ]
}
```

**Performance Note:**
⚠️ **This can be SLOW for large libraries!** (1000+ albums = 10-30 seconds). Consider running as background task via workers API.

**Code Reference:**
```python
# src/soulspot/api/routers/compilations.py (lines 138-168)
@router.post("/analyze-all")
async def analyze_all_albums(
    only_undetected: bool = False,
    min_tracks: int = 2,
    ...) -> dict[str, Any]:
    """Analyze all albums for compilation status."""
    ...
```

---

### 3. GET `/api/library/compilations/stats`

**Purpose:** Get compilation statistics for library.

**Request:** None

**Response:**
```json
{
  "total_albums": 1234,
  "compilation_albums": 42,
  "various_artists_albums": 18,
  "compilation_percent": 3.4
}
```

**Use Cases:**
- Dashboard widgets ("You have 42 compilations")
- Library health checks
- Post-analysis summaries

**Code Reference:**
```python
# src/soulspot/api/routers/compilations.py (lines 171-182)
@router.get("/stats")
async def get_compilation_stats(...) -> dict[str, Any]:
    """Get statistics about compilations in the library."""
    ...
```

---

### 4. POST `/api/library/compilations/set-status`

**Purpose:** Manually override compilation status.

**Request:**
```json
{
  "album_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_compilation": true,
  "reason": "User confirmed: This is a soundtrack compilation"
}
```

**Response:**
```json
{
  "success": true,
  "album_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_compilation": true,
  "reason": "User confirmed: This is a soundtrack compilation"
}
```

**Use Cases:**
- Fix false positives (automatic detection marked as compilation, but it's not)
- Fix false negatives (album IS compilation, but not detected)
- Store audit trail (reason field)

**Code Reference:**
```python
# src/soulspot/api/routers/compilations.py (lines 185-207)
@router.post("/set-status")
async def set_compilation_status(request: SetCompilationRequest, ...) -> dict[str, Any]:
    """Manually set compilation status for an album."""
    ...
```

---

### 5. POST `/api/library/compilations/verify-musicbrainz`

**Purpose:** Verify compilation status via **MusicBrainz API** (authoritative source).

**Request:**
```json
{
  "album_id": "550e8400-e29b-41d4-a716-446655440000",
  "update_if_confirmed": true
}
```

**Response:**
```json
{
  "album_id": "550e8400-e29b-41d4-a716-446655440000",
  "verified": true,
  "is_compilation": true,
  "musicbrainz_mbid": "6b9b8e1e-...",
  "detection_reason": "mb_compilation_type",
  "updated": true
}
```

**Rate Limits:**
⚠️ **MusicBrainz has strict rate limits: 1 request/second!** Don't call this in loops. Use `/verify-borderline` for bulk verification.

**Code Reference:**
```python
# src/soulspot/api/routers/compilations.py (lines 210-232)
@router.post("/verify-musicbrainz")
async def verify_with_musicbrainz(request: VerifyMusicBrainzRequest, ...) -> dict[str, Any]:
    """Verify compilation status via MusicBrainz API."""
    ...
```

---

### 6. POST `/api/library/compilations/verify-borderline`

**Purpose:** Bulk verify **borderline albums** (50-75% diversity) via MusicBrainz.

**Query Parameters:**
- `limit` (int, default: `20`, range: 1-100) - Max albums to verify

**Request:** (empty body)

**Response:**
```json
{
  "verified_count": 12,
  "updated_count": 8,
  "results": [
    {
      "album_id": "...",
      "album_title": "...",
      "verified": true,
      "is_compilation": true,
      "musicbrainz_mbid": "...",
      "updated": true
    }
  ]
}
```

**Performance Note:**
⚠️ **This is VERY SLOW!** (20 albums = ~20 seconds minimum due to 1 req/sec rate limit). Run as background task!

**Code Reference:**
```python
# src/soulspot/api/routers/compilations.py (lines 235-257)
@router.post("/verify-borderline")
async def verify_borderline_albums(limit: int = 20, ...) -> dict[str, Any]:
    """Verify borderline albums via MusicBrainz in bulk."""
    ...
```

---

### 7. GET `/api/library/compilations/{album_id}/detection-info`

**Purpose:** Get **detailed detection info** for UI display.

**Request:** None (album ID in path)

**Response:**
```json
{
  "album_id": "550e8400-e29b-41d4-a716-446655440000",
  "album_title": "Now That's What I Call Music! 50",
  "is_compilation": true,
  "detection_reason": "track_diversity",
  "confidence": 0.95,
  "track_count": 20,
  "unique_artists": 18,
  "diversity_ratio": 0.90,
  "explanation": "High track artist diversity detected: 18 unique artists across 20 tracks (90% diversity). Threshold is 75%."
}
```

**Use Cases:**
- Album detail pages ("Why is this marked as compilation?")
- Tooltips in library views
- Debugging detection issues

**Explanation Field:**
Human-readable reason for detection result. Examples:
- `"Detected via explicit compilation flag (TCMP/cpil tag) in audio files. This is the most reliable indicator."`
- `"High track artist diversity detected: 18 unique artists across 20 tracks (90% diversity). Threshold is 75%."`
- `"Verified via MusicBrainz: Album has 'Compilation' secondary type."`

**Code Reference:**
```python
# src/soulspot/api/routers/compilations.py (lines 264-291)
@router.get("/{album_id}/detection-info")
async def get_detection_info(album_id: str, ...) -> dict[str, Any]:
    """Get detailed compilation detection info for an album."""
    ...
```

---

## Detection Logic (Lidarr-Style Heuristics)

**3-Tier Detection System:**

```python
# Tier 1: Explicit Flags (highest confidence)
if track.has_compilation_flag():  # TCMP=1 or cpil=1
    return True, "explicit_flag", confidence=1.0

# Tier 2: Album Artist Pattern Matching
if album.artist in ["Various Artists", "VA", "Diverse Künstler", "Varios Artistas"]:
    return True, "album_artist_pattern", confidence=0.95

# Tier 3: Track Artist Diversity Analysis
diversity_ratio = unique_artists / total_tracks

if diversity_ratio >= 0.75:  # 75%+ unique artists
    return True, "track_diversity", confidence=0.90
elif diversity_ratio < 0.25:  # <25% diversity (single artist dominates)
    return False, "dominant_artist", confidence=0.85
elif 0.50 <= diversity_ratio < 0.75:  # 50-75% (borderline)
    return None, "borderline_diversity", confidence=0.60  # Consider MusicBrainz verification
else:
    return False, "no_indicators", confidence=0.50
```

**Pattern Matching (Tier 2):**
Matches album artists like:
- `"Various Artists"` (exact match)
- `"V.A."`, `"VA"`, `"V/A"` (abbreviations)
- `"Diverse Künstler"` (German)
- `"Varios Artistas"` (Spanish)
- `"Various"`, `"Compilation"`, `"Unknown Artist"` (case-insensitive)

---

## Workflow Example

```python
import httpx

async def process_library_compilations():
    async with httpx.AsyncClient() as client:
        base_url = "http://localhost:8000/api/library/compilations"
        
        # 1. Get initial statistics
        stats = await client.get(f"{base_url}/stats")
        print(f"Before: {stats.json()['compilation_albums']} compilations")
        
        # 2. Analyze all albums
        result = await client.post(
            f"{base_url}/analyze-all",
            params={"only_undetected": True, "min_tracks": 3}
        )
        print(f"Analyzed {result.json()['analyzed_count']} albums")
        print(f"Changed {result.json()['changed_count']} albums")
        
        # 3. Verify borderline cases via MusicBrainz
        borderline = await client.post(
            f"{base_url}/verify-borderline",
            params={"limit": 10}
        )
        print(f"Verified {borderline.json()['verified_count']} albums via MusicBrainz")
        
        # 4. Get updated statistics
        stats = await client.get(f"{base_url}/stats")
        print(f"After: {stats.json()['compilation_albums']} compilations")
        
        # 5. Manual override (fix false positive)
        await client.post(
            f"{base_url}/set-status",
            json={
                "album_id": "abc123...",
                "is_compilation": False,
                "reason": "This is a single-artist album, NOT a compilation"
            }
        )
```

---

## Summary

**7 Endpoints** for compilation detection:

| Endpoint | Method | Purpose | Performance |
|----------|--------|---------|-------------|
| `/compilations/analyze` | POST | Analyze single album | Fast (<100ms) |
| `/compilations/analyze-all` | POST | Analyze all albums | Slow (10-30s for 1000 albums) |
| `/compilations/stats` | GET | Get compilation statistics | Fast (<50ms) |
| `/compilations/set-status` | POST | Manual override | Fast (<100ms) |
| `/compilations/verify-musicbrainz` | POST | Verify via MusicBrainz | 1-2s (rate limited) |
| `/compilations/verify-borderline` | POST | Bulk MusicBrainz verification | Very slow (1s per album) |
| `/compilations/{id}/detection-info` | GET | Get detection details | Fast (<100ms) |

**Best Practices:**
- ✅ Use `/analyze-all` after library scans (as background task)
- ✅ Use `/verify-borderline` for confident results (run overnight)
- ✅ Use `/set-status` for user corrections (store reason)
- ❌ Don't call `/verify-musicbrainz` in loops (rate limits!)
- ❌ Don't run `/analyze-all` on every request (cache results)
