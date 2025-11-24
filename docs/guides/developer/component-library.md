# Component Library Reference

> **Version:** 1.0  
> **Last Updated:** 2025-11-16  
> **Status:** Production Ready

---

## 📖 Overview

This document provides a comprehensive reference for all reusable UI components available in SoulSpot. Components are built using the UI 1.0 Design System and can be used across all pages.

**Component Locations:**
- **Jinja Macros:** `/src/soulspot/templates/includes/_components.html`
- **Loading States:** `/src/soulspot/templates/includes/_skeleton.html`
- **Navigation:** `/src/soulspot/templates/includes/_navigation.html`
- **Partials:** `/src/soulspot/templates/partials/`

---

## 🎨 Design System Foundation

All components use the **UI 1.0 Design System** located in `/docs/ui/`:

- **theme.css**: Design tokens (colors, typography, spacing)
- **components.css**: Base component styles
- **layout.css**: Layout utilities and grid system

**Color Palette:**
- Primary: `#fe4155` (Red)
- Secondary: `#533c5b` (Purple)
- Success: `#10b981` (Green)
- Warning: `#f59e0b` (Orange)
- Danger: `#ef4444` (Red)
- Info: `#3b82f6` (Blue)

---

## 📦 Component Catalog

### 1. Alert / Notification

Display important messages to users.

**Macro:** `alert(type, title, message, icon, dismissible)`

**Parameters:**
- `type` (string): `'success'`, `'warning'`, `'danger'`, `'info'` (default: `'info'`)
- `title` (string): Optional title text
- `message` (string): Main message content
- `icon` (boolean): Show icon (default: `true`)
- `dismissible` (boolean): Show close button (default: `false`)

**Usage:**
```jinja
{% from "includes/_components.html" import alert %}

{{ alert('success', 'Success!', 'Your playlist was imported successfully.') }}
{{ alert('warning', '', 'Token will expire soon.', dismissible=true) }}
{{ alert('danger', 'Error', 'Failed to connect to Spotify.') }}
{{ alert('info', '', 'Connect your Spotify account to get started.') }}
```

**HTML Output:**
```html
<div class="alert alert-success" role="alert">
    <div class="alert-icon">
        <svg>...</svg>
    </div>
    <div class="alert-content flex-1">
        <div class="alert-title">Success!</div>
        Your playlist was imported successfully.
    </div>
</div>
```

**Accessibility:**
- Uses `role="alert"` for screen readers
- Icons have `aria-hidden="true"`
- Dismissible alerts have `aria-label="Dismiss alert"`

---

### 2. Badge

Small status indicators and labels.

**Macro:** `badge(text, type, pulse)`

**Parameters:**
- `text` (string): Badge text
- `type` (string): `'success'`, `'warning'`, `'danger'`, `'info'`, `'neutral'` (default: `'neutral'`)
- `pulse` (boolean): Animated pulse effect (default: `false`)

**Usage:**
```jinja
{% from "includes/_components.html" import badge %}

{{ badge('Active', 'success') }}
{{ badge('Pending', 'warning', pulse=true) }}
{{ badge('Failed', 'danger') }}
{{ badge('New', 'info') }}
{{ badge('Spotify', 'neutral') }}
```

**HTML Output:**
```html
<span class="badge badge-success">Active</span>
<span class="badge badge-warning badge-pulse">Pending</span>
```

**Variants:**
- `.badge-success`: Green (✓)
- `.badge-warning`: Orange (!)
- `.badge-danger`: Red (✗)
- `.badge-info`: Blue (i)
- `.badge-neutral`: Gray

---

### 3. Button Group

Group of related buttons.

**Macro:** `button_group(buttons, size)`

**Parameters:**
- `buttons` (list): List of button objects
- `size` (string): `'sm'`, `'base'`, `'lg'` (default: `'base'`)

**Button Object Properties:**
- `text` (string): Button text
- `icon` (string): Optional icon HTML
- `variant` (string): `'primary'`, `'secondary'`, `'outline'`, `'ghost'`, `'danger'`
- `action` (string): Optional onclick handler
- `hx_post`, `hx_get`, `hx_target`, `hx_swap`: HTMX attributes
- `disabled` (boolean): Disable button
- `label` (string): aria-label

