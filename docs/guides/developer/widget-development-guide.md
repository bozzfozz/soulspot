# Custom Widget Development Guide

> **⚠️ DEPRECATED - December 2025**  
> **This widget system has been removed from SoulSpot.**  
> **The widget system was deprecated and removed via migration `ee19001hhj49_remove_widget_system.py`.**  
> **This documentation is kept for historical reference only.**

> **Version:** 1.0  
> **Last Updated:** 2025-11-17  
> **Audience:** Developers creating custom dashboard widgets

---

## 📖 Table of Contents

1. [Overview](#overview)
2. [Widget Template Structure](#widget-template-structure)
3. [Creating a Custom Widget](#creating-a-custom-widget)
4. [Configuration Schema](#configuration-schema)
5. [SSE Integration](#sse-integration)
6. [Testing Your Widget](#testing-your-widget)
7. [Best Practices](#best-practices)
8. [API Reference](#api-reference)
9. [Examples](#examples)

---

## Overview

The SoulSpot widget system allows developers to create custom dashboard widgets using a JSON-based template format. Widgets are automatically discovered at application startup and can be added to any dashboard page.

### Key Features

- **JSON-based templates**: Easy to create and maintain
- **Configuration schemas**: Define widget-specific settings
- **SSE support**: Real-time updates without polling
- **Category and tags**: Organize widgets for discovery
- **Automatic discovery**: Drop a JSON file and restart
- **Permission system**: Control access to sensitive widgets

### Architecture

```
Widget Template (JSON)
    ↓
Template Registry (Discovery & Validation)
    ↓
API Endpoints (Template CRUD)
    ↓
Dashboard UI (Widget Rendering)
```

---

## Widget Template Structure

A widget template is a JSON file with the following structure:

```json
{
  "id": "unique_widget_id",
  "type": "widget_type",
  "is_enabled": true,
  "is_system": false,
  "config": {
    "name": "Widget Display Name",
    "description": "Brief description of what the widget does",
    "version": "1.0.0",
    "author": "Your Name or Organization",
    "template_path": "partials/widgets/your_widget.html",
    "icon": "icon-name",
    "category": "monitoring|search|utility|management|general",
    "supports_config": true,
    "config_schema": { /* JSON Schema for configuration */ },
    "default_config": { /* Default configuration values */ },
    "default_span_cols": 6,
    "min_span_cols": 4,
    "max_span_cols": 12,
    "data_endpoint": "/api/ui/widgets/your-widget/content",
    "supports_sse": false,
    "sse_events": [],
    "poll_interval": 5,
    "requires_auth": false,
    "permissions": [],
    "tags": ["tag1", "tag2"]
  }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier for the widget |
| `type` | string | Yes | Widget type (usually same as id) |
| `is_enabled` | boolean | No | Whether widget is active (default: true) |
| `is_system` | boolean | No | System widgets cannot be unregistered (default: false) |
| `config.name` | string | Yes | Display name shown in widget catalog |
| `config.description` | string | Yes | Brief description for users |
| `config.version` | string | No | Semantic version (default: "1.0.0") |
| `config.author` | string | No | Author name or organization |
| `config.template_path` | string | Yes | Path to Jinja2 template relative to templates/ |
| `config.icon` | string | No | Icon name from icon set (default: "puzzle") |
| `config.category` | string | No | Widget category (default: "general") |
| `config.supports_config` | boolean | No | Whether widget has configuration (default: false) |
| `config.config_schema` | object | No | JSON Schema for widget configuration |
| `config.default_config` | object | No | Default configuration values |
| `config.default_span_cols` | number | No | Default width in columns 1-12 (default: 6) |
| `config.min_span_cols` | number | No | Minimum width (default: 4) |
| `config.max_span_cols` | number | No | Maximum width (default: 12) |
| `config.data_endpoint` | string | No | API endpoint for widget data |
| `config.supports_sse` | boolean | No | Whether widget supports SSE (default: false) |
| `config.sse_events` | array | No | List of SSE event types to subscribe to |
| `config.poll_interval` | number | No | Polling interval in seconds, 0 to disable (default: 5) |
| `config.requires_auth` | boolean | No | Whether widget requires authentication (default: false) |
| `config.permissions` | array | No | List of required permissions |
| `config.tags` | array | No | Tags for search and filtering |

---

## Creating a Custom Widget

### Step 1: Create Widget Template JSON

Create a file in `src/soulspot/templates/widget_templates/my_widget.json`:

```json
{
  "id": "my_custom_widget",
  "type": "my_custom_widget",
  "is_enabled": true,
  "is_system": false,
  "config": {
    "name": "My Custom Widget",
    "description": "A custom widget that does something awesome",
    "version": "1.0.0",
    "author": "My Name",
    "template_path": "partials/widgets/my_custom_widget.html",
    "icon": "star",
    "category": "utility",
    "default_span_cols": 6,
    "data_endpoint": "/api/ui/widgets/my-custom-widget/content",
    "poll_interval": 10,
    "tags": ["custom", "utility"]
  }
}
```

### Step 2: Create Widget Template HTML

Create `src/soulspot/templates/partials/widgets/my_custom_widget.html`:

```html
{# My Custom Widget #}
<div class="widget-content">
  <div class="widget-header">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
      {{ widget.config.name }}
    </h3>
  </div>
  
  <div class="widget-body mt-4">
    <!-- Your widget content here -->
    <p class="text-sm text-gray-600 dark:text-gray-400">
      {{ message|default("Hello from custom widget!") }}
    </p>
  </div>
</div>
```

### Step 3: Create Data Endpoint (Optional)

If your widget needs dynamic data, create an endpoint in your API router:

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="src/soulspot/templates")

@router.get("/my-custom-widget/content", response_class=HTMLResponse)
async def my_widget_content(request: Request) -> Any:
    """Get custom widget content."""
    return templates.TemplateResponse(
        "partials/widgets/my_custom_widget.html",
        {
            "request": request,
            "message": "Dynamic content from API!",
        },
    )
```

### Step 4: Discover and Test

1. Restart the application
2. Call the discover endpoint: `POST /api/widgets/templates/discover`
3. Verify your widget appears: `GET /api/widgets/templates`
4. Add it to a dashboard page through the UI

---

## Configuration Schema

Widgets can define configuration options using JSON Schema:

```json
{
  "config": {
    "supports_config": true,
    "config_schema": {
      "refresh_interval": {
        "type": "number",
        "min": 5,
        "max": 300,
        "default": 30,
        "description": "Refresh interval in seconds"
      },
      "show_details": {
        "type": "boolean",
        "default": true,
        "description": "Show detailed information"
      },
      "display_mode": {
        "type": "select",
        "options": ["compact", "normal", "detailed"],
        "default": "normal",
        "description": "Display mode"
      }
    },
    "default_config": {
      "refresh_interval": 30,
      "show_details": true,
      "display_mode": "normal"
    }
  }
}
```

### Accessing Configuration in Templates

```html
{% if config.show_details %}
  <div class="details">
    <!-- Detailed view -->
  </div>
{% endif %}

<p>Refresh: {{ config.refresh_interval }}s</p>
```

---

## SSE Integration

For real-time updates, enable SSE support:

### 1. Configure SSE in Template

```json
{
  "config": {
    "supports_sse": true,
    "sse_events": ["downloads_update", "custom_event"],
    "poll_interval": 0
  }
}
```

### 2. Add SSE JavaScript to Widget Template

```html
<div id="my-widget-{{ instance_id }}" data-sse-enabled="true">
  <!-- Widget content -->
</div>

<script>
(function() {
  const widgetId = '{{ instance_id }}';
  const widget = document.getElementById('my-widget-' + widgetId);
  
  if (typeof SSEClient === 'undefined') {
    console.error('SSEClient not loaded');
    return;
  }

  const sseClient = new SSEClient('/api/sse/stream', {
    debug: true,
    reconnectInterval: 3000
  });

  // Handle custom events
  sseClient.on('downloads_update', function(data) {
    console.log('Update received:', data);
    // Update widget DOM here
  });

  sseClient.connect();

  // Cleanup
  window.addEventListener('beforeunload', function() {
    sseClient.disconnect();
  });
})();
</script>
```

### 3. Emit Events from Backend

```python
# In your SSE event generator
yield SSEEvent(
    data={
        "widget_type": "my_custom_widget",
        "data": {"value": 42}
    },
    event="custom_event",
).encode()
```

---

## Testing Your Widget

### 1. Template Validation Test

```python
def test_custom_widget_template():
    from pathlib import Path
    from soulspot.domain.entities.widget_template import WidgetTemplate
    
    template_file = Path("src/soulspot/templates/widget_templates/my_widget.json")
    template = WidgetTemplate.from_file(template_file)
    
    assert template.id == "my_custom_widget"
    assert template.config.name == "My Custom Widget"
    errors = template.config.validate()
    assert len(errors) == 0
```

### 2. Registry Test

```python
def test_widget_in_registry():
    from soulspot.application.services.widget_template_registry import (
        get_widget_template_registry
    )
    
    registry = get_widget_template_registry()
    registry.discover_templates()
    
    widget = registry.get("my_custom_widget")
    assert widget is not None
    assert widget.is_enabled
```

### 3. API Endpoint Test

```python
@pytest.mark.asyncio
async def test_widget_endpoint():
    from httpx import AsyncClient, ASGITransport
    from soulspot.main import app
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/widgets/templates/my_custom_widget")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "my_custom_widget"
```

---

## Best Practices

### Performance

1. **Use SSE for frequent updates** (< 5 seconds)
2. **Set poll_interval to 0** for static widgets
3. **Limit data payload** size in API responses
4. **Use lazy loading** for heavy content
5. **Cache results** when appropriate

### Security

1. **Set `requires_auth: true`** for sensitive data
2. **Define `permissions`** array for access control
3. **Validate all inputs** in data endpoints
4. **Escape HTML** in templates
5. **Use CSRF tokens** for state-changing actions

### Usability

1. **Choose appropriate `default_span_cols`** (6 for standard, 4 for compact)
2. **Set reasonable `min/max_span_cols`** constraints
3. **Provide clear `description`** in template
4. **Use meaningful `tags`** for discoverability
5. **Handle empty/error states** gracefully

### Maintenance

1. **Version your widgets** using semantic versioning
2. **Document configuration** options clearly
3. **Test on multiple screen sizes**
4. **Provide example configurations**
5. **Keep templates simple** and focused

---

## API Reference

### Widget Template Registry

```python
from soulspot.application.services.widget_template_registry import (
    get_widget_template_registry
)

registry = get_widget_template_registry()

# Get all templates
templates = registry.get_all(enabled_only=True)

# Get by ID
widget = registry.get("widget_id")

# Search
results = registry.search(
    query="search term",
    category="monitoring",
    tags=["real-time"]
)

# Discover from file system
count = registry.discover_templates()
```

### REST API Endpoints

```bash
# List all templates
GET /api/widgets/templates

# Get specific template
GET /api/widgets/templates/{id}

# Filter by category
GET /api/widgets/templates/category/monitoring

# Search
POST /api/widgets/templates/search
{
  "query": "search",
  "category": "utility",
  "tags": ["custom"]
}

# Discover custom templates
POST /api/widgets/templates/discover

# List categories
GET /api/widgets/templates/categories/list

# List tags
GET /api/widgets/templates/tags/list
```

---

## Examples

### Example 1: Simple Static Widget

```json
{
  "id": "welcome_widget",
  "type": "welcome_widget",
  "config": {
    "name": "Welcome",
    "description": "Display a welcome message",
    "template_path": "partials/widgets/welcome.html",
    "category": "general",
    "default_span_cols": 12,
    "poll_interval": 0,
    "tags": ["static", "informational"]
  }
}
```

### Example 2: Configurable Widget

```json
{
  "id": "clock_widget",
  "type": "clock_widget",
  "config": {
    "name": "Clock",
    "description": "Display current time",
    "template_path": "partials/widgets/clock.html",
    "category": "utility",
    "supports_config": true,
    "config_schema": {
      "format": {
        "type": "select",
        "options": ["12h", "24h"],
        "default": "12h"
      },
      "show_seconds": {
        "type": "boolean",
        "default": true
      }
    },
    "default_config": {
      "format": "12h",
      "show_seconds": true
    },
    "default_span_cols": 4,
    "poll_interval": 1,
    "tags": ["time", "utility"]
  }
}
```

### Example 3: SSE-Enabled Real-Time Widget

```json
{
  "id": "live_stats",
  "type": "live_stats",
  "config": {
    "name": "Live Statistics",
    "description": "Real-time system statistics",
    "template_path": "partials/widgets/live_stats.html",
    "category": "monitoring",
    "default_span_cols": 6,
    "data_endpoint": "/api/ui/widgets/live-stats/content",
    "supports_sse": true,
    "sse_events": ["stats_update"],
    "poll_interval": 0,
    "tags": ["real-time", "monitoring", "statistics"]
  }
}
```

---

## Support

For questions or issues:

1. Check the [Widget Template System Documentation](../architecture.md#widget-system)
2. Review existing system widgets in `src/soulspot/application/services/widget_template_registry.py`
3. Open an issue on GitHub with the `widget-system` label

---

**Last Updated:** 2025-11-17  
**Version:** 1.0  
**Maintained by:** SoulSpot Team
