# UI Design System - Version 3.0

> **⚠️ DEPRECATED - UNREALIZED DESIGN:** This v3.0 card-based UI was **never implemented**. Current UI uses HTMX + Pure CSS (`src/soulspot/templates/`). See `docs/feat-ui/README.md` and `docs/development/design-guidelines.md` for actual UI system.

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

## Overview

Version 3.0 replaces the current widget-based UI with a **clean, card-based design system**. This document defines the UI card catalog, design patterns, and component specifications to ensure consistency and prevent "UI garbage".

## Design Philosophy

**Core Principles:**
- **Clarity over complexity**: Each card has a single, clear purpose
- **Consistency**: Reusable card types with predictable behavior
- **Modularity**: Cards are module-agnostic and composable
- **Accessibility**: WCAG 2.1 AA compliance minimum
- **Performance**: Lazy loading, progressive enhancement

**Visual Language:**
- Clean, minimal aesthetic
- Generous whitespace
- Clear visual hierarchy
- Consistent spacing system (4px base unit)
- Limited color palette with semantic meaning

---

## Card Catalog

### 1. Status Card

**Purpose**: Display module/system status, health checks, and availability.

**Use Cases:**
- Module health dashboard
- Connection status (Spotify, Soulseek, MusicBrainz)
- System health overview
- Missing module warnings

**Anatomy:**
```
┌─────────────────────────────────────────┐
│ [Icon] Module Name              [Badge] │
│                                         │
│ Status: Active                          │
│ Last Check: 2 minutes ago               │
│                                         │
│ ▰▰▰▰▰▰▰▰▰▱ 90% Health                  │
│                                         │
│ [View Details]                          │
└─────────────────────────────────────────┘
```

**States:**
- ✅ Active (green badge)
- ⚠️  Warning (yellow badge)
- ❌ Inactive (red badge)
- ⏳ Loading (gray badge, pulsing)

**HTML Structure:**
```html
<div class="card card--status" data-module="soulseek">
  <div class="card__header">
    <div class="card__icon">
      <svg><!-- module icon --></svg>
    </div>
    <h3 class="card__title">Soulseek</h3>
    <span class="badge badge--success">Active</span>
  </div>
  
  <div class="card__body">
    <dl class="card__metadata">
      <div class="metadata__item">
        <dt>Status</dt>
        <dd>Active</dd>
      </div>
      <div class="metadata__item">
        <dt>Last Check</dt>
        <dd>2 minutes ago</dd>
      </div>
    </dl>
    
    <div class="progress-bar">
      <div class="progress-bar__fill" style="width: 90%"></div>
      <span class="progress-bar__label">90% Health</span>
    </div>
  </div>
  
  <div class="card__footer">
    <button class="btn btn--secondary btn--sm">View Details</button>
  </div>
</div>
```

**HTMX Integration:**
```html
<!-- Auto-refresh every 30 seconds -->
<div class="card card--status" 
     hx-get="/api/modules/soulseek/status"
     hx-trigger="every 30s"
     hx-swap="outerHTML">
  <!-- card content -->
</div>
```

---

### 2. Action Card

**Purpose**: Trigger operations or workflows (search, download, sync).

**Use Cases:**
- Search interface
- Download initiation
- Playlist sync triggers
- Quick actions

**Anatomy:**
```
┌─────────────────────────────────────────┐
│ [Icon] Search Track                     │
│                                         │
│ ┌─────────────────────────────────┐   │
│ │ Search for songs...              │   │
│ └─────────────────────────────────┘   │
│                                         │
│ [Search] [Advanced]                     │
└─────────────────────────────────────────┘
```

**HTML Structure:**
```html
<div class="card card--action">
  <div class="card__header">
    <div class="card__icon">
      <svg><!-- search icon --></svg>
    </div>
    <h3 class="card__title">Search Track</h3>
  </div>
  
  <form class="card__body" 
        hx-post="/api/spotify/search"
        hx-target="#search-results"
        hx-indicator="#search-spinner">
    <div class="form-group">
      <input type="text" 
             name="query" 
             class="input input--lg"
             placeholder="Search for songs..."
             required>
    </div>
    
    <div class="card__actions">
      <button type="submit" class="btn btn--primary">
        Search
      </button>
      <button type="button" class="btn btn--secondary">
        Advanced
      </button>
    </div>
  </form>
  
  <div id="search-spinner" class="htmx-indicator">
    <div class="spinner"></div>
  </div>
</div>
```

