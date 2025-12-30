# UI Redesign Master Plan (Pro Edition)

**Category:** UI/UX Design / Implementation Plan  
**Status:** 🎯 Ready for Implementation  
**Last Updated:** 2025-12-30  
**Related:** [UI Architecture](./ui-architecture-principles.md), [Component Library](./component-library.md), [Accessibility Guide](./accessibility-guide.md)

---

## Executive Summary

### Vision

Transform SoulSpot's UI into a **professional, scalable, and intuitive system** balancing:
- **Premium aesthetics** (glassmorphism, dark mode)
- **Functional clarity** (MediaManager-inspired UX)
- **Enterprise-grade features** (Command Palette, advanced filtering)

### Constraints

- ❌ **No npm build steps** – Pure CSS-in-HTML, Bootstrap Icons, HTMX
- ✅ **Hexagonal Architecture** – Domain-driven design, port/repository sync
- ✅ **WCAG AA Compliance** – Light Mode support
- ✅ **Backwards Compatibility** – Legacy components coexist during migration

### Outcomes

- **4 Phases** delivered incrementally
- **50+ reusable Jinja2 components**
- **Pro Command Palette** (Cmd+K / Ctrl+K)
- **Mobile-first responsive** with bottom sheet modals
- **Light/Dark theme toggle**
- **Zero breaking changes**

## Phase 1: Foundation (CSS Design Tokens)

### Objective

Establish single source of truth for colors, spacing, typography, animations using CSS custom properties.

### Deliverables

**File:** `src/soulspot/static/css/variables.css`

```css
/* Design Tokens */
:root {
  /* Colors */
  --color-primary: #8b5cf6;
  --color-success: #10b981;
  --color-warning: #eab308;
  --color-error: #ef4444;
  
  /* Service Colors */
  --spotify-green: #1db954;
  --tidal-cyan: #00d9ff;
  --deezer-orange: #ff9900;
  
  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;
  
  /* Typography */
  --font-sans: system-ui, -apple-system, sans-serif;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  
  /* Breakpoints */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
}

/* Theme Toggle */
:root[data-theme="light"] {
  --bg-primary: #ffffff;
  --text-primary: #000000;
}

:root[data-theme="dark"] {
  --bg-primary: #1f2937;
  --text-primary: #f9fafb;
}
```

**File:** `src/soulspot/static/css/animations.css`

```css
/* Pure CSS animations (no build step) */
@keyframes shimmer {
  0% { background-position: -1000px 0; }
  100% { background-position: 1000px 0; }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { 
    opacity: 0;
    transform: translateY(20px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}

/* Utility classes */
.fade-in { animation: fadeIn 0.3s ease-out; }
.slide-up { animation: slideUp 0.4s ease-out; }
.shimmer { animation: shimmer 2s infinite; }
```

### Touch Target Sizing

```css
/* WCAG 2.5.5 AAA: Minimum 44×44px */
.btn, button, a, input[type="checkbox"] {
  min-width: 44px;
  min-height: 44px;
}

/* Recommended: 48×48px */
.btn-primary {
  min-width: 48px;
  min-height: 48px;
}

/* Mobile critical: 56×56px */
@media (max-width: 768px) {
  .btn-critical {
    min-width: 56px;
    min-height: 56px;
  }
}
```

## Phase 2: Core Components

### Layout Components

```jinja2
{# Page Header #}
{% macro page_header(title, subtitle=None, action_text=None) %}
<header class="page-header">
  <div>
    <h1>{{ title }}</h1>
    {% if subtitle %}<p>{{ subtitle }}</p>{% endif %}
  </div>
  {% if action_text %}
  <button class="btn btn-primary">{{ action_text }}</button>
  {% endif %}
</header>
{% endmacro %}

{# Media Grid #}
{% macro media_grid(columns=5, gap='md') %}
<div class="media-grid" style="--columns: {{ columns }}; --gap: var(--space-{{ gap }});">
  {{ caller() }}
</div>
{% endmacro %}
```

### Data Display Components

```jinja2
{# Media Card #}
{% macro media_card(title, subtitle, image, type='album', status=None) %}
<article class="media-card media-card-{{ type }}">
  <img src="{{ image }}" alt="{{ title }}" loading="lazy">
  {% if status %}
  <span class="badge badge-{{ status }}">{{ status }}</span>
  {% endif %}
  <h3>{{ title }}</h3>
  <p>{{ subtitle }}</p>
</article>
{% endmacro %}
```

### Forms & Inputs

