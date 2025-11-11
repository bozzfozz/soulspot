# Harmony-v1 Inspired Design Guidelines

## Overview

This design system is based on the harmony-v1 backup project, which uses a Wizarr-inspired theme. The design tokens have been extracted and adapted for use in SoulSpot Bridge, providing a cohesive and modern user interface.

## Source

- **Original Project**: [harmony-v1 backup](https://github.com/bozzfozz/V/tree/main/backup/harmony-v1)
- **Inspiration**: Wizarr theme
- **Font**: Inter (replacing any proprietary fonts from the original)

## Color Palette

### Brand Colors

#### Primary
- **Base**: `#fe4155` (Vibrant red/pink)
- **Hover**: `#982633` (Darker red)
- **Usage**: Primary actions, links, emphasis
- **CSS Variable**: `var(--color-primary)`

#### Secondary
- **Base**: `#533c5b` (Deep purple)
- **Hover**: `#332538` (Darker purple)
- **Usage**: Secondary actions, accents
- **CSS Variable**: `var(--color-secondary)`

#### Blue
- **Primary**: `#3b82f6` (Bright blue)
- **Secondary**: `#1d4ed8` (Darker blue)
- **Usage**: Information, alternative primary
- **CSS Variable**: `var(--color-blue-primary)`

### Semantic Colors

#### Success (Green)
- **Light**: `#10b981`
- **Dark**: `#34d399`
- **Usage**: Success messages, positive actions, completed states
- **CSS Variable**: `var(--color-success)`

#### Warning (Orange/Amber)
- **Light**: `#f59e0b`
- **Dark**: `#fbbf24`
- **Usage**: Warning messages, caution states
- **CSS Variable**: `var(--color-warning)`

#### Danger/Error (Red)
- **Light**: `#ef4444`
- **Dark**: `#f87171`
- **Usage**: Error messages, destructive actions, failed states
- **CSS Variable**: `var(--color-danger)`

#### Info (Blue)
- **Light**: `#3b82f6`
- **Dark**: `#60a5fa`
- **Usage**: Informational messages, help text
- **CSS Variable**: `var(--color-info)`

### Neutral Colors

#### Light Mode
- **Background**: `#f9fafb` - Main page background
- **Surface**: `#ffffff` - Cards, panels, elevated elements
- **Surface Alt**: `#f3f4f6` - Alternative surface, input backgrounds
- **Border**: `#e5e7eb` - Borders, dividers
- **Text**: `#111827` - Primary text
- **Text Muted**: `#6b7280` - Secondary text, descriptions

#### Dark Mode
- **Background**: `#111827` - Main page background
- **Surface**: `#1f2937` - Cards, panels, elevated elements
- **Surface Alt**: `#374151` - Alternative surface, input backgrounds
- **Border**: `#4b5563` - Borders, dividers
- **Text**: `#f9fafb` - Primary text
- **Text Muted**: `#9ca3af` - Secondary text, descriptions

## Typography

### Font Family

**Primary**: Inter  
**Fallback**: `-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif`

**Note**: Inter is a free and open-source font that replaces any proprietary fonts from the original project. It's loaded from Google Fonts.

```css
font-family: var(--font-family);
/* "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif */
```

### Font Sizes

| Size | Rem | Pixels | CSS Variable | Usage |
|------|-----|--------|--------------|-------|
| xs   | 0.75rem | 12px | `--font-size-xs` | Small labels, captions |
| sm   | 0.875rem | 14px | `--font-size-sm` | Body text (small), buttons |
| base | 1rem | 16px | `--font-size-base` | Body text, default |
| lg   | 1.125rem | 18px | `--font-size-lg` | Emphasized body text |
| xl   | 1.25rem | 20px | `--font-size-xl` | H3, card titles |
| 2xl  | 1.5rem | 24px | `--font-size-2xl` | H2 |
| 3xl  | 1.875rem | 30px | `--font-size-3xl` | H2 (large) |
| 4xl  | 2.25rem | 36px | `--font-size-4xl` | H1 |

### Font Weights

| Weight | Value | CSS Variable | Usage |
|--------|-------|--------------|-------|
| Normal | 400 | `--font-weight-normal` | Body text |
| Medium | 500 | `--font-weight-medium` | Emphasis |
| Semibold | 600 | `--font-weight-semibold` | Headings, buttons |
| Bold | 700 | `--font-weight-bold` | Strong emphasis |

### Line Heights

| Name | Value | CSS Variable | Usage |
|------|-------|--------------|-------|
| Tight | 1.25 | `--line-height-tight` | Headings |
| Normal | 1.5 | `--line-height-normal` | Body text |
| Relaxed | 1.625 | `--line-height-relaxed` | Long-form content |

## Spacing Scale

Based on a 4px base unit:

| Name | Rem | Pixels | CSS Variable |
|------|-----|--------|--------------|
| xs   | 0.25rem | 4px | `--space-xs` |
| sm   | 0.5rem | 8px | `--space-sm` |
| md   | 1rem | 16px | `--space-md` |
| lg   | 1.5rem | 24px | `--space-lg` |
| xl   | 2rem | 32px | `--space-xl` |
| 2xl  | 2.5rem | 40px | `--space-2xl` |

## Border Radius

| Name | Value | CSS Variable | Usage |
|------|-------|--------------|-------|
| sm   | 0.25rem | `--radius-sm` | Small elements |
| md   | 0.5rem | `--radius-md` | Buttons, inputs |
| lg   | 0.75rem | `--radius-lg` | Cards |
| xl   | 1rem | `--radius-xl` | Large containers |
| full | 9999px | `--radius-full` | Pills, badges |

## Shadows

| Name | CSS Variable | Usage |
|------|--------------|-------|
| sm   | `--shadow-sm` | Subtle elevation |
| md   | `--shadow-md` | Cards, dropdowns |
| lg   | `--shadow-lg` | Modals, popovers |
| xl   | `--shadow-xl` | Heavy elevation |

## Transitions

| Name | Duration | CSS Variable |
|------|----------|--------------|
| fast | 150ms | `--transition-fast` |
| normal | 200ms | `--transition-normal` |
| slow | 300ms | `--transition-slow` |

All transitions use `ease-in-out` easing.

## Components

### Buttons

**Base class**: `.harmony-btn`

**Variants**:
- `.harmony-btn-primary` - Primary actions (gradient background)
- `.harmony-btn-secondary` - Secondary actions
- `.harmony-btn-outline` - Outline style
- `.harmony-btn-danger` - Destructive actions

**Sizes**:
- `.harmony-btn-sm` - Small buttons
- Default - Medium buttons
- `.harmony-btn-lg` - Large buttons

**States**:
- `:hover` - Subtle lift and shadow
- `:disabled` - Reduced opacity, no pointer

### Cards

**Base class**: `.harmony-card`

**Structure**:
- `.harmony-card-header` - Header section with bottom border
- `.harmony-card-title` - Card title
- `.harmony-card-body` - Main content
- `.harmony-card-footer` - Footer section with top border

**Features**:
- Hover effect: lift and increased shadow
- Responsive padding
- Border and background

### Badges

**Base class**: `.harmony-badge`

**Variants**:
- `.harmony-badge-success` - Success state
- `.harmony-badge-warning` - Warning state
- `.harmony-badge-danger` - Danger state
- `.harmony-badge-info` - Info state
- `.harmony-badge-muted` - Neutral state

### Alerts

**Base class**: `.harmony-alert`

**Variants**:
- `.harmony-alert-success` - Success messages
- `.harmony-alert-warning` - Warning messages
- `.harmony-alert-danger` - Error messages
- `.harmony-alert-info` - Info messages

### Form Inputs

**Base class**: `.harmony-input`

**Features**:
- Focus state with border color and shadow
- Placeholder text styling
- Full width by default

## Accessibility

### WCAG Contrast Ratios

All text/background color combinations have been validated for accessibility:

#### Primary Color (#fe4155) on White
- **Contrast Ratio**: ~3.5:1
- **Rating**: ⚠️ AA for large text only (18pt+)
- **Recommendation**: Use white text on primary background, or ensure text is large enough

#### Text Colors on Backgrounds

**Light Mode**:
- Dark text (#111827) on light backgrounds (#f9fafb, #ffffff): ✅ AAA (>7:1)
- Muted text (#6b7280) on light backgrounds: ✅ AA (>4.5:1)

**Dark Mode**:
- Light text (#f9fafb) on dark backgrounds (#111827, #1f2937): ✅ AAA (>7:1)
- Muted text (#9ca3af) on dark backgrounds: ✅ AA (>4.5:1)

#### Semantic Colors

**Success**: 
- Light (#10b981) on white: ✅ AA (>4.5:1)
- Badge uses tinted background for better contrast

**Warning**: 
- Light (#f59e0b) on white: ⚠️ AA Large text only
- Badge uses tinted background for better contrast

**Danger**: 
- Light (#ef4444) on white: ⚠️ AA Large text only
- Badge uses tinted background for better contrast

### Recommendations

1. **Primary Action Text**: Always use white text on primary color backgrounds
2. **Body Text**: Use `--color-text` for primary text, `--color-text-muted` for secondary
3. **Large Text**: For headings and emphasized text, all color combinations meet AA
4. **Interactive Elements**: Ensure focus states are visible with border and shadow
5. **Reduced Motion**: Theme respects `prefers-reduced-motion` media query

### Known Issues

⚠️ **Primary color contrast**: The primary brand color (#fe4155) has limited contrast on white backgrounds. To maintain accessibility:
- Use it for large text (18pt+/24px+) only
- Use white text when primary is the background
- Prefer the badge/alert tinted backgrounds for small text

## Usage Examples

### Using CSS Variables

```css
.my-element {
  color: var(--color-text);
  background: var(--color-surface);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
```

### Using Component Classes

```html
<!-- Button -->
<button class="harmony-btn harmony-btn-primary">
  Click me
</button>

<!-- Card -->
<div class="harmony-card">
  <div class="harmony-card-header">
    <h3 class="harmony-card-title">Card Title</h3>
  </div>
  <div class="harmony-card-body">
    Card content goes here
  </div>
</div>

<!-- Badge -->
<span class="harmony-badge harmony-badge-success">
  Active
</span>
```

### Including the Theme

In your Jinja2 template:

```html
<head>
  {% include 'includes/_theme.html' %}
</head>
```

### Tailwind Integration

To extend your existing Tailwind config with Harmony colors:

```js
const harmonyTheme = require('./design/tailwind.theme.js');

module.exports = {
  theme: {
    extend: {
      ...harmonyTheme.extend
    }
  }
}
```

## Demo Page

Visit `/theme-sample` to see all components and design tokens in action.

## Design Token Files

- **Colors**: `design/tokens/colors.json`
- **Typography**: `design/tokens/typography.json`
- **Tailwind Extension**: `design/tailwind.theme.js`
- **CSS Theme**: `src/soulspot/static/css/theme.css`

## License Note

The design tokens were extracted from the harmony-v1 backup project (team-owned). The Inter font is licensed under the SIL Open Font License and is free to use.
