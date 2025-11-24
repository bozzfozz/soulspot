# AI Agent Workflows für SoulSpot Bridge v3.0

## Inhaltsverzeichnis

1. [Übersicht](#übersicht)
2. [Was sind AI Agentic Workflows?](#was-sind-ai-agentic-workflows)
3. [GitHub-Native AI Workflows](#github-native-ai-workflows)
4. [Workflow-Typen und Kategorien](#workflow-typen-und-kategorien)
5. [Architektur und Funktionsweise](#architektur-und-funktionsweise)
6. [Integration in SoulSpot Bridge](#integration-in-soulspot-bridge)
7. [Workflow-Implementierung über GitHub](#workflow-implementierung-über-github)
8. [Sicherheit und Best Practices](#sicherheit-und-best-practices)
9. [Praktische Beispiele](#praktische-beispiele)
10. [Ressourcen und Weiterführende Links](#ressourcen-und-weiterführende-links)

---

## Übersicht

**AI Agent Workflows** repräsentieren einen Paradigmenwechsel in der Entwicklungsautomatisierung: Statt Code zu schreiben, beschreiben Teams in natürlicher Sprache, was passieren soll. KI-Agenten interpretieren diese Anweisungen, treffen Entscheidungen und führen Aktionen aus.

### Wichtigste Erkenntnisse (TL;DR)

- **Was:** GitHub Actions Workflows mit integrierten AI-Agenten für automatisierte Entwicklungsaufgaben
- **Warum:** Zugänglicher, wartbarer, auditable Automatisierung direkt in GitHub
- **Wie:** YAML Workflow-Definitionen → GitHub Actions → AI-Agenten-Ausführung (direkt im Browser nutzbar)
- **Status:** Basiert auf GitHub Copilot und GitHub Actions (produktionsreif)
- **Nutzen für SoulSpot:** Automatisierte Code-Reviews, Dependency-Updates, Dokumentationspflege, QA-Tests

> ✅ **HINWEIS:** Diese Workflows nutzen GitHub-native Features (Actions, Copilot) und können direkt über die GitHub-Weboberfläche verwendet werden - ohne lokale Tools oder IDE-Setup.

---

## Was sind AI Agentic Workflows?

### Grundkonzepte

**Agentic Programming** ersetzt imperative Skripte durch deklarative, natürlichsprachige Beschreibungen:

```markdown
**Klassisch (GitHub Actions YAML):**
- Explizite Schritte: checkout → setup → install → test → deploy
- Fehlerbehandlung muss vorhergesehen werden
- Wartungsintensiv bei Änderungen

**Agentic (Natural Language):**
- Zielbeschreibung: "Ensure all tests pass and coverage is >80%"
- KI plant die Schritte
- Adaptiert an Änderungen im Repository
```

### Kernprinzipien

1. **Thought–Action–Observation Loop**
   - **Thought**: Agent analysiert Kontext und plant
   - **Action**: Führt Werkzeuge aus (Git, Tests, Analysen)
   - **Observation**: Bewertet Ergebnisse
   - **Repeat**: Iteriert bis Ziel erreicht ist

2. **Autonomie-Level**
   - **Simple**: KI generiert Output (Kommentare, Docs)
   - **Router**: KI entscheidet, welche Jobs ausgeführt werden
   - **Autonomous**: KI erstellt neue Tasks und Tools

3. **Actions-First Architecture**
   - Baut auf GitHub Actions auf
   - Nutzt bestehende Permissions, Logs, Auditing
   - Versionskontrolliert und nachvollziehbar

---

## GitHub-Native AI Workflows

### Projekt-Übersicht

**GitHub-Native AI Workflows** nutzen die integrierten Features von GitHub (Actions, Copilot, Issues, Pull Requests) um KI-gestützte Automatisierung direkt im Browser bereitzustellen - ohne lokale Tools oder IDE-Setup.

**Kern-Features:**
- GitHub Actions: Automatisierte Workflows mit YAML-Definition
- GitHub Copilot: KI-Integration für Code-Reviews und Vorschläge
- GitHub Issues/PRs: Automatische Kommentare und Status-Updates
- Web-basiert: Alles über die GitHub-Weboberfläche nutzbar

### Verfügbare Workflow-Kategorien

Folgende Workflow-Typen können direkt in GitHub implementiert werden:

#### Triage & Analyse-Workflows

1. **🏷️ Issue Triage (GitHub Actions + Labels)**
   - Automatisches Triagieren von Issues und Pull Requests
   - Labeling, Prioritäten, Kategorisierung
   - Direkt über GitHub Actions konfigurierbar

2. **🏥 CI Doctor (GitHub Actions)**
   - Überwacht CI-Workflows
   - Analysiert Fehler automatisch
   - Erstellt Diagnose-Reports als Comments

3. **🔍 Code Review Assistant (GitHub Copilot)**
   - Intelligenter Repository-Assistent
   - Beantwortet Fragen zum Code
   - Analysiert Architektur direkt in Pull Requests

4. **🔍 Daily Accessibility Review (GitHub Actions)**
   - Prüft Barrierefreiheit
   - Führt automatisierte Tests aus
   - Reports als GitHub Issues

#### Research, Status & Planning-Workflows

6. **📚 Weekly Research (GitHub Actions + Issues)**
   - Sammelt Research-Updates
   - Verfolgt Industrie-Trends
   - Erstellt wöchentliche Issue-Reports

7. **👥 Daily Team Status (GitHub Actions)**
   - Analysiert Repository-Aktivität
   - Erstellt Status-Reports als Issues

8. **📋 Daily Plan (GitHub Actions)**
   - Aktualisiert Planungs-Issues
   - Team-Koordination via Issue-Comments

#### Coding & Development-Workflows

9. **📦 Dependency Updater (GitHub Dependabot + Actions)**
    - Aktualisiert Dependencies automatisch
    - Erstellt Pull Requests
    - GitHub-native via Dependabot

10. **📖 Documentation Update (GitHub Actions)**
    - Automatische Dokumentationspflege
    - Triggered bei Code-Änderungen

11. **🏥 PR Review Assistant (GitHub Copilot)**
    - Analysiert Pull Request Code
    - Implementiert Review-Vorschläge
    - Direkt in GitHub PR-Ansicht nutzbar

12. **🔎 Daily QA Tests (GitHub Actions)**
    - Führt explorative QA-Tasks aus
    - Reports als PR-Comments

13. **🧪 Test Coverage Monitor (GitHub Actions)**
    - Überwacht Test-Coverage
    - Erstellt Coverage-Reports
    - Badges in README

14. **⚡ Performance Monitor (GitHub Actions)**
    - Analysiert Performance-Metriken
    - Benchmarking in CI/CD
    - Regression-Detection

---

## Workflow-Typen und Kategorien

### Nach Funktion

| Kategorie | Workflows | Primärer Zweck |
|-----------|-----------|----------------|
| **Triage & Analyse** | Issue Triage, CI Doctor, Repo Ask, Accessibility Review, Q Optimizer | Automatische Analyse und Diagnose |
| **Planning & Status** | Weekly Research, Daily Team Status, Daily Plan, Plan Command | Strategische Planung und Reporting |
| **Development** | Daily Progress, Dependency Updater, Documentation Update, PR Fix | Code-Generierung und Wartung |
| **Quality Assurance** | Daily QA, Test Coverage Improver, Performance Improver | Qualitätssicherung und Optimierung |

### Nach Autonomie-Grad

**Level 1: Assistenz (Read-Only)**
- Repo Ask
- Weekly Research
- Daily Team Status
- **Risiko:** Niedrig (keine Änderungen)

**Level 2: Vorschläge (Write mit Review)**
- Issue Triage (Labels, Kommentare)
- Daily Plan (Issue-Updates)
- Documentation Update (PR-Erstellung)
- **Risiko:** Mittel (Änderungen erfordern Review)

**Level 3: Autonomous (Code-Änderungen)**
- Daily Progress (Feature-Entwicklung)
- PR Fix (Bug-Fixes)
- Test Coverage Improver (Test-Generierung)
- Performance Improver (Code-Optimierung)
- **Risiko:** Hoch (direkter Code-Impact)

> ⚠️ **Sicherheitshinweis:** Workflows, die Code schreiben, sollten mit Vorsicht installiert und nur experimentell genutzt werden. Obwohl Tasks in GitHub Actions ausgeführt werden und keinen Zugriff auf Secrets haben, operieren sie in einer Umgebung mit ausgehenden Netzwerk-Requests. Untrusted Inputs (Issue-Beschreibungen, Kommentare, Code) könnten potenziell ausgenutzt werden. Pull Requests und Outputs müssen sehr sorgfältig geprüft werden, bevor sie gemerged werden.

---

## Architektur und Funktionsweise

### Workflow-Lifecycle

```
1. Definition (Markdown)
   ↓
2. Kompilierung (gh-aw CLI)
   ↓
3. GitHub Actions (YAML)
   ↓
4. Agent-Ausführung (Container)
   ↓
5. Tool-Nutzung (Git, APIs, Analysen)
   ↓
6. Output (Issues, PRs, Kommentare)
```

### Komponenten-Architektur

```
┌─────────────────────────────────────────────────┐
│           Workflow Definition (.md)             │
│  - Natural Language Beschreibung                │
│  - Trigger-Konfiguration                        │
│  - Permissions & Safe Outputs                   │
│  - Tool-Zugriff                                 │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│          gh-aw CLI (Kompilierung)               │
│  - Parst Markdown                               │
│  - Generiert GitHub Actions YAML                │
│  - Validiert Konfiguration                      │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│        GitHub Actions Workflow (.yml)           │
│  - Standard GitHub Actions                      │
│  - Event-Trigger (push, issues, schedule)       │
│  - Job-Definition                               │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│         AI Agent (Container-Ausführung)         │
│  - LLM (Claude, GPT-4, etc.)                    │
│  - Tool-Zugriff (git, curl, filesystem)         │
│  - Repository-Kontext                           │
│  - Thought-Action-Observation Loop              │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           GitHub Repository Outputs             │
│  - Issues (Berichte, Tasks)                     │
│  - Pull Requests (Code-Änderungen)              │
│  - Kommentare (Feedback, Analysen)              │
│  - Labels (Kategorisierung)                     │
└─────────────────────────────────────────────────┘
```

### Agent Reasoning Pattern

**Thought–Action–Observation (TAO) Loop:**

```python
while not goal_achieved():
    # THOUGHT: Analyse aktuellen Zustand
    context = analyze_repository_state()
    plan = create_action_plan(context, goal)
    
    # ACTION: Führe Werkzeuge aus
    result = execute_tool(plan.next_action)
    
    # OBSERVATION: Bewerte Ergebnis
    observation = evaluate_result(result)
    
    # ADAPTATION: Passe Plan an
    if observation.success:
        update_progress()
    else:
        adjust_strategy(observation.errors)
```

### Sicherheitsmechanismen

1. **Permissions Control**
   ```yaml
   permissions:
     contents: read       # Nur Lesen standardmäßig
     issues: write        # Explizit für Issue-Änderungen
     pull-requests: write # Explizit für PR-Erstellung
   ```

2. **Safe Outputs**
   ```yaml
   safe-outputs:
     create-pull-request:
       max: 5             # Maximal 5 PRs pro Run
       title-prefix: "[AI]" # Markierung
   ```

3. **Timeouts & Limits**
   ```yaml
   timeout-minutes: 30    # Max. Laufzeit
   stop-after: 30 days    # Auto-Deaktivierung
   ```

4. **Sandboxing**
   - Ausführung in isolierten GitHub Actions Containern
   - Kein Zugriff auf Repository-Secrets
   - Kontrollierter Netzwerk-Zugriff

---

## Integration in SoulSpot Bridge

### Anwendungsfälle für SoulSpot Bridge v3.0

#### 1. **Code Quality & Review Automation**

**Workflow: "SoulSpot Code Guardian"**
```markdown
---
on: pull_request
permissions:
  contents: read
  pull-requests: write
safe-outputs:
  create-comment:
    max: 1
---

# SoulSpot Code Guardian

Du bist ein Senior Python Backend Engineer, spezialisiert auf FastAPI und SQLAlchemy.

## Aufgabe
Überprüfe Pull Requests auf:
1. **Architektur-Compliance:**
   - Verwendet Database Module (kein direktes SQLAlchemy)
   - Nutzt Settings Service (keine .env imports)
   - Strukturierte Errors (code, message, context, resolution)
   
2. **Code Quality:**
   - Passes ruff, mypy strict mode
   - >80% Test Coverage
   - Google-style Docstrings
   
3. **Security:**
   - Bandit clean
   - Keine Secrets im Code
   - Input-Validierung
   
Erstelle einen Kommentar mit detaillierten Findings und konkreten Verbesserungsvorschlägen.
```

**Installation:**
```bash
gh aw add soulspot/code-guardian --pr
```

#### 2. **Dependency Management**

**Workflow: "SoulSpot Dependency Sentinel"**
```markdown
---
on:
  schedule:
    - cron: '0 9 * * 1'  # Montags 9 Uhr
permissions:
  contents: write
  pull-requests: write
safe-outputs:
  create-pull-request:
    max: 3
---

# SoulSpot Dependency Sentinel

## Aufgabe
1. Prüfe `poetry.lock` auf veraltete Dependencies
2. Aktualisiere nur PATCH- und MINOR-Versionen (kein Breaking)
3. Führe Tests aus (`make test`)
4. Erstelle PRs für jede erfolgreiche Update-Kategorie:
   - `[deps] Update backend dependencies`
   - `[deps] Update dev dependencies`
   - `[deps] Update frontend dependencies (npm)`

## Bedingungen
- Nur wenn Tests grün sind
- Changelog-Eintrag in PR-Beschreibung
- Link zu Security-Advisories bei relevanten Updates
```

#### 3. **Documentation Sync**

**Workflow: "SoulSpot Doc Doctor"**
```markdown
---
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
---

# SoulSpot Doc Doctor

## Aufgabe
Wenn Code in `src/` oder `alembic/versions/` geändert wird:

1. **API Docs aktualisieren:**
   - `docs/api/*.md` auf Basis der FastAPI-Routen
   - Neue Endpoints dokumentieren
   - Deprecated Endpoints markieren

2. **Module Docs synchronisieren:**
   - `docs/version-3.0/MODULE_SPECIFICATION.md`
   - Neue Module ergänzen
   - Änderungen in bestehenden Modulen reflektieren

3. **Migration Guide aktualisieren:**
   - Bei Alembic-Änderungen `docs/version-3.0/MIGRATION_FROM_V2.md` erweitern
   - Breaking Changes dokumentieren

Erstelle eine PR mit dem Titel: `[docs] Sync documentation with code changes`
```

#### 4. **Test Coverage Watcher**

**Workflow: "SoulSpot Test Guardian"**
```markdown
---
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
---

# SoulSpot Test Guardian

## Aufgabe
Für jeden PR:

1. **Coverage analysieren:**
   - Führe `make test-cov` aus
   - Parse HTML-Report aus `htmlcov/`
   - Identifiziere unter-getestete Module (<80%)

2. **Fehlende Tests identifizieren:**
   - Neue Funktionen ohne Tests
   - Geänderte Funktionen mit verringerter Coverage
   - Edge Cases ohne Tests

3. **Kommentar erstellen:**
   - Coverage-Status Badge
   - Liste unter-getesteter Dateien
   - Konkrete Test-Vorschläge
   - Markiere als Blocker, wenn <80% Coverage

## Beispiel-Kommentar-Format
```
🧪 **Test Coverage Report**

Overall: 78% ❌ (Target: 80%)

### Under-tested Files:
- `src/soulspot/services/spotify.py`: 65% (-15%)
  - Missing: Error handling for OAuth failures
  - Missing: Edge case for empty playlist

### Suggested Tests:
```python
async def test_spotify_oauth_failure_handling():
    # Test when Spotify returns 401
    ...
```
```
```

#### 5. **Architecture Compliance Monitor**

**Workflow: "SoulSpot Architecture Guardian"**
```markdown
---
on:
  pull_request:
    types: [opened, synchronize]
permissions:
  contents: read
  pull-requests: write
safe-outputs:
  create-comment:
    max: 1
---

# SoulSpot Architecture Guardian

## Aufgabe
Validiere jeden PR gegen SoulSpot v3.0 Architektur-Richtlinien:

### 1. Database Module Usage
Scanne alle Python-Dateien auf:
- ❌ `from sqlalchemy import ...` (direkter Import)
- ❌ `session.query(...)` (direkter Session-Zugriff)
- ✅ `database_service.get_entity(...)` (korrekt)
- ✅ `from soulspot.database import DatabaseService` (korrekt)

### 2. Settings Service Usage
Scanne auf:
- ❌ `os.getenv(...)` (verboten)
- ❌ `from dotenv import load_dotenv` (verboten)
- ✅ `settings_service.get(...)` (korrekt)

### 3. Error Handling
Prüfe auf:
- ❌ `raise Exception("...")` (generisch)
- ✅ Strukturierte Errors mit `code`, `message`, `context`, `resolution`

### 4. Module Boundaries
Prüfe auf:
- ❌ Cross-Module Imports (z.B. `from spotify import ...` in `soulseek/`)
- ✅ Event-basierte Kommunikation

Erstelle einen Kommentar mit Violations und konkreten Fixes.
```

### Empfohlene Workflows für SoulSpot

| Workflow | Priorität | Nutzen | Risiko |
|----------|-----------|--------|--------|
| **Code Guardian** | 🔴 Hoch | Architecture Compliance, Code Quality | Niedrig (nur Kommentare) |
| **Test Guardian** | 🔴 Hoch | Verhindert Coverage-Rückgang | Niedrig (nur Kommentare) |
| **Doc Doctor** | 🟡 Mittel | Docs immer aktuell | Mittel (PR-Erstellung) |
| **Dependency Sentinel** | 🟡 Mittel | Security & Freshness | Mittel (kann Tests brechen) |
| **Architecture Guardian** | 🔴 Hoch | Verhindert Architektur-Drift | Niedrig (nur Kommentare) |
| **Daily Progress** | 🟢 Niedrig | Feature-Entwicklung | Hoch (autonomer Code) |

---

## Workflow-Implementierung über GitHub

### Schritt-für-Schritt-Anleitung (Ohne lokale Tools)

#### 1. Workflow direkt in GitHub erstellen

**Via GitHub Web-Oberfläche:**
1. Öffne dein Repository auf GitHub.com
2. Navigiere zu "Actions" Tab
3. Klicke "New workflow"
4. Wähle "set up a workflow yourself"
5. Erstelle YAML-Datei direkt im Browser

**Oder via File-Upload:**
1. Navigiere zu `.github/workflows/` in deinem Repo
2. Klicke "Add file" → "Create new file"
3. Benenne die Datei (z.B. `architecture-guardian.yml`)
4. Füge Workflow-YAML ein (siehe Templates unten)
5. Commit direkt im Browser

#### 2. Workflow aus Template hinzufügen

**GitHub Actions Marketplace nutzen:**
```
1. Gehe zu github.com/marketplace/actions
2. Suche nach relevanten Actions (z.B. "code review", "linting")
3. Klicke "Use latest version"
4. GitHub zeigt YAML-Snippet → Kopieren
5. Einfügen in .github/workflows/NAME.yml
6. Commit via Web-UI
```

#### 3. Eigenen Workflow erstellen (Web-basiert)

**a) Workflow-Datei über GitHub UI erstellen:**

1. Gehe zu deinem Repository auf github.com
2. Klicke auf "Add file" → "Create new file"
3. Dateiname: `.github/workflows/soulspot-code-guardian.yml`
4. GitHub erkennt automatisch, dass es ein Workflow ist

**b) Workflow-YAML definieren:**

```yaml
name: SoulSpot Code Guardian

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install ruff mypy bandit
          
      - name: Run linters
        run: |
          ruff check . --output-format=github
          mypy . --strict
          bandit -r . -f json
          
      - name: Comment results
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '🔍 Code Quality Check completed!'
            })
```

**c) Workflow committen:**

1. Scroll zum Ende der Seite
2. Commit-Message: `feat(ci): Add SoulSpot Code Guardian workflow`
3. Wähle "Commit directly to main" oder "Create new branch"
4. Klicke "Commit new file"

**Fertig!** Der Workflow ist jetzt aktiv und wird bei Pull Requests automatisch ausgeführt.

#### 4. GitHub Copilot für Code-Reviews nutzen (Browser)

**Direkt in Pull Requests:**

1. Öffne einen Pull Request auf github.com
2. GitHub Copilot ist automatisch verfügbar (falls aktiviert)
3. Nutze `/` Befehle in PR-Comments:
   - `/review` - Automatisches Code-Review
   - `/explain` - Code-Erklärung
   - `/fix` - Vorschläge zur Fehlerbehebung

**In Issue-Diskussionen:**

1. Öffne ein Issue auf github.com
2. Schreibe einen Kommentar mit `@copilot`
3. Stelle Fragen zum Code oder Architecture
4. Copilot antwortet direkt im Issue

**Code-Vorschläge in PRs:**

1. GitHub Copilot analysiert PR-Code automatisch
2. Klicke auf "Files changed" im PR
3. Copilot zeigt Inline-Vorschläge
4. Klicke "Commit suggestion" um anzuwenden

---

## Sicherheit und Best Practices

### Sicherheits-Checkliste

#### Vor der Installation

- [ ] **Permissions reviewen:** Nur notwendige Permissions vergeben
- [ ] **Safe Outputs konfigurieren:** Limits für PRs/Issues setzen
- [ ] **Timeout festlegen:** Maximal 30 Minuten
- [ ] **Stop-After aktivieren:** Workflow automatisch nach 30 Tagen stoppen
- [ ] **Code-Workflows mit Vorsicht:** Nur experimentell nutzen, dann deaktivieren

#### Während der Nutzung

- [ ] **PRs sorgfältig reviewen:** ALLE AI-generierten PRs manuell prüfen
- [ ] **Issue-Qualität überwachen:** Sinnlose Issues sofort löschen
- [ ] **Logs kontrollieren:** GitHub Actions Logs auf verdächtige Aktivitäten prüfen
- [ ] **Kosten im Blick:** LLM API-Kosten monitoren
- [ ] **Disable bei Problemen:** Workflow sofort deaktivieren bei Fehlfunktionen

#### Nach der Nutzung

- [ ] **Erfolg evaluieren:** Workflow-Nutzen vs. Wartungsaufwand
- [ ] **Archivieren oder Löschen:** Ungenutzte Workflows entfernen
- [ ] **Lessons Learned dokumentieren:** Was funktioniert, was nicht

### Best Practices

#### 1. Start Small

```markdown
✅ RICHTIG:
- Beginne mit Read-Only Workflows (Repo Ask, Team Status)
- Teste intensiv mit einzelnen PRs
- Erweitere schrittweise zu Write-Workflows

❌ FALSCH:
- Sofort Daily Progress (autonomous code) aktivieren
- Auf Production-Repo ohne Tests installieren
- Mehrere Workflows gleichzeitig hinzufügen
```

#### 2. Clear Instructions

```markdown
✅ RICHTIG:
# SoulSpot Code Guardian

Du bist ein Senior Python Backend Engineer.

## Kontext
SoulSpot nutzt FastAPI, SQLAlchemy, HTMX.

## Aufgabe
Prüfe auf:
1. Database Module Usage (kein direktes SQLAlchemy)
2. Settings Service Usage (kein os.getenv)
3. Type Hints (mypy strict)

## Output
Kommentar mit:
- ✅ Passed Checks
- ❌ Failed Checks + Fixes


❌ FALSCH:
# Code Checker

Check the code for issues.
```

#### 3. Constrain Outputs

```yaml
✅ RICHTIG:
safe-outputs:
  create-pull-request:
    max: 1                    # Nur 1 PR pro Run
    title-prefix: "[AI]"      # Klar markiert
    body-max-length: 5000     # Verhindert Spam
  create-issue:
    max: 2
    labels: ["ai-generated", "needs-review"]

❌ FALSCH:
safe-outputs:
  create-pull-request:
    max: 100  # Unkontrolliert
```

#### 4. Timeout & Limits

```yaml
✅ RICHTIG:
timeout-minutes: 15          # Verhindert Endlos-Loops
stop-after: 30 days          # Auto-Deaktivierung
concurrency:
  group: soulspot-guardian
  cancel-in-progress: true   # Keine Überlappung

❌ FALSCH:
timeout-minutes: 180  # 3 Stunden ist zu lang
# Kein stop-after
```

#### 5. Human-in-the-Loop

```markdown
✅ RICHTIG:
- Alle PRs als DRAFT erstellen
- Kommentare mit "needs-review" Label
- Issues mit Checkliste für menschliche Validierung

❌ FALSCH:
- Direkt in main mergen
- Auto-merge aktivieren
- Issues ohne Review-Hinweis
```

#### 6. Monitoring & Alerting

```bash
# GitHub Actions Monitoring
gh run list --workflow=soulspot-code-guardian.yml --limit 50

# Failures checken
gh run list --workflow=soulspot-code-guardian.yml --status=failure

# Kosten tracken (bei externen LLM APIs)
# Setze Budget-Alerts in OpenAI/Anthropic Dashboard

# Wöchentliches Review
gh issue list --label="ai-generated" --state=all
gh pr list --label="ai-generated" --state=all
```

### Häufige Fehler vermeiden

| Fehler | Warum schlecht | Lösung |
|--------|----------------|--------|
| **Zu vage Instructions** | Agent weiß nicht, was zu tun ist | Konkrete Aufgaben, Beispiele, Kontext |
| **Unbegrenzte Outputs** | Spam-Issues/PRs | `safe-outputs` mit max Limits |
| **Keine Timeouts** | Kosten-Explosion, Hänger | `timeout-minutes: 15` |
| **Production-First** | Ungetestete Workflows auf Live-Repo | Staging-Repo zuerst |
| **Auto-Merge** | Gefährlicher AI-generierter Code | Immer DRAFT PRs + manuelles Review |
| **Fehlende Stop-After** | Vergessene Workflows laufen ewig | `stop-after: 30 days` |
| **Secrets im Workflow** | Security-Risiko | Nutze GitHub Secrets |

---

## Praktische Beispiele

### Beispiel 1: Simple Documentation Updater

**Szenario:** Halte README.md aktuell mit letzten Releases

**Workflow-Definition** (`.github/workflows/agentics/readme-updater.md`):
```markdown
---
name: README Updater
on:
  release:
    types: [published]
permissions:
  contents: write
  pull-requests: write
safe-outputs:
  create-pull-request:
    max: 1
    title-prefix: "[docs]"
tools:
  - read-file
  - write-file
engine: gpt-4o  # Schnell für einfache Tasks
timeout-minutes: 10
stop-after: 60 days
---

# README Updater

## Aufgabe
Wenn ein neues Release veröffentlicht wird:

1. Lese `README.md`
2. Aktualisiere den "Latest Release" Badge:
   ```markdown
   ![Latest Release](https://img.shields.io/github/v/release/bozzfozz/soulspot-bridge)
   ```
3. Füge Changelog-Eintrag im README hinzu unter "## Recent Changes"
4. Erstelle PR mit Titel: `[docs] Update README for release vX.Y.Z`

## Beispiel
Wenn Release `v3.1.0` veröffentlicht wird:
```markdown
## Recent Changes

### v3.1.0 (2025-11-22)
- ✨ New: AI Agent Workflows Documentation
- 🐛 Fix: OAuth token refresh
- 📝 Docs: Updated API examples
```
```

**Kompilieren und committen:**
```bash
gh aw compile .github/workflows/agentics/readme-updater.md
git add .github/workflows/agentics/readme-updater.md .github/workflows/readme-updater.yml
git commit -m "feat(ci): Add README auto-updater workflow"
git push
```

**Erwartetes Ergebnis:**
- Bei jedem Release wird automatisch eine PR erstellt
- PR aktualisiert README mit Release-Info
- Manuelles Review und Merge

---

### Beispiel 2: Advanced Test Coverage Guardian

**Szenario:** Verhindere Coverage-Rückgang und schlage konkrete Tests vor

**Workflow-Definition** (`.github/workflows/agentics/test-coverage-guardian.md`):
```markdown
---
name: Test Coverage Guardian
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
engine: claude-3-5-sonnet  # Beste Reasoning für komplexe Analyse
timeout-minutes: 20
stop-after: 30 days
---

# Test Coverage Guardian

Du bist ein Senior QA Engineer für Python/FastAPI-Projekte.

## Kontext
- **Projekt:** SoulSpot Bridge v3.0
- **Framework:** FastAPI + SQLAlchemy (async)
- **Test-Framework:** pytest + pytest-asyncio
- **Coverage-Ziel:** >80%

## Aufgabe
Für jeden Pull Request:

### 1. Coverage messen
```bash
# In GitHub Actions Container
poetry install --with dev
make test-cov  # Runs: pytest --cov=src/soulspot --cov-report=html --cov-report=term
```

### 2. Coverage analysieren
- Parse `htmlcov/index.html` für Overall Coverage
- Identifiziere Files mit <80% Coverage
- Finde neue/geänderte Dateien im PR (via `git diff`)
- Cross-reference: Welche geänderten Dateien haben niedrige Coverage?

### 3. Konkrete Test-Vorschläge generieren
Für jede unter-getestete Datei:
- Analysiere den Code
- Identifiziere ungetestete Funktionen
- Identifiziere fehlende Edge Cases
- Generiere konkrete pytest-Code-Beispiele

### 4. Status setzen
```yaml
Status Check: "test-coverage"
- ✅ Success: Overall ≥80% UND alle geänderten Files ≥80%
- ❌ Failure: Overall <80% ODER geänderte Files <80%
- ⚠️ Warning: Overall ≥80% ABER einzelne Files <70%
```

### 5. Kommentar erstellen
Format:
```markdown
## 🧪 Test Coverage Report

**Overall Coverage:** 82% ✅

### Changed Files Coverage:
| File | Coverage | Status | Change |
|------|----------|--------|--------|
| `src/soulspot/services/spotify.py` | 65% | ❌ | -15% |
| `src/soulspot/api/routes.py` | 88% | ✅ | +3% |

### ❌ Under-tested: `spotify.py` (65%)

**Missing Tests:**
1. **Error Handling:** OAuth token refresh failure
   ```python
   async def test_spotify_oauth_refresh_failure(mocker):
       mocker.patch('httpx.AsyncClient.post', side_effect=httpx.HTTPStatusError(...))
       with pytest.raises(SpotifyAuthError):
           await spotify_service.refresh_token("invalid_token")
   ```

2. **Edge Case:** Empty playlist handling
   ```python
   async def test_spotify_empty_playlist():
       playlist = await spotify_service.get_playlist("empty_playlist_id")
       assert playlist.tracks == []
       assert playlist.total == 0
   ```

### 💡 Recommendations:
- Add tests for error scenarios in `spotify.py`
- Increase coverage to 80% before merging
```

## Fehlerbehandlung
Wenn Coverage-Messung fehlschlägt:
- Kommentiere mit Error und Anleitung zur lokalen Ausführung
- Setze Status auf "neutral" (nicht failure)
```

**Lokale Konfiguration** (`.github/workflows/agentics/test-coverage-guardian.config.md`):
```markdown
# Test Coverage Guardian Configuration

## Coverage Thresholds
- Overall: 80%
- Per-File (changed): 80%
- Per-File (existing): 70% (Warnung)

## Excluded Patterns
- `src/soulspot/main.py` (Entry point)
- `alembic/versions/*.py` (Migrations)
- `tests/**/*.py` (Test files selbst)

## Priority Test Types
1. Error/Exception handling (highest)
2. Edge cases (empty, null, invalid)
3. Async operations (race conditions)
4. Database transactions (rollback scenarios)
5. Integration points (external APIs)
```

**Kompilieren:**
```bash
gh aw compile .github/workflows/agentics/test-coverage-guardian.md
git add .github/workflows/agentics/test-coverage-guardian.md
git add .github/workflows/agentics/test-coverage-guardian.config.md
git add .github/workflows/test-coverage-guardian.yml
git commit -m "feat(ci): Add Test Coverage Guardian with concrete test suggestions"
git push
```

---

### Beispiel 3: Architecture Compliance Enforcer

**Szenario:** Stelle sicher, dass Code SoulSpot v3.0 Architektur folgt

**Workflow-Definition** (`.github/workflows/agentics/architecture-guardian.md`):
```markdown
---
name: Architecture Guardian
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
  - web-search  # Für Architektur-Docs
engine: claude-3-5-sonnet
timeout-minutes: 15
stop-after: 30 days
---

# SoulSpot Architecture Guardian

Du bist der Architektur-Wächter für SoulSpot Bridge v3.0.

## SoulSpot v3.0 Architektur-Prinzipien

### 1. Database Module (Mandatory)
**Regel:** ALLE DB-Operationen MÜSSEN über `DatabaseService` laufen.

**✅ Erlaubt:**
```python
from soulspot.database import DatabaseService

db_service = DatabaseService()
user = await db_service.get_entity("User", user_id)
await db_service.create_entity("Track", track_data)
```

**❌ Verboten:**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

session.query(User).filter_by(id=user_id).first()  # DIREKTE SQLAlchemy-Nutzung
```

### 2. Settings Service (Mandatory)
**Regel:** ALLE Config-Zugriffe MÜSSEN über `SettingsService` laufen.

**✅ Erlaubt:**
```python
from soulspot.settings import SettingsService

settings = SettingsService()
spotify_client_id = await settings.get("spotify.client_id")
```

**❌ Verboten:**
```python
import os
from dotenv import load_dotenv

spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")  # DIREKT aus ENV
```

### 3. Structured Errors (Mandatory)
**Regel:** ALLE Exceptions MÜSSEN strukturiert sein.

**✅ Erlaubt:**
```python
raise SoulspotError(
    code="SPOTIFY_AUTH_FAILED",
    message="Failed to authenticate with Spotify",
    context={"user_id": user_id, "reason": "invalid_token"},
    resolution="Re-authenticate via /auth/spotify",
    docs_url="https://docs.soulspot.dev/errors/SPOTIFY_AUTH_FAILED"
)
```

**❌ Verboten:**
```python
raise Exception("Spotify auth failed")  # GENERISCH
raise ValueError("Invalid token")  # NICHT STRUKTURIERT
```

### 4. Module Boundaries (Mandatory)
**Regel:** Module dürfen NICHT direkt andere Module importieren.

**✅ Erlaubt:**
```python
# In spotify/service.py
from soulspot.events import EventBus

event_bus.publish("spotify.playlist.synced", {"playlist_id": "..."})
```

**❌ Verboten:**
```python
# In spotify/service.py
from soulspot.soulseek.downloader import SoulseekDownloader  # CROSS-MODULE IMPORT

downloader.download_track(track)  # DIREKTE KOPPLUNG
```

### 5. Type Hints (Mandatory)
**Regel:** ALLE Public Functions brauchen Type Hints (mypy strict).

**✅ Erlaubt:**
```python
async def get_playlist(self, playlist_id: str) -> Playlist:
    ...

async def sync_tracks(
    self,
    playlist_id: str,
    force: bool = False
) -> list[Track]:
    ...
```

**❌ Verboten:**
```python
async def get_playlist(self, playlist_id):  # KEINE TYPE HINTS
    ...
```

## Aufgabe
Scanne ALLE geänderten Python-Dateien im PR auf Architektur-Violations:

### Scan-Algorithmus
```python
violations = []

for file in changed_python_files:
    content = read_file(file)
    
    # 1. Database Module Check
    if "from sqlalchemy" in content or "import sqlalchemy" in content:
        if "session.query" in content or "create_engine" in content:
            violations.append({
                "file": file,
                "rule": "Database Module",
                "severity": "CRITICAL",
                "line": find_line_number(...),
                "code_snippet": extract_snippet(...),
                "fix": "Ersetze durch database_service.get_entity(...)"
            })
    
    # 2. Settings Service Check
    if "os.getenv" in content or "load_dotenv" in content:
        violations.append({...})
    
    # 3. Structured Errors Check
    if "raise Exception" in content or "raise ValueError" in content:
        # Aber: Prüfe ob es SoulspotError ist
        if not "SoulspotError(" in content:
            violations.append({...})
    
    # 4. Module Boundaries Check
    if "from soulspot.spotify" in file.path("soulspot/soulseek"):
        violations.append({...})
    
    # 5. Type Hints Check
    # Parse AST für function definitions ohne annotations
    ...
```

### Output Format
```markdown
## 🏛️ Architecture Compliance Report

**Status:** ❌ FAILED (3 violations found)

---

### ❌ CRITICAL: Direct SQLAlchemy Usage
**File:** `src/soulspot/services/spotify.py`  
**Line:** 45  
**Rule:** Database Module Mandatory

**Violation:**
```python
45: session.query(User).filter_by(id=user_id).first()
```

**Fix:**
```python
# Ersetze durch:
user = await database_service.get_entity(
    entity_type="User",
    filters={"id": user_id}
)
```

**Documentation:** [Database Module Guide](https://github.com/bozzfozz/soulspot-bridge/blob/main/docs/version-3.0/DATABASE_MODULE.md)

---

### ❌ CRITICAL: Direct ENV Access
**File:** `src/soulspot/api/auth.py`  
**Line:** 12  
**Rule:** Settings Service Mandatory

**Violation:**
```python
12: client_id = os.getenv("SPOTIFY_CLIENT_ID")
```

**Fix:**
```python
# Ersetze durch:
from soulspot.settings import SettingsService

settings = SettingsService()
client_id = await settings.get("spotify.client_id")
```

---

### ❌ HIGH: Generic Exception
**File:** `src/soulspot/services/downloader.py`  
**Line:** 78  
**Rule:** Structured Errors Mandatory

**Violation:**
```python
78: raise Exception("Download failed")
```

**Fix:**
```python
raise SoulspotError(
    code="DOWNLOAD_FAILED",
    message=f"Failed to download track: {track.title}",
    context={
        "track_id": track.id,
        "source": "soulseek",
        "error": str(e)
    },
    resolution="Check network connectivity and retry",
    docs_url="https://docs.soulspot.dev/errors/DOWNLOAD_FAILED"
)
```

---

## Summary
- ❌ 3 violations found (2 CRITICAL, 1 HIGH)
- 🔧 All violations have concrete fixes provided
- 📚 See [Architecture Guide](https://github.com/bozzfozz/soulspot-bridge/blob/main/docs/version-3.0/ARCHITECTURE.md)

**Action Required:** Fix all CRITICAL violations before merge.
```

## Fehlerbehandlung
- Wenn File-Scan fehlschlägt: Logge Error, fahre fort mit nächstem File
- Wenn keine Python-Dateien geändert: Kommentiere "No Python files changed, skipping architecture check ✅"
```

**Kompilieren:**
```bash
gh aw compile .github/workflows/agentics/architecture-guardian.md
git add .github/workflows/agentics/architecture-guardian.md .github/workflows/architecture-guardian.yml
git commit -m "feat(ci): Add Architecture Guardian for v3.0 compliance enforcement"
git push
```

**Erwartetes Ergebnis:**
- Jeder PR wird auf Architektur-Violations gescannt
- Detaillierter Kommentar mit konkreten Fixes
- Verhindert Architektur-Drift

---

## Ressourcen und Weiterführende Links

### Offizielle Dokumentation

**GitHub Actions & Workflows:**
- 🏠 GitHub Actions Dokumentation: [https://docs.github.com/en/actions](https://docs.github.com/en/actions)
- 📘 Workflow-Syntax: [https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- 🛠️ Actions Marketplace: [https://github.com/marketplace?type=actions](https://github.com/marketplace?type=actions)
- 💼 GitHub Copilot: [https://docs.github.com/en/copilot](https://docs.github.com/en/copilot)

**GitHub Features:**
- 🔐 Secrets Management: [https://docs.github.com/en/actions/security-guides/encrypted-secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- 🏷️ GitHub Labels API: [https://docs.github.com/en/rest/issues/labels](https://docs.github.com/en/rest/issues/labels)
- 📦 Dependabot: [https://docs.github.com/en/code-security/dependabot](https://docs.github.com/en/code-security/dependabot)

### SoulSpot Bridge v3.0 Kontext

**Architektur-Dokumentation:**
- 📐 [Architecture Overview](./ARCHITECTURE.md)
- 🗄️ [Database Module](./DATABASE_MODULE.md)
- ⚙️ [Module Specification](./MODULE_SPECIFICATION.md)
- 🔧 [Module Communication](./MODULE_COMMUNICATION.md)
- 🎨 [UI Design System](./UI_DESIGN_SYSTEM.md)

**AI Integration:**
- 🤖 [AI Agent Recommendations](./AI_AGENT_RECOMMENDATIONS.md)
- 📝 [Code Documentation Guidelines](./CODE_DOCUMENTATION.md)

### GitHub Web UI Tutorials

**Workflow-Erstellung:**
- 📄 [Creating GitHub Actions](https://docs.github.com/en/actions/quickstart)
- 📊 [Using the workflow editor](https://docs.github.com/en/actions/using-workflows/about-workflows#creating-a-workflow-file)
- 🏗️ [GitHub Actions Examples](https://github.com/actions/starter-workflows)

**AI-Integration:**
- 🧠 [GitHub Copilot in PRs](https://docs.github.com/en/copilot/using-github-copilot/asking-github-copilot-questions-in-your-ide)
- 🤖 [Copilot Chat](https://docs.github.com/en/copilot/github-copilot-chat/using-github-copilot-chat-in-your-ide)

### Nützliche GitHub Actions

**Code Quality:**
```yaml
# In deinem Workflow verwenden:
- uses: actions/checkout@v4              # Code auschecken
- uses: actions/setup-python@v5          # Python einrichten
- uses: github/super-linter@v5           # Multi-Language Linter
- uses: codecov/codecov-action@v3        # Coverage Reports
```

**Security:**
```yaml
- uses: aquasecurity/trivy-action@master # Security Scanner
- uses: github/codeql-action/init@v3     # CodeQL Analysis
```

### Community & Support

**GitHub Discussions:**
- 💬 [GitHub Actions Community](https://github.com/orgs/community/discussions/categories/actions)
- 🐛 [Report Issues](https://github.com/actions/runner/issues)
- 📚 [GitHub Community Forum](https://github.community/)

---

## Zusammenfassung

**AI Agent Workflows** revolutionieren Repository-Automatisierung durch:

1. **GitHub-Native Integration:** Workflows direkt in GitHub Actions, nutzbar über Web-UI
2. **Kein lokales Setup:** Alles funktioniert im Browser ohne IDE oder CLI
3. **GitHub Copilot Integration:** KI-Unterstützung direkt in PRs und Issues
4. **Produktionsreif:** Basiert auf stabilen GitHub Features (Actions, Copilot, Dependabot)

**Für SoulSpot Bridge v3.0** ermöglichen sie:
- ✅ Automatische Architecture Compliance Checks via GitHub Actions
- ✅ Code-Reviews mit GitHub Copilot direkt in Pull Requests
- ✅ Dependency-Updates via GitHub Dependabot
- ✅ Dokumentations-Synchronisation via Actions
- ✅ Test-Coverage Monitoring in CI/CD

**Wichtigste Vorteile:**
1. Web-basiert (kein lokales Setup erforderlich)
2. Kostenlos für öffentliche Repos (GitHub Actions)
3. GitHub Copilot für PRs (~$10-20/Monat)
4. Integriert mit GitHub Security Features
5. Audit-Trail via GitHub Actions Logs

**Nächste Schritte:**
1. GitHub Copilot aktivieren (falls noch nicht vorhanden)
2. Ersten Workflow über GitHub UI erstellen (z.B. Linter)
3. GitHub Copilot in PRs testen (`/review` command)
4. Test Coverage Action hinzufügen
5. Monitoring über GitHub Actions Tab

---

**Dokument-Version:** 2.0 (GitHub-Native)
**Letzte Aktualisierung:** 2025-11-24  
**Änderungen:** Umgestellt von CLI/IDE-basiert auf GitHub-Web-native Nutzung
**Autor:** AI Documentation Agent (via GitHub Copilot)  
**Lizenz:** MIT (wie SoulSpot Bridge Projekt)

---

**✅ Hinweis:** Diese Version fokussiert auf GitHub-native Features, die direkt über die Web-Oberfläche nutzbar sind - ohne lokale Tool-Installation. Alle beschriebenen Workflows können im Browser erstellt und verwaltet werden.
