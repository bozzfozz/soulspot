# A11Y-First Implementation Guide for SoulSpot UI Redesign v2.0

**Target:** WCAG 2.1 Level AA/AAA compliance across all 4 redesign phases.

---

## 1. WCAG 2.1 Compliance Matrix

| Guideline | Level | Phase | Status | Notes |
|-----------|-------|-------|--------|-------|
| 2.1.1 Keyboard | A | 2 | 🔄 In Progress | Tab/Shift+Tab navigation for all interactive elements |
| 2.1.2 No Keyboard Trap | A | 2 | 🔄 In Progress | Focus trap implementation required for modals |
| 2.4.3 Focus Order | A | 2 | 🔄 In Progress | Logical tab order matching visual flow |
| 2.5.5 Target Size | AAA | 1 | ❌ Not Started | Minimum 44×44px (48×48 recommended, 56×56 mobile) |
| 4.1.2 Name, Role, Value | A | 2 | 🔄 In Progress | ARIA labels for all interactive components |
| 2.3.3 Animation from Interactions | AAA | 1 | 🔄 In Progress | prefers-reduced-motion support |
| 1.4.3 Contrast (Minimum) | AA | 1 | ✅ Done | 4.5:1 for normal text, 3:1 for large text |
| 1.4.11 Non-text Contrast | AAA | 1 | ✅ Done | 3:1 for UI components and graphical elements |

---

## 2. Focus Trap Implementation

**Why:** Modal dialogs must trap focus (WCAG 2.1.2: No Keyboard Trap). When modal opens, Tab key cycles only within modal. When modal closes, focus restores to trigger element.

### FocusTrap Class (Vanilla JS)

```javascript
// static/js/focus-trap.js
// Browser Support: Chrome 60+, Firefox 55+, Safari 12+, Edge 79+
// Dependencies: None (Vanilla JS)
// Integration: Works with HTMX-loaded modals (see "HTMX Integration" section below)
class FocusTrap {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      initialFocus: options.initialFocus || null,
      returnFocus: options.returnFocus !== false,
      allowOutsideClick: options.allowOutsideClick || false,
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

  getFirstFocusableElement() {
    const focusableElements = this.getFocusableElements();
    return focusableElements.length > 0 ? focusableElements[0] : null;
  }

  getLastFocusableElement() {
    const focusableElements = this.getFocusableElements();
    return focusableElements.length > 0 ? focusableElements[focusableElements.length - 1] : null;
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
      // Shift+Tab on first element -> focus last element
      if (activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      }
    } else {
      // Tab on last element -> focus first element
      if (activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }
  }
}
```

### Usage Example

```javascript
// In your modal handler
const modal = document.querySelector('[role="dialog"]');
const focusTrap = new FocusTrap(modal, {
  initialFocus: modal.querySelector('.modal-close-button'),
  returnFocus: true,
});

// When modal opens
focusTrap.activate();

// When modal closes
focusTrap.deactivate();
```

### HTMX Integration (Project-Specific)

**SoulSpot uses HTMX v1.9.10** – modals are dynamically loaded. Activate focus trap **after** HTMX swap:

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
    
    // Store focusTrap instance for cleanup
    modal._focusTrap = focusTrap;
  }
});

// Cleanup on modal close
document.addEventListener('htmx:beforeRequest', (event) => {
  const modal = document.querySelector('[role="dialog"]');
  if (modal && modal._focusTrap) {
    modal._focusTrap.deactivate();
    delete modal._focusTrap;
  }
});
```

**Existing Implementation:** `static/js/app.js` already has `KeyboardNav.trapFocus()` – enhance it with the `FocusTrap` class above for full WCAG 2.1.2 compliance.

---

## 3. Keyboard Navigation Patterns

| Component | Tab | Shift+Tab | ↑↓ | Enter | Escape |
|-----------|-----|-----------|-----|-------|--------|
| **Modal Dialog** | Cycle within modal | Cycle within modal | N/A | Close (if button) | Close modal, restore focus |
| **Command Palette** | Cycle in results | Cycle in results | Navigate results | Execute command | Close palette |
| **Dropdown Menu** | Close menu | Close menu | Highlight item | Select item | Close menu |
| **Tabs** | Next tab | Prev tab | Next/Prev tab | N/A | N/A |
| **Radio Group** | Group (once) | Group (once) | Navigate options | Select | N/A |
| **Combobox** | Open/Close | N/A | Navigate options | Select | Close |

---

## 4. ARIA Labels & Patterns

### Modal Dialog Pattern

```html
<div role="dialog" aria-modal="true" aria-labelledby="modal-title" aria-describedby="modal-description">
  <h2 id="modal-title">Delete Playlist</h2>
  <p id="modal-description">This action cannot be undone.</p>
  
  <button aria-label="Close dialog">✕</button>
  <button>Cancel</button>
  <button>Delete</button>
