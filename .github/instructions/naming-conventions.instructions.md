---
description: 'Naming conventions for functions, parameters, and constructors in SoulSpot'
applyTo: '**/*.py'
---

# Naming Conventions

## 🎯 Quick Reference

**The 5 Critical Rules:**

1. **Service-Specific Naming** → `fetch_spotify_artist()` NOT `fetch_artist()`
2. **Operation Prefixes** → `get_*` (DB), `fetch_*` (API), `create_*` (write)
3. **Constructor Order** → `session`, `service_plugin`, optional dependencies
4. **Async for I/O** → Network/DB = `async def`, Pure functions = `def`
5. **Named Arguments** → Always use at call-sites: `Service(session=s, plugin=p)`

| Context | Rule | Example |
|---------|------|---------|
| **Function** | Verb + Noun | `sync_playlist_tracks()` |
| **Service-Specific** | Include service name | `spotify_plugin`, NOT `plugin` |
| **Boolean Param** | Use `is_*`, `has_*`, `should_*` | `is_exact_match=True` |
| **Constructor** | `session` first, then plugins | `__init__(session, spotify_plugin)` |
| **Private** | Underscore prefix | `self._session`, `_normalize()` |
| **Workers** | Get `db`, not `session` | `Worker(db=db, settings=...)` |

---

## Core Philosophy

**Names are contracts.** A developer reading a function call should understand:
1. **What it does** (action)
2. **What it returns** (if applicable)
3. **What it affects** (side-effects: DB writes, API calls, state mutations)

---

## General Naming Rules

### 1. Use Descriptive Verb-Noun Combinations

✅ **CORRECT:**
```python
async def fetch_artist_from_spotify(artist_id: str) -> Artist:
async def sync_playlist_tracks(playlist_id: str) -> None:
async def enrich_track_metadata(track: Track) -> Track:
```

❌ **WRONG:**
```python
async def get_data(id: str):  # Too vague
async def do_sync():  # What is being synced?
async def process(item):  # Process how?
```

### 2. Prefix by Operation Type

| Prefix | Meaning | Side-Effects | Returns |
|--------|---------|-------------|---------|
| `get_*` | Fetch existing data | **None** (read-only) | Entity/DTO or None |
| `fetch_*` | Retrieve from external API | **API call** (network) | Entity/DTO |
| `create_*` | Insert new record | **DB write** | Created entity |
| `update_*` | Modify existing record | **DB write** | Updated entity |
| `delete_*` | Remove record | **DB write** | None or bool |
| `sync_*` | Synchronize external → local | **DB write + API** | Summary DTO |
| `enrich_*` | Add metadata/details | **May write** | Enriched entity |
| `process_*` | Complex multi-step operation | **May write** | Result DTO |
| `validate_*` | Check data validity | **None** (pure) | bool or raises |
| `check_*` | Boolean query | **None** (read-only) | bool |
| `build_*` | Construct object | **None** (pure) | New object |
| `calculate_*` | Pure computation | **None** (pure) | Computed value |
| `list_*` | Get collection | **None** (read-only) | List[Entity] |
| `count_*` | Get count | **None** (read-only) | int |

**Examples:**
```python
# Read-only queries (no side-effects)
async def get_track_by_id(track_id: int) -> Track | None:
async def list_artists(limit: int = 50) -> list[Artist]:
async def count_pending_downloads() -> int:

# External API calls (network side-effect)
async def fetch_spotify_playlist(playlist_id: str) -> SpotifyPlaylistDTO:
async def fetch_musicbrainz_metadata(isrc: str) -> MusicBrainzDTO:

# Database writes (state mutation)
async def create_track(track_data: TrackCreateDTO) -> Track:
async def update_download_status(download_id: int, status: str) -> None:
async def delete_playlist(playlist_id: int) -> bool:

# Complex operations (multiple side-effects)
async def sync_spotify_library() -> LibrarySyncResult:
async def enrich_track_metadata(track: Track) -> Track:
async def process_download_queue() -> DownloadProcessingResult:

# Pure functions (no side-effects, no async)
def calculate_audio_fingerprint(file_path: Path) -> str:
def validate_isrc_format(isrc: str) -> bool:
def build_search_query(artist: str, title: str) -> str:
```

