# Compilation Analysis

> **Version:** 1.0  
> **Status:** ✅ Active  
> **Last Updated:** 2025-12-12  
> **Service:** `src/soulspot/application/services/compilation_analyzer_service.py`

---

## Overview

Der Compilation Analyzer ist ein Post-Scan Service, der Compilation-Alben über **Track Artist Diversity** erkennt. Er läuft NACH dem Library-Scan und erkennt Compilations, die durch explizite Flags (TCMP, cpil) oder Album-Artist-Patterns nicht erkannt wurden.

**Problem:**
- Album ohne TCMP-Flag, Album Artist = "First Track Artist"
- Aber: 10 verschiedene Artists haben Tracks beigetragen!
- → Library Scanner erkennt dies NICHT als Compilation

**Lösung:**
- Analyzer berechnet Track Artist Diversity nach dem Scan
- Markiert Alben mit hoher Diversity als Compilation

---

## Key Features

- **Post-Scan Detection**: Läuft nach Library-Scan für vollständige Track-Daten
- **Lidarr-Compatible**: Implementiert Lidarr's `TrackGroupingService.IsVariousArtists()` Logik
- **Multi-Phase Approach**: 
  - Phase 1: Automatische Diversity Detection (immer aktiv)
  - Phase 2: Batch-Analysis für ganze Bibliothek
  - Phase 3: MusicBrainz Verification für Borderline Cases (50-75% Diversity)
- **Manual Override**: User kann Compilation-Status manuell setzen
- **Statistics**: Library-weite Compilation-Statistiken

---

## Detection Algorithm

### Diversity Calculation

```python
diversity_ratio = unique_artists / total_tracks

# Examples:
# Album mit 12 Tracks, 1 Artist → 1/12 = 8.3% diversity → Regular Album
# Album mit 12 Tracks, 8 Artists → 8/12 = 66.7% diversity → Compilation
# Album mit 12 Tracks, 12 Artists → 12/12 = 100% diversity → Compilation
```

### Thresholds (from Lidarr)

| Diversity | Classification | Confidence |
|-----------|---------------|-----------|
| < 50% | Regular Album | High |
| 50-75% | Borderline (needs verification) | Medium |
| > 75% | Compilation | High |
| 100% | Compilation | Very High |

### Minimum Track Count

```python
MIN_TRACKS_FOR_DIVERSITY = 4  # Albums < 4 tracks not analyzed

# Why? Singles (1-3 tracks) with different artists aren't compilations
# Example: Single with remix → 2 different artists, but not a compilation
```

---

## Use Cases

### 1. Post-Scan Compilation Detection

```python
from soulspot.application.services.compilation_analyzer_service import (
    CompilationAnalyzerService
)

analyzer = CompilationAnalyzerService(session)

# Analyze single album after import
result = await analyzer.analyze_album(album_id="abc123")

if result.changed:
    print(f"Album '{result.album_title}' marked as compilation")
    print(f"Reason: {result.detection_reason}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Track Artists: {result.unique_artists}/{result.track_count}")
```

### 2. Batch Library Analysis

```python
# Analyze ALL undetected albums (≥4 tracks)
results = await analyzer.analyze_all_albums(
    only_undetected=True,  # Skip already-detected compilations
    min_tracks=4           # Minimum track count
)

changed_albums = [r for r in results if r.changed]
print(f"Found {len(changed_albums)} new compilations")

for album in changed_albums:
    print(f"- {album.album_title}: {album.unique_artists} artists, {album.confidence:.0%} confidence")
```

### 3. MusicBrainz Verification (Phase 3)

```python
# Verify borderline albums (50-75% diversity) via MusicBrainz API
analyzer = CompilationAnalyzerService(session, musicbrainz_client=mb_client)

results = await analyzer.verify_borderline_albums(
    diversity_min=0.5,   # 50% diversity
    diversity_max=0.75,  # 75% diversity
    limit=50             # Max 50 albums (rate-limit!)
)

for result in results:
    if result.get('updated'):
        print(f"✅ {result['album_title']}: MB confirmed compilation={result['is_compilation']}")
```

