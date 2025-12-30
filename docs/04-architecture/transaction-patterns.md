# Transaction Management Patterns

**Category:** Architecture  
**Status:** ENFORCED ✅  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Data Layer Patterns](./data-layer-patterns.md)

---

## The Golden Rule

```
Who starts the operation commits it.
```

**In Practice:**
- **Routes (simple CRUD):** Route commits
- **Services (complex operations):** Service commits
- **Use Cases (orchestrated flows):** Use Case commits

**NEVER:**
- ❌ Route starts, Service commits, Route commits again
- ❌ Multiple Services commit in same request
- ❌ Repository commits (Repos are data access only)

---

## When Who Commits?

### Pattern A: Route Commits (Simple CRUD)

For simple operations where route directly calls one service method:

```python
# src/soulspot/api/routers/artists.py

@router.delete("/artists/{artist_id}")
async def delete_artist(
    artist_id: UUID,
    session: AsyncSession = Depends(get_session),
    service: ArtistService = Depends(get_artist_service),
) -> dict[str, str]:
    """Delete an artist - simple operation."""
    await service.delete(artist_id)  # Service does NOT commit
    await session.commit()  # Route commits
    return {"status": "deleted"}
```

```python
# src/soulspot/application/services/artist_service.py

class ArtistService:
    async def delete(self, artist_id: UUID) -> None:
        """Delete artist from database.
        
        Note: Does NOT commit - caller is responsible for commit.
        """
        artist = await self._repo.get_by_id(artist_id)
        if not artist:
            raise EntityNotFoundError(f"Artist not found: {artist_id}")
        
        await self._repo.delete(artist)
        # NO commit here!
```

**When Route Commits:**
- ✅ Simple CRUD (create, read, update, delete)
- ✅ Single service method called
- ✅ No complex orchestration

---

### Pattern B: Service Commits (Complex Operations)

For complex operations with multiple repository calls:

```python
# src/soulspot/application/services/playlist_sync_service.py

class PlaylistSyncService:
    async def sync_playlist(self, playlist_id: UUID) -> SyncResultDTO:
        """Sync playlist with Spotify - complex operation.
        
        This method:
        1. Fetches playlist from Spotify
        2. Updates local playlist metadata
        3. Syncs all tracks
        4. Updates sync timestamp
        
        Note: This method COMMITS because it's a unit of work.
        """
        playlist = await self._playlist_repo.get_by_id(playlist_id)
        if not playlist:
            raise EntityNotFoundError(f"Playlist not found: {playlist_id}")
        
        # Multiple operations as one unit of work
        spotify_data = await self._spotify.get_playlist(playlist.spotify_id)
        await self._update_metadata(playlist, spotify_data)
        await self._sync_tracks(playlist, spotify_data["tracks"])
        await self._update_sync_timestamp(playlist)
        
        # Service commits - this is a unit of work
        await self._session.commit()
        
        return SyncResultDTO(
            playlist_id=playlist_id,
            tracks_added=self._tracks_added,
            tracks_removed=self._tracks_removed,
        )
```

```python
# src/soulspot/api/routers/playlists.py

@router.post("/playlists/{playlist_id}/sync")
async def sync_playlist(
    playlist_id: UUID,
    service: PlaylistSyncService = Depends(get_playlist_sync_service),
) -> SyncResultResponse:
    """Sync playlist with Spotify."""
    result = await service.sync_playlist(playlist_id)  # Service commits internally
    # NO commit here - service already committed
    return result
```

**When Service Commits:**
- ✅ Multiple repository calls as atomic operation
- ✅ External API calls + DB updates together
- ✅ "All or nothing" semantics desired

---

### Pattern C: Use Case Commits (Orchestrated Flows)

For orchestrated flows with multiple services:

