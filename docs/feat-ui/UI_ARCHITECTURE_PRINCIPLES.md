# SoulSpot UI Architecture Principles

**Version:** 1.0  
**Created:** 17. Dezember 2025  
**Status:** ✅ Active Design Guidelines

---

## 🎯 Core Principles

### 1. Erweiterungsfreundlichkeit (Extensibility-First)

**Problem:** Jede neue Feature erfordert neue Components/Templates → Spaghetti Code

**Solution:** **Component-Based Architecture mit Atomic Design**

```
Atoms (Kleinste Bausteine)
  ↓
Molecules (Kombinationen von Atoms)
  ↓
Organisms (Komplexe UI-Bereiche)
  ↓
Templates (Page Layouts)
  ↓
Pages (Konkrete Instanzen)
```

#### 1.1 Atomic Design System

**Atoms** (`templates/components/atoms/`)
```jinja2
{# button.html - Kleinste wiederverwendbare Einheit #}
{% macro button(text, variant='primary', icon=None, size='md', disabled=False) %}
<button class="btn btn-{{ variant }} btn-{{ size }}" 
        {% if disabled %}disabled{% endif %}
        aria-label="{{ text }}">
  {% if icon %}<i class="{{ icon }}"></i>{% endif %}
  {{ text }}
</button>
{% endmacro %}
```

**Molecules** (`templates/components/molecules/`)
```jinja2
{# search_bar.html - Kombination von Atoms #}
{% import "components/atoms/button.html" as btn %}
{% import "components/atoms/input.html" as inp %}

{% macro search_bar(placeholder, action_url) %}
<form class="search-bar" hx-get="{{ action_url }}" hx-trigger="keyup changed delay:300ms">
  {{ inp.input(type='search', placeholder=placeholder, icon='bi-search') }}
  {{ btn.button('Search', variant='primary', icon='bi-search') }}
</form>
{% endmacro %}
```

**Organisms** (`templates/components/organisms/`)
```jinja2
{# artist_card.html - Komplexe UI-Komponente #}
{% import "components/molecules/image_with_overlay.html" as img %}
{% import "components/molecules/action_menu.html" as menu %}

{% macro artist_card(artist) %}
<article class="artist-card" data-artist-id="{{ artist.id }}">
  {{ img.image_with_overlay(src=artist.image, alt=artist.name, type='circular') }}
  <h3>{{ artist.name }}</h3>
  <p class="text-muted">{{ artist.genre }}</p>
  {{ menu.action_menu(actions=['play', 'follow', 'share']) }}
</article>
{% endmacro %}
```

**Warum das erweiterungsfreundlich ist:**
- ✅ **Neue Services**: Einfach neue Organisms erstellen (z.B. `tidal_artist_card.html`)
- ✅ **Konsistenz**: Atoms garantieren einheitliches Look & Feel
- ✅ **Änderungen**: Button-Update → alle 200 Buttons automatisch aktualisiert
- ✅ **Testing**: Jede Ebene isoliert testbar

#### 1.2 Service-Agnostic Components (Multi-Provider Ready)

**Problem:** `spotify_artist_card.html` funktioniert nicht für Tidal/Deezer

**Solution:** **Generic Domain Models + Service Adapters**

```
Generic Component (95% Reuse)
      ↓
Service Adapter (5% Custom Logic)
      ↓
Rendering
```

**Beispiel: Generic Artist Card**
```jinja2
{# components/organisms/artist_card.html - Service-agnostic #}
{% macro artist_card(artist, service='generic') %}
<article class="artist-card" data-service="{{ service }}">
  {# Generic Artist Entity - funktioniert für Spotify/Tidal/Deezer #}
  <img src="{{ artist.image_url }}" alt="{{ artist.name }}">
  <h3>{{ artist.name }}</h3>
  
  {# Service-specific badge #}
  {% if service != 'generic' %}
  <span class="badge badge-{{ service }}">
    <i class="icon-{{ service }}"></i> {{ service|title }}
  </span>
  {% endif %}
  
  {# Generic Actions - funktionieren überall #}
  <div class="actions">
    <button hx-post="/api/artists/{{ artist.id }}/play" class="btn-icon">
      <i class="bi-play-fill"></i>
    </button>
    <button hx-post="/api/artists/{{ artist.id }}/follow" class="btn-icon">
      <i class="bi-heart"></i>
    </button>
  </div>
</article>
{% endmacro %}
```