### 3. Service-Specific Naming (MANDATORY for Multi-Provider Support)

When a function is tied to ONE specific service (Spotify, Tidal, Deezer), **MUST include service name**:

✅ **CORRECT:**
```python
async def fetch_spotify_artist(artist_id: str) -> SpotifyArtistDTO:
async def sync_deezer_favorites() -> DeezerSyncResult:
async def get_tidal_playlist_tracks(playlist_id: str) -> list[TidalTrackDTO]:
```

❌ **WRONG:**
```python
async def fetch_artist(artist_id: str):  # Which service?
async def sync_favorites():  # Ambiguous
async def get_playlist_tracks(id: str):  # Generic
```

**When to use service prefix:**
- OAuth/Auth operations → `authenticate_spotify_user()`, `refresh_deezer_token()`
- API client methods → `SpotifyClient.fetch_playlist()`, `DeezerClient.search_tracks()`
- Service-specific sync → `sync_spotify_library()`, `sync_tidal_playlists()`
- Plugin/adapter implementations → `SpotifyPlugin.get_new_releases()`

**When NOT to use service prefix:**
- Domain entities → `Track`, `Artist`, `Album` (service-agnostic)
- Generic utilities → `normalize_artist_name()`, `parse_isrc()`
- Multi-service aggregation → `search_all_providers()`, `get_aggregated_releases()`

---

## Layer-Specific Patterns

### API Layer (Routes)

**Pattern:** Action verb matching HTTP method

```python
# GET endpoints - use list_* or get_*
@router.get("/tracks")
async def list_tracks() -> list[TrackDTO]:

@router.get("/tracks/{track_id}")
async def get_track(track_id: int) -> TrackDTO:

# POST endpoints - use create_* or add_*
@router.post("/tracks")
async def create_track(data: TrackCreateDTO) -> TrackDTO:

# PUT/PATCH endpoints - use update_*
@router.patch("/tracks/{track_id}")
async def update_track(track_id: int, data: TrackUpdateDTO) -> TrackDTO:

# DELETE endpoints - use delete_* or remove_*
@router.delete("/tracks/{track_id}")
async def delete_track(track_id: int) -> None:

# Complex operations - use action verbs
@router.post("/playlists/{playlist_id}/sync")
async def sync_playlist(playlist_id: int) -> SyncResultDTO:
```

### Application Layer (Services)

**Pattern:** Business operation names (use cases)

```python
class TrackService:
    # Queries (read-only)
    async def get_track_by_isrc(self, isrc: str) -> Track | None:
    async def list_all_tracks(self, limit: int = 100) -> list[Track]:
    async def find_duplicates(self) -> list[DuplicateCandidate]:
    
    # Commands (write operations)
    async def import_spotify_track(self, spotify_uri: str) -> Track:
    async def enrich_track_metadata(self, track: Track) -> Track:
    async def merge_duplicate_tracks(self, keep_id: int, remove_id: int) -> Track:
    
    # Complex workflows
    async def sync_all_playlists() -> PlaylistSyncResult:
    async def process_pending_enrichments() -> EnrichmentResult:
```

### Domain Layer (Entities)

**Pattern:** Domain-driven, business-focused names

```python
class Track:
    # Factories (class methods)
    @classmethod
    def from_spotify(cls, spotify_dto: SpotifyTrackDTO) -> "Track":
    
    @classmethod
    def from_musicbrainz(cls, mb_dto: MusicBrainzDTO) -> "Track":
    
    # Business logic (instance methods)
    def calculate_similarity(self, other: "Track") -> float:
    def is_duplicate_of(self, other: "Track") -> bool:
    def needs_enrichment(self) -> bool:
    
    # Properties (read-only computed values)
    @property
    def spotify_id(self) -> str | None:
    
    @property
    def display_title(self) -> str:
```

