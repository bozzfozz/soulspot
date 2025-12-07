# Parallel Coordinator Agent

Koordiniert mehrere Subagents für parallele Task-Ausführung.

## Rolle

Der Parallel Coordinator ist der **Dispatcher** – er:
1. Parst eingehende `parallel:` Tasks
2. Splittet in einzelne Sub-Tasks
3. Ruft spezialisierte Subagents auf
4. Aggregiert Ergebnisse
5. Gibt kombiniertes Ergebnis zurück

## Input Format

```
parallel: <agent1>: <task1> | <agent2>: <task2> | <agent3>: <task3>
```

### Beispiele

```bash
# Drei parallele Tasks
parallel: code: Add validation | test: Write tests | docs: Update API

# Zwei parallele Recherchen
parallel: search: Find Track usages | search: Find Artist usages

# Code + Test Kombination
parallel: code: Refactor service | test: Update tests for refactor
```

## Output Format

```
═══════════════════════════════════════════
  Parallel Execution Complete
───────────────────────────────────────────
  Subagents: 3
  Duration: X seconds
───────────────────────────────────────────
  ✅ code-agent: Validation added (src/validators.py)
  ✅ test-agent: 5 tests created (tests/test_validators.py)
  ✅ docs-agent: API docs updated (docs/api.md)
───────────────────────────────────────────
  Status: All Complete
═══════════════════════════════════════════
```

## Supported Subagents

| Präfix | Agent | Beschreibung |
|--------|-------|--------------|
| `research:` | research-agent | Codebase recherchieren (primär) |
| `search:` | research-agent | Codebase durchsuchen (alias) |
| `code:` | code-agent | Code schreiben/editieren |
| `test:` | test-agent | Tests schreiben/ausführen |
| `docs:` | docs-agent | Dokumentation |
| `fix:` | code-agent | Bug fixes |
| `refactor:` | code-agent | Code refactoring |

## Error Handling

```
═══════════════════════════════════════════
  Parallel Execution Complete (with errors)
───────────────────────────────────────────
  ✅ code-agent: Success
  ❌ test-agent: Failed (import error)
  ✅ docs-agent: Success
───────────────────────────────────────────
  Status: Partial Success (2/3)
  Action: Review test-agent error
═══════════════════════════════════════════
```

## Integration

```python
# Wird via runSubagent aufgerufen
runSubagent(
    prompt="parallel: code: Add feature | test: Write tests",
    description="Parallel task execution"
)
```
