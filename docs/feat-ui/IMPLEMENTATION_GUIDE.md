# ⚠️ DEPRECATED - SoulSpot UI - Implementation Guide

## Document Information
- **Version**: 1.0 (DEPRECATED)
- **Last Updated**: 2025-11-26
- **Status**: ❌ DEPRECATED
- **Replaced By:** [feat-ui-pro.md](./feat-ui-pro.md) (specific 4-phase plan) + [ACCESSIBILITY_GUIDE.md](./ACCESSIBILITY_GUIDE.md) (implementation patterns) + [QUALITY_GATES_A11Y.md](./QUALITY_GATES_A11Y.md) (testing procedures)
- **Date Deprecated:** 9. Dezember 2025
- **Reason:** Too generic. New docs provide specific implementation steps with A11Y compliance, HTMX integration, and quality gates.
- **Related**: [ROADMAP.md](./ROADMAP.md) ❌ DEPRECATED, [TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md) ❌ DEPRECATED

**DO NOT USE THIS FILE. See [feat-ui-pro.md](./feat-ui-pro.md) for actionable implementation plan.**

---

<details>
<summary>Original Content (Archived)</summary>

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Environment Setup](#development-environment-setup)
3. [Project Structure](#project-structure)
4. [Development Workflow](#development-workflow)
5. [Creating Components](#creating-components)
6. [Styling Guidelines](#styling-guidelines)
7. [JavaScript Development](#javascript-development)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (for Tailwind CSS)
- Git
- Code editor (VS Code recommended)

### Initial Setup

1. **Clone the repository**:
```bash
cd /home/bozzfozz/Dokumente/soulspot.code-workspace
```

2. **Install Python dependencies**:
```bash
poetry install
# or
pip install -r requirements.txt
```

3. **Install Node dependencies**:
```bash
npm install
```

4. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run database migrations**:
```bash
alembic upgrade head
```

6. **Start the development server**:
```bash
# Terminal 1: Run FastAPI server
uvicorn soulspot.main:app --reload --port 8000

# Terminal 2: Watch Tailwind CSS
npm run dev:css
```

7. **Access the application**:
```
http://localhost:8000
```

---

## Development Environment Setup

### Recommended VS Code Extensions

- **Python**: Python language support
- **Pylance**: Python IntelliSense
- **Tailwind CSS IntelliSense**: Tailwind class autocomplete
- **HTML CSS Support**: HTML/CSS IntelliSense
- **Auto Rename Tag**: Auto rename paired HTML tags
- **Prettier**: Code formatter
- **ESLint**: JavaScript linter

### VS Code Settings

Create `.vscode/settings.json`:
```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "tailwindCSS.experimental.classRegex": [
    ["class:\\s*[\"'`]([^\"'`]*)[\"'`]", "([a-zA-Z0-9\\-:]+)"]
  ],
  "files.associations": {
    "*.html": "jinja-html"
  }
}
```

---

## Project Structure

### Directory Layout

```
src/soulspot/
├── templates/                  # Jinja2 templates
│   ├── base.html              # Base layout
│   ├── components/            # Reusable components
│   │   ├── layout/
│   │   │   ├── Sidebar.html
│   │   │   ├── TopBar.html
│   │   │   └── PageHeader.html
│   │   ├── navigation/
│   │   │   ├── Breadcrumbs.html
│   │   │   ├── Tabs.html
│   │   │   └── Pagination.html
│   │   ├── data-display/
│   │   │   ├── Card.html
│   │   │   ├── Table.html
│   │   │   └── Badge.html
│   │   ├── input/
│   │   │   ├── Button.html
│   │   │   ├── Input.html
│   │   │   └── Select.html
│   │   ├── feedback/
│   │   │   ├── Alert.html
│   │   │   ├── Modal.html
│   │   │   └── Loading.html
│   │   └── specialized/
│   │       ├── LibraryView.html
│   │       ├── QueueManager.html
│   │       └── ActivityFeed.html
│   ├── pages/                 # Page templates
│   │   ├── dashboard.html
│   │   ├── library/
│   │   ├── playlists/
│   │   ├── downloads/
│   │   ├── search.html
│   │   └── settings.html
│   └── includes/              # Partial templates
│       ├── _theme.html
│       ├── _navigation.html
│       └── _scripts.html
├── static/
│   ├── css/
│   │   ├── base/
│   │   │   ├── reset.css
│   │   │   ├── variables.css
│   │   │   └── typography.css
│   │   ├── components/
│   │   │   ├── layout.css
│   │   │   ├── navigation.css
│   │   │   ├── cards.css
│   │   │   └── buttons.css
│   │   └── main.css           # Main entry point
│   ├── js/
│   │   ├── core/
│   │   │   ├── app.js
│   │   │   ├── api.js
│   │   │   └── state.js
│   │   ├── components/
│   │   │   ├── navigation.js
│   │   │   ├── library.js
│   │   │   └── queue.js
│   │   └── utils/
│   │       ├── helpers.js
│   │       └── validators.js
│   └── assets/
│       ├── images/
│       └── icons/
└── api/
    └── routers/
        └── ui.py              # UI-specific API endpoints
```

---

## Development Workflow

### 1. **Planning**

Before writing code:
1. Review the [ROADMAP.md](./ROADMAP.md) for context
2. Check [TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md) for architecture
3. Consult [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) for design tokens
4. Review [COMPONENT_LIBRARY.md](./COMPONENT_LIBRARY.md) for existing components

### 2. **Creating a New Feature**

**Step 1: Create a branch**
```bash
git checkout -b feat/library-grid-view
```

**Step 2: Plan the component**
- Sketch the UI
- Identify reusable components
- Define props and data structure
- Plan API endpoints (if needed)

**Step 3: Implement**
- Create component template
- Add styles
- Implement JavaScript (if needed)
- Connect to API

**Step 4: Test**
- Functionality testing
- Accessibility testing
- Responsive testing
- Cross-browser testing

**Step 5: Review and merge**
- Self-review code
- Submit for peer review
- Address feedback
- Merge to main

### 3. **Daily Development Cycle**

```bash
# 1. Pull latest changes
git pull origin main

# 2. Start development servers
# Terminal 1: FastAPI
uvicorn soulspot.main:app --reload

# Terminal 2: Tailwind CSS watcher
npm run dev:css

# 3. Make changes
# Edit templates, CSS, JavaScript

# 4. Test in browser
# http://localhost:8000

# 5. Commit changes
git add .
git commit -m "feat: add library grid view"
git push origin feat/library-grid-view
```

---

## Creating Components

### Component Creation Checklist

- [ ] Create component template file
- [ ] Define component props
- [ ] Implement HTML structure
- [ ] Add CSS classes
- [ ] Implement JavaScript (if needed)
- [ ] Add accessibility attributes
- [ ] Test responsiveness
- [ ] Document usage
- [ ] Add to component library

### Example: Creating a New Component

**1. Create the template file**

`templates/components/data-display/StatCard.html`:
```html
{# 
  StatCard Component
  
  Props:
    - title: str - Card title
    - value: str|int - Stat value
    - icon: str - Font Awesome icon class
    - color: str - Color variant (primary, success, warning, danger)
    - trend: dict - Optional trend data {value: int, direction: 'up'|'down'}
#}

<div class="stat-card stat-card-{{ color or 'primary' }}">
  <div class="stat-card-icon">
    <i class="{{ icon }}"></i>
  </div>
  
  <div class="stat-card-content">
    <div class="stat-card-title">{{ title }}</div>
    <div class="stat-card-value">{{ value }}</div>
    
    {% if trend %}
    <div class="stat-card-trend stat-card-trend-{{ trend.direction }}">
      <i class="fa-solid fa-arrow-{{ 'up' if trend.direction == 'up' else 'down' }}"></i>
      {{ trend.value }}%
    </div>
    {% endif %}
  </div>
</div>
```

**2. Add styles**

`static/css/components/cards.css`:
```css
/* Stat Card */
.stat-card {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-lg);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: all var(--transition-normal);
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.stat-card-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  font-size: var(--font-size-2xl);
}

.stat-card-primary .stat-card-icon {
  background: rgba(254, 65, 85, 0.1);
  color: var(--color-primary);
}

.stat-card-content {
  flex: 1;
}

.stat-card-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--space-xs);
}

.stat-card-value {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-text);
}

.stat-card-trend {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  font-size: var(--font-size-sm);
  margin-top: var(--space-xs);
}

.stat-card-trend-up {
  color: var(--color-success);
}

.stat-card-trend-down {
  color: var(--color-danger);
}
```

**3. Use the component**

`templates/pages/dashboard.html`:
```html
{% extends "base.html" %}

{% block content %}
<div class="dashboard-stats">
  {% include 'components/data-display/StatCard.html' with {
    'title': 'Total Playlists',
    'value': stats.playlists,
    'icon': 'fa-solid fa-list',
    'color': 'primary',
    'trend': {'value': 12, 'direction': 'up'}
  } %}
  
  {% include 'components/data-display/StatCard.html' with {
    'title': 'Total Tracks',
    'value': stats.tracks,
    'icon': 'fa-solid fa-music',
    'color': 'success'
  } %}
</div>
{% endblock %}
```

---

## Styling Guidelines

### CSS Architecture

**1. Use CSS Custom Properties**
```css
/* Good */
.button {
  background: var(--color-primary);
  padding: var(--space-md);
  border-radius: var(--radius-md);
}

/* Bad */
.button {
  background: #fe4155;
  padding: 16px;
  border-radius: 8px;
}
```

**2. Follow BEM-like naming**
```css
/* Block */
.card { }

/* Element */
.card-header { }
.card-body { }
.card-footer { }

/* Modifier */
.card-primary { }
.card-large { }
```

**3. Use Tailwind utilities for layout**
```html
<!-- Good: Use Tailwind for layout -->
<div class="flex items-center gap-4">
  <div class="card">...</div>
</div>

<!-- Bad: Custom CSS for simple layouts -->
<div class="custom-flex-container">
  <div class="card">...</div>
</div>
```

**4. Component-specific styles in separate files**
```css
/* static/css/components/cards.css */
.card { /* Card styles */ }

/* static/css/components/buttons.css */
.btn { /* Button styles */ }
```

### Responsive Design

**Mobile-first approach**:
```css
/* Mobile (default) */
.sidebar {
  width: 100%;
}

/* Tablet and up */
@media (min-width: 768px) {
  .sidebar {
    width: 250px;
  }
}

/* Desktop and up */
@media (min-width: 1024px) {
  .sidebar {
    width: 280px;
  }
}
```

---

## JavaScript Development

### Module Structure

**1. Core modules** (`static/js/core/`):
- `app.js` - Application initialization
- `api.js` - API client
- `state.js` - State management

**2. Component modules** (`static/js/components/`):
- `navigation.js` - Navigation behavior
- `library.js` - Library view logic
- `queue.js` - Queue management

**3. Utility modules** (`static/js/utils/`):
- `helpers.js` - Helper functions
- `validators.js` - Validation functions

### Example: API Client

`static/js/core/api.js`:
```javascript
/**
 * API Client
 * Handles all API requests with error handling
 */

class APIClient {
  constructor(baseURL = '/api') {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // GET request
  async get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;
    return this.request(url);
  }

  // POST request
  async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  // PUT request
  async put(endpoint, data) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }

  // DELETE request
  async delete(endpoint) {
    return this.request(endpoint, {
      method: 'DELETE'
    });
  }
}