---

### 3. Data Card

**Purpose**: Display structured data (track info, download details, statistics).

**Use Cases:**
- Track/album information
- Download progress
- Statistics and metrics
- Configuration summary

**Anatomy:**
```
┌─────────────────────────────────────────┐
│ [Album Art] Track Title                 │
│             Artist Name                  │
│                                         │
│ Album: Album Name                       │
│ Duration: 3:45                          │
│ Quality: 320 kbps                       │
│                                         │
│ [Play] [Download] [More]                │
└─────────────────────────────────────────┘
```

**HTML Structure:**
```html
<div class="card card--data" data-track-id="spotify:track:123">
  <div class="card__media">
    <img src="/api/albums/cover.jpg" 
         alt="Album cover"
         class="card__image">
  </div>
  
  <div class="card__content">
    <h3 class="card__title">Let It Be</h3>
    <p class="card__subtitle">The Beatles</p>
    
    <dl class="card__metadata">
      <div class="metadata__item">
        <dt>Album</dt>
        <dd>Let It Be</dd>
      </div>
      <div class="metadata__item">
        <dt>Duration</dt>
        <dd>3:45</dd>
      </div>
      <div class="metadata__item">
        <dt>Quality</dt>
        <dd>320 kbps</dd>
      </div>
    </dl>
  </div>
  
  <div class="card__footer">
    <button class="btn btn--primary btn--sm">Play</button>
    <button class="btn btn--secondary btn--sm" 
            hx-post="/api/downloads"
            hx-vals='{"track_id": "spotify:track:123"}'>
      Download
    </button>
    <button class="btn btn--ghost btn--sm">More</button>
  </div>
</div>
```

---

### 4. Progress Card

**Purpose**: Show ongoing operations with progress indicators.

**Use Cases:**
- Download progress
- Import progress
- Sync progress
- Batch operations

**Anatomy:**
```
┌─────────────────────────────────────────┐
│ Downloading: Beatles - Let It Be        │
│                                         │
│ ▰▰▰▰▰▰▰▱▱▱ 75%                         │
│                                         │
│ 3.5 MB / 4.7 MB · 2m 15s remaining     │
│                                         │
│ [Pause] [Cancel]                        │
└─────────────────────────────────────────┘
```

**HTML Structure:**
```html
<div class="card card--progress" 
     hx-get="/api/downloads/dl-456/progress"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  <div class="card__header">
    <h3 class="card__title">Downloading: Beatles - Let It Be</h3>
  </div>
  
  <div class="card__body">
    <div class="progress-bar progress-bar--lg">
      <div class="progress-bar__fill" style="width: 75%"></div>
      <span class="progress-bar__label">75%</span>
    </div>
    
    <div class="card__stats">
      <span>3.5 MB / 4.7 MB</span>
      <span>·</span>
      <span>2m 15s remaining</span>
    </div>
  </div>
  
  <div class="card__footer">
    <button class="btn btn--secondary btn--sm"
            hx-post="/api/downloads/dl-456/pause">
      Pause
    </button>
    <button class="btn btn--ghost btn--sm"
            hx-delete="/api/downloads/dl-456">
      Cancel
    </button>
  </div>
</div>
```

**Server-Sent Events Integration:**
```html
<!-- Real-time updates via SSE -->
<div class="card card--progress" 
     sse-connect="/api/downloads/dl-456/events"
     sse-swap="progress">
  <!-- card content -->
</div>
```

---

### 5. List Card

**Purpose**: Display collections of items (playlist tracks, search results, queue).

**Use Cases:**
- Search results list
- Download queue
- Playlist view
- Module list

**Anatomy:**
```
┌─────────────────────────────────────────┐
│ Download Queue (3 items)         [Sort] │
│                                         │
│ ┌─ Item 1 ──────────────────────────┐  │
│ │ [Icon] Track Name                 │  │
│ │        Artist · Album       [🗑]  │  │
│ └───────────────────────────────────┘  │
│                                         │
│ ┌─ Item 2 ──────────────────────────┐  │
│ │ [Icon] Track Name                 │  │
│ │        Artist · Album       [🗑]  │  │
│ └───────────────────────────────────┘  │
│                                         │
│ ┌─ Item 3 ──────────────────────────┐  │
│ │ [Icon] Track Name                 │  │
│ │        Artist · Album       [🗑]  │  │
│ └───────────────────────────────────┘  │
│                                         │
│ [Clear All]                             │
└─────────────────────────────────────────┘
```

