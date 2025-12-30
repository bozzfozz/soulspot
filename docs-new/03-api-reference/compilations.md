# Compilations API

**Base Path**: `/library/compilations`

**Purpose**: Compilation album detection and management using Lidarr-style heuristics. Analyzes albums for compilation characteristics (multiple artists, "Various Artists" patterns, explicit flags) with optional MusicBrainz verification.

**Critical Context**: Compilation detection uses 3-tier heuristics: explicit flags (TCMP/cpil tags) → album artist patterns → track diversity analysis. MusicBrainz verification available for borderline cases (rate-limited to 1 req/sec).

---

## Endpoints Overview (7 endpoints)

- `POST /library/compilations/analyze` - Analyze single album
- `POST /library/compilations/analyze-all` - Bulk analyze all albums
- `GET /library/compilations/stats` - Get compilation statistics
- `POST /library/compilations/set-status` - Manual compilation status override
- `POST /library/compilations/verify-musicbrainz` - Verify single album via MusicBrainz
- `POST /library/compilations/verify-borderline` - Bulk verify uncertain albums
- `GET /library/compilations/{album_id}/detection-info` - Get detailed detection info for UI

---

## Detection Heuristics

### Lidarr-Style 3-Tier Approach

**Tier 1: Explicit Compilation Flags** (Highest Confidence)
- TCMP/cpil tags in audio file metadata
- Most reliable indicator - always trusted

**Tier 2: Album Artist Pattern Matching**
- Matches "Various Artists", "VA", "V/A", "V.A.", "Diverse Künstler", etc.
- Language-aware patterns (English, German, etc.)

**Tier 3: Track Artist Diversity**
- **≥75% unique artists**: Likely compilation
- **<25% dominant artist**: No single artist dominates
- **50-75% diversity**: Borderline - recommend MusicBrainz verification

**Example**:
```
Album: "Now That's What I Call Music 95"
Tracks: 20
Unique Artists: 18
Diversity: 90% (18/20) → COMPILATION
```

---

## Endpoints

### 1. Analyze Single Album

**Endpoint**: `POST /library/compilations/analyze`

**Purpose**: Analyze one album for compilation status using heuristics.

**Request Body**:
```json
{
  "album_id": "uuid-v4"
}
```

