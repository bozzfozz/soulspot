# Metadata API Reference

> **Version:** 2.0  
> **Last Updated:** 9. Dezember 2025  
> **Status:** ✅ Active  
> **Related Router:** `src/soulspot/api/routers/metadata.py`  
> **Related Service:** `src/soulspot/application/services/metadata_merger.py`

---

## Overview

The Metadata API provides **multi-source metadata enrichment** and **conflict resolution** for tracks, artists, and albums. It intelligently merges data from **Spotify**, **MusicBrainz**, and **Last.fm** using a configurable authority hierarchy.

**Key Features:**
- 🔍 **Multi-Source Enrichment** - Fetch metadata from 3 external services simultaneously
- 🏆 **Authority Hierarchy** - Manual > MusicBrainz > Spotify > Last.fm (configurable)
- ⚔️ **Conflict Detection** - Identifies discrepancies between sources
- ✅ **Manual Resolution** - Override with custom values or select preferred source
- 🏷️ **Tag Normalization** - Standardize "feat./ft./featuring" formats
- 🛠️ **Auto-Fix** - One-click metadata correction for tracks

**Use Cases:**
- Enrich incomplete metadata (missing ISRC, release dates, genres)
- Resolve conflicts when sources disagree (e.g., different release years)
- Normalize artist names (remove duplicate "feat." variations)
- Bulk metadata improvement for imported tracks

---

## Endpoints

### 1. POST `/api/metadata/enrich`

**Purpose:** Enrich track metadata from multiple sources (Spotify, MusicBrainz, Last.fm).

**Request Body:**
```json
{
  "track_id": "770e8400-e29b-41d4-a716-446655440001",
  "force_refresh": false,
  "enrich_artist": true,
  "enrich_album": true,
  "use_spotify": true,
  "use_musicbrainz": true,
  "use_lastfm": true,
  "manual_overrides": {
    "genre": "Progressive Rock",
    "release_date": "1975-09-12"
  }
}
```

**Request Schema:**
```python
class EnrichMetadataMultiSourceRequest(BaseModel):
    track_id: str                         # Track UUID
    force_refresh: bool = False           # Bypass cache, re-fetch from APIs
    enrich_artist: bool = True            # Also enrich related artist metadata
    enrich_album: bool = True             # Also enrich related album metadata
    use_spotify: bool = True              # Enable Spotify as source
    use_musicbrainz: bool = True          # Enable MusicBrainz as source
    use_lastfm: bool = True               # Enable Last.fm as source (optional)
    manual_overrides: dict[str, Any] = {} # User-provided overrides (highest priority)
```

**Response:**
```json
{
  "track_id": "770e8400-e29b-41d4-a716-446655440001",
  "enriched_fields": [
    "isrc",
    "release_date",
    "genre",
    "album_art_url"
  ],
  "sources_used": [
    "MUSICBRAINZ",
    "SPOTIFY",
    "LASTFM"
  ],
  "conflicts": [
    {
      "field_name": "release_date",
      "current_value": "1975-09-12",
      "current_source": "MUSICBRAINZ",
      "conflicting_values": {
        "SPOTIFY": "1975-09-15",
        "LASTFM": "1975-09-10"
      }
    }
  ],
  "errors": []
}
```

**Authority Hierarchy (Conflict Resolution):**
1. **MANUAL** - User-provided overrides (highest priority)
2. **MUSICBRAINZ** - Official metadata database
3. **SPOTIFY** - Streaming service data
4. **LASTFM** - Community-contributed data (lowest priority)

**Behavior:**
- Fetches metadata from **all enabled sources** in parallel
- Merges results using **authority hierarchy** (higher priority wins)
- Detects **conflicts** when sources disagree on field values
- Enriches **related entities** (artist, album) if flags enabled
- Skips API calls if `force_refresh=False` and data cached

**Errors:**
- `404 Not Found` - Track not found in database
- `500 Internal Server Error` - External API error or network failure

