# Dashboard Widget System - Developer Quick Start

> **For:** Developers who want to understand, modify, or extend the dashboard widget system  
> **Version:** v2.0  
> **Last Updated:** 2025-11-17

---

## 📚 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Creating a New Widget](#creating-a-new-widget)
4. [Working with Templates](#working-with-templates)
5. [HTMX Patterns](#htmx-patterns)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### The Big Picture

```
┌─────────────────────────────────────────────────────┐
│                   Dashboard Page                     │
│  ┌───────────────────────────────────────────────┐  │
│  │             Widget Canvas (CSS Grid)           │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐   │  │
│  │  │ Widget 1 │  │ Widget 2 │  │ Widget 3 │   │  │
│  │  │  (6 col) │  │  (6 col) │  │  (4 col) │   │  │
│  │  └──────────┘  └──────────┘  └──────────┘   │  │
│  │  ┌────────────────────────────┐              │  │
│  │  │       Widget 4 (12 col)    │              │  │
│  │  └────────────────────────────┘              │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Tech Stack

- **Backend:** FastAPI + Jinja2
- **Frontend:** HTMX + Vanilla JS (minimal)
- **Styling:** TailwindCSS + Custom CSS Grid
- **Database:** SQLAlchemy (async) + Alembic migrations
- **Grid System:** 12 columns (responsive: 1/8/12)

### Data Flow

```
User Action (Button Click)
    ↓
HTMX Request (hx-post="/api/ui/widgets/instances/{id}/move-up")
    ↓
FastAPI Endpoint (dashboard.py)
    ↓
Domain Logic (WidgetInstance.move_up())
    ↓
Repository Save (WidgetInstanceRepository.update())
    ↓
Database Update (SQLAlchemy)
    ↓
Return HTML Fragment (widget_canvas.html)
    ↓
HTMX Swap (innerHTML of #widget-canvas)
    ↓
Updated UI (user sees widget moved)
```

---

## Quick Start

### 1. Repository Structure

```
src/soulspot/
├── api/routers/
│   ├── dashboard.py      # Dashboard page & canvas endpoints
│   └── widgets.py        # Widget content endpoints
├── domain/entities/
│   └── widget.py         # Widget, Page, WidgetInstance entities
├── infrastructure/persistence/repositories/
│   └── widget_*.py       # Widget repositories
├── templates/
│   ├── dashboard.html    # Main dashboard page
│   ├── partials/
│   │   ├── widget_canvas.html        # Canvas with all widgets
│   │   ├── widget_catalog_modal.html # Add widget modal
│   │   ├── widget_config_modal.html  # Configure widget modal
│   │   └── widgets/
│   │       ├── active_jobs.html
│   │       ├── spotify_search.html
│   │       ├── missing_tracks.html
│   │       ├── quick_actions.html
│   │       └── metadata_manager.html
│   └── includes/
└── static/
    └── dashboard.css     # Widget grid system & styles
```

### 2. Database Schema

```sql
-- Widget types registry
CREATE TABLE widgets (
    id INTEGER PRIMARY KEY,
    type VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    template_path VARCHAR(200) NOT NULL,
    default_config JSON
);

-- Dashboard pages
CREATE TABLE pages (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_default BOOLEAN DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- Widget instances (placed on pages)
CREATE TABLE widget_instances (
    id INTEGER PRIMARY KEY,
    page_id INTEGER NOT NULL,
    widget_type VARCHAR(50) NOT NULL,
    position_row INTEGER DEFAULT 0,
    position_col INTEGER DEFAULT 0,
    span_cols INTEGER DEFAULT 6,
    config JSON,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE,
    FOREIGN KEY (widget_type) REFERENCES widgets(type) ON DELETE CASCADE,
    UNIQUE (page_id, position_row, position_col)
);
```

### 3. Key Concepts

**Widget Type vs Widget Instance**
- **Widget Type:** Definition in `widgets` table (e.g., "active_jobs")
- **Widget Instance:** Specific placement on a page (e.g., "active_jobs at row 0, col 0, 6 columns wide")

**Page Management**
- Users can have multiple pages (e.g., "My Dashboard", "Downloads", "Library")
- One page is marked as default
- Widgets are scoped to a page

**Grid System**
- 12 columns on desktop
- 8 columns on tablet
- 1 column on mobile
- Widgets span 4, 6, or 12 columns

---

## Creating a New Widget

### Step 1: Add Widget Type to Database

Edit migration file or run SQL:

```python
# In alembic migration
op.execute("""
    INSERT INTO widgets (type, name, template_path, default_config) VALUES
    ('my_widget', 'My Widget', 'partials/widgets/my_widget.html', '{"refresh": 10}')
""")
```

### Step 2: Create Widget Template

Create `src/soulspot/templates/partials/widgets/my_widget.html`:

```html
{# My Widget - Shows something useful #}
<div class="widget-content">
  <div class="widget-header">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white">My Widget</h3>
    <span class="text-sm text-gray-500 dark:text-gray-400">{{ count|default(0) }} items</span>
  </div>
  
  <div class="widget-body mt-4">
    {% if items and items|length > 0 %}
      <div class="space-y-2">
        {% for item in items %}
          <div class="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <p class="text-sm text-gray-900 dark:text-white">{{ item.title }}</p>
          </div>
        {% endfor %}
      </div>
    {% else %}
      <div class="text-center py-8 text-gray-500 dark:text-gray-400">
        <svg class="mx-auto h-12 w-12 text-gray-400 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
        <p class="mt-2 text-sm">No items to display</p>
      </div>
    {% endif %}
  </div>
</div>
```

### Step 3: Create Content Endpoint

Add to `src/soulspot/api/routers/widgets.py`:

```python
@router.get("/my-widget/content", response_class=HTMLResponse)
async def my_widget_content(
    request: Request,
    # Add any dependencies you need
) -> Any:
    """Get my widget content."""
    # Fetch data from your services/repositories
    items = []  # Your data here
    
    return templates.TemplateResponse(
        "partials/widgets/my_widget.html",
        {
            "request": request,
            "items": items,
            "count": len(items),
        },
    )
```

### Step 4: Add Configuration (Optional)

If your widget needs configuration, add to `widget_config_modal.html`:

```html
{% elif widget.type == 'my_widget' %}
  <div>
    <label for="refresh" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
      Refresh Interval (seconds)
    </label>
    <input type="number" 
           id="refresh"
           name="refresh" 
           value="{{ instance.config.refresh if instance.config else 10 }}"
           min="1"
           max="60"
           aria-describedby="refresh_help"
           class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg">
    <p id="refresh_help" class="mt-1 text-xs text-gray-500 dark:text-gray-400">
      How often to refresh the widget data
    </p>
  </div>
{% endif %}
```

### Step 5: Add to Catalog

Update `widget_catalog_modal.html` to include your widget's icon and description:

```html
{% elif widget.type == 'my_widget' %}
  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <!-- Your icon SVG path here -->
  </svg>
{% endif %}
```

### Step 6: Test

```bash
# Run migration
alembic upgrade head

# Start server
uvicorn soulspot.main:app --reload

# Navigate to dashboard and add your widget
open http://localhost:8000/dashboard
```

---

## Working with Templates

### Template Structure

All widget templates follow this pattern:

```html
{# Widget Name - Description #}
<div class="widget-content" 
     {% if needs_polling %}
     hx-get="/api/ui/widgets/my-widget/content"
     hx-trigger="load, every 5s"
     hx-swap="innerHTML"
     {% endif %}>
  
  {# Header with title and optional metadata #}
  <div class="widget-header">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Title</h3>
    <span class="text-sm text-gray-500 dark:text-gray-400">Metadata</span>
  </div>
  
  {# Body with content or empty state #}
  <div class="widget-body mt-4">
    {% if has_content %}
      <!-- Your content here -->
    {% else %}
      <!-- Empty state -->
    {% endif %}
  </div>
</div>
```

### Common Jinja2 Patterns

```html
{# Conditional rendering #}
{% if condition %}
  <p>Content</p>
{% else %}
  <p>Alternative</p>
{% endif %}

{# Loops #}
{% for item in items %}
  <div>{{ item.name }}</div>
{% endfor %}

{# Filters #}
{{ value|default('N/A') }}
{{ text|title }}
{{ count|round(2) }}

{# Limited lists #}
{% for item in items[:5] %}  {# Only first 5 #}

{# Length check #}
{% if items|length > 5 %}
  <a href="/view-all">View all {{ items|length }} items</a>
{% endif %}
```

### Accessibility in Templates

```html
{# Always include ARIA labels #}
<button aria-label="Remove widget" title="Remove">
  ✕
</button>

{# Use semantic HTML #}
<button> not <div onclick="">

{# Include screen reader text #}
<span class="sr-only">Loading...</span>

{# Proper form labels #}
<label for="input-id">Label Text</label>
<input id="input-id" name="field_name">

{# ARIA live regions for dynamic updates #}
<div role="status" aria-live="polite">
  Status message
</div>
```

---

## HTMX Patterns

### Pattern 1: Simple Content Replacement

```html
<button hx-get="/api/endpoint"
        hx-target="#target-id"
        hx-swap="innerHTML">
  Load Content
</button>

<div id="target-id">
  <!-- Content will be loaded here -->
</div>
```

### Pattern 2: Form Submission

```html
<form hx-post="/api/endpoint"
      hx-target="#result"
      hx-swap="innerHTML">
  <input name="field" type="text">
  <button type="submit">Submit</button>
</form>

<div id="result"></div>
```

### Pattern 3: Polling (Auto-refresh)

```html
<div hx-get="/api/endpoint"
     hx-trigger="load, every 5s"
     hx-swap="innerHTML">
  <!-- Content refreshes every 5 seconds -->
</div>
```

### Pattern 4: Debounced Input

```html
<input type="text"
       hx-get="/api/search"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#results">
```

### Pattern 5: Confirmation

```html
<button hx-delete="/api/resource/123"
        hx-confirm="Are you sure?"
        hx-target="#item-123"
        hx-swap="outerHTML swap:300ms">
  Delete
</button>
```

### Pattern 6: Loading Indicator

```html
<button hx-post="/api/action"
        hx-indicator="#spinner">
  Do Action
  <span id="spinner" class="htmx-indicator">
    <svg class="animate-spin">...</svg>
  </span>
</button>
```

### Pattern 7: Modal Loading

```html
<button hx-get="/api/modal"
        hx-target="#modal-container"
        hx-swap="innerHTML">
  Open Modal
</button>

<div id="modal-container"></div>
```

### HTMX Events

```javascript
// Listen for HTMX events
document.body.addEventListener('htmx:afterSwap', function(event) {
  console.log('Content swapped', event.detail);
  // Do something after swap (e.g., focus management)
});

document.body.addEventListener('htmx:responseError', function(event) {
  console.error('HTMX error', event.detail);
  // Show error message
});
```

---

## Testing

### Unit Tests (Domain Logic)

```python
def test_widget_instance_move_up():
    """Test moving widget up."""
    instance = WidgetInstance(
        id=1,
        page_id=1,
        widget_type="test",
        position_row=1,
        position_col=0,
        span_cols=6
    )
    
    instance.move_up()
    
    assert instance.position_row == 0
```

### Integration Tests (API)

```python
@pytest.mark.asyncio
async def test_add_widget():
    """Test adding a widget to dashboard."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/ui/widgets/instances",
            data={
                "page_id": "1",
                "widget_type": "active_jobs"
            }
        )
        assert response.status_code in [200, 201]
```

### Manual Testing Checklist

```
Dashboard Page
□ Page loads without errors
□ Widget canvas renders
□ Edit mode toggle works
□ Add widget button appears in edit mode

Widget Operations
□ Can add widget from catalog
□ Widget appears in correct position
□ Can move widget up/down/left/right
□ Can resize widget (4/6/12 columns)
□ Can configure widget
□ Configuration saves correctly
□ Can remove widget
□ Confirmation dialog appears

Keyboard Navigation
□ Can Tab through all controls
□ Enter/Space activates buttons
□ Ctrl+E toggles edit mode
□ Ctrl+A opens add widget (edit mode)
□ Ctrl+P toggles page switcher
□ Ctrl+? opens shortcuts modal
□ Esc closes modals

Accessibility
□ Screen reader announces widgets
□ ARIA labels are descriptive
□ Focus is visible
□ Focus management after HTMX swaps
□ Color contrast is sufficient

Responsive Design
□ Mobile layout (1 column)
□ Tablet layout (8 columns)
□ Desktop layout (12 columns)
□ No horizontal scroll
□ Touch-friendly on mobile

Dark Mode
□ All widgets support dark mode
□ Proper contrast in dark mode
□ Modals work in dark mode
```

---

## Troubleshooting

### Problem: Widget doesn't appear after adding

**Check:**
1. Widget type exists in database (`SELECT * FROM widgets WHERE type='...'`)
2. Template file exists at correct path
3. Content endpoint returns 200 OK
4. HTMX request succeeds (check Network tab)
5. No JavaScript errors (check Console)

**Debug:**
```python
# Add logging to endpoint
import logging
logger = logging.getLogger(__name__)

@router.get("/my-widget/content")
async def my_widget_content(...):
    logger.info("Widget content requested")
    # Your code
    logger.info(f"Returning {len(items)} items")
    return response
```

### Problem: Widget layout breaks

**Check:**
1. CSS classes are correct (`widget-col-4`, not `widget-col-04`)
2. Span doesn't exceed 12 columns
3. Position doesn't push widget off grid
4. Browser console for CSS errors
5. Inspect element to see computed styles

**Fix:**
```python
# Ensure valid span
if self.position_col + self.span_cols > 12:
    raise ValueError("Widget extends beyond grid")
```

### Problem: HTMX request fails

**Check:**
1. Network tab shows request
2. Request URL is correct
3. Response status code
4. Response content type (should be HTML)
5. HTMX attributes are correct

**Debug:**
```html
<!-- Add debug attributes -->
<button hx-post="/api/endpoint"
        hx-target="#result"
        hx-swap="innerHTML"
        hx-on::before-request="console.log('Request starting')"
        hx-on::after-request="console.log('Request complete')">
  Action
</button>
```

### Problem: Focus management issues

**Check:**
1. HTMX `afterSwap` event listener is registered
2. Focus target element exists after swap
3. Element is focusable (`tabindex` if needed)
4. No JavaScript errors preventing focus

**Fix:**
```javascript
document.body.addEventListener('htmx:afterSwap', function(event) {
  if (event.detail.target.id === 'widget-canvas') {
    // Find first button in canvas
    const firstButton = event.detail.target.querySelector('button');
    if (firstButton) {
      setTimeout(() => firstButton.focus(), 100);
    }
  }
});
```

### Problem: Widget configuration doesn't save

**Check:**
1. Form fields have correct `name` attributes
2. POST endpoint receives data
3. Config is valid JSON
4. Database update succeeds
5. Response includes success message

**Debug:**
```python
@router.post("/widgets/instances/{instance_id}/config")
async def save_config(instance_id: int, request: Request, ...):
    form_data = await request.form()
    logger.info(f"Config data: {dict(form_data)}")
    
    # Validate config
    config = dict(form_data)
    logger.info(f"Parsed config: {config}")
    
    instance.update_config(config)
    # ...
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Widget not found | Type mismatch | Check widget type string exactly matches |
| Grid overflow | Span too large | Validate span + position ≤ 12 |
| Dark mode broken | Missing dark: classes | Add `dark:` prefix to color classes |
| Focus lost | No focus management | Add focus() after swap |
| Keyboard shortcut conflicts | Browser defaults | Use Ctrl/Cmd + custom key |
| Mobile layout broken | Fixed widths | Use responsive classes (w-full, etc.) |
| HTMX not working | Script not loaded | Check script tag in base.html |
| Polling too frequent | Low interval | Increase to 5s+ for non-critical |

---

## Resources

### Documentation
- [HTMX Docs](https://htmx.org/docs/)
- [TailwindCSS Docs](https://tailwindcss.com/docs)
- [Jinja2 Docs](https://jinja.palletsprojects.com/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

### Internal Docs
- [Frontend Roadmap](frontend-development-roadmap.md)
- [Implementation Summary](v2.0-dashboard-implementation-summary.md)
- [UI Design System](ui/README_UI_1_0.md)

### Tools
- **Browser DevTools** - Inspect, debug, test
- **HTMX Extension** - Browser extension for debugging
- **axe DevTools** - Accessibility testing
- **Lighthouse** - Performance and accessibility audit

---

## Quick Reference

### File Paths
```
Templates:     src/soulspot/templates/
Widgets:       src/soulspot/templates/partials/widgets/
API:           src/soulspot/api/routers/dashboard.py
Domain:        src/soulspot/domain/entities/widget.py
Repositories:  src/soulspot/infrastructure/persistence/repositories/
CSS:           src/soulspot/static/dashboard.css
Tests:         tests/integration/test_dashboard_widgets.py
```

### Common Commands
```bash
# Migrations
alembic upgrade head
alembic downgrade -1
alembic revision -m "description"

# Development
uvicorn soulspot.main:app --reload
pytest tests/integration/ -v
ruff check src/
mypy src/soulspot/

# Testing
pytest tests/integration/test_dashboard_widgets.py -v -k test_name
pytest --cov=src/soulspot --cov-report=html
```

### CSS Classes
```css
/* Widget grid */
.widget-canvas          /* Grid container */
.widget-card            /* Widget card */
.widget-col-4           /* 4 column span */
.widget-col-6           /* 6 column span (default) */
.widget-col-12          /* 12 column span (full width) */

/* Widget structure */
.widget-content         /* Widget content container */
.widget-header          /* Widget header */
.widget-body            /* Widget body */
.widget-controls        /* Edit mode controls */

/* States */
.edit-mode-active       /* Edit mode enabled */
.htmx-indicator         /* HTMX loading indicator */
.sr-only                /* Screen reader only */
```

---

**Need Help?**
- Check the [Implementation Summary](v2.0-dashboard-implementation-summary.md) for detailed architecture
- Review [test_dashboard_widgets.py](../tests/integration/test_dashboard_widgets.py) for examples
- Look at existing widgets for patterns
- Ask the team in #frontend-dev channel

**Last Updated:** 2025-11-17  
**Maintainer:** Frontend Team
