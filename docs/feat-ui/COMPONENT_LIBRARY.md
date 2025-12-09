# ⚠️ DEPRECATED - SoulSpot UI - Component Library

## Document Information
- **Version**: 1.0 (DEPRECATED)
- **Last Updated**: 2025-11-26
- **Status**: ❌ DEPRECATED
- **Replaced By:** Actual implementations in `src/soulspot/templates/includes/_components.html`, `_design_system.html`, `_skeleton.html` + [feat-ui-pro.md](./feat-ui-pro.md) Phase 2
- **Date Deprecated:** 9. Dezember 2025
- **Reason:** Theoretical component specs. Real components now exist in templates/includes/ with Jinja2 macros following Hexagonal Architecture.
- **Related**: [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) ❌ DEPRECATED, [TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md) ❌ DEPRECATED

**DO NOT USE THIS FILE. See `templates/includes/_components.html` for actual component implementations.**

---

<details>
<summary>Original Content (Archived)</summary>

---

## Introduction

This document provides a comprehensive reference for all UI components in the SoulSpot redesign. Each component includes:
- Purpose and usage
- Props/parameters
- HTML structure
- CSS classes
- JavaScript behavior (if applicable)
- Accessibility considerations
- Examples
- **Light Mode Colors** (MediaManager Reference)

---

## Light Mode Color Reference (MediaManager)

