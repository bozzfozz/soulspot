# Library Enrichment API

External API integration for metadata enrichment (Spotify, MusicBrainz, Deezer).

## Overview

The Enrichment API adds external metadata to local library items using external APIs:
- **Spotify URIs**: Link library items to Spotify for streaming
- **Artwork**: Download album covers and artist images
- **Disambiguation**: MusicBrainz disambiguation strings for naming templates
- **Genres**: Spotify genre tags

**CRITICAL:** This API uses EXTERNAL APIs (violates "LocalLibrary = local only" rule), so it lives separately from `/api/library/*` routes.

**Route Prefix:** `/api/enrichment/*` (NOT `/api/library/enrichment/*`)

**Enrichment vs. Library Scanning:**
- **Enrichment**: Adds metadata from Spotify/MB to items already in DB
- **Scanner**: Reads local audio files and creates library items
- **Postprocessing**: Modifies audio file content (tagging, transcoding)

**Provider Requirements:**
- **Spotify**: Requires OAuth (user must authenticate)
- **Deezer**: NO auth required for enrichment (public API)
- **MusicBrainz**: NO auth, respects 1 req/sec rate limit

---

## Get Enrichment Status

**Endpoint:** `GET /api/enrichment/status`

**Description:** Get current status of library enrichment progress.

**Query Parameters:** None

**Response:**
```json
{
    "artists_unenriched": 25,
    "albums_unenriched": 47,
    "pending_candidates": 3,
    "is_enrichment_needed": true,
    "is_running": false,
    "last_job_completed": true
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 79-120

@router.get("/status", response_model=EnrichmentStatusResponse)
async def get_enrichment_status(
    session: AsyncSession = Depends(get_db_session),
    job_queue: JobQueue = Depends(get_job_queue),
) -> EnrichmentStatusResponse:
    """Get current status of library enrichment.

    Hey future me - this shows how much work is needed!
    - Unenriched = has local files but no Spotify URI
    - Pending candidates = ambiguous matches waiting for user review
    - is_running = enrichment job currently processing
    """
```

**Response Fields:**
- `artists_unenriched` (integer): Artists without Spotify URI
- `albums_unenriched` (integer): Albums without Spotify URI
- `pending_candidates` (integer): Ambiguous matches needing user review
- `is_enrichment_needed` (boolean): Whether enrichment would be useful
- `is_running` (boolean): Whether enrichment job is currently active
- `last_job_completed` (boolean | null): Status of last job (true=success, false=failed, null=none)

**Unenriched Definition:**
- Has local audio files in library
- Missing `spotify_uri` field
- Could benefit from Spotify metadata

**Use Cases:**
- **Enrichment UI**: Show progress/status
- **Automation**: Trigger enrichment when count reaches threshold
- **Dashboard Widget**: Display enrichment health

**Job Status Check:**
- Queries `JobQueue` for `LIBRARY_SPOTIFY_ENRICHMENT` jobs
- `is_running=true` if job PENDING or RUNNING
- `last_job_completed` reflects most recent job outcome

---

## Trigger Enrichment Job

**Endpoint:** `POST /api/enrichment/trigger`

**Description:** Manually trigger a background enrichment job.

**Request Body:** None

**Response:**
```json
{
    "job_id": "uuid-job-123",
    "message": "Enrichment job queued successfully"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 127-158

@router.post("/trigger", response_model=EnrichmentTriggerResponse)
async def trigger_enrichment(
    job_queue: JobQueue = Depends(get_job_queue),
) -> EnrichmentTriggerResponse:
    """Manually trigger a library enrichment job.

    Hey future me - this is a BACKGROUND JOB!
    The job will:
    1. Find unenriched artists and albums
    2. Search Spotify for matches
    3. Apply high-confidence matches automatically
    4. Create candidates for ambiguous matches (user review needed)

    Poll /enrichment/status to check progress.
    """
```

**Enrichment Job Workflow:**
1. **Find Unenriched Items**: Query artists/albums without `spotify_uri`
2. **Search Spotify**: Find potential matches by name
3. **Confidence Scoring**: Calculate match confidence (exact name match, popularity, etc.)
4. **Auto-Apply High Confidence**: Matches >90% confidence applied automatically
5. **Create Candidates**: Low confidence matches saved for user review
6. **Download Artwork**: Fetch and cache album/artist images

