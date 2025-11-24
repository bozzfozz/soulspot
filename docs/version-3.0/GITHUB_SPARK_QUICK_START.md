# GitHub Spark Implementation Guide - Quick Start

**Version:** 3.0.0  
**Last Updated:** 2025-11-24  
**Purpose:** Quick reference for implementing SoulSpot Bridge UI with GitHub Spark

---

## What is This Document?

This is a **quick start guide** for developers who want to implement the SoulSpot Bridge Web UI using **GitHub Spark** (React + TypeScript). For the complete specification, see [GITHUB_SPARK_WEB_UI.md](./GITHUB_SPARK_WEB_UI.md).

---

## Why GitHub Spark?

GitHub Spark is GitHub's platform for creating AI-powered micro-apps using React and TypeScript. It's ideal for SoulSpot Bridge because:

1. **Modern Stack**: React 18 + TypeScript 5 + Vite
2. **Type Safety**: Full TypeScript ensures API contract compliance
3. **AI Integration**: GitHub Copilot accelerates component development
4. **Component-Based**: Perfect fit for our modular architecture
5. **Developer Experience**: Excellent tooling and debugging

---

## Key Differences: HTMX vs GitHub Spark

| Aspect | Current (HTMX) | GitHub Spark (React) |
|--------|---------------|---------------------|
| **Rendering** | Server-side HTML | Client-side React components |
| **State** | DOM-based | React State + Context API |
| **Real-time** | SSE (hx-sse) | SSE with custom hooks |
| **Routing** | FastAPI routes | React Router |
| **Type Safety** | None | Full TypeScript |
| **Testing** | Minimal | Jest + React Testing Library |
| **Bundle Size** | Small (HTMX ~14KB) | Medium (~200KB gzipped) |
| **Best For** | Simple apps | Complex interactive UIs |

---

## 5-Minute Quick Start

### Step 1: Initialize Project

```bash
# Create new Vite + React + TypeScript project
npm create vite@latest soulspot-spark -- --template react-ts

cd soulspot-spark
npm install
```

### Step 2: Install Dependencies

```bash
# Core dependencies
npm install react-router-dom @tanstack/react-query axios

# Form handling
npm install react-hook-form @hookform/resolvers zod

# UI styling
npm install tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### Step 3: Copy Design Tokens

Create `src/styles/tokens.ts` from [GITHUB_SPARK_WEB_UI.md Section 3.1](./GITHUB_SPARK_WEB_UI.md#31-design-tokens).

### Step 4: Implement First Card Component

Create `src/components/cards/StatusCard.tsx` from [GITHUB_SPARK_WEB_UI.md Section 3.2.1](./GITHUB_SPARK_WEB_UI.md#321-statuscard-component).

### Step 5: Set Up API Client

Create `src/services/api/client.ts` from [GITHUB_SPARK_WEB_UI.md Section 9](./GITHUB_SPARK_WEB_UI.md#9-api-client-service).

### Step 6: Create Dashboard Page

Create `src/modules/dashboard/DashboardPage.tsx` from [GITHUB_SPARK_WEB_UI.md Section 6.1](./GITHUB_SPARK_WEB_UI.md#61-dashboard-module).

### Step 7: Run Development Server

```bash
npm run dev
# Open http://localhost:3000
```

---

## Component Reference (Quick Links)

### Card Components
- [StatusCard](./GITHUB_SPARK_WEB_UI.md#321-statuscard-component) - Module health & status
- [ActionCard](./GITHUB_SPARK_WEB_UI.md#322-actioncard-component) - Forms & actions
- [DataCard](./GITHUB_SPARK_WEB_UI.md#323-datacard-component) - Track/album info
- [ProgressCard](./GITHUB_SPARK_WEB_UI.md#324-progresscard-component) - Download progress
- [ListCard](./GITHUB_SPARK_WEB_UI.md#325-listcard-component) - Item lists
- [AlertCard](./GITHUB_SPARK_WEB_UI.md#326-alertcard-component) - Notifications

### Custom Hooks
- [useApi](./GITHUB_SPARK_WEB_UI.md#51-api-hooks) - API queries & mutations
- [useEventSource](./GITHUB_SPARK_WEB_UI.md#52-event-source-hook-sse) - Real-time SSE
- [useToast](./GITHUB_SPARK_WEB_UI.md#53-toast-hook) - Toast notifications

### Pages
- [Dashboard](./GITHUB_SPARK_WEB_UI.md#61-dashboard-module)
- [Soulseek Downloads](./GITHUB_SPARK_WEB_UI.md#62-soulseek-module)
- [Spotify Search](./GITHUB_SPARK_WEB_UI.md#63-spotify-module)

---

## Project Structure

```
soulspot-spark/
├── src/
│   ├── app/                 # App root & routing
│   ├── components/          # Reusable components
│   │   ├── cards/          # 7 card components
│   │   ├── forms/          # Form components
│   │   └── ui/             # UI primitives
│   ├── modules/            # Feature modules
│   │   ├── dashboard/
│   │   ├── soulseek/
│   │   ├── spotify/
│   │   └── library/
│   ├── services/           # API & services
│   ├── hooks/              # Custom hooks
│   ├── types/              # TypeScript types
│   ├── styles/             # Design tokens & CSS
│   └── utils/              # Utilities
└── tests/                  # Test files
```

---

## Implementation Checklist

**Week 1: Foundation**
- [ ] Set up Vite + React + TypeScript project
- [ ] Configure TailwindCSS with design tokens
- [ ] Implement core UI primitives (Button, Input, Badge)
- [ ] Set up API client with interceptors
- [ ] Configure React Query

**Week 2: Card Components**
- [ ] Implement StatusCard
- [ ] Implement ActionCard
- [ ] Implement DataCard
- [ ] Implement ProgressCard
- [ ] Implement ListCard
- [ ] Implement AlertCard

**Week 3: Module Pages**
- [ ] Build Dashboard page
- [ ] Build Soulseek Downloads page
- [ ] Build Spotify Search page
- [ ] Implement routing & navigation

**Week 4: Advanced Features**
- [ ] Implement authentication context
- [ ] Add real-time updates (SSE)
- [ ] Write tests (80% coverage)
- [ ] Performance optimization

**Week 5: Polish**
- [ ] Accessibility audit
- [ ] Dark mode support
- [ ] Documentation
- [ ] Deployment

---

## Common Tasks

### Adding a New Page

1. Create page component: `src/modules/{module}/NewPage.tsx`
2. Add route in `src/app/Routes.tsx`
3. Add navigation link in `src/components/layout/Navigation.tsx`
4. Create API hooks in `src/hooks/use{Module}.ts`

### Adding a New Card Type

1. Design component interface
2. Implement component in `src/components/cards/`
3. Add to component library documentation
4. Write unit tests

### Integrating with Backend API

1. Define TypeScript types in `src/types/api.ts`
2. Create API hook in `src/hooks/`
3. Use React Query for caching & updates
4. Handle errors with toast notifications

---

## Testing

### Unit Test Example

```typescript
import { render, screen } from '@testing-library/react';
import { StatusCard } from './StatusCard';

