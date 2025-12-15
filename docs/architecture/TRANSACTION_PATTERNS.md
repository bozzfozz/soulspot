# SoulSpot Transaction Management Standards

> **PFLICHTLEKTÜRE** für alle, die mit Datenbank-Sessions arbeiten.

---

## 1. Die goldene Regel

```
Wer die Operation startet, committet auch.
```

**In der Praxis:**
- **Routes (einfache CRUD)**: Route committet
- **Services (komplexe Operationen)**: Service committet
- **Use Cases (orchestrierte Flows)**: Use Case committet

**NIEMALS:**
- ❌ Route startet, Service committet, Route committet nochmal
- ❌ Mehrere Services committen in derselben Request
- ❌ Repository committet (Repos sind nur Data Access)

---

## 2. Wann committet wer?

### Pattern A: Route Commits (Simple CRUD)

Für einfache Operationen, wo die Route direkt einen Service aufruft:

```python
# src/soulspot/api/routers/artists.py

@router.delete("/artists/{artist_id}")
async def delete_artist(
    artist_id: UUID,
    session: AsyncSession = Depends(get_session),
    service: ArtistService = Depends(get_artist_service),
) -> dict[str, str]:
    """Delete an artist - simple operation."""
    await service.delete(artist_id)  # Service macht KEIN commit
    await session.commit()  # Route committet
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
        # KEIN commit hier!
```

**Wann Route committet:**
- ✅ Einfache CRUD (create, read, update, delete)
- ✅ Einzelne Service-Methode aufgerufen
- ✅ Keine komplexe Orchestrierung

---

### Pattern B: Service Commits (Complex Operations)

Für komplexe Operationen mit mehreren Repository-Aufrufen:

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
        
        # Service committet - das ist ein Unit of Work
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
    result = await service.sync_playlist(playlist_id)  # Service committet intern
    # KEIN commit hier - Service hat schon committed
    return result
```

**Wann Service committet:**
- ✅ Mehrere Repository-Aufrufe als atomare Operation
- ✅ Externe API-Calls + DB-Updates zusammen
- ✅ "All or nothing" Semantik gewünscht

---

### Pattern C: Use Case Commits (Orchestrated Flows)

Für orchestrierte Flows mit mehreren Services:

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
            
            # Use Case committet - das ist die Transaktionsgrenze
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

**Wann Use Case committet:**
- ✅ Mehrere Services orchestriert
- ✅ Komplexer Business-Flow
- ✅ Explizite Transaktionsgrenzen nötig

---

## 3. Repository: NIEMALS committen!

Repositories sind nur Data Access Layer - sie committen NIE:

```python
# ✅ RICHTIG: Repository ohne commit
class ArtistRepository:
    async def create(self, artist: Artist) -> Artist:
        """Create artist in database.
        
        Note: Does NOT commit. Caller must commit.
        """
        self._session.add(artist)
        await self._session.flush()  # flush ist OK - macht Daten sichtbar
        return artist
    
    async def delete(self, artist: Artist) -> None:
        """Delete artist from database.
        
        Note: Does NOT commit. Caller must commit.
        """
        await self._session.delete(artist)
        # KEIN commit!


# ❌ FALSCH: Repository mit commit
class ArtistRepository:
    async def create(self, artist: Artist) -> Artist:
        self._session.add(artist)
        await self._session.commit()  # ❌ NIEMALS!
        return artist
```

---

## 4. Session Lifecycle

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

---

## 5. Flush vs Commit

| Operation | Was passiert | Wann verwenden |
|-----------|--------------|----------------|
| `flush()` | Schreibt zu DB, aber noch in Transaktion | IDs generieren, Constraints prüfen |
| `commit()` | Macht Änderungen permanent | Am Ende der Operation |
| `rollback()` | Verwirft alle Änderungen | Bei Fehlern |

```python
# Beispiel: flush für ID-Generierung
async def create_artist_with_albums(self, artist_data, albums_data):
    artist = Artist(**artist_data)
    self._session.add(artist)
    await self._session.flush()  # Artist bekommt ID
    
    for album_data in albums_data:
        album = Album(**album_data, artist_id=artist.id)  # ID verfügbar!
        self._session.add(album)
    
    await self._session.commit()  # Alles zusammen committen
