# AI Agents Overview – SoulSpot Bridge

Konsolidierte AI-Agenten für effiziente Entwicklung.

## Agent-Struktur (6 Agents)

```
.github/agents/
├── planner-agent.md              # Planning, Specs, Strategy
├── backend-agent.md              # Python, FastAPI, Backend
├── frontend-agent-pro.md         # HTMX, Templates, UI
├── qa-agent.md                   # Tests, Coverage, Code Quality
├── architecture-guardian-agent.md # Architektur-Enforcement
└── review-agent-new.md           # Pre-PR: Docs, Security, Final
```

## Workflow

```
plan: → backend:/frontend: → test: → arch: → review: → PR
```

| Schritt | Agent | Präfix |
|---------|-------|--------|
| 1. Planung | planner-agent | `plan:`, `spec:` |
| 2. Backend | backend-agent | `backend:`, `api:` |
| 3. Frontend | frontend-agent-pro | `frontend:`, `ui:` |
| 4. Testing | qa-agent | `test:`, `qa:`, `coverage:` |
| 5. Architektur | architecture-guardian | `arch:` |
| 6. Review | review-agent | `review:`, `docs:`, `security:` |

## Agent-Beschreibungen

### 1. Planner Agent (`plan:`, `spec:`)
**Zweck:** Strategische Planung vor Implementation

- Implementation Plans erstellen
- Specification Documents generieren
- Requirements analysieren
- Architektur-Strategie entwickeln

### 2. Backend Agent (`backend:`, `api:`)
**Zweck:** Python/FastAPI Backend-Entwicklung

- FastAPI Routes und Routers
- Service Layer Logic
- Database Operations
- Authentication/Authorization

### 3. Frontend Agent (`frontend:`, `ui:`)
**Zweck:** HTMX/Templates UI-Entwicklung

- HTMX Interactions
- Jinja2 Templates
- CSS/Tailwind Styling
- Responsive Design

### 4. QA Agent (`test:`, `qa:`, `coverage:`)
**Zweck:** Quality Assurance & Testing

- Unit/Integration/E2E Tests schreiben
- Code Quality Reviews
- Coverage-Analyse (min. 80%)
- Linter/Type-Check ausführen

### 5. Architecture Guardian (`arch:`)
**Zweck:** Architektur-Enforcement

- Layer-Violations erkennen
- Port-Repository-Sync prüfen
- Import-Regeln durchsetzen
- Architectural Drift verhindern

### 6. Review Agent (`review:`, `docs:`, `security:`)
**Zweck:** Pre-PR Final Checks

- Documentation Sync prüfen
- Dependency Security Checks
- Changelog erstellen
- Final Quality Gates

## Beispiel-Workflow

```bash
# 1. Planung
plan: Implement new download queue feature

# 2. Backend
backend: Add DownloadQueueService with priority support

# 3. Frontend
frontend: Add download queue UI with progress indicators

# 4. Testing
test: Write unit tests for DownloadQueueService
coverage: Check coverage for new service

# 5. Architektur
arch: Verify layer boundaries for download module

# 6. Review
review: Final pre-PR check
docs: Update API docs for download endpoints
```

## Parallele Ausführung

```bash
parallel: backend: Add API | frontend: Add UI | test: Write tests
```

## Archivierte Agents (Konsolidiert)

| Alt (12 Agents) | Neu (6 Agents) |
|-----------------|----------------|
| plan.agent.md | → planner-agent.md |
| planner.agent.md | → planner-agent.md |
| specification.agent.md | → planner-agent.md |
| review-agent.md (QA) | → qa-agent.md |
| test-coverage-guardian-agent.md | → qa-agent.md |
| code-quality-reviewer-agent.md | → qa-agent.md |
| documentation-sync-agent.md | → review-agent-new.md |
| dependency-security-agent.md | → review-agent-new.md |
| backend-frontend-agent.md | → backend-agent.md |

## Agent Usage Guide

| Scenario | Agent | Präfix |
|----------|-------|--------|
| Neue Feature planen | planner-agent | `plan:` |
| API Endpoints schreiben | backend-agent | `backend:` |
| HTMX UI bauen | frontend-agent | `frontend:` |
| Tests schreiben | qa-agent | `test:` |
| Coverage prüfen | qa-agent | `coverage:` |
| Architektur prüfen | architecture-guardian | `arch:` |
| Docs aktualisieren | review-agent | `docs:` |
| Security Check | review-agent | `security:` |
| Pre-PR Review | review-agent | `review:` |

## Quality Gates

Alle Agents enforced diese Gates vor Completion:
- ✅ `ruff check` passes
- ✅ `mypy` passes
- ✅ `bandit` passes (keine HIGH/CRITICAL)
- ✅ Tests grün (> 80% coverage)

### 4. Structured Output
Agents provide:
- Clear severity levels (CRITICAL, HIGH, MEDIUM, LOW)
- Concrete code examples (not pseudo-code)
- Explanations of WHY, not just WHAT
- Links to relevant documentation

## Integration with Development Workflow

### Pre-Commit Hooks
Quick checks before commit:
- `architecture-guardian-agent` - scan staged files
- `test-coverage-guardian-agent` - check coverage on changed files
- `dependency-security-agent` - scan if dependency files changed

### Pull Request Review
Comprehensive analysis:
- `code-quality-reviewer-agent` - full review
- `architecture-guardian-agent` - architectural compliance
- `test-coverage-guardian-agent` - coverage analysis
- `documentation-sync-agent` - check docs are updated

### CI/CD Pipeline
Automated enforcement:
- All security checks (bandit, dependency-security-agent)
- All quality checks (ruff, mypy, code-quality-reviewer-agent)
- Coverage gates (test-coverage-guardian-agent)

## Agent Maintenance

### Adding New Agents
To add a new agent:
1. Create `.github/agents/your-agent-name.md`
2. Follow the YAML frontmatter format:
   ```yaml
   ---
   name: your-agent-name
   model: Claude 3.5 Sonnet
   color: <color>
   description: Use this agent when...
   ---
   ```
3. Include AI-Model attribution
4. Define clear scope and responsibilities
5. Provide examples and output formats
6. Document success criteria

### Updating Existing Agents
- Keep agent instructions aligned with project evolution
- Update examples to reflect current codebase patterns
- Adjust quality thresholds as project matures

## Success Metrics

Agents are successful when they:
- ✅ Prevent bugs before they reach production
- ✅ Improve code quality over time
- ✅ Reduce manual review burden
- ✅ Educate developers on best practices
- ✅ Maintain consistent standards across codebase

## References

- Original documentation: `docs/version-3.0/AI_AGENT_WORKFLOWS.md`
- Implementation guide: `docs/version-3.0/AI_AGENT_WORKFLOWS_IMPLEMENTATION.md`
- GitHub Copilot Agent docs: `.github/agents/README.md` (this file)

---

**Last Updated:** 2024-11-24
**Total Agents:** 9 (4 existing + 5 new)
**Total Lines:** ~2,920 lines of agent instructions
