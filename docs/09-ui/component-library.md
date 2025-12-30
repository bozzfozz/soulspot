# Component Library

**Category:** UI/UX Design  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [UI Architecture](./ui-architecture-principles.md), [Design Guidelines](../08-ui-components/design-guidelines.md), [HTMX Patterns](../05-developer-guides/htmx-patterns.md)

---

## Overview

Comprehensive reference for all reusable UI components in SoulSpot following Atomic Design principles.

## Component Import

```jinja2
{% import "includes/macros.html" as macros %}
{% import "includes/_components.html" as components %}
```

## Layout Components

### Page Header

Top-level header with title, subtitle, and action buttons.

```jinja2
{% call macros.page_header("Library", subtitle="Browse your music collection") %}
  <button class="btn btn-primary">
    <i class="bi bi-plus"></i> Add Music
  </button>
{% endcall %}
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `title` | string | required | Page title |
| `subtitle` | string | None | Optional subtitle |
| `action_text` | string | None | Primary action button text |
| `action_url` | string | None | Action button URL |
| `action_icon` | string | None | Action button icon class |

### Section Header

Section divider with optional "View All" link.

```jinja2
{{ macros.section_header(
    "New Releases",
    subtitle="Fresh music from your favorite artists",
    view_all_url="/browse/new-releases"
) }}
```

### Media Grid

Responsive grid container for media cards.

```jinja2
{% call macros.media_grid(columns=5, gap='md') %}
    {{ macros.media_card(...) }}
    {{ macros.media_card(...) }}
{% endcall %}
```

**Responsive Breakpoints:**

| Screen Size | 5col | 4col | 3col | 2col |
|-------------|------|------|------|------|
| >1200px | 5 | 4 | 3 | 2 |
| 992-1200px | 4 | 4 | 3 | 2 |
| 768-992px | 3 | 3 | 3 | 2 |
| <768px | 2 | 2 | 2 | 2 |

## Data Display Components

### Media Card

Generic card for albums, artists, playlists, or tracks.

```jinja2
{{ macros.media_card(
    title="Dark Side of the Moon",
    subtitle="Pink Floyd",
    image="/images/albums/dsotm.jpg",
    href="/library/albums/pink-floyd-dark-side",
    type="album",
    status="downloaded",
    play_url="/api/queue/add?album_id=123"
) }}
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `title` | string | required | Display title |
| `subtitle` | string | None | Subtitle (artist name, etc.) |
| `image` | string | None | Image URL |
| `href` | string | None | Link URL |
| `type` | string | "album" | Type: `album`, `artist`, `playlist`, `track` |
| `status` | string | None | Badge: `downloaded`, `streaming` |
| `play_url` | string | None | HTMX endpoint for play button |

**Visual Features:**
- Hover: Card lifts with shadow
- Play button overlay on hover
- Circular image for `type="artist"`
- Status badge in top-right corner

### Artist Card

```jinja2
{{ macros.artist_card(
    name="Michael Jackson",
    image_url="/images/artists/mj.jpg",
    genre="Pop",
    stats="12 albums • 147 tracks",
    service="spotify"
) }}
```

**Service Badge Colors:**

| Service | Badge Color | Icon |
|---------|-------------|------|
| Spotify | Green `#1db954` | `bi-spotify` |
| Tidal | Cyan `#00d9ff` | `bi-music-note` |
| Deezer | Orange `#ff9900` | `bi-disc` |
| Local | Gray `#6b7280` | `bi-folder` |

### Album Card

```jinja2
{{ macros.album_card(
    title="Thriller",
    artist="Michael Jackson",
    year=1982,
    image="/images/albums/thriller.jpg",
    completeness=100,
    track_count=9
) }}
```

**Completeness Progress Bar:**

| Percentage | Color | Description |
|------------|-------|-------------|
| 100% | Green `#10b981` | ✅ Complete |
| 75-99% | Yellow `#eab308` | ⚠️ Almost complete |
| 50-74% | Orange `#f59e0b` | ⚠️ Partial |
| 1-49% | Red `#ef4444` | ❌ Mostly missing |
| 0% | Gray `#6b7280` | ❌ No local files |

## Forms & Inputs

### Text Input

```jinja2
{{ macros.input(
    name="artist_name",
    label="Artist Name",
    placeholder="Enter artist name...",
    required=True,
    icon="bi-search"
) }}
```

### Search Bar

```jinja2
{{ macros.search_bar(
    placeholder="Search tracks, artists, albums...",
    action_url="/api/search/quick",
    debounce=300
) }}
```

**HTMX Integration:**

```html
<input 
  type="search" 
  name="q"
  hx-get="/api/search/quick"
  hx-trigger="keyup changed delay:300ms"
  hx-target="#search-results">
```

### Select Dropdown

```jinja2
{{ macros.select(
    name="quality_profile",
    label="Quality Profile",
    options=[
        {"value": 1, "label": "Lossless"},
        {"value": 2, "label": "High Quality"},
        {"value": 3, "label": "Any Quality"}
    ],
    selected=1
) }}
```