```python
# src/soulspot/application/use_cases/import_artist_use_case.py

class ImportArtistUseCase:
    """Import artist from Spotify including all albums and tracks.
    
    This is a complex use case that coordinates multiple services.
    The use case owns the transaction.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        artist_service: ArtistService,
        album_service: AlbumService,
        track_service: TrackService,
        spotify_plugin: SpotifyPlugin,
    ):
        self._session = session
        self._artist_service = artist_service
        self._album_service = album_service
        self._track_service = track_service
        self._spotify = spotify_plugin
    
    async def execute(self, spotify_artist_id: str) -> ImportResultDTO:
        """Execute the import - this owns the transaction."""
        try:
            # 1. Import artist
            artist = await self._artist_service.import_from_spotify(spotify_artist_id)
            
            # 2. Import all albums
            albums = await self._spotify.get_artist_albums(spotify_artist_id)
            for album_data in albums:
                await self._album_service.import_from_spotify(album_data)
            
            # 3. Import all tracks
            for album in albums:
                tracks = await self._spotify.get_album_tracks(album["id"])
                for track_data in tracks:
                    await self._track_service.import_from_spotify(track_data)
            
            # Use Case commits - this is the transaction boundary
            await self._session.commit()
            
            return ImportResultDTO(
                artist_id=artist.id,
                albums_imported=len(albums),
                status="success",
            )
        
        except Exception as e:
            await self._session.rollback()
            raise
```

**When Use Case Commits:**
- ✅ Multiple services orchestrated
- ✅ Complex business flow
- ✅ Explicit transaction boundaries needed

---

## Repository: NEVER Commit!

Repositories are data access layer only - they NEVER commit:

```python
# ✅ RIGHT: Repository without commit
class ArtistRepository:
    async def create(self, artist: Artist) -> Artist:
        """Create artist in database.
        
        Note: Does NOT commit. Caller must commit.
        """
        self._session.add(artist)
        await self._session.flush()  # flush is OK - makes data visible
        return artist
    
    async def delete(self, artist: Artist) -> None:
        """Delete artist from database.
        
        Note: Does NOT commit. Caller must commit.
        """
        await self._session.delete(artist)
        # NO commit!


# ❌ WRONG: Repository with commit
class ArtistRepository:
    async def create(self, artist: Artist) -> Artist:
        self._session.add(artist)
        await self._session.commit()  # ❌ NEVER!
        return artist
```

---

## Session Lifecycle

### Dependency Injection Pattern

```python
# src/soulspot/api/dependencies.py

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for request scope.
    
    Session is automatically rolled back if no commit happened.
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            # Rollback uncommitted changes (safety net)
            await session.rollback()
```

---

### Request Scope = Transaction Scope

```
Request Start
    │
    ▼
Session Created (Dependency)
    │
    ▼
Route/Service/UseCase Operations
    │
    ▼
Commit (explicit) OR Rollback (on error/no commit)
    │
    ▼
Session Closed
    │
    ▼
Request End
```

**Key Points:**
- Session lives for entire request
- Uncommitted changes auto-rollback on request end
- Explicit commit required to persist changes

---

## Flush vs Commit

| Operation | What Happens | When to Use |
|-----------|--------------|-------------|
| `flush()` | Writes to DB, still in transaction | Generate IDs, check constraints |
| `commit()` | Makes changes permanent | End of operation |
| `rollback()` | Discards all changes | On errors |

### Example: Flush for ID Generation

```python
async def create_artist_with_albums(self, artist_data, albums_data):
    """Create artist and albums in one transaction."""
    artist = Artist(**artist_data)
    self._session.add(artist)
    await self._session.flush()  # Artist gets ID generated
    
    for album_data in albums_data:
        album = Album(**album_data, artist_id=artist.id)  # ID available!
        self._session.add(album)
    
    await self._session.commit()  # Commit everything together
```

**Why Flush?**
- Database generates `artist.id` after INSERT
- Need that ID to create related albums
- Flush writes artist, makes ID available, but keeps transaction open

---

## Error Handling with Transactions

### Pattern: Try-Commit-Except-Rollback

```python
# Service or Use Case
async def complex_operation(self, data: dict) -> Result:
    """Complex operation with transaction handling."""
    try:
        # Multiple operations
        artist = await self._create_artist(data["artist"])
        album = await self._create_album(data["album"], artist.id)
        tracks = await self._create_tracks(data["tracks"], album.id)
        
        # All succeeded - commit
        await self._session.commit()
        
        return Result(success=True, artist_id=artist.id)
    
    except ValidationError as e:
        # Validation failed - rollback
        await self._session.rollback()
        raise InvalidInputError(str(e))
    
    except DatabaseError as e:
        # DB error - rollback
        await self._session.rollback()
        raise OperationFailedError(f"Database error: {e}")
    
    except Exception as e:
        # Unknown error - rollback
        await self._session.rollback()
        logger.exception("Unexpected error in complex_operation")
        raise
```

---

### Nested Transactions (AVOID!)

