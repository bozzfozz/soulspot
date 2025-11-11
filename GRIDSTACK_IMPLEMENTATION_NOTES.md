# GridStack Page-Builder Implementation Notes

> **Created:** 2025-11-11  
> **Status:** Planning Complete  
> **Next Phase:** Design & Architecture

---

## 📝 Documentation Status

### Completed ✅
- [x] Full roadmap specification added to `docs/development-roadmap.md`
- [x] Quick reference guide created at `docs/gridstack-page-builder-quick-ref.md`
- [x] Table of contents updated
- [x] Changelog entries added
- [x] Status header updated

### Documentation Files

1. **docs/development-roadmap.md**
   - Lines added: ~570
   - Total size: 3,261 lines
   - Contains: Full specifications for phases P1-P11 and L1-L4

2. **docs/gridstack-page-builder-quick-ref.md**
   - Lines: ~410
   - Purpose: Developer quick reference
   - Contains: Phase summaries, timelines, API overview

---

## 🎯 Implementation Phases Overview

### Grid Page-Builder (P1-P11)

**Foundation (P1-P3)** - 7-10 days
- P1: GridStack integration, canvas, drag & drop
- P2: Widget system backend (registry, instances, rendering)
- P3: Page management (CRUD, switching)

**Core Features (P4-P7)** - 7-11 days
- P4: Layout persistence and synchronization
- P5: Widget catalog with drag & drop
- P6: Edit/view mode toggle
- P7: Widget configuration and settings

**Polish & Production (P8-P11)** - 9-13 days
- P8: UI improvements and visual helpers
- P9: Templates and reusability
- P10: Security, validation, permissions
- P11: Performance optimization

**Total: 23-34 days**

### Live Widgets (L1-L4)

**MVP (L1-L2)** - 4-6 days
- L1: Polling-based live widgets (download, now playing, health)
- L2: User controls and performance tuning

**Advanced (L3-L4)** - 5-7 days (Optional)
- L3: Push mode with SSE/WebSockets
- L4: Observability and stability

**Total: 9-13 days (4-6 for MVP)**

---

## 🗓️ Recommended Implementation Timeline

### Option 1: Minimal MVP (15-20 days)
**Phases:** P1 + P2 + P3 + P4 + P5 + L1

**Delivers:**
- Functional grid builder
- Basic page management
- Widget catalog
- Layout persistence
- Live widgets (polling)

**Good for:** Quick validation of concept

---

### Option 2: Full MVP (25-30 days) ⭐ RECOMMENDED
**Phases:** P1-P7 + L1-L2

**Delivers:**
- Complete grid builder
- Edit/view modes
- Widget configuration
- Live widgets with user controls

**Good for:** Production-ready v2.0 release

---

### Option 3: Complete Feature Set (35-45 days)
**Phases:** P1-P11 + L1-L4

**Delivers:**
- All grid features
- Templates
- Performance optimization
- Push mode for live widgets

**Good for:** Enterprise deployment

---

## 🔧 Technical Implementation Notes

### Key Dependencies
```json
{
  "gridstack": "^10.x",
  "htmx": "^1.9.x (already in use)",
  "jinja2": "^3.x (already in use)",
  "fastapi": "^0.115.x (already in use)",
  "sqlalchemy": "^2.x (already in use)"
}
```

### Database Schema (Draft)

#### Tables to Add

**pages**
```sql
CREATE TABLE pages (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    user_id INTEGER,  -- For multi-user support
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**widget_definitions** (or use JSON config)
```sql
CREATE TABLE widget_definitions (
    id INTEGER PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    template_name VARCHAR(255) NOT NULL,
    default_w INTEGER DEFAULT 4,
    default_h INTEGER DEFAULT 3,
    category VARCHAR(100),
    settings_schema JSON,
    is_live BOOLEAN DEFAULT FALSE,
    refresh_interval INTEGER DEFAULT 0
);
```

**widget_instances**
```sql
CREATE TABLE widget_instances (
    id INTEGER PRIMARY KEY,
    page_id INTEGER NOT NULL,
    widget_id INTEGER NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    w INTEGER NOT NULL,
    h INTEGER NOT NULL,
    settings JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE,
    FOREIGN KEY (widget_id) REFERENCES widget_definitions(id)
);
```

### API Endpoints to Implement

#### Widget Registry
```python
@router.get("/api/widgets")
async def get_widget_registry() -> List[WidgetDefinition]:
    """Return all available widgets with their schemas"""
    pass
```

#### Page Management
```python
@router.get("/api/pages")
async def list_pages(user_id: int) -> List[Page]:
    """List all pages for a user"""
    pass

@router.get("/api/pages/{page_id}")
async def get_page(page_id: int) -> PageWithWidgets:
    """Get page with all widget instances"""
    pass

@router.post("/api/pages")
async def create_page(page: PageCreate) -> Page:
    """Create a new page"""
    pass

@router.put("/api/pages/{page_id}")
async def update_page(page_id: int, page: PageUpdate) -> Page:
    """Update page metadata"""
    pass

@router.delete("/api/pages/{page_id}")
async def delete_page(page_id: int) -> None:
    """Delete a page and all its widgets"""
    pass
```

#### Widget Instances
```python
@router.post("/api/widgets/instances")
async def create_widget_instance(instance: WidgetInstanceCreate) -> WidgetInstance:
    """Add a widget to a page"""
    pass

@router.put("/api/widgets/instances/{instance_id}/settings")
async def update_widget_settings(instance_id: int, settings: dict) -> WidgetInstance:
    """Update widget settings"""
    pass