### Checkbox

```jinja2
{{ macros.checkbox(
    name="monitored",
    label="Monitor for new releases",
    checked=True
) }}
```

## Feedback Components

### Toast Notification

```jinja2
{{ macros.toast(
    message="Track added to queue",
    type="success",
    duration=3000
) }}
```

**Types:**

| Type | Color | Icon |
|------|-------|------|
| `success` | Green | `bi-check-circle` |
| `error` | Red | `bi-exclamation-circle` |
| `warning` | Yellow | `bi-exclamation-triangle` |
| `info` | Blue | `bi-info-circle` |

### Progress Bar

```jinja2
{{ macros.progress_bar(
    current=75,
    total=100,
    label="Download Progress"
) }}
```

### Loading Skeleton

```jinja2
{{ macros.skeleton_card(count=5) }}
```

**Visual:**

```
┌──────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│  ← Shimmer animation
│ ▓▓▓▓▓▓▓░░░░░░░░░│
│ ▓▓▓░░░░░░░░░░░░░│
└──────────────────┘
```

## Navigation Components

### Tab Navigation

```jinja2
{{ macros.tabs(
    tabs=[
        {"id": "library", "label": "Library", "active": True},
        {"id": "playlists", "label": "Playlists"},
        {"id": "downloads", "label": "Downloads"}
    ]
) }}
```

### Breadcrumb

```jinja2
{{ macros.breadcrumb(
    items=[
        {"label": "Library", "url": "/library"},
        {"label": "Artists", "url": "/library/artists"},
        {"label": "Pink Floyd"}
    ]
) }}
```

### Pagination

```jinja2
{{ macros.pagination(
    current_page=3,
    total_pages=10,
    base_url="/library/artists"
) }}
```

## Specialized Components

### Download Queue Item

```jinja2
{{ macros.download_item(
    title="Bohemian Rhapsody",
    artist="Queen",
    status="downloading",
    progress=45,
    priority="high"
) }}
```

**Status States:**

| Status | Color | Icon |
|--------|-------|------|
| `pending` | Gray | `bi-clock` |
| `queued` | Blue | `bi-list-ul` |
| `downloading` | Yellow | `bi-arrow-down` |
| `completed` | Green | `bi-check-circle` |
| `failed` | Red | `bi-x-circle` |

### Filter Bar

```jinja2
{{ macros.filter_bar(
    filters=[
        {"type": "select", "name": "monitored", "label": "Monitored", "options": [...]},
        {"type": "search", "name": "search", "placeholder": "Filter by name..."}
    ]
) }}
```

### Action Menu (Dropdown)

```jinja2
{{ macros.action_menu(
    actions=[
        {"label": "Play", "icon": "bi-play", "url": "/api/play/123"},
        {"label": "Add to Queue", "icon": "bi-plus", "url": "/api/queue/add/123"},
        {"label": "Delete", "icon": "bi-trash", "class": "text-danger"}
    ]
) }}
```

## Animations

### Fade In

```css
.fade-in {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

### Slide Up

```css
.slide-up {
  animation: slideUp 0.4s ease-out;
}

@keyframes slideUp {
  from { 
    opacity: 0;
    transform: translateY(20px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}
```

### Shimmer (Loading)

```css
.shimmer {
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 0%,
    var(--bg-quaternary) 50%,
    var(--bg-tertiary) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
```

## Accessibility Patterns

### Focus Trap (Modals)

```javascript
class FocusTrap {
  constructor(element) {
    this.element = element;
    this.focusableElements = element.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select, [tabindex]:not([tabindex="-1"])'
    );
  }
  
  activate() {
    this.firstElement = this.focusableElements[0];
    this.lastElement = this.focusableElements[this.focusableElements.length - 1];
    this.firstElement.focus();
    this.element.addEventListener('keydown', this.handleKeydown.bind(this));
  }
  
  handleKeydown(e) {
    if (e.key !== 'Tab') return;
    
    if (e.shiftKey && document.activeElement === this.firstElement) {
      e.preventDefault();
      this.lastElement.focus();
    } else if (!e.shiftKey && document.activeElement === this.lastElement) {
      e.preventDefault();
      this.firstElement.focus();
    }
  }
}
```

### ARIA Labels

```html
<!-- Icon-only buttons MUST have aria-label -->
<button aria-label="Play track">
  <i class="bi-play-fill" aria-hidden="true"></i>
</button>

<!-- Links with icons need descriptive text -->
<a href="/library" aria-label="Go to library">
  <i class="bi-music-note" aria-hidden="true"></i>
  Library
</a>
```

## Related Documentation

- [UI Architecture](./ui-architecture-principles.md) - Design principles
- [HTMX Patterns](../05-developer-guides/htmx-patterns.md) - Interactive patterns
- [Design Guidelines](../08-ui-components/design-guidelines.md) - Visual standards
- [Accessibility Guide](./accessibility-guide.md) - WCAG 2.1 compliance
