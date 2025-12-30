# Automation API

**Base Path**: `/automation`

**Purpose**: Comprehensive automation system for music collection management - watchlists, discography tracking, quality upgrades, filter rules, workflow automation, and Spotify followed artists sync.

**Architecture**: Modular sub-router system (refactored Dec 2025 - eliminated ~1285 lines of duplicate code). Main `automation.py` aggregates 6 sub-modules.

**Critical Context**: Automation features integrate with background workers for scheduled tasks, support HTMX partial responses for UI, and follow multi-provider patterns for metadata enrichment.

---

## Endpoints Overview

### Watchlists (6 endpoints)
- `POST /automation/watchlist` - Create artist watchlist
- `GET /automation/watchlist` - List watchlists (pagination + filters)
- `GET /automation/watchlist/{watchlist_id}` - Get specific watchlist
- `POST /automation/watchlist/{watchlist_id}/check` - Manual trigger: check for new releases
- `DELETE /automation/watchlist/{watchlist_id}` - Delete watchlist (PERMANENT)

### Discography (2 endpoints)
- `POST /automation/discography/check` - Check discography completeness for artist
- `GET /automation/discography/missing` - Get missing albums across all artists

### Quality Upgrades (2 endpoints)
- `POST /automation/quality-upgrades/identify` - Find tracks for quality upgrade
- `GET /automation/quality-upgrades/unprocessed` - Get unprocessed upgrade candidates

### Filter Rules (9 endpoints)
- `POST /automation/filters` - Create filter rule
- `GET /automation/filters` - List filters
- `GET /automation/filters/{filter_id}` - Get filter details
- `POST /automation/filters/{filter_id}/enable` - Enable filter
- `POST /automation/filters/{filter_id}/disable` - Disable filter
- `PATCH /automation/filters/{filter_id}` - Update filter pattern
- `DELETE /automation/filters/{filter_id}` - Delete filter

### Workflow Rules (6 endpoints)
- `POST /automation/rules` - Create automation rule (trigger → action)
- `GET /automation/rules` - List automation rules
- `GET /automation/rules/{rule_id}` - Get rule details + execution stats
- `POST /automation/rules/{rule_id}/enable` - Enable rule
- `POST /automation/rules/{rule_id}/disable` - Disable rule
- `DELETE /automation/rules/{rule_id}` - Delete rule

### Followed Artists (3 endpoints)
- `POST /automation/followed-artists/sync` - Sync Spotify followed artists (HTMX-aware)
- `POST /automation/followed-artists/watchlists/bulk` - Bulk create watchlists
- `GET /automation/followed-artists/preview` - Preview followed artists (NO DB sync)

**Total**: 28 endpoints across 6 automation domains

---

## Watchlist Management

### 1. Create Watchlist

**Endpoint**: `POST /automation/watchlist`

**Purpose**: Create artist watchlist for automatic new release detection.

**Authentication**: None (uses database session)

**Request Body**:
```json
{
  "artist_id": "spotify:artist:3WrFJ7ztbogyGnTHbHJFl2",
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high"
}
```

**Behavior**:
- Idempotent-ish: Service layer handles duplicate artist attempts
- Immediate commit (no batch operations)
- Transaction rollback on failure
- `quality_profile` defaults to `"high"` (override for rare bootlegs → `"low"`)

