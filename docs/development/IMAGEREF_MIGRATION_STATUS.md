# ImageRef Migration - Status

## Status: Phase 4 COMPLETED ✅

### Summary

Die ImageRef-Migration vereinheitlicht alle Artwork/Cover/Image-Felder:

| Entity | Field | DB Column (ALT) | DB Column (NEU) |
|--------|-------|-----------------|-----------------|
| Artist | `image: ImageRef` | `artwork_url` | `image_url` |
| Album | `cover: ImageRef` | `artwork_url`, `artwork_path` | `cover_url`, `cover_path` |
| Playlist | `cover: ImageRef` | `artwork_url` | `cover_url` |

---

## Phase 4: Database Column Renaming (COMPLETED ✅)

### Migration File
✅ `alembic/versions/yy36021aaB69_rename_to_imageref_naming.py`

### Model/Repository Updates ✅
- `ArtistModel`: `artwork_url` → `image_url`, `image_path` unchanged
- `AlbumModel`: `artwork_url` → `cover_url`, `artwork_path` → `cover_path`, `image_path` REMOVED (was redundant)
- `PlaylistModel`: `artwork_url` → `cover_url`
- All Repository mappings updated

### Service Updates ✅
- `discography_service.py`, `enrichment_service.py`, `library_view_service.py`, `automation_workers.py`
- `spotify_sync_service.py`, `deezer_sync_service.py`, `local_library_enrichment_service.py`

### UI Router Updates ✅
- All Model references in `ui.py` updated to new column names

### Bug Fixes Applied ✅
- Fixed undefined `sp_artist.artwork_url` → `sp_artist.image.url` in enrichment service
- Fixed undefined `sp_album.artwork_url` → `sp_album.cover.url` in enrichment service

### Nächste Schritte
1. ⏳ Migration: `alembic upgrade head`
2. ⏳ Live Test in Docker

---

## Completed Phases (1-3)

3. **Repository Layer Updates**
   - `ArtistRepository`: Model ↔ Entity Mapping mit ImageRef
   - `AlbumRepository`: Model ↔ Entity Mapping mit ImageRef
   - `PlaylistRepository`: Model ↔ Entity Mapping mit ImageRef

4. **Plugin Layer Updates**
   - `DeezerPlugin`: Erstellt DTOs mit ImageRef
   - `SpotifyPlugin`: Erstellt DTOs mit ImageRef

5. **API Layer**
   - `artists.py`, `search.py`, `ui.py`, `playlists.py`, `automation.py`, `automation_followed_artists.py`
   - Response Format bleibt kompatibel (flache Strings für Templates)

#### Phase 2 ✅

6. **Service Layer - Sync Services**
   - `spotify_sync_service.py`: Alle DTO-Zugriffe korrigiert (`artist_dto.image.url`, `album_dto.cover.url`, `playlist_dto.cover.url`)
   - `deezer_sync_service.py`: Alle DTO-Zugriffe korrigiert
   - Model-Zugriffe bleiben unverändert (`model.artwork_url`)

7. **Service Layer - Discover & Enrichment**
   - `discover_service.py`: DTO-Zugriffe korrigiert
   - `postprocessing/metadata_service.py`: Entity-Zugriffe korrigiert (`album.cover.url`)
   - `local_library_enrichment_service.py`: DTO-Zugriffe korrigiert

8. **Use Cases**
   - `import_spotify_playlist.py`: Entity/DTO-Zugriffe korrigiert
   - `enrich_metadata_multi_source.py`: DTO-Zugriffe korrigiert

#### Phase 3 ✅ (abgeschlossen: Dezember 2025)

9. **Verbleibende Services**
   - `watchlist_service.py`: DTO-Zugriffe korrigiert (`album.cover.url`)
   - `artwork_service.py`: DTO-Zugriffe korrigiert (`artist_dto.image.url`, `best_match.cover.url`)
   - `charts_service.py`: DTO-Zugriffe korrigiert (`dto.image.url`)

10. **Verifizierte Model-Zugriffe (KORREKT - unverändert)**
    - `discography_service.py`: `album.artwork_url` (AlbumModel)
    - `automation_workers.py`: `album.artwork_url` (AlbumModel)
    - `enrichment_service.py`: `artist.artwork_url`, `album.artwork_url` (ArtistModel, AlbumModel)

Diese bleiben unverändert, da sie DB-Spalten referenzieren:
- `model.artwork_url` - SQLAlchemy Model-Attribut
- `existing_model.artwork_url` - DB Update
- `AlbumModel.artwork_url.is_(None)` - SQLAlchemy Query

### API Response Format:

Die API Responses geben weiterhin flache Strings zurück:
```python
# Router gibt aus:
{
    "image_url": artist.image.url,  # Flacher String für Template
    "cover_url": album.cover.url,
}
```

## Mapping-Übersicht:

| Kontext | Alter Zugriff | Neuer Zugriff |
|---------|---------------|---------------|
| ArtistDTO | `dto.artwork_url` | `dto.image.url` |
| AlbumDTO | `dto.artwork_url` | `dto.cover.url` |
| PlaylistDTO | `dto.artwork_url` | `dto.cover.url` |
| TrackDTO.album | `dto.album.artwork_url` | `dto.album.cover.url` |
| Artist Entity | `artist.artwork_url` | `artist.image.url` |
| Album Entity | `album.artwork_url` | `album.cover.url` |
| Playlist Entity | `playlist.artwork_url` | `playlist.cover.url` |
| ArtistModel | `model.artwork_url` | **UNVERÄNDERT** |
| AlbumModel | `model.artwork_url` | **UNVERÄNDERT** |
| PlaylistModel | `model.artwork_url` | **UNVERÄNDERT** |

Templates erwarten weiterhin:
```html
<img src="{{ artist.image_url }}">
<img src="{{ album.artwork_url }}">
```

## Wichtige Hinweise:

1. **DB Spalten bleiben unverändert!**
   - `ArtistModel.artwork_url`, `ArtistModel.image_path`
   - `AlbumModel.artwork_url`, `AlbumModel.artwork_path`
   - `PlaylistModel.artwork_url`, `PlaylistModel.cover_path`

2. **Nur Python Code ändert sich:**
   - Entity Felder: `image`, `cover` (ImageRef)
   - DTO Felder: `image`, `cover` (ImageRef)
   - Repository Mapping: Model ↔ Entity

3. **Keine Migrationen nötig!**
   - DB Schema bleibt gleich
   - Nur Python-seitiges Mapping ändert sich
