# 🎯 Dokumentations-Migration - Sofort-Start-Anleitung

> **Status:** ✅ Bereit zur Ausführung  
> **Dauer:** 12-18 Stunden  
> **Kritischer Fokus:** Code-Synchronisation (Phase 3)

---

## 📋 Was wurde vorbereitet:

### 1. Haupt-Dokumente
- ✅ **DOCUMENTATION_MIGRATION_PLAN.md** - Vollständiger 7-Phasen-Plan
- ✅ **CODE_VALIDATION_REFERENCE.md** - Code-Sync Workflows & Checklisten
- ✅ **scripts/migrate-docs.sh** - Automatisiertes Migrations-Skript
- ✅ **scripts/validate-docs.sh** - Code-Sync Validierungs-Skript

### 2. Neue Features im Plan
- ✅ **Phase 3: Code-Synchronisation & Validierung (5-8h)** - KRITISCH!
- ✅ Validation Checklists für API/Feature/Architecture Docs
- ✅ Automatisierte Code-Doc Sync Checks
- ✅ "Code Verified: YYYY-MM-DD" Header-Pflicht

---

## 🚀 Quick Start (3 Optionen)

### Option A: Mit GitHub Copilot Agent (Empfohlen für virtuelle Umgebung)

⚠️ **Hinweis:** In der virtuellen GitHub-Umgebung können Shell-Skripte nicht direkt ausgeführt werden.
Stattdessen nutzen wir Copilot Agents mit den Plan-Dokumenten als Anleitung.

```
1. Agent starten mit diesem Prompt:
   "Führe Dokumentations-Migration aus nach DOCUMENTATION_MIGRATION_PLAN.md.
    Fokus auf Phase 3: Code-Synchronisation - jedes Doc gegen aktuellen Code validieren!"

2. Agent wird:
   - Ordner-Struktur erstellen
   - Dateien migrieren
   - ⚠️ KRITISCH: Jeden Endpoint/Service gegen Code prüfen
   - Code-Beispiele aus echtem Source extrahieren
   - Validation durchführen

3. Du überwachst:
   - Phase 3 besonders genau
   - Code-Beispiele sind echt (nicht erfunden)
   - Endpoints existieren im Code
```

**Zeitaufwand:** 2h Setup + 5-8h Code-Sync (Agent-gestützt)

---

### Option B: Schrittweise mit Agent (Empfohlen)

**Tag 1 (4h) - Phase 1+2: Setup & Migration**

Agent Prompt:
```
Task #1: Dokumentations-Migration Phase 1+2

1. Erstelle Ordner-Struktur in docs-new/ gemäß DOCUMENTATION_MIGRATION_PLAN.md
2. Migriere HIGH Priority Docs:
   - API Reference (17 Dateien)
   - Core Architecture (8 Dateien)
   - User Guides (6 Dateien)
3. Kopiere Dateien 1:1 (noch OHNE Code-Validierung)

Siehe: DOCUMENTATION_MIGRATION_PLAN.md Phase 1+2
```

**Tag 2 (6h) - Phase 3: Code-Synchronisation ⚠️ KRITISCH**

Agent Prompt für JEDES API Doc:
```
Task #2.1: Validiere docs-new/03-api-reference/auth.md gegen Code

KRITISCH: Nicht einfach kopieren, sondern:

1. Öffne src/soulspot/api/routers/auth.py
2. Suche alle @router. Decorators
3. Liste alle Endpoints auf (GET/POST/PUT/DELETE + Pfad)
4. Vergleiche mit auth.md:
   - Jeder Endpoint im Code MUSS dokumentiert sein
   - Jeder dokumentierte Endpoint MUSS im Code existieren
5. Für jedes Code-Beispiel:
   - Extrahiere ECHTEN Code aus Router-Datei
   - Füge Source-Pfad + Line Numbers hinzu
   - Kein Pseudo-Code!
6. Füge Header hinzu: "Code Verified: 2025-12-30"

Wiederhole für alle 17 API-Docs.
```

**Tag 3 (4h) - Phase 4+5: Polish & Quality**

Agent Prompt:
```
Task #3: Quality Gates

1. Prüfe alle Links in docs-new/
2. Vereinheitliche alle Version-Referenzen auf v2.0
3. Validiere:
   - Endpoint Count: Code vs Docs
   - Service Coverage: Alle Services dokumentiert?
   - Code Verified Headers: Alle vorhanden?

Siehe: CODE_VALIDATION_REFERENCE.md
```

