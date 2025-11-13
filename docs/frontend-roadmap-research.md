# Frontend V2.0 - Repository Inventory & Architecture Research

> **Created:** 2025-11-13  
> **Status:** Part 1 of 3 - Repository Inventory & Architecture Research  
> **Purpose:** Comprehensive analysis for V2.0 Dynamic Views & Widget Palette feature  
> **Next:** Part 2 will cover API Contracts & Widget System Design

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Repository Inventory](#repository-inventory)
3. [External Research](#external-research)
4. [Architecture Options](#architecture-options)
5. [Recommended Architecture](#recommended-architecture)
6. [Integration Considerations](#integration-considerations)
7. [References & Sources](#references--sources)

---

## 🎯 Executive Summary

### Current State
SoulSpot Bridge is a server-driven web application built with:
- **Backend:** FastAPI (Python 3.12+) with SQLAlchemy
- **Frontend:** Jinja2 templates + HTMX + Tailwind CSS
- **Architecture:** Layered architecture with DDD principles
- **Deployment:** Docker-based with production readiness

### V2.0 Goal
Implement a **Grid-Based Page Builder** with **Widget Palette** allowing users to:
- Create custom dashboard layouts using drag-and-drop
- Add, remove, and configure widgets (Active Jobs, Search, Playlists, etc.)
- Save and load personalized views
- Real-time widget updates for live data

### Key Finding
**Recommendation:** Progressive, server-centric approach using HTMX + GridStack.js + Jinja2 partials
- ✅ Aligns with existing architecture
- ✅ Minimal JavaScript overhead
- ✅ Progressive enhancement friendly
- ✅ Easier to maintain and test

---

## 📦 Repository Inventory

### A. Frontend Structure

#### Templates (8 files)
**Location:** `src/soulspot/templates/`

| File | Purpose | HTMX Usage | Widget Potential |
|------|---------|-----------|------------------|
| `base.html` | Base layout with navigation | No | N/A - Base template |
| `index.html` | Dashboard/home page | ✅ Session check | ⭐ Main canvas target |
| `playlists.html` | Playlist listing | ✅ Sync actions | ⭐ Playlist widget |
| `downloads.html` | Download queue | ✅ Polling, filters | ⭐⭐ Active Jobs widget |
| `import_playlist.html` | Import interface | ✅ Form submission | ⭐ Quick action widget |
| `auth.html` | Spotify authentication | ✅ OAuth flow | Authentication widget |
| `theme-sample.html` | Design system showcase | No | Component library |
| `includes/_theme.html` | Theme variables | No | Design tokens |

**Key Findings:**
- ✅ HTMX already integrated (v1.9.10)
- ✅ Server-side rendering with Jinja2
- ✅ Tailwind CSS for styling
- ❌ No GridStack or layout management yet
- ❌ No widget system or dynamic views
- ✅ Good foundation for progressive enhancement

#### Static Assets
**Location:** `src/soulspot/static/`

**JavaScript** (`static/js/`):
- `app.js` (40 lines) - Basic HTMX event handlers and auto-refresh
  - Polling for downloads (5s interval)
  - HTMX event listeners
  - OAuth auto-fill logic
  
**CSS** (`static/css/`):
- `style.css` (14.7KB) - Tailwind compiled output
- `theme.css` (10KB) - Harmony theme variables
- `input.css` (4.6KB) - Tailwind source

**Key Findings:**
- ✅ Minimal JavaScript footprint (~40 lines)
- ✅ HTMX handles most interactivity
- ❌ No GridStack integration
- ❌ No drag-and-drop libraries
- ❌ No layout persistence logic
- ✅ Tailwind configured with 12-column grid system

#### Configuration
**Tailwind Config** (`tailwind.config.js`):
```javascript
content: [
  "./src/soulspot/templates/**/*.html",
  "./src/soulspot/static/js/**/*.js",
]
```
- ✅ 12-column grid system available
- ✅ Custom color palette (primary, secondary, semantic colors)
- ✅ Responsive breakpoints (sm, md, lg, xl, 2xl)
- ✅ Dark mode support via CSS variables

### B. Backend Structure

#### API Routes
**Location:** `src/soulspot/api/routers/`

| Router | Purpose | Endpoints | Widget Relevance |
|--------|---------|-----------|------------------|
| `ui.py` | HTML page serving | 6 routes | ⭐ Will serve widget partials |
| `downloads.py` | Download management | CRUD operations | ⭐⭐ Active Jobs widget API |
| `playlists.py` | Playlist operations | List, sync | ⭐⭐ Playlist widget API |
| `tracks.py` | Track search | Search endpoint | ⭐ Search widget API |
| `auth.py` | OAuth flow | Authorize, callback | Authentication status |

**Key Findings:**
- ✅ REST API structure in place
- ✅ FastAPI with Jinja2Templates integration
- ❌ No widget registry endpoints
- ❌ No view/layout persistence endpoints
- ❌ No widget rendering partials yet
- ✅ Good foundation for extending with widget APIs

#### Domain Layer
**Location:** `src/soulspot/domain/`

Key entities:
- `entities/track.py` - Track domain model
- `entities/playlist.py` - Playlist domain model
- `entities/download.py` - Download job model
- `value_objects/` - TrackId, PlaylistId, etc.

**Key Findings:**
- ✅ Clean domain model with entities and value objects
- ❌ No Page or Widget entities yet
- ❌ No WidgetInstance or LayoutConfig domain models
- ✅ Repository pattern already implemented

#### Infrastructure Layer
**Database:** SQLAlchemy with SQLite (production: PostgreSQL ready)
**Integrations:** slskd, Spotify, MusicBrainz, CoverArt Archive

**Key Findings:**
- ✅ Alembic migrations in place
- ❌ No tables for pages, widgets, or layouts
- ❌ No widget_definitions or widget_instances tables
- ✅ Easy to extend with new tables via migration

### C. Existing GridStack Documentation

**Files:**
- `GRIDSTACK_IMPLEMENTATION_NOTES.md` (443 lines)
- `docs/gridstack-page-builder-quick-ref.md` (410 lines)

**Key Findings:**
- ✅ Comprehensive planning already done
- ✅ 11 phases (P1-P11) + 4 live widget phases (L1-L4) defined
- ✅ Database schema drafted
- ✅ API endpoint specifications outlined
- ✅ Timeline estimates: 25-30 days for full MVP
- ❌ No implementation yet - pure planning

### D. Search Patterns Results

**GridStack references:** Found in archived roadmaps and planning docs only  
**Widget patterns:** No implementation found  
**SSE/WebSocket:** No implementation found  
**Layout/Save View:** No implementation found  
**Drag/Drop:** No implementation found  

**Conclusion:** V2.0 is greenfield - no legacy code to migrate or refactor.

---

## 🔬 External Research

### A. HTMX + GridStack Integration

#### Key Resources
1. **GridStack.js Official Docs** - https://gridstackjs.com/
   - Version: 10.x (latest stable)
   - Features: Touch support, responsive, auto-positioning
   - Bundle size: ~47KB minified

2. **HTMX Documentation** - https://htmx.org/docs/
   - Already using v1.9.10
   - Server-driven UI philosophy
   - Out-of-band swaps for targeted updates

3. **Integration Patterns** - Research from various sources:
   - htmx.org/examples/ (server-driven components)
   - GridStack + Alpine.js patterns (similar progressive approach)
   - Django + HTMX + GridStack examples

#### Integration Challenges & Solutions

**Challenge 1: HTMX DOM Swaps Breaking GridStack**
- **Problem:** When HTMX swaps HTML, GridStack loses its initialized state
- **Solution:** Re-initialize GridStack after HTMX swaps using `htmx:afterSwap` event
```javascript
document.body.addEventListener('htmx:afterSwap', function(evt) {
  if (evt.detail.target.id === 'widget-container') {
    GridStack.init({...options});
  }
});
```

**Challenge 2: Server-Side Rendering of Widget Positions**
- **Problem:** GridStack expects JavaScript-driven initialization
- **Solution:** Render widget positions as data attributes in Jinja2, then hydrate
```html
<div class="grid-stack-item" 
     gs-x="{{ widget.x }}" 
     gs-y="{{ widget.y }}"
     gs-w="{{ widget.w }}" 
     gs-h="{{ widget.h }}">
  <div class="grid-stack-item-content">
    {% include widget.template %}
  </div>
</div>
```

**Challenge 3: Persisting Layout Changes**
- **Problem:** Need to send layout updates to server after drag/drop
- **Solution:** Capture GridStack `change` event and POST to server
```javascript
grid.on('change', function(event, items) {
  htmx.ajax('POST', '/api/builder/layout', {
    values: {layout: JSON.stringify(items)},
    target: '#status',
  });
});
```

**Challenge 4: Live Widget Updates**
- **Problem:** Widgets need real-time data without full page refresh
- **Solution:** HTMX polling or SSE for individual widgets
```html
<div hx-get="/api/widgets/active-jobs/render" 
     hx-trigger="every 3s"
     hx-swap="innerHTML">
  <!-- Widget content -->
</div>
```

#### Best Practices Identified
1. ✅ Keep GridStack initialization minimal - let server render positions
2. ✅ Use HTMX `hx-preserve` to prevent widget re-render during parent swaps
3. ✅ Separate edit mode (drag enabled) from view mode (drag disabled)
4. ✅ Use JSON in data attributes for complex widget configurations
5. ✅ Implement optimistic UI updates for better perceived performance

### B. Alternative Solutions Evaluated

#### Option 1: GridStack.js ⭐ RECOMMENDED
**Pros:**
- ✅ Mature, well-documented (10+ years)
- ✅ Touch support for mobile/tablet
- ✅ Responsive breakpoints built-in
- ✅ Small bundle size (~47KB)
- ✅ No framework dependency
- ✅ Works well with server-rendered HTML

**Cons:**
- ⚠️ Requires JavaScript (but progressive enhancement possible)
- ⚠️ HTMX integration needs careful event handling
- ⚠️ Mobile drag-and-drop UX can be tricky

**Verdict:** Best fit for server-centric architecture

#### Option 2: Muuri (https://github.com/haltu/muuri)
**Pros:**
- ✅ Smooth animations
- ✅ Drag & drop, sorting
- ✅ No dependencies

**Cons:**
- ❌ Less popular (fewer examples)
- ❌ More focused on masonry layouts
- ❌ No built-in responsive breakpoints
- ❌ Would require more custom code

**Verdict:** Good for specific use cases, not ideal for grid builder

#### Option 3: Packery (https://packery.metafizzy.co/)
**Pros:**
- ✅ Nice masonry layout
- ✅ Drag and drop

**Cons:**
- ❌ Commercial license required
- ❌ Not actively maintained
- ❌ Less suitable for fixed grid layouts

**Verdict:** Not recommended

#### Option 4: React-Grid-Layout (SPA approach)
**Pros:**
- ✅ Very popular in React ecosystem
- ✅ Excellent developer experience
- ✅ Rich feature set

**Cons:**
- ❌ Requires full SPA architecture
- ❌ Complete rewrite of frontend
- ❌ Larger bundle size
- ❌ More complex build process
- ❌ Loses server-rendering benefits

**Verdict:** Architectural mismatch - not recommended

### C. Server-Driven UI Patterns

#### Research Sources
- **htmx.org/essays/** - Server-side rendering philosophy
- **Phoenix LiveView patterns** - Server-driven real-time UIs
- **Hotwire (Rails)** - Turbo Frames and Streams
- **Django Unicorn** - Reactive components without JavaScript

#### Key Patterns for Widget System

**Pattern 1: Partial Templates for Widgets**
- Each widget = separate Jinja2 template
- Server renders widget HTML on demand
- HTMX swaps widget content on update
- Example: `templates/widgets/active_jobs.html`

**Pattern 2: Widget Configuration via JSON**
- Store widget settings as JSON in database
- Pass to template as context variable
- Template renders based on settings
- Edit settings via modal, POST to server

**Pattern 3: Real-Time Updates via SSE**
- Server-Sent Events for push updates
- HTMX SSE extension: `hx-sse="connect:/stream"`
- Each widget subscribes to relevant events
- Fallback: polling with `hx-trigger="every Ns"`

**Pattern 4: Optimistic UI for Layout Changes**
- GridStack updates UI immediately on drag
- Background HTMX POST persists to server
- On error, revert or show notification
- Keeps UI responsive

### D. Accessibility Research

#### ARIA Patterns for Drag & Drop
**Source:** WAI-ARIA Authoring Practices Guide  
**URL:** https://www.w3.org/WAI/ARIA/apg/patterns/

**Key Requirements:**
1. **Keyboard Support**
   - Space/Enter to grab item
   - Arrow keys to move
   - Space/Enter to drop
   - Esc to cancel

2. **ARIA Attributes**
   ```html
   <div role="grid" aria-label="Dashboard layout">
     <div role="gridcell" 
          aria-grabbed="false" 
          aria-dropeffect="move">
       <div role="application" aria-label="Active Jobs Widget">
         <!-- Widget content -->
       </div>
     </div>
   </div>
   ```

3. **Focus Management**
   - Clear focus indicators
   - Focus trap in modals
   - Announce state changes to screen readers

4. **Screen Reader Announcements**
   - Use `aria-live` regions for updates
   - Announce drag start/end
   - Announce position changes

**GridStack Accessibility:**
- ⚠️ No built-in keyboard support
- ⚠️ Requires custom implementation
- ✅ Can add ARIA attributes to generated HTML
- 📝 Need to implement keyboard navigation layer

**Recommended Approach:**
- Phase 1: Mouse/touch drag-and-drop only
- Phase 2: Add keyboard navigation
- Phase 3: Full WCAG AA compliance
- Testing: Use axe-core automated checks + manual testing

---

## 🏗️ Architecture Options

### Option 1: Progressive Server-Centric (HTMX + GridStack) ⭐

#### Technology Stack
- **Grid Layout:** GridStack.js 10.x (~47KB)
- **Interactivity:** HTMX 1.9.x (already in use)
- **Templating:** Jinja2 (server-side)
- **Styling:** Tailwind CSS (12-column grid)
- **Real-time:** Server-Sent Events (SSE) with HTMX extension
- **Storage:** PostgreSQL (JSON columns for layouts)

#### Architecture Diagram
```
┌─────────────────────────────────────────┐
│         Browser (Client)                │
├─────────────────────────────────────────┤
│  GridStack.js (Layout Management)       │
│  HTMX (Interactivity)                   │
│  Minimal Custom JS (Init, Events)       │
│  Tailwind CSS (Styling)                 │
└─────────────────────────────────────────┘
                    ↕ HTTP/SSE
┌─────────────────────────────────────────┐
│       FastAPI Backend (Server)          │
├─────────────────────────────────────────┤
│  Jinja2 Templates (Widget Rendering)    │
│  REST Endpoints (CRUD, Layout)          │
│  SSE Streams (Real-time Updates)        │
│  SQLAlchemy ORM (Persistence)           │
└─────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────┐
│         PostgreSQL Database             │
├─────────────────────────────────────────┤
│  pages (user views)                     │
│  widget_definitions (widget catalog)    │
│  widget_instances (placed widgets)      │
└─────────────────────────────────────────┘
```

#### Request Flow Examples

**1. Page Load**
```
User → GET /builder → FastAPI
  ↓
FastAPI queries DB for user's page
  ↓
Jinja2 renders base layout + widgets
  ↓
HTML with data-gs-* attributes sent to browser
  ↓
GridStack.init() hydrates layout
  ↓
HTMX initializes polling for live widgets
```

**2. Widget Update (Live Data)**
```
Browser (every 3s) → hx-get="/api/widgets/123/render"
  ↓
FastAPI fetches fresh data (jobs, tracks, etc.)
  ↓
Jinja2 renders widget partial
  ↓
HTMX swaps innerHTML of widget
  ↓
User sees updated data
```

**3. Layout Change (Drag Widget)**
```
User drags widget → GridStack 'change' event
  ↓
JS captures new positions
  ↓
hx-post="/api/builder/layout" (JSON payload)
  ↓
FastAPI validates and saves to DB
  ↓
Success response
  ↓
Optional: Toast notification
```

#### Pros
- ✅ **Consistency:** Aligns with existing architecture
- ✅ **Performance:** Server-side rendering, fast initial load
- ✅ **SEO:** Fully server-rendered (if public pages needed)
- ✅ **Progressive Enhancement:** Works without JS (basic view)
- ✅ **Simplicity:** Less JavaScript to maintain
- ✅ **Testing:** Standard FastAPI + pytest testing
- ✅ **Security:** Server validates all changes
- ✅ **Caching:** Can cache rendered partials
- ✅ **Team Skills:** Python team doesn't need React expertise

#### Cons
- ⚠️ **HTMX + GridStack Integration:** Requires careful event handling
- ⚠️ **Real-time Complexity:** SSE setup more complex than WebSocket
- ⚠️ **Mobile UX:** GridStack drag-and-drop not perfect on mobile
- ⚠️ **Accessibility:** Need custom keyboard navigation
- ⚠️ **Learning Curve:** Team needs to learn GridStack API

#### Effort Estimate
- **Phase 1 (Grid + Widgets):** 10-12 days
- **Phase 2 (Persistence):** 5-7 days
- **Phase 3 (Real-time):** 4-6 days
- **Phase 4 (Polish + A11y):** 8-10 days
- **Total:** 27-35 days

---

### Option 2: Client-Driven SPA (React + react-grid-layout)

#### Technology Stack
- **Framework:** React 18 + TypeScript
- **Grid Layout:** react-grid-layout
- **State Management:** Redux or Zustand
- **API Client:** React Query + Axios
- **Styling:** Tailwind CSS + CSS Modules
- **Real-time:** WebSocket (socket.io or native)
- **Build:** Vite or Create React App

#### Architecture Diagram
```
┌─────────────────────────────────────────┐
│    Browser (Single Page Application)   │
├─────────────────────────────────────────┤
│  React Components (Widget System)       │
│  react-grid-layout (Layout)             │
│  Redux/Zustand (State)                  │
│  React Query (API Cache)                │
│  WebSocket Client (Real-time)           │
└─────────────────────────────────────────┘
                    ↕ REST + WS
┌─────────────────────────────────────────┐
│       FastAPI Backend (API Only)        │
├─────────────────────────────────────────┤
│  REST Endpoints (JSON API)              │
│  WebSocket Server (Real-time)           │
│  SQLAlchemy ORM (Persistence)           │
└─────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────┐
│         PostgreSQL Database             │
└─────────────────────────────────────────┘
```

#### Pros
- ✅ **Rich Interactivity:** Excellent user experience
- ✅ **Mature Ecosystem:** react-grid-layout very popular
- ✅ **Developer Experience:** React DevTools, hot reload
- ✅ **Real-time:** WebSocket simpler than SSE
- ✅ **Mobile:** Better mobile UX with libraries like react-dnd
- ✅ **Community:** Large React community for help

#### Cons
- ❌ **Complete Rewrite:** All templates need converting to React
- ❌ **Bundle Size:** Large JavaScript bundle (~300KB+)
- ❌ **Build Complexity:** Webpack/Vite config, multiple build steps
- ❌ **Team Skills:** Requires React expertise
- ❌ **Testing:** Need Jest, React Testing Library, E2E setup
- ❌ **Maintenance:** Two codebases (API + SPA)
- ❌ **SEO:** SSR setup complex (Next.js) if needed
- ❌ **Deployment:** More complex (serve static + API)
- ❌ **Architecture Mismatch:** Loses server-rendering benefits

#### Effort Estimate
- **Phase 1 (React Setup):** 5-7 days
- **Phase 2 (Convert Templates):** 15-20 days
- **Phase 3 (Grid + Widgets):** 10-12 days
- **Phase 4 (Real-time + Polish):** 8-10 days
- **Total:** 38-49 days

**Additional Cost:** Ongoing maintenance of two separate codebases

---

### Option 3: Hybrid (HTMX + Alpine.js + GridStack)

#### Technology Stack
- **Base:** HTMX (existing)
- **Reactivity:** Alpine.js (lightweight ~15KB)
- **Grid Layout:** GridStack.js
- **Templating:** Jinja2 (server-side)
- **Real-time:** SSE with HTMX

#### Pros
- ✅ Adds reactivity to Option 1 with minimal overhead
- ✅ Alpine.js good for widget-level interactivity
- ✅ Still mostly server-driven
- ✅ Smaller than full SPA

#### Cons
- ⚠️ Adds another dependency (Alpine.js)
- ⚠️ Team needs to learn Alpine.js
- ⚠️ Not necessary for MVP - HTMX + minimal JS sufficient

#### Verdict
**Possible future enhancement, but not needed for MVP**

---

## ✅ Recommended Architecture

### **Option 1: Progressive Server-Centric (HTMX + GridStack)**

#### Justification

**1. Alignment with Current Stack**
- Already using HTMX + Jinja2 + FastAPI
- No need to rewrite existing templates
- Leverages team's Python expertise
- Consistent with project philosophy (server-driven UI)

**2. Cost-Benefit Analysis**
- 27-35 days vs 38-49 days (SPA)
- Lower maintenance burden (single codebase approach)
- Simpler deployment (no separate frontend build)
- Faster time to market

**3. Technical Advantages**
- Server-side rendering = fast initial load
- Better caching opportunities
- Easier to secure (all logic on server)
- Progressive enhancement fallback

**4. Team Considerations**
- Python team doesn't need deep React knowledge
- Easier to onboard new developers
- Less context switching (server templates)

**5. Future Flexibility**
- Can add more JavaScript interactivity later if needed
- Can migrate specific widgets to SPA pattern if required
- Not locked into architectural decision

#### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| HTMX + GridStack conflicts | Medium | High | Extensive testing, event handling patterns |
| Mobile drag-and-drop UX | Medium | Medium | Responsive design, touch optimizations |
| Accessibility gaps | Medium | Medium | Phased approach, axe-core testing |
| Performance (many widgets) | Low | Medium | Lazy loading, caching, pagination |
| SSE browser support | Low | Low | Polling fallback, all modern browsers support SSE |

---

## 🔧 Integration Considerations

### A. GridStack.js Integration Details

#### Installation
```bash
# Via CDN (recommended for MVP)
<script src="https://cdn.jsdelivr.net/npm/gridstack@10/dist/gridstack-all.js"></script>
<link href="https://cdn.jsdelivr.net/npm/gridstack@10/dist/gridstack.min.css" rel="stylesheet"/>

# Or via npm (for production)
npm install gridstack
```

#### Initialization Pattern
```javascript
// File: src/soulspot/static/js/builder.js
document.addEventListener('DOMContentLoaded', function() {
  const grid = GridStack.init({
    column: 12,
    cellHeight: '70px',
    acceptWidgets: true,
    removable: '#trash',
    float: true,
    disableOneColumnMode: false, // Important for mobile
  });

  // Listen for layout changes
  grid.on('change', function(event, items) {
    saveLayout(items);
  });

  // Re-init after HTMX swaps
  document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.classList.contains('grid-stack')) {
      GridStack.init();
    }
  });
});

function saveLayout(items) {
  const layout = items.map(item => ({
    id: item.el.dataset.widgetId,
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
  }));
  
  htmx.ajax('POST', '/api/builder/layout', {
    values: {layout: JSON.stringify(layout)},
    swap: 'none',
  });
}
```

### B. HTMX Patterns for Widgets

#### Pattern 1: Polling Widget
```html
<div class="grid-stack-item" gs-x="0" gs-y="0" gs-w="4" gs-h="3">
  <div class="grid-stack-item-content">
    <div hx-get="/api/widgets/active-jobs/render"
         hx-trigger="every 3s"
         hx-swap="innerHTML"
         hx-preserve="true">
      {% include 'widgets/active_jobs.html' %}
    </div>
  </div>
</div>
```

#### Pattern 2: Action Button in Widget
```html
<!-- Inside widget template -->
<button hx-post="/api/downloads/{{ job.id }}/pause"
        hx-target="#job-{{ job.id }}"
        hx-swap="outerHTML"
        class="btn-sm">
  Pause
</button>
```

#### Pattern 3: Widget Configuration Modal
```html
<button hx-get="/api/widgets/{{ widget.id }}/settings"
        hx-target="#modal-container"
        hx-swap="innerHTML"
        class="widget-config-btn">
  ⚙️ Settings
</button>
```

### C. Server-Side Rendering Pattern

#### Widget Partial Template Example
```jinja2
{# templates/widgets/active_jobs.html #}
<div class="widget-card">
  <div class="widget-header">
    <h3>Active Jobs</h3>
    <span class="badge">{{ jobs|length }}</span>
  </div>
  <div class="widget-body">
    {% for job in jobs %}
    <div id="job-{{ job.id }}" class="job-item">
      <span>{{ job.track_name }}</span>
      <div class="progress-bar" style="width: {{ job.progress }}%"></div>
      <div class="job-actions">
        <button hx-post="/api/downloads/{{ job.id }}/pause">Pause</button>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
```

#### Backend Endpoint
```python
@router.get("/api/widgets/active-jobs/render")
async def render_active_jobs_widget(
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> HTMLResponse:
    active_jobs = await download_repository.list_active()
    return templates.TemplateResponse(
        "widgets/active_jobs.html",
        {"jobs": active_jobs}
    )
```

### D. Performance Considerations

#### Lazy Loading Strategy
- Load grid canvas immediately
- Lazy-load widget content after page load
- Use Intersection Observer for below-fold widgets

#### Caching Strategy
- Cache widget templates in memory (Jinja2 compiled)
- Cache widget data per user (Redis or in-memory)
- ETags for widget partial responses
- Short TTL for live widgets (3-5s), longer for static (60s)

#### Bundle Size Optimization
- GridStack: ~47KB minified
- HTMX: ~14KB (already loaded)
- Custom JS: <5KB
- **Total Additional:** ~52KB (acceptable)

---

## 📚 References & Sources

### Official Documentation
1. **GridStack.js** - https://gridstackjs.com/
   - API Documentation: https://gridstackjs.com/api/
   - Examples: https://gridstackjs.com/demo/

2. **HTMX** - https://htmx.org/
   - Documentation: https://htmx.org/docs/
   - Examples: https://htmx.org/examples/
   - SSE Extension: https://htmx.org/extensions/server-sent-events/

3. **Tailwind CSS** - https://tailwindcss.com/
   - Grid System: https://tailwindcss.com/docs/grid-template-columns

4. **FastAPI** - https://fastapi.tiangolo.com/
   - Templates: https://fastapi.tiangolo.com/advanced/templates/
   - WebSockets: https://fastapi.tiangolo.com/advanced/websockets/

### Accessibility Resources
5. **WAI-ARIA Authoring Practices** - https://www.w3.org/WAI/ARIA/apg/
   - Drag and Drop: https://www.w3.org/WAI/ARIA/apg/patterns/

6. **axe-core** - https://github.com/dequelabs/axe-core
   - Automated accessibility testing

### Integration Patterns
7. **Server-Driven UI Patterns**
   - Phoenix LiveView: https://hexdocs.pm/phoenix_live_view/
   - Hotwire: https://hotwired.dev/
   - Django Unicorn: https://www.django-unicorn.com/

8. **HTMX + GridStack Examples**
   - Community examples from htmx.org forums
   - GitHub: Search for "htmx gridstack" implementations

### Alternative Evaluations
9. **Muuri** - https://github.com/haltu/muuri
10. **Packery** - https://packery.metafizzy.co/
11. **react-grid-layout** - https://github.com/react-grid-layout/react-grid-layout

---

## 📝 Next Steps

This document completes **Part 1: Repository Inventory & Architecture Research**.

### Deliverables in This Document
- ✅ Comprehensive repository inventory
- ✅ Analysis of existing codebase (templates, static assets, backend)
- ✅ External research on HTMX + GridStack integration
- ✅ Evaluation of alternative solutions
- ✅ Recommended architecture with detailed justification
- ✅ Integration considerations and patterns
- ✅ References and sources

### Next Documents (Separate PRs)
- **Part 2:** API Contracts & Widget System Design
  - Backend endpoint specifications (REST + SSE)
  - Database schema design
  - Widget lifecycle and interface contracts
  - Example implementations

- **Part 3:** Updated Frontend Roadmap
  - Concrete Epics with Acceptance Criteria
  - Task breakdown (Now/Next/Later)
  - Effort estimates and priorities
  - Testing strategy
  - Migration and rollout plan

---

**Document Status:** Complete  
**Review Requested:** Yes  
**Next Action:** Create Part 2 PR for API Contracts & Widget System Design
