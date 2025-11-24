# AI Agent Workflows - Praktische Implementierung für SoulSpot

## Inhaltsverzeichnis

1. [Quick Start](#quick-start)
2. [Installation & Setup](#installation--setup)
3. [Empfohlene Workflows für SoulSpot](#empfohlene-workflows-für-soulspot)
4. [Workflow-Templates](#workflow-templates)
5. [Konfiguration & Customization](#konfiguration--customization)
6. [Troubleshooting](#troubleshooting)
7. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Quick Start

### 5-Minuten-Setup für SoulSpot

**Schritt 1: CLI installieren**
```bash
# GitHub CLI installieren (falls noch nicht vorhanden)
brew install gh  # macOS
# oder
sudo apt install gh  # Linux

# gh-aw Extension installieren
gh extension install githubnext/gh-aw
```

**Schritt 2: Authentifizierung**
```bash
# GitHub authentifizieren
gh auth login

# API-Key für AI-Modell konfigurieren (Beispiel: Anthropic Claude)
gh secret set ANTHROPIC_API_KEY --body "sk-ant-..."
```

**Schritt 3: Ersten Workflow hinzufügen**
```bash
cd /path/to/soulspot

# Beispiel: Issue Triage (Read-Only, sicher zum Testen)
gh aw add githubnext/agentics/issue-triage --pr
```

**Schritt 4: PR reviewen und mergen**
```bash
# PR wurde automatisch erstellt, reviewen:
gh pr view
gh pr merge
```

**Fertig!** Der Workflow wird bei neuen Issues automatisch getriggert.

---

## Installation & Setup

### Voraussetzungen

**Systemanforderungen:**
- Git 2.30+
- GitHub CLI (gh) 2.40+
- Repository mit Admin-Rechten
- GitHub Actions aktiviert

**Account-Anforderungen:**
- GitHub Account mit Repo-Zugriff
- API-Key für AI-Modell (siehe [Modell-Auswahl](#modell-auswahl))

### Detaillierte Installation

#### 1. GitHub CLI installieren

**macOS:**
```bash
brew install gh
```

**Linux (Debian/Ubuntu):**
```bash
type -p curl >/dev/null || (sudo apt update && sudo apt install curl -y)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh -y
```

**Windows:**
```powershell
winget install --id GitHub.cli
```

**Verifizierung:**
```bash
gh --version
# Ausgabe: gh version 2.40.1 (oder höher)
```

#### 2. gh-aw Extension installieren

```bash
gh extension install githubnext/gh-aw

# Verifizierung
gh aw --version
```

#### 3. Repository vorbereiten

**GitHub Actions aktivieren:**
```bash
# In Repository-Settings
Settings → Actions → General
→ ✅ "Allow all actions and reusable workflows"
→ ✅ "Allow GitHub Actions to create and approve pull requests"
```

**Branch Protection (Optional, empfohlen):**
```bash
Settings → Branches → Add rule
→ Branch name pattern: main
→ ✅ "Require pull request reviews before merging"
→ ✅ "Require status checks to pass before merging"
```

### Modell-Auswahl

#### Option 1: GitHub Copilot (Empfohlen für Integration)

**Vorteile:**
- Nahtlose GitHub-Integration
- Keine separate API-Key-Verwaltung
- Zugriff auf mehrere Modelle (Claude, GPT-4, Gemini)

**Setup:**
```bash
# GitHub Copilot Subscription erforderlich ($10-19/Monat)
# Kein separater API-Key nötig, nutzt GitHub Token
```

**Workflow-Konfiguration:**
```markdown
---
engine: copilot  # Oder: claude-3-5-sonnet, gpt-4o, gemini-pro
---
```

#### Option 2: Anthropic Claude (Empfohlen für Qualität)

**Vorteile:**
- Beste Reasoning-Qualität
- Große Context-Window (200K tokens)
- Exzellent für komplexe Architektur-Checks

**Setup:**
```bash
# API-Key von https://console.anthropic.com/
gh secret set ANTHROPIC_API_KEY --body "sk-ant-..."
```

**Workflow-Konfiguration:**
```markdown
---
engine: claude-3-5-sonnet
---
```

**Kosten:**
- Input: $3 / 1M tokens
- Output: $15 / 1M tokens
- Geschätzt: $5-20/Monat für SoulSpot (abhängig von Nutzung)

#### Option 3: OpenAI GPT-4

**Vorteile:**
- Schnelle Response-Zeiten
- Gute Python/FastAPI-Kenntnisse
- Günstigere Option

**Setup:**
```bash
# API-Key von https://platform.openai.com/
gh secret set OPENAI_API_KEY --body "sk-..."
```

**Workflow-Konfiguration:**
```markdown
---
engine: gpt-4o  # Oder: gpt-4o-mini (günstiger)
---
```

**Kosten:**
- GPT-4o: Input $2.50/1M, Output $10/1M
- GPT-4o mini: Input $0.15/1M, Output $0.60/1M

---

## Empfohlene Workflows für SoulSpot

### Prioritäts-Matrix

| Workflow | Priorität | Setup-Zeit | Nutzen | Risiko |
|----------|-----------|------------|--------|--------|
| **Architecture Guardian** | 🔴 Hoch | 30 min | Verhindert Architektur-Drift | Niedrig |
| **Test Coverage Guardian** | 🔴 Hoch | 30 min | Verhindert Coverage-Rückgang | Niedrig |
| **Code Quality Reviewer** | 🟡 Mittel | 20 min | Automatisches Code-Review | Niedrig |
| **Documentation Sync** | 🟡 Mittel | 25 min | Docs aktuell halten | Mittel |
| **Dependency Updater** | 🟢 Niedrig | 30 min | Security & Freshness | Mittel |
| **Daily Progress** | 🟢 Niedrig | 45 min | Feature-Entwicklung | Hoch |

### Empfohlene Reihenfolge

**Phase 1: Safety First (Woche 1)**
1. ✅ Architecture Guardian (Prevent architectural violations)
2. ✅ Test Coverage Guardian (Ensure quality)

**Phase 2: Quality Automation (Woche 2-3)**
3. ✅ Code Quality Reviewer (Automated reviews)
4. ✅ Documentation Sync (Keep docs fresh)

**Phase 3: Automation Expansion (Woche 4+)**
5. ⚠️ Dependency Updater (Mit Vorsicht, Test-Suite muss robust sein)
6. ⚠️ Daily Progress (Nur experimentell, intensives Monitoring)

---

## Workflow-Templates

### Template 1: SoulSpot Architecture Guardian

**Zweck:** Stelle sicher, dass Code SoulSpot v3.0 Architektur-Prinzipien folgt

**Datei:** `.github/workflows/agentics/soulspot-architecture-guardian.md`

```markdown
---
name: SoulSpot Architecture Guardian
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
safe-outputs:
  create-comment:
    max: 1
    body-max-length: 15000
tools:
  - bash
  - read-file
  - list-files
engine: claude-3-5-sonnet
timeout-minutes: 15
stop-after: 30 days
---

# SoulSpot Architecture Guardian

Du bist der Architektur-Wächter für SoulSpot v3.0.

## Architektur-Prinzipien

### 1. Database Module (CRITICAL)
**Regel:** ALLE DB-Operationen über `DatabaseService`

✅ **Erlaubt:**
```python
from soulspot.database import DatabaseService
db = DatabaseService()
user = await db.get_entity("User", user_id)
```

❌ **Verboten:**
```python
from sqlalchemy import create_engine
session.query(User).first()  # DIREKT SQLAlchemy
```

### 2. Settings Service (CRITICAL)
**Regel:** ALLE Config-Zugriffe über `SettingsService`

✅ **Erlaubt:**
```python
from soulspot.settings import SettingsService
settings = SettingsService()
api_key = await settings.get("spotify.client_id")
```

❌ **Verboten:**
```python
import os
api_key = os.getenv("SPOTIFY_CLIENT_ID")  # DIREKT ENV
```

### 3. Structured Errors (CRITICAL)
**Regel:** Alle Exceptions strukturiert

✅ **Erlaubt:**
```python
raise SoulspotError(
    code="AUTH_FAILED",
    message="Authentication failed",
    context={"user_id": user_id},
    resolution="Re-authenticate",
    docs_url="https://docs.soulspot.dev/errors/AUTH_FAILED"
)
```

❌ **Verboten:**
```python
raise Exception("Auth failed")  # GENERISCH
```

### 4. Module Boundaries (CRITICAL)
**Regel:** Keine direkten Cross-Module Imports

✅ **Erlaubt:**
```python
from soulspot.events import EventBus
event_bus.publish("spotify.synced", {...})
```

❌ **Verboten:**
```python
from soulspot.spotify import SpotifyService  # In soulseek Module
```

### 5. Type Hints (HIGH)
**Regel:** Alle Public Functions mit Type Hints

✅ **Erlaubt:**
```python
async def get_playlist(self, id: str) -> Playlist:
    ...
```

❌ **Verboten:**
```python
async def get_playlist(self, id):  # KEINE HINTS
    ...
```

## Aufgabe

1. **Scanne alle geänderten Python-Dateien** auf Violations
2. **Kategorisiere nach Severity:** CRITICAL, HIGH, MEDIUM, LOW
3. **Erstelle detaillierten Kommentar:**
   - Liste aller Violations
   - Konkrete Code-Snippets
   - Exakte Fix-Vorschläge
   - Links zur Dokumentation

## Output Format

```markdown
## 🏛️ Architecture Compliance Report

**Status:** ❌ FAILED (2 violations)

### ❌ CRITICAL: Direct SQLAlchemy Usage
**File:** `src/soulspot/services/spotify.py`
**Line:** 45

**Violation:**
```python
45: session.query(User).filter_by(id=user_id).first()
```

**Fix:**
```python
user = await database_service.get_entity("User", {"id": user_id})
```

**Docs:** [Database Module Guide](link)

---

### Summary
- 2 violations (1 CRITICAL, 1 HIGH)
- Fix CRITICAL before merge
```

## Fehlerbehandlung
- Bei Scan-Fehler: Logge, fahre fort
- Keine Python-Dateien: "No Python files, skipping ✅"
```

**Installation:**
```bash
cd /path/to/soulspot
gh aw compile .github/workflows/agentics/soulspot-architecture-guardian.md
git add .github/workflows/agentics/soulspot-architecture-guardian.md
git add .github/workflows/soulspot-architecture-guardian.yml
git commit -m "feat(ci): Add Architecture Guardian workflow"
git push
```

---

### Template 2: SoulSpot Test Coverage Guardian

**Zweck:** Verhindere Coverage-Rückgang, schlage konkrete Tests vor

**Datei:** `.github/workflows/agentics/soulspot-test-coverage-guardian.md`

```markdown
---
name: SoulSpot Test Coverage Guardian
on:
  pull_request:
    types: [opened, synchronize]
permissions:
  contents: read
  pull-requests: write
  statuses: write
safe-outputs:
  create-comment:
    max: 1
    body-max-length: 10000
  create-status:
    max: 1
tools:
  - bash
  - read-file
  - list-files
engine: claude-3-5-sonnet
timeout-minutes: 20
stop-after: 30 days
---

# SoulSpot Test Coverage Guardian

Du bist QA Engineer für SoulSpot v3.0.

## Kontext
- **Framework:** FastAPI + SQLAlchemy (async)
- **Tests:** pytest + pytest-asyncio
- **Ziel:** >80% Coverage

## Aufgabe

### 1. Coverage messen
```bash
poetry install --with dev
make test-cov
```

### 2. Coverage analysieren
- Parse `htmlcov/index.html`
- Identifiziere Files <80%
- Finde geänderte Dateien (git diff)
- Cross-reference: Geänderte Files mit niedriger Coverage

### 3. Test-Vorschläge generieren
Für jede unter-getestete Datei:
- Analysiere Code
- Identifiziere ungetestete Funktionen
- Identifiziere fehlende Edge Cases
- Generiere pytest-Code-Beispiele

### 4. Status setzen
- ✅ Success: Overall ≥80% UND geänderte Files ≥80%
- ❌ Failure: Overall <80% ODER geänderte Files <80%

### 5. Kommentar erstellen
```markdown
## 🧪 Test Coverage Report

**Overall:** 82% ✅

### Changed Files:
| File | Coverage | Status |
|------|----------|--------|
| `spotify.py` | 65% | ❌ |
| `routes.py` | 88% | ✅ |

### ❌ Under-tested: `spotify.py` (65%)

**Missing Tests:**
1. OAuth refresh failure
```python
async def test_spotify_oauth_refresh_failure(mocker):
    mocker.patch('httpx.post', side_effect=httpx.HTTPError(...))
    with pytest.raises(SpotifyAuthError):
        await spotify_service.refresh_token("bad_token")
```

2. Empty playlist handling
```python
async def test_empty_playlist():
    playlist = await spotify_service.get_playlist("empty_id")
    assert playlist.tracks == []
```
```

## Config
- Overall Threshold: 80%
- Per-File (changed): 80%
- Per-File (existing): 70% (Warning)
```

**Installation:**
```bash
gh aw compile .github/workflows/agentics/soulspot-test-coverage-guardian.md
git add .github/workflows/agentics/soulspot-test-coverage-guardian.md
git add .github/workflows/soulspot-test-coverage-guardian.yml
git commit -m "feat(ci): Add Test Coverage Guardian"
git push
```

---

### Template 3: SoulSpot Code Quality Reviewer

**Zweck:** Automatisches Code-Review für Pull Requests

**Datei:** `.github/workflows/agentics/soulspot-code-reviewer.md`

```markdown
---
name: SoulSpot Code Quality Reviewer
on:
  pull_request:
    types: [opened, synchronize]
permissions:
  contents: read
  pull-requests: write
safe-outputs:
  create-comment:
    max: 1
tools:
  - bash
  - read-file
  - list-files
engine: claude-3-5-sonnet
timeout-minutes: 15
stop-after: 30 days
---

# SoulSpot Code Quality Reviewer

Du bist Senior Python Backend Engineer.

## Aufgabe
Review Pull Request auf:

### 1. Code Quality
- **Ruff:** `ruff check .`
- **Mypy:** `mypy --strict .`
- **Bandit:** `bandit -r .`

### 2. Documentation
- Google-style Docstrings
- Function signatures dokumentiert
- Complex logic hat Kommentare
- "Future-self" Erklärungen für tricky Code

### 3. Best Practices
- DRY (Don't Repeat Yourself)
- SOLID Principles
- Async/await korrekt verwendet
- Error Handling robust

### 4. Security
- Input Validation
- SQL Injection Prevention (via DatabaseService)
- Keine Secrets im Code
- CSRF Protection (für HTMX Forms)

## Output
```markdown
## 🔍 Code Quality Review

### ✅ Passed Checks
- Ruff: Clean
- Mypy: No type errors
- Bandit: No security issues

### ⚠️ Warnings
1. **Missing Docstring:** `src/soulspot/api/routes.py:45`
   ```python
   async def sync_playlist(playlist_id: str):  # Needs docstring
   ```
   
   **Suggestion:**
   ```python
   async def sync_playlist(playlist_id: str) -> dict:
       """Synchronize Spotify playlist with local database.
       
       Args:
           playlist_id: Spotify playlist ID
           
       Returns:
           dict: Sync statistics (added, updated, errors)
           
       Raises:
           SpotifyAuthError: If authentication fails
       """
   ```

2. **Complex Logic:** `src/soulspot/services/downloader.py:120`
   - Nested loops with error handling
   - Add "Future-self" comment explaining retry logic

### 💡 Suggestions
- Consider extracting `_validate_track_metadata()` helper
- Use `httpx.AsyncClient` context manager for connections
```
```

**Installation:**
```bash
gh aw compile .github/workflows/agentics/soulspot-code-reviewer.md
git add .github/workflows/agentics/soulspot-code-reviewer.md .github/workflows/soulspot-code-reviewer.yml
git commit -m "feat(ci): Add Code Quality Reviewer"
git push
```

---

### Template 4: SoulSpot Documentation Sync

**Zweck:** Halte Dokumentation synchron mit Code-Änderungen

**Datei:** `.github/workflows/agentics/soulspot-doc-sync.md`

```markdown
---
name: SoulSpot Documentation Sync
on:
  push:
    branches: [main]
    paths:
      - 'src/**/*.py'
      - 'alembic/versions/*.py'
permissions:
  contents: write
  pull-requests: write
safe-outputs:
  create-pull-request:
    max: 1
    title-prefix: "[docs]"
tools:
  - bash
  - read-file
  - write-file
  - list-files
engine: gpt-4o  # Schneller für Docs
timeout-minutes: 20
stop-after: 60 days
---

# SoulSpot Documentation Sync

Du bist Technical Writer für SoulSpot.

## Aufgabe
Wenn Code in `src/` oder `alembic/versions/` geändert wird:

### 1. API Docs aktualisieren
- Scanne `src/soulspot/api/` für neue/geänderte Endpoints
- Update `docs/api/*.md`
- Dokumentiere Request/Response Schemas
- Füge cURL-Beispiele hinzu

### 2. Module Docs synchronisieren
- Update `docs/version-3.0/MODULE_SPECIFICATION.md`
- Neue Module ergänzen
- Geänderte Module reflektieren

### 3. Migration Guide erweitern
- Bei Alembic-Änderungen: Update `MIGRATION_FROM_V2.md`
- Breaking Changes dokumentieren
- Upgrade-Schritte beschreiben

## Output
Erstelle PR:
- **Titel:** `[docs] Sync documentation with code changes`
- **Body:**
  ```markdown
  ## Documentation Updates
  
  ### Changes
  - 📝 Updated API docs for new `/api/playlists/sync` endpoint
  - 🔄 Refreshed Module Specification for Spotify Module
  - 🚨 Added migration steps for database schema v3.2.0
  
  ### Files Changed
  - `docs/api/spotify-api.md`
  - `docs/version-3.0/MODULE_SPECIFICATION.md`
  - `docs/version-3.0/MIGRATION_FROM_V2.md`
  ```
```

**Installation:**
```bash
gh aw compile .github/workflows/agentics/soulspot-doc-sync.md
git add .github/workflows/agentics/soulspot-doc-sync.md .github/workflows/soulspot-doc-sync.yml
git commit -m "feat(ci): Add Documentation Sync workflow"
git push
```

---

## Konfiguration & Customization

### Lokale Konfiguration

Workflows können via `.config.md` Dateien angepasst werden:

**Beispiel:** `.github/workflows/agentics/soulspot-architecture-guardian.config.md`

```markdown
# Architecture Guardian Configuration

## Severity Levels
- **CRITICAL:** Architecture violations (Database Module, Settings Service)
- **HIGH:** Structured Errors, Type Hints
- **MEDIUM:** Docstrings, Comments
- **LOW:** Style, Optimizations

## Custom Rules

### Backend-Specific
- Enforce async/await for all DB ops
- Require Pydantic models for API schemas
- Transaction management for multi-step operations

### Frontend-Specific
- HTMX responses must set `HX-Trigger` headers
- All forms need CSRF tokens
- Accessibility: ARIA labels on interactive elements

## Excluded Paths
- `tests/**/*.py` (Test files)
- `alembic/versions/*.py` (Migrations)
- `scripts/*.py` (One-off scripts)

## False Positive Handling
- Direct SQLAlchemy allowed in Database Module itself
- os.getenv allowed in Settings Service itself
```

**Anwenden:**
```bash
# Config-Datei erstellen
touch .github/workflows/agentics/soulspot-architecture-guardian.config.md

# Workflow neu kompilieren
gh aw compile .github/workflows/agentics/soulspot-architecture-guardian.md

# Committen
git add .github/workflows/agentics/soulspot-architecture-guardian.config.md
git commit -m "config(ci): Customize Architecture Guardian rules"
git push
```

### Workflow-Parameter

**Timeouts anpassen:**
```markdown
---
timeout-minutes: 30  # Erhöhen für große Repos
---
```

**Stop-After verlängern:**
```markdown
---
stop-after: 90 days  # Statt 30 Tage
---
```

**Mehr Safe Outputs:**
```markdown
---
safe-outputs:
  create-pull-request:
    max: 3  # Statt 1
  create-comment:
    max: 5
    body-max-length: 20000
---
```

### AI-Modell wechseln

**Für schnellere Tasks (Docs):**
```markdown
---
engine: gpt-4o-mini  # Günstiger, schneller
---
```

**Für komplexe Analyse (Architecture):**
```markdown
---
engine: claude-3-5-sonnet  # Beste Reasoning-Qualität
---
```

**Für Multi-Modal (Design-to-Code):**
```markdown
---
engine: gemini-pro  # Kann Bilder analysieren
---
```

---

## Troubleshooting

### Häufige Probleme

#### Problem 1: Workflow wird nicht getriggert

**Symptome:**
- PR erstellt, aber kein Workflow-Run
- `gh run list` zeigt nichts

**Lösungen:**
```bash
# 1. Check: Ist Workflow committed?
git log --oneline --all | grep "workflow"

# 2. Check: GitHub Actions aktiviert?
# Settings → Actions → General → Enable Actions

# 3. Check: Branch Protection blockiert?
# Settings → Branches → Edit Rule → Uncheck "Require status checks"

# 4. Manuell triggern:
gh aw run soulspot-architecture-guardian

# 5. Workflow-Syntax validieren:
gh aw compile .github/workflows/agentics/soulspot-architecture-guardian.md --check
```

#### Problem 2: API-Key Fehler

**Symptome:**
- Error: "ANTHROPIC_API_KEY not found"
- 401 Unauthorized

**Lösungen:**
```bash
# 1. Secret neu setzen
gh secret set ANTHROPIC_API_KEY --body "sk-ant-..."

# 2. Secret verifizieren
gh secret list
# Sollte ANTHROPIC_API_KEY zeigen

# 3. Repository-Zugriff prüfen
# Settings → Secrets and variables → Actions
# ANTHROPIC_API_KEY sollte sichtbar sein

# 4. API-Key testen (lokal)
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":1024,"messages":[{"role":"user","content":"Hello"}]}'
```

#### Problem 3: Timeout-Fehler

**Symptome:**
- Workflow bricht nach 15 Minuten ab
- "Job was cancelled because it exceeded the maximum execution time"

**Lösungen:**
```markdown
# Erhöhe Timeout in Workflow-Datei:
---
timeout-minutes: 30  # Statt 15
---

# Neu kompilieren:
gh aw compile .github/workflows/agentics/soulspot-architecture-guardian.md

# Oder: Optimiere Workflow
# - Reduziere zu scannende Dateien
# - Nutze schnelleres Modell (gpt-4o-mini)
# - Parallelisiere Tasks
```

#### Problem 4: Zu viele API-Requests

**Symptome:**
- Hohe Kosten
- Rate-Limit Errors

**Lösungen:**
```markdown
# 1. Begrenze Workflow-Runs:
---
on:
  pull_request:
    types: [opened]  # Nur bei PR-Erstellung, nicht bei jedem Push
---

# 2. Nutze Caching:
---
tools:
  - bash
  - cache  # Cache Results
---

# 3. Günstigeres Modell:
---
engine: gpt-4o-mini  # Statt claude-3-5-sonnet
---

# 4. Concurrency Limits:
---
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # Cancelt laufende Runs bei neuem Push
---
```

#### Problem 5: Workflow erstellt zu viele PRs/Issues

**Symptome:**
- Spam-Issues
- Ungewollte PRs

**Lösungen:**
```markdown
# Strikte Safe Outputs:
---
safe-outputs:
  create-pull-request:
    max: 1  # Maximal 1 PR pro Run
  create-issue:
    max: 0  # Keine Issues erlauben
---

# Workflow temporär deaktivieren:
gh workflow disable soulspot-architecture-guardian.yml

# Workflow löschen:
rm .github/workflows/soulspot-architecture-guardian.yml
git commit -m "chore(ci): Remove malfunctioning workflow"
git push
```

### Debug-Techniken

**1. Workflow-Logs anzeigen:**
```bash
# Letzten Run anzeigen
gh run list --workflow=soulspot-architecture-guardian.yml --limit 1
gh run view <run-id> --log

# Fehlgeschlagene Runs
gh run list --workflow=soulspot-architecture-guardian.yml --status=failure
gh run view <run-id> --log
```

**2. Lokal testen (simuliert):**
```bash
# Workflow-Markdown lokal lesen
cat .github/workflows/agentics/soulspot-architecture-guardian.md

# Manuell ausführen (Pseudo-Code)
# - API-Key exportieren: export ANTHROPIC_API_KEY="..."
# - Workflow-Logic in Script umwandeln
# - Lokal ausführen und debuggen
```

**3. Kompilierungs-Fehler prüfen:**
```bash
# Workflow kompilieren mit Validierung
gh aw compile .github/workflows/agentics/soulspot-architecture-guardian.md --check

# Output zeigt Syntax-Fehler oder Warnungen
```

---

## Monitoring & Maintenance

### Regelmäßige Checks

**Wöchentlich:**
```bash
# 1. Workflow-Runs checken
gh run list --workflow=soulspot-architecture-guardian.yml --limit 20

# 2. Fehlgeschlagene Runs untersuchen
gh run list --status=failure --limit 10
gh run view <run-id> --log

# 3. Erstellte Issues/PRs reviewen
gh issue list --label="ai-generated"
gh pr list --label="ai-generated"

# 4. API-Kosten prüfen (bei externen Providern)
# → Anthropic Console: https://console.anthropic.com/
# → OpenAI Dashboard: https://platform.openai.com/usage
```

**Monatlich:**
```bash
# 1. Workflow-Erfolgsrate berechnen
total=$(gh run list --workflow=soulspot-architecture-guardian.yml --limit 100 --json status | jq '. | length')
success=$(gh run list --workflow=soulspot-architecture-guardian.yml --limit 100 --json status | jq '[.[] | select(.status=="completed")] | length')
echo "Success Rate: $(($success * 100 / $total))%"

# 2. Kosten-Analyse
# - Summe API-Calls
# - Durchschnitt Tokens pro Run
# - Gesamtkosten

# 3. Workflow-Nutzen evaluieren
# - Wie viele Issues wurden gefunden?
# - Wurden sie gefixt?
# - Zeitersparnis vs. Kosten?
```

### Performance-Optimierung

**1. Redundante Workflows deaktivieren:**
```bash
# Wenn zwei Workflows ähnliches tun:
gh workflow disable redundant-workflow.yml
```

**2. Trigger optimieren:**
```markdown
# Vorher: Bei jedem Push
---
on:
  pull_request:
    types: [opened, synchronize, reopened, edited]
---

# Nachher: Nur bei Öffnung
---
on:
  pull_request:
    types: [opened]
---
```

**3. Schnelleres Modell für einfache Tasks:**
```markdown
# Statt claude-3-5-sonnet ($$$)
---
engine: gpt-4o-mini  # ($$)
---
```

### Workflow-Lifecycle

**1. Experimentieren (Woche 1-2):**
- Read-Only Workflows (Repo Ask, Team Status)
- Intensive Überwachung
- Frequent adjustments

**2. Stabilisieren (Woche 3-4):**
- Write Workflows (Code Reviewer, Doc Sync)
- Tuning von Prompts und Configs
- Etablieren von Best Practices

**3. Produktiv nutzen (Woche 5+):**
- Workflows laufen stabil
- Regelmäßige Reviews reduzieren
- Fokus auf Nutzen-Maximierung

**4. Wartung (Ongoing):**
- Monatliche Performance-Reviews
- Kosten-Optimierung
- Workflow-Updates bei Architektur-Änderungen

### Deaktivierung & Cleanup

**Temporär deaktivieren:**
```bash
gh workflow disable soulspot-architecture-guardian.yml
```

**Reaktivieren:**
```bash
gh workflow enable soulspot-architecture-guardian.yml
```

**Permanent löschen:**
```bash
rm .github/workflows/soulspot-architecture-guardian.yml
rm .github/workflows/agentics/soulspot-architecture-guardian.md
git commit -m "chore(ci): Remove Architecture Guardian workflow"
git push
```

---

## Nächste Schritte

### Für Einsteiger

1. ✅ Installiere `gh-aw` CLI
2. ✅ Füge **Issue Triage** hinzu (Read-Only, sicher)
3. ✅ Teste mit einem Test-Issue
4. ✅ Wenn erfolgreich: Füge **Architecture Guardian** hinzu

### Für Fortgeschrittene

1. ✅ Implementiere alle empfohlenen Workflows (Phase 1-2)
2. ✅ Customization via `.config.md` Dateien
3. ✅ Monitoring-Dashboard aufsetzen
4. ✅ Kosten-Tracking implementieren
5. ✅ Team-Training für Workflow-Nutzung

### Für Experten

1. ✅ Eigene Custom Workflows entwickeln
2. ✅ Multi-Repo Workflow-Sharing
3. ✅ Workflow-as-Code Best Practices etablieren
4. ✅ Beitragen zur GitHub Next Agentics Sammlung

---

**Dokument-Version:** 1.0  
**Letzte Aktualisierung:** 2025-11-22  
**Autor:** AI Documentation Agent  
**Verwandte Docs:** [AI_AGENT_WORKFLOWS.md](./AI_AGENT_WORKFLOWS.md)
