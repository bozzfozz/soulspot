# Copilot / AI Assistant Instructions

Focused repository-specific guidance for AI coding agents to be productive immediately.

## 0. CRITICAL: Virtual GitHub Environment

⚠️ **THIS REPOSITORY RUNS IN A VIRTUAL GITHUB ENVIRONMENT**

**What this means:**
- 🔴 **NO** local file system access (e.g., `/home/user/`, `~/`, `C:\Users\...`)
- 🔴 **NO** attempting to `mkdir`, `touch`, or create files outside the workspace
- 🔴 **NO** reading from system paths or environment variables (except through tools)
- 🟢 **ONLY** use absolute paths with `vscode-vfs://` scheme (e.g., `vscode-vfs://github/bozzfozz/soulspot/src/...`)
- 🟢 **ONLY** use provided tools (read_file, create_file, run_in_terminal, etc.)
- 🟢 **ONLY** reference files that exist within the workspace

**Path Format:**
```
✅ CORRECT:   vscode-vfs://github/bozzfozz/soulspot/src/soulspot/main.py
❌ WRONG:     /home/user/soulspot/src/soulspot/main.py
❌ WRONG:     ~/soulspot/src/soulspot/main.py
❌ WRONG:     C:\Users\bozzfozz\soulspot\src\soulspot\main.py
```

**All Agents Must Follow This Rule:**
- If any agent attempts local file creation or reads outside the workspace, it VIOLATES this policy
- Use `run_in_terminal` ONLY for code execution, not filesystem exploration
- Always use tool-provided APIs for file operations

## 0.1 🔥 CRITICAL: ALWAYS VERIFY BEFORE CHANGING CODE

⚠️ **ABSOLUTE RULE: VERIFY BEFORE MODIFYING, ADDING, OR REMOVING ANYTHING**

**MANDATORY verification checklist for ANY code change:**

1. **Check Documentation FIRST:**
   - Read `docs/architecture/DATA_STANDARDS.md` (DTO definitions)
   - Read `docs/architecture/DATA_LAYER_PATTERNS.md` (Entity/Repository patterns)
   - Read `docs/architecture/CONFIGURATION.md` (Config/Settings patterns)
   - Search `docs/` for the feature/field/function name

2. **Check Database Schema:**
   - Read `src/soulspot/infrastructure/persistence/models.py` (SQLAlchemy models)
   - Search for related fields in all `*Model` classes
   - Verify Entity ↔ Model consistency (both must have same fields!)

3. **Check Migrations:**
   - Search `alembic/versions/` for relevant changes
   - If migration exists for a field → It's intentional, respect it!

4. **Check DTOs and Plugins:**
   - Read `src/soulspot/infrastructure/plugins/dto.py`
   - Check if DTO has the field/parameter
   - If DTO has it → Entity/Model MUST have it too for mapping!

5. **Check Usage Across Codebase:**
   - Use `grep_search` to find all references
   - Check Services, Repositories, Routes
   - If used in multiple places → INVESTIGATE before changing!

6. **Check Interface-Implementation Contracts:**
   - Read `src/soulspot/domain/ports/__init__.py` (Interfaces)
   - Verify Repository implements ALL interface methods
   - If you change Repository → Update Interface too!

**Decision Matrix:**

| Situation | Action |
|-----------|--------|
| **Error: "unexpected keyword argument X"** | ❌ Don't remove X! Check if Model/DTO has X → Add to Entity |
| **Error: "missing required argument Y"** | ✅ Check DTO default values, add Y with proper default |
| **Adding new feature** | ✅ Add to: DTO → Entity → Model → Migration → Repository |
| **Deprecating feature** | ✅ Mark `@deprecated`, document in CHANGELOG, keep for 1 version |
| **Refactoring function** | ✅ Check ALL usages first, update callers, test |

**Examples:**

```python
❌ WRONG: See Album() error "unexpected keyword 'source'"
          → Delete "source" parameter from caller
          → BREAKS: AlbumModel HAS source field in DB!

✅ RIGHT: See Album() error "unexpected keyword 'source'"
          → Check AlbumModel: HAS source field ✓
          → Check Album Entity: MISSING source field!
          → Add source to Album Entity
          → Update AlbumRepository._model_to_entity()
          → Keep source in caller

❌ WRONG: Want to add new field "rating" to Track
          → Add to Track Entity only
          → BREAKS: TrackModel doesn't have it, repo fails!

✅ RIGHT: Want to add new field "rating" to Track
          → Add to TrackDTO (with default)
          → Add to Track Entity (with default)
          → Add to TrackModel (nullable column)
          → Create Alembic migration
          → Update TrackRepository add/update methods
          → Update _model_to_entity mapping
```

**RED FLAGS (stop and verify!):**
- Any error message mentioning "argument" or "keyword"
- About to modify constructor signature
- About to add/remove field from Entity/Model/DTO
- Migration exists for the feature you're changing
- Function is used in more than 3 places

**GOLDEN RULE:**
```
BEFORE ANY CHANGE:
1. Read Documentation
2. Check DB Schema & Migrations
3. Verify DTOs & Entities are in sync
4. Search for all usages
5. Understand the FULL DATA FLOW

Entity ↔ Model ↔ DTO ↔ Plugin
ALL FOUR must be consistent!

🚨 IF UNSURE AFTER VERIFICATION → ASK USER, DON'T GUESS! 🚨
When in doubt → CLARIFY with user before proceeding!
Breaking changes require careful planning.
```

**Escalation Protocol:**
1. ✅ **Simple/Clear** → Proceed with change after verification
2. ⚠️ **Uncertain** → Present findings + ask user for decision
3. 🚨 **Breaking/Complex** → Document impact + request approval