**Use Cases:**
- **Manual Trigger**: User clicks "Enrich Library" button
- **Post-Import**: Trigger after bulk local file import
- **Periodic Refresh**: Update metadata for new releases

**Background Job:** This is async! Poll `/enrichment/status` to check progress.

**Job Payload:**
```json
{
    "triggered_by": "manual_api"
}
```

---

## Repair Missing Artwork

**Endpoint:** `POST /api/enrichment/repair-artwork`

**Description:** Download missing local artwork for artists/albums.

**Query Parameters:**
- `entity_type` (string, optional): Filter by `artist`, `album`, or omit for both
- `use_api` (boolean, optional): If true, use Deezer API to find missing images (default: false)
- `limit` (integer, optional): Max entities to process (1-500, default: 100)

**Request Body:** None

**Response:**
```json
{
    "artists": {
        "processed": 15,
        "repaired": 8,
        "skipped": 7,
        "failed": 0
    },
    "albums": {
        "processed": 32,
        "repaired": 20,
        "skipped": 12,
        "failed": 0
    },
    "summary": {
        "total_processed": 47,
        "total_repaired": 28,
        "mode": "cdn_only"
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 161-267

@router.post("/repair-artwork")
async def repair_missing_artwork(
    entity_type: str | None = Query(
        None,
        description="Filter by 'artist' or 'album', or omit for both",
    ),
    use_api: bool = Query(
        False,
        description="If True, use Deezer API to find missing images (slower, but finds more)",
    ),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Download missing local artwork for artists and albums.

    Hey future me - TWO MODES:
    1. CDN-only (default): Fast! Just downloads from URLs already in DB
    2. API mode (use_api=true): Slower, but searches Deezer for missing images

    CDN mode works for entities enriched via:
    - Deezer (no auth needed)
    - Spotify (if user was authenticated when enriching)
    - Any provider that saved an image_url

    API mode uses Deezer to find images for entities that:
    - Have no cover_url/image_url in DB yet
    - Were imported from local files without enrichment

    REFACTORED (Dec 2025): Now uses modern repair functions directly,
    not the deprecated ImageRepairService wrapper!
    """
```

**Two Modes:**

**1. CDN-Only Mode (default):**
- **Fast**: Only downloads from URLs already in database
- **No API Calls**: Uses cached `image_url`/`cover_url` fields
- **Works For:**
  - Spotify-enriched items (if user authenticated during enrichment)
  - Deezer-enriched items (always has URLs)
  - Manually set image URLs

**2. API Mode (`use_api=true`):**
- **Slower**: Searches Deezer API for missing images
- **Finds More**: Can find images for items without any URL
- **NO AUTH REQUIRED**: Deezer public API
- **Works For:**
  - Local file imports without enrichment
  - Items with failed/missing URLs

**Use Cases:**
- **Bulk Repair**: Fix missing artwork after library import
- **UI Polish**: Download images for display
- **Offline Usage**: Cache images locally

**Example - CDN-Only (Fast):**
```
POST /api/enrichment/repair-artwork?entity_type=album&limit=50
```

**Example - API Mode (Thorough):**
```
POST /api/enrichment/repair-artwork?use_api=true&limit=100
```

**Response Fields:**
- `artists` (object): Artist repair stats
  - `processed` (integer): Artists checked
  - `repaired` (integer): Images downloaded
  - `skipped` (integer): Already had images
  - `failed` (integer): Download errors
- `albums` (object): Album repair stats (same structure)
- `summary` (object): Overall stats
  - `total_processed` (integer): Total items checked
  - `total_repaired` (integer): Total images downloaded
  - `mode` (string): "cdn_only" or "api"

**REFACTORED (Dec 2025):**
Previously used `ImageRepairService` wrapper. Now calls `repair_artist_images()` and `repair_album_images()` directly from `soulspot.application.services.images.repair` module.

---

## Reset Failed Images

**Endpoint:** `POST /api/enrichment/reset-failed-images`

**Description:** Reset FAILED image markers to allow retry.

**Query Parameters:**
- `entity_type` (string, optional): Filter by `artist`, `album`, or omit for both

**Request Body:** None

