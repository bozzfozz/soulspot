# Dashboard Implementation Guide

> **Version:** 1.0  
> **Status:** Production Ready  
> **Last Updated:** 2025-11-17

---

## Overview

This document describes the complete dashboard implementation for SoulSpot version 1.0, including the dynamic widget system, HTMX integration, and customizable page builder functionality.

---

## Architecture

The dashboard system consists of several key components:

### 1. Database Schema

**Widgets Table** - Widget type registry
- Stores metadata for all available widget types
- Includes type, name, description, template path, and default configuration
- Seeded with 5 core widgets

**Pages Table** - Dashboard pages
- User-customizable dashboard layouts
- Supports default page designation
- Includes slug validation and metadata

**Widget Instances Table** - Placed widgets
- Links widgets to specific pages
- Stores position (x, y coordinates)
- Stores size (width, height in 12-column grid)
- Includes widget-specific configuration

### 2. Domain Layer

**Widget Entity**
- Type, name, description validation
- Template path management
- Default configuration handling

**Page Entity**
- Default page business logic
- Slug validation
- Metadata management

**WidgetInstance Entity**
- 12-column grid positioning
- Movement and resize logic
- Configuration management

### 3. API Layer

All dashboard endpoints return HTML fragments for HTMX consumption:

**Dashboard Endpoints**
- `GET /dashboard` - Main dashboard page rendering
- `GET /api/ui/dashboard/canvas` - Widget canvas generation
- `GET /api/ui/dashboard/catalog` - Widget catalog modal
- `GET /api/ui/dashboard/widget/{id}/config` - Widget configuration modal

**Widget Instance Endpoints**
- `POST /api/ui/dashboard/widgets` - Create widget instance
- `PATCH /api/ui/dashboard/widgets/{id}` - Update widget (move/resize)
- `DELETE /api/ui/dashboard/widgets/{id}` - Remove widget

**Widget Content Endpoints** (`/api/ui/widgets/`)
- `active-jobs/content` - Active download jobs with real-time updates
- `spotify-search/content` - Spotify track search interface
- `missing-tracks/content` - Missing tracks from playlists
- `quick-actions/content` - Configurable quick action buttons
- `metadata-manager/content` - Metadata issues and fixes

### 4. Repository Layer

**WidgetRepository**
- Widget type CRUD operations
- Widget registry management

**PageRepository**
- Dashboard page CRUD
- Default page queries

**WidgetInstanceRepository**
- Widget instance CRUD
- Position and size management
- Configuration updates

---

## Widget System

### Core Widgets

1. **Active Jobs Widget**
   - Displays active download jobs with progress bars
   - Auto-refreshes every 5 seconds via HTMX polling
   - Shows job status and control buttons
   - Real-time updates without page reload

2. **Spotify Search Widget**
   - Search interface for Spotify tracks
   - Direct download integration
   - Quick add to playlists

3. **Missing Tracks Widget**
   - Shows missing tracks from selected playlist
   - Playlist selection dropdown
   - Bulk download functionality

4. **Quick Actions Widget**
   - Configurable button grid
   - Fast access to common actions
   - Customizable per user

5. **Metadata Manager Widget**
   - Displays metadata issues
   - Quick-fix capabilities
   - Batch operations support

### Widget Templates

All widgets use Jinja2 templates located in:
```
src/soulspot/templates/partials/widgets/
├── active_jobs.html
├── active_jobs_sse.html (SSE-enabled version)
├── spotify_search.html
├── missing_tracks.html
├── quick_actions.html
└── metadata_manager.html
```

### Widget Template System

**WidgetTemplate Entity**
- JSON-based extensibility framework
- Template file format with comprehensive metadata
- Support for widget-specific configuration schemas
- Size constraints (4-12 column spans)
- Category and tag-based organization

> **⚠️ DEPRECATED:** The widget system has been removed (migration `ee19001hhj49_remove_widget_system.py`).

**WidgetTemplateRegistry Service** ~~(REMOVED)~~
- ~~Centralized template management~~
- ~~In-memory caching~~
- ~~Automatic discovery from `widget_templates/` directory~~
- ~~Pre-registration of system widgets~~

---

## HTMX Integration

The dashboard uses several HTMX patterns for interactivity:

### Lazy Loading
Widgets load content on demand:
```html
<div hx-get="/api/ui/widgets/active-jobs/content" 
     hx-trigger="load"
     hx-target="this"
     hx-swap="innerHTML">
  Loading...
</div>
```

### Polling
Active Jobs widget polls for updates:
```html
<div hx-get="/api/ui/widgets/active-jobs/content"
     hx-trigger="every 5s"
     hx-swap="innerHTML">
  <!-- content -->
</div>
```

### Server-Sent Events (SSE)
Real-time updates using SSE:
- Endpoint: `/api/sse/stream`
- Event types: `connected`, `downloads_update`, `heartbeat`, `error`
- Connection health monitoring with 30-second heartbeat
- Automatic reconnection with exponential backoff
- Graceful degradation to polling if unavailable