```jinja2
{# Search Bar #}
{% macro search_bar(placeholder, action_url, debounce=300) %}
<form class="search-bar">
  <input 
    type="search" 
    name="q"
    placeholder="{{ placeholder }}"
    hx-get="{{ action_url }}"
    hx-trigger="keyup changed delay:{{ debounce }}ms"
    hx-target="#search-results">
</form>
{% endmacro %}
```

### Focus Trap (Accessibility)

```javascript
// Implemented in Phase 1 (see Accessibility Guide)
class FocusTrap {
  constructor(element) { ... }
  activate() { ... }
  deactivate() { ... }
}

// HTMX integration
document.addEventListener('htmx:afterSwap', (event) => {
  const modal = event.detail.target.querySelector('[role="dialog"]');
  if (modal) {
    const trap = new FocusTrap(modal);
    trap.activate();
  }
});
```

## Phase 3: Pro Features

### Command Palette (Cmd+K)

```html
<!-- Modal triggered by Cmd+K / Ctrl+K -->
<dialog id="command-palette" role="dialog" aria-labelledby="palette-title">
  <h2 id="palette-title" class="sr-only">Command Palette</h2>
  <input 
    type="search" 
    placeholder="Type a command or search..."
    hx-get="/api/search/commands"
    hx-trigger="keyup changed delay:100ms"
    hx-target="#command-results">
  <div id="command-results" role="listbox"></div>
</dialog>

<script>
// Keyboard shortcut
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    document.getElementById('command-palette').showModal();
  }
});
</script>
```

### Mobile Bottom Sheets

```css
/* Mobile-specific modal pattern */
@media (max-width: 768px) {
  .modal {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    border-radius: 16px 16px 0 0;
    transform: translateY(100%);
    transition: transform 0.3s ease-out;
  }
  
  .modal.open {
    transform: translateY(0);
  }
}
```

### Advanced Filtering

```jinja2
{# Filter Bar #}
{% macro filter_bar(filters) %}
<div class="filter-bar">
  {% for filter in filters %}
  <div class="filter-group">
    <label>{{ filter.label }}</label>
    {% if filter.type == 'select' %}
    <select name="{{ filter.name }}">
      {% for option in filter.options %}
      <option value="{{ option.value }}">{{ option.label }}</option>
      {% endfor %}
    </select>
    {% elif filter.type == 'search' %}
    <input type="search" name="{{ filter.name }}" placeholder="{{ filter.placeholder }}">
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endmacro %}
```

## Phase 4: Polish & Integration

### Animations

```css
/* Staggered card animations */
.media-card {
  animation: fadeIn 0.4s ease-out;
  animation-delay: calc(var(--index) * 0.05s);
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .media-card {
    animation: none;
  }
}
```

### Light Mode Toggle

```javascript
// Theme switcher
function toggleTheme() {
  const root = document.documentElement;
  const currentTheme = root.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  
  root.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
}

// Restore theme on page load
document.addEventListener('DOMContentLoaded', () => {
  const savedTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
});
```

### Quality Gates

```bash
# Run before PR (see Quality Gates doc)
./scripts/quality-gates-a11y.sh

# Expected output:
✓ Code Quality: PASS
✓ Unit Tests: PASS
✓ A11Y Scan: 0 violations
✓ HTML Validation: PASS
```

## Implementation Priority

| Phase | Estimated Effort | Critical Path |
|-------|------------------|---------------|
| **Phase 1** | 2-3 days | ✅ Foundation |
| **Phase 2** | 5-7 days | ✅ Components |
| **Phase 3** | 3-5 days | ⏳ Pro Features |
| **Phase 4** | 2-3 days | ⏳ Polish |

**Total:** 12-18 days

## Success Criteria

- [ ] All components use design tokens
- [ ] WCAG 2.1 AA compliance (axe-core 0 violations)
- [ ] Touch targets ≥44×44px
- [ ] Keyboard navigation works for all features
- [ ] Light/Dark theme toggle works
- [ ] Command Palette responds to Cmd+K
- [ ] Mobile bottom sheets on <768px
- [ ] Zero breaking changes to existing routes

## Related Documentation

- [UI Architecture](./ui-architecture-principles.md) - Design principles
- [Component Library](./component-library.md) - Component reference
- [Accessibility Guide](./accessibility-guide.md) - WCAG compliance
- [Quality Gates](./quality-gates-a11y.md) - Testing framework
- [Service-Agnostic Strategy](./service-agnostic-strategy.md) - Multi-service design