### Infrastructure Layer (Repositories)

**Pattern:** Database operation names

```python
class TrackRepository:
    # CRUD operations
    async def get_by_id(self, track_id: int) -> Track | None:
    async def get_by_isrc(self, isrc: str) -> Track | None:
    async def create(self, track: Track) -> Track:
    async def update(self, track: Track) -> Track:
    async def delete(self, track_id: int) -> None:
    
    # Collection queries
    async def list_all(self, limit: int = 100) -> list[Track]:
    async def find_by_artist(self, artist_id: int) -> list[Track]:
    async def search_by_title(self, title: str) -> list[Track]:
    
    # Aggregations
    async def count_all() -> int:
    async def count_by_status(self, status: str) -> int:
    
    # Bulk operations
    async def create_many(self, tracks: list[Track]) -> list[Track]:
    async def delete_many(self, track_ids: list[int]) -> int:
```

---

## Async/Await Naming

### Rule: Use `async def` for ALL I/O operations

✅ **CORRECT:**
```python
async def fetch_from_api(url: str) -> dict:  # Network I/O
async def save_to_database(entity: Entity) -> None:  # DB I/O
async def read_file_async(path: Path) -> str:  # File I/O
```

❌ **WRONG:**
```python
def fetch_from_api(url: str) -> dict:  # Blocks event loop!
async def calculate_hash(data: bytes) -> str:  # Pure computation, doesn't need async
```

### Rule: Pure functions SHOULD NOT be async

```python
# ✅ CORRECT - Pure computation, no I/O
def normalize_artist_name(name: str) -> str:
def validate_isrc(isrc: str) -> bool:
def calculate_similarity(a: str, b: str) -> float:

# ❌ WRONG - Unnecessary async overhead
async def normalize_artist_name(name: str) -> str:
```

---

## Parameter Naming

### 1. Use Full Words (No Abbreviations)

✅ **CORRECT:**
```python
def fetch_artist(artist_id: str, include_albums: bool = False):
def sync_playlist(playlist_id: int, force_refresh: bool = False):
```

❌ **WRONG:**
```python
def fetch_artist(art_id: str, inc_alb: bool = False):
def sync_playlist(pl_id: int, force: bool = False):
```

### 2. Boolean Parameters: Use `is_*`, `has_*`, `should_*`

✅ **CORRECT:**
```python
def search_tracks(query: str, is_exact_match: bool = False):
def process_queue(should_skip_errors: bool = True):
def validate_track(track: Track, has_metadata: bool = False):
```

❌ **WRONG:**
```python
def search_tracks(query: str, exact: bool = False):
def process_queue(skip: bool = True):
```

### 3. Collections: Plural Names

✅ **CORRECT:**
```python
def process_tracks(tracks: list[Track]):
def merge_artists(artist_ids: list[int]):
```

❌ **WRONG:**
```python
def process_tracks(track_list: list[Track]):
def merge_artists(artist_id_array: list[int]):
```

---

## Return Type Naming

### 1. DTO Suffix for Data Transfer Objects

✅ **CORRECT:**
```python
class SpotifyTrackDTO:
class LibrarySyncResultDTO:
class DownloadStatusDTO:
```

### 2. Result/Response Suffix for Complex Returns

✅ **CORRECT:**
```python
class PlaylistSyncResult:
    synced_count: int
    failed_count: int
    errors: list[str]

class SearchResponse:
    results: list[Track]
    total_count: int
    page: int
```

---

## Common Anti-Patterns

### ❌ WRONG: Generic Names

```python
def process():  # Process what?
def handle_data():  # Handle how?
def do_stuff():  # What stuff?
def manager():  # Manages what?
```

### ❌ WRONG: Misleading Names

```python
async def get_user():  # Sounds read-only, but actually creates user if not exists
async def fetch_playlist():  # Sounds like API call, but only queries DB
def validate_track():  # Sounds pure, but actually modifies track
```

### ❌ WRONG: Inconsistent Prefixes