**HTML Structure:**
```html
<div class="card card--list">
  <div class="card__header">
    <h3 class="card__title">Download Queue (3 items)</h3>
    <button class="btn btn--ghost btn--sm">Sort</button>
  </div>
  
  <ul class="card__list">
    <li class="list-item" data-download-id="dl-123">
      <div class="list-item__icon">
        <svg><!-- music icon --></svg>
      </div>
      <div class="list-item__content">
        <h4 class="list-item__title">Let It Be</h4>
        <p class="list-item__subtitle">The Beatles · Let It Be</p>
      </div>
      <button class="list-item__action"
              hx-delete="/api/downloads/dl-123"
              hx-target="closest .list-item"
              hx-swap="outerHTML swap:1s">
        🗑
      </button>
    </li>
    
    <!-- More items... -->
  </ul>
  
  <div class="card__footer">
    <button class="btn btn--ghost"
            hx-delete="/api/downloads/queue"
            hx-confirm="Clear all downloads?">
      Clear All
    </button>
  </div>
</div>
```

---

### 6. Alert Card

**Purpose**: Display warnings, errors, or important notifications.

**Use Cases:**
- Missing module warnings
- Connection errors
- Configuration issues
- Success/error messages

**Anatomy:**
```
┌─────────────────────────────────────────┐
│ ⚠️  Module Missing                      │
│                                         │
│ Operation 'download.track' requires:    │
│ • Soulseek module                       │
│                                         │
│ Please enable the Soulseek module to    │
│ use download functionality.             │
│                                         │
│ [Enable Module] [Dismiss]               │
└─────────────────────────────────────────┘
```

**Severity Levels:**
- `alert--error` (red)
- `alert--warning` (yellow)
- `alert--info` (blue)
- `alert--success` (green)

**HTML Structure:**
```html
<div class="card card--alert alert--warning">
  <div class="card__header">
    <div class="card__icon">⚠️</div>
    <h3 class="card__title">Module Missing</h3>
    <button class="card__close" aria-label="Dismiss">×</button>
  </div>
  
  <div class="card__body">
    <p>Operation 'download.track' requires:</p>
    <ul>
      <li>Soulseek module</li>
    </ul>
    <p>Please enable the Soulseek module to use download functionality.</p>
  </div>
  
  <div class="card__footer">
    <button class="btn btn--primary"
            hx-post="/api/modules/soulseek/enable">
      Enable Module
    </button>
    <button class="btn btn--ghost"
            hx-delete="/api/alerts/missing-module-soulseek">
      Dismiss
    </button>
  </div>
</div>
```

---

### 7. Form Card

**Purpose**: Collect user input with validation.

**Use Cases:**
- Onboarding credential collection
- Settings/configuration
- Advanced search
- Module configuration

**Anatomy:**
```
┌─────────────────────────────────────────┐
│ Spotify Configuration                   │
│                                         │
│ Client ID *                             │
│ ┌─────────────────────────────────┐   │
│ │ your_client_id                   │   │
│ └─────────────────────────────────┘   │
│                                         │
│ Client Secret *                         │
│ ┌─────────────────────────────────┐   │
│ │ ••••••••••••••••                │   │
│ └─────────────────────────────────┘   │
│                                         │
│ [Test Connection] [Save]                │
└─────────────────────────────────────────┘
```

**HTML Structure:**
```html
<div class="card card--form">
  <div class="card__header">
    <h3 class="card__title">Spotify Configuration</h3>
  </div>
  
  <form class="card__body"
        hx-post="/api/modules/spotify/config"
        hx-target="#config-result">
    <div class="form-group">
      <label for="client-id" class="form-label">
        Client ID <span class="required">*</span>
      </label>
      <input type="text" 
             id="client-id"
             name="client_id"
             class="input"
             placeholder="your_client_id"
             required>
      <span class="form-hint">
        Get this from Spotify Developer Dashboard
      </span>
    </div>
    
    <div class="form-group">
      <label for="client-secret" class="form-label">
        Client Secret <span class="required">*</span>
      </label>
      <input type="password" 
             id="client-secret"
             name="client_secret"
             class="input"
             placeholder="••••••••••••••••"
             required>
    </div>
    
    <div id="config-result"></div>
    
    <div class="card__actions">
      <button type="button" 
              class="btn btn--secondary"
              hx-post="/api/modules/spotify/test-connection"
              hx-include="[name='client_id'], [name='client_secret']"
              hx-target="#config-result">
        Test Connection
      </button>
      <button type="submit" class="btn btn--primary">
        Save
      </button>
    </div>
  </form>
</div>
```

