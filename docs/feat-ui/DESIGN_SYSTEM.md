# ⚠️ DEPRECATED - SoulSpot UI - Design System

## Document Information
- **Version**: 1.0 (DEPRECATED)
- **Last Updated**: 2025-11-26
- **Status**: ❌ DEPRECATED
- **Replaced By:** `src/soulspot/static/css/variables.css` (actual implementation) + [feat-ui-pro.md](./feat-ui-pro.md) Phase 1
- **Date Deprecated:** 9. Dezember 2025
- **Reason:** Color palette (#fe4155 red) conflicts with current implementation (#8b5cf6 violet). Design tokens now maintained in `variables.css` as single source of truth.
- **Related**: [ROADMAP.md](./ROADMAP.md) ❌ DEPRECATED, [TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md) ❌ DEPRECATED

**DO NOT USE THIS FILE. See `src/soulspot/static/css/variables.css` for current design tokens.**

---

<details>
<summary>Original Content (Archived)</summary>

---

## Introduction

The SoulSpot Design System combines the best aspects of **Lidarr's** functional UI patterns and **MediaManager's** modern aesthetics with SoulSpot's existing premium design language featuring glassmorphism and dark mode.

### Design Principles

1. **Clarity**: Clear visual hierarchy and intuitive interactions
2. **Consistency**: Unified design language across all components
3. **Efficiency**: Optimized for power users and quick actions
4. **Beauty**: Premium aesthetics with attention to detail
5. **Accessibility**: WCAG AA compliant, keyboard-friendly

---

## Color System

### Brand Colors

#### Primary - Vibrant Red/Pink
```css
--color-primary: #fe4155;
--color-primary-hover: #982633;
--color-primary-light: #ff6b7a;
--color-primary-dark: #d63547;
```

**Usage**: Primary actions, links, emphasis, brand elements

**Examples**:
- Primary buttons
- Active navigation items
- Important badges
- Links

#### Secondary - Deep Purple
```css
--color-secondary: #533c5b;
--color-secondary-hover: #332538;
--color-secondary-light: #6d4f76;
--color-secondary-dark: #3d2a44;
```

**Usage**: Secondary actions, accents, alternative emphasis

**Examples**:
- Secondary buttons
- Alternative badges
- Accent elements

### Semantic Colors

#### Success - Green
```css
--color-success: #10b981;
--color-success-light: #34d399;
--color-success-dark: #059669;
--color-success-bg: rgba(16, 185, 129, 0.1);
```

**Usage**: Success messages, completed states, positive actions

#### Warning - Amber
```css
--color-warning: #f59e0b;
--color-warning-light: #fbbf24;
--color-warning-dark: #d97706;
--color-warning-bg: rgba(245, 158, 11, 0.1);
```

**Usage**: Warning messages, caution states, pending actions

#### Danger - Red
```css
--color-danger: #ef4444;
--color-danger-light: #f87171;
--color-danger-dark: #dc2626;
--color-danger-bg: rgba(239, 68, 68, 0.1);
```

**Usage**: Error messages, destructive actions, failed states

#### Info - Blue
```css
--color-info: #3b82f6;
--color-info-light: #60a5fa;
--color-info-dark: #2563eb;
--color-info-bg: rgba(59, 130, 246, 0.1);
```

**Usage**: Informational messages, help text, neutral actions

### Neutral Colors (Dark Mode)

#### Background Shades
```css
--color-bg: #111827;           /* Main background */
--color-bg-alt: #0f172a;       /* Alternative background */
--color-bg-elevated: #1e293b;  /* Elevated surfaces */
```

#### Surface Shades
```css
--color-surface: #1f2937;      /* Cards, panels */
--color-surface-alt: #374151;  /* Alternative surface */
--color-surface-hover: #4b5563; /* Hover state */
```

#### Border Shades
```css
--color-border: #4b5563;       /* Default borders */
--color-border-light: #6b7280; /* Light borders */
--color-border-dark: #374151;  /* Dark borders */
```

#### Text Shades
```css
--color-text: #f9fafb;         /* Primary text */
--color-text-secondary: #e5e7eb; /* Secondary text */
--color-text-muted: #9ca3af;   /* Muted text */
--color-text-disabled: #6b7280; /* Disabled text */
```

---

### Neutral Colors (Light Mode) — MediaManager Reference

> **Note:** Light Mode colors are derived from the [MediaManager](https://github.com/maxdorninger/MediaManager) design system using OKLCH color space for perceptual uniformity.

#### Background Shades (Light)
```css
/* OKLCH Values → Hex Approximation */
--color-bg: #ffffff;           /* oklch(1 0 0) - Pure white, main background */
--color-bg-alt: #fafafa;       /* oklch(0.985 0 0) - Off-white, alternative */
--color-bg-elevated: #ffffff;  /* oklch(1 0 0) - Elevated surfaces */
```

#### Surface Shades (Light)
```css
--color-surface: #ffffff;      /* oklch(1 0 0) - Cards, panels */
--color-surface-alt: #f5f5f5;  /* oklch(0.97 0 0) - Secondary/muted bg */
--color-surface-hover: #f5f5f5; /* oklch(0.97 0 0) - Hover state */
```

#### Border Shades (Light)
```css
--color-border: #e5e5e5;       /* oklch(0.922 0 0) - Default borders */
--color-border-light: #ebebeb; /* oklch(0.94 0 0) - Lighter borders */
--color-border-dark: #d4d4d4;  /* oklch(0.87 0 0) - Darker borders */
```

#### Text Shades (Light)
```css
--color-text: #1a1a1a;         /* oklch(0.145 0 0) - Primary text */
--color-text-secondary: #333333; /* oklch(0.205 0 0) - Secondary text */
--color-text-muted: #888888;   /* oklch(0.556 0 0) - Muted text */
--color-text-disabled: #b3b3b3; /* oklch(0.708 0 0) - Disabled text */
```

#### Primary/Action Colors (Light)
```css
--color-primary-light: #333333;          /* oklch(0.205 0 0) - Primary action (dark) */
--color-primary-foreground-light: #fafafa; /* oklch(0.985 0 0) - Text on primary */
```

#### Destructive/Error (Light)
```css
--color-destructive-light: #d32f2f;      /* oklch(0.577 0.245 27.325) - Error/delete */
--color-destructive-foreground-light: #ffffff; /* Text on destructive */
```

#### Focus & Interaction (Light)
```css
--color-ring-light: #b3b3b3;   /* oklch(0.708 0 0) - Focus ring */
--color-input-light: #e5e5e5;  /* oklch(0.922 0 0) - Input borders/bg */
```

### Light Mode Full CSS Variable Set

```css
/* Light Mode Theme - MediaManager Reference */
:root[data-theme="light"],
.light {
  /* Backgrounds */
  --color-bg: #ffffff;
  --color-bg-alt: #fafafa;
  --color-bg-elevated: #ffffff;
  
  /* Surfaces */
  --color-surface: #ffffff;
  --color-surface-alt: #f5f5f5;
  --color-surface-hover: #f5f5f5;
  
  /* Borders */
  --color-border: #e5e5e5;
  --color-border-light: #ebebeb;
  --color-border-dark: #d4d4d4;
  
  /* Text */
  --color-text: #1a1a1a;
  --color-text-secondary: #333333;
  --color-text-muted: #888888;
  --color-text-disabled: #b3b3b3;
  
  /* Primary Actions */
  --color-primary: #333333;
  --color-primary-hover: #1a1a1a;
  --color-primary-foreground: #fafafa;
  
  /* Secondary */
  --color-secondary: #f5f5f5;
  --color-secondary-hover: #ebebeb;
  --color-secondary-foreground: #333333;
  
  /* Accent */
  --color-accent: #f5f5f5;
  --color-accent-foreground: #333333;
  
  /* Muted */
  --color-muted: #f5f5f5;
  --color-muted-foreground: #888888;
  
  /* Destructive */
  --color-destructive: #d32f2f;
  --color-destructive-foreground: #ffffff;
  
  /* Forms & Interaction */
  --color-input: #e5e5e5;
  --color-ring: #b3b3b3;
  
  /* Popover */
  --color-popover: #ffffff;
  --color-popover-foreground: #1a1a1a;
  
  /* Card */
  --color-card: #ffffff;
  --color-card-foreground: #1a1a1a;
}
```

### Light Mode Chart Colors (MediaManager)

```css
:root[data-theme="light"] {
  --color-chart-1: #f5a623;  /* oklch(0.646 0.222 41.116) - Orange-yellow */
  --color-chart-2: #4a90e2;  /* oklch(0.6 0.118 184.704) - Blue */
  --color-chart-3: #2c3e50;  /* oklch(0.398 0.07 227.392) - Dark blue */
  --color-chart-4: #d4e157;  /* oklch(0.828 0.189 84.429) - Yellow-green */
  --color-chart-5: #9ccc65;  /* oklch(0.769 0.188 70.08) - Green-yellow */
}
```

### Light Mode Sidebar Colors (MediaManager)

```css
:root[data-theme="light"] {
  --sidebar-background: #fafafa;          /* oklch(0.985 0 0) */
  --sidebar-foreground: #1a1a1a;          /* oklch(0.145 0 0) */
  --sidebar-primary: #333333;             /* oklch(0.205 0 0) */
  --sidebar-primary-foreground: #fafafa;  /* oklch(0.985 0 0) */
  --sidebar-accent: #f5f5f5;              /* oklch(0.97 0 0) */
  --sidebar-accent-foreground: #333333;   /* oklch(0.205 0 0) */
  --sidebar-border: #e5e5e5;              /* oklch(0.922 0 0) */
  --sidebar-ring: #b3b3b3;                /* oklch(0.708 0 0) */
}
```

### Dark vs Light Mode Comparison

| Color Role | Dark Mode | Light Mode | Notes |
|------------|-----------|------------|-------|
| **Background** | `#111827` | `#ffffff` | Inverted main bg |
| **Surface** | `#1f2937` | `#ffffff` | Cards, panels |
| **Surface Alt** | `#374151` | `#f5f5f5` | Secondary surfaces |
| **Border** | `#4b5563` | `#e5e5e5` | Dividers, outlines |
| **Text Primary** | `#f9fafb` | `#1a1a1a` | Main text |
| **Text Secondary** | `#e5e7eb` | `#333333` | Secondary text |
| **Text Muted** | `#9ca3af` | `#888888` | Muted/placeholder |
| **Primary Action** | `#fe4155` (SoulSpot Red) | `#333333` | Buttons, links |
| **Destructive** | `#ef4444` | `#d32f2f` | Error states |
| **Focus Ring** | `#fe4155` | `#b3b3b3` | Keyboard focus |

### Color Usage Guidelines

#### Contrast Ratios (WCAG AA)
- **Normal text**: Minimum 4.5:1
- **Large text** (18pt+): Minimum 3:1
- **UI components**: Minimum 3:1

#### WCAG Contrast Validation (Light Mode - MediaManager)

| Component/Pair | Colors | Contrast Ratio | WCAG AA | WCAG AAA | Notes |
|-----------|--------|----------|----------|----------|-------|
| **Layout** |
| Text on Background | #1a1a1a on #ffffff | 16.1:1 | ✅ Pass | ✅ Pass | Primary text |
| Muted Text on Background | #888888 on #ffffff | 3.5:1 | ✅ Pass (large) | ⚠️ Fail | Secondary/muted text |
| Border on Background | #e5e5e5 on #ffffff | 1.3:1 | ⚠️ Fail | ⚠️ Fail | Decorative only |
| **Buttons** |
| Primary Button Text | #fafafa on #333333 | 12.6:1 | ✅ Pass | ✅ Pass | Primary action |
| Destructive Button | #ffffff on #d32f2f | 4.6:1 | ✅ Pass | ⚠️ Fail | Error/delete action |
| Secondary Button Text | #333333 on #f5f5f5 | 10.5:1 | ✅ Pass | ✅ Pass | Secondary action |
| **Forms** |
| Input Text | #1a1a1a on #ffffff | 16.1:1 | ✅ Pass | ✅ Pass | User input |
| Input Border | #e5e5e5 on #ffffff | 1.3:1 | ⚠️ Fail | ⚠️ Fail | Decorative |
| Input Focus Ring | #b3b3b3 on #ffffff | 2.0:1 | ⚠️ Fail | ⚠️ Fail | Keyboard navigation |
| Disabled Input Text | #b3b3b3 on #f5f5f5 | 1.6:1 | ⚠️ Fail | ⚠️ Fail | Disabled state (intentional) |
| **Tables** |
| Table Text | #1a1a1a on #ffffff | 16.1:1 | ✅ Pass | ✅ Pass | Standard text |
| Table Header | #fafafa on #333333 | 12.6:1 | ✅ Pass | ✅ Pass | Header background |
| Table Row Hover | #333333 on #f5f5f5 | 10.5:1 | ✅ Pass | ✅ Pass | Hover state |
| **Alert/Status** |
| Error Alert | #d32f2f on #ffffff | 5.0:1 | ✅ Pass | ⚠️ Fail | Error messages |
| Success Alert | #059669 on #ffffff | 4.5:1 | ✅ Pass | ⚠️ Fail | Success messages |
| Warning Alert | #d97706 on #ffffff | 3.4:1 | ✅ Pass (large) | ⚠️ Fail | Warning messages |
| Info Alert | #2563eb on #ffffff | 4.5:1 | ✅ Pass | ⚠️ Fail | Info messages |
| **Cards & Modals** |
| Card Text | #1a1a1a on #ffffff | 16.1:1 | ✅ Pass | ✅ Pass | Card content |
| Card Border | #e5e5e5 on #ffffff | 1.3:1 | ⚠️ Fail | ⚠️ Fail | Decorative |
| Modal Backdrop | rgba(0,0,0,0.5) | - | - | - | Semi-transparent overlay |
| **Sidebar** |
| Sidebar Text | #1a1a1a on #fafafa | 15.6:1 | ✅ Pass | ✅ Pass | Navigation items |
| Sidebar Active | #fafafa on #333333 | 12.6:1 | ✅ Pass | ✅ Pass | Active item |
| Sidebar Hover | #333333 on #f5f5f5 | 10.5:1 | ✅ Pass | ✅ Pass | Hover state |

**Legend:**
- ✅ Pass = Meets WCAG requirement
- ⚠️ Fail = Does not meet ratio (acceptable for decorative elements, borders, disabled states)
- Ratios calculated using WCAG 2.1 relative luminance formula

#### Color Combinations
✅ **Recommended**:
- White text on primary/secondary backgrounds
- Dark text on light backgrounds
- Semantic colors with tinted backgrounds

⚠️ **Use with caution**:
- Primary color for small text on white
- Semantic colors for small text on white

---

## Typography

### Font Family

**Primary Font**: Inter  
**Source**: Google Fonts  
**Fallback**: System fonts

```css
--font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
```

**Why Inter?**
- Excellent readability at all sizes
- Wide range of weights
- Open-source and free
- Optimized for screens

### Font Sizes

| Name | Size | Rem | Usage |
|------|------|-----|-------|
| xs | 12px | 0.75rem | Small labels, captions, metadata |
| sm | 14px | 0.875rem | Body text (small), button text |
| base | 16px | 1rem | Body text, default size |
| lg | 18px | 1.125rem | Emphasized body text |
| xl | 20px | 1.25rem | H3, card titles |
| 2xl | 24px | 1.5rem | H2, section titles |
| 3xl | 30px | 1.875rem | H2 (large), page titles |
| 4xl | 36px | 2.25rem | H1, hero titles |
| 5xl | 48px | 3rem | Display titles |

### Font Weights

| Name | Weight | Usage |
|------|--------|-------|
| Normal | 400 | Body text, descriptions |
| Medium | 500 | Emphasis, labels |
| Semibold | 600 | Headings, buttons, strong emphasis |
| Bold | 700 | Extra strong emphasis, numbers |

### Line Heights

| Name | Value | Usage |
|------|-------|-------|
| Tight | 1.25 | Headings, titles |
| Normal | 1.5 | Body text, default |
| Relaxed | 1.625 | Long-form content |
| Loose | 2 | Spacious layouts |

### Typography Scale

```css
/* Headings */
h1 {
  font-size: var(--font-size-4xl);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-tight);
}

h2 {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-tight);
}

h3 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-tight);
}

/* Body text */
body {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-normal);
  line-height: var(--line-height-normal);
}

/* Small text */
.text-sm {
  font-size: var(--font-size-sm);
}

/* Muted text */
.text-muted {
  color: var(--color-text-muted);
}
```

---

## Spacing System

### Base Unit
**4px** - All spacing is based on multiples of 4px

### Spacing Scale

| Name | Size | Rem | Usage |
|------|------|-----|-------|
| xs | 4px | 0.25rem | Tight spacing, icon gaps |
| sm | 8px | 0.5rem | Small gaps, compact layouts |
| md | 16px | 1rem | Default spacing, padding |
| lg | 24px | 1.5rem | Section spacing |
| xl | 32px | 2rem | Large gaps, page margins |
| 2xl | 40px | 2.5rem | Extra large spacing |
| 3xl | 48px | 3rem | Section dividers |
| 4xl | 64px | 4rem | Page sections |

### Spacing Usage

```css
/* Padding */
.p-sm { padding: var(--space-sm); }
.p-md { padding: var(--space-md); }
.p-lg { padding: var(--space-lg); }

/* Margin */
.m-sm { margin: var(--space-sm); }
.m-md { margin: var(--space-md); }
.m-lg { margin: var(--space-lg); }

/* Gap (flexbox/grid) */
.gap-sm { gap: var(--space-sm); }
.gap-md { gap: var(--space-md); }
.gap-lg { gap: var(--space-lg); }
```

---

## Border Radius

### Radius Scale

| Name | Size | Usage |
|------|------|-------|
| sm | 0.25rem (4px) | Small elements, badges |
| md | 0.5rem (8px) | Buttons, inputs, cards |
| lg | 0.75rem (12px) | Large cards, panels |
| xl | 1rem (16px) | Modals, large containers |
| 2xl | 1.5rem (24px) | Hero sections |
| full | 9999px | Pills, circular elements |

### Usage Examples

```css
/* Buttons */
.btn {
  border-radius: var(--radius-md);
}

/* Cards */
.card {
  border-radius: var(--radius-lg);
}

/* Badges */
.badge {
  border-radius: var(--radius-full);
}
```

---

## Shadows & Elevation

### Shadow Scale

| Name | CSS Value | Usage |
|------|-----------|-------|
| sm | `0 1px 2px rgba(0, 0, 0, 0.05)` | Subtle elevation |
| md | `0 4px 6px rgba(0, 0, 0, 0.1)` | Cards, dropdowns |
| lg | `0 10px 15px rgba(0, 0, 0, 0.1)` | Modals, popovers |
| xl | `0 20px 25px rgba(0, 0, 0, 0.15)` | Heavy elevation |
| 2xl | `0 25px 50px rgba(0, 0, 0, 0.25)` | Maximum elevation |

### Glow Effects

```css
/* Primary glow */
.glow-primary {
  box-shadow: 0 0 20px rgba(254, 65, 85, 0.3);
}

/* Success glow */
.glow-success {
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);
}
```

### Glassmorphism

```css
.glass {
  background: rgba(31, 41, 55, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
```

---

## Transitions & Animations

### Transition Durations

| Name | Duration | Usage |
|------|----------|-------|
| fast | 150ms | Small UI changes, hover states |
| normal | 200ms | Default transitions |
| slow | 300ms | Complex animations, modals |

### Easing Functions

```css
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-in: cubic-bezier(0.4, 0, 1, 1);
```

### Common Animations

#### Fade In
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.animate-fade-in {
  animation: fadeIn 200ms ease-out;
}
```

#### Slide In
```css
@keyframes slideIn {
  from { 
    opacity: 0;
    transform: translateY(10px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-slide-in {
  animation: slideIn 300ms ease-out;
}
```

#### Pulse
```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
```

#### Spin
```css
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
```

---

## Layout System

### Grid System

```css
/* Grid columns */
.grid-cols-2 { display: grid; grid-template-columns: repeat(2, 1fr); }
.grid-cols-3 { display: grid; grid-template-columns: repeat(3, 1fr); }
.grid-cols-4 { display: grid; grid-template-columns: repeat(4, 1fr); }

/* Responsive grid */
.grid-responsive {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: var(--space-lg);
}
```

### Flexbox Utilities

```css
/* Flex containers */
.flex { display: flex; }
.flex-col { flex-direction: column; }
.flex-row { flex-direction: row; }

/* Alignment */
.items-center { align-items: center; }
.items-start { align-items: flex-start; }
.items-end { align-items: flex-end; }

.justify-center { justify-content: center; }
.justify-between { justify-content: space-between; }
.justify-end { justify-content: flex-end; }

/* Gap */
.gap-2 { gap: var(--space-sm); }
.gap-4 { gap: var(--space-md); }
.gap-6 { gap: var(--space-lg); }
```

### Container

```css
.container {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 var(--space-lg);
}
```

---

## Component Patterns

### Buttons

#### Variants

**Primary Button**:
```html
<button class="btn btn-primary">
  <i class="fa-solid fa-plus"></i>
  Add Playlist
</button>
```

```css
.btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
  color: white;
  border: none;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
```

**Secondary Button**:
```html
<button class="btn btn-secondary">
  Cancel
</button>
```

**Outline Button**:
```html
<button class="btn btn-outline">
  Learn More
</button>
```

**Ghost Button**:
```html
<button class="btn btn-ghost">
  <i class="fa-solid fa-ellipsis"></i>
</button>
```

#### Sizes

```html
<button class="btn btn-sm">Small</button>
<button class="btn">Default</button>
<button class="btn btn-lg">Large</button>
```

#### States

```html
<button class="btn" disabled>Disabled</button>
<button class="btn loading">
  <i class="fa-solid fa-spinner animate-spin"></i>
  Loading...
</button>
```

### Cards

#### Basic Card
```html
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Card Title</h3>
  </div>
  <div class="card-body">
    Card content goes here
  </div>
  <div class="card-footer">
    <button class="btn btn-primary">Action</button>
  </div>
</div>
```

#### Glass Card
```html
<div class="card glass">
  <!-- Content -->
</div>
```

#### Hover Card
```html
<div class="card card-hover">
  <!-- Content -->
</div>
```

```css
.card-hover:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}
```

### Badges

```html
<span class="badge badge-success">Active</span>
<span class="badge badge-warning">Pending</span>
<span class="badge badge-danger">Failed</span>
<span class="badge badge-info">Info</span>
<span class="badge badge-muted">Muted</span>
```

### Alerts

```html
<div class="alert alert-success">
  <i class="fa-solid fa-check-circle"></i>
  <div>
    <strong>Success!</strong>
    <p>Your playlist has been imported.</p>
  </div>
</div>
```

### Forms

#### Input
```html
<div class="form-group">
  <label for="name">Playlist Name</label>
  <input type="text" id="name" class="form-input" placeholder="Enter name">
</div>
```

#### Select
```html
<div class="form-group">
  <label for="quality">Quality</label>
  <select id="quality" class="form-select">
    <option>320kbps</option>
    <option>256kbps</option>
    <option>192kbps</option>
  </select>
</div>
```

#### Checkbox
```html
<label class="form-checkbox">
  <input type="checkbox">
  <span>Remember me</span>
</label>
```

---

## Icons

### Icon System
**Library**: Font Awesome 6 (Free)

### Icon Sizes

```css
.icon-xs { font-size: 0.75rem; }  /* 12px */
.icon-sm { font-size: 1rem; }     /* 16px */
.icon-md { font-size: 1.25rem; }  /* 20px */
.icon-lg { font-size: 1.5rem; }   /* 24px */
.icon-xl { font-size: 2rem; }     /* 32px */
```

### Common Icons

| Usage | Icon | Class |
|-------|------|-------|
| Music | 🎵 | `fa-solid fa-music` |
| Playlist | 📋 | `fa-solid fa-list` |
| Download | ⬇️ | `fa-solid fa-download` |
| Search | 🔍 | `fa-solid fa-search` |
| Settings | ⚙️ | `fa-solid fa-cog` |
| User | 👤 | `fa-solid fa-user` |
| Plus | ➕ | `fa-solid fa-plus` |
| Check | ✓ | `fa-solid fa-check` |
| Times | ✕ | `fa-solid fa-times` |
| Spotify | 🎧 | `fa-brands fa-spotify` |

---

## Responsive Design

### Breakpoints

| Name | Min Width | Usage |
|------|-----------|-------|
| sm | 640px | Mobile landscape |
| md | 768px | Tablet portrait |
| lg | 1024px | Tablet landscape, small desktop |
| xl | 1280px | Desktop |
| 2xl | 1536px | Large desktop |

### Mobile-First Approach

```css
/* Mobile first (default) */
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

### Responsive Utilities

```css
/* Hide on mobile */
.hidden-mobile {
  display: none;
}

@media (min-width: 768px) {
  .hidden-mobile {
    display: block;
  }
}

/* Show only on mobile */
.mobile-only {
  display: block;
}

@media (min-width: 768px) {
  .mobile-only {
    display: none;
  }
}
```

---

## Accessibility

### Focus States

```css
/* Default focus */
:focus {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Focus visible (keyboard only) */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Remove focus for mouse users */
:focus:not(:focus-visible) {
  outline: none;
}
```

### Skip Links

```html
<a href="#main-content" class="skip-link">
  Skip to main content
</a>
```

```css
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--color-primary);
  color: white;
  padding: var(--space-sm) var(--space-md);
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
```

### Screen Reader Only

```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
```

---

## Best Practices

### 1. **Use Semantic HTML**
```html
<!-- Good -->
<nav>
  <ul>
    <li><a href="/">Home</a></li>
  </ul>
</nav>

<!-- Bad -->
<div class="nav">
  <div class="nav-item">
    <a href="/">Home</a>
  </div>
</div>
```

### 2. **Provide Alternative Text**
```html
<!-- Good -->
<img src="album.jpg" alt="Album cover for Dark Side of the Moon">

<!-- Bad -->
<img src="album.jpg">
```

### 3. **Use ARIA When Needed**
```html
<button aria-label="Close modal" aria-expanded="true">
  <i class="fa-solid fa-times"></i>
</button>
```

### 4. **Maintain Color Contrast**
- Test with tools like WebAIM Contrast Checker
- Aim for WCAG AA (4.5:1 for normal text)

### 5. **Support Keyboard Navigation**
- All interactive elements should be keyboard accessible
- Provide visible focus indicators
- Implement logical tab order

---

## Resources

### Design Tools
- **Figma**: Design mockups and prototypes
- **Contrast Checker**: WebAIM Contrast Checker
- **Color Palette**: Coolors.co

### Development Tools
- **Tailwind CSS**: Utility-first CSS framework
- **Font Awesome**: Icon library
- **Google Fonts**: Inter font family

### Accessibility Tools
- **axe DevTools**: Accessibility testing
- **NVDA**: Screen reader (Windows)
- **VoiceOver**: Screen reader (macOS)

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-26  
**Status**: Draft - Awaiting Approval
