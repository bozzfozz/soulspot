# Task Dependency Graph - Plugin System Implementation

**Purpose:** Execution order and parallelization strategy for all 14 Phase 0 tasks.

**Last Updated:** 2025-12-10

---

## Critical Path (Sequential - 4 tasks)

**These MUST be done in order (no parallelization possible):**

```
0.1 IPlugin Interface
    ↓ (blocks 0.2)
0.2 PluginManager
    ↓ (blocks 0.3)
0.3 Service Layer Updates
    ↓ (blocks 0.4)
0.4 FastAPI Dependency Injection
```

**Reasoning:**
- 0.2 needs IPlugin interface to register plugins
- 0.3 needs PluginManager to inject into services
- 0.4 needs updated services to wire up in FastAPI

**Duration:** ~6 hours (sequential work)

---

## Parallel Track A: Infrastructure Layer (5 tasks)

**Can run in parallel AFTER Task 0.1 completes:**

```
[After 0.1 IPlugin is done]
    ├── 0.6 Settings Management (no dependencies)
    ├── 0.7 Rate Limiter (no dependencies)
    ├── 0.8 Circuit Breaker (needs DB schema, but can mock)
    ├── 0.10 IDownloadBackend (no dependencies)
    └── 0.11 IMetadataProvider (no dependencies)
```

**Dependencies:**
- **0.6 Settings:** None (pure Pydantic models)
- **0.7 Rate Limiter:** None (token bucket algorithm, standalone)
- **0.8 Circuit Breaker:** Needs `plugin_health` table (from 0.9), but can use in-memory dict for dev
- **0.10 IDownloadBackend:** None (interface definition)
- **0.11 IMetadataProvider:** None (interface definition)

**Duration:** ~8 hours (2 developers parallel = 4 hours wall time)

---

## Parallel Track B: Data Layer (2 tasks)

**Can run in parallel with Track A:**

```
[After 0.1 IPlugin is done]
    ├── 0.5 SessionManager (needs ServiceSession from 0.1)
    └── 0.9 DB Migration (independent, but blocks 0.8 testing)
```

**Dependencies:**
- **0.5 SessionManager:** Needs `ServiceSession` class from Task 0.1
- **0.9 DB Migration:** None (can run anytime, but other tasks need it for testing)

**Duration:** ~6 hours (1 developer)

**RECOMMENDATION:** Do 0.9 (DB Migration) FIRST, then 0.5 (SessionManager) can use real DB in tests.

---

## Integration Track C (2 tasks)

**Can ONLY run after Critical Path + Parallel Tracks complete:**

```
[After 0.4 FastAPI DI + 0.10 IDownloadBackend + 0.5 SessionManager]
    ├── 0.12 Download Queue Integration
    └── 0.13 Background Workers Refactoring
```

**Dependencies:**
- **0.12 Download Queue:** Needs 0.3 (Service Layer), 0.9 (DB), 0.10 (IDownloadBackend)
- **0.13 Background Workers:** Needs 0.2 (PluginManager), 0.5 (SessionManager)

**Duration:** ~5 hours (sequential)

---

## Testing Task (Ongoing)

```
0.14 Testing Strategy
    → Runs throughout ALL tasks (unit tests per task)
    → Final integration tests in Phase 1
```

**Dependencies:** None (can write test strategy docs anytime)

**Duration:** ~2 hours (documentation), ongoing (test writing)

---

## Execution Plan (Optimized for Speed)

### **Week 1 - Day 1-2: Critical Path**
```
Hour 0-2:   Task 0.1 (IPlugin Interface)
Hour 2-4:   Task 0.2 (PluginManager)
Hour 4-7:   Task 0.3 (Service Layer Updates)
Hour 7-9:   Task 0.4 (FastAPI DI)
Hour 9-10:  Integration Testing (0.1-0.4 work together)
```

**Deliverable:** Core plugin system functional (can register mock plugins)

---

### **Week 1 - Day 3-5: Parallel Infrastructure + Data**

