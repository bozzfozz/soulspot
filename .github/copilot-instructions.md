<!-- Copied/merged for AI coding agents: concise, actionable guidance for contributors and assistants -->
# Copilot / AI Assistant Instructions

This file contains focused, repository-specific guidance to help AI coding agents be productive immediately.

1. Purpose & Big Picture
- **What:** SoulSpot Bridge syncs Spotify playlists and downloads tracks via the Soulseek `slskd` service, enriches metadata and stores organized music files.
- **Architecture:** Python FastAPI app (async SQLAlchemy) in `src/soulspot`, background workers coordinating with `slskd`, and a web UI. DB migrations in `alembic/`.

2. Recommended dev environment
- **Prefer:** `poetry` (project declares `pyproject.toml`). Use `poetry install --with dev` to get dev tools (mypy, ruff, pytest).
- **Alternative:** The `Makefile` exposes pragmatic targets (install/test/lint/format). CI may still rely on `pip` + `requirements.txt`.

3. Key commands (examples)
- Install deps (poetry): `poetry install --with dev`
- Run tests: `pytest tests/ -v` or `make test`
- Run unit-only: `make test-unit`
- Run coverage: `make test-cov`
- Lint/format: `make lint` / `make format` (ruff)
- Type-check: `make type-check` (mypy)
- Security scan: `make security` (bandit)
- Start Docker stack: `make docker-up` (uses `docker/docker-compose.yml`)
- DB migrations: `alembic upgrade head` (or `make db-upgrade`)

4. Project layout & important files to inspect
- `src/soulspot/` — application package (API, services, CLI entry `soulspot.main:main`).
- `alembic/` — migration scripts and `env.py` (DB setup). Look at `alembic/versions/` for schema history.
- `docker/` — `docker-compose.yml`, `docker-compose.dev.yml`, and service settings; `docker/README.md` for container setup.
- `tests/` — unit and integration tests. Pytest config is in `pyproject.toml` (testpaths, pytest plugins).
- `pyproject.toml` — dependencies, tooling (ruff, mypy, pytest) and strict type rules.
- `Makefile` / `Justfile` — convenient task shortcuts used by contributors and CI.

5. Code patterns & conventions (observable)
- **Strict typing:** `mypy` is enabled with `strict = true`. Follow typed function signatures for public code.
- **Formatting & linting:** `ruff` is the primary linter/formatter. Follow its config in `pyproject.toml`.
- **Async DB usage:** SQLAlchemy async engine is used (see `src/soulspot/*` and `alembic/env.py`); tests use `pytest-asyncio`.
- **Tests path:** tests live under `tests/`; use `factory_boy`, `pytest-mock`, and `pytest-httpx` for HTTP clients.

6. Integration points & external services
- **Spotify OAuth:** Credentials in `.env` (see `.env.example`), required for playlist sync.
- **slskd (Soulseek):** External downloader; API key or username/password configured via env. The app expects `mnt/downloads` and `mnt/music` mounts for files.
- **Music metadata:** MusicBrainz and CoverArtArchive APIs are used for enrichment.

7. When editing code (practical rules)
- Run `make format` and `make lint` before opening a PR.
- Add/adjust type hints to satisfy `mypy` (CI enforces strict settings). Prefer explicit return types and parameter types.
- For DB schema changes: add an Alembic revision under `alembic/versions/` and update `alembic.ini` if needed; run migrations locally with `make db-upgrade`.

8. Tests and CI expectations
- Unit and integration tests run under `pytest` using config in `pyproject.toml`. Use `pytest --maxfail=1 -q` for quick local feedback.
- Coverage is gathered with `make test-cov` and HTML output is in `htmlcov/`.

9. Files/locations an AI should open first for context
- `src/soulspot/main.py` (entry/CLI)
- `src/soulspot/api/` (routes and request flow)
- `alembic/env.py` and `alembic/versions/` (DB migrations)
- `docker/docker-compose.yml` and `docker/README.md` (runtime environment)
- `pyproject.toml` (tooling and strict config)

10. Useful examples to copy or follow
- When adding async DB code, mirror patterns used in `src/soulspot/repository/*` and the session management in `alembic/env.py`.
- For HTTP clients, prefer `httpx` and follow testing style in `tests/` using `pytest-httpx`.

11. What not to assume
- Do not assume `pip` is the canonical source of truth — the repo uses Poetry in `pyproject.toml`, but the `Makefile` contains pragmatic pip-based targets used by some workflows.
- Do not assume synchronous DB usage; code is primarily async.

12. When unsure — minimal reproducible steps to run locally
1. `cp .env.example .env` and fill required keys (Spotify, SLSKD).
2. `poetry install --with dev`
3. `make docker-up` (or run services in local Python env if you prefer)
4. `pytest tests/ -q`

If anything in this file is unclear or missing (CI details, secrets handling, or preferred workflow), please flag the area and I will refine the instructions.
## 2.0 Prozessübersicht

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


All quality checks must pass: ruff, mypy, bandit, codeql.
