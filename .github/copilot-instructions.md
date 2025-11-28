
# Copilot / AI Assistant Instructions

This file contains focused, repository-specific guidance to help AI coding agents be productive immediately.

1. Purpose & Big Picture
- **What:** SoulSpot syncs Spotify playlists and downloads tracks via the Soulseek `slskd` service, enriches metadata and stores organized music files.
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
- When adding async DB code, mirror patterns used in `src/soulspot/infrastructure/persistence/repositories.py` and the session management in `alembic/env.py`.
- For HTTP clients, prefer `httpx` and follow testing style in `tests/` using `pytest-httpx`.

11. What not to assume
- Do not assume `pip` is the canonical source of truth — the repo uses Poetry in `pyproject.toml`, but the `Makefile` contains pragmatic pip-based targets used by some workflows.
- Do not assume synchronous DB usage; code is primarily async.

12. Reserved (placeholder for future use)

13. Verify Before Writing (PFLICHT)

**Anweisung für alle Agenten:**  
Bevor du Pfade, Konfigurationswerte, Dateinamen oder technische Details in Code oder Dokumentation schreibst, **MUSST** du diese im Repository verifizieren.

**Was IMMER zu prüfen ist:**
- **Dateipfade:** Prüfe `.env.example`, `settings.py`, `docker-compose.yml` für tatsächliche Pfade (z.B. DB-Pfad ist `./soulspot.db` lokal, `/config/soulspot.db` in Docker – NICHT `data/soulspot.db`)
- **Konfigurationswerte:** Lies die tatsächlichen Defaults aus dem Code, nicht raten
- **Klassennamen/Imports:** Nutze `grep_search` oder `read_file` um existierende Namen zu verifizieren
- **Test-Dateipfade:** Prüfe die tatsächliche Verzeichnisstruktur unter `tests/`
- **Port-Nummern, URLs, API-Endpunkte:** Verifiziere gegen den tatsächlichen Code

**Verboten:**
- Pfade oder Werte aus dem Gedächtnis oder "üblichen Konventionen" schreiben
- Annahmen über Verzeichnisstrukturen ohne Verifizierung
- Dateien referenzieren die nicht existieren

**Beispiel-Workflow:**
```
❌ FALSCH: "Die DB liegt unter data/soulspot.db"
✅ RICHTIG: Erst `.env.example` lesen → DATABASE_URL=sqlite+aiosqlite:///./soulspot.db → "Die DB liegt unter ./soulspot.db"
```

14. Häufige Fehlerquellen vermeiden (Lessons Learned)

### 14.1 Interface-Repository-Sync
Wenn du eine Methode zu einem Repository hinzufügst (z.B. `TrackRepository.get_by_isrc()`), **MUSST** du auch das entsprechende Interface in `src/soulspot/domain/ports/__init__.py` aktualisieren.

```
❌ FALSCH: Nur TrackRepository.get_by_isrc() hinzufügen
✅ RICHTIG: Auch ITrackRepository.get_by_isrc() als abstrakte Methode hinzufügen
```

### 14.2 Export-Vollständigkeit
Neue Klassen/Funktionen müssen in der `__init__.py` des Moduls exportiert werden, sonst sind sie nicht importierbar.

**Checkliste bei neuen Klassen:**
- [ ] Klasse in `__init__.py` importieren
- [ ] Klasse zu `__all__` hinzufügen (falls vorhanden)

### 14.3 Migration-Kette prüfen
Bevor du eine neue Alembic-Migration erstellst:
1. `ls alembic/versions/` ausführen um die letzte Revision zu finden
2. `down_revision` auf die **tatsächlich letzte** Migration setzen
3. Bei Merge-Konflikten: `alembic merge heads` nutzen

### 14.4 Bestehenden Code nicht duplizieren
**Vor jeder Implementierung:**
1. `grep_search` nach ähnlichen Funktionsnamen/Patterns
2. Prüfen ob Service/Repository/Helper bereits existiert
3. Bestehende Patterns wiederverwenden statt neu erfinden

```
❌ FALSCH: Neue `get_spotify_token()` Funktion schreiben
✅ RICHTIG: Erst suchen → DatabaseTokenManager existiert bereits → wiederverwenden
```

### 14.5 Async-Konsistenz
**ALLE** Datenbankoperationen müssen `async`/`await` nutzen. Keine synchronen DB-Calls!

```python
# ❌ FALSCH
def get_track(self, id):
    return self.session.query(Track).get(id)

# ✅ RICHTIG  
async def get_track(self, id):
    result = await self.session.execute(select(Track).where(Track.id == id))
    return result.scalar_one_or_none()
```

### 14.6 Test-Datei-Struktur spiegelt Source-Struktur
Tests müssen die Source-Struktur spiegeln:
- `src/soulspot/application/services/foo.py` → `tests/unit/application/services/test_foo.py`
- **NICHT:** `tests/unit/test_foo.py`

### 14.7 Keine Placeholder/Stubs als "fertig" markieren
Eine Funktion ist **NICHT fertig** wenn sie:
- `pass` oder `...` enthält
- `# TODO` hat
- Nur `return None` ohne Logik
- Einen `NotImplementedError` wirft

### 14.8 Service-spezifische Namenskonvention (Erweiterbarkeit)

Bei Klassen/Modulen die **service-spezifisch** sind (Spotify, Tidal, Deezer, etc.), **MUSS** der Service-Name im Namen enthalten sein für spätere Erweiterbarkeit.

**Namensschema:**
```
{ServiceName}{Funktion}
```

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

**Dokumentations-Checkliste bei PRs:**
- [ ] Betroffene Docs identifiziert
- [ ] Code-Beispiele in Docs noch korrekt
- [ ] Neue Funktionen dokumentiert
- [ ] Veraltete Docs entfernt/aktualisiert

**Wo Docs leben:**
| Thema | Ort |
|-------|-----|
| API-Referenz | `docs/api/` |
| User-Guides | `docs/guides/` |
| Development | `docs/development/` |
| Architektur | `docs/architecture/` (falls vorhanden) |
| Beispiele | `docs/examples/` |

**Verboten:**
- Code ändern ohne zugehörige Docs zu prüfen
- Neue Features ohne Dokumentation als "fertig" markieren
- Veraltete Docs stehen lassen

```
❌ FALSCH: Feature implementieren → PR öffnen → Docs vergessen
✅ RICHTIG: Feature implementieren → Docs aktualisieren → PR öffnen
```

15. When unsure — minimal reproducible steps to run locally
1. `cp .env.example .env` and fill required keys (Spotify, SLSKD).
2. `poetry install --with dev`
3. `make docker-up` (or run services in local Python env if you prefer)
4. `pytest tests/ -q`

If anything in this file is unclear or missing (CI details, secrets handling, or preferred workflow), please flag the area and I will refine the instructions.

16. PR-Completion Checklist

- "Bevor du einen PR öffnest oder eine Aufgabe als erledigt markierst, führe lokal: `ruff check . --config pyproject.toml`, `mypy --config-file mypy.ini .`, `bandit -r . -f json -o /tmp/bandit-report.json` aus und vermerke in der PR‑Beschreibung je Check Befehl, Exit‑Code, kurze Zahlen (Violations/Errors/HIGH‑Findings) sowie den CodeQL‑Workflow‑Status (GitHub Actions URL oder local run status). Öffne den PR nur, wenn alle Checks erfolgreich sind oder Ausnahmen dokumentiert und freigegeben wurden."



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