---

## Design Tokens

### Spacing Scale (4px base)
```css
--space-xs: 4px;   /* 0.25rem */
--space-sm: 8px;   /* 0.5rem */
--space-md: 16px;  /* 1rem */
--space-lg: 24px;  /* 1.5rem */
--space-xl: 32px;  /* 2rem */
--space-2xl: 48px; /* 3rem */
```

### Typography Scale
```css
--text-xs: 0.75rem;   /* 12px */
--text-sm: 0.875rem;  /* 14px */
--text-base: 1rem;    /* 16px */
--text-lg: 1.125rem;  /* 18px */
--text-xl: 1.25rem;   /* 20px */
--text-2xl: 1.5rem;   /* 24px */
--text-3xl: 1.875rem; /* 30px */
```

### Color Palette
```css
/* Semantic Colors */
--color-primary: #3b82f6;      /* Blue */
--color-success: #10b981;      /* Green */
--color-warning: #f59e0b;      /* Yellow */
--color-error: #ef4444;        /* Red */

/* Neutral Colors */
--color-bg-base: #ffffff;
--color-bg-muted: #f9fafb;
--color-bg-subtle: #f3f4f6;

--color-text-primary: #111827;
--color-text-secondary: #6b7280;
--color-text-muted: #9ca3af;

--color-border: #e5e7eb;
--color-border-strong: #d1d5db;

/* Dark Mode */
@media (prefers-color-scheme: dark) {
  --color-bg-base: #111827;
  --color-bg-muted: #1f2937;
  --color-bg-subtle: #374151;
  
  --color-text-primary: #f9fafb;
  --color-text-secondary: #d1d5db;
  --color-text-muted: #9ca3af;
  
  --color-border: #374151;
  --color-border-strong: #4b5563;
}
```

### Border Radius
```css
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-xl: 16px;
--radius-full: 9999px;
```

### Shadows
```css
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
--shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1);
```

---

## Card Base Styles

```css
/* Base Card */
.card {
  background: var(--color-bg-base);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: all 0.2s ease;
}

.card:hover {
  box-shadow: var(--shadow-md);
}

/* Card Header */
.card__header {
  padding: var(--space-lg);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.card__icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
}

.card__title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
  flex: 1;
}

/* Card Body */
.card__body {
  padding: var(--space-lg);
}

/* Card Footer */
.card__footer {
  padding: var(--space-lg);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-muted);
  display: flex;
  gap: var(--space-sm);
  justify-content: flex-end;
}
```

---

## Responsive Grid System

**Card Grid Layout:**
```html
<div class="card-grid">
  <div class="card"><!-- Card 1 --></div>
  <div class="card"><!-- Card 2 --></div>
  <div class="card"><!-- Card 3 --></div>
</div>
```

**CSS Grid:**
```css
.card-grid {
  display: grid;
  gap: var(--space-lg);
  
  /* Responsive columns */
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}

/* 2-column on medium screens */
@media (min-width: 768px) {
  .card-grid--2col {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 3-column on large screens */
@media (min-width: 1024px) {
  .card-grid--3col {
    grid-template-columns: repeat(3, 1fr);
  }
}
```

---

## Module-Specific Card Examples

### Soulseek Module

**Download Queue Card:**
```html
<div class="card card--list" 
     hx-get="/api/soulseek/queue"
     hx-trigger="every 5s">
  <div class="card__header">
    <h3 class="card__title">Download Queue</h3>
    <span class="badge">3 active</span>
  </div>
  
  <ul class="card__list" id="download-queue">
    <!-- List items dynamically loaded -->
  </ul>
</div>
```

### Spotify Module

**Track Search Card:**
```html
<div class="card card--action">
  <div class="card__header">
    <h3 class="card__title">Search Spotify</h3>
  </div>
  
  <form class="card__body"
        hx-post="/api/spotify/search"
        hx-target="#search-results">
    <input type="text" 
           name="query"
           class="input input--lg"
           placeholder="Search for tracks, albums, artists...">
    
    <button type="submit" class="btn btn--primary btn--block">
      Search
    </button>
  </form>
</div>

<div id="search-results" class="card-grid">
  <!-- Results loaded here -->
</div>
```