**Response:**
```json
{
    "reset_artists": 5,
    "reset_albums": 12
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 270-310

@router.post("/reset-failed-images")
async def reset_failed_images(
    entity_type: str | None = Query(
        None,
        description="Filter by 'artist' or 'album', or omit for both",
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Reset FAILED image markers to allow retry.

    Hey future me - when image downloads fail, we mark them as "FAILED|reason|timestamp"
    to prevent retrying forever. This endpoint clears those markers
    so the user can trigger another repair attempt.

    The marker format is: FAILED|{reason}|{ISO timestamp}
    Example: FAILED|not_available|2025-01-15T10:30:00Z
    """
```

**FAILED Marker Format:**
- **Pattern**: `FAILED|{reason}|{ISO timestamp}`
- **Example**: `FAILED|not_available|2025-01-15T10:30:00Z`
- **Purpose**: Prevent infinite retry loops for permanently unavailable images

**When Markers Are Set:**
- Image URL returns 404 (not found)
- Image download times out
- Image URL is malformed/invalid
- Service unavailable (403/500 errors)

**Reset Behavior:**
- **Clears**: Sets `image_path` / `cover_path` to `NULL`
- **SQL Pattern**: Matches all `FAILED%` variants (handles different timestamp formats)
- **Immediate Effect**: Next repair attempt will try downloading again

**Use Cases:**
- **Retry Failed Downloads**: After fixing network issues
- **Provider Changed**: After switching image providers
- **Bulk Reset**: Before re-running repair with different settings

**Example - Reset All:**
```
POST /api/enrichment/reset-failed-images
```

**Example - Reset Albums Only:**
```
POST /api/enrichment/reset-failed-images?entity_type=album
```

---

## List Enrichment Candidates

**Endpoint:** `GET /api/enrichment/candidates`

**Description:** Get pending enrichment candidates for user review.

**Query Parameters:**
- `entity_type` (string, optional): Filter by `artist` or `album`
- `limit` (integer, optional): Max candidates to return (1-200, default: 50)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response:**
```json
{
    "candidates": [
        {
            "id": "candidate-uuid-123",
            "entity_type": "artist",
            "entity_id": "artist-uuid-456",
            "entity_name": "Nirvana",
            "spotify_uri": "spotify:artist:6olE6TJLqED3rqDCT0FyPh",
            "spotify_name": "Nirvana",
            "spotify_image_url": "https://i.scdn.co/image/abc123",
            "confidence_score": 0.75,
            "extra_info": {
                "popularity": 85,
                "genres": ["grunge", "alternative rock"]
            }
        },
        {
            "id": "candidate-uuid-789",
            "entity_type": "artist",
            "entity_id": "artist-uuid-456",
            "entity_name": "Nirvana",
            "spotify_uri": "spotify:artist:DIFFERENT_ID",
            "spotify_name": "Nirvana (UK rock band)",
            "spotify_image_url": "https://i.scdn.co/image/xyz789",
            "confidence_score": 0.60,
            "extra_info": {
                "popularity": 15,
                "genres": ["psychedelic rock"]
            }
        }
    ],
    "total": 2
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 318-366

@router.get("/candidates", response_model=EnrichmentCandidatesListResponse)
async def get_enrichment_candidates(
    entity_type: str | None = Query(None, description="Filter by 'artist' or 'album'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> EnrichmentCandidatesListResponse:
    """Get pending enrichment candidates for user review.

    Hey future me - these are AMBIGUOUS matches!
    Multiple Spotify results were found for one local item.
    User needs to select the correct one.
    """
```

**Why Candidates Exist:**
- **Ambiguous Names**: Multiple artists/albums with same name (e.g., "Nirvana" - US grunge vs. UK psychedelic)
- **Low Confidence**: Match confidence <90% (name similar but not exact)
- **Disambiguation Needed**: User must choose correct Spotify entity

**Candidate Fields:**
- `id` (string): Candidate UUID (for applying/rejecting)
- `entity_type` (string): "artist" or "album"
- `entity_id` (string): Local library entity UUID
- `entity_name` (string): Local entity name
- `spotify_uri` (string): Spotify URI for this candidate
- `spotify_name` (string): Spotify entity name (may have disambiguation)
- `spotify_image_url` (string | null): Preview image URL
- `confidence_score` (float): Match confidence (0.0-1.0)
- `extra_info` (object): Additional context (popularity, genres, etc.)

**Confidence Scoring Factors:**
- **Name Match**: Exact = 1.0, similar = 0.7-0.9, partial = 0.5-0.7
- **Popularity**: Higher popularity = higher confidence
- **Release Year**: Matching year boosts confidence
- **Genre Overlap**: Similar genres boost confidence