// Export singleton instance
export const api = new APIClient();
```

### Example: Component JavaScript

`static/js/components/library.js`:
```javascript
import { api } from '../core/api.js';
import { State } from '../core/state.js';

/**
 * Library View Component
 */
export class LibraryView {
  constructor(container) {
    this.container = container;
    this.viewMode = State.get('libraryViewMode', 'grid');
    this.init();
  }

  init() {
    this.setupViewToggle();
    this.setupFilters();
    this.setupSort();
  }

  setupViewToggle() {
    const toggleButtons = this.container.querySelectorAll('.view-toggle-btn');
    
    toggleButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const viewMode = btn.dataset.view;
        this.setViewMode(viewMode);
      });
    });
  }

  async setViewMode(mode) {
    this.viewMode = mode;
    State.set('libraryViewMode', mode);
    
    // Update active button
    this.container.querySelectorAll('.view-toggle-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === mode);
    });
    
    // Reload items with new view mode
    await this.loadItems({ view: mode });
  }

  async loadItems(params = {}) {
    try {
      const items = await api.get('/library/artists', {
        view: this.viewMode,
        ...params
      });
      
      this.renderItems(items);
    } catch (error) {
      console.error('Failed to load library items:', error);
      this.showError('Failed to load items');
    }
  }

  renderItems(items) {
    const container = this.container.querySelector('.library-items');
    // Render logic here
  }

  showError(message) {
    // Show error toast
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  const libraryContainer = document.querySelector('.library-view');
  if (libraryContainer) {
    new LibraryView(libraryContainer);
  }
});
```

---

## Testing

### Manual Testing Checklist

**Functionality**:
- [ ] All features work as expected
- [ ] Forms validate correctly
- [ ] API calls succeed
- [ ] Error handling works

**Accessibility**:
- [ ] Keyboard navigation works
- [ ] Focus indicators visible
- [ ] ARIA labels present
- [ ] Screen reader compatible
- [ ] Color contrast sufficient

**Responsiveness**:
- [ ] Mobile (320px - 767px)
- [ ] Tablet (768px - 1023px)
- [ ] Desktop (1024px+)
- [ ] Touch interactions work

**Cross-browser**:
- [ ] Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Edge

### Automated Testing

**Python tests** (pytest):
```bash
pytest tests/
```

**Accessibility tests** (axe-core):
```javascript
// tests/accessibility.test.js
import { test } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

test('Library page is accessible', async ({ page }) => {
  await page.goto('http://localhost:8000/library');
  await injectAxe(page);
  await checkA11y(page);
});
```

---

## Deployment

### Build Process

**1. Build CSS**:
```bash
npm run build:css
```

**2. Minify JavaScript**:
```bash
npm run build:js
```

**3. Optimize images**:
```bash
npm run optimize:images
```

### Docker Deployment

```bash
# Build image
docker build -t soulspot:latest .

# Run container
docker run -p 8000:8000 soulspot:latest
```

---

## Troubleshooting

### Common Issues

**Issue**: Tailwind classes not working
**Solution**: Ensure Tailwind watcher is running (`npm run dev:css`)

**Issue**: HTMX not updating content
**Solution**: Check network tab for API errors, verify HTMX attributes

**Issue**: JavaScript not loading
**Solution**: Check browser console for errors, verify script paths

**Issue**: Styles not applying
**Solution**: Clear browser cache, check CSS file order in base.html

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-26  
**Status**: Draft - Awaiting Approval