**Code Reference:**
```python
# src/soulspot/api/routers/metadata.py (lines 90-187)
@router.post("/enrich", response_model=MetadataEnrichmentResponse)
async def enrich_metadata(
    request: EnrichMetadataMultiSourceRequest,
    use_case: EnrichMetadataMultiSourceUseCase = Depends(get_enrich_use_case),
) -> MetadataEnrichmentResponse:
    """Enrich track metadata from multiple sources."""
    ...
```

---

### 2. POST `/api/metadata/resolve-conflict`

**Purpose:** Manually resolve a metadata conflict by selecting a source or providing custom value.

**Request Body (Select Source):**
```json
{
  "track_id": "770e8400-e29b-41d4-a716-446655440001",
  "field_name": "release_date",
  "selected_source": "MUSICBRAINZ"
}
```

**Request Body (Custom Value):**
```json
{
  "track_id": "770e8400-e29b-41d4-a716-446655440001",
  "field_name": "release_date",
  "selected_source": "MANUAL",
  "custom_value": "1975-09-12"
}
```

**Request Schema:**
```python
class ResolveConflictRequest(BaseModel):
    track_id: str | None = None          # Track UUID (mutually exclusive with artist_id/album_id)
    artist_id: str | None = None         # Artist UUID
    album_id: str | None = None          # Album UUID
    field_name: str                      # Field to resolve (e.g., "release_date", "genre")
    selected_source: MetadataSourceEnum  # MANUAL | MUSICBRAINZ | SPOTIFY | LASTFM
    custom_value: Any | None = None      # Custom value (required if selected_source=MANUAL)
```

**Response:**
```json
{
  "message": "Conflict resolved successfully",
  "entity_type": "track",
  "field_name": "release_date",
  "selected_source": "MUSICBRAINZ"
}
```

**Behavior:**
- Updates entity with selected source's value OR custom value
- Marks `metadata_sources[field_name]` to prevent future conflicts
- Supports **tracks, artists, albums** (via different ID fields)

**Errors:**
- `400 Bad Request` - Missing track_id/artist_id/album_id (must provide exactly one)
- `404 Not Found` - Entity not found in database
- `500 Internal Server Error` - Database update failure

**Code Reference:**
```python
# src/soulspot/api/routers/metadata.py (lines 189-287)
@router.post("/resolve-conflict")
async def resolve_conflict(
    request: ResolveConflictRequest,
    track_repository: TrackRepository = Depends(get_track_repository),
    artist_repository: ArtistRepository = Depends(get_artist_repository),
    album_repository: AlbumRepository = Depends(get_album_repository),
) -> dict[str, Any]:
    """Resolve a metadata conflict by selecting a source or providing custom value."""
    ...
```

---

### 3. POST `/api/metadata/normalize-tags`

**Purpose:** Normalize artist/track names (standardize "feat./ft./featuring" formats).

**Request Body:**
```json
[
  "Pink Floyd feat. David Gilmour",
  "Radiohead ft. Thom Yorke",
  "The Beatles featuring Paul McCartney"
]
```

**Response:**
```json
[
  {
    "original": "Pink Floyd feat. David Gilmour",
    "normalized": "Pink Floyd (feat. David Gilmour)",
    "changed": true
  },
  {
    "original": "Radiohead ft. Thom Yorke",
    "normalized": "Radiohead (feat. Thom Yorke)",
    "changed": true
  },
  {
    "original": "The Beatles featuring Paul McCartney",
    "normalized": "The Beatles (feat. Paul McCartney)",
    "changed": true
  }
]
```

**Behavior:**
- Applies normalization rules:
  - `feat.` → `(feat. ...)`
  - `ft.` → `(feat. ...)`
  - `featuring` → `(feat. ...)`
- Returns **original**, **normalized**, **changed** for each tag
- Useful for cleaning up inconsistent metadata

**Use Cases:**
- De-duplicate artists with different "feat." formats
- Standardize imported metadata before saving
- Preview normalization results in UI

**Code Reference:**
```python
# src/soulspot/api/routers/metadata.py (lines 289-321)
@router.post("/normalize-tags", response_model=list[TagNormalizationResult])
async def normalize_tags(
    tags: list[str],
    metadata_merger: MetadataMerger = Depends(get_metadata_merger),
) -> list[TagNormalizationResult]:
    """Normalize a list of tags/artist names."""
    ...
```

