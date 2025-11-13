# Frontend HTMX Inventory Report

> **Created:** 2025-11-13  
> **Purpose:** Comprehensive inventory of existing HTMX usage, templates, and frontend artifacts  
> **Status:** Complete

---

## 📑 Table of Contents

1. [Executive Summary](#executive-summary)
2. [HTMX Usage Analysis](#htmx-usage-analysis)
3. [Template Inventory](#template-inventory)
4. [Static Assets Inventory](#static-assets-inventory)
5. [Component & Partial Inventory](#component--partial-inventory)
6. [Readiness Assessment](#readiness-assessment)

---

## Executive Summary

### Current State
SoulSpot Bridge already uses HTMX extensively in its frontend architecture:
- **HTMX Version:** 1.9.10 (loaded via CDN in base.html)
- **Templates Using HTMX:** 5 of 11 templates (45%)
- **Total hx-* Attributes Found:** ~25+ instances
- **Primary Patterns:** hx-get, hx-post, hx-trigger, hx-swap, hx-target

### Key Findings
✅ **Strong Foundation:** Existing HTMX usage demonstrates familiarity and working patterns  
✅ **Progressive Enhancement:** Current implementation follows HTMX best practices  
✅ **Minimal JavaScript:** Only ~38KB of custom JS (app.js + search.js)  
⚠️ **No Partials Directory:** Templates don't have dedicated HTMX-loadable partials yet  
⚠️ **No SSE/WebSocket:** No real-time update patterns implemented yet  
📊 **GridStack Not Yet Integrated:** Planning stage only, no implementation

---

## HTMX Usage Analysis

### Templates with HTMX Integration

#### 1. `auth.html` - Spotify Authentication
**HTMX Attributes:** 4 instances  
**Patterns Used:**
```html
<!-- Authorize Button -->
hx-get="/api/v1/auth/authorize"
hx-target="#auth-result"

<!-- Callback Handler -->
hx-get="/api/v1/auth/callback"
hx-target="#token-result"
```

**Assessment:** ✅ Ready  
**Usage:** Simple GET requests with target swapping for OAuth flow  
**Strengths:** Clean separation of concerns, progressive enhancement  
**Gaps:** None

---

#### 2. `downloads.html` - Download Queue Management
**HTMX Attributes:** ~20+ instances  
**Patterns Used:**
```html
<!-- Global Queue Controls -->
hx-post="/api/v1/downloads/pause"
hx-swap="none"

hx-post="/api/v1/downloads/resume"
hx-swap="none"

<!-- Per-Download Controls -->
hx-post="/api/v1/downloads/{{ download.id }}/pause"
hx-swap="outerHTML"
hx-target="[data-download-id='{{ download.id }}']"

hx-post="/api/v1/downloads/{{ download.id }}/resume"
hx-swap="outerHTML"
hx-target="[data-download-id='{{ download.id }}']"

hx-post="/api/v1/downloads/{{ download.id }}/retry"
hx-swap="outerHTML"
hx-target="[data-download-id='{{ download.id }}']"

hx-post="/api/v1/downloads/{{ download.id }}/cancel"
hx-swap="outerHTML"
hx-target="[data-download-id='{{ download.id }}']"
```

**Assessment:** ✅ Ready (Advanced)  
**Usage:** Complex state management with targeted element swapping  
**Strengths:** 
- Granular control over individual downloads
- Proper use of outerHTML for element replacement
- Data attributes for precise targeting

**Gaps:** 
- No polling/SSE for real-time progress updates
- Client-side JavaScript handles filtering and batch operations

---

#### 3. `import_playlist.html` - Playlist Import
**HTMX Attributes:** 6 instances  
**Patterns Used:**
```html
<!-- Session Check on Load -->
hx-get="/api/v1/auth/session" 
hx-trigger="load"
hx-swap="innerHTML"

<!-- Import Form -->
hx-post="/api/v1/playlists/import"
hx-target="#import-result"
hx-swap="innerHTML"
```

**Assessment:** ✅ Ready  
**Usage:** Load-triggered session check + form submission with result swap  
**Strengths:** 
- Automatic session validation on page load
- Form handling without page refresh

**Gaps:** None

---

#### 4. `index.html` - Home Dashboard
**HTMX Attributes:** 3 instances  
**Patterns Used:**
```html
<!-- Session Status -->
hx-get="/api/v1/auth/session" 
hx-trigger="load"
hx-swap="innerHTML"
```

**Assessment:** ✅ Ready  
**Usage:** Session status check on page load  
**Strengths:** Consistent pattern with import_playlist.html  
**Gaps:** None

---

#### 5. `playlists.html` - Playlist Browser
**HTMX Attributes:** 2 instances  
**Patterns Used:**
```html
<!-- Sync Playlist -->
hx-post="/api/v1/playlists/{{ playlist.id }}/sync"
hx-swap="outerHTML"
```

**Assessment:** ✅ Ready  
**Usage:** Playlist sync with element replacement  
**Strengths:** Simple and effective pattern  
**Gaps:** Could benefit from progress feedback

---

### Templates WITHOUT HTMX

#### 1. `base.html` - Base Template
**Assessment:** ✅ Ready (Infrastructure)  
**Contains:** 
- HTMX script tag (CDN v1.9.10)
- Navigation structure
- Skip-to-content link (accessibility)

**Notes:** Correctly loads HTMX for all pages

---

#### 2. `search.html` - Track Search
**Assessment:** ⚠️ Partial  
**Current Implementation:** Full JavaScript (search.js - 26KB)  
**HTMX Opportunities:**
- Search form submission → hx-post with debouncing
- Filter panel → hx-get for filter application
- Result cards → hx-target for loading search results
- Autocomplete → hx-get with hx-trigger="keyup changed delay:300ms"

**Recommendation:** High priority for HTMX migration

---

#### 3. `settings.html` - Settings Page
**Assessment:** 🔴 Missing  
**Current Implementation:** Static template  
**HTMX Opportunities:**
- Form submission → hx-post
- Settings validation → hx-post with inline feedback
- Theme toggle → hx-post with instant preview

---

#### 4. `theme-sample.html` - UI Component Showcase
**Assessment:** ✅ Ready (Static)  
**Notes:** Static showcase page, no interactivity needed

---

### HTMX Patterns Summary

| Pattern | Usage Count | Pages | Readiness |
|---------|-------------|-------|-----------|
| `hx-get` | 7 | auth, import_playlist, index | ✅ Working |
| `hx-post` | 18+ | auth, downloads, playlists, import_playlist | ✅ Working |
| `hx-trigger` | 3 | import_playlist, index | ✅ Working |
| `hx-swap` | 23+ | All HTMX pages | ✅ Working |
| `hx-target` | 7 | auth, downloads, import_playlist | ✅ Working |
| `hx-boost` | 0 | None | 🔴 Not Used |
| `hx-sse` | 0 | None | 🔴 Not Implemented |
| `hx-ws` | 0 | None | 🔴 Not Implemented |
| `hx-indicator` | 0 | None | 🔴 Not Used |

---

## Template Inventory

### Complete Template List

```
src/soulspot/templates/
├── base.html                    # Base layout with HTMX CDN ✅
├── index.html                   # Home dashboard (HTMX: session) ✅
├── auth.html                    # Spotify OAuth (HTMX: authorize/callback) ✅
├── downloads.html               # Download queue (HTMX: extensive) ✅
├── playlists.html               # Playlist browser (HTMX: sync) ✅
├── import_playlist.html         # Import wizard (HTMX: session/import) ✅
├── search.html                  # Track search (JS-heavy, no HTMX) ⚠️
├── settings.html                # Settings page (Static) 🔴
├── theme-sample.html            # UI showcase (Static) ✅
└── includes/
    ├── _skeleton.html           # Loading skeletons (Jinja2 macros) ✅
    └── _theme.html              # Theme switcher (Minimal) ✅
```

**Total Templates:** 11  
**With HTMX:** 5 (45%)  
**Without HTMX:** 4 (36%)  
**Infrastructure:** 2 (18%)

---

## Static Assets Inventory

### JavaScript Files

#### 1. `app.js` (12.2 KB)
**Purpose:** Core application utilities  
**Contains:**
- ToastManager (notification system)
- LoadingManager (button/overlay loading states)
- KeyboardNav (keyboard shortcuts - Ctrl/Cmd+K, Escape)
- Theme utilities

**HTMX Integration:** ✅ Complementary  
**Lines of Code:** ~340  
**Dependencies:** None (vanilla JS)

**Modules:**
```javascript
ToastManager.show(message, type, title, duration)
ToastManager.success() / error() / warning() / info()

LoadingManager.showButtonLoading(button)
LoadingManager.hideButtonLoading(button)
LoadingManager.showOverlayLoading(container, message)
LoadingManager.hideOverlayLoading(container)

KeyboardNav.init()  // Ctrl/Cmd+K search focus, Escape modals
```

**Assessment:** ✅ Keep as-is (utility layer, not replacing HTMX)

---

#### 2. `search.js` (26.5 KB)
**Purpose:** Advanced search interface  
**Contains:**
- SearchManager class (~700 lines)
- Debounced autocomplete
- Client-side filtering
- Bulk selection
- Search history (localStorage)

**HTMX Migration Potential:** 🔴 High Priority  
**Lines of Code:** ~700  
**Dependencies:** None (vanilla JS)

**Current Approach:** Full client-side state management  
**HTMX Alternative:** 
- Server-side rendering of search results
- hx-get for autocomplete with debounce
- hx-post for bulk download
- Reduce JS to ~100 lines (just UI helpers)

**Recommendation:** Phase 2 migration to HTMX patterns

---

### CSS Files

#### 1. `input.css` (8.9 KB)
**Purpose:** Tailwind input file with custom utilities  
**Assessment:** ✅ Ready (compiled to style.css)

#### 2. `style.css` (30.5 KB)
**Purpose:** Compiled Tailwind CSS  
**Assessment:** ✅ Ready

#### 3. `theme.css` (10.1 KB)
**Purpose:** Theme-specific styles and dark mode  
**Assessment:** ✅ Ready

**Total CSS:** ~50 KB (reasonable size)

---

## Component & Partial Inventory

### Jinja2 Macros (`includes/_skeleton.html`)

```jinja2
<!-- Loading Skeletons -->
{% macro card_skeleton() %}
{% macro list_skeleton() %}
{% macro stats_skeleton() %}
{% macro table_skeleton() %}
{% macro spinner(size='md') %}
```

**Assessment:** ✅ Ready for HTMX partials  
**Usage:** Loading states while HTMX fetches content

**Recommendation:** These can serve as loading indicators:
```html
<div hx-get="/api/widgets/active-jobs" 
     hx-trigger="load" 
     hx-indicator=".htmx-indicator">
  {{ card_skeleton() }}
</div>
```

---

### Theme Components (`includes/_theme.html`)

Minimal theme switcher component.  
**Assessment:** ✅ Ready

---

### Missing Components for v2.0

**Needed for HTMX-First Widget System:**

1. **Widget Partials** (Not yet created)
   ```
   templates/partials/widgets/
   ├── active_jobs.html           # 🔴 Missing
   ├── spotify_search.html         # 🔴 Missing
   ├── missing_tracks.html         # 🔴 Missing
   ├── quick_actions.html          # 🔴 Missing
   └── metadata_manager.html       # 🔴 Missing
   ```

2. **Widget Container Partial** (Not yet created)
   ```html
   <!-- templates/partials/widget_card.html -->
   <div class="widget-card" data-widget-id="{{ widget.id }}">
     <div class="widget-header">
       <h3>{{ widget.title }}</h3>
       <button hx-delete="/api/widgets/{{ widget.id }}">Remove</button>
     </div>
     <div class="widget-body">
       {% include widget.template %}
     </div>
   </div>
   ```

3. **Canvas Layout Partial** (Not yet created)
   ```html
   <!-- templates/partials/canvas.html -->
   <div class="widget-canvas" hx-get="/api/views/current" hx-trigger="load">
     <!-- Widgets loaded here -->
   </div>
   ```

---

## Readiness Assessment

### Overall Readiness by Category

| Category | Status | Confidence | Notes |
|----------|--------|------------|-------|
| **HTMX Foundation** | ✅ Ready | 95% | Already integrated, v1.9.10 |
| **Basic HTMX Patterns** | ✅ Ready | 90% | Working in 5 templates |
| **Advanced Patterns (SSE)** | 🔴 Missing | 0% | Not implemented yet |
| **Widget Partials** | 🔴 Missing | 0% | Need to create |
| **Canvas System** | 🔴 Missing | 0% | Planning stage only |
| **JavaScript Utilities** | ✅ Ready | 95% | Toast, Loading, KeyboardNav |
| **Tailwind CSS** | ✅ Ready | 100% | Fully configured |
| **Accessibility** | ✅ Ready | 85% | WCAG 2.1 AA compliant |

---

### Readiness for v2.0 Widget System

#### ✅ What We Have (Ready)
- [x] HTMX library integrated (v1.9.10)
- [x] Working HTMX patterns in production
- [x] Tailwind CSS with custom theme
- [x] Loading state components (skeletons, spinners)
- [x] Toast notification system
- [x] Keyboard navigation utilities
- [x] Base template structure
- [x] Accessibility foundation (skip links, ARIA, focus management)

#### ⚠️ What Needs Work (Partial)
- [ ] Search page migration to HTMX (currently full JS)
- [ ] Settings page interactivity
- [ ] Real-time update patterns (polling/SSE)
- [ ] hx-indicator usage for loading states
- [ ] hx-boost for navigation links

#### 🔴 What's Missing (Not Started)
- [ ] Widget partial templates (5 core widgets)
- [ ] Widget container component
- [ ] Canvas layout system
- [ ] Widget palette UI
- [ ] Widget configuration modals
- [ ] View persistence API endpoints
- [ ] Server-side rendering for widgets
- [ ] hx-sse integration for real-time widgets

---

### Migration Priorities

#### High Priority (Blocking v2.0)
1. **Create Widget Partial System** - Templates for HTMX-loadable widgets
2. **Canvas Layout Implementation** - Container for widget cards
3. **Widget Registry API** - Backend endpoints for widget CRUD
4. **View Persistence** - Save/load widget layouts

#### Medium Priority (Enhances v2.0)
1. **Search Page HTMX Migration** - Replace search.js with server-side rendering
2. **Real-time Updates** - SSE or polling for live widgets
3. **Settings Page Interactivity** - HTMX forms with validation
4. **Widget Configuration Modals** - Per-widget settings

#### Low Priority (Polish)
1. **hx-boost Navigation** - Faster page transitions
2. **Advanced hx-indicator** - Custom loading states
3. **Optimistic Updates** - Instant UI feedback with hx-swap-oob

---

## Technical Debt & Recommendations

### Current Technical Debt

1. **search.js Complexity** (26KB)
   - **Impact:** Medium
   - **Effort to Fix:** ~3-5 days
   - **Recommendation:** Phase 2 migration to HTMX after v2.0 MVP

2. **No Partial Templates**
   - **Impact:** High (blocks v2.0)
   - **Effort to Fix:** ~1-2 days
   - **Recommendation:** Priority 1 - create `templates/partials/` structure

3. **No Real-time Patterns**
   - **Impact:** Medium
   - **Effort to Fix:** ~2-3 days (SSE), ~1 day (polling)
   - **Recommendation:** Start with polling, migrate to SSE later

4. **Minimal hx-indicator Usage**
   - **Impact:** Low
   - **Effort to Fix:** ~0.5 days
   - **Recommendation:** Add during v2.0 widget implementation

---

### Architecture Recommendations

#### 1. Adopt Partial Template Structure
```
templates/
├── pages/           # Full page templates
├── partials/        # HTMX-loadable components
│   ├── widgets/     # Widget partials
│   ├── forms/       # Form partials
│   └── cards/       # Reusable card components
└── includes/        # Jinja2 macros & includes
```

#### 2. Progressive Enhancement Strategy
- Keep JavaScript for utilities (Toast, Loading, KeyboardNav)
- Use HTMX for all server interactions
- Fallback to standard forms without JavaScript

#### 3. Real-time Update Approach
**Phase 1 (MVP):** Simple polling with hx-trigger
```html
<div hx-get="/api/widgets/active-jobs" 
     hx-trigger="every 5s">
  <!-- Widget content -->
</div>
```

**Phase 2 (Production):** Server-Sent Events
```html
<div hx-ext="sse" 
     sse-connect="/api/widgets/active-jobs/stream"
     sse-swap="message">
  <!-- Widget content -->
</div>
```

#### 4. Widget Communication Pattern
Use HTMX events for widget-to-widget communication:
```javascript
// Widget A triggers event after action
htmx.trigger('#widget-a', 'job-completed', {jobId: 123});

// Widget B listens and refreshes
<div hx-get="/api/widgets/stats" 
     hx-trigger="job-completed from:body">
```

---

## Conclusion

### Summary
SoulSpot Bridge has a **strong HTMX foundation** with 45% of templates already using HTMX patterns effectively. The infrastructure (CDN, Tailwind, utilities) is in place and working well.

### Key Gaps
1. No widget partial templates yet (required for v2.0)
2. No real-time update patterns (SSE/polling)
3. Search page is JavaScript-heavy (migration opportunity)
4. No widget canvas system (planning stage)

### Readiness for v2.0
**Overall: 60% Ready**
- Infrastructure: 95% ✅
- HTMX Patterns: 90% ✅
- Widget System: 0% 🔴
- Real-time: 0% 🔴

### Effort to Production-Ready v2.0
**Estimated:** 15-20 days
- Widget partials: 3-4 days
- Canvas system: 4-5 days
- Backend APIs: 3-4 days
- Real-time (polling): 1-2 days
- Testing & polish: 4-5 days

---

**Next Steps:** See `docs/frontend-roadmap-htmx-evaluation.md` for detailed architecture options, recommendations, and implementation plan.
