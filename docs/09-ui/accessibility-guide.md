# Accessibility Guide

**Category:** UI/UX Design / Quality  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [Component Library](./component-library.md), [Quality Gates](./quality-gates-a11y.md), [UI Architecture](./ui-architecture-principles.md)

---

## Overview

A11Y-First implementation guide for SoulSpot targeting **WCAG 2.1 Level AA/AAA** compliance.

## WCAG 2.1 Compliance Matrix

| Guideline | Level | Status | Implementation |
|-----------|-------|--------|----------------|
| **2.1.1 Keyboard** | A | ✅ Required | Tab/Shift+Tab for all interactive elements |
| **2.1.2 No Keyboard Trap** | A | ✅ Required | Focus trap in modals |
| **2.4.3 Focus Order** | A | ✅ Required | Logical tab order |
| **2.5.5 Target Size** | AAA | ✅ Required | Minimum 44×44px (48×48px recommended) |
| **4.1.2 Name, Role, Value** | A | ✅ Required | ARIA labels for all components |
| **2.3.3 Animation** | AAA | ✅ Required | `prefers-reduced-motion` support |
| **1.4.3 Contrast (Min)** | AA | ✅ Required | 4.5:1 text, 3:1 large text |
| **1.4.11 Non-text Contrast** | AAA | ✅ Required | 3:1 UI components |

## Focus Trap Implementation

**Why:** Modal dialogs must trap focus (WCAG 2.1.2). Tab key cycles only within modal.

### FocusTrap Class

```javascript
// static/js/focus-trap.js
class FocusTrap {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      initialFocus: options.initialFocus || null,
      returnFocus: options.returnFocus !== false,
      ...options,
    };
    this.previousActiveElement = null;
    this.handleKeydown = this.handleKeydown.bind(this);
  }

  activate() {
    this.previousActiveElement = document.activeElement;
    
    // Set initial focus
    if (this.options.initialFocus) {
      this.options.initialFocus.focus();
    } else {
      const firstFocusable = this.getFirstFocusableElement();
      if (firstFocusable) firstFocusable.focus();
    }

    this.element.addEventListener('keydown', this.handleKeydown);
  }

  deactivate() {
    this.element.removeEventListener('keydown', this.handleKeydown);
    
    if (this.options.returnFocus && this.previousActiveElement) {
      this.previousActiveElement.focus();
    }
  }

  getFocusableElements() {
    const selector = [
      'a[href]',
      'button:not([disabled])',
      'textarea:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(',');
    
    return Array.from(this.element.querySelectorAll(selector));
  }

  handleKeydown(event) {
    if (event.key !== 'Tab') return;

    const focusableElements = this.getFocusableElements();
    if (focusableElements.length === 0) return;

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    const activeElement = document.activeElement;

    if (event.shiftKey) {
      // Shift+Tab on first element → focus last element
      if (activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      }
    } else {
      // Tab on last element → focus first element
      if (activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }
  }
}
```

### HTMX Integration

Activate focus trap **after** HTMX swap:

```javascript
// static/js/app.js
document.addEventListener('htmx:afterSwap', (event) => {
  const modal = event.detail.target.querySelector('[role="dialog"]');
  if (modal) {
    const focusTrap = new FocusTrap(modal, {
      initialFocus: modal.querySelector('.modal-close-button, .btn-primary'),
      returnFocus: true,
    });
    focusTrap.activate();
    
    // Store for cleanup
    modal._focusTrap = focusTrap;
  }
});

document.addEventListener('htmx:beforeSwap', (event) => {
  const modal = event.detail.target.querySelector('[role="dialog"]');
  if (modal && modal._focusTrap) {
    modal._focusTrap.deactivate();
  }
});
```

## Keyboard Navigation

### Tab Order

**Principle:** Logical visual flow

```html
<!-- Correct tab order: 1 → 2 → 3 → 4 -->
<form>
  <input name="title" tabindex="1">      <!-- 1 -->
  <input name="artist" tabindex="2">     <!-- 2 -->
  <button type="submit" tabindex="3">    <!-- 3 -->
  <button type="reset" tabindex="4">     <!-- 4 -->
</form>
```

### Skip Links

```html
<!-- First element in <body> -->
<a href="#main-content" class="skip-link">
  Skip to main content
</a>

<!-- CSS for skip link -->
<style>
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--color-primary);
  color: white;
  padding: 8px;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
</style>
```

## Touch Target Sizing

**WCAG 2.5.5 (AAA):** Minimum 44×44px

