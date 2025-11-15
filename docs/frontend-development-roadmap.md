# SoulSpot Bridge – Frontend Development Roadmap

> **Last Updated:** 2025-11-15  
> **Version:** 0.2.0 (Alpha → Beta Preparation)  
> **Status:** Phase 7 Complete | UI 1.0 Design System Complete | V2.0 Planning Complete (HTMX-Only Approach) | Ready for Implementation  
> **Owner:** Frontend Team  
> **Next:** V2.0 Dashboard Builder (HTMX-Only, 12-18 days)

> **📌 Hinweis:** Für eine detaillierte **Version 1.0 Roadmap** mit Feature-Freeze-Kriterien, Meilensteinen und Qualitätssicherung, siehe [Frontend Development Roadmap v1.0](../frontend-development-roadmap.md).

---

## 📑 Table of Contents

1. [Vision & Goals](#-vision--goals)
2. [Current Status](#-current-status)
3. [Architecture Overview](#-architecture-overview)
4. [Now (Next 4-8 Weeks)](#-now-next-4-8-weeks)
5. [Next (2-3 Months)](#-next-2-3-months)
6. [Later (>3 Months)](#-later-3-months)
7. [Dependencies & Risks](#-dependencies--risks)
8. [Links & References](#-links--references)

---

## 🎯 Vision & Goals

The frontend of SoulSpot Bridge provides:

- 🎨 **User Interface** – Clean, modern, responsive web UI using Jinja2 templates
- ⚡ **Interactivity** – Dynamic interactions powered by HTMX with minimal JavaScript
- 🎨 **Styling** – Tailwind CSS for utility-first styling and consistent design
- ♿ **Accessibility** – WCAG AA compliance, keyboard navigation, screen reader support
- 📱 **Responsive Design** – Mobile-first approach, works on all screen sizes
- 🌙 **Dark Mode** – Theme support with user preferences

### Core Principles

- **Progressive Enhancement** – Works without JavaScript, enhanced with HTMX
- **Server-Side Rendering** – Jinja2 templates for fast initial load
- **Minimal JS** – HTMX handles most interactivity, JS only when necessary
- **Component-Based** – Reusable template partials and components
- **Performance** – Optimized assets, lazy loading, efficient updates

---

## 📍 Current Status

### ✅ Completed Phases

| Phase | Status | Key Features |
|-------|--------|--------------|
| **Phase 5: Web UI & API** | ✅ Complete | Jinja2 Templates, HTMX Integration, Tailwind CSS, Basic Pages |
| **Phase 7: UI/UX Enhancements** | ✅ Complete | Loading States, Toast Notifications, Keyboard Navigation, Accessibility |
| **Phase 7: Advanced Search** | ✅ Complete | Advanced Filters, Autocomplete, Bulk Actions, Search History |
| **UI 1.0 Design System** | ✅ Complete | Neutral Design Tokens, Component Library, Layout Utilities, Demo Page |

**Implemented Features:**
- ✅ Base template with navigation
- ✅ Home dashboard
- ✅ Spotify authentication pages
- ✅ Download queue views
- ✅ Track search interface
- ✅ Basic HTMX interactions
- ✅ Tailwind CSS styling
- ✅ Dark mode support
- ✅ **Skeleton loading screens** (Phase 7)
- ✅ **Toast notification system** (Phase 7)
- ✅ **Keyboard navigation & accessibility** (Phase 7)
- ✅ **Advanced search with filters** (Phase 7)
- ✅ **Search autocomplete with debouncing** (Phase 7)
- ✅ **Bulk download actions** (Phase 7)
- ✅ **UI 1.0 Design System** (Neutral component library based on Wizarr)

### 🔄 Current Phase: v2.0 Planning – Dynamic Views & Widget-Palette

**Status:** Planning & Design  
**Focus:** Grid-based page builder with customizable widgets

---

## 🏗️ Architecture Overview

### Technology Stack

| Component | Technology | Status |
|-----------|-----------|--------|
| **Template Engine** | Jinja2 | ✅ Implemented |
| **Interactivity** | HTMX | ✅ Implemented |
| **Styling** | Tailwind CSS | ✅ Implemented |
| **JavaScript** | Vanilla JS (minimal) | ✅ Implemented |
| **Build Tool** | Tailwind CLI | ✅ Implemented |
| **Icons** | Heroicons / Lucide | ✅ Implemented |

### Template Structure

```
templates/
├── base.html                   # Base layout
├── components/                 # Reusable components
│   ├── navbar.html
│   ├── footer.html
│   ├── modal.html
│   └── alert.html
├── pages/                      # Page templates
│   ├── home.html
│   ├── search.html
│   ├── queue.html
│   └── settings.html
└── partials/                   # HTMX-loadable partials
    ├── track_item.html
    ├── job_item.html
    └── status_badge.html
```

### HTMX Integration Patterns

#### 1. Dynamic Content Loading
```html
<div hx-get="/api/jobs" hx-trigger="load" hx-swap="innerHTML">
  Loading...
</div>
```

#### 2. Form Submissions
```html
<form hx-post="/api/downloads" hx-target="#queue" hx-swap="beforeend">
  <!-- Form fields -->
</form>
```

#### 3. Polling for Updates
```html
<div hx-get="/api/jobs/active" hx-trigger="every 2s" hx-swap="outerHTML">
  <!-- Job list -->
</div>
```

---

## 🚀 Now (Next 4-8 Weeks)

### Priority: HIGH (P0/P1)

---

#### 0. UI 1.0 Design System 🎨

**Epic:** Neutral Design Foundation  
**Owner:** Frontend Team  
**Priority:** P1 (Foundation)  
**Effort:** Small (3-4 days)  
**Status:** ✅ **COMPLETE** (Delivered 2025-11-15)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Design Tokens** | Color palette, typography, spacing | P1 | Small | ✅ Complete |
| **Component Library** | Buttons, cards, forms, tables, etc. | P1 | Medium | ✅ Complete |
| **Layout Utilities** | Grid, flexbox, spacing, responsive | P1 | Small | ✅ Complete |
| **Demo Showcase** | Interactive component examples | P1 | Small | ✅ Complete |
| **Documentation** | Usage guide and integration docs | P1 | Small | ✅ Complete |

**Acceptance Criteria:**
- [x] Complete design token system (colors, typography, spacing, shadows)
- [x] Component styles for buttons, cards, badges, alerts, forms, tables, nav, modals
- [x] Layout utilities for page structure and responsive design
- [x] Interactive demo page showcasing all components
- [x] Comprehensive documentation with usage examples
- [x] MIT license attribution to Wizarr maintained
- [x] No branding elements (logos, product names) included

**Delivered Artifacts:**

1. **`docs/ui/theme.css`** (8.8 KB)
   - CSS custom properties for all design tokens
   - Color palette (primary, secondary, semantic colors)
   - Typography scale (font families, sizes, weights, line heights)
   - Spacing scale (consistent 4px increments)
   - Border radius, shadows, transitions, z-index
   - Dark mode support with automatic detection
   - Accessibility features (focus states, reduced motion)

2. **`docs/ui/components.css`** (15 KB)
   - **Buttons**: Primary, secondary, outline, ghost, danger, success variants with sizes (sm, base, lg)
   - **Cards**: Header, body, footer with hover effects
   - **Badges**: Success, warning, danger, info, neutral with pulse animation
   - **Alerts**: Success, warning, danger, info with icon support
   - **Forms**: Inputs, textarea, select, checkbox, radio with focus states
   - **Tables**: Responsive tables with hover and striped variants
   - **Navigation**: Horizontal nav, vertical nav, tabs
   - **Modals**: Backdrop with blur, header, body, footer
   - **Loading**: Spinners (3 sizes), progress bars, skeleton screens
   - **Utility Classes**: Text colors, backgrounds

3. **`docs/ui/layout.css`** (12 KB)
   - **Container**: Responsive max-width containers (sm, md, lg, xl, full)
   - **Grid**: CSS Grid utilities (1-12 columns, auto-fit)
   - **Flexbox**: Flex direction, alignment, justification
   - **Page Layouts**: Header, content, footer, sidebar structures
   - **Dashboard Grid**: 12-column grid for widgets
   - **Spacing**: Margin and padding utilities
   - **Typography**: Heading styles (h1-h4), text alignment
   - **Responsive**: Breakpoint-specific utilities (hide/show)
   - **Display**: Block, inline, inline-block, hidden
   - **Position**: Relative, absolute, fixed, sticky
   - **Overflow**: Auto, hidden, x-auto, y-auto

4. **`docs/ui/ui-demo.html`** (21 KB)
   - Complete showcase of all components and utilities
   - Interactive examples with live previews
   - Color palette swatches
   - Typography hierarchy
   - Button variants and states
   - Card layouts
   - Form elements
   - Tables with data
   - Navigation patterns
   - Loading states
   - Alerts and badges
   - Spacing scale visualization
   - Dark mode toggle example

5. **`docs/ui/README_UI_1_0.md`** (10.7 KB)
   - Comprehensive usage documentation
   - Installation and integration guide
   - Component usage examples with code snippets
   - Customization instructions (overriding tokens)
   - Dark mode implementation guide
   - Responsive design patterns
   - Accessibility features and guidelines
   - Browser support matrix
   - MIT license attribution to Wizarr
   - Contributing guidelines

**Design Source:**
- Based on [Wizarr](https://github.com/wizarrrr/wizarr) (MIT License)
- Visual design language extracted and neutralized
- All branding removed (logos, names, marketing content)
- Design tokens converted to reusable CSS custom properties
- Component classes use neutral `ui-` prefix

**Integration:**
- Can be integrated into any web project
- No JavaScript dependencies required
- Works with Tailwind CSS or standalone
- Compatible with HTMX and server-side rendering
- Supports both light and dark modes
- WCAG 2.1 AA accessible by default

**Impact:**
- Provides consistent design foundation for SoulSpot Bridge
- Can be reused across multiple projects
- Reduces time to implement UI components
- Ensures design consistency and accessibility
- Fully documented and ready for v2.0 widget system

---

#### 1. UI/UX Improvements

**Epic:** Enhanced User Experience  
**Owner:** Frontend Team  
**Priority:** P1  
**Effort:** Medium (2-3 weeks)  
**Status:** ✅ **COMPLETE** (Delivered 2025-11-13)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Loading States** | Skeleton screens, spinners | P1 | Small | ✅ Complete |
| **Error Handling** | User-friendly error messages | P0 | Small | ✅ Complete |
| **Success Feedback** | Toast notifications, confirmations | P1 | Small | ✅ Complete |
| **Empty States** | Meaningful empty state designs | P1 | Small | ✅ Complete |
| **Keyboard Navigation** | Full keyboard accessibility | P1 | Medium | ✅ Complete |

**Acceptance Criteria:**
- [x] Loading states for all async operations
- [x] Consistent error message styling and placement
- [x] Toast notification system implemented
- [x] Empty states for all list views
- [x] Tab navigation works throughout app
- [x] Focus management for modals and dialogs

**Delivered Features:**
- ✅ Skeleton screens (card, list, stats, table variants)
- ✅ Loading spinners (3 sizes: sm/md/lg)
- ✅ ToastManager JavaScript module (success/error/warning/info)
- ✅ LoadingManager for button and overlay states
- ✅ KeyboardNav module with shortcuts (Ctrl/Cmd+K, Escape)
- ✅ WCAG 2.1 AA accessibility compliance
- ✅ Skip-to-content link for screen readers
- ✅ Full ARIA labels and roles throughout templates
- ✅ Focus ring indicators on all interactive elements

**Documentation:**
- `docs/keyboard-navigation.md` - Keyboard shortcuts guide
- `docs/ui-ux-visual-guide.md` - Component showcase
- `docs/ui-ux-testing-report.md` - Test coverage (12/12 pass)

---

#### 2. Advanced Search Interface

**Epic:** Enhanced Search UI  
**Owner:** Frontend Team  
**Priority:** P1  
**Effort:** Medium (2 weeks)  
**Status:** ✅ **COMPLETE** (Delivered 2025-11-13)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Advanced Filters UI** | Filter by artist, album, quality | P1 | Medium | ✅ Complete |
| **Search Suggestions** | Autocomplete with HTMX | P1 | Medium | ✅ Complete |
| **Result Previews** | Expanded track information | P1 | Small | ✅ Complete |
| **Bulk Actions** | Select multiple results | P1 | Medium | ✅ Complete |
| **Search History** | Recent searches display | P2 | Small | ✅ Complete |

**Acceptance Criteria:**
- [x] Filter panel with collapsible sections
- [x] Autocomplete suggestions (debounced)
- [x] Expandable result cards
- [x] Checkbox selection for bulk download
- [x] Search history (client-side storage)

**Delivered Features:**
- ✅ Advanced search page at `/ui/search`
- ✅ Collapsible filter panel (quality, artist, album, duration)
- ✅ Debounced autocomplete (300ms) with Spotify API
- ✅ Expandable track result cards with full metadata
- ✅ Multi-select with checkboxes and "Select All"
- ✅ Bulk download functionality
- ✅ Search history (localStorage, max 10 searches)
- ✅ SearchManager JavaScript module (~700 lines)
- ✅ Real-time client-side filtering
- ✅ Full keyboard navigation support

**Documentation:**
- `docs/advanced-search-guide.md` - Complete user guide with examples and troubleshooting

---

#### 3. Download Queue Management

**Epic:** Enhanced Queue UI  
**Owner:** Frontend Team  
**Priority:** P0  
**Effort:** Medium (2 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Priority Indicators** | Visual priority badges | P1 | Small | 📋 Planned |
| **Drag & Drop Reorder** | Manual priority adjustment | P1 | Medium | 📋 Planned |
| **Progress Visualization** | Enhanced progress bars | P0 | Small | 📋 Planned |
| **Pause/Resume Controls** | Individual job controls | P0 | Small | 📋 Planned |
| **Batch Operations** | Select multiple jobs | P1 | Medium | 📋 Planned |
| **Queue Filters** | Filter by status, priority | P1 | Small | 📋 Planned |

**Acceptance Criteria:**
- [ ] Priority badges (P0/P1/P2) displayed
- [ ] Drag & drop reordering functional
- [ ] Progress bars with percentage and ETA
- [ ] Pause/resume buttons per job
- [ ] Checkbox selection for batch actions
- [ ] Filter dropdown for job status

---

#### 4. Settings & Configuration

**Epic:** Settings UI  
**Owner:** Frontend Team  
**Priority:** P1  
**Effort:** Medium (2 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Settings Page** | Comprehensive settings UI | P1 | Medium | 📋 Planned |
| **Form Validation** | Client-side validation | P1 | Small | 📋 Planned |
| **Theme Switcher** | Light/dark/auto theme selector | P1 | Small | 📋 Planned |
| **API Key Management** | Secure input fields | P1 | Small | 📋 Planned |
| **Reset Functionality** | Reset to defaults | P2 | Small | 📋 Planned |

**Acceptance Criteria:**
- [ ] Settings page with tabbed sections
- [ ] Form validation with error messages
- [ ] Theme switcher with persistence
- [ ] Password/API key inputs with show/hide
- [ ] Reset to defaults button with confirmation

---

## 📅 Next (2-3 Months)

### Priority: STRATEGIC (P0 for v2.0)

#### 5. v2.0 Dynamic Views & Widget-Palette ⭐ HTMX-ONLY APPROACH

**Epic:** HTMX-Only Dashboard Builder (Button-Based Layout)  
**Owner:** Frontend Team  
**Priority:** P0 (Strategic)  
**Effort:** Medium (12-18 days / 2.5-3.5 weeks)  
**Status:** 📋 Planned (Evaluation Complete)

> **Architecture Decision:** Pure HTMX approach with button-based layout controls instead of GridStack drag-and-drop.  
> **Rationale:** Superior accessibility, faster development (12-18 days vs 25-35), zero custom JS, mobile-friendly.  
> **See:** `docs/frontend-roadmap-htmx-evaluation.md` for complete evaluation.

| Phase | Description | Priority | Effort | Status |
|-------|-------------|----------|--------|--------|
| **Phase 0: Foundation** | Database schema, migrations | P0 | 2 days | 📋 Planned |
| **Phase 1: Canvas & Widgets** | Widget partials, CSS Grid layout | P0 | 4-5 days | 📋 Planned |
| **Phase 2: Core Features** | Add/remove, movement, resize | P0 | 3-4 days | 📋 Planned |
| **Phase 3: Advanced** | Edit/view mode, config, pages | P0 | 2-3 days | 📋 Planned |
| **Phase 4: Launch** | Testing, polish, rollout | P0 | 3-4 days | 📋 Planned |

**Total Effort:** 12-18 days (vs 25-35 for GridStack hybrid)

---

**Key Features:**

##### Layout System: Button-Based (No Drag-and-Drop)
- **CSS Grid (12 columns)** – Responsive grid with Tailwind
- **Button Controls** – ↑ ↓ ← → for movement, ⬌ for resize
- **Row-Based Stacking** – Widgets stack in rows, move via button clicks
- **Zero JavaScript** – 100% HTMX attributes + Jinja2 templates
- **Edit/View Modes** – Toggle between editing and viewing
- **Mobile Friendly** – Standard button taps (no complex gestures)

**Why Buttons Instead of Drag-and-Drop?**
✅ **Accessibility First** – Keyboard/screen-reader friendly by default  
✅ **Mobile Friendly** – Works perfectly on touch devices  
✅ **Zero Custom JS** – Pure HTMX (no GridStack integration)  
✅ **Faster Development** – 12-18 days vs 25-35 days  
✅ **Easy Testing** – Standard HTTP request/response  
❌ **Trade-off:** No free drag positioning (acceptable)

##### Widget System
- **Widget Catalog Modal** – HTMX modal with widget selection (`hx-get`)
- **Add Widget** – `hx-post` to create instance, returns HTML
- **Remove Widget** – `hx-delete` removes from canvas
- **Widget Configuration** – Modal forms with `hx-post`
- **Live Updates** – `hx-trigger="every 5s"` polling (Phase 1), SSE (Phase 2)
- **Page Management** – Multiple dashboards with save/load

##### 5 Core Widgets (MVP)

1. **Active Jobs Widget**
   - Real-time job monitoring via polling
   - Progress bars with ETA
   - Pause/cancel/retry buttons (HTMX)
   - Configurable refresh interval (config modal)

2. **Spotify Search Widget**
   - Inline search with `hx-get` + debounce
   - Result preview cards
   - Quick download via `hx-post`
   - Filter settings modal

3. **Missing Tracks Widget**
   - Playlist comparison display
   - Missing track list
   - Bulk download action (`hx-post`)
   - CSV/JSON export button

4. **Quick Actions Widget**
   - Configurable button grid
   - Common actions (scan, import, fix) via `hx-post`
   - Visual feedback (toast notifications)
   - Keyboard shortcuts (existing KeyboardNav)

5. **Metadata Manager Widget**
   - Metadata issue list
   - Filter controls via `hx-get`
   - Quick-fix actions (`hx-post`)
   - Batch operations

---

**Acceptance Criteria (Definition of Done):**

**Phase 0: Foundation**
- [x] Database migration created (`widgets`, `pages`, `widget_instances` tables)
- [x] Widget registry seeded (5 core widgets)
- [x] API endpoint stubs created

**Phase 1: Canvas & Widgets**
- [ ] CSS Grid layout system (12 columns, responsive)
- [ ] Widget partial templates created (5 widgets)
- [ ] Canvas rendering endpoint (`GET /api/pages/{id}/canvas`)
- [ ] Widget card wrapper template
- [ ] Responsive breakpoints (mobile: 4 cols, tablet: 8 cols, desktop: 12 cols)

**Phase 2: Core Features**
- [ ] Widget catalog modal (`GET /api/widgets/catalog`)
- [ ] Add widget endpoint (`POST /api/widgets/instances`)
- [ ] Remove widget endpoint (`DELETE /api/widgets/instances/{id}`)
- [ ] Move up/down buttons (`POST /api/widgets/instances/{id}/move-{direction}`)
- [ ] Resize button (`POST /api/widgets/instances/{id}/resize`)
- [ ] Position swap logic (move widgets between rows)

**Phase 3: Advanced**
- [ ] Edit/view mode toggle (show/hide controls)
- [ ] Widget configuration modal (`GET /api/widgets/instances/{id}/config`)
- [ ] Save widget config (`POST /api/widgets/instances/{id}/config`)
- [ ] Page management (create/rename/delete pages)
- [ ] Page switcher sidebar
- [ ] Default page setting

**Phase 4: Launch**
- [ ] Integration tests (80%+ coverage)
- [ ] E2E tests (critical paths with Playwright)
- [ ] Accessibility audit (WCAG 2.1 AA with axe-core)
- [ ] Performance benchmarks (<1s load, <300ms actions)
- [ ] Feature flag deployment
- [ ] Beta testing (10 users, 1 week)
- [ ] Staged rollout (10% → 50% → 100%)

**Quality Gates:**
- [ ] All 5 widgets functional with live updates
- [ ] Mobile responsive (tested on iPhone, Android)
- [ ] Keyboard navigation works (tab, enter, escape)
- [ ] Screen reader compatible (tested with NVDA/VoiceOver)
- [ ] No console errors or warnings
- [ ] Performance: Initial load <1s, actions <300ms

---

**Technical Implementation:**

**Database Schema:**
```sql
CREATE TABLE widgets (
    id INTEGER PRIMARY KEY,
    type VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    template_path VARCHAR(200) NOT NULL,
    default_config JSON
);

CREATE TABLE pages (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_default BOOLEAN DEFAULT FALSE
);

CREATE TABLE widget_instances (
    id INTEGER PRIMARY KEY,
    page_id INTEGER NOT NULL REFERENCES pages(id),
    widget_type VARCHAR(50) NOT NULL REFERENCES widgets(type),
    position_row INTEGER NOT NULL DEFAULT 0,
    position_col INTEGER NOT NULL DEFAULT 0,
    span_cols INTEGER NOT NULL DEFAULT 6,
    config JSON,
    UNIQUE(page_id, position_row, position_col)
);
```

**HTMX Patterns Used:**
- `hx-get` – Load widget content, catalog modal
- `hx-post` – Add widget, move, resize, config save
- `hx-delete` – Remove widget
- `hx-trigger="load"` – Load widget on canvas render
- `hx-trigger="every 5s"` – Polling for live updates
- `hx-swap="innerHTML"` – Replace content
- `hx-swap="outerHTML"` – Replace entire element
- `hx-swap="beforeend"` – Append to canvas
- `hx-target` – Specify swap target element
- `hx-vals` – Send JSON data with request
- `hx-confirm` – Confirmation dialog

**Example Widget Card Template:**
```html
<div class="widget-card widget-col-6" id="widget-instance-42">
  {% include "partials/widgets/active_jobs.html" %}
  
  {% if edit_mode %}
  <div class="widget-controls">
    <button hx-post="/api/widgets/instances/42/move-up"
            hx-target="#widget-canvas"
            hx-swap="innerHTML"
            aria-label="Move up">↑</button>
    <button hx-post="/api/widgets/instances/42/move-down"
            aria-label="Move down">↓</button>
    <button hx-delete="/api/widgets/instances/42"
            hx-confirm="Remove widget?"
            aria-label="Remove">✕</button>
  </div>
  {% endif %}
</div>
```

---

**Dependencies:**

**Backend:**
- [ ] FastAPI endpoints (13 new routes)
- [ ] Database migrations (Alembic)
- [ ] Widget registry seeder
- [ ] Template rendering helpers

**Frontend:**
- [ ] Widget partial templates (5 widgets)
- [ ] CSS Grid styles (Tailwind utilities)
- [ ] Modal container in base.html
- [ ] Existing: HTMX (already integrated ✅)
- [ ] Existing: Toast notifications (already implemented ✅)
- [ ] Existing: Loading states (already implemented ✅)

**External:**
- None! (No GridStack, no additional libraries)

---

**Risks & Mitigations:**

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **User resistance to buttons** | LOW | MEDIUM | User testing, clear labels, tooltips |
| **Performance (many widgets)** | MEDIUM | MEDIUM | Lazy loading, pagination, caching |
| **Mobile layout complexity** | LOW | MEDIUM | Mobile-first CSS, extensive testing |
| **Backend load (polling)** | MEDIUM | MEDIUM | Rate limiting, upgrade to SSE in Phase 2 |
| **Browser compatibility** | LOW | LOW | HTMX works on all modern browsers |

**Overall Risk:** ✅ LOW (proven technology stack, no complex integration)

---

**Migration Path:**

**Week 1-2: Development**
- Phase 0-1: Foundation & Canvas (6-7 days)

**Week 2-3: Feature Complete**
- Phase 2-3: Core Features & Advanced (5-7 days)

**Week 3-4: Testing & Launch**
- Phase 4: Testing, polish, rollout (3-4 days)

**Rollback Plan:**
- Feature flag toggle (instant rollback to current UI)
- Database rollback (drop widget tables)
- No breaking changes to existing pages

---

**Success Metrics:**

**Development:**
- Actual time vs estimate (target: within 20%)
- Bug count during development (target: <10 critical)
- Test coverage (target: >80%)

**Post-Launch:**
- User adoption rate (target: 70% within 2 weeks)
- Average widgets per dashboard (target: 3-5)
- Dashboard creation rate (target: 1+ per user)
- User satisfaction (target: 4+/5 stars)
- Performance: P95 load time (target: <1.5s)

---

**Documentation:**

**For Developers:**
- [x] `docs/frontend-htmx-inventory.md` – Current HTMX usage inventory
- [x] `docs/frontend-roadmap-htmx-evaluation.md` – Complete evaluation & design (1000+ lines)
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Widget development guide

**For Users:**
- [ ] Dashboard builder user guide
- [ ] Widget configuration guide
- [ ] Video tutorial (optional)

---

**References:**
- See: `docs/frontend-roadmap-htmx-evaluation.md` for complete architecture analysis
- See: `docs/frontend-htmx-inventory.md` for current state inventory
- See: `docs/frontend-development-roadmap-archived-gridstack.md` for original GridStack plan

---

#### 6. Playlist Management UI

**Epic:** Playlist Features  
**Owner:** Frontend Team  
**Priority:** P1  
**Effort:** Medium (2-3 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Playlist Browser** | List and browse playlists | P1 | Medium | 📋 Planned |
| **Playlist Details** | Track list, metadata | P1 | Small | 📋 Planned |
| **Sync Status** | Visual sync indicators | P1 | Small | 📋 Planned |
| **Missing Tracks** | Compare and download | P0 | Medium | 📋 Planned |
| **Export Options** | M3U, CSV, JSON export | P1 | Small | 📋 Planned |

---

#### 7. Library Browser

**Epic:** Music Library UI  
**Owner:** Frontend Team  
**Priority:** P1  
**Effort:** Large (3-4 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Artist Browser** | Grid/list view of artists | P1 | Medium | 📋 Planned |
| **Album Browser** | Album grid with covers | P1 | Medium | 📋 Planned |
| **Track List** | Sortable, filterable tracks | P1 | Medium | 📋 Planned |
| **Search & Filter** | Advanced library search | P1 | Medium | 📋 Planned |
| **Metadata Editing** | Inline metadata editor | P1 | Large | 📋 Planned |

---

## 🔮 Later (>3 Months)

### Priority: MEDIUM/LOW (P2/P3)

#### 8. Advanced UI Features

| Feature | Description | Priority | Effort | Phase |
|---------|-------------|----------|--------|-------|
| **Mobile App** | React Native / PWA | P3 | Very Large | Phase 8 |
| **Browser Extension** | Quick add-to-queue button | P2 | Medium | Phase 8 |
| **Charts & Analytics** | Library statistics | P2 | Medium | Phase 8 |
| **Visualizations** | Genre charts, playcount graphs | P2 | Medium | Phase 8 |
| **Theme Customization** | Custom color schemes | P3 | Medium | Phase 8 |

---

#### 9. Accessibility Enhancements

| Feature | Description | Priority | Effort | Phase |
|---------|-------------|----------|--------|-------|
| **WCAG AAA** | Full AAA compliance | P2 | Large | Phase 8 |
| **Screen Reader** | Enhanced ARIA labels | P1 | Medium | Phase 7 |
| **High Contrast** | High contrast theme | P2 | Small | Phase 8 |
| **Reduced Motion** | Respect prefers-reduced-motion | P1 | Small | Phase 7 |
| **Focus Indicators** | Clear focus styles | P1 | Small | Phase 7 |

---

#### 10. Internationalization

| Feature | Description | Priority | Effort | Phase |
|---------|-------------|----------|--------|-------|
| **i18n Framework** | Translation infrastructure | P2 | Large | Phase 8 |
| **German Translation** | Full DE localization | P2 | Medium | Phase 8 |
| **French Translation** | Full FR localization | P3 | Medium | Phase 9 |
| **Spanish Translation** | Full ES localization | P3 | Medium | Phase 9 |
| **RTL Support** | Right-to-left languages | P3 | Large | Phase 9 |

---

## ⚠️ Dependencies & Risks

### External Dependencies

| Dependency | Impact | Risk Level | Mitigation |
|------------|--------|------------|------------|
| **HTMX Library** | Core interactivity | CRITICAL | Pin version (v1.9.10), CDN fallback |
| **Tailwind CSS** | Styling framework | HIGH | Self-hosted, build process |
| **~GridStack.js~** | ~~Widget grid~~ **REMOVED** | ~~HIGH~~ NONE | ✅ Replaced with HTMX-only button-based layout |
| **Heroicons** | Icon library | LOW | Local copy, SVG fallback |

**Note:** GridStack.js dependency removed in favor of pure HTMX approach with button-based layout controls.

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **~HTMX + GridStack Conflicts~** | ~~MEDIUM~~ **ELIMINATED** | ~~HIGH~~ NONE | ✅ No GridStack = No conflicts |
| **Performance (many widgets)** | MEDIUM | MEDIUM | Lazy loading, pagination, caching |
| **Mobile Responsiveness** | LOW | MEDIUM | ✅ Button-based layout = mobile-friendly by design |
| **Accessibility Gaps** | LOW | LOW | ✅ Native button accessibility, automated testing (axe) |
| **Browser Compatibility** | LOW | LOW | Progressive enhancement, HTMX polyfills |
| **User Resistance (buttons)** | LOW | MEDIUM | Clear labels, tooltips, user testing |
| **Backend Load (polling)** | MEDIUM | MEDIUM | Rate limiting, caching, upgrade to SSE in Phase 2 |

**Overall Risk Profile:** ✅ **LOW** (significantly reduced by eliminating GridStack)

### Dependencies Between Features

```
Phase 5 (Basic UI) ✅
    ↓
Phase 7 (UI Enhancements) ✅
    ├─→ Advanced Search UI ✅
    ├─→ Queue Management UI (partial)
    ├─→ Settings UI
    └─→ Loading/Error States ✅
    ↓
v2.0 (Dynamic Views) - HTMX-ONLY APPROACH
    ├─→ Phase 0: Foundation (database, migrations)
    ├─→ Phase 1: Canvas & Widget Partials (CSS Grid, templates)
    ├─→ Phase 2: Core Features (add/remove/move/resize)
    ├─→ Phase 3: Advanced (edit/view mode, config, pages)
    └─→ Phase 4: Launch (testing, rollout)
    ↓
Phase 8 (Advanced Features)
    ├─→ Mobile App / PWA
    ├─→ Browser Extension
    └─→ Analytics UI
```
    ├─→ Browser Extension
    └─→ Analytics UI
```

---

## 🔗 Links & References

### Documentation

- [Design Guidelines](design-guidelines.md)
- [Style Guide](soulspot-style-guide.md)
- [UI Screenshots](ui-screenshots.md)
- [Accessibility Guide](contributing.md#accessibility)

### Related Roadmaps

- [Backend Development Roadmap](backend-development-roadmap.md)
- [Cross-Cutting Concerns Roadmap](roadmap-crosscutting.md)
- [Full Development Roadmap (Index)](development-roadmap.md)

### External Resources

- [HTMX Documentation](https://htmx.org/docs/)
- [HTMX SSE Extension](https://htmx.org/extensions/server-sent-events/)
- [HTMX Examples](https://htmx.org/examples/)
- [Hypermedia Systems Book](https://hypermedia.systems/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)

---

## 📝 Changelog

### 2025-11-13: V2.0 HTMX-Only Architecture Decision

**Major Changes:**
- ✅ **Architecture Decision:** HTMX-Only with button-based layout (NO GridStack)
- ✅ Created comprehensive evaluation: `docs/frontend-roadmap-htmx-evaluation.md` (1000+ lines)
- ✅ Created inventory report: `docs/frontend-htmx-inventory.md` (567 lines)
- ✅ Updated v2.0 section with complete HTMX-only implementation plan
- ✅ Archived original GridStack plan: `docs/frontend-development-roadmap-archived-gridstack.md`
- ✅ Reduced development effort: 12-18 days (vs 25-35 for GridStack)
- ✅ Eliminated GridStack.js dependency and integration complexity
- ✅ Improved accessibility (WCAG 2.1 AA native compliance)
- ✅ Simplified mobile support (button-based vs drag-and-drop)
- ✅ Updated technical risks (LOW overall, eliminated GridStack conflicts)

**Rationale:**
Pure HTMX with button-based layout controls delivers superior accessibility, faster development, zero custom JavaScript, and mobile-friendly UX while accepting the trade-off of no free drag positioning.

**Implementation Ready:**
- Database schema designed (widgets, pages, widget_instances)
- API endpoints specified (13 routes)
- Template structure defined
- CSS Grid layout system designed
- HTMX patterns documented
- Effort estimate: 12-18 days across 4 phases

**Documentation:**
- `docs/frontend-roadmap-htmx-evaluation.md` - Complete evaluation with research, architecture options, API specs, code examples (26KB, 1001 lines)
- `docs/frontend-htmx-inventory.md` - Current HTMX usage inventory with readiness assessment (16KB, 567 lines)
- `docs/frontend-development-roadmap-archived-gridstack.md` - Original GridStack plan (archived for reference)

### 2025-11-12: Frontend Roadmap Created

**Changes:**
- ✅ Split from monolithic development roadmap
- ✅ Frontend-specific focus areas defined
- ✅ v2.0 Dynamic Views detailed planning (GridStack approach)
- ✅ Priorities and effort estimates added
- ✅ Dependencies and risks documented
- ✅ Now/Next/Later structure implemented

**Source:** Original `development-roadmap.md` (archived)

---

**End of Frontend Development Roadmap**