---

### 4. GET `/api/metadata/sources/hierarchy`

**Purpose:** Get configured metadata source authority hierarchy.

**Request:** None

**Response:**
```json
{
  "MANUAL": 0,
  "MUSICBRAINZ": 1,
  "SPOTIFY": 2,
  "LASTFM": 3
}
```

**Explanation:**
- **Lower value = Higher priority** (0 is highest)
- **MANUAL** (0) - User overrides always win
- **MUSICBRAINZ** (1) - Official database (most accurate)
- **SPOTIFY** (2) - Streaming service data
- **LASTFM** (3) - Community data (least trusted)

**Use Cases:**
- Display hierarchy in UI settings
- Understand conflict resolution behavior
- Debugging metadata merge issues

**Code Reference:**
```python
# src/soulspot/api/routers/metadata.py (lines 323-347)
@router.get("/sources/hierarchy")
async def get_source_hierarchy() -> dict[str, int]:
    """Get the metadata source authority hierarchy."""
    return {
        source.value: priority
        for source, priority in MetadataMerger.AUTHORITY_HIERARCHY.items()
    }
```

---

### 5. POST `/api/metadata/{track_id}/auto-fix`

**Purpose:** Auto-fix track metadata issues by enriching from all external sources.

**Path Parameters:**
- `track_id` *(string, UUID)* - Track UUID

**Request:** None

**Response:**
```json
{
  "track_id": "770e8400-e29b-41d4-a716-446655440001",
  "success": true,
  "enriched_fields": [
    "isrc",
    "release_date",
    "genre",
    "album_art_url"
  ],
  "sources_used": [
    "MUSICBRAINZ",
    "SPOTIFY",
    "LASTFM"
  ],
  "message": "Metadata auto-fixed successfully"
}
```

**Behavior:**
- Forces **refresh** (bypasses cache)
- Enriches **track, artist, album** (cascade)
- Uses **all 3 sources** (Spotify, MusicBrainz, Last.fm)
- Merges results using authority hierarchy
- One-click fix for common metadata issues

**Use Cases:**
- "Fix this track" button in UI
- Bulk metadata correction
- Post-import cleanup

**Errors:**
- `400 Bad Request` - Invalid track_id format (not UUID)
- `404 Not Found` - Track not found in database
- `500 Internal Server Error` - External API error

**Code Reference:**
```python
# src/soulspot/api/routers/metadata.py (lines 349-416)
@router.post("/{track_id}/auto-fix")
async def auto_fix_track_metadata(
    track_id: str,
    use_case: EnrichMetadataMultiSourceUseCase = Depends(get_enrich_use_case),
) -> dict[str, Any]:
    """Auto-fix metadata for a single track."""
    ...
```

---

### 6. POST `/api/metadata/update-from-spotify`

**Purpose:** Update track metadata directly from Spotify (bypass multi-source enrichment).

**Request Body:**
```json
{
  "track_id": "770e8400-e29b-41d4-a716-446655440001",
  "spotify_track_id": "3n3Ppam7vgaVa1iaRUc9Lp",
  "overwrite_existing": false
}
```

**Request Schema:**
```python
class UpdateFromSpotifyRequest(BaseModel):
    track_id: str            # Track UUID
    spotify_track_id: str    # Spotify Track ID (e.g., "3n3Ppam7vgaVa1iaRUc9Lp")
    overwrite_existing: bool = False  # Overwrite non-empty fields
```

**Response:**
```json
{
  "track_id": "770e8400-e29b-41d4-a716-446655440001",
  "updated_fields": [
    "isrc",
    "duration_ms",
    "album_art_url"
  ],
  "message": "Metadata updated from Spotify"
}
```

**Behavior:**
- Fetches metadata **only from Spotify**
- Faster than multi-source enrichment
- If `overwrite_existing=false`, only fills empty fields
- If `overwrite_existing=true`, replaces ALL fields

**Use Cases:**
- Quick Spotify-specific updates
- Import metadata for newly added tracks
- Sync with Spotify changes (e.g., album art updates)