**SSE JavaScript Client**
- `SSEClient` class with automatic reconnection
- Heartbeat timeout detection (60s default)
- Event listener management
- Connection status tracking

### Edit Mode
Users can customize their dashboard:
- Drag and drop widgets to reposition
- Resize widgets within 12-column grid
- Add widgets from catalog
- Configure widget settings
- Remove widgets

---

## Grid System

The dashboard uses a 12-column responsive grid:

**Column Spans**
- Minimum width: 4 columns (33%)
- Maximum width: 12 columns (100%)
- Common sizes: 4, 6, 8, 12 columns

**Position Coordinates**
- X: 0-11 (column position)
- Y: 0-∞ (row position)
- Height: Number of rows occupied

**Responsive Breakpoints**
- Mobile: Stack widgets vertically
- Tablet: 2-column layout
- Desktop: Full 12-column layout

---

## Accessibility

The dashboard implementation includes:

**Keyboard Navigation**
- Tab through all interactive elements
- Arrow keys for widget selection in edit mode
- Enter/Space to activate buttons
- Escape to close modals

**Screen Reader Support**
- ARIA labels on all widgets
- ARIA live regions for dynamic updates
- Descriptive button labels
- Form field labels and hints

**Visual Accessibility**
- High contrast focus indicators
- Clear visual hierarchy
- Sufficient color contrast (WCAG AA)
- No reliance on color alone for information

---

## Reusable UI Components

The implementation includes 10 reusable Jinja2 macros in `_components.html`:

1. **Alert/Notification** - 4 types (success, info, warning, danger), dismissible
2. **Badge** - 5 types with pulse animation
3. **Button Group** - Flexible layouts
4. **Progress Bar** - With labels and colors
5. **Empty State** - With icon and action button
6. **Status Indicator** - 7 states
7. **Priority Badge** - P0/P1/P2 levels
8. **Data Table** - With actions and sorting
9. **Form Field** - With validation states
10. **Pagination** - Accessible page navigation

---

## Performance Considerations

**Lazy Loading**
- Widgets load content only when visible
- Reduces initial page load time
- Improves perceived performance

**Efficient Polling**
- Only active widgets poll for updates
- Configurable polling intervals
- Automatic stop when widget hidden

**SSE for Real-Time Updates**
- More efficient than polling for live data
- Reduced server load
- Lower latency for updates

**Caching**
- Widget registry cached in memory
- Template caching via Jinja2
- Database query optimization

**Database Indexes**
- Indexes on widget_instances (page_id, position)
- Indexes on pages (user_id, is_default)
- Efficient queries for dashboard rendering

---

## Testing

### Unit Tests
- Widget entity validation
- Page business logic
- Repository operations
- Configuration validation

### Integration Tests
- API endpoint responses
- HTMX interactions
- Widget CRUD operations
- Grid positioning logic

### E2E Tests
- Dashboard rendering
- Widget drag and drop
- Widget resize operations
- Configuration updates

---

## Development Workflow

### Adding a New Widget

1. **Create Widget Template**
   ```html
   <!-- src/soulspot/templates/partials/widgets/my_widget.html -->
   <div class="widget-content">
     <!-- widget content -->
   </div>
   ```

2. **Create Content Endpoint**
   ```python
   @router.get("/my-widget/content")
   async def get_my_widget_content():
       return templates.TemplateResponse(
           "partials/widgets/my_widget.html",
           {"request": request}
       )
   ```

3. **Register Widget**
   Add to widget registry initialization:
   ```python
   Widget(
       type="my_widget",
       name="My Widget",
       description="Description",
       template_path="partials/widgets/my_widget.html",
       default_config={}
   )
   ```

4. **Add to Catalog**
   Widget automatically appears in catalog modal

### Customizing Widget Behavior

Widgets can be customized via configuration:
```json
{
  "refresh_interval": 5,
  "show_controls": true,
  "max_items": 10
}
```

Configuration is passed to template context and can control widget behavior.

---

## Future Enhancements

Potential improvements for future versions:

- **Widget Sharing** - Share custom layouts with other users
- **Widget Templates** - Pre-built layout templates
- **Advanced Filters** - More sophisticated data filtering in widgets
- **Custom Themes** - User-selectable color schemes
- **Widget Permissions** - Role-based widget access
- **Analytics Widgets** - Detailed usage statistics
- **External Data Sources** - Integration with external APIs
- **Mobile App** - Native mobile dashboard experience

---

## Related Documentation

- [Widget Development Guide](../guides/developer/widget-development-guide.md)
- [Dashboard Developer Guide](../guides/developer/dashboard-developer-guide.md)
- [HTMX Patterns](../guides/developer/htmx-patterns.md)
- [Component Library](../guides/developer/component-library.md)
- [User Guide](../guides/user/user-guide.md)

---

**Version 1.0** is complete and production-ready with all core dashboard functionality implemented.