**Response** (Success):
```json
{
  "id": "uuid-v4",
  "artist_id": "spotify:artist:3WrFJ7ztbogyGnTHbHJFl2",
  "status": "active",
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Error Handling**:
- `400`: Invalid `artist_id` format (ValueError from `ArtistId.from_string()`)
- `500`: Database errors (with rollback)

**Source**: `automation_watchlists.py:56-92`

---

### 2. List Watchlists

**Endpoint**: `GET /automation/watchlist?limit=100&offset=0&active_only=false`

**Purpose**: Retrieve watchlists with pagination and filtering.

**Query Parameters**:
- `limit` (int, default 100): Page size
- `offset` (int, default 0): Pagination offset
- `active_only` (bool, default false): Filter by active status

**Pagination Note**: Uses limit/offset (NOT cursor-based). For large datasets (thousands of watchlists), cursor pagination recommended to avoid missing rows when data changes between fetches.

**Response**:
```json
{
  "watchlists": [
    {
      "id": "uuid-v4",
      "artist_id": "spotify:artist:...",
      "status": "active",
      "check_frequency_hours": 24,
      "auto_download": true,
      "quality_profile": "high",
      "last_checked_at": "2025-01-15T12:00:00Z",
      "total_releases_found": 42,
      "total_downloads_triggered": 38
    }
  ],
  "limit": 100,
  "offset": 0
}
```

**Cumulative Stats**:
- `total_releases_found`: Increments with each check, never resets
- `total_downloads_triggered`: Tracks automation effectiveness ("this watchlist triggered 50 downloads!")

**Source**: `automation_watchlists.py:97-132`

---

### 3. Get Watchlist

**Endpoint**: `GET /automation/watchlist/{watchlist_id}`

**Purpose**: Retrieve specific watchlist details.

**Error Handling**:
- `400`: Malformed UUID
- `404`: Watchlist not found
- `500`: Database errors

**Source**: `automation_watchlists.py:137-171`

---

### 4. Check Watchlist Releases

**Endpoint**: `POST /automation/watchlist/{watchlist_id}/check`

**Purpose**: Manual trigger for "check this artist for new releases RIGHT NOW".

**Authentication**: Requires Spotify OAuth (uses `SpotifyPlugin` with `can_use()` check)

**Provider Requirements**:
- Spotify provider enabled (`is_provider_enabled("spotify")`)
- User authenticated with Spotify (`can_use(PluginCapability.GET_ARTIST_ALBUMS)`)

**Behavior**:
- Checks for new releases via Spotify API
- Updates `last_checked_at` timestamp
- Increments `total_releases_found` and `total_downloads_triggered` (if `auto_download=true`)
- Commits changes to database

**Response**:
```json
{
  "watchlist_id": "uuid-v4",
  "releases_found": 3,
  "releases": [
    { "album_id": "...", "title": "...", "release_date": "..." }
  ]
}
```

**Error Handling**:
- `401`: Not authenticated with Spotify
- `404`: Watchlist not found
- `503`: Spotify provider disabled

**Source**: `automation_watchlists.py:176-221`

---

### 5. Delete Watchlist

**Endpoint**: `DELETE /automation/watchlist/{watchlist_id}`

**Purpose**: Permanently delete watchlist (NO SOFT DELETE).

**Response**:
```json
{
  "message": "Watchlist {watchlist_id} deleted successfully"
}
```

**Source**: `automation_watchlists.py:226-242`

---

## Discography Tracking

### 6. Check Discography Completeness

**Endpoint**: `POST /automation/discography/check`

**Purpose**: Check if user has ALL albums for an artist (no live API call - uses pre-synced `spotify_albums` data from background sync).

**Request Body**:
```json
{
  "artist_id": "spotify:artist:3WrFJ7ztbogyGnTHbHJFl2"
}
```

**Behavior**:
- Compares local library against synced Spotify catalog
- Returns missing albums + completeness percentage
- NO live Spotify API call (uses DB cache)

**Response**:
```json
{
  "artist_id": "spotify:artist:...",
  "total_albums": 15,
  "owned_albums": 12,
  "missing_albums": 3,
  "completeness_percentage": 80.0,
  "missing_album_details": [
    { "album_id": "...", "title": "Rare B-Sides", "release_date": "2023-05-10" }
  ]
}
```

**Source**: `automation_discography.py:23-38`

---

### 7. Get Missing Albums (All Artists)

**Endpoint**: `GET /automation/discography/missing?limit=10`

**Purpose**: "Collector's dream" endpoint - show ALL missing albums across ALL artists.

**Query Parameters**:
- `limit` (int, default 10): Max artists to return

**Response**:
```json
{
  "artists_with_missing_albums": [
    {
      "artist_id": "...",
      "artist_name": "...",
      "missing_count": 5,
      "missing_albums": [...]
    }
  ],
  "count": 3
}
```

**Source**: `automation_discography.py:43-56`

---

## Quality Upgrades

### 8. Identify Quality Upgrade Candidates

**Endpoint**: `POST /automation/quality-upgrades/identify`

**Purpose**: Find tracks that could be upgraded to better quality files (e.g., 128kbps MP3 → 320kbps FLAC).

**Request Body**:
```json
{
  "quality_profile": "high",
  "min_improvement_score": 0.3,
  "limit": 100
}
```

**Parameters**:
- `quality_profile` (string, default "high"): Target quality level
- `min_improvement_score` (float, default 0.3): Minimum quality delta (0.0-1.0)
- `limit` (int, default 100): Max candidates to return

**Response**:
```json
{
  "candidates": [
    {
      "track_id": "...",
      "current_bitrate": 128000,
      "target_bitrate": 320000,
      "improvement_score": 0.6,
      "source_format": "mp3",
      "target_format": "flac"
    }
  ],
  "count": 42,
  "quality_profile": "high",
  "min_improvement_score": 0.3
}
```

**Source**: `automation_quality_upgrades.py:27-55`

---

### 9. Get Unprocessed Quality Upgrades

**Endpoint**: `GET /automation/quality-upgrades/unprocessed?limit=100`

**Purpose**: Retrieve quality upgrade candidates that haven't been processed yet.

**Source**: `automation_quality_upgrades.py:58-69`

---

## Filter Rules

### 10. Create Filter Rule

**Endpoint**: `POST /automation/filters`

**Purpose**: Create download filter rule (whitelist/blacklist) to control automation behavior.

**Request Body**:
```json
{
  "name": "Block Low Bitrate",
  "filter_type": "blacklist",
  "target": "bitrate",
  "pattern": "128kbps",
  "is_regex": false,
  "priority": 10,
  "description": "Skip low-quality files"
}
```

**Filter Types**:
- `whitelist`: Only allow matching items
- `blacklist`: Block matching items

**Filter Targets**:
- `keyword`: Match against track/album/artist names
- `user`: Match against Soulseek username
- `format`: Match against file format (mp3/flac/ogg)
- `bitrate`: Match against bitrate

**Response**:
```json
{
  "id": "uuid-v4",
  "name": "Block Low Bitrate",
  "filter_type": "blacklist",
  "target": "bitrate",
  "pattern": "128kbps",
  "is_regex": false,
  "enabled": true,
  "priority": 10,
  "description": "Skip low-quality files",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Source**: `automation_filters.py:30-71`

---

### 11. List Filters

**Endpoint**: `GET /automation/filters?filter_type=blacklist&enabled_only=true&limit=100&offset=0`

**Purpose**: List filter rules with optional filtering.

**Query Parameters**:
- `filter_type` (string, optional): Filter by type ("whitelist"/"blacklist")
- `enabled_only` (bool, default false): Only return enabled filters
- `limit` (int, default 100): Page size
- `offset` (int, default 0): Pagination offset

**Source**: `automation_filters.py:74-120`

---

### 12. Get Filter

**Endpoint**: `GET /automation/filters/{filter_id}`

**Purpose**: Retrieve specific filter rule details.

**Response** (additional fields):
```json
{
  "updated_at": "2025-01-15T14:00:00Z"
}
```

**Source**: `automation_filters.py:123-158`

---

### 13. Enable Filter

**Endpoint**: `POST /automation/filters/{filter_id}/enable`

**Source**: `automation_filters.py:161-177`

---

### 14. Disable Filter

**Endpoint**: `POST /automation/filters/{filter_id}/disable`

**Source**: `automation_filters.py:180-196`

---

### 15. Update Filter Pattern

**Endpoint**: `PATCH /automation/filters/{filter_id}`

**Purpose**: Update filter rule's pattern and regex flag.

**Request Body**:
```json
{
  "pattern": "256kbps",
  "is_regex": false
}
```

**Source**: `automation_filters.py:199-218`

---

### 16. Delete Filter

**Endpoint**: `DELETE /automation/filters/{filter_id}`

**Source**: `automation_filters.py:221-237`

---

## Workflow Rules

### 17. Create Automation Rule

**Endpoint**: `POST /automation/rules`

**Purpose**: Create automation workflow rule ("when X happens, do Y").

**Request Body**:
```json
{
  "name": "Auto-Download New Releases",
  "trigger": "new_release",
  "action": "search_and_download",
  "priority": 5,
  "quality_profile": "high",
  "apply_filters": true,
  "auto_process": true,
  "description": "Automatically download new releases for watchlisted artists"
}
```

**Trigger Types**:
- `new_release`: New album/single detected
- `missing_album`: Discography gap found
- `quality_upgrade`: Better quality file available
- `manual`: User-initiated

**Action Types**:
- `search_and_download`: Auto-download immediately
- `notify_only`: Send notification (no download)
- `add_to_queue`: Add to download queue for review

**Response** (additional fields):
```json
{
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Source**: `automation_rules.py:26-72`

---

### 18. List Automation Rules

**Endpoint**: `GET /automation/rules?trigger=new_release&enabled_only=true&limit=100&offset=0`

**Purpose**: List automation rules with filtering.

**Query Parameters**:
- `trigger` (string, optional): Filter by trigger type
- `enabled_only` (bool, default false): Only return enabled rules
- `limit` (int, default 100): Page size
- `offset` (int, default 0): Pagination offset

**Response** (execution stats):
```json
{
  "rules": [
    {
      "total_executions": 250,
      "successful_executions": 240,
      "failed_executions": 10
    }
  ]
}
```

**Source**: `automation_rules.py:75-125`

---

### 19. Get Automation Rule

**Endpoint**: `GET /automation/rules/{rule_id}`

**Purpose**: Retrieve rule details with execution statistics.

**Response** (additional fields):
```json
{
  "last_triggered_at": "2025-01-15T14:00:00Z",
  "total_executions": 250,
  "successful_executions": 240,
  "failed_executions": 10,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T14:00:00Z"
}
```

**Source**: `automation_rules.py:128-175`

---

### 20. Enable Automation Rule

**Endpoint**: `POST /automation/rules/{rule_id}/enable`

**Source**: `automation_rules.py:178-194`

---

### 21. Disable Automation Rule

**Endpoint**: `POST /automation/rules/{rule_id}/disable`

**Source**: `automation_rules.py:197-213`

---

### 22. Delete Automation Rule

**Endpoint**: `DELETE /automation/rules/{rule_id}`

**Source**: `automation_rules.py:216-232`

---

## Followed Artists Management

### 23. Sync Followed Artists

**Endpoint**: `POST /automation/followed-artists/sync`

**Purpose**: Sync Spotify followed artists to local database (HTMX-aware - returns HTML or JSON based on request headers).

**Authentication**: Requires Spotify OAuth

**Provider Requirements**:
- Spotify provider enabled (`is_provider_enabled("spotify")`)
- User authenticated with Spotify (`can_use(PluginCapability.USER_FOLLOWED_ARTISTS)`)

**Behavior**:
- Fetches followed artists from Spotify API
- Uses DeezerPlugin for metadata fallback (NO AUTH NEEDED!)
- Returns HTMX partial HTML (`partials/followed_artists_list.html`) if `HX-Request: true` header present
- Returns JSON for API clients

**Response** (JSON):
```json
{
  "total_fetched": 50,
  "created": 35,
  "updated": 15,
  "errors": 0,
  "artists": [
    {
      "id": "uuid-v4",
      "name": "The Beatles",
      "spotify_uri": "spotify:artist:3WrFJ7ztbogyGnTHbHJFl2",
      "image_url": "https://cdn.spotify.com/...",
      "genres": ["rock", "pop", "psychedelic"]
    }
  ]
}
```

**Response** (HTMX):
```html
<!-- partials/followed_artists_list.html -->
<div class="followed-artists">
  <!-- Rendered artist cards with stats -->
</div>
```

**Image Handling**: Uses `ImageRef.url` for CDN/cached image URLs (not direct Spotify URLs).

**Error Handling**:
- `401`: Not authenticated with Spotify
- `503`: Spotify provider disabled
- `500`: Sync errors (with rollback)

**Source**: `automation_followed_artists.py:51-118`

---

### 24. Bulk Create Watchlists

**Endpoint**: `POST /automation/followed-artists/watchlists/bulk`

**Purpose**: Create watchlists for multiple artists at once (batch operation).

**Request Body**:
```json
{
  "artist_ids": [
    "spotify:artist:3WrFJ7ztbogyGnTHbHJFl2",
    "spotify:artist:6vWDO969PvNqNYHIOW5v0m"
  ],
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high"
}
```

**Behavior**:
- Skips artists with existing watchlists (logs info, no error)
- Continues processing on individual failures
- Commits all successful creates at end (atomic batch)
- Rollback on catastrophic failure

**Response**:
```json
{
  "total_requested": 50,
  "created": 42,
  "failed": 8,
  "failed_artists": [
    "spotify:artist:invalid-uri",
    "spotify:artist:another-failed-id"
  ]
}
```

**Source**: `automation_followed_artists.py:123-165`

---

### 25. Preview Followed Artists

**Endpoint**: `GET /automation/followed-artists/preview?limit=50`

**Purpose**: Lightweight preview of Spotify followed artists WITHOUT syncing to database (first page only).

**Query Parameters**:
- `limit` (int, default 50, max 50): Number of artists to fetch

**Authentication**: Uses shared Spotify token (`get_spotify_token_shared`)

**Behavior**:
- Fetches first page from Spotify API
- NO database operations
- Uses `SpotifyClient` directly (not plugin)

**Response**:
```json
{
  "artists": [...],
  "next": "cursor-for-next-page",
  "total": 250
}
```

**Use Case**: Quick preview before full sync (avoid 100+ artist sync if user only has 5 followed).

**Source**: `automation_followed_artists.py:170-187`

---

## Architecture Notes

### Modular Design

**Refactoring History** (Dec 2025):
- **Before**: Monolithic `automation.py` with ~1285 lines of duplicated code
- **After**: Aggregator pattern with 6 specialized sub-routers
- **Benefit**: Maintainability, testability, clear separation of concerns

**Sub-Router Organization**:
```python
# automation.py (aggregator)
router.include_router(watchlists_router)         # Watchlist CRUD + check releases
router.include_router(discography_router)        # Discography completeness
router.include_router(quality_upgrades_router)   # Quality upgrade candidates
router.include_router(filters_router)            # Download filter rules
router.include_router(rules_router)              # Workflow automation rules
router.include_router(followed_artists_router)   # Spotify followed artists sync
```

**Source**: `automation.py:28-38`

---

### HTMX Support

**Partial Response Pattern**:
- `automation_followed_artists.py` supports HTMX partial responses
- Detection: `request.headers.get("HX-Request") == "true"`
- Returns: Jinja2 template response with `Content-Type: text/html; charset=utf-8`
- Use Case: Dynamic UI updates without full page reload

**Example**:
```python
# automation_followed_artists.py:95-108
if is_htmx:
    return templates.TemplateResponse(
        request,
        "partials/followed_artists_list.html",
        context={...},
        headers={"Content-Type": "text/html; charset=utf-8"},
    )
```

---

### Multi-Provider Integration

**Deezer Fallback**:
- Followed artists sync uses DeezerPlugin for metadata enrichment
- **NO AUTH REQUIRED** for Deezer public API
- Graceful fallback if Spotify metadata incomplete

**Source**: `automation_followed_artists.py:74-78`

---

### Background Worker Integration

**Automation Features** (executed by background workers):
- Watchlist periodic checks (based on `check_frequency_hours`)
- Discography sync (updates `spotify_albums` table)
- Quality upgrade detection
- Filter rule application during downloads
- Workflow rule execution (trigger → action)

**Coordination**: Background workers call automation services directly (not via HTTP endpoints).

---

## Performance Considerations

### Pagination

**Limit/Offset Pattern**:
- Used for watchlists, filters, rules
- **Warning**: For datasets >1000 items, consider cursor-based pagination to avoid missing rows when data changes between fetches

**Source**: `automation_watchlists.py:97` (comment about pagination issues)

---

### Batch Operations

**Bulk Watchlist Creation**:
- Atomic commit (all-or-nothing for batch)
- Individual failures logged but don't halt processing
- Returns detailed success/failure stats

**Optimization Opportunity**: Could implement true batch SQL inserts for large artist lists (current: N individual INSERTs).

---

### Database Transactions

**Transaction Scopes**:
- Individual endpoints: Single commit per request
- Bulk operations: Commit after all individual creates
- Error handling: Rollback on exceptions

**Pattern**:
```python
try:
    # ... service operations ...
    await session.commit()
except Exception as e:
    await session.rollback()
    raise HTTPException(...)
```

---

## Security Considerations

### Provider Authentication

**Spotify OAuth Check Pattern**:
```python
from soulspot.application.services.app_settings_service import AppSettingsService
from soulspot.domain.ports.plugin import PluginCapability

app_settings = AppSettingsService(session)
if not await app_settings.is_provider_enabled("spotify"):
    raise HTTPException(status_code=503, detail="Spotify provider disabled")
if not spotify_plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
    raise HTTPException(status_code=401, detail="Not authenticated with Spotify")
```

**Endpoints Requiring Auth**:
- Watchlist check releases
- Followed artists sync/preview

**Public Endpoints** (No Auth):
- Watchlist CRUD (local operations)
- Discography checks (uses DB cache)
- Quality upgrades (local analysis)
- Filter/rule CRUD (local operations)

---

### Destructive Operations

**Permanent Deletions** (NO SOFT DELETE):
- `DELETE /automation/watchlist/{watchlist_id}`
- `DELETE /automation/filters/{filter_id}`
- `DELETE /automation/rules/{rule_id}`

**Warning**: No undo mechanism - implement confirmation dialogs in UI.

---

## Testing Recommendations

### Unit Tests

**Mock Points**:
- `WatchlistService`, `DiscographyService`, `QualityUpgradeService`, etc.
- `SpotifyPlugin.can_use()` for auth checks
- `AppSettingsService.is_provider_enabled()` for provider checks

**Test Cases**:
- Invalid artist ID formats (ValueError from `ArtistId.from_string()`)
- Provider disabled scenarios
- Authentication failures
- Bulk operation partial failures
- HTMX vs JSON response detection

---

### Integration Tests

**Scenarios**:
- End-to-end watchlist workflow (create → check → download)
- Bulk watchlist creation with mixed valid/invalid artist IDs
- HTMX partial response rendering
- Filter rule priority ordering
- Workflow rule trigger → action execution

---

## Common Pitfalls

### 1. Forgetting Provider Checks

**Wrong**:
```python
# Assumes Spotify always available
releases = await spotify_plugin.get_artist_albums(artist_id)
```

**Right**:
```python
if not await app_settings.is_provider_enabled("spotify"):
    raise HTTPException(status_code=503, detail="Spotify disabled")
if not spotify_plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
    raise HTTPException(status_code=401, detail="Not authenticated")
releases = await spotify_plugin.get_artist_albums(artist_id)
```

---

### 2. Pagination at Scale

**Issue**: Limit/offset pagination can miss rows if data changes between page fetches (e.g., new watchlist created while user paginating).

**Solution**: Implement cursor-based pagination for >1000 watchlists.

---

### 3. Bulk Operation Error Handling

**Issue**: One failed artist_id shouldn't halt entire bulk watchlist creation.

**Solution**: Current implementation continues on individual failures, logs errors, returns detailed stats.

---

### 4. HTMX Response Format

**Issue**: Returning JSON when HTMX expects HTML (or vice versa).

**Solution**: Check `HX-Request` header and return appropriate format:
```python
is_htmx = request.headers.get("HX-Request") == "true"
if is_htmx:
    return templates.TemplateResponse(...)
return JSONResponse(...)
```

---

## Related Documentation

- **Services**: `WatchlistService`, `DiscographyService`, `QualityUpgradeService`, `FilterService`, `AutomationWorkflowService`, `FollowedArtistsService`
- **Entities**: `Watchlist`, `FilterRule`, `AutomationRule` (see `src/soulspot/domain/entities/`)
- **Background Workers**: `docs/architecture/BACKGROUND_WORKERS.md`
- **Multi-Provider Patterns**: `docs/architecture/CORE_PHILOSOPHY.md` Section 3

---

**Validation Status**: ✅ All 28 endpoints validated against source code (6 sub-routers analyzed)
