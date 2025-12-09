# Onboarding UI Visual Guide

> **⚠️ DEPRECATED:** This file is superseded by **onboarding-ui-overview.md** (comprehensive guide).

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

## Screenshots & Visual Mockups

Since we cannot take actual screenshots in this environment, here's a detailed visual description of the onboarding UI states:

---

## State 1: Initial Page Load

```
┌─────────────────────────────────────────────────────────────────┐
│                          [Skip Link]                             │
│                                                                   │
│                                                                   │
│                    ┌──────────────────────┐                      │
│                    │                      │                      │
│                    │         🎵           │  ← Logo (4rem size)  │
│                    │                      │                      │
│                    └──────────────────────┘                      │
│                                                                   │
│              Willkommen bei SoulSpot                             │
│         (Heading 2, semibold, centered)                          │
│                                                                   │
│  Verbinde Spotify, um Songs und Playlists zu synchronisieren.   │
│             (Subtitle, muted color, centered)                    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                                                          │    │
│  │                    ⟳  (Loading Spinner)                 │    │
│  │                                                          │    │
│  │          Verbindungsstatus wird geprüft...              │    │
│  │                 (Muted text, centered)                   │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│           [  Weiter  ]  [  Nicht jetzt  ]                       │
│         (Disabled)      (Ghost button)                           │
│                                                                   │
│  ─────────────────────────────────────────────────────────       │
│                                                                   │
│  Die Spotify-Verbindung ist erforderlich, um Playlists zu       │
│  synchronisieren und Songs herunterzuladen. Du kannst diesen     │
│  Schritt auch später in den Einstellungen durchführen.          │
│         (Small muted text, centered)                             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Colors (UI 1.0 Design System):**
- Background: `var(--ui-bg)` - Light: #f9fafb, Dark: #111827
- Card: `var(--ui-surface)` - Light: #ffffff, Dark: #1f2937
- Primary Button: `var(--ui-primary)` - #fe4155
- Text: `var(--ui-text)` - Light: #111827, Dark: #f9fafb
- Muted Text: `var(--ui-text-muted)` - Light: #6b7280, Dark: #9ca3af

---

## State 2: After Clicking "Weiter" - Not Connected

```
┌─────────────────────────────────────────────────────────────────┐
│                          [Skip Link]                             │
│                                                                   │
│                    ┌──────────────────────┐                      │
│                    │         🎵           │                      │
│                    └──────────────────────┘                      │
│                                                                   │
│              Willkommen bei SoulSpot                             │
│  Verbinde Spotify, um Songs und Playlists zu synchronisieren.   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ℹ️  Spotify noch nicht verbunden                       │    │
│  │                                                          │    │
│  │      Klicke auf "Spotify verbinden", um fortzufahren.   │    │
│  │                                                          │    │
│  │                                                          │    │
│  │              [ 🎵 Spotify verbinden ]                   │    │
│  │                (Success/Green button)                    │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│           [  Weiter  ]  [  Nicht jetzt  ]                       │
│          (Enabled)      (Ghost button)                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Info Alert Colors:**
- Background: `var(--ui-info-light)` - rgba(59, 130, 246, 0.1)
- Border: `var(--ui-info-border)` - rgba(59, 130, 246, 0.2)
- Icon: `var(--ui-info)` - #3b82f6
- Text: `var(--ui-text)` - Normal text color

**Success Button (Spotify Connect):**
- Background: `var(--ui-success)` - #10b981
- Text: white
- Icon: Spotify logo (white)

---

## State 3: After Clicking "Weiter" - Already Connected

```
┌─────────────────────────────────────────────────────────────────┐
│                          [Skip Link]                             │
│                                                                   │
│                    ┌──────────────────────┐                      │
│                    │         🎵           │                      │
│                    └──────────────────────┘                      │
│                                                                   │
│              Willkommen bei SoulSpot                             │
│  Verbinde Spotify, um Songs und Playlists zu synchronisieren.   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ✅  Spotify ist bereits verbunden!                     │    │
│  │                                                          │    │
│  │      Weiterleitung zum Dashboard...                     │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│           [  Weiter  ]  [  Nicht jetzt  ]                       │
│                                                                   │
│  (Redirects to / after 1.5 seconds)                              │
└─────────────────────────────────────────────────────────────────┘
```

**Success Alert Colors:**
- Background: `var(--ui-success-light)` - rgba(16, 185, 129, 0.1)
- Border: `var(--ui-success-border)` - rgba(16, 185, 129, 0.2)
- Icon: `var(--ui-success)` - #10b981
- Text: `var(--ui-text)` - Normal text color

---

## Component Details

### Card Dimensions

- **Max Width:** 768px (`.ui-container-md`)
- **Margin Top:** 5rem (80px)
- **Card Padding:**
  - Header: 2.5rem 1.5rem 1.5rem (top, horizontal, bottom)
  - Body: 1.5rem (all sides, via `.ui-card-body`)
  - Footer: 1.5rem (all sides, via `.ui-card-footer`)
- **Border Radius:** `var(--ui-radius-lg)` - 0.5rem (8px)
- **Shadow:** `var(--ui-shadow-sm)` - Subtle shadow
- **Border:** 1px solid `var(--ui-border)`

### Logo

- **Size:** 4rem (64px)
- **Margin Bottom:** 1rem
- **Current:** 🎵 emoji
- **Future:** Replace with actual SoulSpot logo SVG

### Typography

- **Heading:** `.ui-heading-2`
  - Font Size: `var(--ui-text-3xl)` - 1.875rem (30px)
  - Font Weight: `var(--ui-font-bold)` - 700
  - Margin Bottom: 0.5rem

