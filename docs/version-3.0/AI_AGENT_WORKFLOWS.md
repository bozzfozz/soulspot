# AI Agent Workflows für SoulSpot v3.0

> **⚠️ DEPRECATED - UNREALIZED WORKFLOWS:** These v3.0 AI agent workflows were **never implemented**. This document is from planning phase only.

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

## Inhaltsverzeichnis

1. [Übersicht](#übersicht)
2. [Was sind AI Agentic Workflows?](#was-sind-ai-agentic-workflows)
3. [GitHub Next Agentic Workflows](#github-next-agentic-workflows)
4. [Workflow-Typen und Kategorien](#workflow-typen-und-kategorien)
5. [Architektur und Funktionsweise](#architektur-und-funktionsweise)
6. [Integration in SoulSpot](#integration-in-soulspot)
7. [Workflow-Implementierung](#workflow-implementierung)
8. [Sicherheit und Best Practices](#sicherheit-und-best-practices)
9. [Praktische Beispiele](#praktische-beispiele)
10. [Ressourcen und Weiterführende Links](#ressourcen-und-weiterführende-links)

---

## Übersicht

**AI Agent Workflows** repräsentieren einen Paradigmenwechsel in der Entwicklungsautomatisierung: Statt Code zu schreiben, beschreiben Teams in natürlicher Sprache, was passieren soll. KI-Agenten interpretieren diese Anweisungen, treffen Entscheidungen und führen Aktionen aus.

### Wichtigste Erkenntnisse (TL;DR)

- **Was:** Markdown-basierte Workflow-Definitionen, die zu GitHub Actions kompiliert werden
- **Warum:** Zugänglicher, wartbarer, auditable Automatisierung
- **Wie:** Natural-Language-Beschreibungen → `gh-aw` CLI → YAML Workflows → AI-Agenten-Ausführung
- **Status:** Research-Prototyp von GitHub Next (nicht produktionsreif)
- **Nutzen für SoulSpot:** Automatisierte Code-Reviews, Dependency-Updates, Dokumentationspflege, QA-Tests

> ⚠️ **WARNUNG:** GitHub Agentic Workflows sind ein Research-Demonstrator. Diese Workflows sind nur Beispiele und nicht für den Produktionseinsatz vorgesehen. Verwendung auf eigenes Risiko.

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

## GitHub Next Agentic Workflows

### Projekt-Übersicht

**GitHub Next** ist das Research-Team von GitHub, das zukünftige Entwicklerwerkzeuge erforscht. **Agentic Workflows** ist eines ihrer Experimente zur "natürlichsprachigen Programmierung" von Automatisierung.

**Projektlinks:**
- Homepage: [https://githubnext.com/projects/agentic-workflows/](https://githubnext.com/projects/agentic-workflows/)
- Dokumentation: [https://githubnext.github.io/gh-aw/](https://githubnext.github.io/gh-aw/)
- Repository: [https://github.com/githubnext/agentics](https://github.com/githubnext/agentics)
- CLI-Tool: [https://github.com/githubnext/gh-aw](https://github.com/githubnext/gh-aw)

### Verfügbare Workflow-Sammlung

GitHub Next stellt eine **Beispiel-Familie wiederverwendbarer Workflows** bereit:

#### Triage & Analyse-Workflows

1. **🏷️ Issue Triage**
   - Automatisches Triagieren von Issues und Pull Requests
   - Labeling, Prioritäten, Kategorisierung
   - Docs: [issue-triage.md](https://github.com/githubnext/agentics/blob/main/docs/issue-triage.md)

2. **🏥 CI Doctor**
   - Überwacht CI-Workflows
   - Analysiert Fehler automatisch
   - Erstellt Diagnose-Reports
   - Docs: [ci-doctor.md](https://github.com/githubnext/agentics/blob/main/docs/ci-doctor.md)

3. **🔍 Repo Ask**
   - Intelligenter Repository-Assistent
   - Beantwortet Fragen zum Code
   - Analysiert Architektur
   - Docs: [repo-ask.md](https://github.com/githubnext/agentics/blob/main/docs/repo-ask.md)

4. **🔍 Daily Accessibility Review**
   - Prüft Barrierefreiheit
   - Führt automatisierte Tests aus
   - Docs: [daily-accessibility-review.md](https://github.com/githubnext/agentics/blob/main/docs/daily-accessibility-review.md)

5. **🔧 Q - Workflow Optimizer**
   - Expertensystem für Workflow-Analyse
   - Optimiert agentic Workflows
   - Docs: [q.md](https://github.com/githubnext/agentics/blob/main/docs/q.md)

#### Research, Status & Planning-Workflows

6. **📚 Weekly Research**
   - Sammelt Research-Updates
   - Verfolgt Industrie-Trends
   - Docs: [weekly-research.md](https://github.com/githubnext/agentics/blob/main/docs/weekly-research.md)

7. **👥 Daily Team Status**
   - Analysiert Repository-Aktivität
   - Erstellt Status-Reports
   - Docs: [daily-team-status.md](https://github.com/githubnext/agentics/blob/main/docs/daily-team-status.md)

8. **📋 Daily Plan**
   - Aktualisiert Planungs-Issues
   - Team-Koordination
   - Docs: [daily-plan.md](https://github.com/githubnext/agentics/blob/main/docs/daily-plan.md)

9. **📋 Plan Command**
   - `/plan` Kommando in Issues
   - Zerlegt Issues in Sub-Tasks
   - Docs: [plan.md](https://github.com/githubnext/agentics/blob/main/docs/plan.md)

#### Coding & Development-Workflows

10. **⚡ Daily Progress**
    - Automatische tägliche Feature-Entwicklung
    - Folgt strukturiertem Roadmap
    - Docs: [daily-progress.md](https://github.com/githubnext/agentics/blob/main/docs/daily-progress.md)

11. **📦 Daily Dependency Updater**
    - Aktualisiert Dependencies
    - Erstellt Pull Requests
    - Docs: [daily-dependency-updates.md](https://github.com/githubnext/agentics/blob/main/docs/daily-dependency-updates.md)

12. **📖 Regular Documentation Update**
    - Automatische Dokumentationspflege
    - Docs: [update-docs.md](https://github.com/githubnext/agentics/blob/main/docs/update-docs.md)

13. **🏥 PR Fix**
    - Analysiert fehlende CI-Checks
    - Implementiert Fixes für Pull Requests
    - Docs: [pr-fix.md](https://github.com/githubnext/agentics/blob/main/docs/pr-fix.md)

14. **🔎 Daily Adhoc QA**
    - Führt explorative QA-Tasks aus
    - Docs: [daily-qa.md](https://github.com/githubnext/agentics/blob/main/docs/daily-qa.md)

15. **🧪 Daily Test Coverage Improver**
    - Verbessert Test-Coverage
    - Fügt bedeutungsvolle Tests hinzu
    - Docs: [daily-test-improver.md](https://github.com/githubnext/agentics/blob/main/docs/daily-test-improver.md)

16. **⚡ Daily Performance Improver**
    - Analysiert und verbessert Performance
    - Benchmarking und Optimierung
    - Docs: [daily-perf-improver.md](https://github.com/githubnext/agentics/blob/main/docs/daily-perf-improver.md)

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

## Integration in SoulSpot

### Anwendungsfälle für SoulSpot v3.0

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

## Workflow-Implementierung

### Schritt-für-Schritt-Anleitung

#### 1. Installation des `gh-aw` CLI

```bash
# gh CLI muss installiert sein
brew install gh  # macOS
# oder
sudo apt install gh  # Linux

# gh-aw Extension installieren
gh extension install githubnext/gh-aw
```

#### 2. Workflow hinzufügen (aus Beispiel-Sammlung)

```bash
# Beispiel: Issue Triage Workflow hinzufügen
cd /path/to/soulspot
gh aw add githubnext/agentics/issue-triage --pr

# Erstellt automatisch eine PR mit dem Workflow
```

#### 3. Eigenen Workflow erstellen

**a) Workflow-Datei erstellen:**
```bash
mkdir -p .github/workflows/agentics
touch .github/workflows/agentics/soulspot-code-guardian.md
```

**b) Workflow definieren (Markdown):**
```markdown
---
name: SoulSpot Code Guardian
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
safe-outputs:
  create-comment:
    max: 1
    body-max-length: 10000
tools:
  - read-file
  - list-files
  - web-search
timeout-minutes: 15
stop-after: 30 days
---

# SoulSpot Code Guardian

Du bist ein Senior Python Backend Engineer für SoulSpot v3.0.

## Kontext
SoulSpot ist eine FastAPI-App für Spotify-Playlist-Sync und Soulseek-Downloads.

### Architektur-Richtlinien
1. **Database Module:** IMMER `database_service` nutzen, NIEMALS direktes SQLAlchemy
2. **Settings Service:** IMMER `settings_service`, NIEMALS `os.getenv` oder `.env`
3. **Structured Errors:** IMMER mit `code`, `message`, `context`, `resolution`, `docs_url`
4. **Module Boundaries:** KEINE Cross-Module Imports, nur Event-basiert

## Aufgabe
Überprüfe den Pull Request auf:
1. Architektur-Violations (siehe oben)
2. Code Quality (ruff, mypy, Docstrings)
3. Security (Bandit, Secrets, Input-Validation)
4. Testing (>80% Coverage für neue/geänderte Dateien)

## Output
Erstelle einen strukturierten Kommentar:
- ✅ Passed Checks
- ❌ Failed Checks mit konkreten Fixes
- 💡 Verbesserungsvorschläge
- 📝 Fehlende Dokumentation
```

**c) Workflow kompilieren:**
```bash
cd /path/to/soulspot
gh aw compile .github/workflows/agentics/soulspot-code-guardian.md

# Generiert:
# .github/workflows/soulspot-code-guardian.yml
```

**d) Workflow commiten und pushen:**
```bash
git add .github/workflows/agentics/soulspot-code-guardian.md
git add .github/workflows/soulspot-code-guardian.yml
git commit -m "feat(ci): Add SoulSpot Code Guardian agentic workflow"
git push origin main
```

#### 4. AI-Modell konfigurieren

**Unterstützte Engines (siehe [gh-aw Docs](https://githubnext.github.io/gh-aw/reference/engines/)):**
- **GitHub Copilot** (empfohlen für Integration)
- **Anthropic Claude** (beste Reasoning-Qualität)
- **OpenAI GPT-4** (gute Balance)
- **Azure OpenAI**
- **Google Gemini**

**API-Key als Secret hinzufügen:**
```bash
# Für GitHub Copilot
gh secret set GITHUB_TOKEN --body "$GITHUB_TOKEN"

# Für Anthropic Claude
gh secret set ANTHROPIC_API_KEY --body "sk-ant-..."

# Für OpenAI
gh secret set OPENAI_API_KEY --body "sk-..."
```

**Engine in Workflow-Datei spezifizieren:**
```markdown
---
name: My Workflow
engine: claude-3-5-sonnet  # oder gpt-4, copilot, gemini-pro
---
```

#### 5. Lokale Konfiguration (Optional)

**`.github/workflows/agentics/soulspot-code-guardian.config.md`:**
```markdown
# SoulSpot Code Guardian Configuration

## Custom Rules

### Backend Python Rules
- Enforce async/await for all DB operations
- Require type hints on all public functions
- Docstrings must include Examples section

### Frontend HTMX Rules
- All forms must have CSRF tokens
- HTMX responses must set correct `HX-*` headers
- Accessibility: All interactive elements need ARIA labels

## Severity Levels
- **Critical:** Architecture violations, security issues
- **High:** Missing tests, type hint violations
- **Medium:** Documentation gaps, minor style issues
- **Low:** Suggestions, optimizations
```

#### 6. Workflow testen

**Manuell triggern:**
```bash
gh aw run soulspot-code-guardian
```

**In PR testen:**
```bash
# Erstelle Test-PR
git checkout -b test/agentic-workflow
git commit --allow-empty -m "test: Trigger Code Guardian"
git push origin test/agentic-workflow
gh pr create --title "Test: Code Guardian" --body "Testing agentic workflow"

# Workflow wird automatisch getriggert
gh run list --workflow=soulspot-code-guardian.yml
gh run view <run-id> --log
```

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
   ![Latest Release](https://img.shields.io/github/v/release/bozzfozz/soulspot)
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
- **Projekt:** SoulSpot v3.0
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

Du bist der Architektur-Wächter für SoulSpot v3.0.

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

**Documentation:** [Database Module Guide](https://github.com/bozzfozz/soulspot/blob/main/docs/version-3.0/DATABASE_MODULE.md)

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
- 📚 See [Architecture Guide](https://github.com/bozzfozz/soulspot/blob/main/docs/version-3.0/ARCHITECTURE.md)

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

**GitHub Next Agentic Workflows:**
- 🏠 Projekt-Homepage: [https://githubnext.com/projects/agentic-workflows/](https://githubnext.com/projects/agentic-workflows/)
- 📘 Dokumentation: [https://githubnext.github.io/gh-aw/](https://githubnext.github.io/gh-aw/)
- 🛠️ CLI-Tool (gh-aw): [https://github.com/githubnext/gh-aw](https://github.com/githubnext/gh-aw)
- 📦 Workflow-Sammlung: [https://github.com/githubnext/agentics](https://github.com/githubnext/agentics)

**Einzelne Workflow-Dokumentationen:**
- 🏷️ [Issue Triage](https://github.com/githubnext/agentics/blob/main/docs/issue-triage.md)
- 🏥 [CI Doctor](https://github.com/githubnext/agentics/blob/main/docs/ci-doctor.md)
- 🔍 [Repo Ask](https://github.com/githubnext/agentics/blob/main/docs/repo-ask.md)
- ⚡ [Daily Progress](https://github.com/githubnext/agentics/blob/main/docs/daily-progress.md)
- 📋 [Plan Command](https://github.com/githubnext/agentics/blob/main/docs/plan.md)
- 🧪 [Test Coverage Improver](https://github.com/githubnext/agentics/blob/main/docs/daily-test-improver.md)
- 📦 [Dependency Updater](https://github.com/githubnext/agentics/blob/main/docs/daily-dependency-updates.md)
- [Alle Workflows →](https://github.com/githubnext/agentics/tree/main/docs)

### SoulSpot v3.0 Kontext

**Architektur-Dokumentation:**
- 📐 [Architecture Overview](./ARCHITECTURE.md)
- 🗄️ [Database Module](./DATABASE_MODULE.md)
- ⚙️ [Module Specification](./MODULE_SPECIFICATION.md)
- 🔧 [Module Communication](./MODULE_COMMUNICATION.md)
- 🎨 [UI Design System](./UI_DESIGN_SYSTEM.md)

**AI Integration:**
- 🤖 [AI Agent Recommendations](./AI_AGENT_RECOMMENDATIONS.md)
- 📝 [Code Documentation Guidelines](./CODE_DOCUMENTATION.md)

### Externe Ressourcen

**Agentic Workflows Konzepte:**
- 📄 [Microsoft Research: Agentic Workflows](https://www.microsoft.com/en-us/research/project/agentic-workflows/)
- 📊 [Weaviate: What are Agentic Workflows?](https://weaviate.io/blog/what-are-agentic-workflows)
- 🏗️ [Orkes: Agentic Workflow Architecture](https://orkes.io/blog/what-are-agentic-workflows/)

**AI Agents & LLMs:**
- 🧠 [Anthropic Claude Documentation](https://docs.anthropic.com/)
- 🤖 [OpenAI GPT-4 Documentation](https://platform.openai.com/docs/)
- 💼 [GitHub Copilot Documentation](https://docs.github.com/en/copilot)

### Tools & CLI

**Installation & Setup:**
```bash
# GitHub CLI
brew install gh  # macOS
sudo apt install gh  # Linux

# gh-aw Extension
gh extension install githubnext/gh-aw
gh aw --help
```

**Nützliche Kommandos:**
```bash
# Workflow hinzufügen (aus Sammlung)
gh aw add githubnext/agentics/<workflow-name> --pr

# Workflow kompilieren (Markdown → YAML)
gh aw compile <workflow.md>

# Workflow manuell starten
gh aw run <workflow-name>

# Workflow-Status checken
gh run list --workflow=<workflow-name>.yml
gh run view <run-id> --log
```

### Community & Support

**Feedback & Diskussion:**
- 💬 [GitHub Next Discord](https://gh.io/next-discord) - Channel: `#continuous-ai`
- 🐛 [Issue Tracker (gh-aw)](https://github.com/githubnext/gh-aw/issues)
- 📚 [Discussions (agentics)](https://github.com/githubnext/agentics/discussions)

---

## Zusammenfassung

**AI Agent Workflows** revolutionieren Repository-Automatisierung durch:

1. **Natürlichsprachige Programmierung:** Markdown statt YAML/Bash
2. **Autonome AI-Agenten:** Reasoning, Planning, Adaptation
3. **GitHub Actions Integration:** Sichere, auditable Ausführung
4. **Wiederverwendbare Workflows:** Issue Triage, CI Doctor, Test Improver, etc.

**Für SoulSpot v3.0** ermöglichen sie:
- ✅ Automatische Architecture Compliance Checks
- ✅ Test Coverage Überwachung mit konkreten Test-Vorschlägen
- ✅ Dependency-Updates mit automatischen Tests
- ✅ Dokumentations-Synchronisation
- ✅ Code Quality Enforcement

**Wichtigste Sicherheitsregeln:**
1. Start Small (Read-Only → Write)
2. Safe Outputs (Limits für PRs/Issues)
3. Timeouts & Stop-After
4. Human-in-the-Loop (DRAFT PRs)
5. Continuous Monitoring

**Nächste Schritte:**
1. `gh extension install githubnext/gh-aw` installieren
2. Mit Read-Only Workflow starten (z.B. Repo Ask)
3. SoulSpot Code Guardian implementieren
4. Test Coverage Guardian hinzufügen
5. Monitoring aufsetzen und evaluieren

---

**Dokument-Version:** 1.0  
**Letzte Aktualisierung:** 2025-11-22  
**Autor:** AI Documentation Agent (via GitHub Copilot)  
**Lizenz:** MIT (wie SoulSpot Projekt)

---

**⚠️ Rechtlicher Hinweis:** GitHub Agentic Workflows sind ein **Research-Prototyp** und nicht für den Produktionseinsatz vorgesehen. Alle Workflows müssen sorgfältig getestet und überwacht werden. Verwendung auf eigenes Risiko. Siehe [GitHub Next Terms](https://githubnext.com/terms) für Details.