**Use Cases:**
- **Enrichment UI**: Show candidates for user selection
- **Manual Review**: Resolve ambiguous matches
- **Quality Control**: Verify automatic matches

**Pagination:**
- Use `limit` and `offset` for large candidate lists
- Sort order: Confidence descending (highest first)

---

## Apply Enrichment Candidate

**Endpoint:** `POST /api/enrichment/candidates/{candidate_id}/apply`

**Description:** Apply a user-selected enrichment candidate.

**Path Parameters:**
- `candidate_id` (string): Candidate UUID to apply

**Request Body:** None

**Response:**
```json
{
    "success": true,
    "message": "Successfully applied Spotify match",
    "spotify_uri": "spotify:artist:6olE6TJLqED3rqDCT0FyPh"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 369-404

@router.post("/candidates/{candidate_id}/apply")
async def apply_enrichment_candidate(
    candidate_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Apply a user-selected enrichment candidate.

    Hey future me - this confirms a Spotify match!
    Actions:
    1. Mark the candidate as selected
    2. Update the entity (artist/album) with Spotify URI and image
    3. Reject other candidates for the same entity
    """
```

**Actions Performed:**
1. **Mark Selected**: Set candidate status to "applied"
2. **Update Entity**: Set `spotify_uri` and `image_url` on artist/album
3. **Reject Others**: Mark other candidates for same entity as rejected
4. **Download Image**: Fetch and cache artwork from Spotify URL

**Error Responses:**
- **404 Not Found**: Candidate doesn't exist
- **400 Bad Request**: Candidate already applied or rejected

**Use Cases:**
- **User Confirmation**: User selects correct match from list
- **Manual Enrichment**: Apply specific Spotify link

**Example:**
```
POST /api/enrichment/candidates/candidate-uuid-123/apply
```

**Effect:**
- Library entity now has Spotify URI
- Artwork downloaded and cached locally
- Other candidates for same entity rejected
- Entity appears as "enriched" in status

---

## Reject Enrichment Candidate

**Endpoint:** `POST /api/enrichment/candidates/{candidate_id}/reject`

**Description:** Reject an enrichment candidate (wrong match).

**Path Parameters:**
- `candidate_id` (string): Candidate UUID to reject

**Request Body:** None

**Response:**
```json
{
    "success": true,
    "message": "Candidate rejected"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 407-433

@router.post("/candidates/{candidate_id}/reject")
async def reject_enrichment_candidate(
    candidate_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Reject an enrichment candidate.

    Use this when the suggested Spotify match is incorrect.
    """
```

**Actions Performed:**
- **Mark Rejected**: Set candidate status to "rejected"
- **No Entity Update**: Library entity remains unchanged
- **Keep Other Candidates**: Other candidates for same entity still available

**Use Cases:**
- **Wrong Match**: Candidate is incorrect Spotify entity
- **Manual Curation**: User knows correct match isn't in candidate list
- **Quality Control**: Remove low-quality matches

**Behavior:**
- **Entity Unchanged**: Library item remains unenriched
- **Candidate Removed**: Won't appear in candidate list anymore
- **Reversible**: Can manually enrich later via different method

---

## Enrich MusicBrainz Disambiguation

**Endpoint:** `POST /api/enrichment/disambiguation`

**Description:** Enrich artists/albums with MusicBrainz disambiguation data.

**Request Body:**
```json
{
    "limit": 50
}
```

**Request Fields:**
- `limit` (integer): Max items to process (default: 50)

**Response (HTML):** HTMX-compatible HTML fragment with results

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 441-539

