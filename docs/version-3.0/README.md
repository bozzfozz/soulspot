# SoulSpot Bridge - Version 3.0 Architecture Documentation

**Version:** 3.0.0  
**Status:** Planning Phase  
**Created:** 2025-11-21  
**Purpose:** Modular Architecture Design and Specification

---

## Overview

This directory contains the complete architectural design for SoulSpot Bridge Version 3.0, which transitions from a layered monolith to a **fully modular, feature-based architecture**.

---

## 📚 Documentation Structure

### Core Documents

1. **[ROADMAP.md](./ROADMAP.md)** - Comprehensive Roadmap
   - Executive summary and goals
   - Current architecture analysis
   - Target architecture vision
   - Detailed migration strategy (12-week timeline)
   - Module categories and examples
   - Success criteria and risks
   - **Start here** to understand the big picture

2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Architecture Specification
   - System-level architecture diagrams
   - Module-level architecture patterns
   - Complete directory structures
   - Design patterns and best practices
   - Testing, configuration, and deployment strategies
   - Security and performance considerations
   - **Reference guide** for architectural decisions

3. **[MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md)** - Module Template
   - Standard module structure (required files and folders)
   - Backend layer specifications (API, Application, Domain, Infrastructure)
   - Frontend layer specifications (Pages, Widgets, Partials)
   - Code quality checklist and requirements
   - Testing requirements (80%+ coverage)
   - Documentation requirements
   - **Use this template** when creating new modules

4. **[MODULE_COMMUNICATION.md](./MODULE_COMMUNICATION.md)** - Communication Patterns
   - Event bus architecture and implementation
   - Direct module calls via registry
   - Event schemas and versioning
   - Cross-module data contracts
   - Error handling and retry strategies
   - Testing communication patterns
   - **Essential guide** for module integration

### Example Implementation

5. **[SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md)** - Reference Implementation
   - Complete Soulseek module design
   - Domain model (entities, value objects, services)
   - Application layer (services, use cases, DTOs)
   - API layer (routes, schemas, dependencies)
   - Frontend components (pages, widgets, partials)
   - Event contracts and integration points
   - Comprehensive testing examples
   - **Blueprint for all modules** - study this carefully

---

## 🎯 Quick Navigation

### For Project Managers

Start with:
1. [ROADMAP.md](./ROADMAP.md) - Section 1 (Executive Summary)
2. [ROADMAP.md](./ROADMAP.md) - Section 11 (Timeline and Milestones)
3. [ROADMAP.md](./ROADMAP.md) - Section 12 (Risks and Mitigation)

**Goal:** Understand project scope, timeline, and risks

### For Architects

Read in order:
1. [ROADMAP.md](./ROADMAP.md) - Complete
2. [ARCHITECTURE.md](./ARCHITECTURE.md) - Complete
3. [MODULE_COMMUNICATION.md](./MODULE_COMMUNICATION.md) - Complete
4. [SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md) - Review example

**Goal:** Understand system design and make architectural decisions

### For Developers (Backend)

Essential reading:
1. [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md) - Sections 4-6 (Backend, Configuration, Testing)
2. [SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md) - Sections 3-5 (Domain, Application, API)
3. [MODULE_COMMUNICATION.md](./MODULE_COMMUNICATION.md) - Sections 2-3 (Events, Direct Calls)

**Goal:** Build modules following specifications and patterns

### For Developers (Frontend)

Essential reading:
1. [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md) - Section 5 (Frontend Structure)
2. [SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md) - Section 8 (Frontend Components)
3. [ARCHITECTURE.md](./ARCHITECTURE.md) - Section 7 (Frontend Architecture)

**Goal:** Build consistent, modular frontend components

### For QA/Testers

Focus on:
1. [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md) - Section 7 (Testing Requirements)
2. [SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md) - Section 9 (Testing Strategy)
3. [ARCHITECTURE.md](./ARCHITECTURE.md) - Section 8 (Testing Strategy)

**Goal:** Ensure modules meet quality standards

---

## 🏗️ Architecture at a Glance

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser / API Clients                    │
└─────────────────────────────────────────────────────────────┘
                            ↓↓↓
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Gateway + Module Registry              │
└─────────────────────────────────────────────────────────────┘
                            ↓↓↓
┌─────────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Soulseek  │  │ Spotify  │  │ Library  │  │ Metadata │   │
│  │ Module   │  │  Module  │  │  Module  │  │  Module  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                   Feature Modules (Self-Contained)          │
└─────────────────────────────────────────────────────────────┘
                            ↓↓↓
