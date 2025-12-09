# ⚠️ DEPRECATED - SoulSpot UI Integration Guide

> **Status:** ❌ DEPRECATED  
> **Replaced By:** [feat-ui-pro.md](./feat-ui-pro.md) Phase 2-4 (incremental component migration) + [SERVICE_AGNOSTIC_STRATEGY.md](./SERVICE_AGNOSTIC_STRATEGY.md) (component naming)  
> **Date Deprecated:** 9. Dezember 2025  
> **Reason:** Generic integration steps. New docs provide specific migration path with service-agnostic naming and backwards compatibility strategy.

**DO NOT USE THIS FILE. See [feat-ui-pro.md](./feat-ui-pro.md) for current integration strategy.**

---

<details>
<summary>Original Content (Archived)</summary>

This guide details the process of integrating the new UI prototype (located in `docs/feat-ui/prototype/`) into the main SoulSpot application (`src/soulspot/`).

## 📋 Migration Strategy: Complete Rebuild

We are adopting a **Complete Rebuild Strategy**. This means we are **not** running the old and new UI in parallel. Instead, we are replacing the frontend entirely, page by page.

### Why this approach?
- **Clean Slate**: Allows us to implement new architecture without legacy constraints.
- **New Features**: Enables new flows like Onboarding that didn't exist before.
- **Simplicity**: Avoids the complexity of maintaining two UI codebases simultaneously.

### The Process
1. **Prepare Backend**: Ensure API endpoints are ready for the new frontend.
2. **Replace Templates**: Overwrite old templates with new ones from the prototype.
3. **Add New Pages**: Implement completely new pages (e.g., Onboarding) that have no equivalent in the old UI.
4. **Verify**: Test the new flow immediately.

---

## 1. Asset Migration

### Static Files
Completely replace the existing static assets or add the new ones alongside if needed for admin tools, but the main UI will use the new assets exclusively.

```bash
# Source
docs/feat-ui/prototype/static/new-ui/

# Destination
src/soulspot/static/new-ui/
```

**Action Items:**
- Copy `css/` folder (variables.css, main.css, components.css, ui-components.css)
- Copy `js/` folder (app.js)
- Ensure `src/soulspot/main.py` mounts the static directory correctly.

### Templates
Move the HTML templates to the application's templates directory.

```bash
# Source
docs/feat-ui/prototype/templates/new-ui/

# Destination
src/soulspot/templates/new-ui/
```

**Action Items:**
- Copy `base.html`
- Copy `pages/` directory
- Update template inheritance paths if necessary (currently set to `new-ui/base.html`, which should work if the folder structure is preserved).

---

## 2. Backend Implementation

You need to create FastAPI routes to serve these templates. It is recommended to create a new router file `src/soulspot/routes/ui.py`.

### Route Structure

#### Main Routes
```python
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Data needed:
    # - stats (playlists, tracks, downloads, queue)
    # - recent_playlists
    # - activity_feed
    # - spotify_connected (bool)
    return templates.TemplateResponse("new-ui/pages/dashboard.html", {
        "request": request,
        "stats": {...},
        "recent_playlists": [...],
        ...
    })

@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    return templates.TemplateResponse("new-ui/pages/search.html", {"request": request})
```

#### Library Routes
```python
@router.get("/library/artists", response_class=HTMLResponse)
async def library_artists(request: Request):
    # Data needed: artists list, pagination info
    return templates.TemplateResponse("new-ui/pages/library-artists.html", {...})

@router.get("/library/albums", response_class=HTMLResponse)
async def library_albums(request: Request):
    # Data needed: albums list, pagination info
    return templates.TemplateResponse("new-ui/pages/library-albums.html", {...})

@router.get("/library/tracks", response_class=HTMLResponse)
async def library_tracks(request: Request):
    # Data needed: tracks list, pagination info
    return templates.TemplateResponse("new-ui/pages/library-tracks.html", {...})
```

#### Detail Routes
```python
@router.get("/library/artists/{artist_id}", response_class=HTMLResponse)
async def artist_detail(request: Request, artist_id: str):
    # Data needed: artist details, albums, popular tracks
    return templates.TemplateResponse("new-ui/pages/artist-detail.html", {...})

@router.get("/library/albums/{album_id}", response_class=HTMLResponse)
async def album_detail(request: Request, album_id: str):
    # Data needed: album details, tracks
    return templates.TemplateResponse("new-ui/pages/album-detail.html", {...})

@router.get("/playlists/{playlist_id}", response_class=HTMLResponse)
async def playlist_detail(request: Request, playlist_id: str):
    # Data needed: playlist details, tracks
    return templates.TemplateResponse("new-ui/pages/playlist-detail.html", {...})
```

---

## 3. API & HTMX Integration

The prototype uses HTMX for dynamic interactions. You need to implement the API endpoints referenced in the HTML `hx-*` attributes.

### Search API
- **Endpoint**: `/api/search`
- **Method**: GET
- **Params**: `q` (query), `filter` (type)
- **Returns**: HTML partial (search results)

### Library Actions
- **Endpoint**: `/api/library/artists/search`
- **Endpoint**: `/api/library/albums/search`
- **Endpoint**: `/api/library/tracks/search`
- **Returns**: HTML partials (grids/tables)

### Player/Download Actions
- **Endpoint**: `/api/player/play/{id}` (POST)
- **Endpoint**: `/api/downloads/add/{id}` (POST)
- **Endpoint**: `/api/downloads/queue` (GET - for polling)

### Import Actions
- **Endpoint**: `/api/playlists/import` (POST)
- **Endpoint**: `/api/playlists/sync-all` (POST)

---

## 4. Data Models

Ensure your Jinja2 templates receive objects with these attributes:

**Artist**:
- `id`, `name`, `image_url`, `album_count`, `track_count`

**Album**:
- `id`, `name`, `artist`, `cover_url`, `year`, `track_count`, `downloaded` (bool)

**Track**:
- `id`, `title`, `artist`, `album`, `duration`, `downloaded` (bool), `status` (enum)

**Playlist**:
- `id`, `name`, `cover_url`, `track_count`, `downloaded` (bool), `owner`

---

## 5. Migration Checklist

- [ ] Copy static files to `src/soulspot/static/new-ui/`
- [ ] Copy templates to `src/soulspot/templates/new-ui/`
- [ ] Create `src/soulspot/routes/ui.py`
- [ ] Register new router in `main.py`
- [ ] Implement Dashboard route & data
- [ ] Implement Library routes & data
- [ ] Implement Detail routes & data
- [ ] Implement Search API
- [ ] Implement Download/Queue API
- [ ] Verify all HTMX calls work with real backend
- [ ] Remove old UI files (after verification)

---

**Note**: The prototype HTML files currently contain some mock data logic (Jinja2 `if` statements). When integrating, replace these with actual variables passed from FastAPI.