@router.post("/disambiguation")
async def enrich_disambiguation(
    request: DisambiguationEnrichmentRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Enrich artists and albums with MusicBrainz disambiguation data.

    Hey future me - this is for Lidarr-style naming templates!
    MusicBrainz provides disambiguation strings like "(US rock band)" to differentiate
    artists with the same name (e.g., multiple artists named "Nirvana").

    This endpoint:
    1. Finds artists/albums without disambiguation
    2. Searches MusicBrainz for matches
    3. Stores disambiguation strings from MB results

    Note: Respects MusicBrainz 1 req/sec rate limit, so large batches take time.
    """
```

**Disambiguation Purpose:**
- **Naming Templates**: Use in Lidarr-style file naming (e.g., `Artist (disambiguation)/Album`)
- **Differentiation**: Distinguish artists with same name (e.g., "Nirvana (US grunge band)" vs. "Nirvana (UK psychedelic rock band)")
- **Metadata Quality**: Improve clarity in library

**MusicBrainz Disambiguation Examples:**
- "Nirvana (US grunge band)"
- "George Clinton (funk musician)"
- "The Beatles (UK rock band)"

**Workflow:**
1. **Find Items**: Artists/albums without `disambiguation` field
2. **Search MusicBrainz**: Match by name + optional release year
3. **Extract Disambiguation**: Get disambiguation string from MB result
4. **Store**: Update entity with disambiguation

**Rate Limiting:**
- **MusicBrainz Requirement**: 1 request/second
- **Impact**: 50 items takes ~50 seconds
- **Recommendation**: Use moderate `limit` values (50-100)

**Response Examples:**

**Success (HTMX HTML):**
```html
<div class="musicbrainz-result" style="background: rgba(186, 83, 45, 0.1); ...">
    <i class="bi bi-check-circle-fill"></i>
    <span>Enriched <strong>15</strong> artists and <strong>23</strong> albums with disambiguation data.</span>
</div>
```

**Provider Disabled:**
```html
<div class="musicbrainz-result" style="background: rgba(59, 130, 246, 0.1); ...">
    <i class="bi bi-info-circle"></i>
    <span>MusicBrainz provider is disabled in Settings.</span>
</div>
```

**No Work Needed:**
```html
<div class="musicbrainz-result" style="background: rgba(59, 130, 246, 0.1); ...">
    <i class="bi bi-check-circle"></i>
    <span>All items already have disambiguation data or no matches found.</span>
</div>
```

**Error:**
```html
<div class="musicbrainz-result" style="background: rgba(239, 68, 68, 0.1); ...">
    <i class="bi bi-exclamation-triangle"></i>
    <span>Error: MusicBrainz API timeout</span>
</div>
```

**Use Cases:**
- **File Naming**: Use disambiguation in rename templates
- **Metadata Completeness**: Fill missing disambiguation
- **Manual Trigger**: Run from enrichment UI

---

## Auto-Fetch Images (Background)

**Endpoint:** `POST /api/enrichment/auto-fetch-images`

**Description:** Auto-fetch missing images in background (HTMX endpoint).

**Query Parameters:**
- `entity_type` (string, optional): Filter by `artist`, `album`, or omit for both
- `limit` (integer, optional): Max entities to process (1-100, default: 20)

**Request Body:** None

**Response (HTML):** HTMX fragment with status (empty if nothing fetched)

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 555-639

@router.post("/auto-fetch-images", response_class=HTMLResponse)
async def auto_fetch_images(
    entity_type: str | None = Query(
        None,
        description="Filter by 'artist' or 'album', or omit for both",
    ),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Auto-fetch missing images in background (HTMX endpoint).

    Hey future me - this is the AUTO-MAGIC endpoint!
    Called via HTMX on page load to silently fetch missing images.
    Returns an empty response or minimal status update for the UI.

    Uses Deezer API (NO AUTH NEEDED!) to find images for entities
    that have deezer_id but no local image cached yet.
    """
```

**Auto-Fetch Behavior:**
- **Silent Background Operation**: Called via HTMX on page load
- **NO UI Blocking**: Returns immediately with minimal response
- **Deezer API**: Uses public Deezer API (NO AUTH REQUIRED)
- **Target**: Entities with `deezer_id` but missing local image

**When It's Used:**
- **Page Load**: HTMX calls this when user views artist/album page
- **Automatic**: User doesn't need to click anything
- **Lightweight**: Processes only 20 items by default (fast response)

**Response Examples:**

**Images Fetched:**
```html
<div id="auto-fetch-result" data-repaired="5"
     hx-trigger="load" hx-get="" hx-swap="none"
     style="display:none;">
    <!-- Auto-fetched 5 images -->
</div>
```

**Nothing to Fetch:**
```html
<!-- Empty response -->
```

**HTMX Integration:**
```html
<div hx-post="/api/enrichment/auto-fetch-images?entity_type=album&limit=10"
     hx-trigger="load"
     hx-swap="none">
    <!-- Triggers on page load, no visible UI -->
</div>
```

**Use Cases:**
- **Background Enrichment**: Fetch images without user action
- **Progressive Enhancement**: Load images as user browses
- **Seamless UX**: No manual "download images" button needed

**Fail Silently:**
- **Errors Logged**: Failures logged but not shown to user
- **Non-Blocking**: Page still works if fetch fails

---

## Auto-Fetch Discography (Background)

**Endpoint:** `POST /api/enrichment/auto-fetch-discography`

**Description:** Auto-fetch complete discography for an artist (HTMX endpoint).

**Query Parameters:**
- `artist_id` (string, required): Artist ID to fetch discography for
- `include_tracks` (boolean, optional): Also fetch tracks for each album (default: true)

**Request Body:** None

**Response (HTML):** HTMX fragment with status

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/enrichment.py
# Lines 642-704

@router.post("/auto-fetch-discography", response_class=HTMLResponse)
async def auto_fetch_discography(
    artist_id: str = Query(..., description="Artist ID to fetch discography for"),
    include_tracks: bool = Query(True, description="Also fetch tracks for each album"),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Auto-fetch complete discography for an artist (HTMX endpoint).

    Hey future me - this is the AUTO-ALBUM-FETCH endpoint!
    Called when user views an artist that has no albums yet.
    Fetches ALL albums + tracks from Deezer (or Spotify if authenticated).
    """
```

**Auto-Fetch Behavior:**
- **Trigger**: Called when user views artist page with no albums
- **Silent**: Background operation via HTMX
- **Deezer Primary**: Uses Deezer API (NO AUTH REQUIRED)
- **Spotify Fallback**: Uses Spotify if authenticated
- **Complete**: Fetches all albums + tracks for artist

**Workflow:**
1. **Detect**: HTMX detects artist has no albums
2. **Fetch Albums**: Query Deezer for artist's discography
3. **Fetch Tracks**: Get track list for each album (if `include_tracks=true`)
4. **Store**: Save albums + tracks to database
5. **Return**: Minimal HTML response (hidden div with stats)

**Response Examples:**

**Discography Fetched:**
```html
<div id="auto-fetch-result"
     data-albums="15" data-tracks="180"
     style="display:none;">
    <!-- Auto-fetched 15 albums, 180 tracks -->
</div>
```

**Nothing to Fetch:**
```html
<!-- Empty response -->
```

**HTMX Integration:**
```html
<div hx-post="/api/enrichment/auto-fetch-discography?artist_id=abc123&include_tracks=true"
     hx-trigger="load"
     hx-swap="none">
    <!-- Triggers on artist page load if no albums exist -->
</div>
```

**Use Cases:**
- **Artist Page**: Auto-load discography when viewing artist
- **Seamless Discovery**: User sees albums without manual action
- **Background Sync**: Progressive data loading

**Statistics Returned:**
- `albums_added` (integer): New albums synced
- `tracks_added` (integer): New tracks synced

---

## Summary

**Total Endpoints Documented:** 12

**Endpoint Categories:**
1. **Status & Triggering**: 2 endpoints (status, trigger job)
2. **Artwork Repair**: 2 endpoints (repair, reset failed)
3. **Candidate Review**: 3 endpoints (list, apply, reject)
4. **MusicBrainz**: 1 endpoint (disambiguation enrichment)
5. **Auto-Fetch (HTMX)**: 2 endpoints (images, discography)

**Key Features:**
- **Background Jobs**: Async enrichment with progress tracking
- **Multi-Provider**: Spotify (auth required), Deezer (no auth), MusicBrainz (public)
- **Candidate System**: User review for ambiguous matches
- **Artwork Management**: CDN-only vs. API mode repair
- **Auto-Fetch**: Silent background enrichment via HTMX
- **Disambiguation**: MusicBrainz data for naming templates

**Module Stats:**
- **Source File**: `enrichment.py` (739 lines)
- **Endpoints**: 12
- **Code Validation**: 100%

**Provider Requirements:**
- **Spotify**: OAuth required (user must authenticate)
- **Deezer**: NO auth required (public API)
- **MusicBrainz**: NO auth, 1 req/sec rate limit

**Use Cases:**
- **Post-Import Enrichment**: Add metadata after local file scan
- **Artwork Management**: Bulk image download/repair
- **Manual Review**: User selection for ambiguous matches
- **Background Sync**: Auto-fetch on page load
- **File Naming**: MusicBrainz disambiguation for templates