**Code Reference:**
```python
# src/soulspot/api/routers/metadata.py
@router.post("/update-from-spotify")
async def update_from_spotify(
    request: UpdateFromSpotifyRequest,
    track_repository: TrackRepository = Depends(get_track_repository),
    spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin),
) -> dict[str, Any]:
    """Update track metadata directly from Spotify."""
    ...
```

---

## Data Models

### MetadataEnrichmentResponse

```python
class MetadataEnrichmentResponse(BaseModel):
    track_id: str                            # Track UUID
    enriched_fields: list[str]               # List of fields that were updated
    sources_used: list[str]                  # Data sources queried (SPOTIFY, MUSICBRAINZ, LASTFM)
    conflicts: list[MetadataConflict]        # Detected conflicts between sources
    errors: list[str]                        # Errors from external APIs (if any)
```

### MetadataConflict

```python
class MetadataConflict(BaseModel):
    field_name: str                          # Field with conflict (e.g., "release_date")
    current_value: Any                       # Current value in database
    current_source: MetadataSourceEnum       # Source of current value
    conflicting_values: dict[MetadataSourceEnum, Any]  # Alternative values from other sources
```

**Example:**
```json
{
  "field_name": "release_date",
  "current_value": "1975-09-12",
  "current_source": "MUSICBRAINZ",
  "conflicting_values": {
    "SPOTIFY": "1975-09-15",
    "LASTFM": "1975-09-10"
  }
}
```

### MetadataSourceEnum

```python
class MetadataSourceEnum(str, Enum):
    MANUAL = "MANUAL"              # User-provided override
    MUSICBRAINZ = "MUSICBRAINZ"    # MusicBrainz database
    SPOTIFY = "SPOTIFY"            # Spotify API
    LASTFM = "LASTFM"              # Last.fm API
```

### TagNormalizationResult

```python
class TagNormalizationResult(BaseModel):
    original: str      # Original tag/artist name
    normalized: str    # Normalized tag (standardized format)
    changed: bool      # True if normalization changed the value
```

---

## Code Examples

### Example 1: Enrich Track from All Sources

```python
import httpx

async def enrich_track_metadata(track_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/metadata/enrich",
            json={
                "track_id": track_id,
                "force_refresh": True,
                "enrich_artist": True,
                "enrich_album": True,
                "use_spotify": True,
                "use_musicbrainz": True,
                "use_lastfm": True
            }
        )
        return response.json()

# Enrich track with force refresh
result = await enrich_track_metadata("770e8400-e29b-41d4-a716-446655440001")
print(f"Enriched fields: {result['enriched_fields']}")
print(f"Sources used: {result['sources_used']}")
print(f"Conflicts detected: {len(result['conflicts'])}")
```

### Example 2: Resolve Conflict with Custom Value

```python
async def resolve_release_date_conflict(track_id: str, custom_date: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/metadata/resolve-conflict",
            json={
                "track_id": track_id,
                "field_name": "release_date",
                "selected_source": "MANUAL",
                "custom_value": custom_date
            }
        )
        return response.json()

# Override with user-provided release date
result = await resolve_release_date_conflict(
    "770e8400-e29b-41d4-a716-446655440001",
    "1975-09-12"
)
print(result["message"])  # "Conflict resolved successfully"
```

### Example 3: Normalize Artist Tags

```python
async def normalize_artist_names(artist_names: list[str]):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/metadata/normalize-tags",
            json=artist_names
        )
        return response.json()

# Normalize artist names
artists = [
    "Pink Floyd feat. David Gilmour",
    "Radiohead ft. Thom Yorke",
    "The Beatles featuring Paul McCartney"
]
results = await normalize_artist_names(artists)

for result in results:
    if result["changed"]:
        print(f"{result['original']} → {result['normalized']}")
```

### Example 4: Auto-Fix Track Metadata

```python
async def auto_fix_track(track_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/metadata/{track_id}/auto-fix"
        )
        return response.json()

# One-click metadata fix
result = await auto_fix_track("770e8400-e29b-41d4-a716-446655440001")
print(f"Success: {result['success']}")
print(f"Fixed fields: {result['enriched_fields']}")
```