**Problem:**
```python
# ❌ WRONG - nested commits/rollbacks get confusing
async def outer_operation():
    await inner_operation()
    await self._session.commit()  # What if inner already committed?

async def inner_operation():
    # Do stuff
    await self._session.commit()  # Now outer commit will fail!
```

**Solution:**
```python
# ✅ RIGHT - only ONE layer commits
async def outer_operation():
    """Only this commits."""
    await inner_operation()  # Inner does NOT commit
    await self._session.commit()

async def inner_operation():
    """No commit - caller will commit."""
    # Do stuff
    # NO commit here!
```

---

## Common Patterns

### CRUD Route Pattern

```python
@router.post("/artists")
async def create_artist(
    artist_data: ArtistCreate,
    session: AsyncSession = Depends(get_session),
    repo: ArtistRepository = Depends(get_artist_repository),
) -> ArtistResponse:
    """Create artist - route commits."""
    artist = Artist(**artist_data.dict())
    await repo.create(artist)  # Repo does NOT commit
    await session.commit()  # Route commits
    return ArtistResponse.from_entity(artist)
```

---

### Complex Service Pattern

```python
class SpotifySyncService:
    async def sync_followed_artists(self) -> SyncResult:
        """Sync followed artists - service commits."""
        followed = await self._spotify.get_followed_artists()
        
        synced = []
        for artist_dto in followed.items:
            artist = await self._import_artist(artist_dto)
            synced.append(artist)
        
        # Service commits - atomic sync
        await self._session.commit()
        
        return SyncResult(synced_count=len(synced))
```

---

### Use Case Pattern

```python
class ImportPlaylistUseCase:
    async def execute(self, playlist_url: str) -> ImportResult:
        """Import playlist - use case commits."""
        try:
            # Multiple service calls
            playlist_data = await self._spotify.get_playlist(playlist_url)
            playlist = await self._playlist_service.create(playlist_data)
            
            for track_data in playlist_data["tracks"]:
                await self._track_service.import_track(track_data, playlist.id)
            
            # Use case commits - owns transaction
            await self._session.commit()
            
            return ImportResult(playlist_id=playlist.id, success=True)
        
        except Exception as e:
            await self._session.rollback()
            return ImportResult(success=False, error=str(e))
```

---

## Anti-Patterns to Avoid

### ❌ Double Commit

```python
# WRONG!
async def route():
    await service.do_something()  # Service commits
    await session.commit()  # Route commits again - ERROR!
```

**Error:** `InvalidRequestError: This session is in 'committed' state`

---

### ❌ Repository Commits

```python
# WRONG!
class ArtistRepository:
    async def create(self, artist):
        self._session.add(artist)
        await self._session.commit()  # Repository should NOT commit!
```

**Why wrong?** Breaks transaction boundaries, prevents atomic multi-repo operations.

---

### ❌ No Commit at All

```python
# WRONG!
@router.post("/artists")
async def create_artist(artist_data, repo):
    await repo.create(Artist(**artist_data))
    # Forgot to commit!
    return {"status": "created"}
```

**Result:** Data not persisted, rolled back when session closes.

---

### ❌ Commit in Loop

```python
# WRONG!
async def import_many_artists(artists_data):
    for data in artists_data:
        artist = Artist(**data)
        await self._repo.create(artist)
        await self._session.commit()  # Commits each one - slow!
```

**Better:**
```python
# RIGHT!
async def import_many_artists(artists_data):
    for data in artists_data:
        artist = Artist(**data)
        await self._repo.create(artist)
    
    await self._session.commit()  # One commit at end - fast!
```

---

## Verification Checklist

Before committing code with DB operations:

- [ ] **Who commits?** Route, Service, or Use Case - but only ONE
- [ ] **Repository commits?** NO - repositories never commit
- [ ] **Error handling?** try/except with rollback on error
- [ ] **Flush needed?** Only if need generated ID for related entities
- [ ] **Nested commits?** Avoid - only outermost layer commits
- [ ] **Loop commits?** Avoid - commit once after loop
- [ ] **Session scope?** Matches request scope (dependency injection)

---

## Related Documentation

- **[Data Layer Patterns](./data-layer-patterns.md)** - Repository patterns and best practices
- **[Service Separation Principles](./service-separation-principles.md)** - Service responsibility boundaries

---

**Status:** ✅ ENFORCED - Code review blocks violations  
**Priority:** CRITICAL - Violating these patterns causes data corruption  
**Training:** All developers must understand before touching database code
