# UI 1.0 Design System

> **Version:** 1.0.0
> **Status:** Production Ready
> **Lokation:** `/docs/ui/` (SoulSpot Bridge Repository)
> **Letzte Aktualisierung:** 2025-11-15


## 📋 Overview

This design system provides a complete set of design tokens, component styles, and layout utilities that can be integrated into any web application. All branding elements (logos, product names, marketing content) have been removed to create a clean, generic foundation.

**Integration in SoulSpot Bridge:** Dieses Design System bildet die Grundlage für die Web-Oberfläche von SoulSpot Bridge Version 1.0. Alle UI-Komponenten verwenden diese Styles für eine konsistente und moderne Benutzererfahrung.

## 🎯 Purpose

- **Neutral Foundation**: No project-specific branding or content
- **Reusable Components**: Pre-styled UI components ready to use
- **Consistent Design**: Unified color scheme, typography, and spacing
- **Accessible**: WCAG 2.1 AA compliant with focus states and screen reader support
- **Responsive**: Mobile-first design with breakpoint utilities
- **Dark Mode**: Built-in dark mode support with automatic detection

## 📦 What's Included

### 1. Design Tokens (`theme.css`)

Complete set of CSS custom properties for:

- **Colors**: Primary, secondary, semantic colors (success, warning, danger, info)
- **Typography**: Font families, sizes, weights, line heights
- **Spacing**: Consistent spacing scale (4px increments)
- **Border Radius**: Small to full rounded corners
- **Shadows**: Elevation system from subtle to prominent
- **Transitions**: Timing functions for smooth animations
- **Z-Index**: Layering system for modals, dropdowns, tooltips

### 2. Components (`components.css`)

Ready-to-use component classes:

- **Buttons**: Primary, secondary, outline, ghost, danger variants with sizes
- **Cards**: Header, body, footer with hover effects
- **Badges**: Status indicators in all semantic colors
- **Alerts**: Success, warning, danger, info notifications
- **Forms**: Inputs, textareas, selects, checkboxes, radios
- **Tables**: Responsive tables with hover states
- **Navigation**: Horizontal nav, vertical nav, tabs
- **Modals**: Backdrop, container, header, body, footer
- **Loading**: Spinners, progress bars, skeleton screens

### 3. Layout Utilities (`layout.css`)

Page structure and layout helpers:

- **Container**: Responsive max-width containers
- **Grid**: CSS Grid utilities with responsive columns
- **Flexbox**: Flex utilities for alignment and distribution
- **Page Layouts**: Header, content, footer, sidebar layouts
- **Spacing**: Margin and padding utilities
- **Typography**: Heading styles and text alignment
- **Responsive**: Breakpoint-specific utilities
- **Display**: Show/hide utilities for responsive design

### 4. Demo Page (`ui-demo.html`)

Comprehensive showcase of all components and utilities with live examples.

## 🚀 Getting Started

### Installation

#### Für SoulSpot Bridge
Das Design System ist bereits in SoulSpot Bridge integriert. Die CSS-Dateien befinden sich in `/docs/ui/` und werden von den Jinja2-Templates referenziert.

#### Für externe Projekte
1. Copy the UI files to your project:
```bash
cp -r docs/ui/ /path/to/your/project/ui/
```

2. Include the CSS files in your HTML:
```html
<link rel="stylesheet" href="/path/to/ui/theme.css">
<link rel="stylesheet" href="/path/to/ui/components.css">
<link rel="stylesheet" href="/path/to/ui/layout.css">
```

**Hinweis:** Die Pfade müssen entsprechend Ihrer Projektstruktur angepasst werden.

### Basic Usage

#### Page Structure
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your App</title>
  <link rel="stylesheet" href="ui/theme.css">
  <link rel="stylesheet" href="ui/components.css">
  <link rel="stylesheet" href="ui/layout.css">
