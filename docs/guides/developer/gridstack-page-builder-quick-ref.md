# GridStack Page-Builder — Quick Reference Guide

> **Version:** 2.0 Roadmap  
> **Status:** Planning Phase  
> **Last Updated:** 2025-11-11

---

## 📋 Overview

This quick reference guide provides a concise overview of all phases for implementing the GridStack-based page builder in SoulSpot v2.0.

**Full Documentation:** See [development-roadmap.md](development-roadmap.md) for complete specifications.

---

## 🎯 Core Concept

A visual page builder within FastAPI + HTMX + Templates architecture:
- **Pages (Dashboards)**: Multiple customizable views
- **Widgets**: Draggable, resizable components
- **Canvas**: Grid-based layout (GridStack.js)
- **Persistence**: DB-stored layouts and configurations

---

## 📐 Grid Page-Builder Phases (P1-P11)

### Phase P1 — Basis-Layout & GridStack-Integration
**Goal:** Functional grid surface with drag, drop, and resize

**Key Deliverables:**
- GridStack.js integration (12-column grid)
- Canvas template with `div.grid-stack`
- Drag & drop functionality
- HTMX compatibility verification
- Responsive behavior (desktop, tablet)

**Complexity:** LOW  
**Duration:** 2-3 days

---

### Phase P2 — Widget-System (Backend)
**Goal:** Standardized, extensible widget system

**Key Deliverables:**
- Widget catalog (DB/config): `id`, `slug`, `name`, `description`, `template_name`, `default_w`, `default_h`
- Widget instances: page association, layout info (x, y, w, h), settings (JSON)
- Rendering mechanism: `/widgets/render/{instance_id}`
- Template folder structure: `templates/widgets/`
- Domain service integration for data

**Complexity:** MEDIUM  
**Duration:** 3-4 days

---

### Phase P3 — Page-Management
**Goal:** Multiple independent pages (dashboards)

**Key Deliverables:**
- Page model: `id`, `name`, `description`, `created_at`, `updated_at`
- Page menu/sidebar UI
- CRUD operations (create, rename, duplicate, delete)
- Page switching with HTMX
- Widget-to-page association via `page_id`

**Complexity:** MEDIUM  
**Duration:** 2-3 days

---

### Phase P4 — Layout-Speicherung & Synchronisation
**Goal:** Reliable persistence of position and size changes

**Key Deliverables:**
- GridStack event handlers (`change`, `added`, `removed`)
- Update endpoint: `/builder/pages/{page_id}/layout`
- Server-side validation (grid limits, minimum sizes)
- JSON-based layout format
- Autosave functionality
- Manual save with feedback

**Complexity:** MEDIUM  
**Duration:** 2-3 days

---

### Phase P5 — Widget-Katalog & Hinzufügen
**Goal:** Easy widget addition from catalog

**Key Deliverables:**
- Widget catalog UI (sidebar/panel)
- Widget metadata display (name, icon, description, category)
- Drag & drop from catalog to canvas
- Alternative: Click-to-add with default position
- Widget instance creation API
- Category filtering
- Optional: Search, preview

**Complexity:** MEDIUM  
**Duration:** 2-3 days

---

### Phase P6 — Bearbeitungs- und Ansichtsmodi
**Goal:** Separation of "edit layout" vs "view/use"

**Key Deliverables:**
- Edit mode: Drag/resize enabled, handles visible, delete buttons
- View mode: Interactions disabled, clean UI
- Mode toggle (global per page/user)
- Session-based mode persistence

**Complexity:** LOW  
**Duration:** 1-2 days

---

### Phase P7 — Widget-Konfiguration & Einstellungen
**Goal:** Configurable widgets without hardcoded parameters

**Key Deliverables:**
- Settings schema per widget type
- Settings modal UI (HTMX-based)
- Settings CRUD API
- Per-instance JSON settings storage
- Setting integration in widget rendering

**Examples:**
- Download widget: Queue filters
- Statistics widget: Time range (day/week/month)
- Live widgets: Refresh interval, live on/off

**Complexity:** MEDIUM  
**Duration:** 2-3 days

---

### Phase P8 — UI-Komfort & Feinschliff
**Goal:** Improved usability and layout creation experience

**Key Deliverables:**
- Visual helpers (snap lines, guides)
- Auto-scroll on drag to edge
- Widget context menu (duplicate, z-index control)
- Save feedback notifications
- Error handling UI

**Complexity:** LOW-MEDIUM  
**Duration:** 2-3 days

---

### Phase P9 — Layout-Templates & Wiederverwendbarkeit
**Goal:** Quick creation of predefined dashboards

**Key Deliverables:**
- Template system for pages
- Predefined templates:
  - "Musik-Board": Now Playing, Download Status, Playlist Overview
  - "System-Board": Health Status, Logs, Queue Statistics
- Create from template
- Save as template
- JSON blueprint format

**Complexity:** MEDIUM  
**Duration:** 2-3 days

---

### Phase P10 — Sicherheit, Stabilität & Fehlerfall-Strategien
**Goal:** Robust builder behavior in edge cases

**Key Deliverables:**
- Server-side validation (positions, sizes)
- Fallback views for missing templates/data
- Error logging
- Rate limiting for layout updates
- Permission model (edit vs view)

**Complexity:** MEDIUM  
**Duration:** 2-3 days

---

### Phase P11 — Performance & Optimierung
**Goal:** Scalable behavior with many widgets

**Key Deliverables:**
- Lazy loading (render on viewport entry)
- Batch rendering (grouped requests)
- Optimized GridStack configuration
- Backend caching for widget data
- Performance monitoring metrics