**Usage für verschiedene Services:**
```jinja2
{# Spotify Artist #}
{{ artist_card(spotify_artist, service='spotify') }}

{# Tidal Artist #}
{{ artist_card(tidal_artist, service='tidal') }}

{# Local Library Artist #}
{{ artist_card(local_artist, service='local') }}
```

**Erweiterung für neuen Service (Deezer):**
1. Add `badge-deezer` CSS class (5 min)
2. Add `icon-deezer` icon (2 min)
3. **Fertig!** Component funktioniert sofort.

#### 1.3 Plugin-Based Feature System

**Problem:** Neue Features erfordern Core-Code-Änderungen

**Solution:** **UI Plugins als Jinja2 Extensions**

```python
# src/soulspot/ui/plugins/base.py
class UIPlugin:
    """Base class für UI-Erweiterungen"""
    
    name: str
    enabled: bool = True
    
    def get_sidebar_items(self) -> list[dict]:
        """Sidebar Navigation Items"""
        return []
    
    def get_dashboard_widgets(self) -> list[dict]:
        """Dashboard Widgets"""
        return []
    
    def register_routes(self, router):
        """Custom Routes"""
        pass

# src/soulspot/ui/plugins/lyrics_plugin.py
class LyricsPlugin(UIPlugin):
    name = "lyrics"
    
    def get_sidebar_items(self):
        return [{
            'icon': 'bi-music-note-list',
            'label': 'Lyrics',
            'url': '/lyrics',
            'badge': 'New'
        }]
    
    def get_dashboard_widgets(self):
        return [{
            'title': 'Recently Added Lyrics',
            'template': 'plugins/lyrics/dashboard_widget.html',
            'size': 'medium'
        }]
```

**Dynamic Sidebar Generation:**
```jinja2
{# templates/includes/sidebar.html #}
<nav class="sidebar">
  {# Core Navigation #}
  <a href="/">Dashboard</a>
  <a href="/library">Library</a>
  
  {# Plugin Navigation (automatisch geladen) #}
  {% for plugin in enabled_plugins %}
    {% for item in plugin.get_sidebar_items() %}
    <a href="{{ item.url }}">
      <i class="{{ item.icon }}"></i>
      {{ item.label }}
      {% if item.badge %}<span class="badge">{{ item.badge }}</span>{% endif %}
    </a>
    {% endfor %}
  {% endfor %}
</nav>
```

**Neue Feature hinzufügen:**
1. Erstelle `ui/plugins/new_feature.py`
2. Implementiere `UIPlugin` Interface
3. Register in `settings.enabled_plugins`
4. **Fertig!** Feature erscheint in Sidebar + Dashboard.

---

### 2. Professionelles Aussehen (Premium UI/UX)

**Goal:** UI soll sich anfühlen wie Spotify/Apple Music/Tidal - nicht wie Hobby-Projekt

#### 2.1 Visual Design Principles

**Prinzip 1: Consistent Spacing System**
```css
/* variables.css - Exaktes 8px Grid System */
:root {
  --space-unit: 8px;
  --space-1: calc(var(--space-unit) * 0.5);  /* 4px */
  --space-2: var(--space-unit);              /* 8px */
  --space-3: calc(var(--space-unit) * 1.5);  /* 12px */
  --space-4: calc(var(--space-unit) * 2);    /* 16px */
  --space-6: calc(var(--space-unit) * 3);    /* 24px */
  --space-8: calc(var(--space-unit) * 4);    /* 32px */
  --space-12: calc(var(--space-unit) * 6);   /* 48px */
}

/* ❌ FALSCH: Beliebige Werte */
.card {
  padding: 17px;  /* Warum 17? */
  margin: 23px;   /* Inkonsistent! */
}

/* ✅ RICHTIG: Grid-basiert */
.card {
  padding: var(--space-4);   /* 16px */
  margin: var(--space-6);    /* 24px */
}
```