</head>
<body>
  <div class="ui-page">
    <header class="ui-page-header">
      <div class="ui-container">
        <!-- Header content -->
      </div>
    </header>

    <main class="ui-page-content">
      <div class="ui-container">
        <!-- Main content -->
      </div>
    </main>

    <footer class="ui-page-footer">
      <div class="ui-container">
        <!-- Footer content -->
      </div>
    </footer>
  </div>
</body>
</html>
```

#### Using Components

**Buttons:**
```html
<button class="ui-btn ui-btn-primary">Primary Button</button>
<button class="ui-btn ui-btn-secondary">Secondary Button</button>
<button class="ui-btn ui-btn-outline">Outline Button</button>
<button class="ui-btn ui-btn-danger ui-btn-sm">Small Danger</button>
```

**Cards:**
```html
<div class="ui-card">
  <div class="ui-card-header">
    <h3 class="ui-card-title">Card Title</h3>
    <p class="ui-card-subtitle">Optional subtitle</p>
  </div>
  <div class="ui-card-body">
    <p>Card content goes here.</p>
  </div>
  <div class="ui-card-footer">
    <button class="ui-btn ui-btn-primary ui-btn-sm">Action</button>
  </div>
</div>
```

**Badges:**
```html
<span class="ui-badge ui-badge-success">Success</span>
<span class="ui-badge ui-badge-warning">Warning</span>
<span class="ui-badge ui-badge-danger">Danger</span>
<span class="ui-badge ui-badge-info">Info</span>
```

**Alerts:**
```html
<div class="ui-alert ui-alert-success">
  <div class="ui-alert-icon">
    <!-- SVG icon -->
  </div>
  <div class="ui-alert-content">
    <div class="ui-alert-title">Success!</div>
    Your operation completed successfully.
  </div>
</div>
```

**Forms:**
```html
<form>
  <div class="ui-form-group">
    <label class="ui-label ui-label-required">Username</label>
    <input type="text" class="ui-input" placeholder="Enter username">
    <div class="ui-form-help">Choose a unique username</div>
  </div>

  <div class="ui-form-group">
    <label class="ui-label">Description</label>
    <textarea class="ui-textarea" placeholder="Enter description"></textarea>
  </div>

  <button type="submit" class="ui-btn ui-btn-primary">Submit</button>
</form>
```

**Layout Grid:**
```html
<div class="ui-grid ui-grid-cols-3">
  <div class="ui-card">Card 1</div>
  <div class="ui-card">Card 2</div>
  <div class="ui-card">Card 3</div>
</div>
```

## 🎨 Customization

### Changing Colors

Override CSS custom properties in your own stylesheet:

```css
:root {
  --ui-primary: #your-color;
  --ui-primary-hover: #your-hover-color;
  /* Override other tokens as needed */
}
```

### Custom Components

Build on top of the base classes:

```css
.my-special-button {
  /* Inherit base button styles */
  @extend .ui-btn;
  @extend .ui-btn-primary;

  /* Add custom styles */
  border-radius: var(--ui-radius-full);
  text-transform: uppercase;
}
```

### Dark Mode

Dark mode is automatic based on system preferences. You can also manually toggle:

```html
<button onclick="toggleDarkMode()">Toggle Dark Mode</button>