**Usage:**
```jinja
{% from "includes/_components.html" import button_group %}

{% set buttons = [
    {'text': 'Save', 'variant': 'primary', 'hx_post': '/api/save'},
    {'text': 'Cancel', 'variant': 'secondary', 'action': 'closeModal()'},
    {'text': 'Delete', 'variant': 'danger', 'hx_delete': '/api/delete', 'label': 'Delete item'}
] %}

{{ button_group(buttons, 'sm') }}
```

**HTML Output:**
```html
<div class="flex gap-2" role="group">
    <button class="btn btn-primary btn-sm focus-ring" hx-post="/api/save">Save</button>
    <button class="btn btn-secondary btn-sm focus-ring" onclick="closeModal()">Cancel</button>
    <button class="btn btn-danger btn-sm focus-ring" hx-delete="/api/delete" aria-label="Delete item">Delete</button>
</div>
```

---

### 4. Progress Bar

Visual progress indicator.

**Macro:** `progress_bar(value, max, label, show_percentage, color)`

**Parameters:**
- `value` (number): Current value
- `max` (number): Maximum value (default: `100`)
- `label` (string): Optional label text
- `show_percentage` (boolean): Display percentage (default: `true`)
- `color` (string): `'primary'`, `'success'`, `'warning'`, `'danger'` (default: `'primary'`)

**Usage:**
```jinja
{% from "includes/_components.html" import progress_bar %}

{{ progress_bar(75, 100, 'Downloading...') }}
{{ progress_bar(3, 10, 'Files', color='success') }}
{{ progress_bar(50, 100, '', show_percentage=false) }}
```

**HTML Output:**
```html
<div class="w-full" role="progressbar" aria-valuenow="75" aria-valuemin="0" aria-valuemax="100">
    <div class="flex justify-between items-center mb-1">
        <span class="text-sm font-medium text-gray-700">Downloading...</span>
        <span class="text-sm text-gray-600">75%</span>
    </div>
    <div class="w-full bg-gray-200 rounded-full h-2">
        <div class="bg-primary-500 h-2 rounded-full transition-all duration-300" style="width: 75%"></div>
    </div>
</div>
```

**Accessibility:**
- Uses `role="progressbar"`
- Includes `aria-valuenow`, `aria-valuemin`, `aria-valuemax`

---

### 5. Empty State

Display when no data is available.

**Macro:** `empty_state(icon, title, description, action_text, action_href)`

**Parameters:**
- `icon` (string): SVG icon HTML
- `title` (string): Heading text
- `description` (string): Explanation text
- `action_text` (string): Optional button text
- `action_href` (string): Optional button URL

**Usage:**
```jinja
{% from "includes/_components.html" import empty_state %}

{% set icon %}
<svg class="w-16 h-16 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/>
</svg>
{% endset %}

{{ empty_state(icon, 'No playlists yet', 'Import a Spotify playlist to get started!', 'Import Playlist', '/playlists/import') }}
```

---

### 6. Status Indicator

Semantic status badge with icon.

**Macro:** `status_indicator(status)`

**Parameters:**
- `status` (string): Status type (see table below)

**Supported Statuses:**

| Status | Color | Icon | Label |
|--------|-------|------|-------|
| `success` | Green | ✓ | Success |
| `pending` | Orange | ⏳ | Pending |
| `queued` | Blue | 📋 | Queued |
| `downloading` | Blue | ⬇️ | Downloading |
| `completed` | Green | ✓ | Completed |
| `failed` | Red | ✗ | Failed |
| `cancelled` | Gray | ⊘ | Cancelled |

**Usage:**
```jinja
{% from "includes/_components.html" import status_indicator %}

{{ status_indicator('downloading') }}
{{ status_indicator('completed') }}
{{ status_indicator('failed') }}
```

**HTML Output:**
```html
<span class="badge badge-primary" aria-label="Downloading">
    ⬇️ Downloading
</span>
```

---

### 7. Priority Badge

Display priority level (P0, P1, P2).

**Macro:** `priority_badge(priority)`

**Parameters:**
- `priority` (number): Priority level (0-2)

**Priority Levels:**
- **P0** (0): High Priority (Red badge)
- **P1** (1): Medium Priority (Orange badge)
- **P2** (2): Low Priority (Blue badge)

**Usage:**
```jinja
{% from "includes/_components.html" import priority_badge %}

{{ priority_badge(0) }}
{{ priority_badge(1) }}
{{ priority_badge(2) }}
```

