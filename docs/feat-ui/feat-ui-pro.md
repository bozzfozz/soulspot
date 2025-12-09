# SoulSpot UI Redesign – Master Plan (Pro Edition)

**Version**: 1.0  
**Status**: 🎯 Ready for Implementation  
**Date**: December 7, 2025

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Phase 1: Foundation (CSS Design Tokens & Variables)](#phase-1-foundation)
3. [Phase 2: Core Components (Layout, Data Display, Forms)](#phase-2-core-components)
4. [Phase 3: Pro Features (Command Palette, Mobile Bottom Sheets, Search)](#phase-3-pro-features)
5. [Phase 4: Polish & Integration (Animations, Light Mode, Testing)](#phase-4-polish--integration)
6. [Technical Architecture](#technical-architecture)
7. [Build-Less Strategy (Pure CSS)](#build-less-strategy)
8. [Quality Gates & Testing](#quality-gates--testing)
9. [Rollout & Documentation](#rollout--documentation)
10. [Risk Assessment & Mitigation](#risk-assessment--mitigation)

---

## Executive Summary

### Vision
Transform SoulSpot's UI into a **professional, scalable, and intuitive system** that balances **premium aesthetics** (glassmorphism, dark mode by default) with **functional clarity** (MediaManager-inspired UX patterns) and **enterprise-grade Pro features** (Command Palette, advanced filtering, queue management).

### Constraints
- ❌ **No npm build steps** – Pure CSS-in-HTML, Bootstrap Icons, HTMX
- ✅ **Hexagonal Architecture** – Domain-driven design, port/repository sync
- ✅ **WCAG AA Compliance** – Light Mode support (MediaManager reference colors)
- ✅ **Backwards Compatibility** – Legacy components coexist during migration

### Outcomes
- **Phase 1 → 4** delivered incrementally (each phase is independently testable)
- **50+ reusable Jinja2 components** organized by concern (layout, forms, feedback, specialized)
- **Pro Command Palette** (Cmd+K / Ctrl+K) with fuzzy search + keyboard nav
- **Mobile-first responsive** with bottom sheet modals for mobile flows
- **Light/Dark theme toggle** with persistent user preference (Pydantic Settings)
- **Zero breaking changes** to existing routes (component macros are additive)

---

## Phase 1: Foundation (CSS Design Tokens & Variables)

### 1.1 Objective
Establish a **single source of truth** for colors, spacing, typography, and animations using CSS custom properties. Light Mode colors derived from [MediaManager design system](https://github.com/maxdorninger/MediaManager) for consistency.

### 1.2 Deliverables

#### File: `src/soulspot/static/new-ui/css/variables.css`
**Status**: ✅ Exists (needs enhancement)

**Enhancements**:
```css
/* ===== SERVICE-SPECIFIC COLORS ===== */
/* Hey future me - Spotify is primary, but leaving room for Tidal/Deezer in the future
   Each service gets its own brand color palette for clear visual distinction */

:root {
  /* Spotify Green */
  --spotify-green: #1db954;
  --spotify-green-dark: #1ed760;
  --spotify-green-subtle: rgba(29, 185, 84, 0.1);
  
  /* Tidal Cyan (placeholder for future) */
  --tidal-cyan: #00d9ff;
  --tidal-cyan-subtle: rgba(0, 217, 255, 0.1);
}

/* ===== LAYOUT GRID SYSTEM ===== */
:root {
  /* Breakpoints (mobile-first) */
  --breakpoint-sm: 640px;   /* Mobile landscape */
  --breakpoint-md: 768px;   /* Tablet portrait */
  --breakpoint-lg: 1024px;  /* Tablet landscape / small desktop */
  --breakpoint-xl: 1280px;  /* Desktop */
  --breakpoint-2xl: 1536px; /* Large desktop */
  
  /* Container widths */
  --container-xs: 320px;
  --container-sm: 640px;
  --container-md: 768px;
  --container-lg: 1024px;
  --container-xl: 1280px;
  --container-2xl: 1536px;
}

/* ===== ANIMATION PRESETS ===== */
:root {
  /* Magic UI animations (Pure CSS @keyframes) */
  --animation-shimmer: shimmer 2s infinite;
  --animation-blur-fade: blurFade 0.6s ease-out;
  --animation-bounce-in: bounceIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
  --animation-float: float 3s ease-in-out infinite;
}

/* ===== GLASSMORPHISM ===== */
:root {
  --glass-bg: rgba(31, 41, 55, 0.8);      /* Dark theme */
  --glass-border: rgba(255, 255, 255, 0.1);
  --glass-backdrop: blur(10px);
}

:root[data-theme="light"] {
  --glass-bg: rgba(255, 255, 255, 0.8);
  --glass-border: rgba(0, 0, 0, 0.05);
}
```

**Why**: Centralizes all design decisions, enables fast theme switching, supports future service integration.

#### File: `src/soulspot/static/new-ui/css/animations.css` (NEW)
**Pure CSS Magic UI animations** (no npm/build required):

```css
/* ===== MAGIC UI ANIMATIONS (Pure CSS) ===== */
/* Hey future me - These @keyframes are ported from Magic UI library
   without the build step. Used for loading states, card reveals, transitions.
   Test in all browsers: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+ */

/* Shimmer: Loading skeleton effect */
@keyframes shimmer {
  0% {
    background-position: -1000px 0;
  }
  100% {
    background-position: 1000px 0;
  }
}

.shimmer {
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 0%,
    var(--bg-quaternary) 50%,
    var(--bg-tertiary) 100%
  );
  background-size: 1000px 100%;
  animation: var(--animation-shimmer);
}

/* Blur Fade: Fade in with blur effect */
@keyframes blurFade {
  from {
    opacity: 0;
    filter: blur(10px);
  }
  to {
    opacity: 1;
    filter: blur(0);
  }
}

.blur-fade {
  animation: var(--animation-blur-fade);
}

/* Bounce In: Spring-like entrance */
@keyframes bounceIn {
  0% {
    opacity: 0;
    transform: scale(0.3);
  }
  50% {
    opacity: 1;
    transform: scale(1.05);
  }
  70% {
    transform: scale(0.9);
  }
  100% {
    transform: scale(1);
  }
}

.bounce-in {
  animation: var(--animation-bounce-in);
}

/* Float: Gentle floating motion */
@keyframes float {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-10px);
  }
}

.float {
  animation: var(--animation-float);
}

/* Slide In (from top, bottom, left, right) */
@keyframes slideInTop {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideInBottom {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.slide-in-top { animation: slideInTop 0.4s ease-out; }
.slide-in-bottom { animation: slideInBottom 0.4s ease-out; }
.slide-in-left { animation: slideInLeft 0.4s ease-out; }
.slide-in-right { animation: slideInRight 0.4s ease-out; }

/* Pulse: Gentle breathing effect */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Spin: Rotation loader */
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.spin {
  animation: spin 1s linear infinite;
}

/* Flip: Card reveal */
@keyframes flip {
  0% {
    transform: perspective(400px) rotateY(-90deg);
    opacity: 0;
  }
  100% {
    transform: perspective(400px) rotateY(0deg);
    opacity: 1;
  }
}

.flip {
  animation: flip 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

/* Glow: Pulse with color */
@keyframes glow {
  0%, 100% {
    box-shadow: 0 0 5px rgba(254, 65, 85, 0.5);
  }
  50% {
    box-shadow: 0 0 20px rgba(254, 65, 85, 0.8);
  }
}

.glow {
  animation: glow 2s ease-in-out infinite;
}
```

**Why**: Foundation for all animated UI feedback (loaders, transitions, reveals).

---

## Phase 2: Core Components (Layout, Data Display, Forms)

### 2.1 Objective
Create **modular, reusable Jinja2 components** for all common UI patterns. Each component is:
- Self-contained (HTML + CSS classes)
- Parameterized (via macro arguments)
- Accessible (semantic HTML, ARIA labels)
- Light Mode ready (color variables mapped)

### 2.2 Component Inventory

#### Layout Components (`templates/components/layout/`)

| Component | File | Purpose | Status |
|-----------|------|---------|--------|
| **Sidebar** | `sidebar.html` | Main navigation, collapsible | Phase 2 |
| **TopBar** | `topbar.html` | Header with search + user menu | Phase 2 |
| **PageHeader** | `page-header.html` | Page title + breadcrumbs + actions | Phase 2 |
| **Container** | `container.html` | Responsive max-width wrapper | Phase 2 |

#### Data Display Components (`templates/components/data-display/`)

| Component | File | Purpose | Status |
|-----------|------|---------|--------|
| **Card** | `card.html` | Generic card with image, title, actions | Phase 2 |
| **Table** | `table.html` | Sortable, filterable data table | Phase 2 |
| **Grid** | `grid.html` | Responsive image/album grid | Phase 2 |
| **List** | `list.html` | Vertical list items (tracks, playlists) | Phase 2 |
| **Badge** | `badge.html` | Status indicators (active, pending, etc.) | Phase 2 |

#### Form Components (`templates/components/forms/`)

| Component | File | Purpose | Status |
|-----------|------|---------|--------|
| **Input** | `input.html` | Text, email, password, tel fields | Phase 2 |
| **Select** | `select.html` | Dropdown with custom styling | Phase 2 |
| **Checkbox** | `checkbox.html` | Styled checkbox groups | Phase 2 |
| **Radio** | `radio.html` | Radio button groups | Phase 2 |
| **Toggle** | `toggle.html` | On/off switch | Phase 2 |
| **SearchBar** | `search-bar.html` | Search with icon + clear button | Phase 2 |
| **FilterPanel** | `filter-panel.html` | Multi-filter sidebar (artists, genres, years) | Phase 2 |

#### Feedback Components (`templates/components/feedback/`)

| Component | File | Purpose | Status |
|-----------|------|---------|--------|
| **Alert** | `alert.html` | Info, success, warning, error messages | Phase 2 |
| **Toast** | `toast.html` | Non-blocking notifications (top-right) | Phase 2 |
| **Modal** | `modal.html` | Centered dialog with header/body/footer | Phase 2 |
| **Loading** | `loading.html` | Spinner, skeleton, progress bar | Phase 2 |
| **ProgressBar** | `progress-bar.html` | Linear progress with percentage | Phase 2 |

#### Navigation Components (`templates/components/navigation/`)

| Component | File | Purpose | Status |
|-----------|------|---------|--------|
| **Breadcrumbs** | `breadcrumbs.html` | Navigation path | Phase 2 |
| **Tabs** | `tabs.html` | Horizontal tabs (HTMX-enabled) | Phase 2 |
| **Pagination** | `pagination.html` | Page navigation (HTMX lazy-load) | Phase 2 |

### 2.3 Implementation Example: Card Component

**File**: `src/soulspot/templates/components/data-display/card.html`

```html
{#
  Card Component - Generic reusable card for albums, artists, playlists
  
  Usage:
    {% include 'components/data-display/card.html' with {
      'title': 'Dark Side of the Moon',
      'subtitle': 'Pink Floyd',
      'image': '/static/images/album.jpg',
      'image_type': 'album',  # 'album' | 'artist' (circular)
      'metadata': [
        {'label': 'Year', 'value': '1973'},
        {'label': 'Tracks', 'value': '10'},
        {'label': 'Type', 'value': 'Album'}
      ],
      'actions': [
        {'icon': 'fa-solid fa-play', 'label': 'Play', 'variant': 'primary', 'htmx_post': '/api/queue/play'},
        {'icon': 'fa-solid fa-plus', 'label': 'Add', 'variant': 'outline', 'htmx_post': '/api/library/add'}
      ],
      'status_badge': 'downloaded',  # 'downloaded' | 'streaming' | null
      'variant': 'default'  # 'default' | 'glass' | 'hover'
    } %}
#}

<div class="card card-{{ variant or 'default' }}" role="article">
  {# Image Section #}
  {% if image %}
  <div class="card-image {% if image_type == 'artist' %}card-image-circular{% endif %}">
    <img src="{{ image }}" alt="{{ title }}" loading="lazy" class="card-image-img">
    
    {# Play Button Overlay (hover) #}
    <div class="card-overlay">
      {% if actions %}
        {% set play_action = actions|selectattr('label', 'equalto', 'Play')|first %}
        {% if play_action %}
        <button class="card-play-btn" 
                hx-post="{{ play_action.htmx_post }}"
                hx-target="body"
                title="Play">
          <i class="fa-solid fa-play"></i>
        </button>
        {% endif %}
      {% endif %}
    </div>
    
    {# Status Badge (top-left) #}
    {% if status_badge %}
    <span class="card-status badge badge-{{ status_badge }}">
      {% if status_badge == 'downloaded' %}
        <i class="fa-solid fa-check"></i> Downloaded
      {% elif status_badge == 'streaming' %}
        <i class="fa-solid fa-cloud"></i> Streaming
      {% endif %}
    </span>
    {% endif %}
  </div>
  {% endif %}

  {# Content Section #}
  <div class="card-content">
    {% if title %}
    <h3 class="card-title">{{ title }}</h3>
    {% endif %}
    
    {% if subtitle %}
    <p class="card-subtitle">{{ subtitle }}</p>
    {% endif %}
    
    {% if metadata %}
    <div class="card-metadata">
      {% for item in metadata %}
      <div class="card-meta-item">
        <span class="card-meta-label">{{ item.label }}:</span>
        <span class="card-meta-value">{{ item.value }}</span>
      </div>
      {% endfor %}
    </div>
    {% endif %}
  </div>

  {# Actions Section #}
  {% if actions %}
  <div class="card-actions">
    {% for action in actions %}
    <button class="btn btn-{{ action.variant or 'primary' }} btn-sm"
            {% if action.htmx_post %}
            hx-post="{{ action.htmx_post }}"
            hx-target="body"
            {% if action.hx_confirm %}
            hx-confirm="{{ action.hx_confirm }}"
            {% endif %}
            {% endif %}
            title="{{ action.label }}">
      {% if action.icon %}<i class="{{ action.icon }}"></i>{% endif %}
      {% if action.show_label != false %}{{ action.label }}{% endif %}
    </button>
    {% endfor %}
  </div>
  {% endif %}
</div>

<style>
.card {
  background: var(--bg-secondary);
  border: var(--border-width) solid var(--border-primary);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  transition: all var(--transition-normal);
}

.card.hover:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.card.glass {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-backdrop);
  border-color: var(--glass-border);
}

.card-image {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
}

.card-image-circular {
  border-radius: var(--radius-full);
}

.card-image-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.card:hover .card-overlay {
  opacity: 1;
}

.card-play-btn {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  background: var(--accent-primary);
  border: none;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-lg);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.card-play-btn:hover {
  transform: scale(1.1);
}

.card-status {
  position: absolute;
  top: var(--space-3);
  left: var(--space-3);
  z-index: var(--z-base);
}

.card-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-subtitle {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0;
}

.card-metadata {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
}

.card-meta-item {
  display: flex;
  justify-content: space-between;
}

.card-meta-label {
  color: var(--text-muted);
}

.card-meta-value {
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}

.card-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
  border-top: var(--border-width) solid var(--border-primary);
  padding-top: var(--space-3);
  margin-top: var(--space-2);
}

/* Light Mode */
:root[data-theme="light"] .card-overlay {
  background: rgba(0, 0, 0, 0.4);
}
</style>
```

**Why**: Card is the most reused component; demonstrates full pattern (HTML + CSS + Jinja2 flexibility).

---

## Phase 3: Pro Features (Command Palette, Mobile Bottom Sheets, Search)

### 3.1 Objective
Implement **enterprise-grade interactions** that separate Pro users from casual ones:
- **Command Palette** (Cmd+K or Ctrl+K) – Fuzzy search + keyboard navigation for power users
- **Mobile Bottom Sheets** – Native-feeling modals for mobile flows (artist selection, filters)
- **Advanced Search** – Multi-field search with real-time HTMX results
- **Queue Manager** – Drag-and-drop reordering, pause/resume controls

### 3.2 Command Palette Component

**File**: `src/soulspot/templates/components/specialized/command-palette.html`

```html
{#
  Command Palette - Pro Feature for power users
  
  Triggered by:
  - Cmd+K (macOS)
  - Ctrl+K (Windows/Linux)
  
  Features:
  - Fuzzy search across tracks, artists, albums, playlists, settings
  - Keyboard navigation (↑/↓, Enter, Escape)
  - Recent searches (localStorage)
  - Action categories (Play, Add, Download, Settings)
  
  Usage: Included in base.html, always available
#}

<div id="command-palette" class="command-palette" hidden>
  <div class="command-palette-backdrop"></div>
  
  <div class="command-palette-container">
    <div class="command-palette-header">
      <i class="fa-solid fa-search"></i>
      <input 
        type="text" 
        class="command-palette-input" 
        placeholder="Search tracks, artists, albums, playlists, settings..."
        autocomplete="off"
        id="command-palette-input"
      >
      <span class="command-palette-hint">ESC to close</span>
    </div>
    
    <div class="command-palette-content">
      {# Results will be populated by HTMX #}
      <div id="command-results" class="command-palette-results">
        {# Default: Show recent searches #}
        <div class="command-group" id="recent-group" hidden>
          <div class="command-group-title">Recent Searches</div>
          <div id="recent-list"></div>
        </div>
        
        {# Tracks #}
        <div class="command-group" id="tracks-group" hidden>
          <div class="command-group-title">Tracks</div>
          <div id="tracks-list"></div>
        </div>
        
        {# Artists #}
        <div class="command-group" id="artists-group" hidden>
          <div class="command-group-title">Artists</div>
          <div id="artists-list"></div>
        </div>
        
        {# Playlists #}
        <div class="command-group" id="playlists-group" hidden>
          <div class="command-group-title">Playlists</div>
          <div id="playlists-list"></div>
        </div>
        
        {# Actions #}
        <div class="command-group" id="actions-group" hidden>
          <div class="command-group-title">Actions</div>
          <div id="actions-list"></div>
        </div>
        
        {# Settings #}
        <div class="command-group" id="settings-group" hidden>
          <div class="command-group-title">Settings</div>
          <div id="settings-list"></div>
        </div>
        
        {# No Results #}
        <div id="no-results" class="command-no-results" hidden>
          <i class="fa-solid fa-search"></i>
          <p>No results found</p>
        </div>
      </div>
    </div>
    
    <div class="command-palette-footer">
      <span class="command-shortcut">↑↓</span> Navigate
      <span class="command-shortcut">Enter</span> Select
      <span class="command-shortcut">ESC</span> Close
    </div>
  </div>
</div>

<style>
.command-palette {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 100px;
  backdrop-filter: blur(2px);
}

.command-palette:not([hidden]) {
  display: flex;
  animation: fadeIn var(--transition-normal);
}

.command-palette-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  cursor: pointer;
}

.command-palette-container {
  position: relative;
  width: 100%;
  max-width: 600px;
  background: var(--bg-secondary);
  border: var(--border-width) solid var(--border-primary);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 70vh;
  animation: slideInTop 0.3s ease-out;
}

.command-palette-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border-bottom: var(--border-width) solid var(--border-primary);
  background: var(--bg-secondary);
}

.command-palette-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
}

.command-palette-input::placeholder {
  color: var(--text-muted);
}

.command-palette-hint {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  white-space: nowrap;
}

.command-palette-content {
  overflow-y: auto;
  flex: 1;
  padding: var(--space-2);
}

.command-group {
  margin-bottom: var(--space-3);
}

.command-group-title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: var(--space-2) var(--space-3);
}

.command-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  text-decoration: none;
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.command-item:hover,
.command-item.selected {
  background: var(--bg-tertiary);
}

.command-item-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-primary);
  font-size: var(--font-size-lg);
}

.command-item-content {
  flex: 1;
  min-width: 0;
}

.command-item-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.command-item-description {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.command-no-results {
  text-align: center;
  padding: var(--space-12);
  color: var(--text-muted);
}

.command-no-results i {
  font-size: var(--font-size-4xl);
  margin-bottom: var(--space-3);
  opacity: 0.5;
}

.command-palette-footer {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-3);
  border-top: var(--border-width) solid var(--border-primary);
  background: var(--bg-primary);
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  justify-content: center;
}

.command-shortcut {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  font-weight: var(--font-weight-medium);
}

/* Light Mode */
:root[data-theme="light"] .command-palette-container {
  background: #ffffff;
  border-color: #e5e5e5;
}

:root[data-theme="light"] .command-palette-input {
  color: #1a1a1a;
}

:root[data-theme="light"] .command-palette-input::placeholder {
  color: #888888;
}
</style>

<script>
// Command Palette JavaScript (HTMX-driven)
const commandPalette = document.getElementById('command-palette');
const input = document.getElementById('command-palette-input');
const backdrop = document.querySelector('.command-palette-backdrop');

// Open with Cmd+K or Ctrl+K
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    commandPalette.removeAttribute('hidden');
    input.focus();
  }
});

// Close on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !commandPalette.hidden) {
    commandPalette.setAttribute('hidden', '');
    input.value = '';
  }
});

// Close on backdrop click
backdrop.addEventListener('click', () => {
  commandPalette.setAttribute('hidden', '');
});

// Fuzzy search with HTMX
let debounceTimer;
input.addEventListener('input', (e) => {
  clearTimeout(debounceTimer);
  const query = e.target.value.trim();
  
  if (!query) {
    // Show recent searches
    document.getElementById('recent-group').removeAttribute('hidden');
    document.getElementById('tracks-group').setAttribute('hidden', '');
    document.getElementById('artists-group').setAttribute('hidden', '');
    document.getElementById('playlists-group').setAttribute('hidden', '');
    document.getElementById('actions-group').setAttribute('hidden', '');
    document.getElementById('settings-group').setAttribute('hidden', '');
    document.getElementById('no-results').setAttribute('hidden', '');
    return;
  }
  
  debounceTimer = setTimeout(() => {
    // HTMX call to /api/search/fuzzy?q=...
    htmx.ajax('GET', `/api/search/fuzzy?q=${encodeURIComponent(query)}`, {
      target: '#command-results',
      swap: 'innerHTML'
    });
  }, 150);
});

// Keyboard navigation (↑/↓, Enter)
document.addEventListener('keydown', (e) => {
  if (commandPalette.hidden) return;
  
  const items = document.querySelectorAll('.command-item');
  const selected = document.querySelector('.command-item.selected');
  
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (!selected && items.length) {
      items[0].classList.add('selected');
    } else if (selected) {
      const next = selected.nextElementSibling;
      if (next && next.classList.contains('command-item')) {
        selected.classList.remove('selected');
        next.classList.add('selected');
      }
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (selected) {
      const prev = selected.previousElementSibling;
      if (prev && prev.classList.contains('command-item')) {
        selected.classList.remove('selected');
        prev.classList.add('selected');
      } else {
        selected.classList.remove('selected');
      }
    }
  } else if (e.key === 'Enter' && selected) {
    e.preventDefault();
    selected.click();
    commandPalette.setAttribute('hidden', '');
  }
});
</script>
```

**Why**: Command Palette is a differentiator for Pro users – enables power-user workflows without leaving the current page.

### 3.3 Mobile Bottom Sheet Component

**File**: `src/soulspot/templates/components/specialized/bottom-sheet.html`

```html
{#
  Bottom Sheet - Mobile-first modal that slides up from bottom
  
  Ideal for: Filter panels, artist selection, quick actions on mobile
  
  Usage:
    {% include 'components/specialized/bottom-sheet.html' with {
      'id': 'artist-selector',
      'title': 'Select Artist',
      'content_template': 'includes/artist-list.html'
    } %}
#}

<div id="{{ id }}" class="bottom-sheet" hidden>
  <div class="bottom-sheet-backdrop"></div>
  
  <div class="bottom-sheet-content">
    <div class="bottom-sheet-header">
      <div class="bottom-sheet-handle"></div>
      <h2 class="bottom-sheet-title">{{ title }}</h2>
      <button class="bottom-sheet-close" aria-label="Close">
        <i class="fa-solid fa-times"></i>
      </button>
    </div>
    
    <div class="bottom-sheet-body">
      {% include content_template %}
    </div>
  </div>
</div>

<style>
.bottom-sheet {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: flex-end;
  backdrop-filter: blur(2px);
}

.bottom-sheet:not([hidden]) {
  display: flex;
}

.bottom-sheet-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  cursor: pointer;
}

.bottom-sheet-content {
  position: relative;
  width: 100%;
  max-height: 90vh;
  background: var(--bg-secondary);
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUpBottom 0.3s ease-out;
}

@keyframes slideUpBottom {
  from {
    transform: translateY(100%);
  }
  to {
    transform: translateY(0);
  }
}

.bottom-sheet-header {
  padding: var(--space-4);
  border-bottom: var(--border-width) solid var(--border-primary);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.bottom-sheet-handle {
  position: absolute;
  top: var(--space-2);
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 4px;
  background: var(--border-primary);
  border-radius: var(--radius-full);
}

.bottom-sheet-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.bottom-sheet-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: var(--font-size-lg);
  transition: color var(--transition-fast);
}

.bottom-sheet-close:hover {
  color: var(--text-primary);
}

.bottom-sheet-body {
  overflow-y: auto;
  flex: 1;
  padding: var(--space-4);
}

/* Tablet and up: use modal instead */
@media (min-width: 768px) {
  .bottom-sheet-content {
    width: 90vw;
    max-width: 500px;
    max-height: 80vh;
    border-radius: var(--radius-xl);
    margin: auto;
  }
}
</style>

<script>
const bottomSheet = document.getElementById('{{ id }}');
const backdrop = bottomSheet.querySelector('.bottom-sheet-backdrop');
const closeBtn = bottomSheet.querySelector('.bottom-sheet-close');

function close() {
  bottomSheet.setAttribute('hidden', '');
}

backdrop.addEventListener('click', close);
closeBtn.addEventListener('click', close);

// Close on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !bottomSheet.hidden) {
    close();
  }
});
</script>
```

**Why**: Mobile UX best practice – bottom sheets feel native and don't interrupt content flow.

---

## Phase 4: Polish & Integration (Animations, Light Mode, Testing)

### 4.1 Objective
Finalize the system with:
- **Animation refinements** – Smooth transitions across all interactive elements
- **Light Mode integration** – Full color palette switch (MediaManager reference)
- **Theme persistence** – User preference stored in Pydantic Settings
- **Comprehensive testing** – Unit + integration tests for all components

### 4.2 Light Mode Theme Switcher

**File**: `src/soulspot/templates/includes/theme-switcher.html` (NEW)

```html
{#
  Theme Switcher - Toggle between dark and light modes
  
  Stores preference in:
  1. localStorage (browser state)
  2. Pydantic UserSettings.theme (database)
  
  Usage: Include in topbar or settings
#}

<div class="theme-switcher">
  <button id="theme-toggle" class="theme-toggle-btn" aria-label="Toggle theme">
    <i class="fa-solid fa-moon" id="theme-icon"></i>
  </button>
</div>

<script>
// Hey future me - Theme switching logic
// Always check BOTH localStorage and server state to avoid mismatches
const root = document.documentElement;
const themeToggle = document.getElementById('theme-toggle');
const themeIcon = document.getElementById('theme-icon');

// Detect initial preference
function getInitialTheme() {
  // 1. Check localStorage first
  const stored = localStorage.getItem('theme');
  if (stored) return stored;
  
  // 2. Check server-stored preference (if available via data attribute)
  const serverTheme = document.documentElement.dataset.theme;
  if (serverTheme) return serverTheme;
  
  // 3. Check system preference
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  
  return 'dark'; // Default to dark
}

function applyTheme(theme) {
  // Update CSS variable
  if (theme === 'light') {
    root.setAttribute('data-theme', 'light');
    themeIcon.className = 'fa-solid fa-sun';
  } else {
    root.removeAttribute('data-theme');
    themeIcon.className = 'fa-solid fa-moon';
  }
  
  // Save to localStorage
  localStorage.setItem('theme', theme);
  
  // Save to server (Pydantic UserSettings.theme)
  htmx.ajax('POST', '/api/settings/theme', {
    values: { theme: theme },
    target: 'body'
  });
}

// Initialize
const currentTheme = getInitialTheme();
applyTheme(currentTheme);

// Toggle on click
themeToggle.addEventListener('click', () => {
  const newTheme = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
  applyTheme(newTheme);
});

// Listen for system preference changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  if (!localStorage.getItem('theme')) {
    applyTheme(e.matches ? 'dark' : 'light');
  }
});
</script>

<style>
.theme-switcher {
  display: inline-block;
}

.theme-toggle-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  font-size: var(--font-size-lg);
}

.theme-toggle-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}
</style>
```

### 4.3 Testing Strategy

**Unit Tests**: `tests/unit/ui/components/test_card.py`

```python
"""
Tests for Card component rendering and props
"""
import pytest
from jinja2 import Environment, FileSystemLoader

@pytest.fixture
def jinja_env():
    """Load Jinja2 environment"""
    return Environment(loader=FileSystemLoader('src/soulspot/templates'))

def test_card_basic_render(jinja_env):
    """Test card renders with basic props"""
    template = jinja_env.get_template('components/data-display/card.html')
    
    html = template.render(
        title='Dark Side of the Moon',
        subtitle='Pink Floyd',
        image='/static/images/album.jpg'
    )
    
    assert 'Dark Side of the Moon' in html
    assert 'Pink Floyd' in html
    assert '<img' in html

def test_card_with_actions(jinja_env):
    """Test card renders with action buttons"""
    template = jinja_env.get_template('components/data-display/card.html')
    
    html = template.render(
        title='Album',
        actions=[
            {'icon': 'fa-solid fa-play', 'label': 'Play', 'variant': 'primary'}
        ]
    )
    
    assert 'Play' in html
    assert 'btn-primary' in html

def test_card_light_mode(jinja_env):
    """Test card color classes for light mode"""
    template = jinja_env.get_template('components/data-display/card.html')
    
    html = template.render(title='Test Card')
    
    # Light mode CSS should be present
    assert 'card' in html
```

**Integration Tests**: `tests/integration/ui/test_command_palette.py`

```python
"""
Integration tests for Command Palette API
"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_command_palette_search(client: AsyncClient):
    """Test command palette fuzzy search API"""
    response = await client.get('/api/search/fuzzy?q=dark+side')
    
    assert response.status_code == 200
    data = response.json()
    assert 'tracks' in data
    assert 'artists' in data
    assert len(data['tracks']) > 0

@pytest.mark.asyncio
async def test_command_palette_recent_searches(client: AsyncClient, auth_user):
    """Test recent searches are returned"""
    # Make a search
    await client.get('/api/search/fuzzy?q=pink+floyd')
    
    # Fetch recent searches
    response = await client.get('/api/search/recent', headers=auth_user)
    
    assert response.status_code == 200
    data = response.json()
    assert 'pink floyd' in [s['query'] for s in data]
```

---

## Technical Architecture

### 5.1 Component Organization (DDD + Hexagonal)

```
src/soulspot/templates/
├── components/                         # Reusable UI components
│   ├── layout/                        # Page structure
│   │   ├── sidebar.html
│   │   ├── topbar.html
│   │   ├── page-header.html
│   │   └── container.html
│   ├── data-display/                  # Content rendering
│   │   ├── card.html
│   │   ├── table.html
│   │   ├── grid.html
│   │   ├── list.html
│   │   └── badge.html
│   ├── forms/                         # Input components
│   │   ├── input.html
│   │   ├── select.html
│   │   ├── checkbox.html
│   │   ├── radio.html
│   │   ├── toggle.html
│   │   └── filter-panel.html
│   ├── feedback/                      # Notifications & feedback
│   │   ├── alert.html
│   │   ├── toast.html
│   │   ├── modal.html
│   │   ├── loading.html
│   │   └── progress-bar.html
│   ├── navigation/                    # Navigation patterns
│   │   ├── breadcrumbs.html
│   │   ├── tabs.html
│   │   └── pagination.html
│   └── specialized/                   # Pro features
│       ├── command-palette.html       # Cmd+K search
│       ├── bottom-sheet.html          # Mobile modals
│       ├── queue-manager.html         # Download queue
│       └── library-view.html          # Multi-view library

src/soulspot/static/new-ui/css/
├── variables.css                      # Design tokens (colors, spacing, etc.)
├── animations.css                     # Magic UI @keyframes (Pure CSS)
├── components.css                     # Component styles (buttons, cards, etc.)
└── utilities.css                      # Utility classes (text-muted, flex, etc.)
```

### 5.2 API Endpoints (New Pro Features)

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/search/fuzzy` | GET | Command palette fuzzy search | `{tracks, artists, albums, playlists, actions, settings}` |
| `/api/search/recent` | GET | Recent searches | `[{query, type, timestamp}]` |
| `/api/settings/theme` | POST | Save theme preference | `{theme: 'light' \| 'dark'}` |
| `/api/queue/reorder` | POST | Reorder downloads | `{success: bool}` |
| `/api/downloads/stream` | GET | SSE stream for progress | `{id, progress, status}` |

**Implementation Location**: `src/soulspot/api/routers/search.py`, `src/soulspot/api/routers/settings.py`

---

## Build-Less Strategy (Pure CSS)

### 6.1 Why No npm/Build?

| Requirement | Solution |
|-------------|----------|
| CSS-in-HTML (no SCSS) | Use CSS custom properties + @media queries |
| Icons (Bootstrap Icons) | CDN or embed SVG inline (preload in base.html) |
| Animations (Magic UI) | Port to pure CSS @keyframes (no postcss plugins) |
| JavaScript (HTMX + vanilla) | No transpilation needed (ES6+ supported everywhere) |
| Tailwind alternative | Design tokens in variables.css + utility classes |

### 6.2 Performance Optimizations

```html
<!-- base.html - Preload critical resources -->
<head>
  <!-- Preload fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
  
  <!-- Preload Bootstrap Icons -->
  <link rel="preload" as="font" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.woff2" type="font/woff2" crossorigin>
  
  <!-- Critical CSS (inline for fast FCP) -->
  <style>
    {# Critical styles: variables.css + base layout #}
  </style>
  
  <!-- Defer non-critical CSS -->
  <link rel="stylesheet" href="/static/new-ui/css/components.css">
</head>
```

---

## Quality Gates & Testing

### 7.1 Pre-Commit Checks

```bash
# Ruff (style + security)
ruff check src/ --config pyproject.toml

# mypy (type checking)
mypy --config-file mypy.ini src/

# HTML/Jinja2 validation
python -m jinja2.ext --validate src/soulspot/templates/

# CSS validation
python scripts/validate-css.py src/soulspot/static/new-ui/css/
```

### 7.2 Testing Coverage

| Area | Tool | Target | Notes |
|------|------|--------|-------|
| **Components** | pytest + Jinja2 | 90%+ | Template rendering tests |
| **API Endpoints** | pytest-httpx | 85%+ | HTMX integration tests |
| **Accessibility** | axe-core (JS) | WCAG AA | Automated a11y checks |
| **Performance** | Lighthouse CI | 90+ | Core Web Vitals |
| **CSS** | Browserslist | Latest 2 versions | Cross-browser compatibility |

---

## Rollout & Documentation

### 8.1 Migration Strategy (Phased)

**Week 1-2**: Phase 1 (Tokens + Animations)
- Deploy `variables.css` + `animations.css`
- Update existing pages to use new tokens
- 0% user impact (CSS-only)

**Week 3-4**: Phase 2 (Core Components)
- Deploy 20 Jinja2 components
- Migrate dashboard + library pages
- Full feature parity with old UI

**Week 5-6**: Phase 3 (Pro Features)
- Deploy Command Palette
- Deploy Mobile Bottom Sheets
- Launch to Pro tier users

**Week 7-8**: Phase 4 (Polish)
- Light Mode GA
- Full documentation
- Deprecate old component macros

### 8.2 Documentation

| Doc | Location | Purpose |
|-----|----------|---------|
| **Master Plan** | `docs/feat-ui/feat-ui-pro.md` | Complete implementation guide |
| **Accessibility Guide** | `docs/feat-ui/ACCESSIBILITY_GUIDE.md` | A11Y patterns & testing |
| **Service Agnostic Strategy** | `docs/feat-ui/SERVICE_AGNOSTIC_STRATEGY.md` | Multi-service architecture |
| **Quality Gates** | `docs/feat-ui/QUALITY_GATES_A11Y.md` | Testing & quality enforcement |
| **Changelog** | `CHANGELOG.md` | Version history |

---

## Risk Assessment & Mitigation

### 9.1 Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| **Light Mode colors aren't accessible** | Medium | High | WCAG AA contrast ratio tests before Phase 4 |
| **Mobile Bottom Sheets don't work on older iOS** | Low | Medium | Test iOS 12+, provide fallback modal |
| **Command Palette search is slow** | Medium | Medium | Implement debounce, cache recent searches |
| **CSS custom properties not supported in IE11** | N/A | Low | Drop IE11 support (Edge 90+ only) |
| **Component macro conflicts with legacy templates** | Low | High | Use unique namespace (`c-` prefix for old macros) |

### 9.2 Fallback Plans

- **Light Mode fails**: Default to dark mode, warn user
- **Command Palette fails**: Graceful fallback to standard search
- **Bottom Sheet doesn't animate**: Still functional, just no slide animation
- **Theme storage fails**: Use localStorage only (no server sync)

---

## Success Criteria

✅ **Completion Definition**:
- [ ] All 50+ components deployed and tested
- [ ] Command Palette working on 100% of pages
- [ ] Light Mode WCAG AA compliant (tested with axe-core)
- [ ] Mobile responsiveness verified (320px - 2560px)
- [ ] Performance: Lighthouse 90+
- [ ] 0 breaking changes to existing routes
- [ ] Full documentation + examples
- [ ] Team trained on component system

---

## Timeline & Dependencies

```
Phase 1 (Weeks 1-2)
├── Design tokens finalization
├── Animation library implementation
└── CSS variable validation

Phase 2 (Weeks 3-4)
├── Component template creation (20 components)
├── Jinja2 macro testing
└── Page migration (dashboard, library, etc.)

Phase 3 (Weeks 5-6)
├── Command Palette development
├── Mobile Bottom Sheet implementation
├── Pro API endpoints
└── Beta testing with Pro users

Phase 4 (Weeks 7-8)
├── Light Mode finalization
├── Comprehensive testing (unit + integration + a11y)
├── Documentation
└── General availability
```

---

## Conclusion

This Master Plan provides a **structured, phased approach** to transforming SoulSpot's UI into a **professional, scalable system** without sacrificing developer velocity or user experience.

**Key Differentiators**:
- ✅ **Build-less** – Pure CSS, no npm complexity
- ✅ **Pro-first** – Command Palette, advanced search, queue management
- ✅ **Accessible** – WCAG AA + Light Mode support
- ✅ **Maintainable** – 50+ reusable, tested components
- ✅ **Future-proof** – Service-agnostic design (Spotify → Tidal → Deezer)

**Next Step**: Begin Phase 1 implementation → `run_in_terminal` to request Task #1.

---

**Document Version**: 1.0  
**Last Updated**: December 7, 2025  
**Status**: ✅ Ready for Implementation  
**Author**: Copilot (Haiku 4.5)  
**Repository**: [SoulSpot](https://github.com/bozzfozz/soulspot)
