# Compilation Analysis

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-12-12  
**Related Docs:** [Local Library Enrichment](./local-library-enrichment.md) | [Library Management](./library-management.md)

---

## Overview

Compilation Analyzer is a post-scan service that detects compilation albums via **Track Artist Diversity**. Runs AFTER library scan and identifies compilations not detected by explicit flags (TCMP, cpil) or album artist patterns.

**Problem:**
- Album without TCMP flag, Album Artist = "First Track Artist"
- But: 10 different artists contributed tracks!
- → Library Scanner does NOT detect as compilation

**Solution:**
- Analyzer calculates Track Artist Diversity after scan
- Marks albums with high diversity as compilation

---

## Features

- **Post-Scan Detection:** Runs after library scan for complete track data
- **Lidarr-Compatible:** Implements Lidarr's `TrackGroupingService.IsVariousArtists()` logic
- **Multi-Phase Approach:**
  - Phase 1: Automatic Diversity Detection (always active)
  - Phase 2: Batch-Analysis for entire library
  - Phase 3: MusicBrainz Verification for Borderline Cases (50-75% diversity)
- **Manual Override:** User can manually set compilation status
- **Statistics:** Library-wide compilation statistics

---

## Detection Algorithm

### Diversity Calculation

```python
diversity_ratio = unique_artists / total_tracks

# Examples:
# Album with 12 tracks, 1 artist → 1/12 = 8.3% diversity → Regular Album
# Album with 12 tracks, 8 artists → 8/12 = 66.7% diversity → Compilation
# Album with 12 tracks, 12 artists → 12/12 = 100% diversity → Compilation
```

---

### Thresholds (from Lidarr)

| Diversity | Classification | Confidence |
|-----------|---------------|-----------|
| < 50% | Regular Album | High |
| 50-75% | Borderline (needs verification) | Medium |
| > 75% | Compilation | High |
| 100% | Compilation | Very High |

---

### Minimum Track Count

```python
MIN_TRACKS_FOR_DIVERSITY = 4  # Albums < 4 tracks not analyzed

# Why? Singles (1-3 tracks) with different artists aren't compilations
# Example: Single with remix → 2 different artists, but not a compilation
```

---

## Use Cases

### Post-Scan Compilation Detection

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

---

### Batch Library Analysis

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

---

### MusicBrainz Verification (Phase 3)

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

---

### Manual Override

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

## Data Model: AlbumAnalysisResult

```python
@dataclass
class AlbumAnalysisResult:
    album_id: str           # Local album ID
    album_title: str        # Album title
    artist_name: str        # Album artist name
    track_count: int        # Total tracks
    unique_artists: int     # Unique track artists
    diversity_ratio: float  # unique_artists / track_count
    confidence: float       # Detection confidence (0.0-1.0)
    is_compilation: bool    # Detected as compilation?
    detection_reason: str   # Why detected/not detected
    changed: bool           # Album status changed?
```

---

## Related Documentation

- **[Local Library Enrichment](./local-library-enrichment.md)** - Various Artists detection
- **[Library Management](./library-management.md)** - Library scan tools

---

**Last Validated:** 2025-12-12  
**Implementation Status:** ✅ Production-ready
