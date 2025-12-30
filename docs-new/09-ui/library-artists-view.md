# Library + Followed Artists View

**Category:** UI/UX Design / Feature  
**Status:** ✅ Design Approved  
**Last Updated:** 2025-12-30  
**Related:** [Library Management](../07-library/README.md), [UI Architecture](./ui-architecture-principles.md), [Plugin System](../02-architecture/plugin-system.md)

---

## Overview

Unified library view showing **local + remote tracked artists** with availability indicators (Lidarr-style).

### Hybrid Concept

The Library view combines:
- **Local Artists** (100% downloaded)
- **Followed Artists** from Spotify/Tidal/Deezer (partially or not downloaded)
- **Availability Indicators** (Lidarr-style progress bars)

**Key Principle:** User sees everything they care about, regardless of local availability.

## Visual Design

### Artist Card (Grid View)

```
┌──────────────────────────────────┐
│ [🎵 Spotify]      Pink Floyd     │  ← Service badge (top-left)
│                                  │
│  [Album Cover Grid 2x2]         │  ← 4 album covers
│                                  │
│  ████████████░░░░ 80%            │  ← Progress bar (green/yellow/red)
│  16/20 Albums • 180/225 Tracks  │  ← Stats
│                                  │
│  [⬇ Download Missing]            │  ← Quick action (if <100%)
└──────────────────────────────────┘
```

**Color States:**

| Completeness | Border Color | Status |
|--------------|--------------|--------|
| 100% | Green | ✅ Complete |
| 50-99% | Yellow | ⚠️ Partial |
| 0-49% | Red | ❌ Mostly missing |

### Artist Card (List View)

```
[🎵] Pink Floyd      ████████░░ 80%    16/20 Albums    [⬇ Download Missing]
[🎵] The Beatles     ██████████ 100%   13/13 Albums    
[🎵] Radiohead       ████░░░░░░ 40%    6/15 Albums     [⬇ Download Missing]
```

## Progress Bar Design

### Visual Representation

```
Complete (100%):
████████████████████ 100%  (All tracks downloaded)

Partial (60%):
████████████░░░░░░░░ 60%   (12/20 albums)

Missing (0%):
░░░░░░░░░░░░░░░░░░░░ 0%    (No local files)

Queued (download in progress):
████████████▶▶▶▶░░░░ 60% ⏳ (3 downloads active)
```

### Color Coding

| Completeness | Bar Color | Border Color | Status |
|--------------|-----------|--------------|--------|
| 100% | `#10b981` (green) | Green | ✅ Complete |
| 75-99% | `#eab308` (yellow) | Yellow | ⚠️ Almost Complete |
| 50-74% | `#f59e0b` (orange) | Orange | ⚠️ Partial |
| 1-49% | `#ef4444` (red) | Red | ❌ Mostly Missing |
| 0% | `#6b7280` (gray) | Gray | ❌ No Local Files |

### CSS Implementation

```css
.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.progress-complete { background: #10b981; }
.progress-almost { background: #eab308; }
.progress-partial { background: #f59e0b; }
.progress-low { background: #ef4444; }
.progress-none { background: #6b7280; }
```

## Service Badges

**Location:** Top-left corner of artist card

**Design:**

```html
<span class="badge badge-spotify">
  <i class="bi-spotify"></i> Spotify
</span>
```

**Badge Colors:**

| Service | Color | Icon |
|---------|-------|------|
| Spotify | `#1db954` | `bi-spotify` |
| Tidal | `#00d9ff` | `bi-music-note` |
| Deezer | `#ff9900` | `bi-disc` |
| Local | `#6b7280` | `bi-folder` |

**Badge Behavior:**

- **Click:** Filter library by this service
- **Hover:** Show tooltip "Followed on Spotify since [date]"
- **Multiple services:** Badge shows count (e.g., "2 services"), hover shows list

## Filter Bar

**Location:** Top of library view (below search bar)

```html
<div class="filter-bar">
  <button class="filter-btn active">All (420)</button>
  <button class="filter-btn">Local (250)</button>
  <button class="filter-btn">Remote (170)</button>
  <button class="filter-btn">Incomplete ⚠️ (120)</button>
  
  <div class="service-filters">
    <label>Services:</label>
    <button class="service-badge badge-spotify">🎵 Spotify</button>
    <button class="service-badge badge-tidal">🎵 Tidal</button>
    <button class="service-badge badge-deezer">🎵 Deezer</button>
  </div>
</div>
```