> All components support Light Mode theming using colors from the [MediaManager](https://github.com/maxdorninger/MediaManager) design system. See [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) for full color palette.

### Quick Reference: Light Mode Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-bg` | `#ffffff` | Main background |
| `--color-surface` | `#ffffff` | Cards, panels |
| `--color-surface-alt` | `#f5f5f5` | Secondary surfaces, hover |
| `--color-border` | `#e5e5e5` | Borders, dividers |
| `--color-text` | `#1a1a1a` | Primary text |
| `--color-text-muted` | `#888888` | Muted/secondary text |
| `--color-primary` | `#333333` | Primary actions |
| `--color-primary-foreground` | `#fafafa` | Text on primary |
| `--color-destructive` | `#d32f2f` | Error/delete actions |
| `--color-ring` | `#b3b3b3` | Focus ring |

---

## Table of Contents

### Layout Components
1. [Sidebar](#sidebar)
2. [TopBar](#topbar)
3. [PageHeader](#pageheader)
4. [Container](#container)

### Navigation Components
5. [Breadcrumbs](#breadcrumbs)
6. [Tabs](#tabs)
7. [Pagination](#pagination)

### Data Display Components
8. [Card](#card)
9. [Table](#table)
10. [Grid](#grid)
11. [List](#list)
12. [Badge](#badge)

### Input Components
13. [Button](#button)
14. [Input](#input)
15. [Select](#select)
16. [Checkbox](#checkbox)
17. [Radio](#radio)
18. [FilterPanel](#filterpanel)
19. [SearchBar](#searchbar)

### Feedback Components
20. [Alert](#alert)
21. [Toast](#toast)
22. [Modal](#modal)
23. [Loading](#loading)
24. [ProgressBar](#progressbar)

### Specialized Components
25. [LibraryView](#libraryview)
26. [QueueManager](#queuemanager)
27. [ActivityFeed](#activityfeed)
28. [AlbumArt](#albumart)

---

## Layout Components

### Sidebar

**Purpose**: Main navigation sidebar with collapsible sections

**Location**: `templates/components/layout/Sidebar.html`

**Props**:
```python
{
  'active_section': str,  # Currently active section
  'collapsed': bool,      # Sidebar collapsed state
  'user': dict           # User data
}
```

**HTML Structure**:
```html
<aside class="sidebar" data-collapsed="false">
  <!-- Logo -->
  <div class="sidebar-header">
    <a href="/" class="sidebar-logo">
      <i class="fa-solid fa-music"></i>
      <span class="sidebar-logo-text">SoulSpot</span>
    </a>
    <button class="sidebar-toggle" aria-label="Toggle sidebar">
      <i class="fa-solid fa-bars"></i>
    </button>
  </div>

  <!-- Navigation -->
  <nav class="sidebar-nav">
    <a href="/dashboard" class="sidebar-item active">
      <i class="fa-solid fa-home"></i>
      <span>Dashboard</span>
    </a>
    
    <div class="sidebar-section">
      <div class="sidebar-section-title">Library</div>
      <a href="/library/artists" class="sidebar-item">
        <i class="fa-solid fa-user-music"></i>
        <span>Artists</span>
      </a>
      <a href="/library/albums" class="sidebar-item">
        <i class="fa-solid fa-compact-disc"></i>
        <span>Albums</span>
      </a>
      <a href="/library/tracks" class="sidebar-item">
        <i class="fa-solid fa-music"></i>
        <span>Tracks</span>
      </a>
    </div>

    <a href="/playlists" class="sidebar-item">
      <i class="fa-solid fa-list"></i>
      <span>Playlists</span>
    </a>

    <a href="/downloads" class="sidebar-item">
      <i class="fa-solid fa-download"></i>
      <span>Downloads</span>
      <span class="sidebar-badge">3</span>
    </a>

    <a href="/search" class="sidebar-item">
      <i class="fa-solid fa-search"></i>
      <span>Search</span>
    </a>
  </nav>

  <!-- Footer -->
  <div class="sidebar-footer">
    <a href="/settings" class="sidebar-item">
      <i class="fa-solid fa-cog"></i>
      <span>Settings</span>
    </a>
    
    <div class="sidebar-user">
      <img src="{{ user.avatar }}" alt="{{ user.name }}" class="sidebar-user-avatar">
      <div class="sidebar-user-info">
        <div class="sidebar-user-name">{{ user.name }}</div>
        <div class="sidebar-user-status">Online</div>
      </div>
    </div>
  </div>
</aside>
```

**CSS Classes**:
```css
.sidebar {
  width: 280px;
  height: 100vh;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-normal);
}

.sidebar[data-collapsed="true"] {
  width: 80px;
}

.sidebar-header {
  padding: var(--space-lg);
  border-bottom: 1px solid var(--color-border);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-text);
  text-decoration: none;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md);
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  text-decoration: none;
  transition: all var(--transition-fast);
}

.sidebar-item:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

.sidebar-item.active {
  background: var(--color-primary);
  color: white;
}

.sidebar-section {
  margin: var(--space-md) 0;
}

.sidebar-section-title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: var(--space-sm) var(--space-md);
}

.sidebar-badge {
  margin-left: auto;
  background: var(--color-primary);
  color: white;
  font-size: var(--font-size-xs);
  padding: 2px 6px;
  border-radius: var(--radius-full);
}

.sidebar-footer {
  border-top: 1px solid var(--color-border);
  padding: var(--space-md);
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
}

.sidebar-user-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
}

.sidebar-user-name {
  font-weight: var(--font-weight-medium);
  color: var(--color-text);
}

.sidebar-user-status {
  font-size: var(--font-size-xs);
  color: var(--color-success);
}
```

**Light Mode Colors (Sidebar)**:
```css
/* Light Mode - Sidebar (MediaManager) */
:root[data-theme="light"] .sidebar {
  background: #fafafa;                    /* --sidebar-background */
  border-right: 1px solid #e5e5e5;        /* --sidebar-border */
}

:root[data-theme="light"] .sidebar-logo {
  color: #1a1a1a;                         /* --sidebar-foreground */
}

:root[data-theme="light"] .sidebar-item {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .sidebar-item:hover {
  background: #f5f5f5;                    /* --sidebar-accent */
  color: #1a1a1a;                         /* --sidebar-foreground */
}

:root[data-theme="light"] .sidebar-item.active {
  background: #333333;                    /* --sidebar-primary */
  color: #fafafa;                         /* --sidebar-primary-foreground */
}

:root[data-theme="light"] .sidebar-section-title {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .sidebar-badge {
  background: #333333;                    /* --sidebar-primary */
  color: #fafafa;                         /* --sidebar-primary-foreground */
}

:root[data-theme="light"] .sidebar-footer {
  border-top: 1px solid #e5e5e5;          /* --sidebar-border */
}

:root[data-theme="light"] .sidebar-user {
  background: #f5f5f5;                    /* --sidebar-accent */
}

:root[data-theme="light"] .sidebar-user-name {
  color: #1a1a1a;                         /* --sidebar-foreground */
}
```

**JavaScript Behavior**:
```javascript
// Toggle sidebar
document.querySelector('.sidebar-toggle').addEventListener('click', () => {
  const sidebar = document.querySelector('.sidebar');
  const isCollapsed = sidebar.dataset.collapsed === 'true';
  sidebar.dataset.collapsed = !isCollapsed;
  
  // Save state
  localStorage.setItem('sidebarCollapsed', !isCollapsed);
});

// Restore state on load
const savedState = localStorage.getItem('sidebarCollapsed');
if (savedState === 'true') {
  document.querySelector('.sidebar').dataset.collapsed = 'true';
}
```

**Accessibility**:
- Semantic `<nav>` element
- ARIA labels for toggle button
- Keyboard navigation support
- Focus indicators on all items

---

### TopBar

**Purpose**: Top navigation bar with search and user menu

**Location**: `templates/components/layout/TopBar.html`

**Props**:
```python
{
  'page_title': str,     # Current page title
  'show_search': bool,   # Show search bar
  'user': dict          # User data
}
```

**HTML Structure**:
```html
<header class="topbar">
  <div class="topbar-left">
    <button class="topbar-menu-toggle" aria-label="Toggle menu">
      <i class="fa-solid fa-bars"></i>
    </button>
    
    <div class="topbar-breadcrumbs">
      <a href="/">Home</a>
      <i class="fa-solid fa-chevron-right"></i>
      <span>{{ page_title }}</span>
    </div>
  </div>

  <div class="topbar-center">
    {% if show_search %}
    <div class="topbar-search">
      <i class="fa-solid fa-search"></i>
      <input type="text" placeholder="Search..." class="topbar-search-input">
      <kbd class="topbar-search-shortcut">Ctrl+K</kbd>
    </div>
    {% endif %}
  </div>

  <div class="topbar-right">
    <button class="topbar-icon-btn" aria-label="Notifications">
      <i class="fa-solid fa-bell"></i>
      <span class="topbar-badge">3</span>
    </button>

    <button class="topbar-icon-btn" aria-label="Toggle theme">
      <i class="fa-solid fa-moon"></i>
    </button>

    <div class="topbar-user-menu">
      <button class="topbar-user-btn">
        <img src="{{ user.avatar }}" alt="{{ user.name }}">
        <span>{{ user.name }}</span>
        <i class="fa-solid fa-chevron-down"></i>
      </button>
      
      <div class="topbar-user-dropdown">
        <a href="/profile">Profile</a>
        <a href="/settings">Settings</a>
        <hr>
        <a href="/logout">Logout</a>
      </div>
    </div>
  </div>
</header>
```

**CSS Classes**:
```css
.topbar {
  height: 64px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-lg);
  gap: var(--space-lg);
}

.topbar-left,
.topbar-center,
.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.topbar-center {
  flex: 1;
  max-width: 600px;
}

.topbar-search {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-sm) var(--space-md);
}

.topbar-search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text);
}

.topbar-search-shortcut {
  font-size: var(--font-size-xs);
  padding: 2px 6px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
}

.topbar-icon-btn {
  position: relative;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.topbar-icon-btn:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

.topbar-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  background: var(--color-primary);
  color: white;
  font-size: 10px;
  padding: 2px 4px;
  border-radius: var(--radius-full);
  min-width: 16px;
  text-align: center;
}
```

**Light Mode Colors (TopBar)**:
```css
/* Light Mode - TopBar (MediaManager) */
:root[data-theme="light"] .topbar {
  background: #ffffff;                    /* --color-surface */
  border-bottom: 1px solid #e5e5e5;       /* --color-border */
}

:root[data-theme="light"] .topbar-breadcrumbs a {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .topbar-breadcrumbs span {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .topbar-search {
  background: #f5f5f5;                    /* --color-surface-alt */
  border: 1px solid #e5e5e5;              /* --color-border */
}

:root[data-theme="light"] .topbar-search-input {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .topbar-search-input::placeholder {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .topbar-search-shortcut {
  background: #ffffff;                    /* --color-surface */
  border: 1px solid #e5e5e5;              /* --color-border */
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .topbar-icon-btn {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .topbar-icon-btn:hover {
  background: #f5f5f5;                    /* --color-surface-hover */
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .topbar-badge {
  background: #333333;                    /* --color-primary */
  color: #fafafa;                         /* --color-primary-foreground */
}

:root[data-theme="light"] .topbar-user-dropdown {
  background: #ffffff;                    /* --color-popover */
  border: 1px solid #e5e5e5;              /* --color-border */
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

:root[data-theme="light"] .topbar-user-dropdown a {
  color: #1a1a1a;                         /* --color-popover-foreground */
}

:root[data-theme="light"] .topbar-user-dropdown a:hover {
  background: #f5f5f5;                    /* --color-accent */
}
```

---

## Data Display Components

### Card

**Purpose**: Reusable card component for displaying content

**Location**: `templates/components/data-display/Card.html`

**Props**:
```python
{
  'title': str,          # Card title
  'image': str,          # Image URL
  'metadata': dict,      # Additional metadata
  'actions': list,       # Action buttons
  'status': str,         # Status badge
  'variant': str         # 'default' | 'glass' | 'hover'
}
```

**HTML Structure**:
```html
<div class="card {% if variant == 'glass' %}card-glass{% endif %} {% if variant == 'hover' %}card-hover{% endif %}">
  {% if image %}
  <div class="card-image">
    <img src="{{ image }}" alt="{{ title }}">
    {% if status %}
    <span class="card-status badge badge-{{ status }}">{{ status }}</span>
    {% endif %}
  </div>
  {% endif %}

  <div class="card-content">
    {% if title %}
    <h3 class="card-title">{{ title }}</h3>
    {% endif %}

    {% if metadata %}
    <div class="card-metadata">
      {% for key, value in metadata.items() %}
      <div class="card-meta-item">
        <span class="card-meta-label">{{ key }}:</span>
        <span class="card-meta-value">{{ value }}</span>
      </div>
      {% endfor %}
    </div>
    {% endif %}
  </div>

  {% if actions %}
  <div class="card-actions">
    {% for action in actions %}
    <button class="btn btn-{{ action.variant or 'primary' }}">
      {% if action.icon %}<i class="{{ action.icon }}"></i>{% endif %}
      {{ action.label }}
    </button>
    {% endfor %}
  </div>
  {% endif %}
</div>
```

**Variants**:

**Album Card**:
```html
<div class="card card-album card-hover">
  <div class="card-image">
    <img src="{{ album.cover_url }}" alt="{{ album.name }}">
    <div class="card-overlay">
      <button class="btn btn-primary btn-icon">
        <i class="fa-solid fa-play"></i>
      </button>
    </div>
  </div>
  <div class="card-content">
    <h3 class="card-title">{{ album.name }}</h3>
    <p class="card-subtitle">{{ album.artist }}</p>
    <div class="card-metadata">
      <span>{{ album.year }}</span>
      <span>{{ album.track_count }} tracks</span>
    </div>
  </div>
</div>
```

**Artist Card**:
```html
<div class="card card-artist card-hover">
  <div class="card-image card-image-circle">
    <img src="{{ artist.image_url }}" alt="{{ artist.name }}">
  </div>
  <div class="card-content text-center">
    <h3 class="card-title">{{ artist.name }}</h3>
    <p class="card-subtitle">{{ artist.genre }}</p>
    <div class="card-stats">
      <div class="card-stat">
        <span class="card-stat-value">{{ artist.album_count }}</span>
        <span class="card-stat-label">Albums</span>
      </div>
      <div class="card-stat">
        <span class="card-stat-value">{{ artist.track_count }}</span>
        <span class="card-stat-label">Tracks</span>
      </div>
    </div>
  </div>
</div>
```

**Light Mode Colors (Card)**:
```css
/* Light Mode - Card (MediaManager) */
:root[data-theme="light"] .card {
  background: #ffffff;                    /* --color-card */
  border: 1px solid #e5e5e5;              /* --color-border */
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

:root[data-theme="light"] .card:hover {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

:root[data-theme="light"] .card-title {
  color: #1a1a1a;                         /* --color-card-foreground */
}

:root[data-theme="light"] .card-subtitle {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .card-metadata {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .card-meta-label {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .card-meta-value {
  color: #333333;                         /* --color-text-secondary */
}

:root[data-theme="light"] .card-glass {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

:root[data-theme="light"] .card-overlay {
  background: rgba(0, 0, 0, 0.4);
}

:root[data-theme="light"] .card-stat-value {
  color: #1a1a1a;                         /* --color-card-foreground */
}

:root[data-theme="light"] .card-stat-label {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .card-actions {
  border-top: 1px solid #e5e5e5;          /* --color-border */
}
```

---

## Specialized Components

### LibraryView

**Purpose**: Unified library view with multiple display modes

**Location**: `templates/components/specialized/LibraryView.html`

**Props**:
```python
{
  'items': list,         # Items to display
  'view_mode': str,      # 'grid' | 'list' | 'table'
  'filters': dict,       # Active filters
  'sort': dict,          # Sort configuration
  'total': int,          # Total item count
  'page': int,           # Current page
  'per_page': int        # Items per page
}
```

**HTML Structure**:
```html
<div class="library-view">
  <!-- Header -->
  <div class="library-header">
    <div class="library-title">
      <h1>{{ title }}</h1>
      <span class="library-count">{{ total }} items</span>
    </div>

    <div class="library-controls">
      <!-- View Mode Toggle -->
      <div class="view-toggle">
        <button class="view-toggle-btn {% if view_mode == 'grid' %}active{% endif %}" 
                data-view="grid" aria-label="Grid view">
          <i class="fa-solid fa-grid"></i>
        </button>
        <button class="view-toggle-btn {% if view_mode == 'list' %}active{% endif %}" 
                data-view="list" aria-label="List view">
          <i class="fa-solid fa-list"></i>
        </button>
        <button class="view-toggle-btn {% if view_mode == 'table' %}active{% endif %}" 
                data-view="table" aria-label="Table view">
          <i class="fa-solid fa-table"></i>
        </button>
      </div>

      <!-- Sort -->
      <div class="library-sort">
        <select class="form-select" name="sort">
          <option value="name">Name</option>
          <option value="date">Date Added</option>
          <option value="artist">Artist</option>
          <option value="year">Year</option>
        </select>
      </div>

      <!-- Filter Toggle -->
      <button class="btn btn-outline" id="filter-toggle">
        <i class="fa-solid fa-filter"></i>
        Filters
        {% if filters|length > 0 %}
        <span class="badge badge-primary">{{ filters|length }}</span>
        {% endif %}
      </button>
    </div>
  </div>

  <!-- Content -->
  <div class="library-content">
    <!-- Filter Panel (Sidebar) -->
    <aside class="library-filters" id="filter-panel">
      {% include 'components/specialized/FilterPanel.html' %}
    </aside>

    <!-- Items -->
    <div class="library-items">
      {% if view_mode == 'grid' %}
      <div class="library-grid">
        {% for item in items %}
        {% include 'components/data-display/Card.html' with item %}
        {% endfor %}
      </div>
      {% elif view_mode == 'list' %}
      <div class="library-list">
        {% for item in items %}
        {% include 'components/data-display/ListItem.html' with item %}
        {% endfor %}
      </div>
      {% elif view_mode == 'table' %}
      <div class="library-table">
        {% include 'components/data-display/Table.html' with items %}
      </div>
      {% endif %}

      <!-- Pagination -->
      {% if total > per_page %}
      <div class="library-pagination">
        {% include 'components/navigation/Pagination.html' %}
      </div>
      {% endif %}
    </div>
  </div>
</div>
```

**CSS Classes**:
```css
.library-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  height: 100%;
}

.library-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg);
}

.library-title {
  display: flex;
  align-items: baseline;
  gap: var(--space-sm);
}

.library-count {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.library-controls {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.view-toggle {
  display: flex;
  gap: var(--space-xs);
  background: var(--color-surface-alt);
  border-radius: var(--radius-md);
  padding: var(--space-xs);
}

.view-toggle-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.view-toggle-btn:hover {
  color: var(--color-text);
}

.view-toggle-btn.active {
  background: var(--color-primary);
  color: white;
}

.library-content {
  display: flex;
  gap: var(--space-lg);
  flex: 1;
  overflow: hidden;
}

.library-filters {
  width: 280px;
  flex-shrink: 0;
  overflow-y: auto;
}

.library-items {
  flex: 1;
  overflow-y: auto;
}

.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-lg);
}

.library-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}
```

**Light Mode Colors (LibraryView)**:
```css
/* Light Mode - LibraryView (MediaManager) */
:root[data-theme="light"] .library-title h1 {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .library-count {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .view-toggle {
  background: #f5f5f5;                    /* --color-surface-alt */
}

:root[data-theme="light"] .view-toggle-btn {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .view-toggle-btn:hover {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .view-toggle-btn.active {
  background: #333333;                    /* --color-primary */
  color: #fafafa;                         /* --color-primary-foreground */
}

:root[data-theme="light"] .library-filters {
  background: #ffffff;                    /* --color-surface */
  border-right: 1px solid #e5e5e5;        /* --color-border */
}

:root[data-theme="light"] .form-select {
  background: #ffffff;                    /* --color-surface */
  border: 1px solid #e5e5e5;              /* --color-input */
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .form-select:focus {
  border-color: #b3b3b3;                  /* --color-ring */
  outline: 2px solid rgba(179, 179, 179, 0.2);
}
```

**JavaScript Behavior**:
```javascript
// View mode toggle
document.querySelectorAll('.view-toggle-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const viewMode = btn.dataset.view;
    
    // Update active state
    document.querySelectorAll('.view-toggle-btn').forEach(b => {
      b.classList.remove('active');
    });
    btn.classList.add('active');
    
    // Save preference
    localStorage.setItem('libraryViewMode', viewMode);
    
    // Update view (HTMX or page reload)
    htmx.ajax('GET', `/library?view=${viewMode}`, {
      target: '.library-items',
      swap: 'innerHTML'
    });
  });
});

// Filter toggle
document.getElementById('filter-toggle').addEventListener('click', () => {
  const panel = document.getElementById('filter-panel');
  panel.classList.toggle('hidden');
});
```

---

### QueueManager

**Purpose**: Download queue management interface

**Location**: `templates/components/specialized/QueueManager.html`

**Props**:
```python
{
  'queue_items': list,       # Queue items
  'active_downloads': int,   # Active download count
  'max_concurrent': int      # Max concurrent downloads
}
```

**HTML Structure**:
```html
<div class="queue-manager">
  <!-- Header -->
  <div class="queue-header">
    <div class="queue-stats">
      <div class="queue-stat">
        <span class="queue-stat-value">{{ active_downloads }}</span>
        <span class="queue-stat-label">Active</span>
      </div>
      <div class="queue-stat">
        <span class="queue-stat-value">{{ queue_items|length }}</span>
        <span class="queue-stat-label">In Queue</span>
      </div>
    </div>

    <div class="queue-actions">
      <button class="btn btn-outline" id="pause-all">
        <i class="fa-solid fa-pause"></i>
        Pause All
      </button>
      <button class="btn btn-outline" id="clear-completed">
        <i class="fa-solid fa-check"></i>
        Clear Completed
      </button>
    </div>
  </div>

  <!-- Queue Items -->
  <div class="queue-items" id="queue-items">
    {% for item in queue_items %}
    <div class="queue-item" data-id="{{ item.id }}" data-status="{{ item.status }}">
      <div class="queue-item-info">
        <img src="{{ item.album_art }}" alt="{{ item.title }}" class="queue-item-image">
        <div class="queue-item-details">
          <div class="queue-item-title">{{ item.title }}</div>
          <div class="queue-item-artist">{{ item.artist }}</div>
        </div>
      </div>

      <div class="queue-item-progress">
        <div class="progress-bar">
          <div class="progress-bar-fill" style="width: {{ item.progress }}%"></div>
        </div>
        <div class="progress-text">{{ item.progress }}%</div>
      </div>

      <div class="queue-item-status">
        <span class="badge badge-{{ item.status }}">{{ item.status }}</span>
      </div>

      <div class="queue-item-actions">
        {% if item.status == 'active' %}
        <button class="btn-icon" data-action="pause">
          <i class="fa-solid fa-pause"></i>
        </button>
        {% elif item.status == 'paused' %}
        <button class="btn-icon" data-action="resume">
          <i class="fa-solid fa-play"></i>
        </button>
        {% elif item.status == 'failed' %}
        <button class="btn-icon" data-action="retry">
          <i class="fa-solid fa-rotate"></i>
        </button>
        {% endif %}
        <button class="btn-icon" data-action="cancel">
          <i class="fa-solid fa-times"></i>
        </button>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
```

**Real-Time Updates (SSE)**:
```javascript
// Connect to SSE endpoint
const eventSource = new EventSource('/api/downloads/stream');

eventSource.addEventListener('download_progress', (event) => {
  const data = JSON.parse(event.data);
  updateQueueItem(data.id, data.progress, data.status);
});

function updateQueueItem(id, progress, status) {
  const item = document.querySelector(`[data-id="${id}"]`);
  if (!item) return;

  // Update progress bar
  const progressBar = item.querySelector('.progress-bar-fill');
  progressBar.style.width = `${progress}%`;

  // Update progress text
  const progressText = item.querySelector('.progress-text');
  progressText.textContent = `${progress}%`;

  // Update status badge
  const statusBadge = item.querySelector('.badge');
  statusBadge.className = `badge badge-${status}`;
  statusBadge.textContent = status;
}
```

**Light Mode Colors (QueueManager)**:
```css
/* Light Mode - QueueManager (MediaManager) */
:root[data-theme="light"] .queue-manager {
  background: #ffffff;                    /* --color-surface */
}

:root[data-theme="light"] .queue-header {
  border-bottom: 1px solid #e5e5e5;       /* --color-border */
}

:root[data-theme="light"] .queue-stat-value {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .queue-stat-label {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .queue-item {
  background: #ffffff;                    /* --color-card */
  border: 1px solid #e5e5e5;              /* --color-border */
}

:root[data-theme="light"] .queue-item:hover {
  background: #fafafa;                    /* --color-bg-alt */
}

:root[data-theme="light"] .queue-item-title {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .queue-item-artist {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .progress-bar {
  background: #e5e5e5;                    /* --color-input */
}

:root[data-theme="light"] .progress-bar-fill {
  background: #333333;                    /* --color-primary */
}

:root[data-theme="light"] .progress-text {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .btn-icon {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .btn-icon:hover {
  background: #f5f5f5;                    /* --color-surface-hover */
  color: #1a1a1a;                         /* --color-text */
}
```

---

## Light Mode: All Remaining Components

### Button (Light Mode)
```css
/* Light Mode - Button Variants (MediaManager) */
:root[data-theme="light"] .btn-primary {
  background: #333333;                    /* --color-primary */
  color: #fafafa;                         /* --color-primary-foreground */
}

:root[data-theme="light"] .btn-primary:hover {
  background: #1a1a1a;                    /* --color-primary-hover (darker) */
}

:root[data-theme="light"] .btn-secondary {
  background: #f5f5f5;                    /* --color-secondary */
  color: #333333;                         /* --color-secondary-foreground */
}

:root[data-theme="light"] .btn-secondary:hover {
  background: #ebebeb;                    /* --color-secondary-hover */
}

:root[data-theme="light"] .btn-outline {
  background: transparent;
  border: 1px solid #e5e5e5;              /* --color-border */
  color: #333333;                         /* --color-text-secondary */
}

:root[data-theme="light"] .btn-outline:hover {
  background: #f5f5f5;                    /* --color-accent */
  border-color: #d4d4d4;                  /* --color-border-dark */
}

:root[data-theme="light"] .btn-ghost {
  background: transparent;
  color: #333333;                         /* --color-text-secondary */
}

:root[data-theme="light"] .btn-ghost:hover {
  background: #f5f5f5;                    /* --color-accent */
}

:root[data-theme="light"] .btn-destructive {
  background: #d32f2f;                    /* --color-destructive */
  color: #ffffff;                         /* --color-destructive-foreground */
}

:root[data-theme="light"] .btn-destructive:hover {
  background: #b71c1c;                    /* darker red */
}

:root[data-theme="light"] .btn:disabled {
  background: #f5f5f5;                    /* --color-muted */
  color: #b3b3b3;                         /* --color-text-disabled */
  cursor: not-allowed;
}
```

### Input & Form Fields (Light Mode)
```css
/* Light Mode - Input/Forms (MediaManager) */
:root[data-theme="light"] .form-input,
:root[data-theme="light"] .form-textarea {
  background: #ffffff;                    /* --color-bg */
  border: 1px solid #e5e5e5;              /* --color-input */
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .form-input::placeholder,
:root[data-theme="light"] .form-textarea::placeholder {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .form-input:focus,
:root[data-theme="light"] .form-textarea:focus {
  border-color: #b3b3b3;                  /* --color-ring */
  outline: 2px solid rgba(179, 179, 179, 0.3);
}

:root[data-theme="light"] .form-input:disabled {
  background: #f5f5f5;                    /* --color-muted */
  color: #b3b3b3;                         /* --color-text-disabled */
}

:root[data-theme="light"] .form-label {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .form-hint {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .form-error {
  color: #d32f2f;                         /* --color-destructive */
}

:root[data-theme="light"] .form-input.error {
  border-color: #d32f2f;                  /* --color-destructive */
}
```

### Checkbox & Radio (Light Mode)
```css
/* Light Mode - Checkbox/Radio (MediaManager) */
:root[data-theme="light"] .form-checkbox input,
:root[data-theme="light"] .form-radio input {
  border: 1px solid #e5e5e5;              /* --color-input */
  background: #ffffff;                    /* --color-bg */
}

:root[data-theme="light"] .form-checkbox input:checked,
:root[data-theme="light"] .form-radio input:checked {
  background: #333333;                    /* --color-primary */
  border-color: #333333;                  /* --color-primary */
}

:root[data-theme="light"] .form-checkbox input:focus,
:root[data-theme="light"] .form-radio input:focus {
  outline: 2px solid rgba(179, 179, 179, 0.3);
}

:root[data-theme="light"] .form-checkbox span,
:root[data-theme="light"] .form-radio span {
  color: #1a1a1a;                         /* --color-text */
}
```

### Toggle/Switch (Light Mode)
```css
/* Light Mode - Toggle/Switch (MediaManager) */
:root[data-theme="light"] .toggle {
  background: #e5e5e5;                    /* --color-input (off state) */
}

:root[data-theme="light"] .toggle.active {
  background: #333333;                    /* --color-primary (on state) */
}

:root[data-theme="light"] .toggle-thumb {
  background: #ffffff;                    /* white thumb */
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
```

### Table (Light Mode)
```css
/* Light Mode - Table (MediaManager) */
:root[data-theme="light"] .table {
  background: #ffffff;                    /* --color-surface */
  border: 1px solid #e5e5e5;              /* --color-border */
}

:root[data-theme="light"] .table th {
  background: #f5f5f5;                    /* --color-muted */
  color: #1a1a1a;                         /* --color-text */
  border-bottom: 1px solid #e5e5e5;       /* --color-border */
}

:root[data-theme="light"] .table td {
  color: #1a1a1a;                         /* --color-text */
  border-bottom: 1px solid #e5e5e5;       /* --color-border */
}

:root[data-theme="light"] .table tr:hover {
  background: #fafafa;                    /* --color-bg-alt */
}

:root[data-theme="light"] .table tr:nth-child(even) {
  background: #fafafa;                    /* alternating rows */
}

:root[data-theme="light"] .table-muted {
  color: #888888;                         /* --color-text-muted */
}
```

### List (Light Mode)
```css
/* Light Mode - List (MediaManager) */
:root[data-theme="light"] .list-item {
  background: #ffffff;                    /* --color-surface */
  border-bottom: 1px solid #e5e5e5;       /* --color-border */
}

:root[data-theme="light"] .list-item:hover {
  background: #fafafa;                    /* --color-bg-alt */
}

:root[data-theme="light"] .list-item-title {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .list-item-subtitle {
  color: #888888;                         /* --color-text-muted */
}
```

### Badge/Tag (Light Mode)
```css
/* Light Mode - Badge (MediaManager) */
:root[data-theme="light"] .badge {
  background: #f5f5f5;                    /* --color-muted */
  color: #333333;                         /* --color-muted-foreground */
}

:root[data-theme="light"] .badge-primary {
  background: #333333;                    /* --color-primary */
  color: #fafafa;                         /* --color-primary-foreground */
}

:root[data-theme="light"] .badge-success {
  background: #d1fae5;                    /* light green bg */
  color: #059669;                         /* --color-success-dark */
}

:root[data-theme="light"] .badge-warning {
  background: #fef3c7;                    /* light amber bg */
  color: #d97706;                         /* --color-warning-dark */
}

:root[data-theme="light"] .badge-danger,
:root[data-theme="light"] .badge-failed {
  background: #fee2e2;                    /* light red bg */
  color: #dc2626;                         /* --color-danger-dark */
}

:root[data-theme="light"] .badge-info {
  background: #dbeafe;                    /* light blue bg */
  color: #2563eb;                         /* --color-info-dark */
}

:root[data-theme="light"] .badge-outline {
  background: transparent;
  border: 1px solid #e5e5e5;              /* --color-border */
  color: #333333;                         /* --color-text-secondary */
}
```

### Alert/Toast (Light Mode)
```css
/* Light Mode - Alert (MediaManager) */
:root[data-theme="light"] .alert {
  background: #ffffff;                    /* --color-surface */
  border: 1px solid #e5e5e5;              /* --color-border */
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .alert-success {
  background: #d1fae5;                    /* light green */
  border-color: #10b981;                  /* --color-success */
  color: #059669;                         /* --color-success-dark */
}

:root[data-theme="light"] .alert-warning {
  background: #fef3c7;                    /* light amber */
  border-color: #f59e0b;                  /* --color-warning */
  color: #d97706;                         /* --color-warning-dark */
}

:root[data-theme="light"] .alert-danger,
:root[data-theme="light"] .alert-error {
  background: #fee2e2;                    /* light red */
  border-color: #ef4444;                  /* --color-danger */
  color: #dc2626;                         /* --color-danger-dark */
}

:root[data-theme="light"] .alert-info {
  background: #dbeafe;                    /* light blue */
  border-color: #3b82f6;                  /* --color-info */
  color: #2563eb;                         /* --color-info-dark */
}

:root[data-theme="light"] .toast {
  background: #ffffff;                    /* --color-popover */
  border: 1px solid #e5e5e5;              /* --color-border */
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
```

### Modal/Dialog (Light Mode)
```css
/* Light Mode - Modal (MediaManager) */
:root[data-theme="light"] .modal-backdrop {
  background: rgba(0, 0, 0, 0.5);
}

:root[data-theme="light"] .modal {
  background: #ffffff;                    /* --color-surface */
  border: 1px solid #e5e5e5;              /* --color-border */
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
}

:root[data-theme="light"] .modal-header {
  border-bottom: 1px solid #e5e5e5;       /* --color-border */
}

:root[data-theme="light"] .modal-title {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .modal-close {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .modal-close:hover {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .modal-body {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .modal-footer {
  border-top: 1px solid #e5e5e5;          /* --color-border */
}
```

### Popover/Dropdown (Light Mode)
```css
/* Light Mode - Popover/Dropdown (MediaManager) */
:root[data-theme="light"] .popover,
:root[data-theme="light"] .dropdown {
  background: #ffffff;                    /* --color-popover */
  border: 1px solid #e5e5e5;              /* --color-border */
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

:root[data-theme="light"] .popover-content,
:root[data-theme="light"] .dropdown-item {
  color: #1a1a1a;                         /* --color-popover-foreground */
}

:root[data-theme="light"] .dropdown-item:hover {
  background: #f5f5f5;                    /* --color-accent */
}

:root[data-theme="light"] .dropdown-divider {
  border-top: 1px solid #e5e5e5;          /* --color-border */
}
```

### Progress Bar (Light Mode)
```css
/* Light Mode - Progress Bar (MediaManager) */
:root[data-theme="light"] .progress {
  background: #e5e5e5;                    /* --color-input (track) */
}

:root[data-theme="light"] .progress-bar {
  background: #333333;                    /* --color-primary (fill) */
}

:root[data-theme="light"] .progress-text {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .progress-success .progress-bar {
  background: #10b981;                    /* --color-success */
}

:root[data-theme="light"] .progress-warning .progress-bar {
  background: #f59e0b;                    /* --color-warning */
}

:root[data-theme="light"] .progress-danger .progress-bar {
  background: #ef4444;                    /* --color-danger */
}
```

### Skeleton/Loader (Light Mode)
```css
/* Light Mode - Skeleton (MediaManager) */
:root[data-theme="light"] .skeleton {
  background: linear-gradient(
    90deg,
    #f5f5f5 25%,
    #ebebeb 50%,
    #f5f5f5 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
}

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

:root[data-theme="light"] .spinner {
  border: 2px solid #e5e5e5;              /* --color-border */
  border-top-color: #333333;              /* --color-primary */
}
```

### Pagination (Light Mode)
```css
/* Light Mode - Pagination (MediaManager) */
:root[data-theme="light"] .pagination {
  background: #ffffff;                    /* --color-surface */
}

:root[data-theme="light"] .pagination-item {
  color: #333333;                         /* --color-text-secondary */
  border: 1px solid #e5e5e5;              /* --color-border */
}

:root[data-theme="light"] .pagination-item:hover {
  background: #f5f5f5;                    /* --color-accent */
}

:root[data-theme="light"] .pagination-item.active {
  background: #333333;                    /* --color-primary */
  color: #fafafa;                         /* --color-primary-foreground */
  border-color: #333333;
}

:root[data-theme="light"] .pagination-item:disabled {
  color: #b3b3b3;                         /* --color-text-disabled */
  cursor: not-allowed;
}
```

### Breadcrumbs (Light Mode)
```css
/* Light Mode - Breadcrumbs (MediaManager) */
:root[data-theme="light"] .breadcrumbs a {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .breadcrumbs a:hover {
  color: #333333;                         /* --color-text-secondary */
}

:root[data-theme="light"] .breadcrumbs span {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .breadcrumbs-separator {
  color: #b3b3b3;                         /* --color-text-disabled */
}
```

### Tabs (Light Mode)
```css
/* Light Mode - Tabs (MediaManager) */
:root[data-theme="light"] .tabs {
  border-bottom: 1px solid #e5e5e5;       /* --color-border */
}

:root[data-theme="light"] .tab-item {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .tab-item:hover {
  color: #333333;                         /* --color-text-secondary */
}

:root[data-theme="light"] .tab-item.active {
  color: #1a1a1a;                         /* --color-text */
  border-bottom: 2px solid #333333;       /* --color-primary */
}
```

### Filter Panel (Light Mode)
```css
/* Light Mode - Filter Panel (MediaManager) */
:root[data-theme="light"] .filter-panel {
  background: #ffffff;                    /* --color-surface */
  border: 1px solid #e5e5e5;              /* --color-border */
}

:root[data-theme="light"] .filter-section-title {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .filter-item {
  color: #333333;                         /* --color-text-secondary */
}

:root[data-theme="light"] .filter-item:hover {
  background: #f5f5f5;                    /* --color-accent */
}

:root[data-theme="light"] .filter-item.active {
  background: #333333;                    /* --color-primary */
  color: #fafafa;                         /* --color-primary-foreground */
}

:root[data-theme="light"] .filter-clear {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .filter-clear:hover {
  color: #d32f2f;                         /* --color-destructive */
}
```

### Search Bar (Light Mode)
```css
/* Light Mode - Search Bar (MediaManager) */
:root[data-theme="light"] .search-bar {
  background: #f5f5f5;                    /* --color-surface-alt */
  border: 1px solid #e5e5e5;              /* --color-border */
}

:root[data-theme="light"] .search-bar:focus-within {
  border-color: #b3b3b3;                  /* --color-ring */
  background: #ffffff;                    /* --color-bg */
}

:root[data-theme="light"] .search-bar input {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .search-bar input::placeholder {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .search-bar-icon {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .search-bar-clear {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .search-bar-clear:hover {
  color: #1a1a1a;                         /* --color-text */
}
```

### Album Art (Light Mode)
```css
/* Light Mode - Album Art (MediaManager) */
:root[data-theme="light"] .album-art {
  background: #f5f5f5;                    /* --color-surface-alt (placeholder) */
  border: 1px solid #e5e5e5;              /* --color-border */
}

:root[data-theme="light"] .album-art-placeholder {
  background: #f5f5f5;                    /* --color-muted */
  color: #b3b3b3;                         /* --color-text-disabled */
}

:root[data-theme="light"] .album-art-overlay {
  background: rgba(0, 0, 0, 0.4);
}
```

### Activity Feed (Light Mode)
```css
/* Light Mode - Activity Feed (MediaManager) */
:root[data-theme="light"] .activity-feed {
  background: #ffffff;                    /* --color-surface */
}

:root[data-theme="light"] .activity-item {
  border-bottom: 1px solid #e5e5e5;       /* --color-border */
}

:root[data-theme="light"] .activity-item:hover {
  background: #fafafa;                    /* --color-bg-alt */
}

:root[data-theme="light"] .activity-icon {
  background: #f5f5f5;                    /* --color-muted */
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .activity-title {
  color: #1a1a1a;                         /* --color-text */
}

:root[data-theme="light"] .activity-description {
  color: #888888;                         /* --color-text-muted */
}

:root[data-theme="light"] .activity-time {
  color: #b3b3b3;                         /* --color-text-disabled */
}
```

---

## Usage Examples

### Complete Page Example

```html
{% extends "base.html" %}

{% block title %}Library - Artists{% endblock %}

{% block content %}
<div class="page-container">
  <!-- Page Header -->
  {% include 'components/layout/PageHeader.html' with {
    'title': 'Artists',
    'subtitle': 'Browse your music library',
    'actions': [
      {'label': 'Add Artist', 'icon': 'fa-solid fa-plus', 'variant': 'primary'}
    ]
  } %}

  <!-- Library View -->
  {% include 'components/specialized/LibraryView.html' with {
    'items': artists,
    'view_mode': view_mode,
    'filters': filters,
    'sort': sort,
    'total': total,
    'page': page,
    'per_page': per_page
  } %}
</div>
{% endblock %}
```

---

## Best Practices

### 1. **Component Reusability**
- Keep components generic and configurable
- Use props for customization
- Avoid hardcoding values

### 2. **Accessibility**
- Use semantic HTML
- Provide ARIA labels
- Ensure keyboard navigation
- Maintain focus management

### 3. **Performance**
- Lazy-load images
- Use virtual scrolling for long lists
- Minimize re-renders
- Optimize CSS selectors

### 4. **Consistency**
- Follow design system guidelines
- Use standard spacing and colors
- Maintain consistent naming conventions

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-26  
**Status**: Draft - Awaiting Approval