**Developer 1 (Infrastructure Track A):**
```
Day 3: 0.6 Settings + 0.7 Rate Limiter
Day 4: 0.10 IDownloadBackend + 0.11 IMetadataProvider
Day 5: 0.8 Circuit Breaker (after 0.9 DB ready)
```

**Developer 2 (Data Track B):**
```
Day 3: 0.9 DB Migration (PRIORITY - others need this!)
Day 4: 0.5 SessionManager
Day 5: Integration Testing (all tracks combined)
```

**Deliverable:** All infrastructure + data components ready

---

### **Week 2 - Day 1-2: Integration Track C**
```
Day 1: 0.12 Download Queue Integration
Day 2: 0.13 Background Workers Refactoring
```

**Deliverable:** Phase 0 complete!

---

### **Week 2 - Day 3-5: Phase 1 (Spotify Plugin)**
```
Day 3: 1.1 Plugin Directory Structure + 1.2 SpotifyPlugin (Part 1)
Day 4: 1.2 SpotifyPlugin (Part 2) + 1.3 OAuth Routes
Day 5: Integration Testing (Spotify works via plugin)
```

**Deliverable:** Spotify migrated to plugin system

---

## Dependency Matrix (Visual)

```
                    ┌──────────┐
                    │ 0.1 IPlugin│
                    └─────┬────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   ┌─────────┐      ┌──────────┐     ┌──────────┐
   │0.2 Plugin│      │0.5 Session│     │0.6 Settings│
   │ Manager  │      │ Manager   │     │          │
   └────┬────┘      └──────────┘     └──────────┘
        │
        ▼
   ┌─────────┐      ┌──────────┐     ┌──────────┐
   │0.3 Service│     │0.7 Rate  │     │0.8 Circuit│
   │  Layer   │     │ Limiter  │     │ Breaker  │
   └────┬────┘      └──────────┘     └─────┬────┘
        │                                   │
        ▼                                   │
   ┌─────────┐      ┌──────────┐          │
   │0.4 FastAPI│     │0.9 DB    │◄─────────┘
   │    DI    │     │Migration │
   └────┬────┘      └─────┬────┘
        │                 │
        └────────┬────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   ┌─────────┐      ┌──────────┐
   │0.10     │      │0.11      │
   │Download │      │Metadata  │
   │Backend  │      │Provider  │
   └────┬────┘      └──────────┘
        │
        ▼
   ┌─────────┐      ┌──────────┐
   │0.12     │      │0.13      │
   │Download │      │Background│
   │Queue    │      │Workers   │
   └─────────┘      └──────────┘
```

---

## Risk Assessment

### **High-Risk Tasks (Careful Execution Required):**
1. **0.3 Service Layer Updates** - Touches many existing files, high merge conflict risk
2. **0.9 DB Migration** - Data loss risk if migration fails
3. **0.13 Background Workers** - Affects live sync, downtime risk

### **Low-Risk Tasks (Can move fast):**
1. **0.1 IPlugin** - New file, no existing code touched
2. **0.6 Settings** - Pure config, easy to test
3. **0.7 Rate Limiter** - Standalone utility

---

## Blockers & Mitigation

| Blocker | Impact | Mitigation |
|---------|--------|------------|
| 0.9 DB Migration fails | Blocks 0.8, 0.12 testing | Test migration on dev DB first, backup prod |
| 0.3 Service Layer breaks tests | Blocks 0.4 | Run tests after EVERY file edit |
| Team unavailable (sick/vacation) | Delays parallel work | Have 1 developer who can do full stack |

---

## Success Criteria (Phase 0 Complete)

✅ All 14 tasks implemented  
✅ Existing Spotify functionality works (old path)  
✅ Plugin system functional (can register mock plugins)  
✅ All existing tests pass  
✅ DB migration successful (no data loss)  
✅ Documentation updated  

**Ready for Phase 1:** Spotify → SpotifyPlugin migration