<script>
  function toggleDarkMode() {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme',
      document.documentElement.classList.contains('dark') ? 'dark' : 'light'
    );
  }

  // Load saved theme on page load
  if (localStorage.getItem('theme') === 'dark' ||
      (!localStorage.getItem('theme') &&
       window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark');
  }
</script>
```

## 📱 Responsive Design

The system uses mobile-first responsive breakpoints:

- **sm**: 640px
- **md**: 768px
- **lg**: 1024px
- **xl**: 1280px
- **2xl**: 1536px

Responsive utilities:
```html
<!-- Hide on mobile -->
<div class="ui-hide-sm">Hidden on small screens</div>

<!-- Show only on mobile -->
<div class="ui-show-mobile">Only visible on mobile</div>

<!-- Show only on desktop -->
<div class="ui-show-desktop">Only visible on desktop</div>
```

## ♿ Accessibility

Built-in accessibility features:

- **Focus States**: Clear focus indicators on all interactive elements
- **ARIA Support**: Semantic HTML with proper ARIA attributes
- **Keyboard Navigation**: Full keyboard support
- **Screen Readers**: Skip links and screen-reader-only content
- **Color Contrast**: WCAG AA compliant color combinations
- **Reduced Motion**: Respects `prefers-reduced-motion` preference

### Accessibility Classes

```html
<!-- Skip to main content -->
<a href="#main" class="ui-skip-link">Skip to main content</a>

<!-- Screen reader only text -->
<span class="ui-sr-only">Additional context for screen readers</span>
```

## 🔧 Browser Support

- Chrome (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Edge (latest 2 versions)
- Mobile Safari (iOS 12+)
- Chrome Mobile (latest)




### Für SoulSpot Bridge Contributors

Wenn Sie UI-Komponenten für SoulSpot Bridge entwickeln:

1. Verwenden Sie die vorhandenen Design-Token aus `theme.css`
2. Erweitern Sie `components.css` nur, wenn neue generische Komponenten benötigt werden
3. Projektspezifische Styles sollten in separaten Dateien (z.B. `soulspot-custom.css`) liegen
4. Testen Sie Ihre Änderungen mit `ui-demo.html` auf Konsistenz
5. Stellen Sie sicher, dass alle neuen Komponenten WCAG 2.1 AA konform sind

## 📚 Resources

### Externe Ressourcen
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [CSS Custom Properties](https://developer.mozilla.org/en-US/docs/Web/CSS/--*)

### SoulSpot Bridge Dokumentation
- [Frontend Development Roadmap v1.0](../frontend-development-roadmap-v1.0.md) – Detaillierte Planung für Version 1.0
- [Architecture Documentation](../architecture.md) – System-Architektur
- [Design Guidelines](../design-guidelines.md) – Design-Prinzipien für SoulSpot Bridge
- [Keyboard Navigation Guide](../keyboard-navigation.md) – Tastaturnavigation
- [UI/UX Testing Report](../ui-ux-testing-report.md) – Test-Ergebnisse

---

## 🔄 Version History

### Version 1.0.0 (2025-11-15)
- ✅ Initial Release – Complete Design System
- ✅ Moved to `/docs/ui/` in SoulSpot Bridge Repository
- ✅ Integration mit SoulSpot Bridge Frontend
- ✅ Vollständige Dokumentation mit Beispielen
- ✅ WCAG 2.1 AA konform
- ✅ Dark Mode Support
- ✅ Responsive Design (Mobile-First)
- ✅ 48 UI-Komponenten
- ✅ Demo-Seite mit interaktiven Beispielen

**Komponenten:**
- Buttons (6 Varianten × 3 Größen)
- Cards (Header, Body, Footer)
- Badges & Alerts (4 Semantic Colors)
- Forms (Input, Textarea, Select, Checkbox, Radio)
- Tables (Responsive, Hover, Striped)
- Navigation (Horizontal, Vertical, Tabs)
- Modals (Backdrop, Container, Header, Body, Footer)
- Loading States (Spinner, Progress Bar, Skeleton)

**Design Tokens:**
- 18 Farb-Variablen (Primary, Secondary, Semantic, Neutrals)
- 13 Typografie-Variablen (Font-Familien, -Größen, -Gewichte)
- 20 Spacing-Variablen (4px-Schritte)
- 5 Border-Radius-Variablen
- 6 Shadow-Variablen
- 3 Transition-Variablen
- 5 Z-Index-Variablen

---

**Version**: 1.0.0
**Last Updated**: 2025-11-15
**Status**: Production Ready
**Lokation**: `/docs/ui/` (SoulSpot Bridge)