**Prinzip 2: Typography Hierarchy**
```css
/* variables.css - Klare Type Scale */
:root {
  /* Type Scale (Major Third - 1.25 ratio) */
  --font-size-xs: 0.8rem;      /* 12.8px - Labels */
  --font-size-sm: 0.875rem;    /* 14px - Body Small */
  --font-size-base: 1rem;      /* 16px - Body */
  --font-size-lg: 1.125rem;    /* 18px - Subheading */
  --font-size-xl: 1.25rem;     /* 20px - Heading 3 */
  --font-size-2xl: 1.563rem;   /* 25px - Heading 2 */
  --font-size-3xl: 1.953rem;   /* 31.25px - Heading 1 */
  
  /* Font Weights - Nur 3 Werte! */
  --font-weight-normal: 400;   /* Body */
  --font-weight-medium: 500;   /* Emphasis */
  --font-weight-bold: 700;     /* Headings */
}

/* ❌ FALSCH: Random Font Sizes */
h1 { font-size: 27px; }  /* Warum 27? */
h2 { font-size: 19px; }  /* Inkonsistent! */

/* ✅ RICHTIG: Type Scale */
h1 { font-size: var(--font-size-3xl); }  /* 31.25px */
h2 { font-size: var(--font-size-2xl); }  /* 25px */
```

**Prinzip 3: Color System mit Semantic Meaning**
```css
/* variables.css - Semantische Farben */
:root {
  /* Base Colors */
  --color-primary: #fe4155;     /* SoulSpot Red - Brand */
  --color-secondary: #1db954;   /* Spotify Green - Service */
  
  /* Semantic Colors - Eindeutige Bedeutung */
  --color-success: #10b981;     /* Download Complete */
  --color-warning: #f59e0b;     /* Missing Metadata */
  --color-error: #ef4444;       /* Download Failed */
  --color-info: #3b82f6;        /* Info Notification */
  
  /* State Colors - Interaktionen */
  --color-hover: rgba(254, 65, 85, 0.1);   /* Hover State */
  --color-active: rgba(254, 65, 85, 0.2);  /* Active State */
  --color-disabled: #6b6b6b;               /* Disabled State */
}

/* ❌ FALSCH: Farben ohne Bedeutung */
.button { background: #3498db; }  /* Was bedeutet diese Farbe? */
.badge { color: #e74c3c; }        /* Error oder Warning? */

/* ✅ RICHTIG: Semantische Farben */
.btn-primary { background: var(--color-primary); }
.badge-error { color: var(--color-error); }
.badge-warning { color: var(--color-warning); }
```

#### 2.2 Professional Animation Patterns

**Prinzip 1: Purposeful Motion (Animationen mit Zweck)**
```css
/* ❌ FALSCH: Animation ohne Grund */
.card {
  animation: spin 2s infinite;  /* Warum dreht sich die Card? */
}

/* ✅ RICHTIG: Animation kommuniziert Status */
.card-loading {
  animation: shimmer 1.5s infinite;  /* "Lädt gerade" */
}

.card-new {
  animation: slideInUp 0.3s ease-out;  /* "Neu hinzugefügt" */
}

.card-error {
  animation: shake 0.3s;  /* "Fehler aufgetreten" */
}
```

