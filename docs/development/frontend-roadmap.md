# SoulSpot – Frontend Development Roadmap

> **Version:** 1.0  
> **Last Updated:** 2025-11-26  
> **Current Phase:** Phase 1-5 Complete ✅ | Phase 2 UI Enhancements Live 🚀  
> **Owner:** Frontend Team  
> **App Version:** v0.1.0

---

## 🎯 Implementation Status

### ✅ Phases Complete (v0.1.0 - Current Release)

**Phase 1-5 Foundation (2025-11-08):**
- ✅ **Core Pages** - All primary pages, queue management, settings UI, search, authentication
- ✅ **UI Design System** - Component library, design tokens, accessibility features
- ✅ **Dashboard System** - Dynamic widget system with drag-and-drop customization
- ✅ **Server-Sent Events (SSE)** - Real-time updates infrastructure
- ✅ **Widget Template System** - Custom widget development framework

**Phase 1 UI Quick Wins (2025-11-26)** ✨ NEW:
- ✅ Optimistic UI updates (instant feedback)
- ✅ Ripple effects on interactions (Material Design)
- ✅ Circular progress indicators (SVG-based)
- ✅ Enhanced keyboard navigation (WCAG 2.1 AA)
- ✅ Lazy image loading (performance)
- ✅ Link prefetching on hover
- ✅ Stagger animations
- ✅ Skip-to-content accessibility

**Phase 2 UI Advanced Features (2025-11-26)** 🎨 NEW:
- ✅ Fuzzy search engine (typo-tolerant)
- ✅ Multi-criteria filtering (status, priority, progress)
- ✅ Native browser notifications
- ✅ Progressive Web App (PWA) with offline support
- ✅ Mobile gestures (swipe, pull-to-refresh)
- ✅ Advanced download filtering UI
- ✅ Glassmorphism design system
- ✅ Master-class UI animations (60fps)

**What's in progress:**
- 🚧 **Testing & Optimization** - Integration tests, E2E tests, performance improvements
- 🚧 **Custom Widget API** - Plugin system and developer tools

**What's planned for v1.0 (Phases 6+):**
1. 📋 **Automation & Watchlists** - Artist watchlists, discography tracking (Phase 6)
2. 📋 **Quality Upgrades** - Detect and upgrade low-quality tracks
3. 📋 **Advanced Search** - Ratings, quality filters, bulk operations
4. 📋 **Library Browser** - Artist/album/track browsing and metadata editing

---

## 📑 Table of Contents