**HTML Output:**
```html
<span class="badge badge-danger" title="High Priority">P0</span>
<span class="badge badge-warning" title="Medium Priority">P1</span>
<span class="badge badge-info" title="Low Priority">P2</span>
```

---

### 8. Data Table

Responsive table with optional actions.

**Macro:** `data_table(headers, rows, actions, empty_message)`

**Parameters:**
- `headers` (list): Column header texts
- `rows` (list): List of row data (each row is a list of cells)
- `actions` (list): Optional action buttons per row
- `empty_message` (string): Message when no data (default: 'No data available')

**Action Object Properties:**
- `text` (string): Button text (if no icon)
- `icon` (string): Button icon HTML
- `variant` (string): Button variant
- `label` (string): aria-label
- `hx_post`, `hx_get`, `hx_delete`: HTMX attributes

**Usage:**
```jinja
{% from "includes/_components.html" import data_table %}

{% set headers = ['Name', 'Artist', 'Album', 'Year'] %}
{% set rows = [
    ['Track 1', 'Artist A', 'Album A', '2023'],
    ['Track 2', 'Artist B', 'Album B', '2024']
] %}
{% set actions = [
    {'icon': '⬇️', 'variant': 'primary', 'label': 'Download', 'hx_post': '/api/download'},
    {'icon': '✗', 'variant': 'danger', 'label': 'Delete', 'hx_delete': '/api/delete'}
] %}

{{ data_table(headers, rows, actions) }}
```

---

### 9. Form Field with Validation

Form input with label, help text, and error display.

**Macro:** `form_field(type, name, label, value, placeholder, required, help_text, error)`

**Parameters:**
- `type` (string): Input type (`'text'`, `'email'`, `'password'`, `'textarea'`, `'select'`)
- `name` (string): Input name attribute
- `label` (string): Label text
- `value` (string): Default value
- `placeholder` (string): Placeholder text
- `required` (boolean): Required field
- `help_text` (string): Help text below input
- `error` (string): Error message

**Usage:**
```jinja
{% from "includes/_components.html" import form_field %}

{{ form_field('text', 'username', 'Username', '', 'Enter username', required=true, help_text='Choose a unique username') }}

{{ form_field('email', 'email', 'Email', '', 'your@email.com', required=true, error='Invalid email format') }}

{% call form_field('select', 'priority', 'Priority', required=true) %}
    <option value="0">P0 - High</option>
    <option value="1">P1 - Medium</option>
    <option value="2">P2 - Low</option>
{% endcall %}
```

**HTML Output:**
```html
<div class="form-group">
    <label for="username" class="form-label form-label-required">Username</label>
    <input type="text" id="username" name="username" class="form-input" placeholder="Enter username" required>
    <p class="form-helper">Choose a unique username</p>
</div>
```

---

### 10. Pagination

Navigate through pages of content.

**Macro:** `pagination(current_page, total_pages, base_url)`

**Parameters:**
- `current_page` (number): Current page number
- `total_pages` (number): Total number of pages
- `base_url` (string): Base URL for page links

**Usage:**
```jinja
{% from "includes/_components.html" import pagination %}

{{ pagination(3, 10, '/search') }}
```

**HTML Output:**
```html
<nav class="flex justify-center items-center gap-2 mt-6" aria-label="Pagination">
    <a href="/search?page=2" class="btn btn-secondary btn-sm focus-ring" aria-label="Previous page">
        ← Previous
    </a>
    <div class="flex gap-1">
        <a href="/search?page=1" class="btn btn-secondary btn-sm focus-ring" aria-label="Go to page 1">1</a>
        <span class="text-gray-500 px-2">...</span>
        <span class="btn btn-primary btn-sm" aria-current="page">3</span>
        <a href="/search?page=4" class="btn btn-secondary btn-sm focus-ring" aria-label="Go to page 4">4</a>
        <span class="text-gray-500 px-2">...</span>
        <a href="/search?page=10" class="btn btn-secondary btn-sm focus-ring" aria-label="Go to page 10">10</a>
    </div>
    <a href="/search?page=4" class="btn btn-secondary btn-sm focus-ring" aria-label="Next page">
        Next →
    </a>
</nav>
```

**Features:**
- Shows first/last page always
- Shows 2 pages before/after current
- Ellipsis for gaps
- Previous/Next buttons
- Accessible with ARIA labels

---