---

## Accessibility Requirements

**Every card MUST:**
1. Have proper heading hierarchy (h1 → h2 → h3)
2. Include ARIA labels for icon-only buttons
3. Support keyboard navigation (tab order, focus states)
4. Provide focus indicators (`:focus-visible`)
5. Have sufficient color contrast (WCAG AA minimum)
6. Support screen readers (semantic HTML, ARIA roles)

**Example:**
```html
<button class="btn btn--ghost" 
        aria-label="Delete track from queue">
  <svg aria-hidden="true"><!-- icon --></svg>
</button>
```

---

## Performance Guidelines

1. **Lazy Loading**: Cards below fold load on scroll
2. **Progressive Enhancement**: Core functionality works without JS
3. **HTMX Optimization**: Use `hx-swap` strategies to minimize reflow
4. **Image Optimization**: WebP format, lazy loading, proper sizing
5. **CSS Containment**: Use `contain: layout style` on cards

```html
<!-- Lazy load cards -->
<div class="card" 
     hx-get="/api/cards/stats"
     hx-trigger="revealed"
     hx-swap="outerHTML">
  <div class="card__skeleton">Loading...</div>
</div>
```

---

## Card Composition Patterns

### Dashboard Layout
```html
<div class="dashboard">
  <div class="dashboard__sidebar">
    <!-- Status cards, navigation -->
    <div class="card card--status">...</div>
  </div>
  
  <div class="dashboard__main">
    <div class="card-grid">
      <!-- Action cards, data cards -->
      <div class="card card--action">...</div>
      <div class="card card--data">...</div>
    </div>
  </div>
</div>
```

### Modal Card
```html
<div class="modal" id="config-modal">
  <div class="modal__backdrop"></div>
  <div class="card card--form modal__content">
    <!-- Form card content -->
  </div>
</div>
```

---

## Migration from Current UI

**Current Widgets → New Cards Mapping:**

| Current Widget | New Card Type | Notes |
|---------------|---------------|-------|
| Module status widget | Status Card | Use health badge states |
| Search widget | Action Card | Add HTMX form handling |
| Download queue widget | List Card + Progress Card | Split queue list and individual progress |
| Track info widget | Data Card | Add media section for album art |
| Error messages | Alert Card | Use severity levels |
| Configuration forms | Form Card | Add test connection action |

**Migration Steps:**
1. Create card CSS framework (design tokens + base styles)
2. Build card components in Soulseek module (pilot)
3. Test accessibility and responsiveness
4. Document card usage in module docs/
5. Migrate remaining modules to cards
6. Remove old widget system

---

## Implementation Checklist

**Phase 1: Foundation (Week 1)**
- [ ] Create design token CSS file
- [ ] Implement base card styles
- [ ] Create card grid system
- [ ] Set up HTMX integration patterns

**Phase 2: Core Cards (Week 2)**
- [ ] Implement Status Card
- [ ] Implement Action Card
- [ ] Implement Data Card
- [ ] Implement Progress Card
- [ ] Test accessibility compliance

**Phase 3: Extended Cards (Week 3)**
- [ ] Implement List Card
- [ ] Implement Alert Card
- [ ] Implement Form Card
- [ ] Create card composition patterns

**Phase 4: Module Integration (Week 4-6)**
- [ ] Migrate Soulseek module UI
- [ ] Migrate Spotify module UI
- [ ] Migrate Library module UI
- [ ] Migrate Metadata module UI

**Phase 5: Polish (Week 7)**
- [ ] Dark mode support
- [ ] Animation polish
- [ ] Performance optimization
- [ ] Documentation completion

---

## Next Steps

1. Review card catalog with design team
2. Create Figma mockups for each card type
3. Build CSS framework with design tokens
4. Implement cards in Soulseek module (pilot)
5. Document learnings and iterate on catalog

**This catalog prevents "UI garbage" by:**
- ✅ Defining exactly 7 card types (no ad-hoc widgets)
- ✅ Providing complete HTML/CSS templates
- ✅ Establishing clear use cases for each type
- ✅ Setting accessibility and performance standards
- ✅ Creating composition patterns for common layouts