### 4. Manual Override

```python
# User says: "This IS a compilation, trust me!"
success = await analyzer.set_compilation_status(
    album_id="abc123",
    is_compilation=True,
    reason="manual_override_by_user"
)

# Or: "This ISN'T a compilation despite diversity"
success = await analyzer.set_compilation_status(
    album_id="xyz789",
    is_compilation=False,
    reason="user_correction"
)
```

---

## API Integration

### Data Model: AlbumAnalysisResult

```python
@dataclass
class AlbumAnalysisResult:
    album_id: str                    # Album UUID
    album_title: str                 # Album title
    previous_is_compilation: bool    # Status before analysis
    new_is_compilation: bool         # Status after analysis
    detection_reason: str            # Reason (e.g., "high_diversity_75%")
    confidence: float                # Confidence (0.0-1.0)
    track_count: int                 # Total tracks analyzed
    unique_artists: int              # Unique artists detected
    changed: bool                    # True if status changed
    musicbrainz_verified: bool       # True if MB verified
    musicbrainz_mbid: str | None     # MB Release Group ID
```

**JSON Response Example:**
```json
{
  "album_id": "abc-123",
  "album_title": "Now That's What I Call Music! 80",
  "previous_is_compilation": false,
  "new_is_compilation": true,
  "detection_reason": "high_diversity_95%",
  "confidence": 0.95,
  "track_count": 20,
  "unique_artists": 19,
  "changed": true,
  "musicbrainz_verified": false,
  "musicbrainz_mbid": null
}
```

---

## Three-Phase Strategy

### Phase 1: Library Scanner (Immediate)
**When:** During file import  
**Method:** Explicit flags (TCMP, cpil) + Album Artist patterns  
**Coverage:** ~60% of compilations

```python
# In library_scanner.py
if metadata.get('TCMP') == '1' or album_artist == "Various Artists":
    secondary_types.append(SecondaryAlbumType.COMPILATION)
```

### Phase 2: Diversity Analyzer (Post-Scan)
**When:** After library scan completes  
**Method:** Track artist diversity calculation  
**Coverage:** +30% (catches remaining compilations)

```python
# After scan
analyzer = CompilationAnalyzerService(session)
results = await analyzer.analyze_all_albums()
# → Finds compilations missed by Phase 1
```

### Phase 3: MusicBrainz Verification (Borderline)
**When:** For uncertain cases (50-75% diversity)  
**Method:** MusicBrainz API lookup  
**Coverage:** +10% (resolves ambiguous cases)

```python
# For borderline albums
analyzer = CompilationAnalyzerService(session, musicbrainz_client=mb)
results = await analyzer.verify_borderline_albums(
    diversity_min=0.5,
    diversity_max=0.75,
    limit=50
)
# → MusicBrainz gives authoritative answer
```

**Total Coverage:** ~100% ✅

---

## Configuration

### Environment Variables

```bash
# MusicBrainz API (optional, for Phase 3)
MUSICBRAINZ_APP_NAME=SoulSpot
MUSICBRAINZ_APP_VERSION=1.0
MUSICBRAINZ_CONTACT=your@email.com
MUSICBRAINZ_RATE_LIMIT=1.0  # Requests per second
```

### Service Initialization

```python
from sqlalchemy.ext.asyncio import AsyncSession
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient

# Phase 1+2: Basic diversity detection
analyzer = CompilationAnalyzerService(session)

# Phase 1+2+3: With MusicBrainz verification
mb_client = MusicBrainzClient()
analyzer = CompilationAnalyzerService(session, musicbrainz_client=mb_client)
```

---

## Integration Patterns

### With Library Scanner

```python
from soulspot.application.services.library_scanner import LibraryScanner

# Step 1: Scan library
scanner = LibraryScanner(...)
scan_result = await scanner.scan_directory("/music")

# Step 2: Run compilation analysis
analyzer = CompilationAnalyzerService(session)
analysis_results = await analyzer.analyze_all_albums()

print(f"Scan imported {scan_result.albums_count} albums")
print(f"Analysis found {sum(r.changed for r in analysis_results)} new compilations")
```

