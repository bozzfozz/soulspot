# ⚠️ DEPRECATED - SoulSpot New UI - MediaManager-Inspired Design

> **Status:** ❌ DEPRECATED  
> **Replaced By:** `src/soulspot/static/css/variables.css` (actual design tokens) + [feat-ui-pro.md](./feat-ui-pro.md) Phase 1  
> **Date Deprecated:** 9. Dezember 2025  
> **Reason:** Design analysis from external screenshot. Actual design tokens now defined in `variables.css` with violet (#8b5cf6) primary color, not MediaManager's palette.

**DO NOT USE THIS FILE. See `src/soulspot/static/css/variables.css` for current design system.**

---

<details>
<summary>Original Content (Archived)</summary>

## Design Analysis from MediaManager Screenshot

### Layout Structure
- **Sidebar Navigation** (left, ~240px width)
  - Dark background
  - Icon + text navigation items
  - Active state highlighting
  - Bottom user section
  
- **Main Content Area**
  - Top stats cards (4 columns)
  - Content grid below
  - Generous spacing
  - Card-based design

### Color Palette (from MediaManager)
```css
/* Dark Theme */
--bg-primary: #0f0f0f;           /* Main background */
--bg-secondary: #1a1a1a;         /* Cards, panels */
--bg-tertiary: #242424;          /* Hover states */

/* Accent */
--accent-primary: #307FFF;       /* Blue accent (MediaManager) */
--accent-hover: #5094FF;

/* Text */
--text-primary: #ffffff;
--text-secondary: #a0a0a0;
--text-muted: #6b6b6b;

/* Borders */
--border-color: #2a2a2a;
```

### Typography
- Clean, modern sans-serif
- Clear hierarchy
- Good contrast

### Components Identified
1. **Sidebar**
   - Navigation items with icons
   - Active state (blue highlight)
   - User profile at bottom

2. **Stats Cards**
   - Icon + number + label
   - 4-column grid
   - Subtle background
   - Hover effects

3. **Content Cards**
   - Poster/cover image
   - Title
   - Metadata
   - Hover overlay with actions

4. **Buttons**
   - Primary (blue)
   - Secondary (outlined)
   - Icon buttons

## New UI Structure for SoulSpot

### Directory Structure
```
src/soulspot/
├── templates/
│   ├── new-ui/                    # NEW: Separate UI
│   │   ├── base.html             # New base layout
│   │   ├── components/
│   │   │   ├── sidebar.html
│   │   │   ├── topbar.html
│   │   │   ├── stat-card.html
│   │   │   ├── media-card.html
│   │   │   ├── table.html
│   │   │   └── modal.html
│   │   └── pages/
│   │       ├── dashboard.html
│   │       ├── library.html
│   │       ├── playlists.html
│   │       ├── downloads.html
│   │       ├── search.html
│   │       └── settings.html
├── static/
│   ├── new-ui/                    # NEW: Separate assets
│   │   ├── css/
│   │   │   ├── main.css
│   │   │   ├── variables.css
│   │   │   ├── components.css
│   │   │   └── pages.css
│   │   └── js/
│   │       ├── app.js
│   │       └── components.js
```

### Key Differences from Current SoulSpot UI
1. **Darker Theme** - More like MediaManager's dark mode
2. **Blue Accent** - Instead of red/pink (or keep SoulSpot's red but use MediaManager's layout)
3. **Card-Based** - Everything in cards
4. **Grid Layouts** - Consistent grid system
5. **Simpler** - Less glassmorphism, more solid backgrounds

## Implementation Strategy

### Option 1: Keep SoulSpot Colors + MediaManager Layout
- Use SoulSpot's #fe4155 (red) as accent
- Use MediaManager's layout and structure
- Best of both worlds

### Option 2: Full MediaManager Clone
- Use MediaManager's blue (#307FFF)
- Exact layout replication
- Adapt for music instead of movies/TV

**Recommendation**: Option 1 - MediaManager layout with SoulSpot's red accent color

## Next Steps
1. Create new base.html with MediaManager-style layout
2. Build sidebar component
3. Create stat cards
4. Build media card component
5. Implement dashboard page