```css
/* Minimum touch target size */
.btn, button, a, input[type="checkbox"], input[type="radio"] {
  min-width: 44px;
  min-height: 44px;
}

/* Recommended: 48×48px */
.btn-primary {
  min-width: 48px;
  min-height: 48px;
}

/* Mobile: 56×56px for critical actions */
@media (max-width: 768px) {
  .btn-critical {
    min-width: 56px;
    min-height: 56px;
  }
}
```

## ARIA Patterns

### Icon-Only Buttons

```html
<!-- ❌ WRONG: No label -->
<button>
  <i class="bi-play-fill"></i>
</button>

<!-- ✅ RIGHT: aria-label + aria-hidden on icon -->
<button aria-label="Play track Thriller">
  <i class="bi-play-fill" aria-hidden="true"></i>
</button>
```

### Form Inputs

```html
<!-- ✅ Explicit label association -->
<label for="artist-name">Artist Name</label>
<input id="artist-name" name="artist" type="text" required aria-required="true">

<!-- ✅ Error messaging -->
<input 
  id="email" 
  type="email" 
  aria-describedby="email-error"
  aria-invalid="true">
<span id="email-error" role="alert">Invalid email format</span>
```

### Live Regions

```html
<!-- Announce dynamic updates -->
<div 
  role="status" 
  aria-live="polite" 
  aria-atomic="true"
  id="download-status">
  Downloading track... 45% complete
</div>

<!-- Urgent announcements -->
<div 
  role="alert" 
  aria-live="assertive"
  id="error-message">
  Download failed! Please retry.
</div>
```

## Color Contrast

### Minimum Ratios (WCAG 2.1)

| Content | Level AA | Level AAA |
|---------|----------|-----------|
| Normal text (<18pt) | 4.5:1 | 7:1 |
| Large text (≥18pt) | 3:1 | 4.5:1 |
| UI components | 3:1 | - |
| Graphical objects | 3:1 | - |

### Testing

```css
/* Good contrast examples */
:root {
  /* Text: 4.8:1 (AA ✅) */
  --text-on-dark: #f9fafb;  /* white */
  --bg-dark: #1f2937;       /* dark gray */
  
  /* Button: 4.6:1 (AA ✅) */
  --btn-primary-text: #ffffff;
  --btn-primary-bg: #8b5cf6;
  
  /* Focus ring: 3.2:1 (AA ✅) */
  --focus-ring: #60a5fa;  /* blue */
}
```

**Tools:**
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- Chrome DevTools Lighthouse
- axe DevTools browser extension

## Animation Accessibility

### Reduced Motion Support

```css
/* Default: Smooth animations */
.card {
  transition: transform 0.3s ease-out;
}

.card:hover {
  transform: translateY(-4px);
}

/* Reduced motion: Disable animations */
@media (prefers-reduced-motion: reduce) {
  .card {
    transition: none;
  }
  
  .card:hover {
    transform: none;
  }
  
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

## Screen Reader Testing

### VoiceOver (macOS)

```
Cmd+F5: Enable VoiceOver
VO+A: Start reading
VO+Right/Left: Navigate elements
VO+Space: Activate element
```

### NVDA (Windows - Free)

```
Ctrl+Alt+N: Start NVDA
Insert+Down: Read from cursor
Tab: Navigate interactive elements
Enter: Activate element
```

### Testing Checklist

- [ ] All images have `alt` text
- [ ] All forms have labels
- [ ] All interactive elements are keyboard accessible
- [ ] Focus order is logical
- [ ] ARIA labels are meaningful
- [ ] Live regions announce updates
- [ ] Headings are hierarchical (h1 → h2 → h3)
- [ ] Links have descriptive text (not "click here")

## Common Patterns

### Modal Dialog

```html
<div 
  role="dialog" 
  aria-labelledby="modal-title" 
  aria-describedby="modal-desc"
  aria-modal="true">
  <h2 id="modal-title">Confirm Delete</h2>
  <p id="modal-desc">Are you sure you want to delete this track?</p>
  <button aria-label="Cancel">Cancel</button>
  <button aria-label="Delete track">Delete</button>
</div>
```

### Loading State

```html
<button aria-busy="true" aria-live="polite">
  <span class="spinner" aria-hidden="true"></span>
  Loading...
</button>
```

### Accordion

```html
<button 
  aria-expanded="false" 
  aria-controls="panel-1"
  id="accordion-header-1">
  Artist Details
</button>
<div 
  id="panel-1" 
  role="region" 
  aria-labelledby="accordion-header-1"
  hidden>
  Content here...
</div>
```

## Related Documentation

- [Quality Gates](./quality-gates-a11y.md) - Automated testing
- [Component Library](./component-library.md) - Accessible components
- [UI Architecture](./ui-architecture-principles.md) - Design principles
- [HTMX Patterns](../05-developer-guides/htmx-patterns.md) - Interactive patterns