## 🔄 Loading States

### Skeleton Components

**Macros:** `card_skeleton()`, `list_skeleton()`, `stats_skeleton()`, `table_skeleton()`, `spinner()`

**Usage:**
```jinja
{% from "includes/_skeleton.html" import card_skeleton, spinner %}

{# Loading state #}
{% if data is none %}
    {{ card_skeleton(6) }}
{% else %}
    {# Actual data #}
{% endif %}

{# Inline spinner #}
{{ spinner('md', 'Loading...') }}
{{ spinner('lg') }}
```

**Skeleton Types:**
- `card_skeleton(count)`: Placeholder cards
- `list_skeleton(count)`: List item placeholders
- `stats_skeleton()`: Dashboard stat cards
- `table_skeleton(rows)`: Table with skeleton rows
- `spinner(size, text)`: Animated spinner

---

## 🧩 Partials (HTMX Fragments)

### Track Item

**File:** `/templates/partials/track_item.html`

**Context Variables:**
- `track.id`: Track ID
- `track.title`: Track title
- `track.artist`: Artist name
- `track.album`: Album name
- `track.album_art`: Album art URL
- `track.duration`: Duration string
- `track.quality`: Quality badge
- `track.year`: Release year
- `show_details`: Show details button

**Usage:**
```jinja
{% include "partials/track_item.html" %}
```

### Download Item

**File:** `/templates/partials/download_item.html`

**Context Variables:**
- `download.id`: Download ID
- `download.track_title`: Track title
- `download.artist`: Artist name
- `download.status`: Status string
- `download.priority`: Priority level (0-2)
- `download.progress_percent`: Progress percentage
- `download.error_message`: Error message if failed
- `download.started_at`: Start timestamp
- `download.created_at`: Created timestamp

**Usage:**
```jinja
{% include "partials/download_item.html" %}
```

---

## 📐 Layout Utilities

### Container

Center content with max-width.

```html
<div class="ui-container">
    <!-- Content -->
</div>

<!-- Variants -->
<div class="ui-container-sm"></div>  <!-- max-width: 640px -->
<div class="ui-container-md"></div>  <!-- max-width: 768px -->
<div class="ui-container-lg"></div>  <!-- max-width: 1024px -->
<div class="ui-container-xl"></div>  <!-- max-width: 1280px -->
<div class="ui-container-full"></div> <!-- max-width: 100% -->
```

### Grid

CSS Grid utilities.

```html
<!-- 3 equal columns -->
<div class="ui-grid ui-grid-cols-3">
    <div>Column 1</div>
    <div>Column 2</div>
    <div>Column 3</div>
</div>

<!-- Responsive columns -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
    <!-- Items -->
</div>

<!-- Dashboard grid (12 columns) -->
<div class="ui-dashboard-grid">
    <!-- Widgets -->
</div>
```

---

## ♿ Accessibility Features

All components include:

- **Semantic HTML**: Proper elements (`button`, `nav`, `main`, etc.)
- **ARIA Labels**: `aria-label`, `aria-labelledby`, `aria-describedby`
- **ARIA Roles**: `role="alert"`, `role="navigation"`, etc.
- **ARIA States**: `aria-current="page"`, `aria-expanded`, etc.
- **Keyboard Navigation**: All interactive elements are keyboard accessible
- **Focus Indicators**: Visible focus rings (`.focus-ring` class)
- **Screen Reader Support**: `sr-only` text for context

**Example:**
```html
<button class="btn btn-primary focus-ring" 
        aria-label="Download track: Song Title">
    ⬇️ Download
</button>
```

---

## 🎨 Theming

Components respect dark mode automatically:

```css
/* Light mode (default) */
:root {
    --ui-primary: #fe4155;
    /* ... */
}

/* Dark mode */
.dark {
    --ui-primary: #fe4155; /* Adjust for dark mode */
    /* ... */
}
```

Toggle dark mode:
```javascript
document.documentElement.classList.toggle('dark');
```

---

## 📚 Additional Resources

- [UI 1.0 Design System Documentation](../ui/README_UI_1_0.md)
- [HTMX Patterns Guide](htmx-patterns.md)
- [User Guide](user-guide.md)
- [Keyboard Navigation Guide](keyboard-navigation.md)

---

**Version:** 1.0  
**Last Updated:** 2025-11-16  
**Maintained by:** Frontend Team
