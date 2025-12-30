# Album Completeness

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-12-12  
**Related Docs:** [Library Management](./library-management.md) | [Metadata Enrichment](./metadata-enrichment.md)

---

## Overview

Album Completeness Feature detects incomplete albums in your library by comparing local track count with official tracklist from metadata sources (Spotify, MusicBrainz).

**Example:**
- You have "OK Computer" by Radiohead with 10 tracks
- Official tracklist has 12 tracks
- → Album is **83.3% complete**, tracks 3 and 7 missing

---

## Features

- **Multi-Source Verification:** Uses Spotify and MusicBrainz for maximum coverage
- **Gap Analysis:** Shows exactly which track numbers missing (not just count)
- **Deluxe Edition Detection:** Treats albums with more tracks than expected as "complete"
- **Percentage Calculation:** Clear percentage for UX (e.g. "75% complete")
- **Graceful Degradation:** Works even if only one metadata source available

---

## Use Cases

### Find Incomplete Downloads

After batch import, check which albums missing tracks:

```python
from soulspot.application.services.album_completeness import AlbumCompletenessService

service = AlbumCompletenessService(
    spotify_client=spotify,
    musicbrainz_client=musicbrainz
)

# Check album
result = await service.check_album_completeness(
    album_id="local_album_id_123",
    local_tracks=[1, 2, 3, 5, 6, 7, 9, 10]  # Tracks 4 and 8 missing
)

print(f"Completeness: {result.completeness_percent}%")
print(f"Missing tracks: {result.missing_track_numbers}")
# Output: Completeness: 80.0%
#         Missing tracks: [4, 8]
```

---

### Standard vs Deluxe Edition

If you have Deluxe Edition (15 tracks) but Spotify only knows Standard Edition (12 tracks):

```python
result = await service.check_album_completeness(
    album_id="deluxe_album_id",
    local_tracks=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]  # 15 tracks
)

print(result.is_complete())  # True - more tracks than expected is OK
print(result.expected_track_count)  # 12 (from Spotify)
print(result.actual_track_count)  # 15 (your local collection)
```

---

### Batch Library Analysis

Find all incomplete albums in library:

```python
incomplete_albums = []
for album in my_album_collection:
    result = await service.check_album_completeness(
        album_id=album.id,
        local_tracks=album.track_numbers
    )
    if not result.is_complete():
        incomplete_albums.append(result)

# Sort by completeness (lowest first)
incomplete_albums.sort(key=lambda x: x.completeness_percent)
for album in incomplete_albums:
    print(f"{album.album_title}: {album.completeness_percent}% - {album.missing_track_count} tracks missing")
```

---

## API Integration

### Data Model: AlbumCompletenessInfo

```python
class AlbumCompletenessInfo:
    album_id: str                    # Local album ID
    album_title: str                 # Album title
    artist_name: str                 # Artist name
    expected_track_count: int        # Tracks per metadata source
    actual_track_count: int          # Local track count
    missing_track_numbers: list[int] # Missing track numbers
    source: str                      # Metadata source ("spotify" or "musicbrainz")
    completeness_percent: float      # Completeness percentage

    def is_complete() -> bool:       # True if actual >= expected
    def to_dict() -> dict[str, Any]: # JSON serialization
```

**JSON Response:**
```json
{
  "album_id": "abc123",
  "album_title": "OK Computer",
  "artist_name": "Radiohead",
  "expected_track_count": 12,
  "actual_track_count": 10,
  "missing_track_count": 2,
  "missing_track_numbers": [3, 7],
  "completeness_percent": 83.33,
  "is_complete": false,
  "source": "spotify"
}
```

---

## Multi-Source Strategy

### Spotify (Primary)

**Advantages:**
- Current and mainstream albums (from ~1990)
- Fast API response
- Reliable track numbering

**Disadvantages:**
- Regional availability varies
- Old/obscure albums often missing
- Requires OAuth token

---

### MusicBrainz (Fallback)

**Advantages:**
- Comprehensive catalog (old + obscure)
- No auth required
- Community-maintained accuracy

**Disadvantages:**
- Slower API response
- Rate limits (1/sec)
- Multiple editions complicate matching

---

## Related Documentation

- **[Library Management](./library-management.md)** - Library scan tools
- **[Metadata Enrichment](./metadata-enrichment.md)** - Multi-source metadata

---

**Last Validated:** 2025-12-12  
**Implementation Status:** ✅ Production-ready