```

---

## 6. Error Handling mit Transactions

```python
# Pattern: Try/Except mit explizitem Rollback
async def complex_operation(self) -> ResultDTO:
    try:
        # Multiple operations
        await self._step_1()
        await self._step_2()
        await self._step_3()
        
        await self._session.commit()
        return ResultDTO(status="success")
    
    except EntityNotFoundError:
        await self._session.rollback()
        raise  # Re-raise domain exception
    
    except Exception as e:
        await self._session.rollback()
        logger.exception(f"Unexpected error: {e}")
        raise BusinessRuleViolation(f"Operation failed: {e}")
```

---

## 7. Nested Operations

Wenn Service A Service B aufruft:

```python
# ❌ FALSCH: Beide committen
class ServiceA:
    async def operation_a(self):
        await self._service_b.operation_b()  # B committet intern
        await self._session.commit()  # A committet auch → Problem!

# ✅ RICHTIG: Nur der äußere committet
class ServiceA:
    async def operation_a(self):
        """Owner der Transaktion."""
        await self._service_b.operation_b()  # B committet NICHT
        await self._session.commit()  # Nur A committet

class ServiceB:
    async def operation_b(self):
        """Nicht Owner - kein commit."""
        # ... DB operations ...
        # KEIN commit - wird von caller gemacht
```

**Regel:** Der "äußerste" Aufrufer committet. Innere Services committen nie.

---

## 8. Background Tasks / Workers

Workers haben eigene Sessions und eigene Transaktionsgrenzen:

```python
class TokenRefreshWorker:
    async def _run_loop(self):
        while not self._stop_event.is_set():
            # Jeder Durchlauf = eigene Session
            async with async_session_maker() as session:
                try:
                    await self._refresh_tokens(session)
                    await session.commit()  # Commit pro Durchlauf
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Token refresh failed: {e}")
            
            await asyncio.sleep(300)  # 5 Minuten
```

---

## 9. Checkliste: Wer committet?

| Szenario | Wer committet? |
|----------|----------------|
| Simple CRUD (GET, POST, PUT, DELETE) | Route |
| Service mit mehreren Repo-Aufrufen | Service |
| Use Case mit mehreren Services | Use Case |
| Background Worker | Worker (pro Iteration) |
| Nested Service Calls | Nur der äußerste |

---

## 10. Anti-Patterns

### ❌ Double Commit
```python
# FALSCH
async def sync_playlist(self):
    await self._service.sync()  # Service committet
    await self._session.commit()  # Route committet nochmal
```

### ❌ Repository Commit
```python
# FALSCH
class TrackRepository:
    async def create(self, track):
        self._session.add(track)
        await self._session.commit()  # Repos committen NIE!
```

### ❌ Commit ohne Error Handling
```python
# FALSCH
async def operation(self):
    await self._step_1()
    await self._step_2()
    await self._session.commit()  # Was wenn step_2 failed?
```

### ❌ Forget to Commit
```python
# FALSCH
@router.post("/artists")
async def create_artist(data: ArtistCreate):
    artist = await service.create(data)
    return artist  # Vergessen zu committen!
```

---

## 11. Debugging Transactions

```python
# Debug-Logging für Transactions
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# Zeigt alle SQL-Statements inkl. BEGIN/COMMIT/ROLLBACK
```

---

## 12. Zusammenfassung

```
┌─────────────────────────────────────────────────────────────────┐
│                         ROUTE LAYER                              │
│  • Committet bei einfachen CRUD-Operationen                     │
│  • Kein Commit wenn Service komplexe Operation macht            │
│  • Session kommt via Dependency Injection                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER                              │
│  • Committet bei komplexen Operationen (Unit of Work)           │
│  • Kein Commit bei einfachen Operationen (Route committet)      │
│  • Dokumentiert in Docstring ob committed wird                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REPOSITORY LAYER                             │
│  • Committet NIEMALS                                            │
│  • Verwendet flush() für ID-Generierung                         │
│  • Nur Data Access - keine Business Logic                       │
└─────────────────────────────────────────────────────────────────┘
```