**Prinzip 2: Easing Functions (Natürliche Bewegungen)**
```css
:root {
  /* Material Design Easing */
  --ease-standard: cubic-bezier(0.4, 0.0, 0.2, 1);    /* Standard */
  --ease-decelerate: cubic-bezier(0.0, 0.0, 0.2, 1);  /* Eingang */
  --ease-accelerate: cubic-bezier(0.4, 0.0, 1, 1);    /* Ausgang */
  --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);  /* Bounce */
}

/* ❌ FALSCH: Linear (robotisch) */
.modal {
  transition: all 0.3s linear;  /* Fühlt sich mechanisch an */
}

/* ✅ RICHTIG: Natural Easing */
.modal {
  transition: all 0.3s var(--ease-decelerate);  /* Sanftes Einblenden */
}

.card:hover {
  transition: transform 0.2s var(--ease-standard);  /* Natürliche Reaktion */
  transform: translateY(-4px);
}
```

**Prinzip 3: Duration Guidelines**
```css
:root {
  /* Animation Durations - Basierend auf UI Element Größe */
  --duration-instant: 100ms;   /* Tooltips, Ripple Effects */
  --duration-fast: 200ms;      /* Hover States, Button Feedback */
  --duration-normal: 300ms;    /* Modals, Dropdowns */
  --duration-slow: 500ms;      /* Page Transitions, Large Movements */
}

/* Regel: Größere Elemente = Längere Duration */
.tooltip {
  transition: opacity var(--duration-instant);  /* Schnell */
}

.modal {
  transition: all var(--duration-normal);  /* Standard */
}

.page-transition {
  transition: transform var(--duration-slow);  /* Langsam */
}
```

#### 2.3 Professional Interaction Patterns

**Hover States - Alle interaktiven Elemente**
```css
/* Prinzip: User muss sofort sehen, dass Element klickbar ist */

/* ❌ FALSCH: Kein visuelles Feedback */
.btn {
  background: var(--color-primary);
}

/* ✅ RICHTIG: Klares Hover-Feedback */
.btn {
  background: var(--color-primary);
  transition: all var(--duration-fast) var(--ease-standard);
}

.btn:hover {
  background: var(--color-primary-dark);
  transform: translateY(-2px);  /* Subtle Lift */
  box-shadow: var(--shadow-md);
}

.btn:active {
  transform: translateY(0);  /* Press Down */
  box-shadow: var(--shadow-sm);
}
```

**Loading States - Feedback für jede Aktion**
```css
/* Prinzip: User muss wissen, dass etwas passiert */

/* ❌ FALSCH: Keine Loading Indication */
<button onclick="saveData()">Save</button>

/* ✅ RICHTIG: Loading State mit Spinner */
<button hx-post="/api/save" 
        hx-indicator="#spinner"
        class="btn"
        aria-busy="false">
  <span class="btn-text">Save</span>
  <span id="spinner" class="spinner" hidden>
    <i class="bi-arrow-repeat spin"></i>
  </span>
</button>

/* CSS */
.btn[aria-busy="true"] .btn-text { display: none; }
.btn[aria-busy="true"] .spinner { display: inline; }

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

**Empty States - Guidance statt Leere**
```jinja2
{# ❌ FALSCH: Leerer Screen ohne Erklärung #}
{% if tracks|length == 0 %}
  <p>No tracks</p>
{% endif %}

{# ✅ RICHTIG: Empty State mit Aktion #}
{% if tracks|length == 0 %}
  <div class="empty-state">
    <div class="empty-state-icon">
      <i class="bi-music-note-list" style="font-size: 4rem; opacity: 0.3;"></i>
    </div>
    <h3>No tracks yet</h3>
    <p class="text-muted">
      Start by importing your Spotify playlists or adding tracks manually
    </p>
    <div class="actions">
      <a href="/playlists/import" class="btn btn-primary">
        <i class="bi-download"></i> Import Playlist
      </a>
      <a href="/browse" class="btn btn-outline">
        <i class="bi-search"></i> Browse Music
      </a>
    </div>
  </div>
{% endif %}
```

#### 2.4 Professional Layout Patterns

**Grid System - Responsive & Consistent**
```css
/* Prinzip: Mobile-First, Breakpoint-basiert */

/* ❌ FALSCH: Fixed Widths */
.grid {
  display: grid;
  grid-template-columns: 200px 200px 200px;  /* Bricht auf Mobile! */
}

/* ✅ RICHTIG: Responsive Grid */
.grid {
  display: grid;
  gap: var(--space-4);
  
  /* Mobile: 1 Column */
  grid-template-columns: 1fr;
  
  /* Tablet: 2 Columns */
  @media (min-width: 640px) {
    grid-template-columns: repeat(2, 1fr);
  }
  
  /* Desktop: 3-4 Columns (Auto-Fit) */
  @media (min-width: 1024px) {
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  }
}
```

**Card Design - Elevation & Depth**
```css
/* Prinzip: Layering durch Shadows */

/* Base Card - Resting State */
.card {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-fast) var(--ease-standard);
}

/* Elevated Card - Hover State */
.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-4px);
}