```python
# Mixing styles in same module
async def fetch_artist():
async def get_album():
async def retrieve_track():  # Pick ONE: fetch, get, or retrieve
```

---

## Private vs Public Functions

### Public Functions (API)
**Must be:** Clear, stable, well-documented

```python
async def sync_spotify_library() -> LibrarySyncResult:
    """Sync user's Spotify library to local database.
    
    Returns:
        LibrarySyncResult with counts and errors.
    """
```

### Private Functions (Helpers)
**Can be:** More concise, implementation-focused

```python
async def _fetch_page(offset: int) -> list[Track]:
    """Helper: Fetch single page from Spotify API."""

def _normalize_name(name: str) -> str:
    """Helper: Lowercase and strip whitespace."""
```

**Rule:** Use `_` prefix for internal helpers that should not be called directly.

---

## Function Signature Examples

### Multi-Service Aggregation Pattern

```python
async def search_all_providers(
    query: str,
    limit_per_provider: int = 20,
    include_spotify: bool = True,
    include_deezer: bool = True,
    include_tidal: bool = True,
) -> AggregatedSearchResult:
    """Search across multiple music providers and aggregate results.
    
    Args:
        query: Search query string
        limit_per_provider: Max results per provider
        include_spotify: Enable Spotify search
        include_deezer: Enable Deezer search
        include_tidal: Enable Tidal search
    
    Returns:
        AggregatedSearchResult with deduplicated tracks and source tags.
    """
```

### Repository Pattern

```python
async def find_by_criteria(
    self,
    artist_name: str | None = None,
    album_title: str | None = None,
    year: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Track]:
    """Find tracks matching given criteria.
    
    Args:
        artist_name: Filter by artist (case-insensitive)
        album_title: Filter by album (case-insensitive)
        year: Filter by release year
        limit: Max results to return
        offset: Pagination offset
    
    Returns:
        List of matching tracks, ordered by created_at DESC.
    """
```

---

## Examples: Before/After

### Example 1: Vague → Clear

❌ **BEFORE:**
```python
async def process(id: str):
    data = await api.get(id)
    db.save(data)
    return data
```

✅ **AFTER:**
```python
async def sync_spotify_artist(spotify_artist_id: str) -> Artist:
    """Fetch artist from Spotify API and save to local database.
    
    Args:
        spotify_artist_id: Spotify artist ID (not URI)
    
    Returns:
        Newly synced Artist entity.
    """
    artist_dto = await self.spotify_client.fetch_artist(spotify_artist_id)
    artist = Artist.from_spotify(artist_dto)
    return await self.artist_repo.create(artist)
```

### Example 2: Generic → Service-Specific

❌ **BEFORE:**
```python
async def get_favorites():
    return await client.favorites()
```

✅ **AFTER:**
```python
async def fetch_deezer_user_favorites() -> list[DeezerTrackDTO]:
    """Fetch current user's favorite tracks from Deezer API.
    
    Requires:
        User must be authenticated (valid Deezer token).
    
    Returns:
        List of Deezer track DTOs.
    """
    return await self.deezer_client.get_user_favorites()
```

### Example 3: Side-Effect Confusion → Explicit

❌ **BEFORE:**
```python
async def get_playlist(playlist_id: int):  # Sounds read-only
    # Actually creates playlist if not exists!
    playlist = await db.get(playlist_id)
    if not playlist:
        playlist = await db.create({"id": playlist_id})
    return playlist
```

✅ **AFTER:**
```python
async def get_or_create_playlist(playlist_id: int) -> Playlist:
    """Get playlist by ID, creating it if it doesn't exist.
    
    Side-effects:
        May insert new record into database.
    
    Args:
        playlist_id: Playlist ID to fetch/create
    
    Returns:
        Existing or newly created Playlist entity.
    """
    playlist = await self.playlist_repo.get_by_id(playlist_id)
    if not playlist:
        playlist = await self.playlist_repo.create(Playlist(id=playlist_id))
    return playlist
```

---

## Final Rule: Names Are Contracts