**When to ask user BEFORE proceeding:**
- Verification shows conflicting information (DTO has field, Model doesn't)
- Migration exists but unclear if feature is abandoned
- Change affects >5 files or multiple layers
- Security/data integrity concerns
- Deprecation without clear replacement path

This rule prevents:
- Breaking Entity ↔ Model ↔ DTO mapping consistency
- Removing planned features that exist in DB/migrations
- Missing interface updates when changing implementations
- Unintentional breaking changes without deprecation
- Making assumptions when facts are unclear

## 0.2 🔍 CRITICAL: ANALYZE BEFORE IMPLEMENTING

⚠️ **ABSOLUTE RULE: SEARCH EXISTING CODE BEFORE WRITING NEW CODE**

**MANDATORY analysis checklist BEFORE implementing ANY feature:**

### Step 1: Search for Existing Solutions
```bash
# ALWAYS do these searches FIRST:
grep_search "function_name_or_keyword"     # Find similar functions
grep_search "ClassName"                     # Find existing classes
semantic_search "what you want to do"       # Find related code
```

### Step 2: Check Existing Services & Utilities
| What you need | Where to look FIRST |
|---------------|---------------------|
| Database operations | `src/soulspot/infrastructure/persistence/repositories.py` |
| Image handling | `src/soulspot/application/services/images/` |
| Settings/Config | `src/soulspot/application/services/app_settings_service.py` |
| Spotify operations | `src/soulspot/application/services/spotify_sync_service.py` |
| Deezer operations | `src/soulspot/application/services/deezer_sync_service.py` |
| File operations | `src/soulspot/application/services/library_cleanup_service.py` |
| Background tasks | `src/soulspot/application/workers/` |
| API dependencies | `src/soulspot/api/dependencies.py` |
| Utility functions | `src/soulspot/domain/utils/` |

### Step 3: Reuse Patterns - NEVER Reinvent
```python
# ❌ WRONG: Create new helper without checking
def my_new_helper():
    # 500 lines of code that already exists elsewhere

# ✅ RIGHT: Search first, reuse existing
from soulspot.application.services.existing_service import existing_helper
result = existing_helper(params)
```

### Step 4: Decision Tree

```
Want to implement Feature X?
           │
           ▼
   ┌───────────────────┐
   │ grep_search for X │
   └─────────┬─────────┘
             │
      Found existing code?
           /    \
         YES     NO
          │       │
          ▼       ▼
   ┌──────────┐  ┌──────────────────┐
   │ REUSE IT │  │ semantic_search  │
   │ or       │  │ for similar      │
   │ EXTEND   │  │ functionality    │
   └──────────┘  └────────┬─────────┘
                          │
                   Found similar?
                      /    \
                    YES     NO
                     │       │
                     ▼       ▼
              ┌──────────┐  ┌──────────────┐
              │ ADAPT IT │  │ NOW you may  │
              │ don't    │  │ create new   │
              │ duplicate│  │ code         │
              └──────────┘  └──────────────┘
```

### Common Mistakes This Rule Prevents

| Mistake | What happens | Prevention |
|---------|--------------|------------|
| Duplicate service method | Two methods do same thing, one gets outdated | Search repos first |
| New utility function | Existing one in utils/ does the same | grep for keywords |
| Copy-paste from other file | Code diverges, bugs get fixed in one place only | Import and reuse |
| New worker for existing task | Race conditions, duplicate processing | Check workers/ first |
| New API endpoint | Existing endpoint already handles this | Check routers/ first |

### Example: The spotify_sync_worker.py Corruption

```python
# ❌ WHAT HAPPENED (file corruption):
# Someone copy-pasted code without checking structure
# Result: Duplicate methods, broken syntax, 1197 lines of chaos

# ✅ WHAT SHOULD HAVE HAPPENED:
# 1. Read existing _create_sync_service() method
# 2. Understand its return pattern
# 3. Modify ONLY the specific part needed
# 4. Test syntax before committing
```

### Required Searches Before ANY Implementation

**MINIMUM 3 searches before writing new code:**

1. **Exact name search:** `grep_search "exact_function_name"`
2. **Keyword search:** `grep_search "related_keyword|alternative_term"`
3. **Semantic search:** `semantic_search "description of what you need"`

**If ALL 3 return nothing relevant → THEN create new code**

### Verification Statement

Before implementing, mentally answer:
- [ ] "I searched for existing code that does this"
- [ ] "I checked the relevant service files listed above"
- [ ] "I found no existing solution OR I'm extending an existing one"
- [ ] "I'm not duplicating functionality"

**🚨 CREATING DUPLICATE CODE IS A BUG, NOT A FEATURE 🚨**

## 0.4 🔨 CRITICAL: REFACTORING COMMITMENT (UNIFIED LIBRARY WORKER)

⚠️ **ABSOLUTE RULE: NO SHORTCUTS, NO EXCUSES, NO HALF-MEASURES**

**When working on the UnifiedLibraryManager refactoring, READ:**
- `docs/architecture/REFACTORING_COMMITMENT_PROTOCOL.md` - BINDING rules
- `docs/architecture/UNIFIED_LIBRARY_WORKER.md` - Architecture
- `docs/architecture/UNIFIED_LIBRARY_WORKER_MIGRATION_INVENTORY.md` - What to migrate

### Refactoring Rules (VERBOTEN = FORBIDDEN):

| Faulheit-Symptom | Beispiel | Status |
|------------------|----------|--------|
| "Temporäre" Lösungen | "Wir können das später richtig machen" | ❌ VERBOTEN |
| Copy-Paste statt Abstraktion | "Ich kopiere den Code erstmal schnell" | ❌ VERBOTEN |
| Halb-fertige Migration | "Die anderen 3 Funktionen mache ich morgen" | ❌ VERBOTEN |
| Shortcuts | "Ich rufe den alten Worker einfach vom neuen auf" | ❌ VERBOTEN |
| "TODO: später" Kommentare | "# TODO: Add Deezer support" | ❌ VERBOTEN |
| Alten Code behalten | "Falls wir zurückrollen müssen" | ❌ VERBOTEN |

### Migration MUSS enthalten:

1. ✅ **KOMPLETT** - Alle Funktionen migriert, keine ausgelassen
2. ✅ **LÖSCHEN** - Alten Code nach erfolgreicher Migration entfernen
3. ✅ **TESTEN** - Live in Docker testen bevor "fertig" sagen
4. ✅ **DOKUMENTIEREN** - Inventar und Docs aktualisieren

**🚨 WENN DU DENKST "DAS KANN ICH SPÄTER MACHEN" → FALSCH! JETZT MACHEN ODER NICHT ANFANGEN 🚨**

## 0.3 📚 CRITICAL: DOCUMENTATION MUST STAY IN SYNC

⚠️ **ABSOLUTE RULE: READ DOCS BEFORE CODING, UPDATE DOCS AFTER CODING**

### Before ANY Code Change - READ These Docs:

| What you're changing | Read FIRST |
|---------------------|------------|
| Entities/Models/DTOs | `docs/architecture/DATA_STANDARDS.md` |
| Repository patterns | `docs/architecture/DATA_LAYER_PATTERNS.md` |
| Settings/Config | `docs/architecture/CONFIGURATION.md` |
| API endpoints | `docs/03-api-reference/` |
| New features | `docs/06-features/` |
| Worker/Background tasks | Check existing worker docs in `docs/` |

### After ANY Code Change - UPDATE These Docs:

| What you changed | Update |
|-----------------|--------|
| New API endpoint | `docs/03-api-reference/` |
| New feature | `docs/06-features/` + `README.md` |
| Config/Settings | `docs/architecture/CONFIGURATION.md` + `.env.example` |
| DB schema | Migration + `docs/architecture/DATA_STANDARDS.md` |
| Breaking change | `CHANGELOG.md` + Migration guide |
| Fixed TODO | `docs/TODO.md` + `docs/TODOS_ANALYSIS.md` |
| Completed task | `docs/ACTION_PLAN.md` status |

### Documentation Locations

```
docs/
├── 01-guides/           # User guides
├── 03-api-reference/    # API documentation  
├── 04-architecture/     # Architecture decisions
├── 06-features/         # Feature documentation
├── 07-library/          # Library management docs
├── TODO.md              # Project TODOs
├── ACTION_PLAN.md       # Current sprint tasks
└── TODOS_ANALYSIS.md    # TODO tracking
```

### The Golden Rule: Code + Docs = ONE Unit

```python
# ❌ WRONG: Change code, forget docs
def new_endpoint():
    """Added new feature"""  # But docs/api/ not updated!
    pass

# ✅ RIGHT: Code AND docs together
def new_endpoint():
    """Added new feature"""
    pass
# THEN: Update docs/03-api-reference/endpoints.md
# THEN: Update README.md if user-facing
# THEN: Update CHANGELOG.md
```

### Mandatory Doc-Sync Checklist

Before marking ANY task complete:
- [ ] Read relevant docs BEFORE implementing
- [ ] Code changes are done
- [ ] Related docs are updated
- [ ] Examples in docs still work
- [ ] No stale/outdated information left behind

### What Happens Without Doc-Sync

| Symptom | Cause |
|---------|-------|
| "Where is feature X documented?" | Added feature, forgot docs |
| "Docs say Y but code does Z" | Changed code, forgot docs |
| "README is outdated" | New features not documented |
| "TODO still listed but already done" | Fixed issue, forgot to update TODO.md |

**🚨 UNDOCUMENTED CODE IS INCOMPLETE CODE 🚨**

**🚨 OUTDATED DOCS ARE WORSE THAN NO DOCS 🚨**

## 1. Purpose & Big Picture

**What:** SoulSpot syncs Spotify playlists and downloads tracks via the Soulseek `slskd` service, enriches metadata and stores organized music files.

**Architecture:**
```
API (FastAPI) → Application (Services, Use Cases) → Domain (Entities, Ports)
                                                           ↓
                                           Infrastructure (Repos, Clients)
```

- **Presentation:** FastAPI app in `src/soulspot/main.py` with HTMX/Jinja2 templates
- **Application:** Business logic in `src/soulspot/application/services/` + use cases
- **Domain:** Entities & ports in `src/soulspot/domain/entities/` + `domain/ports/`
- **Infrastructure:** DB repos + clients in `src/soulspot/infrastructure/` (SQLAlchemy async)
- **Workers:** Background tasks (Spotify sync, token refresh, downloads) managed via `app.state`
- **Migrations:** DB schema versioning via `alembic/versions/`

**Key Insight:** Strict layered architecture. Domain layer is dependency-free (no ORM, no HTTP). Infrastructure implements Domain ports. Never call infrastructure directly from routes.

## 1.1 🚨 KRITISCH: Architecture Instructions

**BEVOR du Code schreibst, lies:**
- `.github/instructions/architecture.instructions.md` - Layer-Regeln, Datenfluss, Attribut-Naming
- `.github/instructions/naming-conventions.instructions.md` - Funktions-/Parameter-/Konstruktor-Naming
- `.github/instructions/python.instructions.md` - Python-Coding-Konventionen
- `.github/instructions/tasksync_v4.instructions.md` - TaskSync Session-Management
- `docs/architecture/DATA_LAYER_PATTERNS.md` - Code-Beispiele für häufige Operationen

**Die häufigsten Fehler:**
- ❌ `spotify_id` in Domain Entities (verwende `spotify_uri`!)
- ❌ Routes rufen Clients direkt auf (verwende Services!)
- ❌ Plugins geben raw dicts zurück (konvertiere zu DTOs!)
- ❌ Neue Repo-Methode ohne Interface-Update (Port vergessen!)

**Quick Rule:**
```
Entity.spotify_uri  → "spotify:artist:ID" (voller URI)
DTO.spotify_id      → "ID" (nur die ID)
Model.spotify_uri   → DB Column (voller URI)
Model.spotify_id    → @property (extrahiert ID aus URI)
```

## 2. Recommended dev environment

- **Prefer:** `poetry` (project declares `pyproject.toml`). Use `poetry install --with dev` to get dev tools (mypy, ruff, pytest).
- **Alternative:** The `Makefile` exposes pragmatic targets (install/test/lint/format). CI may rely on `pip` + `requirements.txt`.

⚠️ **CRITICAL: poetry.lock MUST be in sync with pyproject.toml!**
- When modifying `pyproject.toml`, **ALWAYS** run `poetry lock --no-update` immediately
- See `docs/development/POETRY_LOCK_MANAGEMENT.md` for 3-layer protection system
- Pre-commit hook blocks commits if lock file out of sync (setup: `git config core.hooksPath .githooks`)

## 3. Key commands

- Install deps: `poetry install --with dev`
- ~~Run tests: `pytest tests/ -v` or `make test`~~ **DEPRECATED - No automated tests, live testing only**
- Lint/format: `make lint` / `make format` (ruff)
- Type-check: `make type-check` (mypy strict mode)
- Security scan: `make security` (bandit)
- Check poetry.lock: `make check-lock` (validates sync with pyproject.toml)
- Start Docker: `make docker-up` (uses `docker/docker-compose.yml`)
- DB migrate: `alembic upgrade head` or `make db-upgrade`

**🚨 TESTING POLICY 🚨**
- ❌ NO automated tests (unit/integration/e2e)
- ❌ NEVER write pytest tests
- ✅ ALL testing is done LIVE in Docker environment
- ✅ User tests manually via UI/API after each change

## 4. Critical architecture patterns

### 4.1 Layered Architecture (STRICT)
Every change must respect dependency direction: **API → App → Domain ← Infrastructure**

**Domain Layer** (`src/soulspot/domain/`):
- Pure business logic, NO external dependencies
- Defines ports (interfaces) that infrastructure implements
- Example: `domain/ports/spotify_client.py` defines `ISpotifyClient` interface

**Application Layer** (`src/soulspot/application/services/`):
- Orchestrates domain + infrastructure
- Contains use cases (commands/queries)
- Depends on domain ports (abstractions), not concrete clients
- Pattern: `async def execute(self, cmd) → DTO`

**Infrastructure Layer** (`src/soulspot/infrastructure/`):
- Implements domain ports (adapters)
- Database repos with `async def` SQLAlchemy
- HTTP clients for Spotify/MusicBrainz
- Example: `infrastructure/clients/spotify_client.py` implements `ISpotifyClient`

**API Layer** (`src/soulspot/api/`):
- HTTP routes, request validation only
- Calls application services, never infrastructure directly
- Pattern: Route → AppService → DomainLogic + Infrastructure

### 4.2 Adding a new feature (correct order)
1. **Domain:** Define entity + port (interface)
2. **Infrastructure:** Implement port (client/repo)
3. **Application:** Add service that uses port
4. **API:** Add route that calls service
5. **Test:** Mock ports, test each layer separately

❌ WRONG: Add route → Add service → Oops, domain logic is in service  
✅ RIGHT: Domain port → Infrastructure → Application → API

### 4.3 Repository + Port sync (critical!)
When you add a method to `TrackRepository`, **MUST** add it to `ITrackRepository` interface too.
```python
# src/soulspot/domain/ports/__init__.py
class ITrackRepository(Protocol):
    async def get_by_isrc(self, isrc: str) -> Track | None: ...

# src/soulspot/infrastructure/persistence/repositories.py
class TrackRepository:
    async def get_by_isrc(self, isrc: str) -> Track | None:
        ...
```

### 4.4 Multi-Service Aggregation (MANDATORY!) ⭐

> **"Always use ALL available services, deduplicate, and combine results"**

For ANY feature that fetches external data (Browse, Search, Discovery, New Releases, etc.):

1. **Query ALL enabled services** - Deezer + Spotify + Tidal + ...
2. **Aggregate results** - Combine responses into unified list
3. **Deduplicate** - Use normalized keys (artist_name + album_title, ISRC)
4. **Tag source** - Each result keeps `source` field ("spotify", "deezer", etc.)
5. **Graceful fallback** - If one service fails, show results from others

**Pattern using can_use() (PREFERRED!):**
```python
from soulspot.domain.ports.plugin import PluginCapability

async def get_new_releases():
    all_releases = []
    seen_keys = set()
    source_counts = {"deezer": 0, "spotify": 0}
    
    # 1. Deezer - can_use() checks: capability supported + auth if needed
    #    For Deezer BROWSE_NEW_RELEASES, no auth is needed → returns True
    if await settings.is_provider_enabled("deezer"):
        if deezer_plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES):
            for r in await deezer_plugin.get_browse_new_releases():
                key = normalize(r.artist, r.title)
                if key not in seen_keys:
                    seen_keys.add(key)
                    r.source = "deezer"
                    all_releases.append(r)
                    source_counts["deezer"] += 1
    
    # 2. Spotify - can_use() checks: capability supported + auth if needed
    #    For Spotify, ALL capabilities require auth → returns False if no token
    if await settings.is_provider_enabled("spotify"):
        if spotify_plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES):
            for r in await spotify_plugin.get_new_releases():
                key = normalize(r.artist, r.title)
                if key not in seen_keys:
                    seen_keys.add(key)
                    r.source = "spotify"
                    all_releases.append(r)
                    source_counts["spotify"] += 1
    
    return sorted(all_releases, key=lambda x: x.release_date, reverse=True)
```

**Service Availability Check (USE THESE METHODS!):**
```python
# Check if provider is enabled (not set to "off")
from soulspot.application.services.app_settings_service import AppSettingsService

settings = AppSettingsService(session)

# Check if service is enabled
deezer_enabled = await settings.is_provider_enabled("deezer")  # True if basic/pro
spotify_enabled = await settings.is_provider_enabled("spotify")  # True if basic/pro

# Check specific mode
mode = await settings.get_provider_mode("deezer")  # Returns "off", "basic", "pro"

# Set provider mode (in settings UI)
await settings.set_provider_mode("deezer", "basic")
```

**Authentication Check (USE THESE PROPERTIES!):**
```python
# Quick check if user has authenticated (has token)
if not spotify_plugin.is_authenticated:
    return {"skipped_not_authenticated": True}

# Full validation (makes API call) - use sparingly!
auth_status = await spotify_plugin.get_auth_status()
if not auth_status.is_authenticated:
    # Token expired or invalid
    ...
```

**Complete Check Pattern (PROVIDER + AUTH):**
```python
# 1. FIRST: Provider enabled?
if not await settings.is_provider_enabled("spotify"):
    return {"skipped_provider_disabled": True}

# 2. SECOND: User authenticated?
if not spotify_plugin.is_authenticated:
    return {"skipped_not_authenticated": True}

# 3. THEN: Do the operation
result = await spotify_plugin.get_followed_artists()
```

**Provider Modes:**
- `off` = Disabled completely
- `basic` = Enabled with basic features (metadata/browse)
- `pro` = Full features enabled

**Capability Check (USE THIS FOR FEATURE DECISIONS!):**
```python
from soulspot.domain.ports.plugin import PluginCapability

# Check if a specific feature can be used RIGHT NOW
# (considers both: is the feature supported AND is auth available if needed)
if deezer_plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES):
    releases = await deezer_plugin.get_browse_new_releases()

if spotify_plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS):
    artists = await spotify_plugin.get_followed_artists()

# Get all capabilities with auth requirements
for cap_info in spotify_plugin.get_capabilities():
    print(f"{cap_info.capability}: requires_auth={cap_info.requires_auth}")
```

**Auth Requirements by Service:**

| Service | Public API (no auth) | Auth Required |
|---------|---------------------|---------------|
| **Deezer** | Search, Browse, Artist/Album lookup, Charts, Genres | User favorites, playlists |
| **Spotify** | ❌ NOTHING | ALL operations need OAuth |
| **MusicBrainz** | Everything | N/A |
- `basic` = Enabled with basic features (metadata/browse)
- `pro` = Full features enabled

See: `docs/architecture/CORE_PHILOSOPHY.md` Section 3 for full details.

## 5. Project layout & critical files

| Path | Purpose |
|------|---------|
| `src/soulspot/main.py` | FastAPI factory + app singleton + CLI entry |
| `src/soulspot/api/routers/` | Routes for each feature (spotify, library, settings, etc.) |
| `src/soulspot/application/services/` | Business logic orchestration |
| `src/soulspot/domain/entities/` | Domain models (Track, Artist, Playlist, etc.) |
| `src/soulspot/domain/ports/` | Interface definitions (ISpotifyClient, IRepository, etc.) |
| `src/soulspot/infrastructure/persistence/repositories.py` | SQLAlchemy repo implementations |
| `src/soulspot/infrastructure/clients/` | External API clients (Spotify, MusicBrainz) |
| `alembic/versions/` | DB migrations (strict order, never edit history) |
| `pyproject.toml` | Dependencies + strict mypy/ruff config |
| `tests/unit/` | Isolated unit tests (mock everything) |
| `tests/integration/` | API tests with real DB (use fixtures) |

## 6. Code patterns & conventions

- **Strict typing:** `mypy strict = true`. All functions must have type hints.
- **Async/await:** Use `async def` for all DB/HTTP. Never block event loop.
- **SQLAlchemy:** Async engine + `async with session()`. See `src/soulspot/infrastructure/persistence/repositories.py` for pattern.
- **Workers:** Background tasks in `app.state` (token refresh, spotify sync, downloads). Start in `infrastructure/lifecycle.py`.
- **Testing:** 
  - Unit: Mock all external dependencies, test logic in isolation
  - Integration: Use async fixtures with real DB (see `tests/conftest.py`)
  - HTTP: Use `pytest-httpx` for client mocking

## 7. Configuration Architecture (DATABASE-FIRST!)

⚠️ **CRITICAL: NO `.env` FILES FOR CREDENTIALS!**

SoulSpot uses a **database-first configuration** approach:
- All user-configurable settings are stored in the `app_settings` database table
- Users configure credentials via the Settings UI (not by editing files)
- Changes take effect immediately without app restart

**Where configurations live:**

| Configuration Type | Storage Location | NOT |
|-------------------|------------------|-----|
| **OAuth Credentials** | `app_settings` table | ❌ `.env` |
| **User OAuth Tokens** | `*_sessions` tables | ❌ `.env` |
| **App Preferences** | `app_settings` table | ❌ `.env` |
| **Database URL** | ENV var (only if custom) | - |

**Pattern for accessing credentials:**
```python
# ✅ RIGHT: Load from DB via AppSettingsService
settings_service = AppSettingsService(session)
client_id = await settings_service.get_string("spotify.client_id")

# ❌ WRONG: Load from settings.py / .env
from soulspot.config.settings import get_settings
client_id = get_settings().spotify.client_id  # DON'T DO THIS!
```

**Key Tables:**
- `app_settings`: Key-value store for credentials and preferences
- `spotify_sessions`: Spotify OAuth tokens per browser session
- `deezer_sessions`: Deezer OAuth tokens per browser session

See: `docs/architecture/CONFIGURATION.md` for full details.

## 8. Integration points & external services

| Service | Config Location | Use Case |
|---------|-----------------|----------|
| **Spotify OAuth** | `app_settings` (key: `spotify.*`) | Authenticate users, fetch playlists |
| **Deezer OAuth** | `app_settings` (key: `deezer.*`) | Browse new releases, user library |
| **slskd** | `app_settings` (key: `slskd.*`) | Download tracks via Soulseek |
| **MusicBrainz** | No auth (rate-limited 1/sec) | Track metadata enrichment |
| **CoverArtArchive** | No auth | Fetch album artwork |

Key files:
- `src/soulspot/infrastructure/integrations/spotify_client.py` - Spotify API wrapper
- `src/soulspot/infrastructure/integrations/deezer_client.py` - Deezer API wrapper
- `src/soulspot/infrastructure/integrations/slskd_client.py` - Soulseek download client
- `src/soulspot/infrastructure/integrations/musicbrainz_client.py` - Metadata client

## 9. Verification Before Writing (PFLICHT)

**Before writing paths, config values, or classnames, verify them:**

```bash
# Datenbank-Tabellen prüfen
grep -r "app_settings" src/soulspot/

# Klassennamen + Imports verifizieren
grep -r "class ISpotifyClient" src/soulspot/domain/

# Port-Nummern prüfen
grep "5000\|8000\|5030" docker/docker-compose.yml
```

❌ WRONG: "Credentials from .env"  
✅ RIGHT: "Credentials from `app_settings` table via `AppSettingsService`"

## 10. Common errors to avoid

### 9.1 Breaking Interface-Repository Contract
```python
# ❌ WRONG: Add method only to TrackRepository
class TrackRepository:
    async def get_by_isrc(self, isrc: str): ...

# ✅ RIGHT: Update interface AND implementation
class ITrackRepository(Protocol):
    async def get_by_isrc(self, isrc: str): ...
```

### 9.2 Missing exports in __init__.py
```python
# ❌ WRONG: Define class in entity.py but don't export
# src/soulspot/domain/entities/__init__.py is empty

# ✅ RIGHT: Always export in __init__.py
from .track import Track
__all__ = ["Track"]
```

### 9.3 Calling infrastructure directly from API
```python
# ❌ WRONG: Route calls repo directly
@router.get("/tracks")
async def list_tracks(repo: TrackRepository):
    return await repo.all()

# ✅ RIGHT: Route calls service, which calls repo
@router.get("/tracks")
async def list_tracks(service: TrackService):
    return await service.list_all()
```

### 9.4 Datetime timezone mismatches
```python
# ❌ WRONG: Mix naive (datetime.utcnow()) + aware (datetime.now(timezone.utc))
diff = datetime.utcnow() - stored_dt  # Crash if stored_dt is aware!

# ✅ RIGHT: Always use aware (UTC)
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
if dt.tzinfo is None:
    dt = dt.replace(tzinfo=timezone.utc)
```

### 9.5 Copy-Paste File Corruption (CRITICAL!)
```python
# ❌ WRONG: Copy-paste code without understanding file structure
# Result: Duplicate methods, broken syntax, corrupted files like:
#
#   return SpotifySyncService(
#       session=session,
#       spotify_plugin=spotify_plugin,
#   async def start(self) -> None:    # <-- BROKEN! return not closed!
#
#   break't crash the loop            # <-- BROKEN! merge conflict artifact

# ✅ RIGHT: ALWAYS follow this process:
# 1. READ the entire function/method you want to modify
# 2. UNDERSTAND its structure (opening/closing braces, returns)
# 3. MODIFY only the specific lines needed
# 4. VERIFY syntax after editing (run pylance check)
# 5. NEVER copy large blocks without reading context
```

**Signs of Copy-Paste Corruption:**
- Duplicate method definitions in same class
- `break` or `return` followed by random text
- Unclosed docstrings (`"""` without closing `"""`)
- Missing `return` statements in functions
- Indentation suddenly changes mid-function
diff = now - dt
```

## 10. When unsure — minimal reproducible setup

```bash
cp .env.example .env
# Fill: SPOTIFY_CLIENT_ID, SPOTIFY_REDIRECT_URI, SLSKD_URL

poetry install --with dev
make docker-up

pytest tests/unit/ -v
```

## 11. Final checklist before PR

- [ ] `ruff check . --config pyproject.toml` passes
- [ ] `mypy --config-file mypy.ini src/` passes (strict mode)
- [ ] `bandit -r src/` shows no HIGH/MEDIUM findings
- [ ] `pytest tests/ -q` passes
- [ ] Domain layer has NO external dependencies
## 12. Advanced patterns - Part 1

### 12.1 Interface-Repository sync
When adding a method to a repository, **always update the interface** in `src/soulspot/domain/ports/__init__.py`:
- ❌ WRONG: Add only `TrackRepository.get_by_isrc()`
- ✅ RIGHT: Add to both `ITrackRepository` (interface) and `TrackRepository` (impl)

### 12.2 Export completeness
New classes/functions must be exported in `__init__.py`:
- [ ] Import in `__init__.py`
- [ ] Add to `__all__` (if present)

## 12. Advanced patterns - Part 2

### 12.3 Alembic migration order
Before creating migrations:
1. `ls alembic/versions/` to find latest revision
2. Set `down_revision` to **actual** latest (not guessed)
3. On conflicts: `alembic merge heads`

### 12.4 Don't duplicate code
Search before implementing:
1. Use `grep_search` for similar functions
2. Check if Service/Repo exists
3. Reuse patterns, don't reinvent

**See Section 0.2 for the FULL analysis checklist!**

### 12.5 Async consistency
**ALL** database ops must use `async`/`await`:
```python
# ❌ WRONG
def get_track(self, id):
    return self.session.query(Track).get(id)

# ✅ RIGHT
async def get_track(self, id):
    result = await self.session.execute(select(Track).where(Track.id == id))
    return result.scalar_one_or_none()
```

### 12.6 Test structure mirrors source
- ✅ `src/soulspot/application/services/foo.py` → `tests/unit/application/services/test_foo.py`
- ❌ NOT: `tests/unit/test_foo.py`

### 12.7 Complete functions only
Functions are **NOT done** if:
- Contain `pass`, `...`, or `# TODO`
- Return only `None` without logic
- Raise `NotImplementedError`

## 13. Service-specific extensibility

Classes tied to one service (Spotify, Tidal, Deezer) **must include service name**:
- ✅ `SpotifySession`, `TidalSession` (expandable)
- ✅ `spotify_sessions` table
- ❌ `Session` is ambiguous

**Use prefix for:** OAuth (`SpotifyAuth`), sessions (`SpotifySession`), clients (`SpotifyClient`), tables (`spotify_sessions`).
**No prefix for:** Utilities (`AudioFileProcessor`), domain (`Track`), infrastructure (`Database`).

## 14. Documentation sync (required every PR)

Keep docs synchronized:
| Change | Update |
|--------|--------|
| API changes | `docs/api/` |
| New features | `README.md` |
| Config changes | `.env.example` |
| DB schema | Migrations + docs |
| Breaking changes | `CHANGELOG.md` |

**Forbidden:** Changing code without checking docs. Shipping features without docs.

## 15. Quality gates before PR

**All must pass locally:**
```bash
ruff check . --config pyproject.toml  # NO --fix flag
mypy --config-file mypy.ini src/
bandit -r src/
# pytest DEPRECATED - no automated tests
```

**PR requirements:**
- [ ] Ruff: 0 violations
- [ ] mypy: 0 type errors
- [ ] bandit: No HIGH/MEDIUM findings
- [ ] ~~Tests: All green~~ **DEPRECATED - Live testing only**
- [ ] Repo + Port interfaces synced
- [ ] Docs synchronized
- [ ] **Manual live test in Docker completed**

**🚨 NO AUTOMATED TESTS 🚨**
- This project uses **live testing only** (manual testing in Docker)
- Do NOT write pytest tests
- Do NOT run `pytest` commands
- User validates all changes manually via UI/API

---

**Final note:** Strict layering is key. If something feels hard, check dependency direction: **API → App → Domain ← Infrastructure**.

---

## 16. TaskSync V5 – Terminal-Based Session Management

**When TaskSync is active** (detected by `.github/instructions/tasksync_v4.instructions.md` being loaded):

### Core Behavior
1. **Keep Session Alive** – Do NOT end conversation between tasks
2. **Request Next Task via Terminal** – After completing Task #N, immediately call `run_in_terminal` with `read -p "Task #N+1: " task_input`
3. **Wait for User Input** – Keep conversation open while waiting for terminal input
4. **Parse Special Commands:**
   - `"stop"` → Terminate gracefully, show session summary
   - `"status"` → Report task count and metrics, then request next task
   - `"help"` → Show available commands, then request next task
5. **Respect Code Patterns** – Follow all patterns from Sections 1-15 (architecture, testing, docs, quality gates)

### Session Lifecycle
```
Task #1 Input (Terminal)
         ↓
Agent completes Task #1
         ↓
Terminal: read -p "Task #2: " (Session stays open)
         ↓
Task #2 Input OR "stop" entered
         ↓
Repeat until "stop" OR Token lifetime expires
         ↓
Show Session Summary → End
```

### Token Optimization Math
```
Without TaskSync:
  50 tasks = 50 separate sessions = 50× token consumption = $$$$

With TaskSync V5:
  50 tasks in ONE session = 1× token consumption
  Result: ~99% cost reduction
  Token stays alive until user "stop" or expiry
```

### Rules
- ❌ Do NOT use closing phrases ("Let me know if you need anything", etc.)
- ❌ Do NOT end conversation after task completion
- ✅ Always request next task immediately via `run_in_terminal`
- ✅ Keep conversation active between tasks
- ✅ Session ends ONLY on "stop" OR token lifetime expiry

---

**Beispiele:**
| Generisch (❌) | Service-spezifisch (✅) | Warum |
|---------------|------------------------|-------|
| `Session` | `SpotifySession` | Tidal braucht später eigene `TidalSession` |
| `TokenManager` | `SpotifyTokenManager` | Jeder Service hat eigene Token-Logik |
| `AuthRouter` | `SpotifyAuthRouter` | OAuth-Flows unterscheiden sich |
| `PlaylistSync` | `SpotifyPlaylistSync` | Tidal-Playlists haben andere API |
| `sessions` (Tabelle) | `spotify_sessions` | DB-Schema muss Service unterscheiden |

**Wann Service-Präfix verwenden:**
- OAuth/Auth-Klassen → `SpotifyAuth`, `TidalAuth`
- Session/Token-Management → `SpotifySession`, `SpotifyToken`
- API-Client-Wrapper → `SpotifyClient`, `TidalClient`
- Service-spezifische Repositories → `SpotifySessionRepository`
- DB-Tabellen für Service-Daten → `spotify_sessions`, `tidal_tokens`

**Wann KEIN Service-Präfix:**
- Generische Utilities → `AudioFileProcessor`, `MetadataEnricher`
- Domain-Entities → `Track`, `Artist`, `Album` (sind service-agnostisch)
- Shared Infrastructure → `Database`, `CircuitBreaker`, `RateLimiter`

**Zukunftssicherheit:**
```python
# ✅ Erweiterbar für mehrere Services
class SpotifySession: ...
class TidalSession: ...
class DeezerSession: ...

# ❌ Nicht erweiterbar - was wenn Tidal kommt?
class Session: ...  # Welcher Service?
```

### 14.9 Dokumentation immer mitpflegen (DOC-SYNC)

**Bei JEDER Code-Änderung prüfen:**

1. **API-Änderungen** → `docs/api/` aktualisieren
2. **Neue Features** → `README.md` oder Feature-Docs ergänzen
3. **Config-Änderungen** → `.env.example` und `docs/guides/` anpassen
4. **DB-Schema-Änderungen** → Migration UND Docs aktualisieren
5. **Breaking Changes** → `CHANGELOG.md` und Migration-Guide
6. **TODO-Erledigungen** → `docs/TODO.md` und `docs/TODOS_ANALYSIS.md` aktualisieren
7. **Action Plan Tasks** → `docs/ACTION_PLAN.md` Status updaten

**KRITISCH: Tracking-Dokumente SOFORT aktualisieren!**
| Was erledigt? | Sofort aktualisieren |
|---------------|---------------------|
| TODO aus Code entfernt | `docs/TODOS_ANALYSIS.md` |
| Feature implementiert | `docs/TODO.md` + `docs/ACTION_PLAN.md` |
| Migration durchgeführt | `docs/ACTION_PLAN.md` Week-Status |
| Deprecation-Fix | `docs/DEPRECATION_VERIFICATION_REPORT.md` |

**Dokumentations-Checkliste bei PRs:**
- [ ] Betroffene Docs identifiziert
- [ ] Code-Beispiele in Docs noch korrekt
- [ ] Neue Funktionen dokumentiert
- [ ] Veraltete Docs entfernt/aktualisiert
- [ ] TODOs aktualisiert (wenn relevant)
- [ ] ACTION_PLAN.md aktualisiert (wenn Task betroffen)

**Wo Docs leben:**
| Thema | Ort |
|-------|-----|
| API-Referenz | `docs/api/` |
| User-Guides | `docs/guides/` |
| Development | `docs/development/` |
| Architektur | `docs/architecture/` |
| Tracking | `docs/TODO.md`, `docs/ACTION_PLAN.md`, `docs/TODOS_ANALYSIS.md` |

**Verboten:**
- Code ändern ohne zugehörige Docs zu prüfen
- Neue Features ohne Dokumentation als "fertig" markieren
- Veraltete Docs stehen lassen
- TODOs im Code fixen ohne TODOS_ANALYSIS.md zu aktualisieren

```
❌ FALSCH: TODO fixen → Commit → Docs vergessen
✅ RICHTIG: TODO fixen → TODOS_ANALYSIS.md updaten → Commit
```

15. When unsure — minimal reproducible steps to run locally
1. `cp .env.example .env` and fill required keys (Spotify, SLSKD).
2. `poetry install --with dev`
3. `make docker-up` (or run services in local Python env if you prefer)
4. `pytest tests/ -q`

If anything in this file is unclear or missing (CI details, secrets handling, or preferred workflow), please flag the area and I will refine the instructions.

16. PR-Completion Checklist

- "Bevor du einen PR öffnest oder eine Aufgabe als erledigt markierst, führe lokal: `ruff check . --config pyproject.toml`, `mypy --config-file mypy.ini .`, `bandit -r . -f json -o /tmp/bandit-report.json` aus und vermerke in der PR‑Beschreibung je Check Befehl, Exit‑Code, kurze Zahlen (Violations/Errors/HIGH‑Findings) sowie den CodeQL‑Workflow‑Status (GitHub Actions URL oder local run status). Öffne den PR nur, wenn alle Checks erfolgreich sind oder Ausnahmen dokumentiert und freigegeben wurden."

## 16.5 Startup Validation (MANDATORY!)

**CRITICAL RULE**: After ANY code change affecting services, workers, or initialization:

### Required Validation Steps

1. **Import Check** - Verify modified modules can be imported:
   ```python
   python3 -c "from soulspot.main import create_app; print('✅ Main app')"
   python3 -c "from soulspot.infrastructure.lifecycle import lifespan; print('✅ Lifecycle')"
   ```

2. **Error Check** - Use `get_errors` tool to check VS Code diagnostics for modified files

3. **Syntax Check** - Validate Python syntax:
   ```bash
   python3 -m py_compile src/soulspot/path/to/modified_file.py
   ```

4. **Fix Issues** - Resolve ANY import errors, missing dependencies, or initialization errors

5. **Document Results** - Include validation status in task completion message

### Validation Checklist (Copy to Task Completion)

```
✅ Task completed!

**Validation Results:**
- ✅ Import check: All modules import successfully
- ✅ Error check: No errors in VS Code diagnostics
- ✅ Syntax check: No syntax errors found

Files modified: [list files]
```

### When to Validate

**Always validate after changes to:**
- Service constructors (`__init__` methods)
- Worker initialization
- Dependency injection (`api/dependencies.py`)
- Database repositories/models
- Configuration (`config/settings.py`)
- Requirements (`pyproject.toml`, `requirements.txt`)

**Example - Task Completion with Validation:**

```markdown
✅ Task #19 completed: Auto-import filter by completed downloads

**Changes:**
- Added `DownloadRepository.get_completed_track_ids()`
- Modified `AutoImportService.__init__()` to accept `download_repository`
- Updated service initialization in `lifecycle.py`

**Validation:**
- ✅ Import check: `from soulspot.application.services.auto_import import AutoImportService` succeeds
- ✅ Error check: No errors in 4 modified files (via get_errors tool)
- ✅ Syntax check: All files compile successfully

Task completed. Requesting next task from terminal.
```

See: `docs/development/STARTUP_VALIDATION.md` for full protocol.


17. Future-Self Erklärungen als Kommentar für alle Funktionen

**Anweisung für alle Agenten:**  
Jede neue Funktion (public, private, helper usw.) muss einen erklärenden Kommentar direkt davor bekommen.  
Schreib diesen Kommentar als echte, ehrliche Notiz an dein zukünftiges Selbst – genauso, wie du dir nach sechs Monaten beim nochmaligen Lesen auf die Sprünge helfen willst.

**Erklärungstiefe:**  
- Nicht nur erklären, sondern wie ein „drunk note“ an dein forgetful future self: Was war tricky, warum so gebaut, was können Stolperfallen sein?
- Ehrlich, direkt und ohne Marketing-Sprech.
- Sag, was du fast vergessen hättest, wo Bugs lauern oder Workarounds stecken.

**Beispiel:**  
# Hey future me – diese Funktion holt nur die Bilder aus dem Upload-Ordner,
# weil du letztes Jahr aus Versehen system files gelöscht hast. Pass auf bei der Dateiendung!
def get_uploaded_images():





18. Prozessübersicht (Lifecycle)

**Gesamter Lebenszyklus:**  
Plan → Implement (Bulk) → Validate & Fixⁿ → Auto-Code-Review & Auto-Fixⁿ → Docs (DOC-PROOF) → Impact-Fix → Review → Release

---

### **Plan**
**Ziel:** Klaren Scope, Modulgrenzen, Akzeptanzkriterien und Risiken definieren.  
**Agent MUSS:**
- Einen strukturierten Plan aller Module mit Zweck und Schnittstellen erstellen.  
- Abhängigkeiten, Risiken und Akzeptanzkriterien pro Modul identifizieren, bevor die Implementierung startet.  
- Den Plan möglichst als maschinenlesbares Manifest (YAML oder JSON) speichern.

---

### **Implement (Bulk: alle geplanten Module)**
**Ziel:** Alle geplanten Module vollständig mit Tests und minimalen Dokumentations-Platzhaltern implementieren.  
**Agent MUSS:**
- Vollständige Features umsetzen, keine Mikro-Fixes.  
- Strikte Schichtenarchitektur beibehalten (API → Services → Repository → Core).  
- Cross-Cutting-Aspekte (Fehlerbehandlung, Logging, Konfiguration, Sicherheit) konsistent umsetzen.  
- Änderungen logisch gruppiert committen (ein Concern pro Commit).

---

### **Validate & Fixⁿ**  
**Ziel:** Vollständige Validierungszyklen ausführen, bis alle Prüfungen bestehen.  
**Agent MUSS:**
- Komplette Validierung durchführen: Tests, Typprüfungen, Linter, Security-Scanner, Build-Prüfungen.  
- Alle Fehler strukturiert erfassen und in einem Bericht dokumentieren.  
- Iterative Fix-Commits anwenden, bis alle Checks grün sind.  
- Blockierende Fehler priorisieren (Funktionalität/Test/Sicherheit > Formatierung).

---

### **Auto-Code-Review & Auto-Fixⁿ**
**Ziel:** Automatisierte Code-Prüfung und -Korrektur vor menschlichem Review.  
**Agent MUSS:**
- Statische Analysen und Auto-Fix-Tools ausführen (Formatter, Lint-Fixer, einfache Refactorings).  
- Separate Auto-Fix-Commits oder Draft-PRs erzeugen.  
- Nicht automatisch behebbares als `TODO` oder `TECH-DEBT` mit Begründung und Position kennzeichnen.  
- Einen zusammengefassten Bericht aller automatischen Review-Funde erstellen.

---

### **Docs (Finalize + DOC-PROOF)**
**Ziel:** Dokumentation auf Release-Niveau sicherstellen.  
**Agent MUSS:**
- Alle relevanten Dokumente aktualisieren: API, Architektur, Migration, Changelog, README, Beispielverwendungen.  
- Einen **DOC-PROOF** durchführen:
  - Codebeispiele und Dokumentation sind synchron.  
  - Alle Public Contracts sind dokumentiert.  
  - Jedes Thema hat genau eine führende Quelle.  
- Pipeline abbrechen, wenn ein DOC-PROOF-Mismatch erkannt wird.

---

### **Impact-Fix (Trigger: Repo-Scan / Kompatibilitäts-Patches)**
**Ziel:** Repository-weite Seiteneffekte erkennen und beheben.  
**Agent MUSS:**
- Einen **Impact-Scan** durchführen, wenn Folgendes geändert wurde:
  - Public API, Events, DB-Schema, Config oder CLI.  
  - Gemeinsame Utilitys oder globale Patterns.  
- Abhängige Module identifizieren und Kompatibilitäts- oder Deprecation-Patches anwenden.  
- Migrationsanleitungen bei Bedarf aktualisieren.

---

### **Review (Maintainer Approval)**
**Ziel:** Menschlicher Gatekeeper prüft den Merge.  
**Agent MUSS:**
- Den PR so vorbereiten, dass ein Mensch ihn effizient prüfen kann:
  - Klare Zusammenfassung, Zweck, Scope, Risiko und Teststatus.  
  - Annahmen, offene Fragen und bekannte Einschränkungen explizit auflisten.  
- PR erst als `ready-for-review` markieren, wenn alle automatischen Gates grün sind.

---

### **Release (SemVer, Changelog, Tag, Rollback, Doc-Sync)**
**Ziel:** Saubere und nachvollziehbare Veröffentlichung.  
**Agent MUSS:**
- Version nach **Semantic Versioning (SemVer)** bestimmen.  
- Changelog-Eintrag finalisieren und mit Dokumentation synchronisieren.  
- Git-Tag `vX.Y.Z` erstellen oder CI-basiertes Auto-Tagging vorbereiten.  
- Rollback-Plan und bekannte Risiken in den Release-Notes dokumentieren.  
- Sicherstellen, dass alle Dokumente den veröffentlichten Zustand widerspiegeln (Single Source of Truth).


- Bevor du eine Aufgabe als erledigt markierst oder einen PR vorschlägst, **MUSS** Folgendes gelten:
  - `ruff` läuft ohne relevante Verstöße gemäß Projektkonfiguration.
  - `mypy` läuft ohne Typfehler.
  - `bandit` läuft ohne unakzeptable Findings (gemäß Projekt-Policy).
  - `CodeQL`-Workflow in GitHub Actions ist grün (oder lokal äquivalent geprüft).

- Wenn einer dieser Checks fehlschlägt, ist deine Aufgabe **nicht abgeschlossen**:
  - Fixe den Code, bis alle Checks erfolgreich sind.
  - Dokumentiere bei Bedarf Sonderfälle (z. B. legitime False Positives) in der Pull-Request-Beschreibung.