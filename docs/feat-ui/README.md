# # SoulSpot UI Redesign v2.0

**Status:** ✅ Active Development  
**Version:** 2.0  
**Last Updated:** 9. Dezember 2025

---

## 🚀 Quick Start

### Current Documentation (v2.0)

| Document | Purpose | Status |
|----------|---------|--------|
| **[feat-ui-pro.md](./feat-ui-pro.md)** | 🎯 Master Plan (4 Phases) | ✅ Active |
| **[ACCESSIBILITY_GUIDE.md](./ACCESSIBILITY_GUIDE.md)** | A11Y Implementation (WCAG 2.1) | ✅ Active |
| **[SERVICE_AGNOSTIC_STRATEGY.md](./SERVICE_AGNOSTIC_STRATEGY.md)** | Multi-Service Architecture | ✅ Active |
| **[QUALITY_GATES_A11Y.md](./QUALITY_GATES_A11Y.md)** | Testing & Quality Enforcement | ✅ Active |

### Implementation Phases

**Phase 1: Foundation (CSS Design Tokens & Variables)**
- Design tokens in `static/css/variables.css`
- Touch target sizing (44×44px minimum)
- prefers-reduced-motion support
- Animation @keyframes (Magic UI patterns, pure CSS)

**Phase 2: Core Components (Layout, Data Display, Forms)**
- Focus trap implementation (HTMX integration)
- Keyboard navigation patterns
- ARIA labels & roles
- Jinja2 component macros

**Phase 3: Pro Features (Command Palette, Mobile Bottom Sheets)**
- Cmd+K command palette
- Service-agnostic component naming
- ISRC-based cross-service matching

**Phase 4: Polish & Integration**
- A11Y automated testing (axe-core, Lighthouse)
- Manual testing procedures (keyboard-only, screen reader)
- Quality gates CI/CD (GitHub Actions)

---

## 📂 Documentation Structure

### ✅ Active Documents (v2.0)

```
docs/feat-ui/
├── feat-ui-pro.md                    # 🎯 START HERE - Master Plan v2.0
├── ACCESSIBILITY_GUIDE.md            # A11Y patterns & testing
├── SERVICE_AGNOSTIC_STRATEGY.md      # Multi-service architecture
└── QUALITY_GATES_A11Y.md             # Quality enforcement
```

### ❌ Deprecated Documents (v1.0)

<details>
<summary>Click to view deprecated files (DO NOT USE)</summary>

**Replaced by feat-ui-pro.md:**
- ❌ README.md (this file, v1.0 content)
- ❌ ROADMAP.md
- ❌ IMPLEMENTATION_GUIDE.md
- ❌ INTEGRATION_GUIDE.md
- ❌ TECHNICAL_SPEC.md
- ❌ NAVIGATION.md
- ❌ VISUAL_OVERVIEW.md

**Replaced by ACCESSIBILITY_GUIDE.md:**
- ❌ (no previous A11Y docs)

**Replaced by SERVICE_AGNOSTIC_STRATEGY.md:**
- ❌ BACKEND_ALIGNMENT.md

**Replaced by QUALITY_GATES_A11Y.md:**
- ❌ (no previous quality docs)

**Wrong Technology Stack:**
- ❌ MAGIC_UI_INTEGRATION.md (assumes Tailwind CSS - NOT USED)
- ❌ DASHBOARD_MAGIC_UI_PLAN.md (assumes Tailwind CSS - NOT USED)
- ❌ frontend-agent.md (assumes Tailwind CSS - NOT USED)