- **Subtitle:** `.ui-card-subtitle`
  - Font Size: `var(--ui-text-sm)` - 0.875rem (14px)
  - Color: `var(--ui-text-muted)` - #6b7280 (light mode)
  - Margin Top: `var(--ui-space-1)` - 0.25rem

### Buttons

- **Primary Button (Weiter):**
  - Background: `var(--ui-primary)` - #fe4155
  - Hover: `var(--ui-primary-hover)` - #982633
  - Text: white
  - Padding: `var(--ui-space-2) var(--ui-space-4)` - 0.5rem 1rem
  - Border Radius: `var(--ui-radius-lg)` - 0.5rem

- **Ghost Button (Nicht jetzt):**
  - Background: transparent
  - Text: `var(--ui-text)` - #111827
  - Hover Background: `var(--ui-surface-alt)` - #f3f4f6
  - Same padding as primary

- **Success Button (Spotify verbinden):**
  - Background: `var(--ui-success)` - #10b981
  - Hover: `var(--ui-success-dark)` - #059669
  - Text: white
  - Icon: 20x20 Spotify logo SVG

### Loading Spinner

- **Size:** `.ui-spinner-lg`
  - Width/Height: 2rem (32px)
  - Border: 3px
- **Colors:**
  - Border: `var(--ui-surface-alt)` - #f3f4f6
  - Border Top: `var(--ui-primary)` - #fe4155
- **Animation:** Spin 0.6s linear infinite

### Alert Messages

- **Structure:**
  ```
  ┌────────────────────────────────────────┐
  │  [Icon]  Title                        │
  │          Message text                  │
  └────────────────────────────────────────┘
  ```

- **Padding:** `var(--ui-space-4)` - 1rem
- **Border Radius:** `var(--ui-radius-lg)` - 0.5rem
- **Border:** 1px solid semantic border color
- **Gap between icon and content:** `var(--ui-space-3)` - 0.75rem

---

## Responsive Behavior

### Mobile (< 640px)

- Container padding reduces to `var(--ui-space-3)` - 0.75rem
- Card margins adjust
- Buttons may stack vertically (natural flexbox behavior)
- Logo size remains same for visual impact

### Tablet (640px - 768px)

- Container centered with side margins
- Card width expands up to 768px
- All spacing at standard values

### Desktop (> 768px)

- Container max-width: 768px, centered
- Large white space around card (visual focus)
- All elements at full size

---

## Dark Mode

All UI 1.0 components automatically support dark mode via CSS custom properties:

**Dark Mode Colors:**
- Background: #111827 (dark gray)
- Card Surface: #1f2937 (lighter dark gray)
- Text: #f9fafb (off-white)
- Borders: #4b5563 (medium gray)
- Primary: #fe4155 (same as light mode)
- Success: #34d399 (brighter green)
- Info: #60a5fa (brighter blue)

**Activation:**
- Automatic: `@media (prefers-color-scheme: dark)`
- Manual: `.dark` class on `<html>` or `<body>`
- Storage: `localStorage.getItem('theme')`

---

## Accessibility Features Visual Indicators

### Skip Link
```
┌─────────────────────────────────────┐
│  [Zum Hauptinhalt springen]  ← Initially off-screen (top: -40px)
└─────────────────────────────────────┘
           ↓ On keyboard focus (Tab)
┌─────────────────────────────────────┐
│  [Zum Hauptinhalt springen]  ← Visible (top: 0.5rem)
└─────────────────────────────────────┘
```

**Styling:**
- Background: `var(--ui-primary)` - #fe4155
- Text: white
- Padding: `var(--ui-space-2) var(--ui-space-4)`
- Border Radius: `var(--ui-radius-base)` - 0.25rem
- Z-Index: `var(--ui-z-tooltip)` - 1070

### Focus Indicators

All interactive elements have visible focus ring:
- Outline: 2px solid `var(--ui-primary)` - #fe4155
- Outline Offset: 2px
- Applied via `:focus-visible` pseudo-class

---

## Animation & Transitions

### Button Hover
- Transform: `translateY(-1px)` (primary button)
- Box Shadow: `var(--ui-shadow-md)` (elevation)
- Transition: `var(--ui-transition-base)` - 200ms

### Card Entrance
- No entrance animation (static card)
- Shadow increases on hover for regular cards

### Spinner Animation
- Rotation: 360deg
- Duration: 0.6s
- Timing: linear
- Iteration: infinite

### Page Transition to Dashboard
- JavaScript `window.location.href = '/'` after 1.5s delay
- No CSS transition (full page reload)

---

## Color Palette Reference

From UI 1.0 Design System (`theme.css`):

**Primary Colors:**
- Primary: `#fe4155` (red/pink)
- Primary Hover: `#982633` (darker red)
- Primary Foreground: `#ffffff` (white)

**Semantic Colors:**
- Success: `#10b981` (green)
- Success Dark: `#059669`
- Info: `#3b82f6` (blue)
- Info Dark: `#2563eb`
- Warning: `#f59e0b` (orange)
- Danger: `#ef4444` (red)

**Neutral Colors (Light Mode):**
- Background: `#f9fafb` (very light gray)
- Surface: `#ffffff` (white)
- Surface Alt: `#f3f4f6` (light gray)
- Border: `#e5e7eb` (gray)
- Text: `#111827` (near black)
- Text Muted: `#6b7280` (medium gray)

---

## Comparison: Before vs After Implementation

### Before (No Onboarding)
- Users land directly on dashboard
- No Spotify connection prompt
- Confusing if no playlists exist
- No clear next steps

### After (With Onboarding)
- Clear welcome screen
- Spotify connection status check
- Guided OAuth flow
- Option to skip for later
- Smooth transition to dashboard
- Professional first impression

</details>

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-16  
**Author:** Copilot AI Agent (Frontend Specialist)