1. [What's Next](#-whats-next---priority-ordered)
2. [Technology Stack](#-technology-stack)
3. [Completed Features](#-completed-features)
4. [Vision & Principles](#-vision--principles)
5. [Future Plans (>3 Months)](#-future-plans-3-months)
6. [Dependencies & Risks](#-dependencies--risks)
7. [Links & Resources](#-links--resources)

---

## 🚀 What's Next - Priority Ordered

### Priority 1: Dynamic Dashboard Builder ⭐ START HERE

**Epic: HTMX-Only Dashboard Builder (Button-Based Layout)**  
**Estimated Effort:** 12-18 days (2.5-3.5 weeks)  
**Status:** 🚧 Testing and Final Polish In Progress  
**Team:** Frontend

#### Why This First?
- Core feature for version 1.0
- Enables user customization
- Foundation for other features
- All planning complete

#### What We're Building

A customizable dashboard where users can:
- Add widgets from a catalog (5 core widgets)
- Arrange widgets using button controls (↑ ↓ ← →)
- Resize widgets with button clicks
- Save multiple dashboard layouts
- Switch between edit and view modes

**Architecture:** Pure HTMX + Jinja2 (NO drag-and-drop library needed)

#### Implementation Phases

| Phase | Focus | Estimated Time | Status |
|-------|-------|----------------|--------|
| **Stage: Foundation** | Database schema, migrations, API stubs | 2 days | ✅ Complete |
| **Stage: Canvas & Widgets** | CSS Grid layout, widget templates | 4-5 days | ✅ Complete |
| **Stage: Core Features** | Add/remove/move/resize widgets | 3-4 days | ✅ Complete |
| **Stage: Advanced** | Edit/view modes, config, pages, accessibility | 2-3 days | ✅ Complete |
| **Stage: Launch** | Testing, polish, rollout | 3-4 days | 🚧 In Progress |

#### 5 Core Widgets (MVP)

1. **Active Jobs Widget** - Real-time job monitoring with pause/resume
2. **Spotify Search Widget** - Inline search with quick download
3. **Missing Tracks Widget** - Playlist comparison and bulk download
4. **Quick Actions Widget** - Configurable action buttons
5. **Metadata Manager Widget** - Metadata issues and quick-fix actions

#### Acceptance Criteria

**Must Have:**
- [x] 5 widgets working with live updates
- [x] Button-based add/remove/move/resize
- [x] Edit and view modes
- [x] Save/load dashboard layouts
- [x] Mobile responsive
- [x] Keyboard accessible (WCAG 2.1 AA)

**Quality Gates:**
- [ ] Integration tests (>80% coverage) - In Progress
- [ ] E2E tests for critical paths - Pending
- [ ] Performance: load <1s, actions <300ms - Needs measurement
- [x] Accessibility audit passed - WCAG 2.1 AA compliant

#### Why HTMX-Only (No Drag-and-Drop)?

✅ **Better Accessibility** - Keyboard/screen-reader friendly  
✅ **Mobile Friendly** - Touch-friendly button controls  
✅ **Zero Custom JS** - Pure HTMX patterns  
✅ **Faster Development** - 12-18 days vs 25-35 for GridStack  
✅ **Easier Testing** - Standard HTTP patterns  
❌ **Trade-off:** No free-form drag positioning (acceptable)

**Full Details:** See [`docs/../archived/frontend-roadmap-htmx-evaluation.md`](../archived/frontend-roadmap-htmx-evaluation.md)

---

### Priority 1.5: Server-Sent Events & Widget Templates ⭐ COMPLETE

**Epic: Real-Time Updates & Custom Widget System**  
**Estimated Effort:** 8-10 days  
**Status:** ✅ Complete (Nov 2025)  
**Team:** Full-Stack

#### What Was Built

A comprehensive SSE infrastructure and widget template system that enables:
- Real-time updates for dashboard widgets without polling
- Custom widget development with JSON-based templates
- Plugin architecture for community widgets
- Automatic widget discovery and registration

#### Key Features Implemented

**1. Server-Sent Events (SSE) Infrastructure**
- ✅ FastAPI streaming endpoint (`/api/sse/stream`)
- ✅ SSE event encoding with proper formatting
- ✅ Event types: `connected`, `downloads_update`, `heartbeat`, `error`
- ✅ Connection health monitoring with 30s heartbeats
- ✅ Client disconnect detection and cleanup
- ✅ JavaScript `SSEClient` class with auto-reconnect
- ✅ Configurable reconnection strategy (exponential backoff)
- ✅ Heartbeat timeout detection
- ✅ Debug logging and connection status tracking

**2. Widget Template System**
- ✅ `WidgetTemplate` and `WidgetTemplateConfig` domain entities
- ✅ JSON schema for widget configuration
- ✅ Template validation and error handling
- ✅ `WidgetTemplateRegistry` service
- ✅ File system discovery for custom templates
- ✅ 5 system widgets registered (Active Jobs, Spotify Search, etc.)
- ✅ Category and tag-based organization
- ✅ Search and filtering capabilities

**3. Widget Template API**
- ✅ `GET /api/widgets/templates` - List all templates
- ✅ `GET /api/widgets/templates/{id}` - Get specific template
- ✅ `GET /api/widgets/templates/category/{category}` - Filter by category
- ✅ `POST /api/widgets/templates/search` - Search with filters
- ✅ `POST /api/widgets/templates/discover` - Discover custom templates
- ✅ `GET /api/widgets/templates/categories/list` - List categories
- ✅ `GET /api/widgets/templates/tags/list` - List all tags

**4. SSE-Enabled Widgets**
- ✅ Active Jobs widget with SSE updates (`active_jobs_sse.html`)
- ✅ Real-time progress bar updates
- ✅ Automatic UI synchronization
- ✅ Graceful degradation to polling if SSE unavailable

#### Technical Implementation

**SSE Architecture:**
```
Client (EventSource) → /api/sse/stream → StreamingResponse
                     ↓
                Event Generator (async)
                     ↓
            Repository Updates → SSE Events
                     ↓
            JavaScript SSEClient → DOM Updates
```

**Widget Template Structure:**
```json
{
  "id": "widget_id",
  "type": "widget_type",
  "config": {
    "name": "Widget Name",
    "description": "Widget description",
    "template_path": "partials/widgets/widget.html",
    "supports_sse": true,
    "sse_events": ["event_type"],
    "config_schema": { /* JSON schema */ },
    "default_config": { /* defaults */ }
  }
}
```

**Benefits:**
- ✅ **Performance:** No polling overhead, instant updates
- ✅ **Scalability:** One connection per client vs. polling every N seconds
- ✅ **Extensibility:** Easy to add new widgets via JSON templates
- ✅ **Developer Experience:** Clear API for custom widget development
- ✅ **User Experience:** Real-time updates feel native and responsive

#### Testing & Validation

- ✅ 7 unit tests for widget template system (all passing)
- ✅ 7 integration tests for SSE endpoints (all passing)
- ✅ SSE event encoding validation
- ✅ Connection lifecycle testing
- ✅ Template validation and error handling
- ✅ Registry search and filtering

#### Example Custom Widget

See `src/soulspot/templates/widget_templates/system_stats.json` for a complete example of a custom widget template.

**Full Details:** See implementation in `src/soulspot/api/routers/sse.py` and `src/soulspot/domain/entities/widget_template.py`

---

### Priority 2: Playlist Management UI

**Epic 6: Enhanced Playlist Features**  
**Estimated Effort:** 2-3 weeks  
**Status:** ✅ Complete (Dec 2025)  
**Team:** Frontend

#### What Needs to Be Done

| Feature | Description | Status |
|---------|-------------|--------|
| **Playlist Details Page** | Full track list with metadata | ✅ Complete |
| **Sync Status Indicators** | Visual badges (synced, pending, failed) | ✅ Complete |
| **Missing Tracks View** | Compare playlists and show missing | ✅ Complete |
| **Export Functions** | M3U, CSV, JSON export | ✅ Complete |
| **Bulk Operations** | Select multiple tracks for actions | ✅ Complete |

#### Current State
- ✅ Basic playlists page with grid view
- ✅ Import playlist page
- ✅ Sync button with status indicators
- ✅ Full detail view with track listings
- ✅ Missing tracks comparison feature
- ✅ Bulk selection and download
- ✅ Export modal with M3U/CSV/JSON formats

#### Acceptance Criteria
- [x] Click on playlist → shows detail page with all tracks
- [x] Sync status badges visible and accurate
- [x] Missing tracks comparison works (Spotify vs Library)
- [x] Can export playlist to M3U/CSV/JSON
- [x] Bulk actions available (select multiple, download all)

---

### Priority 3: Library Browser

**Epic 7: Music Library UI**  
**Estimated Effort:** 3-4 weeks  
**Status:** ✅ Complete (Dec 2025)  
**Team:** Frontend

#### What Needs to Be Done

| Feature | Description | Status |
|---------|-------------|--------|
| **Artist Browser** | Grid/list view with cover art | ✅ Complete |
| **Album Browser** | Album grid with metadata | ✅ Complete |
| **Track List View** | Sortable, filterable track table | ✅ Complete |
| **Advanced Search** | Search across entire library | ✅ Complete (client-side) |
| **Metadata Editor** | Inline editing of track metadata | ✅ Complete |

#### Current State
- ✅ Backend API endpoints ready (`/library/...`)
- ✅ Database schema complete
- ✅ Album completeness checking
- ✅ Frontend templates with detail pages
- ✅ Artist and album detail pages
- ✅ Metadata editor with file tag updates
- ✅ Client-side search and filtering

#### Acceptance Criteria
- [x] Browse artists in grid/list view
- [x] Browse albums with cover art
- [x] View and sort tracks
- [x] Search functionality works
- [x] Can edit metadata inline (artist, album, title, genre, etc.)
- [x] Changes persist to database and update files

---

## 🛠️ Technology Stack

| Component | Technology | Version | Status |
|-----------|-----------|---------|--------|
| **Template Engine** | Jinja2 | - | ✅ In Use |
| **Interactivity** | HTMX | 1.9.10 | ✅ In Use |
| **Styling** | Tailwind CSS | 3.x | ✅ In Use |
| **JavaScript** | Vanilla JS (minimal) | ES6+ | ✅ In Use |
| **Icons** | Heroicons / Lucide | - | ✅ In Use |
| **Build Tool** | Tailwind CLI | - | ✅ In Use |

### Design System

**Location:** `/docs/ui/`

- **`theme.css`** - Design tokens (colors, typography, spacing)
- **`components.css`** - UI components (buttons, cards, forms, tables)
- **`layout.css`** - Layout utilities (grid, flexbox, responsive)
- **`ui-demo.html`** - Interactive component showcase
- **`README_UI_1_0.md`** - Complete documentation

---

## ✅ version 1.0 Achievements (Complete)

**Status:** ✅ Completed November 2025  
**All Core Features Delivered:**

### Pages Implemented (9 Total)
1. ✅ Dashboard - Home page with overview
2. ✅ Search - Advanced search with filters
3. ✅ Playlists - Playlist browser (basic)
4. ✅ Import - Playlist import page
5. ✅ Downloads - Queue management with priority
6. ✅ Auth - Spotify authentication
7. ✅ Settings - 5-tab settings page
8. ✅ Onboarding - User onboarding flow
9. ✅ Theme Sample - Component showcase

### Key Features
- ✅ **Download Queue** - Priority indicators, pause/resume, batch operations, filters
- ✅ **Settings UI** - Form validation, theme switcher, API key management, 5 tabs
- ✅ **Advanced Search** - Filters, autocomplete, bulk actions, history
- ✅ **UI/UX** - Loading states, toast notifications, keyboard navigation
- ✅ **Accessibility** - WCAG 2.1 AA compliance, screen reader support
- ✅ **Design System** - 10+ reusable components, dark mode

### Deliverables
- ✅ 10+ reusable Jinja2 component macros
- ✅ 62KB+ comprehensive documentation
- ✅ Full HTMX integration patterns
- ✅ Mobile-first responsive design
- ✅ Complete test coverage

**Full version 1.0 Details:** See [`docs/FRONTEND_V1_SUMMARY.md`](FRONTEND_V1_SUMMARY.md)

---

## 🎯 Vision & Principles

### Vision
Provide a clean, modern, accessible web UI for SoulSpot that works beautifully on all devices without requiring a heavy JavaScript framework.

### Core Principles

**Technical Approach:**
- ✅ **Progressive Enhancement** - Works without JavaScript, enhanced with HTMX
- ✅ **Server-Side Rendering** - Jinja2 templates for fast initial load
- ✅ **Minimal JS** - HTMX handles most interactivity
- ✅ **Component-Based** - Reusable template partials

**User Experience:**
- ✅ **Accessibility First** - WCAG AA compliance, keyboard navigation
- ✅ **Responsive Design** - Mobile-first approach
- ✅ **Performance** - Optimized assets, lazy loading
- ✅ **Dark Mode** - Theme support with user preferences

### HTMX Integration Patterns

```html
<!-- Dynamic Content Loading -->
<div hx-get="/api/jobs" hx-trigger="load" hx-swap="innerHTML">
  Loading...
</div>

<!-- Form Submissions -->
<form hx-post="/api/downloads" hx-target="#queue">
  <!-- Form fields -->
</form>

<!-- Polling for Updates -->
<div hx-get="/api/jobs/active" hx-trigger="every 2s">
  <!-- Job list -->
</div>
```

---

## 🔮 Future Plans (>3 Months)

**Not Planned for version 1.0 - Lower Priority:**

### Advanced Features (Phase 8)
- Mobile App (React Native / PWA) - P3
- Browser Extension - P2
- Charts & Analytics - P2
- Custom Visualizations - P2
- Theme Customization - P3

### Enhanced Accessibility (Phase 8-9)
- WCAG AAA Compliance - P2
- High Contrast Theme - P2
- Additional Language Support - P2

### Internationalization (Phase 8-9)
- i18n Framework - P2
- German Translation - P2
- French/Spanish Translations - P3
- RTL Support - P3

---

## ⚠️ Dependencies & Risks

### External Dependencies

| Dependency | Impact Level | Status | Notes |
|------------|-------------|--------|-------|
| **HTMX** | CRITICAL | ✅ Stable | v1.9.10 pinned, CDN + local fallback |
| **Tailwind CSS** | HIGH | ✅ Stable | Self-hosted, build process |
| **Heroicons** | LOW | ✅ Stable | Local SVG copies |

### Technical Risks (version 1.0)

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **User resistance to button-based layout** | LOW | MEDIUM | User testing, clear tooltips |
| **Performance with many widgets** | MEDIUM | MEDIUM | Lazy loading, pagination, caching |
| **Mobile layout complexity** | LOW | MEDIUM | Mobile-first CSS, testing |
| **Backend load from polling** | MEDIUM | MEDIUM | Rate limiting, SSE upgrade in Phase 2 |

**Overall Risk Level:** ✅ LOW

### Feature Dependencies

```
version 1.0 (Complete) ✅
    ↓
version 1.0 Dashboard Builder (Current Focus)
    ├─→ Stage: Foundation
    ├─→ Stage: Canvas & Widgets
    ├─→ Stage: Core Features
    ├─→ Stage: Advanced
    └─→ Stage: Launch
    ↓
Playlist Management UI
    ↓
Library Browser
    ↓
Future Features (Phase 8+)
```

---

## 🔗 Links & Resources

### Internal Documentation

**version 1.0 Planning:**
- [HTMX Evaluation & Architecture](../archived/frontend-roadmap-htmx-evaluation.md) - Complete version 1.0 technical design
- [HTMX Usage Inventory](archived/frontend-htmx-inventory.md) - Current HTMX patterns

**version 1.0 Reference:**
- [version 1.0 Summary](FRONTEND_V1_SUMMARY.md) - Complete version 1.0 feature list
- [version 1.0 Archived Roadmap](../archived/frontend-development-roadmap-version 1.0.md) - Original version 1.0 planning

**Design Resources:**
- [UI Design System](ui/) - Component library and design tokens
- [Design Guidelines](guide/design-guidelines.md) - Design principles
- [Keyboard Navigation Guide](guide/keyboard-navigation.md) - Shortcuts reference

**Other Roadmaps:**
- [Backend Development Roadmap](backend-roadmap.md) - Backend features
- [Architecture Overview](architecture.md) - System architecture

### External Resources

**HTMX:**
- [HTMX Documentation](https://htmx.org/docs/)
- [HTMX Examples](https://htmx.org/examples/)
- [Hypermedia Systems Book](https://hypermedia.systems/)

**Other:**
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

---

## 📝 Recent Changes

### 2025-11-17: Server-Sent Events & Widget Template System Complete ✅
- ✅ **SSE Infrastructure Implemented**
  - FastAPI streaming endpoint with `text/event-stream`
  - SSE event encoding (connected, downloads_update, heartbeat, error)
  - JavaScript SSEClient class with auto-reconnect
  - Heartbeat monitoring and timeout detection
  - Client disconnect handling
  - Test endpoint for debugging
  - Comprehensive test coverage (7 integration tests)

- ✅ **Widget Template System Implemented**
  - Domain entities: `WidgetTemplate` and `WidgetTemplateConfig`
  - JSON schema validation for configuration
  - Template registry with discovery
  - File system-based custom templates
  - 5 system widgets registered
  - Category and tag organization
  - Search and filtering API
  - REST endpoints for template management
  - Example custom widget (system_stats.json)
  - Unit tests (7 tests, all passing)

- ✅ **SSE-Enabled Widgets**
  - Active Jobs widget with real-time updates
  - Progress bar synchronization
  - Automatic UI updates without page reload
  - Graceful degradation support

**Impact:** Enables real-time dashboard updates and custom widget development, eliminating polling overhead and providing extensibility framework.

### 2025-11-17: version 1.0 Phase 0-3 Complete - Dashboard Widget System Fully Implemented ✅
- ✅ **Stage: Foundation Complete**
  - Database schema with migrations (widgets, pages, widget_instances tables)
  - Domain entities with full business logic
  - API endpoints for all CRUD operations
  - Repository layer implementation

- ✅ **Stage: Canvas & Widgets Complete**
  - CSS Grid 12-column responsive layout
  - 5 core widget templates implemented
  - Widget canvas with loading states
  - Dark mode support
  - Mobile-first responsive design

- ✅ **Stage: Core Features Complete**
  - Button-based widget controls (↑ ↓ ← → ⬌ ⚙ ✕)
  - Add/remove widgets functionality
  - Move widgets in 4 directions
  - Resize widgets (4/6/12 columns)
  - Widget configuration modals
  - Page management (create, switch, delete)

- ✅ **Stage: Advanced Features Complete**
  - Edit and view modes
  - Keyboard navigation (Ctrl+E, Ctrl+A, Ctrl+P, Ctrl+?, Esc)
  - Keyboard shortcuts help modal
  - WCAG 2.1 AA accessibility compliance
  - ARIA labels and roles
  - Focus management
  - Screen reader support
  - Reduced motion support
  - Improved modal UX

- 🚧 **Stage: Launch In Progress**
  - [ ] Integration tests expansion
  - [ ] E2E tests for critical flows
  - [ ] Performance measurement and optimization
  - [ ] Final data integration verification

**Next Actions:**
1. Write comprehensive integration tests
2. Implement E2E tests for keyboard navigation
3. Measure and optimize performance
4. Verify all widget data flows
5. Final polish and documentation

### 2025-11-17: Roadmap Restructured for Clarity
- ✅ Reorganized to prioritize "What's Next"
- ✅ Moved version 1.0 completed features to summary section
- ✅ Improved visual hierarchy and scanning
- ✅ Added clear priority ordering (P1, P2, P3)
- ✅ Simplified structure (removed redundant details)
- ✅ Enhanced "Quick Overview" section

### 2025-11-16: version 1.0 Complete - All Features Delivered
- ✅ version 1.0 marked as complete (9 pages, all features)
- ✅ Updated roadmap to reflect completion status
- ✅ version 1.0 status changed to "Ready for Implementation"

### 2025-11-13: V2.0 HTMX-Only Architecture Decided
- ✅ Architecture decision: HTMX-only with button-based layout
- ✅ Created evaluation docs (1000+ lines)
- ✅ Archived GridStack hybrid approach
- ✅ Reduced effort estimate: 12-18 days

---

**Last Updated:** 2025-11-17  
**Document Owner:** Frontend Team  
**Status:** version 1.0 Complete ✅ | version 1.0 Ready to Start 📋