A function name is a promise to the caller:
- **What it does** (verb: fetch, create, sync)
- **What it affects** (target: artist, playlist, library)
- **What it returns** (type: Artist, SyncResult, bool)

If a function name doesn't tell the whole story, **rename it**.

---

## Parameter & Constructor Naming

### Constructor Parameter Order

**ALWAYS use this order:**

```python
def __init__(
    self,
    # 1. Database Session (required)
    session: AsyncSession,
    
    # 2. Service-specific Plugins (required)
    spotify_plugin: "SpotifyPlugin",  # Service-Name as prefix!
    
    # 3. Other required Dependencies
    token_manager: DatabaseTokenManager,
    
    # 4. Optional Dependencies (with Default)
    image_service: "ArtworkService | None" = None,
    settings_service: "AppSettingsService | None" = None,
) -> None:
```

### Database Session Parameter

**Standard:** `session` (NOT `db_session`, NOT `_session`)

```python
# ✅ CORRECT
def __init__(self, session: AsyncSession) -> None:
    self._session = session  # Internal with underscore

# ❌ WRONG
def __init__(self, db_session: AsyncSession) -> None:
def __init__(self, _session: AsyncSession) -> None:
```

**Reason:** 
- Consistent with SQLAlchemy conventions
- Shorter and unambiguous
- `db_session` is redundant (we know it's DB)

### Plugin Parameter Naming

**RULE:** Plugin parameters MUST have the service name as prefix!

```python
# ✅ CORRECT - Service-specific
class SpotifySyncService:
    def __init__(self, session: AsyncSession, spotify_plugin: "SpotifyPlugin"):
        self._plugin = spotify_plugin  # Internal can be generic

class DeezerSyncService:
    def __init__(self, session: AsyncSession, deezer_plugin: "DeezerPlugin"):
        self._plugin = deezer_plugin

class ProviderSyncOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin",
        deezer_plugin: "DeezerPlugin",
    ):
        self._spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin

# ❌ WRONG - too generic
class DeezerSyncService:
    def __init__(self, session: AsyncSession, plugin: "DeezerPlugin"):  # WRONG!
```

**Reason:**
- Prevents confusion in multi-provider services
- Call-site is self-documenting: `DeezerSyncService(session=s, deezer_plugin=p)`
- IDE autocomplete shows the correct plugin type

### Internal vs. External Attributes

**RULE:** Internal attributes with underscore prefix

```python
class MyService:
    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin",
        public_config: dict,  # Should be public
    ) -> None:
        # Private (only used internally)
        self._session = session
        self._plugin = spotify_plugin
        
        # Public (API for external usage)
        self.config = public_config
```

**Convention:**
| Access | Naming | Example |
|--------|--------|---------|
| Private | `self._name` | `self._session`, `self._plugin` |
| Public | `self.name` | `self.config`, `self.stats` |
| Protected | `self._name` | (Python has no protected, use private) |

### Optional Dependencies

**RULE:** Optional = `Type | None` with `default=None`

```python
# ✅ CORRECT
def __init__(
    self,
    session: AsyncSession,
    image_service: "ArtworkService | None" = None,
) -> None:
    self._image_service = image_service

# ❌ WRONG - no default
def __init__(
    self,
    session: AsyncSession,
    image_service: "ArtworkService | None",  # Missing: = None
) -> None:

# ❌ WRONG - Optional[T] instead of T | None (deprecated style)
def __init__(
    self,
    session: AsyncSession,
    image_service: Optional[ArtworkService] = None,  # Use: Type | None
) -> None:
```

### Worker Parameter Pattern

**RULE:** Workers get `db: Database` (not `session`)

```python
# ✅ CORRECT - Worker gets Database for own sessions
class DeezerSyncWorker:
    def __init__(
        self,
        db: "Database",  # Database instance, not Session!
        settings: "Settings",
        check_interval_seconds: int = 60,
    ) -> None:
        self.db = db  # Public because worker needs it for session_scope
        self._settings = settings
        self.check_interval_seconds = check_interval_seconds

# ❌ WRONG - Worker shouldn't get single session
class BadWorker:
    def __init__(self, session: AsyncSession):  # WRONG!
        # Worker runs long, session can expire!
```

**Reason:**
- Workers run for extended periods
- Sessions can expire or get recycled by pool
- Workers create their own sessions via `db.session_scope()`

### Service Parameter Matrix

| Service Type | session | plugin | other |
|--------------|---------|--------|-------|
| **SpotifySyncService** | `session` | `spotify_plugin` | `image_service=None` |
| **DeezerSyncService** | `session` | `deezer_plugin` | - |
| **ProviderOrchestrator** | `session` | `spotify_plugin`, `deezer_plugin` | `settings_service=None` |
| **AppSettingsService** | `session` | - | - |
| **Workers** | - | - | `db`, `settings` |

### Call-Site Examples

**ALWAYS use named arguments with 2+ parameters:**

```python
# ✅ CORRECT - Named arguments
service = DeezerSyncService(
    session=session,
    deezer_plugin=plugin,
)

worker = DeezerSyncWorker(
    db=db,
    settings=settings,
    check_interval_seconds=60,
)

# ❌ WRONG - Positional arguments
service = DeezerSyncService(session, plugin)  # Unclear!
worker = DeezerSyncWorker(db, settings, 60)   # What is 60?
```

### TYPE_CHECKING Import Pattern

**For forward references:**

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

class MyService:
    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin",  # String annotation!
    ) -> None:
```

### Constructor Checklist

- [ ] `session: AsyncSession` as first parameter
- [ ] Plugin with service prefix: `spotify_plugin`, `deezer_plugin`
- [ ] Optional dependencies at the end with `= None`
- [ ] Internal attributes with `_` prefix
- [ ] TYPE_CHECKING for forward references
- [ ] Named arguments at call-sites

### Complete Service Example

```python
"""Example service following naming conventions."""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

---

## Verification Checklist

**Before committing code, verify:**

### Functions
- [ ] Name reveals intent (verb-noun pattern)
- [ ] Side-effects clear from name (`get_*` vs `fetch_*` vs `create_*`)
- [ ] Service prefix used if service-specific
- [ ] `async def` for ALL I/O operations
- [ ] Pure functions are NOT async
- [ ] Type hints on ALL parameters and return values
- [ ] Docstring explains what, why, edge cases

### Parameters
- [ ] Full words (no abbreviations)
- [ ] Boolean params use `is_*`, `has_*`, `should_*`
- [ ] Collections use plural names

### Constructors
- [ ] `session: AsyncSession` as first parameter
- [ ] Plugin with service prefix: `spotify_plugin`, `deezer_plugin`
- [ ] Optional dependencies at end with `= None`
- [ ] Internal attributes with `_` prefix
- [ ] TYPE_CHECKING for forward references
- [ ] Named arguments at call-sites

### Returns
- [ ] Return type has meaningful name (DTO/Result suffix)
- [ ] Private helpers use `_` prefix
    Hey future me - this service follows the naming conventions!
    See .github/instructions/naming-conventions.instructions.md for details.
    """
    
    def __init__(
        self,
        # 1. Database session (required)
        session: AsyncSession,
        # 2. Service-specific plugin (required)
        spotify_plugin: "SpotifyPlugin",
        # 3. Optional dependencies
        artwork_service: "ArtworkService | None" = None,
    ) -> None:
        """Initialize album service.
        
        Args:
            session: Database session
            spotify_plugin: SpotifyPlugin for API calls
            artwork_service: Optional service for downloading artwork
        """
        # Private attributes with underscore
        self._session = session
        self._plugin = spotify_plugin
        self._artwork_service = artwork_service
    
    async def get_album(self, album_id: str) -> dict:
        """Get album by ID."""
        return await self._plugin.get_album(album_id)
```

---

## See Also

- `.github/instructions/architecture.instructions.md` - Layer rules and dependency flow
- `.github/instructions/python.instructions.md` - General Python conventions
- `docs/architecture/CORE_PHILOSOPHY.md` - Multi-service aggregation patterns