**Complexity:** MEDIUM-HIGH  
**Duration:** 3-4 days

---

## 🔴 Live-Widgets Phases (L1-L4)

### Phase L1 — MVP Live-Widgets (Polling)
**Goal:** Basic live status with polling

**Key Deliverables:**
- Live widget definition (`is_live`, `refresh_interval`)
- Polling strategy (default intervals per category)
- Core widgets:
  - Download Status Widget (2-5s)
  - Now Playing Widget (3-10s)
  - System Health Widget (10-30s)
- Error handling for unavailable sources

**Complexity:** MEDIUM  
**Duration:** 3-4 days  
**Approach:** HTMX polling

---

### Phase L2 — User-Control & Performance-Feintuning
**Goal:** User control and load management

**Key Deliverables:**
- Per-widget refresh configuration
- Pause/resume for live updates
- Global limits (min interval, max parallel updates)
- UI indicators (live status, last update timestamp)

**Complexity:** LOW-MEDIUM  
**Duration:** 1-2 days

---

### Phase L3 — Push-Modus (SSE / WebSockets) [OPTIONAL]
**Goal:** Real-time behavior for critical widgets

**Key Deliverables:**
- Architecture decision (SSE vs WebSocket)
- Prototype for one widget with push
- Fallback to polling
- Per-widget push/poll configuration
- Connection monitoring

**Complexity:** HIGH  
**Duration:** 4-5 days  
**Status:** Optional, after stable polling

---

### Phase L4 — Observability & Stabilität
**Goal:** Measurable and stable live widget behavior

**Key Deliverables:**
- Logging (update frequency, errors)
- Metrics (response times, error rates)
- Fallback displays for persistent errors
- Clear, neutral error messages

**Complexity:** LOW-MEDIUM  
**Duration:** 1-2 days

---

## 🗓️ Estimated Timeline

### Critical Path (Minimum)
**P1 → P2 → P3 → P4 → P5 → L1**
- **Total:** ~15-20 days
- **Result:** Functional grid builder with basic live widgets

### Full MVP (Recommended)
**P1 → P2 → P3 → P4 → P5 → P6 → P7 → L1 → L2**
- **Total:** ~25-30 days
- **Result:** Complete page builder with configurable live widgets

### Complete Feature Set
**All phases P1-P11 + L1-L4**
- **Total:** ~35-45 days
- **Result:** Production-ready with templates, optimization, and push support

---

## 🔗 Data Sources for Live Widgets

### slskd API
- Download list with progress, speed, remaining time, status
- Download history (optional)

### Spotify / Playback Backend
- Currently playing track (artist, album, title)
- Player status (play, pause, skip)

### System / Health Endpoints
- slskd status (online/offline)
- Spotify API token validity
- Database connectivity

**Principle:** Widgets never contain business logic directly. All data access through defined domain services.

---

## 🏗️ Technical Stack

### Frontend
- **GridStack.js**: Grid layout engine
- **HTMX**: Dynamic content updates
- **Jinja2**: Template rendering
- **Tailwind CSS**: Styling

### Backend
- **FastAPI**: REST API
- **SQLAlchemy**: Database ORM
- **Pydantic**: Data validation
- **JSON Schema**: Widget settings validation

---

## 📊 Key API Endpoints

### Widget Registry
```
GET /api/widgets
- Returns all available widgets with schemas
```

### Views Management
```
GET    /api/views              # List all user views
GET    /api/views/:id          # Load specific view
POST   /api/views              # Create/update view
DELETE /api/views/:id          # Delete view
```

### Page Management
```
GET    /api/pages              # List all pages
GET    /api/pages/:id          # Load page with widgets
POST   /api/pages              # Create page
PUT    /api/pages/:id          # Update page
DELETE /api/pages/:id          # Delete page
```

### Widget Instances
```
POST   /api/widgets/instances  # Create widget instance
PUT    /api/widgets/instances/:id/settings  # Update settings
DELETE /api/widgets/instances/:id  # Remove widget
```

### Layout Updates
```
POST   /builder/pages/{page_id}/layout  # Update widget positions/sizes
```

### Widget Rendering
```
GET    /widgets/render/{instance_id}  # Render widget content
```

---

## 🎯 Success Criteria

### Functional
- [ ] Users can create and switch between multiple pages
- [ ] Widgets can be added from catalog via drag & drop
- [ ] Widget positions and sizes persist correctly
- [ ] Live widgets update automatically (polling)
- [ ] Edit/View mode toggle works as expected
- [ ] Widget settings can be configured via modal

### Non-Functional
- [ ] Grid operations feel smooth (< 100ms response)
- [ ] Layout saves complete in < 500ms
- [ ] Live widget updates don't impact UI performance
- [ ] No data loss on concurrent edits
- [ ] Error states are handled gracefully

### Security
- [ ] All operations are server-side validated
- [ ] Permission model enforced (view vs edit)
- [ ] Rate limiting prevents abuse
- [ ] No client-side data tampering possible

---

## 🚀 Next Steps

1. **Review & Approval**: Get maintainer approval for roadmap
2. **Issue Creation**: Create GitHub issues for each phase
3. **Design Phase**: Create wireframes and database schema
4. **Sprint Planning**: Plan first sprint (P1-P3)
5. **Implementation**: Start with Phase P1

---

## 📚 Related Documentation

- [Full Development Roadmap](development-roadmap.md) — Complete v2.0 specifications
- [Architecture Guide](architecture.md) — System architecture overview
- [Contributing Guide](contributing.md) — How to contribute
- [API Documentation](../README.md) — API reference

---

**Questions or feedback?** Open an issue or discussion on GitHub.
