# SoulSpot Component Library

**Version:** 1.0  
**Last Updated:** December 17, 2025

A comprehensive reference for all reusable UI components in SoulSpot.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Layout Components](#layout-components)
3. [Data Display](#data-display)
4. [Forms & Inputs](#forms--inputs)
5. [Feedback](#feedback)
6. [Navigation](#navigation)
7. [Specialized Components](#specialized-components)
8. [Animations](#animations)
9. [Accessibility](#accessibility)

---

## Getting Started

### Import Macros

```jinja2
{% import "includes/macros.html" as macros %}
{% import "includes/_components.html" as components %}
```

### CSS Files

All styles are loaded via `main.css` which imports:
- `variables.css` - Design tokens (colors, spacing, typography)
- `animations.css` - @keyframes and animation utilities
- `components.css` - Core layout and widget styles
- `ui-components.css` - Advanced UI components

---

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

---

### Section Header

Section divider with optional "View All" link.

```jinja2
{{ macros.section_header(
    "New Releases",
    subtitle="Fresh music from your favorite artists",
    view_all_url="/browse/new-releases"
) }}
```

**Output:**
```html
<div class="section-header">
    <div class="section-header-content">
        <h2>New Releases</h2>
        <p>Fresh music from your favorite artists</p>
    </div>
    <a href="/browse/new-releases">View All →</a>
</div>
```

---

### Media Grid

Responsive grid container for media cards. Auto-adjusts columns.

```jinja2
{% call macros.media_grid(columns=5, gap='md') %}
    {{ macros.media_card(...) }}
    {{ macros.media_card(...) }}
{% endcall %}
```

**Responsive Breakpoints:**
| Screen | 5col | 4col | 3col | 2col |
|--------|------|------|------|------|
| >1200px | 5 | 4 | 3 | 2 |
| 992-1200px | 4 | 4 | 3 | 2 |
| 768-992px | 3 | 3 | 3 | 2 |
| <768px | 2 | 2 | 2 | 2 |

---

## Data Display

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
    play_url="/api/queue/add?album_id=123",
    delay=0
) }}
```

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `title` | string | required | Display title |
| `subtitle` | string | None | Subtitle (e.g., artist name) |
| `image` | string | None | Image URL |
| `href` | string | None | Link URL |
| `type` | string | "album" | Type: `album`, `artist`, `playlist`, `track` |
| `status` | string | None | Status badge: `downloaded`, `streaming` |
| `play_url` | string | None | HTMX endpoint for play button |
| `delay` | int | 0 | Animation stagger delay (0-5) |
| `actions` | list | [] | Bottom action buttons |

**Visual Features:**
- Hover: Card lifts and shows shadow
- Play button overlay on hover
- Circular image for `type="artist"`
- Status badge in top-right corner
- Blur-fade-in entrance animation

---

### Track Row

Compact horizontal row for track lists.

```jinja2
{{ macros.track_row(
    number=1,
    title="Comfortably Numb",
    artist="Pink Floyd",
    duration="6:23",
    album="The Wall",
    image="/images/tracks/wall.jpg",
    play_url="/api/queue/add?track_id=123",
    download_url="/api/download/track/123",
    is_downloaded=true,
    is_playing=false
) }}
```

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `number` | int | required | Track number |
| `title` | string | required | Track title |
| `artist` | string | None | Artist name |
| `duration` | string | None | Duration (e.g., "4:32") |
| `album` | string | None | Album name (hidden on mobile) |
| `image` | string | None | Album art URL |
| `play_url` | string | None | HTMX play endpoint |
| `download_url` | string | None | HTMX download endpoint |
| `is_downloaded` | bool | false | Show downloaded badge |
| `is_playing` | bool | false | Highlight as currently playing |

**Visual Features:**
- Hover: Background highlight, show actions
- Play button replaces number on hover
- "..." button opens Bottom Sheet with options
- Responsive: Album column hidden on mobile

---

### Stat Card

Dashboard statistic display.

```jinja2
{{ macros.stat_card(
    label="Total Tracks",
    value="12,345",
    icon="bi bi-music-note",
    change_text="+142 this week",
    change_type="positive"
) }}
```

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `label` | string | required | Stat label |
| `value` | string | required | Stat value |
| `icon` | string | required | Icon class |
| `change_text` | string | None | Change indicator text |
| `change_type` | string | "neutral" | `positive`, `negative`, `neutral` |

---

### Badge

Inline status indicator.

```jinja2
{{ components.badge("Completed", type="success") }}
{{ components.badge("Pending", type="warning") }}
{{ components.badge("Failed", type="danger") }}
```

**Types:** `neutral`, `success`, `warning`, `danger`, `info`, `primary`

---

### Status Indicator

Pre-configured status badges for download states.

```jinja2
{{ components.status_indicator("downloading") }}
{{ components.status_indicator("completed") }}
{{ components.status_indicator("failed") }}
```

**Supported statuses:** `success`, `pending`, `queued`, `downloading`, `completed`, `failed`, `cancelled`

---

## Forms & Inputs

### Button Classes

```html
<button class="btn btn-primary">Primary</button>
<button class="btn btn-outline">Outline</button>
<button class="btn btn-ghost">Ghost</button>
<button class="btn btn-danger">Danger</button>

<!-- Sizes -->
<button class="btn btn-primary btn-sm">Small</button>
<button class="btn btn-primary btn-lg">Large</button>

<!-- Icon Button -->
<button class="btn-icon"><i class="bi bi-gear"></i></button>
```

### Form Inputs

```html
<input type="text" class="form-input" placeholder="Search...">
<select class="form-select">
    <option>Option 1</option>
</select>
<textarea class="form-textarea" rows="4"></textarea>
```

---

## Feedback

### Alert

Message banners for info, warnings, errors.

```jinja2
{{ components.alert(
    type="warning",
    title="Warning",
    message="Please connect your Spotify account",
    dismissible=true
) }}
```

**Types:** `info`, `success`, `warning`, `danger`

---

### Progress Bar

```jinja2
{{ components.progress_bar(
    value=75,
    max=100,
    label="Downloading...",
    show_percentage=true
) }}
```

---

### Empty State

Placeholder for empty content areas.

```jinja2
{{ components.empty_state(
    icon='<i class="bi bi-music-note-beamed" style="font-size: 3rem;"></i>',
    title="No tracks found",
    description="Try importing some music from Spotify",
    action_text="Connect Spotify",
    action_href="/settings#spotify"
) }}
```

---

## Navigation

### Tabs

Horizontal tab navigation.

```jinja2
{{ macros.tabs([
    {'id': 'tracks', 'label': 'Tracks', 'icon': 'bi-music-note', 'count': 142, 'active': true},
    {'id': 'albums', 'label': 'Albums', 'icon': 'bi-disc', 'count': 23},
    {'id': 'artists', 'label': 'Artists', 'icon': 'bi-person', 'count': 12}
]) }}

<div id="tab-tracks" class="tab-pane active">
    <!-- Track content -->
</div>
<div id="tab-albums" class="tab-pane">
    <!-- Album content -->
</div>
```

**Tab switching is handled by `app.js` automatically.**

---

### Breadcrumbs

```jinja2
{{ components.breadcrumb([
    {'text': 'Library', 'href': '/library'},
    {'text': 'Artists', 'href': '/library/artists'},
    {'text': 'Pink Floyd'}
]) }}
```

---

### Pagination

```jinja2
{{ components.pagination(
    current_page=3,
    total_pages=10,
    base_url="/library/tracks"
) }}
```

---

## Specialized Components

### Command Palette

Power-user search modal (Cmd+K / Ctrl+K).

**Included automatically in `base.html`.**

```javascript
// Open programmatically
SoulSpotCommandPalette.open();
SoulSpotCommandPalette.close();
```

**Features:**
- Fuzzy search across tracks, artists, albums, playlists
- Recent searches stored in localStorage
- Keyboard navigation (↑↓, Enter, Esc)
- WCAG accessible

---

### Bottom Sheet

Mobile-first action menu.

**Included automatically in `base.html`.**

```javascript
// Open with content
SoulSpotBottomSheet.open({
    title: 'Track Options',
    content: `
        <button class="bottom-sheet-action">Add to Queue</button>
        <button class="bottom-sheet-action">Add to Playlist</button>
    `
});

// Open with HTMX URL
SoulSpotBottomSheet.open({
    title: 'Track Options',
    contentUrl: '/partials/track-actions?id=123'
});
```

**HTML Triggers:**
```html
<!-- Via template ID -->
<button data-bottom-sheet-trigger="my-actions" data-bottom-sheet-title="Options">
    <i class="bi bi-three-dots"></i>
</button>
<template id="my-actions">
    <button class="bottom-sheet-action">Action 1</button>
</template>

<!-- Via URL -->
<button data-bottom-sheet-url="/partials/actions" data-bottom-sheet-title="Actions">
    More
</button>
```

**Features:**
- Slide-up animation on mobile
- Swipe down to close
- Falls back to modal on tablet/desktop
- iPhone safe area support

---

## Animations

### Entrance Animations

```html
<!-- Blur fade in -->
<div class="blur-fade-in" style="--delay: 0">Content</div>
<div class="blur-fade-in" style="--delay: 1">Delayed</div>

<!-- Slide from left -->
<div class="slide-from-left">Content</div>

<!-- Bounce in -->
<div class="bounce-in">Badge!</div>

<!-- Scroll reveal (needs JS intersection observer) -->
<div class="scroll-reveal" data-delay="1">Content</div>
```

### Continuous Animations

```html
<div class="pulse-soft">Pulsing element</div>
<div class="animate-spin">Spinner</div>
<div class="shimmer-loading">Loading skeleton</div>
<div class="animated-gradient">Gradient text</div>
```

### Hover Animations

```html
<div class="hover-glow">Glows on hover</div>
<div class="hover-scale-interactive">Lifts on hover</div>
<div class="animated-border">Border glow on hover</div>
```

### Feedback Animations

```html
<i class="bounce-check">✓</i>  <!-- Success -->
<div class="shake">Error!</div> <!-- Attention -->
```

---

## Accessibility

### Focus Trap

Automatically enabled for modals and dialogs.

```javascript
// Manual usage
const trap = new FocusTrap(modalElement, {
    initialFocus: '#first-input',
    returnFocus: true,
    escapeDeactivates: true
});

trap.activate();
// ... modal is open ...
trap.deactivate();
```

### Reduced Motion

All animations respect `prefers-reduced-motion`:

```css
@media (prefers-reduced-motion: reduce) {
    /* Animations disabled, immediate transitions */
}
```

### ARIA Labels

- All interactive elements have `aria-label`
- Modals have `role="dialog"` and `aria-modal="true"`
- Tab navigation uses `role="tablist"` and `role="tab"`
- Lists use `role="listbox"` and `role="option"`

---

## Loading States

### Skeleton Cards

```jinja2
{% call macros.media_grid(columns=5) %}
    {{ macros.skeleton_card() }}
    {{ macros.skeleton_card() }}
    {{ macros.skeleton_card() }}
{% endcall %}
```

### Skeleton Rows

```jinja2
{{ macros.skeleton_row() }}
{{ macros.skeleton_row() }}
{{ macros.skeleton_row() }}
```

### Skeleton Text

```jinja2
{{ macros.skeleton_text(width='60%') }}
{{ macros.skeleton_text(width='40%', height='12px') }}
```

---

## Theming

### Dark Mode (Default)

All components use CSS custom properties from `variables.css`.

### Light Mode

Activated via `data-theme="light"` on `<html>`:

```javascript
// Toggle theme
document.documentElement.setAttribute('data-theme', 'light');
localStorage.setItem('theme', 'light');
```

### Custom Accent Color

Override the accent color:

```css
:root {
    --accent-primary: #your-color;
    --accent-hover: #your-hover;
    --accent-subtle: rgba(your-color, 0.1);
}
```

---

## Quick Reference

### CSS Classes Cheatsheet

| Class | Purpose |
|-------|---------|
| `.btn`, `.btn-primary` | Buttons |
| `.card` | Generic card container |
| `.media-card` | Album/artist/playlist card |
| `.track-row` | Track list row |
| `.tabs`, `.tab` | Tab navigation |
| `.badge` | Status badges |
| `.form-input` | Text inputs |
| `.blur-fade-in` | Entrance animation |
| `.skeleton` | Loading placeholder |

### JavaScript APIs

| API | Purpose |
|-----|---------|
| `SoulSpotCommandPalette.open()` | Open search palette |
| `SoulSpotBottomSheet.open({...})` | Open action sheet |
| `new FocusTrap(el)` | Keyboard focus management |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + K` | Open Command Palette |
| `/` | Open Command Palette (when not in input) |
| `Esc` | Close modals/dialogs |
| `Tab` / `Shift+Tab` | Navigate focus |
| `↑ ↓` | Navigate lists |
| `Enter` | Select/activate |

---

**End of Component Library Documentation**
