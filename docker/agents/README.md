# SoulSpot AI Agents

Spezialisierte AI-Agenten für parallele Task-Ausführung.

## Verfügbare Agents

| Agent | Datei | Zweck |
|-------|-------|-------|
| **Parallel Coordinator** | `parallel-coordinator.md` | Koordiniert mehrere Subagents gleichzeitig |
| **Code Agent** | `code-agent.md` | Code schreiben, editieren, refactoren |
| **Test Agent** | `test-agent.md` | Tests schreiben und ausführen |
| **Research Agent** | `research-agent.md` | Codebase durchsuchen, analysieren |
| **Docs Agent** | `docs-agent.md` | Dokumentation erstellen und aktualisieren |

## Usage

### Einzelner Subagent
```
research: How is authentication implemented?
code: Implement feature X
test: Write unit tests for feature X
docs: Document feature X
```

### Empfohlene Reihenfolge
```
1. research:  → Kontext verstehen
2. code:      → Code schreiben
3. test:      → Tests schreiben
4. docs:      → Dokumentieren
```

### Parallele Ausführung
```
parallel: code: Implement feature | test: Write tests | docs: Update docs
```

## Integration mit TaskSync

Diese Agents werden von TaskSync V5 gesteuert:
1. TaskSync empfängt Task vom User
2. TaskSync erkennt `parallel:` Präfix
3. TaskSync dispatcht zu Subagents
4. Subagents arbeiten parallel
5. TaskSync aggregiert Ergebnisse
6. TaskSync fragt nächste Task ab