**Tag 4 (2h) - Phase 6+7: Finalisierung**

Manuell:
```
1. Review docs-new/ komplett
2. Backup: docs → docs-backup-20251230
3. Migration: docs-new → docs
4. Commit
```

---

**❌ ALTE Methode (FALSCH):**
```
Agent Prompt: "Kopiere alle Docs von docs/api/ nach docs-new/03-api-reference/"
# ❌ Keine Code-Validierung!
```

**✅ NEUE Methode (RICHTIG - für virtuelle GitHub-Umgebung):**

**Agent Prompt:**
```
Migriere docs/api/auth-api.md → docs-new/03-api-reference/auth.md

KRITISCHER CODE-SYNC WORKFLOW:

1. Öffne src/soulspot/api/routers/auth.py mit read_file
2. Suche alle Zeilen mit @router.get, @router.post, etc.
3. Erstelle Liste aller Endpoints:
   Beispiel Output:
   - GET /api/auth/authorize (Line 50)
   - GET /api/auth/callback (Line 87)
   - GET /api/auth/session (Line 152)
   - ... (insgesamt 9 Endpoints)

4. Öffne docs/api/auth-api.md
5. Vergleiche dokumentierte Endpoints mit Code-Liste
6. Wenn Mismatch → Dokumentation ANPASSEN (nicht Code!)

7. Für jedes Code-Beispiel in auth-api.md:
   - Öffne Source-Datei mit read_file
   - Extrahiere ECHTEN Code-Block
   - Ersetze alten Code mit echtem Code
   - Füge Kommentar hinzu: # src/soulspot/api/routers/auth.py (lines X-Y)

8. Füge Header hinzu:
   > **Code Verified:** 2025-12-30 ✅

9. Speichere als docs-new/03-api-reference/auth.md

⚠️ Kein Pseudo-Code! Kein "example code"! Nur ECHTER Source!
```utput: 9 endpoints

# 3. Dokumentation prüfen
grep "^### (GET|POST|PUT|DELETE)" docs-new/03-api-reference/auth.md | wc -l
# Output: muss 9 sein!

# 4. Code-Beispiele ECHT machen
sed -n '50,65p' src/soulspot/api/routers/auth.py > /tmp/snippet.txt
## 📊 Erfolgs-Metriken

**Am Ende sollte gelten (via Agent Validation):**

**Agent Validation Prompt:**
```
Validiere docs-new/ Qualität:

1. Endpoint Coverage Check:
   - Durchsuche src/soulspot/api/routers/*.py nach @router. Patterns
   - Zähle alle Endpoints (erwarte ~200)
   - Durchsuche docs-new/03-api-reference/*.md nach "### GET|POST|PUT|DELETE"
   - Zähle dokumentierte Endpoints
   - Report: "Code: X endpoints, Docs: Y endpoints" → MUSS gleich sein!

2. Service Coverage Check:
   - Liste alle *_service.py in application/services/ (erwarte ~18)
   - Durchsuche docs-new/06-features/ nach Service-Namen
   - Report: Welche Services fehlen in Doku?

3. Code Verified Headers:
   - Zähle alle .md in docs-new/ (ohne _archive/)
   - Durchsuche nach "Code Verified:" Pattern
   - Report: "X/Y Docs haben Code Verified Header"

4. Code-Beispiel Validierung (Stichprobe):
   - Wähle 5 zufällige API Docs
   - Für jedes Code-Beispiel:
     - Prüfe ob Source-Pfad angegeben (# src/soulspot/...)
     - Öffne Source-Datei
     - Verify Code-Block existiert tatsächlich
   - Report: "X/5 Code-Beispiele verifiziert"

Finale Bewertung: ✅ PASS oder ❌ FAIL mit Details
```

**Erwartete Metriken:**
- ✅ Endpoints: 200 (Code) = 200 (Docs)
- ✅ Services: 18 dokumentiert von 18
- ✅ Code Verified: ~120/120 Headers
- ✅ Code-Beispiele: 100% echt (Stichprobe)

## 🛠️ Agent Prompts & Helpers

### Endpoint-Liste generieren (Agent Prompt)

```
Liste alle Endpoints in src/soulspot/api/routers/auth.py:

1. Öffne Datei mit read_file
2. Finde alle Zeilen mit @router.get, @router.post, @router.put, @router.delete
3. Extrahiere für jede:
   - HTTP Method (GET/POST/PUT/DELETE)
   - Pfad (z.B. "/authorize")
   - Line Number
4. Ausgabe als Tabelle:

| Line | Method | Path | Function |
|------|--------|------|----------|
| 50   | GET    | /authorize | authorize() |
| 87   | GET    | /callback  | callback() |
| ...  | ...    | ...        | ... |

Total: X endpoints
```