### As Background Worker

```python
import asyncio

async def periodic_compilation_analysis():
    """Background task: Re-analyze library every 24 hours."""
    while True:
        try:
            analyzer = CompilationAnalyzerService(session)
            results = await analyzer.analyze_all_albums(only_undetected=True)
            logger.info(f"Periodic analysis: {len(results)} albums checked")
        except Exception as e:
            logger.error(f"Periodic analysis failed: {e}")
        
        await asyncio.sleep(86400)  # 24 hours

# Start background task
asyncio.create_task(periodic_compilation_analysis())
```

### With API Endpoint

```python
from fastapi import APIRouter, Depends

router = APIRouter()

@router.post("/api/library/analyze-compilations")
async def analyze_compilations(
    session: AsyncSession = Depends(get_session)
):
    """Trigger compilation analysis for all albums."""
    analyzer = CompilationAnalyzerService(session)
    results = await analyzer.analyze_all_albums()
    
    return {
        "analyzed": len(results),
        "changed": sum(r.changed for r in results),
        "results": [r.to_dict() for r in results]
    }
```

---

## Statistics API

### Library Compilation Stats

```python
stats = await analyzer.get_compilation_stats()

# Returns:
{
    "total_albums": 500,
    "compilation_albums": 45,
    "various_artists_albums": 30,
    "compilation_percent": 9.0
}
```

**Interpretation:**
- **compilation_albums**: Alben mit `COMPILATION` secondary type (alle Detektionsmethoden)
- **various_artists_albums**: Alben mit "Various Artists" Album Artist (Subset von compilations)
- **compilation_percent**: % der Library, die Compilations sind

---

## Edge Cases & Gotchas

### 1. Deluxe Editions with Bonus Remixes
**Problem:** Album hat 12 original tracks (1 artist) + 3 remixes (different artists)  
**Diversity:** 4/15 = 26.7% → NOT a compilation ✅  
**Status:** Correctly classified as regular album

### 2. Multi-Disc Classical Compilations
**Problem:** "Greatest Symphonies" - Disc 1 Beethoven, Disc 2 Mozart, Disc 3 Bach  
**Diversity:** 3/30 = 10% (if tracks assigned to disc composers) → NOT a compilation ❌  
**Workaround:** Phase 3 MusicBrainz verification catches this

### 3. Soundtrack with Featured Artists
**Problem:** "Movie Soundtrack" - Main artist + 5 featured artists  
**Diversity:** 6/12 = 50% → Borderline  
**Solution:** Phase 3 MusicBrainz verification (authoritative answer)

### 4. Live Album with Guest Musicians
**Problem:** "Live at Wembley" - Band + 3 guest performers  
**Diversity:** 4/15 = 26.7% → NOT a compilation ✅  
**Status:** Correctly classified as regular album

### 5. DJ Mix Album
**Problem:** "DJ Mix 2024" - 20 tracks, 20 different artists  
**Diversity:** 20/20 = 100% → Compilation ✅  
**Status:** Correctly detected

---

## Performance Considerations

### Database Queries

```python
# analyze_album(): 3 queries
# - Get album + artist (JOIN)
# - Get track artists (JOIN)
# - Update album (if changed)

# analyze_all_albums(): N+3 queries
# - Get album IDs with track counts (1 query)
# - analyze_album() for each (3N queries)
# - Batch commit (1 query)

# For 100 albums: ~303 queries (~1-2 seconds with indexes)
```

### MusicBrainz Rate Limiting

```python
# MusicBrainz: 1 request/second (strict!)
# verify_borderline_albums(limit=50):
# - 50 albums = 50 seconds minimum
# - Use background task or off-peak hours
# - Consider caching MBID results

# Recommendation: Run during maintenance window
```

### Batch Processing

