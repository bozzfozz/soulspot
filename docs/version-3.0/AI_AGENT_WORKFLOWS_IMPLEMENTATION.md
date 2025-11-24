# AI Agent Workflows - GitHub-Native Implementierung für SoulSpot Bridge

## Inhaltsverzeichnis

1. [Quick Start](#quick-start)
2. [Setup über GitHub Web-UI](#setup-über-github-web-ui)
3. [Empfohlene Workflows für SoulSpot](#empfohlene-workflows-für-soulspot)
4. [Workflow-Templates](#workflow-templates)
5. [Konfiguration & Customization](#konfiguration--customization)
6. [Troubleshooting](#troubleshooting)
7. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Quick Start

### 5-Minuten-Setup für SoulSpot Bridge (Nur Browser)

**Schritt 1: GitHub Copilot aktivieren**
1. Gehe zu [github.com/settings/copilot](https://github.com/settings/copilot)
2. Aktiviere GitHub Copilot (falls noch nicht aktiv)
3. Wähle Individual ($10/Monat) oder Business Plan

**Schritt 2: Ersten Workflow erstellen**
1. Öffne dein SoulSpot Bridge Repository auf github.com
2. Klicke auf "Actions" Tab
3. Klicke "New workflow"
4. Wähle "set up a workflow yourself"
5. Kopiere Template (siehe unten) in den Editor
6. Commit im Browser

**Schritt 3: Workflow testen**
1. Erstelle einen Test-PR (oder öffne bestehenden PR)
2. Workflow wird automatisch ausgeführt
3. Siehe Ergebnisse im "Actions" Tab
4. GitHub Copilot kommentiert automatisch

**Fertig!** Keine lokalen Tools oder IDE nötig.

---

## Setup über GitHub Web-UI

### Voraussetzungen

**Account-Anforderungen:**
- GitHub Account mit Repo-Zugriff
- GitHub Copilot Subscription ($10-20/Monat)
- Repository mit Actions aktiviert

**GitHub Features aktivieren:**

1. **Actions aktivieren:**
   ```
   Repository → Settings → Actions → General
   → ✅ "Allow all actions and reusable workflows"
   → ✅ "Allow GitHub Actions to create and approve pull requests"
   ```

2. **Dependabot aktivieren (Optional):**
   ```
   Repository → Settings → Code security → Dependabot
   → ✅ "Dependabot alerts"
   → ✅ "Dependabot security updates"
   → ✅ "Dependabot version updates"
   ```

3. **Branch Protection (Empfohlen):**
   ```
   Repository → Settings → Branches → Add rule
   → Branch name pattern: main
   → ✅ "Require pull request reviews before merging"
   → ✅ "Require status checks to pass before merging"
   ```

### GitHub Copilot für Code-Reviews (Browser)

**Option 1: GitHub Copilot in Pull Requests**

**Zugriff:**
- Öffne einen Pull Request auf github.com
- GitHub Copilot ist automatisch verfügbar (mit Subscription)
- Nutze Slash-Commands direkt in PR-Comments

**Verfügbare Commands:**
```
/review     - Automatisches Code-Review des gesamten PR
/explain    - Erklärt spezifische Code-Änderungen
/fix        - Schlägt Korrekturen für Probleme vor
/tests      - Schlägt Tests für neuen Code vor
```

**Verwendung:**
1. Öffne Pull Request auf github.com
2. Gehe zu "Files changed" Tab
3. Klicke auf Zeile, die du reviewen möchtest
4. Klicke "Add comment"
5. Schreibe `/review` oder `/explain`
6. GitHub Copilot antwortet automatisch

**Option 2: GitHub Copilot in Issues**

1. Öffne ein Issue auf github.com
2. Schreibe einen Kommentar
3. Erwähne `@copilot` mit deiner Frage
4. Beispiel: `@copilot Welche Architektur-Patterns sollten wir für das Database Module nutzen?`
5. Copilot antwortet direkt im Issue

### GitHub Dependabot (Automatische Dependencies)

**Aktivierung über Web-UI:**

1. Gehe zu Repository Settings
2. Klicke "Code security and analysis"
3. Aktiviere "Dependabot alerts"
4. Aktiviere "Dependabot security updates"
5. Klicke "Enable" für "Dependabot version updates"

**Konfiguration erstellen:**

1. Klicke "Add file" → "Create new file"
2. Dateiname: `.github/dependabot.yml`
3. Füge Konfiguration ein:

```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    
  # Docker
  - package-ecosystem: "docker"
    directory: "/docker"
    schedule:
      interval: "weekly"
      
  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

4. Commit direkt im Browser

**Ergebnis:**
- Dependabot erstellt automatisch PRs für Updates
- Jede Woche neue PRs für veraltete Dependencies
- Automatic Security Updates bei Vulnerabilities

### Prioritäts-Matrix

| Workflow | Priorität | Setup-Zeit | Nutzen | Risiko |
|----------|-----------|------------|--------|--------|
| **GitHub Copilot in PRs** | 🔴 Hoch | 5 min | Sofortiges Code-Review | Niedrig |
| **Dependabot** | 🔴 Hoch | 5 min | Automatische Security-Updates | Niedrig |
| **CI Linting & Tests** | 🔴 Hoch | 15 min | Verhindert Fehler | Niedrig |
| **Test Coverage Monitor** | 🟡 Mittel | 20 min | Coverage-Tracking | Niedrig |
| **Documentation Sync** | 🟡 Mittel | 25 min | Docs aktuell halten | Mittel |
| **Auto-Label Issues** | 🟢 Niedrig | 10 min | Organisation | Niedrig |

### Empfohlene Reihenfolge

**Phase 1: Basics (Tag 1)**
1. ✅ GitHub Copilot aktivieren (Browser-basiertes Review)
2. ✅ Dependabot konfigurieren (Automatische Updates)

**Phase 2: Quality Automation (Woche 1)**
3. ✅ CI Linting & Tests (GitHub Actions)
4. ✅ Test Coverage Monitor (Actions + Badge)

**Phase 3: Erweiterte Automatisierung (Woche 2+)**
5. ✅ Documentation Sync (Bei Code-Änderungen)
6. ✅ Issue Auto-Labeling (Triage-Automation)

---

## Workflow-Templates

### Template 1: CI Quality Checks (Linting & Tests)

**Zweck:** Automatisches Linting und Testing bei jedem Push/PR

**Erstellen über GitHub Web-UI:**
1. Gehe zu deinem Repository auf github.com
2. Klicke "Add file" → "Create new file"
3. Dateiname: `.github/workflows/ci-quality.yml`
4. Füge folgenden Inhalt ein:

```yaml
name: CI Quality Checks

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

permissions:
  contents: read
  pull-requests: write

jobs:
  quality-check:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install ruff mypy bandit
          
      - name: Run Ruff Linter
        run: ruff check . --output-format=github
        continue-on-error: false
        
      - name: Run MyPy Type Checker
        run: mypy . --config-file=mypy.ini
        continue-on-error: false
        
      - name: Run Bandit Security Scanner
        run: bandit -r src/ -ll
        continue-on-error: false
        
      - name: Run Tests
        run: make test
        
      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '✅ Quality checks passed!'
            })
```

5. Commit: "Add CI quality workflow"
6. Workflow ist sofort aktiv!

---

### Template 2: Test Coverage Monitor

**Zweck:** Coverage-Reporting und Badge-Generierung

**Datei:** `.github/workflows/coverage.yml`

```yaml
name: Test Coverage

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

permissions:
  contents: read
  pull-requests: write

jobs:
  coverage:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
          
      - name: Run tests with coverage
        run: |
          pytest --cov=src --cov-report=html --cov-report=term --cov-report=json
          
      - name: Get coverage percentage
        id: coverage
        run: |
          COVERAGE=$(python -c "import json; print(json.load(open('coverage.json'))['totals']['percent_covered_display'])")
          echo "percentage=$COVERAGE" >> $GITHUB_OUTPUT
          
      - name: Comment coverage on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const coverage = '${{ steps.coverage.outputs.percentage }}';
            const emoji = coverage >= 80 ? '✅' : '❌';
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `${emoji} Test Coverage: ${coverage}%\n\nTarget: 80%`
            })
            
      - name: Upload coverage to artifacts
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/
```

**Erstellen:**
1. "Add file" → "Create new file"
2. Dateiname: `.github/workflows/coverage.yml`
3. Code einfügen → Commit

---

### Template 3: Documentation Sync

**Zweck:** Automatische Docs-Updates bei Code-Änderungen

**Datei:** `.github/workflows/docs-sync.yml`

```yaml
name: Documentation Sync

on:
  push:
    branches: [ main ]
    paths:
      - 'src/**/*.py'
      - 'alembic/versions/*.py'

permissions:
  contents: write
  pull-requests: write

jobs:
  sync-docs:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Check for doc updates needed
        id: check
        run: |
          # Prüfe ob API docs aktualisiert werden müssen
          if git diff --name-only HEAD~1 | grep -q "src/soulspot/api"; then
            echo "needs_update=true" >> $GITHUB_OUTPUT
          fi
          
      - name: Create issue for doc update
        if: steps.check.outputs.needs_update == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '📝 Documentation Update Required',
              body: 'API code was changed. Please update docs in `docs/api/`',
              labels: ['documentation', 'automation']
            })
```

**Hinweis:** Erstellt automatisch ein Issue wenn API-Code geändert wird.

---

### Template 4: Auto-Label Issues

**Zweck:** Automatisches Labeling von Issues basierend auf Inhalt

**Datei:** `.github/workflows/auto-label.yml`

```yaml
name: Auto-Label Issues

on:
  issues:
    types: [opened, edited]

permissions:
  issues: write

jobs:
  label:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            const issue = context.payload.issue;
            const title = issue.title.toLowerCase();
            const body = issue.body.toLowerCase();
            const labels = [];
            
            // Bug detection
            if (title.includes('bug') || title.includes('error') || title.includes('fix')) {
              labels.push('bug');
            }
            
            // Feature request
            if (title.includes('feature') || title.includes('enhancement')) {
              labels.push('enhancement');
            }
            
            // Documentation
            if (title.includes('doc') || title.includes('documentation')) {
              labels.push('documentation');
            }
            
            // Module-specific
            if (body.includes('spotify') || title.includes('spotify')) {
              labels.push('module:spotify');
            }
            if (body.includes('soulseek') || title.includes('soulseek')) {
              labels.push('module:soulseek');
            }
            if (body.includes('database') || title.includes('database')) {
              labels.push('module:database');
            }
            
            // Apply labels
            if (labels.length > 0) {
              await github.rest.issues.addLabels({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: issue.number,
                labels: labels
              });
            }
```

**Erstellen:**
1. GitHub UI: "Add file" → `.github/workflows/auto-label.yml`
2. Code einfügen → Commit
3. Labels werden automatisch bei neuen Issues vergeben!
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

Du bist Technical Writer für SoulSpot Bridge.

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