**Filter Logic:**

| Filter | Shows |
|--------|-------|
| **All** | All artists (local + followed) |
| **Local** | Artists with 100% completeness |
| **Remote** | Followed artists with 0% local files |
| **Incomplete** | Artists with 1-99% completeness (action needed) |

**Service Filters:**

- Combine with completeness filters (e.g., "Incomplete Spotify Artists")
- Multi-select: Show artists from Spotify OR Tidal

## Quick Actions

### "Download Missing" Button

**Visible when:** Completeness < 100%

**Action:**

```python
# Queue all missing albums for download
async def download_missing_artist(artist_id: str):
    artist = await artist_repo.get_by_id(artist_id)
    missing_albums = await find_missing_albums(artist)
    
    for album in missing_albums:
        await download_service.queue_album(album.id)
    
    return {"queued": len(missing_albums)}
```

**Confirmation:** "Queue 4 albums (58 tracks) for download?"

### Context Menu (Right-click)

```html
<div class="context-menu">
  <button hx-post="/api/artists/{{ artist.id }}/download-all">
    ⬇ Download All
  </button>
  <button hx-post="/api/artists/{{ artist.id }}/download-missing">
    📥 Download Missing Albums
  </button>
  <button hx-post="/api/artists/{{ artist.id }}/monitor">
    🔔 Monitor New Releases
  </button>
  <button hx-get="/api/artists/{{ artist.id }}/stats">
    📊 View Statistics
  </button>
  <hr>
  <button onclick="window.open('https://open.spotify.com/artist/{{ artist.spotify_id }}')">
    🔗 Open in Spotify
  </button>
  <hr>
  <button hx-delete="/api/artists/{{ artist.id }}/unfollow" class="text-danger">
    ❌ Unfollow Artist
  </button>
</div>
```

## Implementation Example

### Jinja2 Template

```jinja2
{% macro artist_card_hybrid(artist, completeness, service) %}
<article class="artist-card" 
         data-artist-id="{{ artist.id }}" 
         data-completeness="{{ completeness }}"
         style="border-color: {{ get_border_color(completeness) }}">
  
  {# Service badge #}
  <span class="badge badge-{{ service }}">
    <i class="icon-{{ service }}"></i> {{ service|title }}
  </span>
  
  {# Artist info #}
  <img src="{{ artist.image_url }}" alt="{{ artist.name }}" class="artist-image">
  <h3>{{ artist.name }}</h3>
  
  {# Progress bar #}
  <div class="progress-bar">
    <div class="progress-bar-fill progress-{{ get_progress_class(completeness) }}"
         style="width: {{ completeness }}%"></div>
  </div>
  <p class="stats">
    {{ completeness }}% • {{ artist.album_count }} Albums • {{ artist.track_count }} Tracks
  </p>
  
  {# Quick action #}
  {% if completeness < 100 %}
  <button class="btn btn-primary btn-sm" 
          hx-post="/api/artists/{{ artist.id }}/download-missing">
    ⬇ Download Missing
  </button>
  {% endif %}
</article>
{% endmacro %}
```

### Python Service

```python
async def get_artist_library_view(
    service: str | None = None,
    completeness_filter: str | None = None
) -> list[ArtistLibraryView]:
    """
    Get hybrid library view with local + followed artists
    """
    artists = await artist_repo.get_all()
    
    result = []
    for artist in artists:
        # Calculate completeness
        total_albums = await get_total_albums(artist.id)
        local_albums = await get_local_albums(artist.id)
        completeness = (local_albums / total_albums * 100) if total_albums > 0 else 0
        
        # Apply filters
        if service and artist.service != service:
            continue
        if completeness_filter == "local" and completeness < 100:
            continue
        if completeness_filter == "remote" and completeness > 0:
            continue
        if completeness_filter == "incomplete" and (completeness == 0 or completeness == 100):
            continue
        
        result.append({
            "artist": artist,
            "completeness": completeness,
            "service": artist.service
        })
    
    return result
```

## Related Documentation

- [Library Management](../07-library/README.md) - Library system overview
- [UI Architecture](./ui-architecture-principles.md) - Component patterns
- [Plugin System ADR](../02-architecture/plugin-system.md) - Hybrid library concept
- [Component Library](./component-library.md) - UI components
