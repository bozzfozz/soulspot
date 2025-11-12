# SoulSpot Bridge – Frontend Development Roadmap

> **Last Updated:** 2025-11-12  
> **Version:** 0.1.0 (Alpha)  
> **Status:** Phase 5 Complete - Basic UI | v2.0 Dynamic Views Planning In Progress  
> **Owner:** Frontend Team

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

**Implemented Features:**
- ✅ Base template with navigation
- ✅ Home dashboard
- ✅ Spotify authentication pages
- ✅ Download queue views
- ✅ Track search interface
- ✅ Basic HTMX interactions
- ✅ Tailwind CSS styling
- ✅ Dark mode support

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

#### 1. UI/UX Improvements

**Epic:** Enhanced User Experience  
**Owner:** Frontend Team  
**Priority:** P1  
**Effort:** Medium (2-3 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Loading States** | Skeleton screens, spinners | P1 | Small | 📋 Planned |
| **Error Handling** | User-friendly error messages | P0 | Small | 📋 Planned |
| **Success Feedback** | Toast notifications, confirmations | P1 | Small | 📋 Planned |
| **Empty States** | Meaningful empty state designs | P1 | Small | 📋 Planned |
| **Keyboard Navigation** | Full keyboard accessibility | P1 | Medium | 📋 Planned |

**Acceptance Criteria:**
- [ ] Loading states for all async operations
- [ ] Consistent error message styling and placement
- [ ] Toast notification system implemented
- [ ] Empty states for all list views
- [ ] Tab navigation works throughout app
- [ ] Focus management for modals and dialogs

---

#### 2. Advanced Search Interface

**Epic:** Enhanced Search UI  
**Owner:** Frontend Team  
**Priority:** P1  
**Effort:** Medium (2 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Advanced Filters UI** | Filter by artist, album, quality | P1 | Medium | 📋 Planned |
| **Search Suggestions** | Autocomplete with HTMX | P1 | Medium | 📋 Planned |
| **Result Previews** | Expanded track information | P1 | Small | 📋 Planned |
| **Bulk Actions** | Select multiple results | P1 | Medium | 📋 Planned |
| **Search History** | Recent searches display | P2 | Small | 📋 Planned |

**Acceptance Criteria:**
- [ ] Filter panel with collapsible sections
- [ ] Autocomplete suggestions (debounced)
- [ ] Expandable result cards
- [ ] Checkbox selection for bulk download
- [ ] Search history (client-side storage)

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

#### 5. v2.0 Dynamic Views & Widget-Palette

**Epic:** Grid-Based Page Builder  
**Owner:** Frontend Team  
**Priority:** P0 (Strategic)  
**Effort:** Very Large (4-5 weeks)

| Phase | Description | Priority | Effort | Status |
|-------|-------------|----------|--------|--------|
| **Phase A: Design** | Wireframes & component design | P0 | Small | 📋 Planned |
| **Phase B: Infrastructure** | Grid canvas + widget palette | P0 | Large | 📋 Planned |
| **Phase C: Core Widgets** | 5 essential widgets | P0 | Large | 📋 Planned |
| **Phase D: Composite** | Widget-in-widget support | P1 | Medium | 📋 Planned |
| **Phase E: Polish** | UX refinements, docs | P1 | Medium | 📋 Planned |

**Key Features:**

##### Grid Canvas
- **GridStack.js Integration** – 12-column responsive grid
- **Drag & Drop** – Free widget placement
- **Resize Support** – Visual resize handles
- **Responsive Layout** – Mobile, tablet, desktop breakpoints
- **Edit/View Modes** – Toggle between editing and viewing

##### Widget System
- **Widget Palette** – Catalog of available widgets
- **Widget Configuration** – Settings modal per widget
- **Widget Actions** – Interactive buttons within widgets
- **Real-Time Updates** – WebSocket or polling for live data
- **Save/Load Views** – Persistent user layouts

##### 5 Core Widgets (MVP)

1. **Active Jobs Widget**
   - Real-time job monitoring
   - Progress bars with ETA
   - Pause/cancel/retry actions
   - Configurable refresh interval

2. **Spotify Search Widget**
   - Inline search interface
   - Result preview cards
   - Quick download button
   - Settings for search mode

3. **Missing Tracks Widget**
   - Playlist comparison
   - Missing track list
   - Bulk download action
   - CSV/JSON export

4. **Quick Actions Widget**
   - Configurable button grid
   - Common actions (scan, import, fix)
   - Keyboard shortcuts
   - Visual feedback

5. **Metadata Manager Widget**
   - Metadata issue list
   - Filter by problem type
   - Quick-fix actions
   - Batch operations

**Acceptance Criteria:**
- [ ] Grid canvas with GridStack.js
- [ ] Drag & drop widget placement
- [ ] Widget palette with category filter
- [ ] Settings modal for widget config
- [ ] All 5 core widgets functional
- [ ] Save/load view persistence
- [ ] Edit/view mode toggle
- [ ] Responsive on mobile/tablet/desktop
- [ ] WCAG AA accessibility compliance

**Dependencies:**
- Backend API endpoints for widgets
- WebSocket or SSE for real-time updates
- Database schema for saved views

**Risks:**
- GridStack.js + HTMX integration complexity
- Performance with many widgets
- Mobile responsiveness challenges

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
| **HTMX Library** | Core interactivity | CRITICAL | Pin version, CDN fallback |
| **Tailwind CSS** | Styling framework | HIGH | Self-hosted, build process |
| **GridStack.js (v2.0)** | Widget grid system | HIGH | Evaluate alternatives, fallback layout |
| **Heroicons** | Icon library | LOW | Local copy, SVG fallback |

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **HTMX + GridStack Conflicts** | MEDIUM | HIGH | Careful event handling, testing |
| **Performance (many widgets)** | MEDIUM | MEDIUM | Lazy loading, virtualization |
| **Mobile Responsiveness** | MEDIUM | HIGH | Mobile-first design, extensive testing |
| **Accessibility Gaps** | MEDIUM | MEDIUM | Automated testing (axe), manual audit |
| **Browser Compatibility** | LOW | MEDIUM | Progressive enhancement, polyfills |

### Dependencies Between Features

```
Phase 5 (Basic UI) ✅
    ↓
Phase 7 (UI Enhancements)
    ├─→ Advanced Search UI
    ├─→ Queue Management UI
    ├─→ Settings UI
    └─→ Loading/Error States
    ↓
v2.0 (Dynamic Views)
    ├─→ Grid Canvas (Phase B)
    ├─→ Widget System (Phase B)
    ├─→ 5 Core Widgets (Phase C)
    └─→ Composite Widgets (Phase D)
    ↓
Phase 8 (Advanced Features)
    ├─→ Mobile App / PWA
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
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [GridStack.js Documentation](https://gridstackjs.com/)
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)

---

## 📝 Changelog

### 2025-11-12: Frontend Roadmap Created

**Changes:**
- ✅ Split from monolithic development roadmap
- ✅ Frontend-specific focus areas defined
- ✅ v2.0 Dynamic Views detailed planning
- ✅ Priorities and effort estimates added
- ✅ Dependencies and risks documented
- ✅ Now/Next/Later structure implemented

**Source:** Original `development-roadmap.md` (archived)

---

**End of Frontend Development Roadmap**
