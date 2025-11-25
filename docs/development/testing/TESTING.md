# Test-Ausführungs-Anleitung für SoulSpot

## Schnellstart

### Alle Tests ausführen
```bash
# Komplette Test-Suite
pytest tests/ -v

# Mit Coverage-Report
pytest tests/ --cov=src/soulspot --cov-report=html --cov-report=term

# Nur Fehler anzeigen
pytest tests/ -q --tb=short
```

### Spezifische Test-Kategorien

#### Unit-Tests (490 Tests - 100% passing)
```bash
# Alle Unit-Tests
pytest tests/unit/ -v

# Schneller Durchlauf
pytest tests/unit/ -q

# Nur Services
pytest tests/unit/application/services/ -v

# Nur Infrastructure
pytest tests/unit/infrastructure/ -v
```

#### Integration-Tests (156 Tests)
```bash
# Alle Integration-Tests
pytest tests/integration/ -v

# Nur API-Tests
pytest tests/integration/api/ -v

# Nur UI-Tests
pytest tests/integration/ui/ -v
```

### Neue Test-Suites

#### Endpoint-Accessibility (46 Tests - 57% passing)
```bash
# Komplette Suite
pytest tests/integration/api/test_endpoint_accessibility.py -v

# Nur erfolgreiche Tests
pytest tests/integration/api/test_endpoint_accessibility.py -v -k "auth or library or settings"

# Einzelne Kategorien
pytest tests/integration/api/test_endpoint_accessibility.py::TestAuthEndpoints -v
pytest tests/integration/api/test_endpoint_accessibility.py::TestLibraryEndpoints -v
pytest tests/integration/api/test_endpoint_accessibility.py::TestPlaylistEndpoints -v
```

#### Error-Handling (28 Tests - 82% passing)
```bash
# Komplette Suite
pytest tests/integration/api/test_error_handling.py -v

# Nur Edge-Cases
pytest tests/integration/api/test_error_handling.py::TestEdgeCases -v

# Nur Validation
pytest tests/integration/api/test_error_handling.py::TestInputValidation -v
```

#### UI-Accessibility (15 Tests - 100% passing ✅)
```bash
# Komplette Suite
pytest tests/integration/ui/test_ui_accessibility.py -v

# Nur Hauptseiten
pytest tests/integration/ui/test_ui_accessibility.py::TestMainUIPages -v

# Nur HTMX
pytest tests/integration/ui/test_ui_accessibility.py::TestHTMXHeaders -v
```

## Erweiterte Optionen

### Coverage-Analyse
```bash
# HTML-Report generieren
pytest tests/ --cov=src/soulspot --cov-report=html
# Report öffnen: htmlcov/index.html

# Terminal-Output mit fehlenden Zeilen
pytest tests/ --cov=src/soulspot --cov-report=term-missing

# Nur bestimmte Module
pytest tests/ --cov=src/soulspot/api --cov-report=term
```

### Performance-Analyse
```bash
# Langsamste Tests anzeigen
pytest tests/ --durations=10

# Parallel ausführen (schneller)
pytest tests/ -n auto  # Benötigt pytest-xdist
```

### Debugging
```bash
# Verbose Output
pytest tests/ -vv

# Bei erstem Fehler stoppen
pytest tests/ -x

# Letzten fehlgeschlagenen Test erneut ausführen
pytest tests/ --lf

# Nur fehlgeschlagene Tests
pytest tests/ --failed-first

# Mit pdb bei Fehler
pytest tests/ --pdb
```

### Filterung
```bash
# Nach Test-Namen
pytest tests/ -k "auth"
pytest tests/ -k "test_health"

# Nach Marker
pytest tests/ -m "slow"  # Wenn Marker definiert

# Ausschließen
pytest tests/ -k "not slow"
```

## Make-Targets

Das Projekt bietet praktische Make-Shortcuts:

```bash
# Installation
make install

# Tests
make test              # Alle Tests
make test-unit         # Nur Unit-Tests
make test-cov          # Mit Coverage

# Code-Qualität
make lint              # Linter ausführen
make format            # Code formatieren
make type-check        # Type-Checking
make security          # Security-Scan

# Cleanup
make clean             # Temporäre Dateien löschen
```

## Continuous Integration

### GitHub Actions Workflow
```yaml
# In .github/workflows/tests.yml
- name: Run tests
  run: |
    pytest tests/ -v --cov=src/soulspot --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Bekannte Probleme & Workarounds

### Problem: Download-Endpoints geben 503
**Ursache**: Job Queue nicht in Test-Fixture  
**Workaround**: Diese Tests überspringen
```bash
pytest tests/ -k "not download"
```

### Problem: Dashboard/Widget-Endpoints geben 404
**Ursache**: Route-Prefix-Problem  
**Workaround**: Diese Tests überspringen
```bash
pytest tests/integration/api/test_endpoint_accessibility.py -k "not dashboard and not widget and not sse"
```

### Nur erfolgreiche neue Tests ausführen
```bash
# Kombination aller funktionierenden Tests
pytest tests/integration/api/test_endpoint_accessibility.py::TestHealthEndpoints \
       tests/integration/api/test_endpoint_accessibility.py::TestAuthEndpoints \
       tests/integration/api/test_endpoint_accessibility.py::TestLibraryEndpoints \
       tests/integration/api/test_endpoint_accessibility.py::TestSettingsEndpoints \
       tests/integration/ui/test_ui_accessibility.py \
       -v
```

## Test-Reports

### HTML-Coverage-Report
```bash
pytest tests/ --cov=src/soulspot --cov-report=html
# Öffne: htmlcov/index.html im Browser
```

### JUnit XML (für CI)
```bash
pytest tests/ --junitxml=test-results.xml
```

### JSON-Report
```bash
pytest tests/ --json-report --json-report-file=report.json
# Benötigt: pip install pytest-json-report
```

## Best Practices

### Vor Commit
```bash
# 1. Formatieren
make format

# 2. Linten
make lint

# 3. Tests
make test

# 4. Type-Check
make type-check

# 5. Security
make security
```

### Für Pull Requests
```bash
# Komplette Validierung
pytest tests/ -v --cov=src/soulspot --cov-report=html --cov-report=term
make lint
make type-check
make security
```

## Troubleshooting

### Tests hängen
```bash
# Timeout setzen
pytest tests/ --timeout=30

# Einzelnen Test debuggen
pytest tests/path/to/test.py::test_name -v --log-cli-level=DEBUG
```

### Import-Fehler
```bash
# PYTHONPATH setzen
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
pytest tests/ -v
```

### Datenbank-Probleme
```bash
# Temporäre Test-DB löschen
rm -rf /tmp/pytest-of-*/
pytest tests/ -v
```

## Ressourcen

- **Test-Report**: `TEST_REPORT.md`
- **Coverage-Report**: `htmlcov/index.html` (nach `make test-cov`)
- **pytest Dokumentation**: https://docs.pytest.org/
- **Coverage.py Dokumentation**: https://coverage.readthedocs.io/

## Support

Bei Problemen:
1. `TEST_REPORT.md` konsultieren
2. Logs mit `-v` und `--log-cli-level=DEBUG` prüfen
3. GitHub Issues erstellen

---

**Letzte Aktualisierung**: 2025-11-18  
**Version**: 0.1.0