/* Active Card - Selected State */
.card.active {
  box-shadow: 0 0 0 2px var(--color-primary);
  background: var(--color-hover);
}

/* Shadow System für Depth */
:root {
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);     /* Level 1 */
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);   /* Level 2 */
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.15); /* Level 3 */
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.2);  /* Level 4 */
}
```

---

### 3. Component Library Structure (Implementierung)

```
src/soulspot/templates/
├── components/
│   ├── atoms/                    # Kleinste Bausteine
│   │   ├── button.html
│   │   ├── input.html
│   │   ├── icon.html
│   │   ├── badge.html
│   │   ├── avatar.html
│   │   └── spinner.html
│   │
│   ├── molecules/                # Kombinationen
│   │   ├── search_bar.html
│   │   ├── dropdown.html
│   │   ├── card_header.html
│   │   ├── action_menu.html
│   │   ├── tag_list.html
│   │   └── progress_bar.html
│   │
│   ├── organisms/                # Komplexe Components
│   │   ├── artist_card.html
│   │   ├── album_card.html
│   │   ├── track_list.html
│   │   ├── navigation_bar.html
│   │   ├── sidebar.html
│   │   └── modal.html
│   │
│   ├── templates/                # Page Layouts
│   │   ├── base_layout.html
│   │   ├── two_column.html
│   │   ├── full_width.html
│   │   └── centered.html
│   │
│   └── pages/                    # Konkrete Pages
│       ├── dashboard.html
│       ├── library.html
│       ├── artist_detail.html
│       └── settings.html
│
├── plugins/                       # Plugin UI Extensions
│   ├── lyrics/
│   │   ├── dashboard_widget.html
│   │   └── lyrics_viewer.html
│   └── recommendations/
│       └── recommendations_panel.html
│
└── includes/                      # Legacy (Migration Path)
    ├── _components.html (deprecated → atoms/)
    └── macros.html (deprecated → molecules/)
```

---

### 4. CSS Architecture (Professional Scaling)

```
src/soulspot/static/new-ui/css/
├── 0-settings/              # Variables & Config
│   ├── _variables.css      # Design Tokens
│   ├── _colors.css         # Color System
│   └── _typography.css     # Type Scale
│
├── 1-tools/                 # Mixins & Functions
│   ├── _breakpoints.css    # Media Query Helpers
│   └── _utilities.css      # Utility Functions
│
├── 2-generic/               # Reset & Base
│   ├── _reset.css          # CSS Reset
│   └── _base.css           # Element Defaults
│
├── 3-elements/              # HTML Elements
│   ├── _headings.css       # h1-h6
│   ├── _links.css          # a
│   └── _forms.css          # input, select, etc.
│
├── 4-objects/               # Layout Patterns
│   ├── _container.css      # Max-width Container
│   ├── _grid.css           # Grid System
│   └── _flex.css           # Flexbox Patterns
│
├── 5-components/            # UI Components
│   ├── _button.css
│   ├── _card.css
│   ├── _modal.css
│   └── _sidebar.css
│
├── 6-utilities/             # Utility Classes
│   ├── _spacing.css        # Margin/Padding
│   ├── _text.css           # Text Utilities
│   └── _display.css        # Display Utilities
│
└── main.css                 # Entry Point (imports all)
```

**ITCSS Methodology Benefits:**
- ✅ **Scalability**: Neue CSS ohne Breaking Changes
- ✅ **Specificity Control**: Klare Hierarchie (Settings → Utilities)
- ✅ **Maintainability**: Jede Datei hat klaren Zweck
- ✅ **Performance**: Optimale CSS Cascade

---

### 5. JavaScript Architecture (Professional Patterns)

```javascript
// src/soulspot/static/new-ui/js/
// Hey future me - ES6 Modules für saubere Dependencies!