test('renders module status', () => {
  render(
    <StatusCard
      moduleId="soulseek"
      moduleName="Soulseek"
      icon={<span>🔗</span>}
      status="active"
      lastCheck="2 min ago"
      healthPercentage={90}
    />
  );
  
  expect(screen.getByText('Soulseek')).toBeInTheDocument();
  expect(screen.getByText('Active')).toBeInTheDocument();
});
```

### Integration Test Example

```typescript
import { renderWithProviders } from '@/test-utils';
import { DashboardPage } from './DashboardPage';
import { server } from '@/mocks/server';
import { rest } from 'msw';

test('displays module statuses', async () => {
  server.use(
    rest.get('/api/modules/status', (req, res, ctx) => {
      return res(ctx.json({ data: [...] }));
    })
  );
  
  renderWithProviders(<DashboardPage />);
  
  await screen.findByText('Soulseek');
});
```

---

## Deployment

### Production Build

```bash
# Build for production
npm run build

# Output in dist/ directory
ls dist/
```

### FastAPI Integration

```python
# Serve React build from FastAPI
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="dist", html=True), name="static")
```

### Environment Variables

```bash
# .env
VITE_API_BASE_URL=http://localhost:8765/api
VITE_ENABLE_DARK_MODE=true
```

---

## Resources

- **Complete Specification**: [GITHUB_SPARK_WEB_UI.md](./GITHUB_SPARK_WEB_UI.md)
- **Design System**: [UI_DESIGN_SYSTEM.md](./UI_DESIGN_SYSTEM.md)
- **Architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Module Spec**: [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md)

---

## Getting Help

1. Read the [complete specification](./GITHUB_SPARK_WEB_UI.md)
2. Check [UI_DESIGN_SYSTEM.md](./UI_DESIGN_SYSTEM.md) for design tokens
3. Review [ARCHITECTURE.md](./ARCHITECTURE.md) for backend integration
4. Open an issue with tag `frontend` or `github-spark`

---

**Ready to start? → [Read the complete specification](./GITHUB_SPARK_WEB_UI.md)**

**AI-Model:** GitHub Copilot