### Code-Beispiel extrahieren (Agent Prompt)

```
Extrahiere Code-Beispiel für Funktion authorize() aus auth.py:

1. Öffne src/soulspot/api/routers/auth.py mit read_file
2. Finde @router.get("/authorize") (ca. Line 50)
3. Extrahiere komplette Funktion (bis nächste @router oder Ende)
4. Formatiere als Code-Block:

```python
# src/soulspot/api/routers/auth.py (lines 50-85)
@router.get("/authorize")
async def authorize(
    request: Request,
    ...
) -> Response:
    # [ECHTER CODE - KEIN BEISPIEL!]
\`\`\`

## 🎯 Nächster Schritt (Virtuelle GitHub-Umgebung)

**Wähle eine Option:**

1. **Mit Agent starten:** → Starte Agent mit Prompt aus Option A/B oben
2. **Manuell schrittweise:** → Folge DOCUMENTATION_MIGRATION_PLAN.md manuell
3. **Erst reviewen:** → Lies CODE_VALIDATION_REFERENCE.md

**Empfehlung für virtuelle Umgebung:**
- **Option A (Agent)** - Schnellster Weg, aber überwache Phase 3 genau!
- **Option B (Schrittweise)** - Beste Kontrolle, nutze Agent pro Phase

**⚠️ KRITISCH für Agent-basierte Migration:**
- Agent muss read_file benutzen für Code-Zugriff
- Agent muss grep_search benutzen für Endpoint-Suche
## 📞 Support

**Bei Fragen während Migration:**
- Plan: `docs/DOCUMENTATION_MIGRATION_PLAN.md`
- Code-Sync: `docs/CODE_VALIDATION_REFERENCE.md`
- Agent Prompts: Siehe oben in diesem Dokument

**Wichtigste Regel:**
> Lieber 1 Tag länger für Phase 3 (Code-Sync) als falsche Doku ausliefern!

**Für virtuelle GitHub-Umgebung:**
- ✅ Nutze Agent mit detaillierten Prompts
- ✅ Agent verwendet read_file, grep_search, semantic_search
- ✅ Überwache Code-Sync in Phase 3 besonders genau
- ❌ Keine Shell-Skripte (funktionieren nicht in vscode-vfs://)

---

**Viel Erfolg! 🚀**

Die Pläne sind bereit, Agent-Prompts vorbereitet, jetzt kann's losgehen!
extract_code() {
    local file=$1
    local start=$2
    local end=$3
    echo "# $file (lines $start-$end)"
    sed -n "${start},${end}p" "$file"
}

# Usage:
extract_code src/soulspot/api/routers/auth.py 50 65
```

### Endpoint-Liste generieren

```bash
# Alle Endpoints eines Routers
list_endpoints() {
    local router=$1
    grep -n "@router\." "$router" | \
    sed 's/\([0-9]*\):.*@router\.\([a-z]*\)("\([^"]*\)".*/Line \1: \2 \3/'
}

# Usage:
list_endpoints src/soulspot/api/routers/auth.py
```

---

## 🎯 Nächster Schritt

**Wähle eine Option:**

1. **Sofort starten:** → `./scripts/migrate-docs.sh --dry-run`
2. **Schrittweise:** → Öffne `DOCUMENTATION_MIGRATION_PLAN.md` Tag 1
3. **Erst reviewen:** → Lies `CODE_VALIDATION_REFERENCE.md`

**Empfehlung:**
- Erste Migration? → **Option B (Schrittweise)**
- Erfahren? → **Option A (Voll-Automatisch)**
- Unsicher? → **Option C (Review)**

---

## 📞 Support

**Bei Fragen während Migration:**
- Plan: `docs/DOCUMENTATION_MIGRATION_PLAN.md`
- Code-Sync: `docs/CODE_VALIDATION_REFERENCE.md`
- Scripts: `scripts/migrate-docs.sh` + `scripts/validate-docs.sh`

**Wichtigste Regel:**
> Lieber 1 Tag länger für Phase 3 (Code-Sync) als falsche Doku ausliefern!

---

**Viel Erfolg! 🚀**

Die Tools sind bereit, der Plan ist detailliert, jetzt kann's losgehen!