// app.js - Main Entry Point
import { SidebarController } from './controllers/sidebar.js';
import { ModalController } from './controllers/modal.js';
import { NotificationService } from './services/notifications.js';

class SoulSpotApp {
  constructor() {
    this.sidebar = new SidebarController();
    this.modal = new ModalController();
    this.notifications = new NotificationService();
  }
  
  init() {
    this.sidebar.init();
    this.modal.init();
    this.setupGlobalListeners();
  }
  
  setupGlobalListeners() {
    // HTMX Event Listeners
    document.addEventListener('htmx:afterSwap', (e) => {
      this.onHTMXSwap(e);
    });
  }
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  window.app = new SoulSpotApp();
  window.app.init();
});
```

**Module Pattern Benefits:**
- ✅ **Separation of Concerns**: Jede Class hat klare Verantwortung
- ✅ **Testability**: Jedes Modul isoliert testbar
- ✅ **Reusability**: Services wiederverwendbar
- ✅ **Maintainability**: Änderungen lokal begrenzt

---

### 6. Design System Documentation (Living Style Guide)

```html
<!-- templates/styleguide.html - Interactive Component Preview -->
<!DOCTYPE html>
<html>
<head>
  <title>SoulSpot Design System</title>
  <link rel="stylesheet" href="/static/new-ui/css/main.css">
</head>
<body>
  <div class="styleguide">
    <nav class="styleguide-nav">
      <a href="#colors">Colors</a>
      <a href="#typography">Typography</a>
      <a href="#buttons">Buttons</a>
      <a href="#cards">Cards</a>
      <a href="#forms">Forms</a>
    </nav>
    
    <main class="styleguide-content">
      <!-- Colors Section -->
      <section id="colors">
        <h2>Color System</h2>
        
        <div class="color-palette">
          <div class="color-swatch">
            <div class="swatch" style="background: var(--color-primary);"></div>
            <code>--color-primary</code>
            <span>#fe4155</span>
          </div>
          <!-- More swatches... -->
        </div>
      </section>
      
      <!-- Buttons Section -->
      <section id="buttons">
        <h2>Buttons</h2>
        
        <div class="component-preview">
          <h3>Primary Button</h3>
          {% import "components/atoms/button.html" as btn %}
          {{ btn.button('Primary', variant='primary') }}
          
          <pre><code>
{{ btn.button('Primary', variant='primary') }}
          </code></pre>
        </div>
        
        <!-- More components... -->
      </section>
    </main>
  </div>