┌─────────────────────────────────────────────────────────────┐
│      Database, Cache, Queue, External APIs, File Storage    │
└─────────────────────────────────────────────────────────────┘
```

### Module Architecture

```
modules/{module_name}/
├── README.md          # ✅ Module overview & getting started
├── CHANGELOG.md       # ✅ Module version history
├── docs/              # ✅ Module documentation
│   ├── architecture.md
│   ├── api.md
│   ├── events.md
│   ├── configuration.md
│   └── development.md
├── submodules/        # Optional: self-contained submodules
│   └── auth/         # e.g., OAuth authentication
│       ├── README.md
│       ├── CHANGELOG.md
│       ├── docs/
│       ├── backend/
│       ├── frontend/
│       └── tests/
├── frontend/          # UI components (HTMX templates)
├── backend/
│   ├── api/          # HTTP endpoints
│   ├── application/  # Business logic orchestration
│   ├── domain/       # Core entities and rules
│   ├── infrastructure/  # Database, external APIs
│   └── config/       # Settings
└── tests/            # Unit + Integration tests
```

---

## 📋 Key Concepts

### 1. Module Independence

- Each module is **self-contained** (frontend + backend + tests)
- Modules communicate **only through contracts** (events, registry)
- Modules can be **developed independently**
- Modules can be **tested in isolation**
- Modules can have **submodules** for complex features (e.g., auth, webhooks)

### 2. Layered Architecture Within Modules

Each module follows clean architecture:
- **API Layer**: HTTP endpoints, request/response handling
- **Application Layer**: Use cases, service orchestration
- **Domain Layer**: Business entities, rules, value objects
- **Infrastructure Layer**: Database, external services, adapters

### 3. Communication Patterns

**Events** (Fire-and-Forget):
```python
# Publisher
await event_bus.publish("download.completed", {"file_path": "..."})

# Subscriber (in another module)
@event_bus.subscribe("download.completed")
async def on_download_completed(event):
    await process(event.data["file_path"])