**Response**:
```json
{
  "album_id": "uuid-v4",
  "album_title": "Now That's What I Call Music 95",
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

**Detection Reasons**:
- `explicit_flag`: TCMP/cpil tag found (confidence: 1.0)
- `album_artist_pattern`: Album artist matches "Various Artists" pattern (confidence: 0.9-1.0)
- `track_diversity`: ≥75% unique artists (confidence: varies)
- `no_dominant_artist`: <25% artist dominance (confidence: varies)
- `borderline_diversity`: 50-75% diversity (recommend MusicBrainz check)
- `no_indicators`: No compilation indicators (confidence: 0.9)
- `mb_various_artists`: MusicBrainz MBID is Various Artists (confidence: 1.0)
- `mb_compilation_type`: MusicBrainz secondary type = Compilation (confidence: 1.0)
- `mb_not_compilation`: MusicBrainz confirms NOT compilation (confidence: 1.0)
- `manual_override`: User-set status

**Source**: `compilations.py:111-129`

---

### 2. Bulk Analyze All Albums

**Endpoint**: `POST /library/compilations/analyze-all?only_undetected=false&min_tracks=2`

**Purpose**: Analyze all albums in library (use after library scan or as periodic cleanup).

**Query Parameters**:
- `only_undetected` (bool, default false): If true, skip albums already marked as compilations
- `min_tracks` (int, default 2, range 2-∞): Minimum track count for diversity analysis

**WARNING**: Can be slow for large libraries (1000+ albums). Consider running as background job.

**Response**:
```json
{
  "analyzed_count": 250,
  "changed_count": 42,
  "results": [
    {
      "album_id": "uuid-v4",
      "album_title": "...",
      "previous_is_compilation": false,
      "new_is_compilation": true,
      "detection_reason": "track_diversity",
      "confidence": 0.85,
      "track_count": 15,
      "unique_artists": 12,
      "changed": true
    }
  ]
}
```

**Note**: Default `only_undetected=false` for HTMX compatibility (analyzes all albums every time).

**Source**: `compilations.py:132-159`

---

### 3. Get Compilation Statistics

**Endpoint**: `GET /library/compilations/stats`

**Purpose**: Retrieve counts and percentages of compilation albums in library.

**Response**:
```json
{
  "total_albums": 500,
  "compilation_albums": 75,
  "various_artists_albums": 60,
  "compilation_percent": 15.0
}
```

**Fields**:
- `total_albums`: Total album count in library
- `compilation_albums`: Albums marked as compilations
- `various_artists_albums`: Subset with "Various Artists" album artist
- `compilation_percent`: Percentage of compilations (compilation_albums / total_albums × 100)

**Source**: `compilations.py:162-173`

---

### 4. Manual Compilation Status Override

**Endpoint**: `POST /library/compilations/set-status`

**Purpose**: Manually override compilation status when automatic detection is wrong.

**Request Body**:
```json
{
  "album_id": "uuid-v4",
  "is_compilation": true,
  "reason": "manual_override"
}
```

**Parameters**:
- `album_id` (string, required): UUID of album
- `is_compilation` (boolean, required): True = mark as compilation
- `reason` (string, default "manual_override"): Reason for override (audit trail)

**Response**:
```json
{
  "success": true,
  "album_id": "uuid-v4",
  "is_compilation": true,
  "reason": "manual_override"
}
```

**Use Cases**:
- Album has unusual artist names → heuristics fail → user corrects
- Album is compilation but low diversity (all tracks by featured artists)
- Album is NOT compilation but has high diversity (live album with guest performers)

**Source**: `compilations.py:176-200`

---

### 5. Verify with MusicBrainz

**Endpoint**: `POST /library/compilations/verify-musicbrainz`

**Purpose**: Verify compilation status via MusicBrainz API for single album.

**Request Body**:
```json
{
  "album_id": "uuid-v4",
  "update_if_confirmed": true
}
```

**Parameters**:
- `album_id` (string, required): UUID of album
- `update_if_confirmed` (bool, default true): Update database if MusicBrainz gives confident answer

**Response**:
```json
{
  "verified": true,
  "mbid": "12345678-1234-1234-1234-123456789012",
  "is_compilation": true,
  "detection_reason": "mb_compilation_type",
  "updated": true
}
```

**MusicBrainz Indicators**:
1. **MBID is Various Artists** → Compilation (confidence 1.0)
2. **Secondary type = "Compilation"** → Compilation (confidence 1.0)
3. **Neither condition met** → NOT compilation (confidence 1.0)

**Rate Limiting**: MusicBrainz enforces strict 1 req/sec limit. **Do NOT** call this in rapid succession for many albums.

**Source**: `compilations.py:203-225`

---

### 6. Verify Borderline Albums

**Endpoint**: `POST /library/compilations/verify-borderline?limit=20`

**Purpose**: Bulk verify albums where local heuristics are uncertain (50-75% diversity).

**Query Parameters**:
- `limit` (int, default 20, range 1-100): Max albums to verify

**Response**:
```json
{
  "verified_count": 18,
  "updated_count": 12,
  "results": [
    {
      "album_id": "uuid-v4",
      "album_title": "Best of 2024",
      "verified": true,
      "mbid": "...",
      "is_compilation": true,
      "detection_reason": "mb_compilation_type",
      "updated": true
    }
  ]
}
```

**WARNING**: This is **SLOW** due to MusicBrainz rate limits (1 req/sec). With `limit=20`, expect ~20 seconds minimum. **Run as background task!**

**Borderline Detection**:
- Albums with 50-75% artist diversity
- Albums with unclear album artist patterns
- Albums flagged as uncertain by local heuristics

**Source**: `compilations.py:228-248`

---

### 7. Get Detection Info

**Endpoint**: `GET /library/compilations/{album_id}/detection-info`

**Purpose**: Get detailed compilation detection info for UI (shows WHY album was/wasn't detected).

**Response**:
```json
{
  "album_id": "uuid-v4",
  "album_title": "Now That's What I Call Music 95",
  "is_compilation": true,
  "detection_reason": "track_diversity",
  "confidence": 0.95,
  "track_count": 20,
  "unique_artists": 18,
  "diversity_ratio": 0.9,
  "explanation": "High track artist diversity detected: 18 unique artists across 20 tracks (90% diversity). Threshold is 75%."
}
```

**Explanation Formats**:
- **explicit_flag**: "Detected via explicit compilation flag (TCMP/cpil tag) in audio files. This is the most reliable indicator."
- **album_artist_pattern**: "Album artist matches 'Various Artists' pattern. Confidence: 95%"
- **track_diversity**: "High track artist diversity detected: 18 unique artists across 20 tracks (90% diversity). Threshold is 75%."
- **borderline_diversity**: "Borderline diversity (65%). Local heuristics uncertain - consider MusicBrainz verification."
- **mb_compilation_type**: "Verified via MusicBrainz: Album has 'Compilation' secondary type."
- **manual_override**: "Compilation status was manually set by user."

**Source**: `compilations.py:256-292`

---

## Architecture Notes

### Lidarr Compatibility

**Design Goal**: Match Lidarr's compilation detection behavior for consistent music library organization.

**Key Heuristics from Lidarr**:
1. Explicit flags (TCMP/cpil) - always trusted
2. "Various Artists" pattern matching - high confidence
3. Track diversity ≥75% - medium confidence
4. No dominant artist (<25%) - medium confidence

**Divergence**: SoulSpot adds MusicBrainz verification for borderline cases (not in Lidarr).

---

### MusicBrainz Integration

**Rate Limiting**:
- MusicBrainz enforces **1 request per second**
- Violating this results in 503 errors + potential IP ban
- Bulk operations (`verify-borderline`) sleep between requests

**Authentication**: None required (public API).

**Reliability**:
- MusicBrainz data is authoritative (human-curated)
- Confidence: 1.0 for all MusicBrainz results
- Fallback: If MBID not found → local heuristics prevail

---

### Background Job Recommendations

**Slow Operations**:
- `POST /analyze-all` - O(N albums × track_count)
- `POST /verify-borderline` - O(N albums) × 1 sec/album

**Solution**: Convert to background tasks with progress tracking.

**Implementation**:
```python
# FastAPI BackgroundTasks
@router.post("/analyze-all-async")
async def analyze_all_async(background_tasks: BackgroundTasks):
    background_tasks.add_task(analyzer.analyze_all_albums)
    return {"status": "started", "job_id": "..."}