```python
# Large libraries (>10k albums): Process in batches
async def analyze_in_batches(batch_size=100):
    offset = 0
    while True:
        results = await analyzer.analyze_all_albums_batch(
            offset=offset,
            limit=batch_size
        )
        if not results:
            break
        offset += batch_size
        await asyncio.sleep(1)  # Breathing room for DB
```

---

## Monitoring & Logging

### Log Messages

```python
# Successful detection
logger.info(
    f"Album '{title}' compilation status changed: "
    f"{was_compilation} → {is_compilation} "
    f"(reason: {reason}, confidence: {confidence:.0%})"
)

# Batch analysis complete
logger.info(
    f"Compilation analysis complete: {analyzed} albums analyzed, "
    f"{changed} status changes"
)

# MusicBrainz verification
logger.info(
    f"MusicBrainz verification complete: {verified}/{total} verified, "
    f"{updated} updated"
)
```

### Metrics Tracking

```python
# Track analysis runs
analysis_runs = 0
total_analyzed = 0
total_changed = 0

async def analyze_with_metrics():
    global analysis_runs, total_analyzed, total_changed
    results = await analyzer.analyze_all_albums()
    analysis_runs += 1
    total_analyzed += len(results)
    total_changed += sum(r.changed for r in results)
```

---

## Testing Strategies

### Unit Tests

```python
import pytest

@pytest.mark.asyncio
async def test_high_diversity_detection():
    # Mock album with 20 tracks, 19 different artists
    result = await analyzer.analyze_album("compilation_id")
    
    assert result.new_is_compilation is True
    assert result.detection_reason == "high_diversity_95%"
    assert result.confidence >= 0.9
    assert result.changed is True

@pytest.mark.asyncio
async def test_low_diversity_not_compilation():
    # Mock regular album: 12 tracks, 1 artist
    result = await analyzer.analyze_album("regular_id")
    
    assert result.new_is_compilation is False
    assert result.unique_artists == 1
    assert result.changed is False
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_analysis_cycle(db_session):
    # Create test album with tracks
    album = await create_test_album(
        title="Test Compilation",
        tracks=[
            ("Artist A", "Track 1"),
            ("Artist B", "Track 2"),
            ("Artist C", "Track 3"),
            ("Artist D", "Track 4"),
        ]
    )
    
    # Run analysis
    analyzer = CompilationAnalyzerService(db_session)
    result = await analyzer.analyze_album(album.id)
    
    # Verify: 4 different artists = 100% diversity → compilation
    assert result.new_is_compilation is True
    assert result.unique_artists == 4
    assert result.confidence == 1.0
```

---

## Related Features

- **[Library Management](./library-management.md)** - Library scanner (Phase 1 detection)
- **[Metadata Enrichment](./metadata-enrichment.md)** - MusicBrainz integration
- **[Album Completeness](./album-completeness.md)** - Album analysis utilities

---

## Troubleshooting

### "Changed count is 0"
**Symptom:** Analysis runs but no albums marked as compilation  
**Causes:**
1. All compilations already detected by Phase 1 (good!)
2. Thresholds too strict → Lower `diversity_min`
3. Albums have < 4 tracks → Not analyzed (expected)

### "MusicBrainz verification fails"
**Symptom:** Phase 3 verification returns errors  
**Causes:**
1. Rate-limit exceeded → Reduce `limit` or add delays
2. Client not configured → Pass `musicbrainz_client` to service
3. API timeout → Network issues, retry later

### "False positives (regular albums marked as compilations)"
**Symptom:** Albums incorrectly classified  
**Causes:**
1. Featured artists in track artists → Normalize feat. tags
2. Multi-disc classical albums → Use Phase 3 MB verification
3. User correction needed → Use `set_compilation_status()` override

### "Database update failed"
**Symptom:** Analysis completes but changes not saved  
**Causes:**
1. Missing `await session.commit()` → Check analyzer code
2. DB constraints violation → Check `secondary_types` column
3. Transaction rollback → Check logs for errors

---

**Version:** 1.0 · **Status:** Active · **Service:** `compilation_analyzer_service.py`
