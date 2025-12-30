# UI Architecture Principles

**Category:** UI/UX Design  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [Component Library](./component-library.md), [Service-Agnostic Strategy](./service-agnostic-strategy.md), [Design Guidelines](../08-ui-components/design-guidelines.md)

---

## Overview

Core architectural principles for SoulSpot's UI redesign, focusing on extensibility, component reusability, and service-agnostic design patterns.

## Core Principles

### 1. Atomic Design System

Organize components in a hierarchical structure from smallest to largest:

```
Atoms (Smallest Units)
  ↓
Molecules (Combinations of Atoms)
  ↓
Organisms (Complex UI Components)
  ↓
Templates (Page Layouts)
  ↓
Pages (Concrete Instances)
```

**Benefits:**
- ✅ Consistent look & feel across entire application
- ✅ Easy to extend with new features
- ✅ Isolated testing for each level
- ✅ Single update propagates to all instances

#### Atoms

```jinja2
{# templates/components/atoms/button.html #}
{% macro button(text, variant='primary', icon=None, size='md', disabled=False) %}
<button class="btn btn-{{ variant }} btn-{{ size }}" 
        {% if disabled %}disabled{% endif %}
        aria-label="{{ text }}">
  {% if icon %}<i class="{{ icon }}"></i>{% endif %}
  {{ text }}
</button>
{% endmacro %}
```

#### Molecules

```jinja2
{# templates/components/molecules/search_bar.html #}
{% import "components/atoms/button.html" as btn %}
{% import "components/atoms/input.html" as inp %}

{% macro search_bar(placeholder, action_url) %}
<form class="search-bar" hx-get="{{ action_url }}" hx-trigger="keyup changed delay:300ms">
  {{ inp.input(type='search', placeholder=placeholder, icon='bi-search') }}
  {{ btn.button('Search', variant='primary', icon='bi-search') }}
</form>
{% endmacro %}
```

#### Organisms

```jinja2
{# templates/components/organisms/artist_card.html #}
{% macro artist_card(artist) %}
<article class="artist-card" data-artist-id="{{ artist.id }}">
  <img src="{{ artist.image }}" alt="{{ artist.name }}" class="artist-image">
  <h3>{{ artist.name }}</h3>
  <p class="text-muted">{{ artist.genre }}</p>
  <div class="action-menu">
    <button class="btn-icon" aria-label="Play">▶</button>
    <button class="btn-icon" aria-label="Follow">❤</button>
  </div>
</article>
{% endmacro %}
```

### 2. Service-Agnostic Components

**Problem:** Spotify-specific components don't work for Tidal/Deezer

**Solution:** Generic domain models + service adapters

```jinja2
{# Generic Artist Card - works for ALL services #}
{% macro artist_card(artist, service='generic') %}
<article class="artist-card" data-service="{{ service }}">
  <img src="{{ artist.image_url }}" alt="{{ artist.name }}">
  <h3>{{ artist.name }}</h3>
  
  {# Service-specific badge (5% custom logic) #}
  {% if service != 'generic' %}
  <span class="badge badge-{{ service }}">
    <i class="icon-{{ service }}"></i> {{ service|title }}
  </span>
  {% endif %}
  
  {# Generic actions (95% reuse) #}
  <div class="actions">
    <button hx-post="/api/artists/{{ artist.id }}/play">Play</button>
    <button hx-post="/api/artists/{{ artist.id }}/follow">Follow</button>
  </div>
</article>
{% endmacro %}
```

**Usage:**

```jinja2
{# Works for all services #}
{{ artist_card(spotify_artist, service='spotify') }}
{{ artist_card(tidal_artist, service='tidal') }}
{{ artist_card(local_artist, service='local') }}
```

**Extensibility:**

Adding new service (Deezer):
1. Add `badge-deezer` CSS class (5 min)
2. Add `icon-deezer` icon (2 min)
3. **Done!** Component works immediately

### 3. Plugin-Based Features

**Problem:** New features require core code changes

**Solution:** UI plugins as Jinja2 extensions

**Pattern:**

```python
# UI Plugin base class
class UIPlugin:
    """Base class for UI extensions"""
    
    def register_components(self, jinja_env):
        """Register custom Jinja2 components"""
        pass
    
    def register_routes(self, app):
        """Register custom routes"""
        pass
```

**Example Plugin:**