</body>
</html>
```

**Living Style Guide Benefits:**
- ✅ **Single Source of Truth**: Design Decisions dokumentiert
- ✅ **Developer Onboarding**: Schnelles Verständnis des Systems
- ✅ **QA Testing**: Alle Components auf einer Page
- ✅ **Design-Dev Alignment**: Designer sehen Code-Implementation

---

## 🎯 Implementation Checklist

### Phase 1: Refactoring (Woche 1)
- [ ] **Atomic Design Migration**
  - [ ] Erstelle `components/atoms/` Struktur
  - [ ] Migriere bestehende Macros zu Atoms
  - [ ] Erstelle `components/molecules/` aus Atom-Kombinationen
  - [ ] Extrahiere Organisms aus Templates

- [ ] **CSS Architecture Refactoring**
  - [ ] Implementiere ITCSS Struktur
  - [ ] Migriere `variables.css` → `0-settings/`
  - [ ] Splitte `components.css` → `5-components/`
  - [ ] Erstelle Utility Classes in `6-utilities/`

### Phase 2: Professional Polish (Woche 2)
- [ ] **Visual Design**
  - [ ] Implementiere 8px Grid System
  - [ ] Definiere Type Scale (Major Third)
  - [ ] Erstelle Semantic Color System
  - [ ] Implementiere Shadow System für Depth

- [ ] **Animations**
  - [ ] Extrahiere Animationen zu `animations.css`
  - [ ] Implementiere Easing Functions
  - [ ] Definiere Duration Guidelines
  - [ ] Add `prefers-reduced-motion` Support

### Phase 3: Extensibility (Woche 3)
- [ ] **Plugin System**
  - [ ] Erstelle `UIPlugin` Base Class
  - [ ] Implementiere Dynamic Sidebar Loading
  - [ ] Implementiere Dashboard Widget System
  - [ ] Dokumentiere Plugin API

- [ ] **Service-Agnostic Components**
  - [ ] Refactore Spotify-specific Components
  - [ ] Implementiere Service Badges
  - [ ] Teste mit Mock Tidal/Deezer Data

### Phase 4: Documentation (Woche 4)
- [ ] **Style Guide**
  - [ ] Erstelle `/styleguide` Route
  - [ ] Dokumentiere alle Atoms
  - [ ] Dokumentiere alle Molecules
  - [ ] Add Interactive Code Previews

- [ ] **Developer Docs**
  - [ ] Component API Documentation
  - [ ] CSS Architecture Guide
  - [ ] Plugin Development Guide
  - [ ] Contribution Guidelines

---

## 🎨 Example: Professional Artist Card (Complete Implementation)

```jinja2
{# components/organisms/artist_card.html #}
{% import "components/atoms/button.html" as btn %}
{% import "components/atoms/badge.html" as badge %}
{% import "components/molecules/image_with_overlay.html" as img %}

{% macro artist_card(
  artist,
  service='local',
  show_actions=True,
  variant='default'
) %}
<article class="artist-card artist-card--{{ variant }}" 
         data-artist-id="{{ artist.id }}"
         data-service="{{ service }}">
  
  {# Image with Play Overlay #}
  <div class="artist-card__image">
    {{ img.image_with_overlay(
      src=artist.image_url,
      alt=artist.name,
      type='circular',
      overlay_icon='bi-play-fill',
      overlay_action='/api/artists/' ~ artist.id ~ '/play'
    ) }}
    
    {# Service Badge #}
    {% if service != 'local' %}
    <div class="artist-card__badge">
      {{ badge.badge(service|title, variant=service, icon='icon-' ~ service) }}
    </div>
    {% endif %}
  </div>
  
  {# Content #}
  <div class="artist-card__content">
    <h3 class="artist-card__name">
      <a href="/library/artists/{{ artist.name|urlencode }}">
        {{ artist.name }}
      </a>
    </h3>
    
    <p class="artist-card__meta text-muted">
      {% if artist.genre %}{{ artist.genre }}{% endif %}
      {% if artist.track_count %}
        • {{ artist.track_count }} tracks
      {% endif %}
    </p>
  </div>
  
  {# Actions #}
  {% if show_actions %}
  <div class="artist-card__actions">
    {{ btn.button('', variant='icon', icon='bi-play-fill', 
                  hx_post='/api/artists/' ~ artist.id ~ '/play',
                  aria_label='Play ' ~ artist.name) }}
    
    {{ btn.button('', variant='icon', icon='bi-heart',
                  hx_post='/api/artists/' ~ artist.id ~ '/follow',
                  aria_label='Follow ' ~ artist.name) }}
    
    {{ btn.button('', variant='icon', icon='bi-three-dots',
                  hx_get='/api/artists/' ~ artist.id ~ '/menu',
                  hx_target='#context-menu',
                  aria_label='More options for ' ~ artist.name) }}
  </div>
  {% endif %}
</article>
{% endmacro %}
```

**CSS (ITCSS Structure):**
```css
/* 5-components/_artist-card.css */

/* Base Card - Mobile First */
.artist-card {
  /* Layout */
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  
  /* Styling */
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
  
  /* Animation */
  transition: all var(--duration-fast) var(--ease-standard);
}

/* Hover State - Professional Lift Effect */
.artist-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-4px);
}

/* Image Container */
.artist-card__image {
  position: relative;
  aspect-ratio: 1;
  border-radius: var(--radius-full);
  overflow: hidden;
}

/* Service Badge - Positioned */
.artist-card__badge {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  z-index: var(--z-base);
}

/* Content Section */
.artist-card__content {
  flex: 1;
  min-width: 0; /* Prevent text overflow */
}

.artist-card__name {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-medium);
  margin: 0 0 var(--space-1) 0;
  
  /* Text Truncation */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artist-card__name a {
  color: var(--text-primary);
  text-decoration: none;
  transition: color var(--duration-fast);
}

.artist-card__name a:hover {
  color: var(--color-primary);
}

.artist-card__meta {
  font-size: var(--font-size-sm);
  margin: 0;
}

/* Actions - Horizontal Layout */
.artist-card__actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-primary);
}

/* Responsive - Desktop Grid Layout */
@media (min-width: 1024px) {
  .artist-card {
    flex-direction: row;
    align-items: center;
  }
  
  .artist-card__image {
    width: 80px;
    flex-shrink: 0;
  }
  
  .artist-card__actions {
    border-top: none;
    padding-top: 0;
  }
}

/* Variant: Compact (for sidebars, etc.) */
.artist-card--compact {
  flex-direction: row;
  padding: var(--space-2);
}

.artist-card--compact .artist-card__image {
  width: 48px;
}

.artist-card--compact .artist-card__actions {
  display: none; /* Hide actions in compact mode */
}
```

**Usage Examples:**
```jinja2
{# Standard Artist Card #}
{{ artist_card(artist, service='spotify') }}

{# Compact Variant (Sidebar) #}
{{ artist_card(artist, variant='compact', show_actions=False) }}

{# Local Library Artist #}
{{ artist_card(local_artist, service='local') }}

{# Tidal Artist (works without changes!) #}
{{ artist_card(tidal_artist, service='tidal') }}
```

---

## ✅ Success Criteria

**Erweiterungsfreundlichkeit:**
- ✅ Neuen Service (Deezer) hinzufügen: < 30 Minuten
- ✅ Neues Plugin entwickeln: < 2 Stunden
- ✅ Neuen Component erstellen: < 1 Stunde
- ✅ Breaking Changes vermeiden: 0 bei Extension

**Professionelles Aussehen:**
- ✅ Design Consistency: 100% (alle Components folgen System)
- ✅ Animation Quality: Material Design Standard
- ✅ Responsive Design: Mobile → Desktop seamless
- ✅ Accessibility: WCAG AA Compliance (Contrast, Keyboard Nav, Screen Reader)

**Maintainability:**
- ✅ CSS Specificity: Niedrig (ITCSS Methodology)
- ✅ Component Reuse: > 90% (Atoms in 100+ Stellen verwendet)
- ✅ Documentation Coverage: 100% (Living Style Guide)
- ✅ Developer Onboarding: < 1 Tag (mit Style Guide)

---

**Version:** 1.0  
**Status:** ✅ Active Design Guidelines  
**Last Updated:** 17. Dezember 2025