</div>
```

### Command Palette Pattern

```html
<div role="combobox" aria-owns="command-list" aria-expanded="true">
  <input aria-autocomplete="list" aria-controls="command-list" type="text" placeholder="Search commands..." />
  <ul id="command-list" role="listbox">
    <li role="option" aria-selected="true">Play Now</li>
    <li role="option">Add to Queue</li>
  </ul>
</div>
```

### Form Field Pattern

```html
<div class="form-group">
  <label for="email">Email Address</label>
  <input 
    id="email" 
    type="email" 
    aria-required="true" 
    aria-describedby="email-error"
  />
  <span id="email-error" role="alert" class="error-message" hidden>
    Please enter a valid email address
  </span>
</div>
```

### Jinja2 Macro Pattern (Project-Specific)

**SoulSpot uses Jinja2 macros** in `templates/includes/_components.html` – create reusable A11Y form field:

```jinja2
{# templates/includes/_a11y_forms.html #}
{%- macro form_field(name, label, type='text', required=False, error_message='', help_text='') -%}
  <div class="form-group">
    <label for="{{ name }}">
      {{ label }}
      {% if required %}<span aria-label="required" style="color: var(--danger);">*</span>{% endif %}
    </label>
    
    <input 
      id="{{ name }}"
      name="{{ name }}"
      type="{{ type }}"
      class="form-input"
      {% if required %}aria-required="true"{% endif %}
      {% if error_message %}aria-invalid="true" aria-describedby="{{ name }}-error"{% endif %}
      {% if help_text %}aria-describedby="{{ name }}-help"{% endif %}
    />
    
    {% if help_text %}
      <small id="{{ name }}-help" class="form-help">{{ help_text }}</small>
    {% endif %}
    
    {% if error_message %}
      <span id="{{ name }}-error" role="alert" class="error-message">
        {{ error_message }}
      </span>
    {% endif %}
  </div>
{%- endmacro -%}
```

**Usage:**
```jinja2
{% from 'includes/_a11y_forms.html' import form_field %}

{{ form_field(
  name='email',
  label='Email Address',
  type='email',
  required=True,
  help_text='We\'ll never share your email'
) }}
```

### Button States

```html
<!-- Loading State -->
<button aria-busy="true" disabled>
  <span aria-hidden="true">⟳</span> Loading...
</button>

<!-- Disabled State -->
<button disabled aria-disabled="true">Disabled Action</button>

<!-- Active/Toggle State -->
<button aria-pressed="true">Bookmark (Active)</button>
```

---

## 5. Touch Target Sizing

**WCAG 2.5.5:** Minimum 44×44px (Level AAA)  
**Recommendation:** 48×48px desktop, 56×56px mobile

### CSS Implementation

```css
/* Base touch target size */
button, a, input[type="checkbox"], input[type="radio"] {
  min-width: 44px;
  min-height: 44px;
  /* Ensure minimum hit area even if visual size is smaller */
  padding: calc((44px - 1em) / 2) calc((44px - 1em) / 2);
}

/* Mobile-specific (larger targets) */
@media (max-width: 768px) {
  button, a, input[type="checkbox"], input[type="radio"] {
    min-width: 56px;
    min-height: 56px;
  }
}

/* Icon-only buttons need explicit sizing */
button.icon-only {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
}

/* Touch target testing overlay */
@media (--a11y-debug-mode) {
  button, a, input {
    outline: 2px solid rgba(255, 0, 0, 0.3);
  }
}
```

---

## 6. Form Validation Patterns

### Real-Time Validation

```html
<div class="form-group">
  <label for="username">Username</label>
  <input 
    id="username"
    type="text"
    aria-required="true"
    aria-invalid="false"
    aria-describedby="username-error username-hint"
    minlength="3"
    maxlength="20"
  />
  <small id="username-hint" class="hint">3-20 characters, alphanumeric only</small>
  <span id="username-error" role="alert" class="error" hidden>
    Username must be 3-20 characters
  </span>
</div>
```

### Validation JavaScript

```javascript
const input = document.getElementById('username');

input.addEventListener('blur', (event) => {
  const isValid = event.target.value.length >= 3;
  const errorSpan = document.getElementById('username-error');
  
  input.setAttribute('aria-invalid', !isValid);
  errorSpan.hidden = isValid;
  
  if (!isValid) {
    errorSpan.textContent = 'Username must be at least 3 characters';
  }
});
```

---

## 7. Prefers-Reduced-Motion Support

**WCAG 2.3.3:** Respect user's motion preferences (OS accessibility setting).

### Global CSS

```css
/* static/css/variables.css - ADD to existing file */
/* Default: Full animations */
:root {
  --animation-duration: 300ms;
  --animation-timing: ease-in-out;
  
  /* Existing SoulSpot transitions (already defined) */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.3s ease;
  --transition-bounce: 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* User prefers reduced motion: Disable animations */
@media (prefers-reduced-motion: reduce) {
  :root {
    --animation-duration: 0ms;
    --animation-timing: linear;
    
    /* Override existing transitions */
    --transition-fast: 0ms linear;
    --transition-normal: 0ms linear;
    --transition-bounce: 0ms linear;
  }

  *, *::before, *::after {
    animation-duration: 0ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0ms !important;
  }
  
  /* Disable specific SoulSpot animations */
  .slide-in-top,
  .slide-in-bottom,
  .slide-in-left,
  .slide-in-right,
  .pulse,
  .spin,
  .flip,
  .glow {
    animation: none !important;
  }
}
```

### Component-Level Example

```css
/* Pagination with Motion */
.pagination-item {
  transition: all var(--animation-duration) var(--animation-timing);
}

@media (prefers-reduced-motion: reduce) {
  .pagination-item {
    transition: none;
  }
}
```

---

## 8. Testing Procedures

### Phase 1: Keyboard-Only Navigation
1. Unplug mouse/trackpad
2. Navigate entire UI using Tab, Shift+Tab, Arrow keys, Enter, Escape
3. Verify:
   - All interactive elements reachable
   - Focus indicator always visible
   - No keyboard traps
   - Escape closes modals

### Phase 2: Screen Reader Testing (NVDA/VoiceOver)

**NVDA (Windows):**
```bash
# Download: https://www.nvaccess.org/download/
# Start: Press Insert+N to toggle
# Read all: Insert+Down
# Navigate: Tab, H (headings), L (links), B (buttons)
```

**VoiceOver (macOS/iOS):**
```bash
# Enable: Cmd+F5
# Start reading: VO+A (VO = Control+Option)
# Navigate: VO+Right Arrow
```

**Test checklist:**
- All text content read correctly
- Form labels announced
- Button purposes clear
- ARIA labels present and accurate
- Link text descriptive (avoid "click here")

### Phase 3: Motion Preferences

1. **Enable in OS:**
   - macOS: System Preferences > Accessibility > Display > Reduce Motion
   - Windows: Settings > Ease of Access > Display > Show animations
   - Linux: GNOME Settings > Accessibility > Animations > Off

2. **Test in DevTools:**
   ```javascript
   // Check if user prefers reduced motion
   const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
   console.log('Prefers reduced motion:', prefersReducedMotion);
   ```

### Phase 4: Touch Target Validation

```bash
# CSS-based validation (visual overlay)
# In DevTools console:
document.querySelectorAll('button, a, input').forEach(el => {
  const rect = el.getBoundingClientRect();
  const isSmall = rect.width < 44 || rect.height < 44;
  if (isSmall) {
    el.style.outline = '2px solid red';
    console.warn('Small touch target:', el, rect.width + 'x' + rect.height);
  }
});
```

### Phase 5: Color Contrast Validation

**Tools:**
- WebAIM Contrast Checker: https://webaim.org/resources/contrastchecker/
- Axe DevTools: Chrome extension
- WAVE: https://wave.webaim.org/

**Test:**
1. Extract hex colors from CSS
2. Check all text/background combinations
3. Target: 4.5:1 (AA), 7:1 (AAA)

### Phase 6: Form Validation

1. Test each form field with invalid input
2. Verify error messages appear with `role="alert"`
3. Test screen reader announces errors
4. Test keyboard can navigate to error message
5. Test Submit button disabled until valid

---

## 9. Resources & References

- **W3C WCAG 2.1:** https://www.w3.org/WAI/WCAG21/quickref/
- **ARIA Authoring Practices Guide:** https://www.w3.org/WAI/ARIA/apg/
- **The A11Y Project:** https://www.a11yproject.com/
- **WebAIM:** https://webaim.org/
- **web.dev Accessibility:** https://web.dev/accessibility/

---

## 10. Phase Integration Checklist

- [ ] Phase 1: Implement touch target sizing + prefers-reduced-motion CSS
- [ ] Phase 2: Add keyboard navigation + ARIA labels to all components
- [ ] Phase 3: Implement focus trap + test with screen reader
- [ ] Phase 4: Run axe-core scan + manual testing suite