```python
class ArtistRecommendationsPlugin(UIPlugin):
    def register_components(self, jinja_env):
        jinja_env.globals['artist_recommendations_widget'] = self.render_widget
    
    def render_widget(self, artist_id):
        # Fetch recommendations
        # Render template
        return template.render()
```

### 4. HTMX-First Interactivity

**Principle:** Minimize JavaScript, use HTMX for dynamic updates

**Pattern:**

```html
<!-- Live search with debounce -->
<input 
  type="search" 
  name="q" 
  hx-get="/api/search/tracks"
  hx-trigger="keyup changed delay:300ms"
  hx-target="#search-results">

<div id="search-results">
  <!-- Results loaded here -->
</div>
```

**Benefits:**
- ✅ No JavaScript framework complexity
- ✅ Server-side rendering keeps logic in Python
- ✅ Progressive enhancement (works without JS)

### 5. Mobile-First Responsive

**Breakpoints:**

| Size | Width | Description |
|------|-------|-------------|
| `sm` | 640px | Mobile landscape |
| `md` | 768px | Tablet portrait |
| `lg` | 1024px | Tablet landscape |
| `xl` | 1280px | Desktop |
| `2xl` | 1536px | Large desktop |

**Grid Pattern:**

```css
.media-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr); /* Mobile: 2 columns */
  gap: 20px;
}

@media (min-width: 768px) {
  .media-grid {
    grid-template-columns: repeat(3, 1fr); /* Tablet: 3 columns */
  }
}

@media (min-width: 1024px) {
  .media-grid {
    grid-template-columns: repeat(5, 1fr); /* Desktop: 5 columns */
  }
}
```

### 6. Accessibility-First (WCAG 2.1 AA)

**Mandatory Patterns:**

| Requirement | Implementation |
|-------------|----------------|
| **Keyboard Navigation** | Tab/Shift+Tab for all interactive elements |
| **Focus Indicators** | Visible focus ring (2px solid, high contrast) |
| **ARIA Labels** | All buttons/icons have `aria-label` |
| **Semantic HTML** | Use `<button>`, `<nav>`, `<main>`, `<article>` |
| **Color Contrast** | 4.5:1 for text, 3:1 for UI components |
| **Touch Targets** | Minimum 44×44px (48×48px recommended) |

**Example:**

```html
<button 
  class="btn-icon" 
  aria-label="Play album Thriller">
  <i class="bi-play-fill" aria-hidden="true"></i>
</button>
```

### 7. Design Token System

**Single Source of Truth:** CSS custom properties

```css
:root {
  /* Colors */
  --color-primary: #8b5cf6;
  --color-success: #10b981;
  --color-warning: #eab308;
  --color-error: #ef4444;
  
  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;
  
  /* Typography */
  --font-sans: system-ui, -apple-system, sans-serif;
  --font-mono: 'Courier New', monospace;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
}
```

**Theme Toggle:**

```css
:root[data-theme="light"] {
  --bg-primary: #ffffff;
  --text-primary: #000000;
}

:root[data-theme="dark"] {
  --bg-primary: #1f2937;
  --text-primary: #f9fafb;
}
```

## Component Organization

```
templates/
├── components/
│   ├── atoms/          # Buttons, inputs, icons
│   ├── molecules/      # Search bars, cards, badges
│   ├── organisms/      # Artist cards, album grids, navigation
│   └── templates/      # Page layouts
├── includes/
│   ├── _components.html  # Component imports
│   └── macros.html       # Utility macros
└── pages/              # Concrete page instances
```

## Best Practices

### DO ✅

- Use generic domain models (Artist, Album, Track)
- Prefix service-specific code with service name (`spotify-auth.html`)
- Keep components small and focused (single responsibility)
- Use HTMX for dynamic updates instead of JavaScript
- Test components in isolation
- Provide ARIA labels for all interactive elements

### DON'T ❌

- Create service-specific components for generic features
- Mix presentation logic with business logic
- Use inline styles (use CSS classes with design tokens)
- Skip accessibility attributes
- Hardcode values (use design tokens)
- Create components without reusability in mind

## Related Documentation

- [Component Library](./component-library.md) - Complete component reference
- [Service-Agnostic Strategy](./service-agnostic-strategy.md) - Multi-service design
- [Accessibility Guide](./accessibility-guide.md) - WCAG 2.1 compliance
- [Design Guidelines](../08-ui-components/design-guidelines.md) - Visual design standards