```

**Module Router** (Intelligent Routing):
```python
# Router finds capable module and routes request
result = await module_router.route_request(
    operation="download.track",
    params={"track_id": "123", "track_info": {...}}
)
# If module unavailable: clear warning in logs/UI, graceful failure
```

**Direct Calls** (Request-Response):
```python
# Query module
stats = await module_registry.query("soulseek", "get_statistics")
```

### 4. Standalone Module Operation

- **Independent Execution**: Each module can run standalone for development/testing
- **Health Monitoring**: Automatic detection of available/missing modules
- **Clear Warnings**: Logs, Docker logs, and UI show missing module warnings
- **Graceful Degradation**: Core features work even when optional modules are unavailable

Example warning when module is missing:
```
⚠️  MISSING MODULE WARNING ⚠️
Operation 'download.track' requires: soulseek
Inactive modules: soulseek
Please enable Soulseek module to use download functionality.
```

### 5. Module Categories

**Core Modules**: `core`, `auth`, `database`  
**Feature Modules**: `soulseek`, `spotify`, `library`, `metadata`  
**Infrastructure Modules**: `notifications`, `settings`, `monitoring`

---

## 🚀 Getting Started

### Creating a New Module

1. **Plan**:
   - Read [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md)
   - Study [SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md) example
   - Define module scope and contracts

2. **Scaffold**:
   ```bash
   ./scripts/create_module.sh {module_name}
   ```

3. **Implement**:
   - Follow [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md) structure
   - Implement domain entities first (pure logic)
   - Then application services (orchestration)
   - Then API routes (HTTP)
   - Finally frontend (templates)

4. **Test**:
   - Unit tests (80%+ coverage)
   - Integration tests (critical flows)
   - Follow examples in [SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md) Section 9

5. **Document**:
   - Module README.md
   - API documentation
   - Event schemas
   - Configuration

6. **Integrate**:
   - Register module in main app
   - Publish/subscribe to events
   - Update [MODULE_COMMUNICATION.md](./MODULE_COMMUNICATION.md)

### Migrating Existing Code

See [ROADMAP.md](./ROADMAP.md) Section 4 for detailed migration strategy.

**Quick steps**:
1. Identify code related to module
2. Create module structure
3. Move code maintaining layer separation
4. Update imports to module paths
5. Add event publishing/subscribing
6. Remove direct cross-module dependencies
7. Test thoroughly

---

## 📊 Progress Tracking

### Documentation Phase ✅ COMPLETE

- [x] Create ROADMAP.md
- [x] Create ARCHITECTURE.md
- [x] Create MODULE_SPECIFICATION.md
- [x] Create MODULE_COMMUNICATION.md
- [x] Create SOULSEEK_MODULE.md example
- [x] Create README.md (this file)

### Implementation Phase 🔜 PLANNED

**Phase 1: Foundation** (Weeks 1-2)
- [ ] Create `modules/` directory
- [ ] Implement core module
- [ ] Implement event bus
- [ ] Implement module registry
- [ ] Create module scaffolding script

**Phase 2: Soulseek Module** (Weeks 3-4)
- [ ] Migrate Soulseek backend
- [ ] Migrate Soulseek frontend
- [ ] Migrate Soulseek tests
- [ ] Document learnings

**Phase 3-5**: See [ROADMAP.md](./ROADMAP.md) Section 11

---

## 🔧 Development Guidelines

### Code Quality Standards

All modules MUST:
- ✅ Pass `ruff check` (linting)
- ✅ Pass `mypy --strict` (type checking)
- ✅ Pass `bandit` (security scan)
- ✅ Achieve 80%+ test coverage
- ✅ Have complete documentation
- ✅ Follow [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md)

### Testing Requirements

- **Unit Tests**: Test domain logic in isolation
- **Integration Tests**: Test module boundaries and flows
- **E2E Tests**: Test cross-module workflows
- **Minimum Coverage**: 80% overall, 90% domain layer

### Documentation Requirements

Every module MUST have:
- **README.md** - Module overview, purpose, features, quick start guide (in module root)
- **CHANGELOG.md** - Module version history following Keep a Changelog format (in module root)
- **docs/** directory containing:
  - **architecture.md** - Architecture, design decisions, component diagrams
  - **api.md** - Complete API documentation (endpoints, schemas)
  - **events.md** - Event schemas, published/subscribed events
  - **configuration.md** - Configuration options, environment variables
  - **development.md** - Development, testing, and contribution guide

**Submodules** MUST have the same documentation structure.

**Documentation Location Rules:**
- Module docs live **in the module directory**, not in global `docs/`
- Submodule docs live **in the submodule directory**
- Global `docs/` only for system-level architecture and cross-module concerns

See [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md) Section 3.2.1 for detailed requirements and examples.

---

## 📖 Reference Links

### Internal Documentation

- [Current Architecture](../project/architecture.md)
- [Backend Roadmap](../development/backend-roadmap.md)
- [Frontend Roadmap](../development/frontend-roadmap.md)
- [Contributing Guide](../project/contributing.md)

### External Resources

- [Clean Architecture (Uncle Bob)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain-Driven Design](https://martinfowler.com/tags/domain%20driven%20design.html)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [Event-Driven Architecture](https://martinfowler.com/articles/201701-event-driven.html)

---

## 💡 FAQs

**Q: Why modular architecture?**  
A: Easier development, testing, and maintenance. Teams can work on different modules independently.

**Q: How do modules communicate?**  
A: Primarily through events (async, loosely coupled). Direct calls via registry for queries.

**Q: Can I mix old and new code?**  
A: No, Version 3.0 will be developed in a separate branch with a clean architecture. Migration from v2.x to v3.0 will be a major version upgrade with migration guides.

**Q: How do I add a new module?**  
A: Follow [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md) and study [SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md).

**Q: What if a module needs data from another module?**  
A: Use events for notifications or direct registry calls for queries. Never import directly.

**Q: How are database changes handled?**  
A: Each module owns its tables. Use Alembic migrations with module prefixes.

---

## 🤝 Contributing

When contributing to modular architecture:

1. Read all core documents first
2. Follow [MODULE_SPECIFICATION.md](./MODULE_SPECIFICATION.md) exactly
3. Study [SOULSEEK_MODULE.md](./SOULSEEK_MODULE.md) for patterns
4. Write tests (80%+ coverage)
5. Document thoroughly
6. Get architectural review before implementation

---

## 📞 Contact

For questions about this architecture:
- Create an issue with tag `architecture-v3`
- Reference specific document and section
- Include use case or example

---

## 📝 Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 3.0.0 | 2025-11-21 | Initial modular architecture design | Integration Orchestrator |

---

**Status:** ✅ Documentation Complete - Ready for Review and Implementation

**Next Steps:**
1. Review all documents with stakeholders
2. Get approval for architecture
3. Begin Phase 1 implementation (Foundation)
4. Start with Soulseek module migration (Phase 2)