### Example 5: Get Source Hierarchy

```python
async def get_metadata_hierarchy():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/metadata/sources/hierarchy")
        return response.json()

# Display hierarchy
hierarchy = await get_metadata_hierarchy()
sorted_sources = sorted(hierarchy.items(), key=lambda x: x[1])
for source, priority in sorted_sources:
    print(f"{priority}: {source}")
```

### Example 6: Update from Spotify Only

```python
async def update_track_from_spotify(track_id: str, spotify_track_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/metadata/update-from-spotify",
            json={
                "track_id": track_id,
                "spotify_track_id": spotify_track_id,
                "overwrite_existing": False
            }
        )
        return response.json()

# Update track from Spotify (fill empty fields only)
result = await update_track_from_spotify(
    "770e8400-e29b-41d4-a716-446655440001",
    "3n3Ppam7vgaVa1iaRUc9Lp"
)
print(f"Updated fields: {result['updated_fields']}")
```

---

## Technical Notes

### Authority Hierarchy Implementation

```python
# src/soulspot/application/services/metadata_merger.py
class MetadataMerger:
    AUTHORITY_HIERARCHY = {
        MetadataSource.MANUAL: 0,       # Highest priority
        MetadataSource.MUSICBRAINZ: 1,
        MetadataSource.SPOTIFY: 2,
        MetadataSource.LASTFM: 3,       # Lowest priority
    }

    def merge_field(self, field_name: str, values: dict[MetadataSource, Any]) -> Any:
        """Merge field value using authority hierarchy."""
        for source in sorted(self.AUTHORITY_HIERARCHY, key=self.AUTHORITY_HIERARCHY.get):
            if source in values and values[source] is not None:
                return values[source]  # Return highest-priority non-null value
        return None
```

### Conflict Detection Logic

```python
def detect_conflicts(self, field_name: str, values: dict[MetadataSource, Any]) -> bool:
    """Detect if sources provide conflicting values for a field."""
    unique_values = set(v for v in values.values() if v is not None)
    return len(unique_values) > 1  # Conflict if 2+ different non-null values
```

### Spotify Token Issue (Known Bug)

⚠️ **WARNING:** Spotify enrichment currently **broken** due to hardcoded `spotify_access_token=None`:

```python
# src/soulspot/api/routers/metadata.py (line 125)
spotify_access_token=None,  # TODO: Get from auth context - requires session/JWT token extraction
```

**Workaround:** Use `/api/metadata/update-from-spotify` endpoint with server-side token OR implement JWT token extraction.

---

## Related Endpoints

**Related Features:**
- [Tracks API](./tracks-api.md) - Track CRUD operations
- [Library Management API](./library-management-api.md) - Bulk metadata enrichment
- [Settings API](./settings-api.md) - Configure enrichment providers

**Workflow Integration:**
```
1. Import Track (Library API)
   ↓
2. Enrich Metadata (Metadata API) ← YOU ARE HERE
   ↓
3. Resolve Conflicts (if any)
   ↓
4. Download Track (Downloads API)
```

---

## Summary

**6 Endpoints** for metadata management:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/metadata/enrich` | POST | Enrich track from multiple sources |
| `/metadata/resolve-conflict` | POST | Manually resolve metadata conflict |
| `/metadata/normalize-tags` | POST | Normalize artist/track names |
| `/metadata/sources/hierarchy` | GET | Get source priority configuration |
| `/metadata/{track_id}/auto-fix` | POST | One-click metadata fix |
| `/metadata/update-from-spotify` | POST | Update from Spotify only |

**Key Features:**
- ✅ **Multi-Source Enrichment** (Spotify, MusicBrainz, Last.fm)
- ✅ **Authority Hierarchy** (Manual > MusicBrainz > Spotify > Last.fm)
- ✅ **Conflict Detection** (identifies discrepancies)
- ✅ **Manual Overrides** (custom values or source selection)
- ✅ **Tag Normalization** (standardize "feat." formats)
- ⚠️ **Spotify Token Bug** (requires JWT token extraction - not yet implemented)