@router.delete("/api/widgets/instances/{instance_id}")
async def remove_widget_instance(instance_id: int) -> None:
    """Remove a widget from a page"""
    pass
```

#### Layout Updates
```python
@router.post("/builder/pages/{page_id}/layout")
async def update_page_layout(
    page_id: int, 
    layout: List[WidgetPosition]
) -> None:
    """Update positions and sizes of all widgets on a page"""
    pass
```

#### Widget Rendering
```python
@router.get("/widgets/render/{instance_id}")
async def render_widget(instance_id: int) -> HTMLResponse:
    """Render a widget's HTML content"""
    pass
```

---

## 🧪 Testing Strategy

### Unit Tests
- Widget registry CRUD
- Page management CRUD
- Widget instance CRUD
- Layout validation logic
- Settings schema validation

### Integration Tests
- Full page creation flow
- Widget addition and removal
- Layout persistence
- Live widget updates

### E2E Tests
- Create page → Add widgets → Save → Reload
- Edit mode → Drag widget → Save → Verify position
- Live widget → Wait for update → Verify content

---

## 🔒 Security Considerations

### Server-Side Validation
- [ ] All widget positions within grid bounds
- [ ] Widget sizes respect min/max constraints
- [ ] Settings conform to JSON schema
- [ ] Rate limiting on layout updates (prevent DOS)
- [ ] Permission checks for page operations

### Permission Model
```python
class Permission(Enum):
    VIEW_PAGE = "page:view"
    EDIT_PAGE = "page:edit"
    CREATE_PAGE = "page:create"
    DELETE_PAGE = "page:delete"
    MANAGE_WIDGETS = "widget:manage"
```

### Input Sanitization
- [ ] Validate all JSON settings
- [ ] Escape HTML in widget templates
- [ ] Prevent XSS in widget content
- [ ] Validate integer ranges (x, y, w, h)

---

## 📊 Performance Targets

### Response Times (p95)
- Page load: < 1s
- Widget render: < 500ms
- Layout update: < 200ms
- Live widget refresh: < 100ms

### Scalability
- Support up to 50 widgets per page
- Support up to 100 pages per user
- Handle 10 concurrent users without degradation

---

## 🚀 Deployment Checklist

### Before Implementation
- [ ] Get maintainer approval on roadmap
- [ ] Create GitHub issues for each phase
- [ ] Set up project board for tracking
- [ ] Assign phases to sprints

### Before Each Phase
- [ ] Review phase documentation
- [ ] Check dependencies are met
- [ ] Allocate time for testing

### After Each Phase
- [ ] Update progress in PR
- [ ] Run tests
- [ ] Update documentation if needed
- [ ] Get code review

---

## 📚 Reference Links

### Documentation
- [Full Roadmap](docs/development-roadmap.md)
- [Quick Reference](docs/gridstack-page-builder-quick-ref.md)
- [Architecture Guide](docs/architecture.md)

### External Resources
- [GridStack.js Documentation](https://gridstackjs.com/)
- [HTMX Documentation](https://htmx.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## ❓ Open Questions

### Technical Decisions
1. **Grid Configuration**: Fixed 12-column vs dynamic?
   - **Recommendation**: Start with fixed 12-column, make configurable later

2. **Widget Storage**: DB vs JSON files?
   - **Recommendation**: DB for instances, JSON/code for definitions

3. **Live Updates**: Polling interval defaults?
   - **Recommendation**: Downloads 3s, Now Playing 5s, Health 15s

4. **Template Format**: Single template vs component-based?
   - **Recommendation**: Single template per widget type initially

5. **Caching Strategy**: Redis or in-memory?
   - **Recommendation**: In-memory for MVP, Redis for Phase P11

### Product Decisions
1. Should users share pages with each other?
   - **Phase F**: Optional feature, not MVP

2. Should there be a widget marketplace?
   - **Phase 9**: Plugin system planning

3. Maximum widgets per page?
   - **Recommendation**: Soft limit 50, hard limit 100

---

## 🎯 Success Metrics

### User-Facing
- Users can create a functional page in < 5 minutes
- No data loss on save operations
- Intuitive drag & drop experience
- Clear visual feedback on all actions

### Technical
- All API endpoints respond within targets
- Zero critical security vulnerabilities
- Test coverage > 80%
- No memory leaks in long-running sessions

---

## 🐛 Known Considerations

### GridStack + HTMX Integration
- HTMX may re-render DOM, breaking GridStack state
- **Solution**: Re-initialize GridStack after HTMX swaps
- **Reference**: P1 documentation

### Concurrent Updates
- Multiple users editing same page simultaneously
- **Solution**: Last-write-wins for MVP, CRDT for later

### Mobile Support
- GridStack drag & drop may not work well on mobile
- **Solution**: P1 tests tablet, full mobile support later

---

## 📝 Next Immediate Actions

1. **Get Maintainer Review**
   - Share roadmap documentation
   - Discuss timeline and priorities
   - Clarify any ambiguities

2. **Create GitHub Issues**
   - One issue per phase (P1-P11, L1-L4)
   - Use issue templates
   - Add labels: `v2.0`, `feature`, `page-builder`

3. **Design Phase**
   - Create wireframes
   - Design database schema
   - Draft API contracts
   - Plan component structure

4. **Sprint Planning**
   - Define Sprint 1: P1-P3 (Foundation)
   - Assign tasks
   - Set up development environment

---

**Last Updated:** 2025-11-11  
**Status:** Ready for implementation planning  
**Questions?** Open an issue or discussion on GitHub
