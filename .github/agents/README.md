# AI Agents Overview - SoulSpot Bridge

This document provides an overview of all AI agents available in `.github/agents/` for the SoulSpot Bridge project.

## Agent Directory Structure

```
.github/agents/
├── architecture-guardian-agent.md        (NEW)
├── backend-agent.md                      (Existing)
├── backend-frontend-agent.md             (Existing)
├── code-quality-reviewer-agent.md        (NEW)
├── dependency-security-agent.md          (NEW)
├── documentation-sync-agent.md           (NEW)
├── frontend-agent.md                     (Existing)
├── review-agent.md                       (Existing)
└── test-coverage-guardian-agent.md       (NEW)
```

## Existing Agents (4)

### 1. **backend-agent** 
- **Model:** Claude 3.5 Sonnet
- **Color:** Red
- **Purpose:** Server-side Python FastAPI/Flask application logic, API endpoints, database operations, service layer implementations, backend architecture decisions
- **Expertise:** Clean/Onion Architecture, dependency injection, repository pattern, async/await

### 2. **frontend-agent**
- **Model:** Google Gemini 3 Pro
- **Color:** Blue
- **Purpose:** HTMX-based interactions, TailwindCSS-styled UIs, FastAPI server-rendered HTML templates
- **Expertise:** Progressive enhancement, responsive design, accessibility (WCAG 2.1), HTMX integration patterns

### 3. **review-agent**
- **Model:** (Not specified)
- **Color:** Cyan
- **Purpose:** QA & Test Automation for FastAPI + HTMX + SQLAlchemy + SQLite applications
- **Expertise:** Unit/integration/E2E testing, coverage requirements (≥90%), pytest, playwright

### 4. **backend-frontend-agent**
- **Model:** (From config)
- **Color:** (From config)
- **Purpose:** Integration between backend and frontend, ensuring cohesive system behavior
- **Expertise:** Cross-layer coordination, architectural consistency

## New Agents (5)

### 1. **architecture-guardian-agent** ⭐
- **Model:** Claude 3.5 Sonnet
- **Color:** Purple
- **Purpose:** Enforce architectural principles and prevent architectural drift
- **Key Responsibilities:**
  - Database Module enforcement (no direct SQLAlchemy outside DB layer)
  - Settings Service enforcement (no direct `os.getenv`)
  - Structured Errors enforcement (no generic exceptions)
  - Module Boundaries enforcement (no cross-module imports)
  - Type Hints enforcement (mypy strict mode)
- **Output:** Detailed violation reports with concrete fixes, line numbers, and documentation links
- **Severity Levels:** CRITICAL, HIGH, MEDIUM, LOW

### 2. **test-coverage-guardian-agent** ⭐
- **Model:** Claude 3.5 Sonnet
- **Color:** Green
- **Purpose:** Prevent test coverage regression and suggest concrete, actionable tests
- **Key Responsibilities:**
  - Measure and report coverage (target: ≥80%, service layer: 100%)
  - Identify under-tested files and specific untested lines
  - Generate complete, copy-paste-ready pytest test code
  - Suggest tests for error handling, edge cases, async operations
- **Output:** Coverage reports with concrete test suggestions including fixtures and mocks
- **Coverage Thresholds:** <70% CRITICAL, 70-79% WARNING, 80-89% ACCEPTABLE, 90%+ EXCELLENT

### 3. **documentation-sync-agent** ⭐
- **Model:** GPT-4o
- **Color:** Yellow
- **Purpose:** Keep documentation synchronized with code changes
- **Key Responsibilities:**
  - API documentation (when FastAPI routes change)
  - Architecture & module documentation (when modules change)
  - Database & migration documentation (when Alembic migrations added)
  - README & getting started (when installation/config changes)
  - Changelog & release notes (on significant changes)
- **Output:** Documentation update proposals with complete markdown content
- **Quality Checks:** Accuracy, completeness, consistency, clarity

### 4. **dependency-security-agent** ⭐
- **Model:** Claude 3.5 Sonnet
- **Color:** Orange
- **Purpose:** Check dependencies for security vulnerabilities before adding them
- **Key Responsibilities:**
  - Scan dependencies against GitHub Advisory Database, Safety DB, npm audit
  - Check for CVEs and known vulnerabilities
  - Verify license compatibility (MIT, Apache, BSD ✅; GPL, AGPL ⚠️)
  - Detect supply chain attacks (typosquatting, malware)
  - Prioritize fixes by severity (CRITICAL, HIGH, MODERATE, LOW)
- **Output:** Security reports with CVE details, CVSS scores, fix commands, and urgency levels
- **Ecosystems:** Python (pip), JavaScript (npm), GitHub Actions

### 5. **code-quality-reviewer-agent** ⭐
- **Model:** Claude 3.5 Sonnet
- **Color:** Blue
- **Purpose:** Comprehensive automated code reviews
- **Key Responsibilities:**
  - Run and analyze ruff, mypy, bandit
  - Check for DRY violations and SOLID principles
  - Review documentation quality (docstrings, comments)
  - Identify performance issues (N+1 queries, sequential async)
  - Ensure adequate test coverage
- **Output:** Structured reviews with critical/important/minor issues, concrete fixes, and positive highlights
- **Review Dimensions:** Code quality, architecture, documentation, performance, testing

## Agent Usage Guide

### When to Use Which Agent

| Scenario | Recommended Agent |
|----------|-------------------|
| Writing new API endpoints | `backend-agent` |
| Building HTMX UI components | `frontend-agent` |
| Coordinating backend-frontend integration | `backend-frontend-agent` |
| Checking architectural compliance | `architecture-guardian-agent` ⭐ |
| Reviewing test coverage | `test-coverage-guardian-agent` ⭐ |
| Updating documentation | `documentation-sync-agent` ⭐ |
| Adding new dependencies | `dependency-security-agent` ⭐ |
| Comprehensive code review | `code-quality-reviewer-agent` ⭐ |
| Writing/reviewing tests | `review-agent` |

### Agent Workflow (Recommended Order)

For a complete feature development cycle:

1. **Development Phase:**
   - Use `backend-agent` or `frontend-agent` for implementation
   - Use `backend-frontend-agent` for integration

2. **Quality Assurance Phase:**
   - Run `architecture-guardian-agent` to check architectural compliance
   - Run `test-coverage-guardian-agent` to ensure adequate testing
   - Run `code-quality-reviewer-agent` for comprehensive review
   - Use `review-agent` to write/improve tests

3. **Pre-Commit Phase:**
   - Run `dependency-security-agent` if dependencies changed
   - Run `documentation-sync-agent` to update docs

4. **Pre-Merge Phase:**
   - Final check with `code-quality-reviewer-agent`
   - Verify all critical issues resolved

## Common Agent Patterns

All agents follow these patterns:

### 1. AI Model Attribution
Every agent file includes:
```markdown
# AI-Model: <model-name>
```

### 2. Future-Self Comments
Agents encourage "future-self" explanatory comments:
```python
# Hey future me - this function does X because Y.
# Watch out for Z when modifying.
```

### 3. Quality Gates
All agents enforce quality gates before considering work complete:
- ✅ `ruff` passes
- ✅ `mypy` passes
- ✅ `bandit` passes (no HIGH/CRITICAL findings)
- ✅ CodeQL workflow green

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
