# UI Documentation

**Category:** UI/UX Design  
**Last Updated:** 2025-12-30  
**Status:** ✅ v2.0 Current

---

## Quick Start

This section covers SoulSpot's **UI redesign architecture** including:
- Atomic Design System (Atoms → Molecules → Organisms → Templates → Pages)
- Service-agnostic components (90%+ code reuse across Spotify/Tidal/Deezer)
- WCAG 2.1 AA accessibility compliance
- HTMX-first interactivity (minimal JavaScript)
- Build-less CSS (no npm/webpack)

**Start here:** [UI Redesign Master Plan](./feat-ui-pro.md)

---

## Current Documentation (v2.0)

| Document | Description | Status |
|----------|-------------|--------|
| **[UI Redesign Master Plan](./feat-ui-pro.md)** | 4-phase implementation plan (Foundation → Core → Pro → Polish) | 🎯 Ready |
| **[UI Architecture](./ui-architecture-principles.md)** | Design principles, Atomic Design, service-agnostic patterns | ✅ Complete |
| **[Component Library](./component-library.md)** | 50+ reusable Jinja2 components reference | ✅ Complete |
| **[Accessibility Guide](./accessibility-guide.md)** | WCAG 2.1 compliance, FocusTrap, keyboard navigation | ✅ Complete |
| **[Quality Gates A11Y](./quality-gates-a11y.md)** | Pre-PR testing (axe-core, Lighthouse, WAVE) | ✅ Complete |
| **[Service-Agnostic Strategy](./service-agnostic-strategy.md)** | Multi-service UI design (Spotify/Tidal/Deezer) | ✅ Complete |
| **[Router Refactoring](./ui-router-refactoring.md)** | UIRenderingService migration plan | ⏳ Postponed |
| **[Library Artists View](./library-artists-view.md)** | Hybrid local + followed artists view | ✅ Design Approved |

---

## Implementation Phases

### Phase 1: Foundation (2-3 days)
- ✅ CSS design tokens (`variables.css`)
- ✅ Touch target sizing (44×44px minimum)
- ✅ Animations (`animations.css`)
- ✅ Theme toggle (light/dark)

### Phase 2: Core Components (5-7 days)
- ✅ Layout components (page header, media grid)
- ✅ Data display (media cards, artist cards, service badges)
- ✅ Forms & inputs (search bar, text input, select, checkbox)
- ✅ FocusTrap accessibility (modal dialogs)
- ✅ Keyboard navigation

### Phase 3: Pro Features (3-5 days)
- ⏳ Command Palette (Cmd+K / Ctrl+K)
- ⏳ Advanced filtering (multi-select, service badges)
- ⏳ Mobile bottom sheets (responsive modals)
- ⏳ Service-agnostic naming (track-card, artist-card vs spotify-track-card)

### Phase 4: Polish & Integration (2-3 days)
- ⏳ A11Y automated testing (axe-core, Lighthouse)
- ⏳ Manual testing (keyboard, screen reader, color contrast)
- ⏳ Quality gates CI/CD
- ⏳ Documentation finalization

**Total Estimated Effort:** 12-18 days

---

## Technology Stack

### CSS
- **Pure CSS** (no Sass/Less/PostCSS)
- **Custom Properties** (CSS variables for theming)
- **Animations** (Pure CSS keyframes, no JavaScript)
- **Responsive** (Mobile-first, CSS Grid)

### JavaScript
- **HTMX v1.9.10** (declarative interactivity)
- **Vanilla JS** (focus trap, theme toggle, keyboard shortcuts)
- **No npm build** (no Webpack/Vite/Rollup)

### Templates
- **Jinja2** (macro-based component system)
- **Atomic Design** (atoms/molecules/organisms/templates)
- **Service-agnostic** (95% component reuse)

### Build Tools
- **None** (build-less approach)

### Package Manager
- **Poetry** (Python dependencies only)
- **NO npm** (no Node.js build pipeline)

### Primary Color
- **Violet** (`#8b5cf6`)

---

## Documentation Structure

```
09-ui/
├── feat-ui-pro.md              # Master Plan (4 phases, design tokens, glassmorphism)
├── ui-architecture-principles.md  # Atomic Design, service-agnostic, HTMX-first
├── component-library.md        # 50+ component reference (layout/data/forms/feedback/nav)
├── accessibility-guide.md      # WCAG 2.1 AA (FocusTrap, keyboard, ARIA, color contrast)
├── quality-gates-a11y.md       # A11Y testing (axe-core, Lighthouse, WAVE, CI/CD)
├── service-agnostic-strategy.md  # Multi-service 90%+ reuse (Spotify/Tidal/Deezer)
├── ui-router-refactoring.md    # UIRenderingService migration (postponed)
├── library-artists-view.md     # Hybrid library (local + followed artists, progress bars)
└── README.md                   # This file
```

---

## Next Steps

1. **Read:** [UI Redesign Master Plan](./feat-ui-pro.md) for complete implementation guide
2. **Implement:** Phase 1 (Foundation) → Phase 2 (Core Components) → Phase 3 (Pro Features) → Phase 4 (Polish)
3. **Test:** [Quality Gates A11Y](./quality-gates-a11y.md) before each PR
4. **Deploy:** Incremental rollout, backwards compatible

---

## Related Documentation

- [Component Library (Storybook-style)](../08-guides/component-library.md) - Original component documentation
- [Library Management](../07-library/README.md) - Library system overview
- [Plugin System ADR](../02-architecture/plugin-system.md) - Hybrid library architecture