**Outdated Design:**
- ❌ DESIGN_SYSTEM.md (red #fe4155 → actual: violet #8b5cf6)
- ❌ COMPONENT_LIBRARY.md (theoretical → actual: templates/includes/)
- ❌ FRONTEND_COMPLETE.md (prototype/ never integrated)
- ❌ MEDIAMANAGER_ANALYSIS.md (external reference → actual: variables.css)

</details>

---

## 🎨 Actual Technology Stack

**CSS:** Pure CSS custom properties (`static/css/variables.css`)  
**JavaScript:** HTMX v1.9.10 + Vanilla JS (`static/js/app.js`)  
**Templates:** Jinja2 macros (`templates/includes/_components.html`)  
**Build Tools:** None (build-less approach)  
**Package Manager:** poetry (Python only, NO npm)  
**Primary Color:** Violet #8b5cf6 (not red #fe4155)

---

## 📋 Next Steps

1. **Read Master Plan:** [feat-ui-pro.md](./feat-ui-pro.md)
2. **Implement Phase 1:** Design tokens + animations
3. **Implement Phase 2:** Components + A11Y patterns
4. **Test:** Run quality gates (`scripts/quality-gates-a11y.sh`)
5. **Deploy:** Incremental rollout per feat-ui-pro.md

---

## 🗑️ Cleanup Instructions

**Delete deprecated files:**
```bash
cd docs/feat-ui/
# Review deprecated files first
grep -l "DEPRECATED" *.md

# Delete after review (BACKUP FIRST!)
# rm ROADMAP.md IMPLEMENTATION_GUIDE.md INTEGRATION_GUIDE.md ...
```

---

<details>
<summary>Original README.md v1.0 (Archived)</summary>

Welcome to the SoulSpot UI Redesign project! This folder contains everything you need to understand, run, and implement the new modern Web UI.

## 🚀 Quick Start

### 1. See How It Looks (Prototype)
We have built a **complete, interactive frontend prototype**. You can run it right now to see the design in action.

👉 **[Go to Prototype](./prototype/README.md)** (Instructions to run)

### 2. Know What To Do (Integration)
Ready to implement this into the main app? We have a step-by-step guide.

- **[Integration Guide](./INTEGRATION_GUIDE.md)**: Step-by-step migration plan.
- **[Backend Alignment](./BACKEND_ALIGNMENT.md)**: Mapping new UI to existing backend architecture.
- **[Frontend Agent](./frontend-agent.md)**: Rules for the AI Frontend Engineer.

---

## 📚 Documentation Index

### Core Documents

| Document | Description |
|----------|-------------|
| **[FRONTEND_COMPLETE.md](./FRONTEND_COMPLETE.md)** | **Start Here**: Overview of the completed frontend work. |
| **[NAVIGATION.md](./NAVIGATION.md)** | Map of all pages and how they connect. |
| **[DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)** | Colors, typography, and UI rules. |
| **[COMPONENT_LIBRARY.md](./COMPONENT_LIBRARY.md)** | Reference for all UI components (Cards, Buttons, etc). |

### Technical Details

| Document | Description |
|----------|-------------|
| **[TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md)** | Architecture and technical requirements. |
| **[ROADMAP.md](./ROADMAP.md)** | Project timeline and phases. |
| **[IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)** | General guide for development workflow. |

---

## 📂 Folder Structure

```
docs/feat-ui/
├── prototype/                   # ✨ THE CODE IS HERE
│   ├── templates/new-ui/       # HTML Files (Dashboard, Library, etc.)
│   └── static/new-ui/          # CSS & JS Files
│
├── INTEGRATION_GUIDE.md         # 📘 HOW TO MERGE IT
├── NAVIGATION.md                # 🗺️ SITE MAP
├── FRONTEND_COMPLETE.md         # ✅ SUMMARY
└── ... (other docs)
```

## 🎨 Design Highlights

- **Style**: Modern, Dark Theme (default), Light Theme (MediaManager-based), Glassmorphism
- **Color**: SoulSpot Red (`#fe4155`) for Dark Mode, MediaManager Gray (`#333333`) for Light Mode
- **Layout**: Fixed Sidebar + Responsive Grid
- **Tech**: HTML5, CSS3 (Variables), Vanilla JS, HTMX
- **Theming**: Full Dark/Light mode support via CSS custom properties

### Theme Support

| Mode | Primary | Background | Text | Source |
|------|---------|------------|------|--------|
| **Dark** | `#fe4155` (SoulSpot Red) | `#111827` | `#f9fafb` | SoulSpot Original |
| **Light** | `#333333` (Neutral Dark) | `#ffffff` | `#1a1a1a` | MediaManager |

See **[DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)** for complete color palettes (Dark vs Light side-by-side).

See **[COMPONENT_LIBRARY.md](./COMPONENT_LIBRARY.md)** for Light Mode CSS for all ~20 components.

## ❓ FAQ

**Q: Do I need the backend to run the prototype?**
A: **No.** The prototype is standalone HTML/CSS/JS. Follow the [Prototype README](./prototype/README.md) to run it.

**Q: Where are the CSS files?**
A: In `docs/feat-ui/prototype/static/new-ui/css/`.

**Q: How do I add a new page?**
A: Copy `base.html` from the prototype templates and extend it. See [COMPONENT_LIBRARY.md](./COMPONENT_LIBRARY.md) for available components.

**Q: How do I enable Light Mode?**
A: Add `data-theme="light"` to your `<html>` or root element. The CSS variables will automatically switch. See [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md#light-mode-full-css-variable-set) for the full variable set.

**Q: Where do the Light Mode colors come from?**
A: Light Mode uses the [MediaManager](https://github.com/maxdorninger/MediaManager) design system (OKLCH color space). All colors are documented in [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md#neutral-colors-light-mode--mediamanager-reference).

---

**Status**: ✅ Frontend Prototype Complete (Ready for Integration)
**Theme Support**: ✅ Dark Mode (default) + ✅ Light Mode (MediaManager-based)
**Last Updated**: 2025-11-28