```

---

## Performance Considerations

### Bulk Analysis Optimization

**Current**: Sequential analysis with DB commit per album.

**Optimization**:
- Batch DB updates (commit every 100 albums)
- Parallel processing (thread pool for CPU-bound diversity calc)
- Progress webhooks for UI feedback

---

### Diversity Calculation Caching

**Issue**: Re-analyzing same album recalculates diversity from scratch.

**Solution**: Cache diversity ratio in `albums` table (computed column or trigger).

---

## Common Pitfalls

### 1. MusicBrainz Rate Limit Violations

**Wrong**:
```python
for album in albums:
    await verify_with_musicbrainz(album.id)  # Instant 503 errors!
```

**Right**:
```python
for album in albums:
    await verify_with_musicbrainz(album.id)
    await asyncio.sleep(1)  # Respect 1 req/sec limit
```

---

### 2. Zero Track Albums

**Issue**: Album has 0 tracks → division by zero in diversity calculation.

**Solution**:
```python
diversity_percent = (
    round(result.unique_artists / result.track_count * 100)
    if result.track_count > 0
    else 0
)
```

**Source**: `compilations.py:295-299`

---

### 3. Ignoring Borderline Cases

**Wrong Flow**:
```
Analyze all albums → 50-75% diversity → Mark NOT compilation → User confused
```

**Right Flow**:
```
Analyze all albums → 50-75% diversity → Flag as borderline → Run MusicBrainz verification
```

---

### 4. Manual Override Without Audit Trail

**Wrong**:
```python
album.is_compilation = True  # No record of WHY this was changed
```

**Right**:
```python
await set_compilation_status(
    album_id=album.id,
    is_compilation=True,
    reason="User corrected: Album has many featured artists, not compilation"
)
```

---

## UI Integration

### Detection Info Display

**Recommended UI**:
```
Album: "Now That's What I Call Music 95"
Status: ✅ Compilation

Detection Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reason: High track artist diversity
Confidence: 95%
Details: 18 unique artists across 20 tracks (90% diversity)

[Override Status] [Verify with MusicBrainz]
```

**Call**: `GET /library/compilations/{album_id}/detection-info`

---

### Bulk Analysis Progress

**Recommended Flow**:
1. User clicks "Analyze All Compilations"
2. Frontend calls `POST /analyze-all` (or async variant)
3. Show progress bar (if using background task with webhooks)
4. Display results: "42 albums updated as compilations"

---

## Testing Recommendations

### Unit Tests

**Mock Points**:
- `CompilationAnalyzerService` - mock album/track queries
- `MusicBrainzClient` - mock API responses

**Test Cases**:
- Explicit flag detection (TCMP tag present)
- "Various Artists" pattern matching
- Diversity ≥75% → compilation
- Diversity 50-75% → borderline
- Diversity <50% → NOT compilation
- MusicBrainz MBID = Various Artists → compilation
- Zero tracks → no crash

---

### Integration Tests

**Scenarios**:
- Bulk analyze 1000 albums (performance test)
- MusicBrainz verify borderline albums (rate limit test)
- Manual override + re-analyze (override persists)
- Album with 0 tracks (edge case)

---

## Related Documentation

- **Services**: `CompilationAnalyzerService` (`src/soulspot/application/services/compilation_analyzer_service.py`)
- **MusicBrainz Integration**: `docs/architecture/EXTERNAL_INTEGRATIONS.md`
- **Library Management**: `docs-new/03-api-reference/library.md`
- **Background Workers**: `docs/architecture/BACKGROUND_WORKERS.md`

---

**Validation Status**: ✅ All 7 endpoints validated against source code (315 lines analyzed)
