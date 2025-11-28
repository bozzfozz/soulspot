# UI Migration Cleanup Guide

> **Datum:** November 2025  
> **Status:** Migration abgeschlossen, Cleanup ausstehend

Die UI wurde vollständig auf das neue Design-System migriert. Dieses Dokument listet alle obsoleten Dateien, die sicher gelöscht werden können.

---

## 🗑️ Zu löschende Dateien

### Templates

```bash
# Obsolete Haupttemplates
rm src/soulspot/templates/theme-sample.html
rm src/soulspot/templates/ui-demo.html
```

### Includes

```bash
# Deprecated - durch sidebar.html und macros.html ersetzt
rm src/soulspot/templates/includes/_navigation.html
rm src/soulspot/templates/includes/_theme.html
```

### Partials (Widget-System)

```bash
# Widget-System wurde entfernt
rm src/soulspot/templates/partials/widget_canvas.html
rm src/soulspot/templates/partials/widget_catalog_modal.html
rm src/soulspot/templates/partials/widget_config_modal.html
rm -rf src/soulspot/templates/partials/widgets/
```

### Alte CSS-Dateien

```bash
# Gesamter Ordner - ersetzt durch /static/new-ui/css/
rm -rf src/soulspot/static/css/
```

**Enthält:**
- `components.css`
- `enhancements.css`
- `input.css`
- `layout.css`
- `modern-ui.css`
- `style.css`
- `theme.css`
- `ui-components.css`
- `ui-layout.css`
- `ui-theme.css`
- `variables.css`

### Tests

```bash
# Tests für altes Theme-System
rm tests/integration/test_theme.py
```

---

## ✅ Neue Struktur (behalten)

### CSS (`/static/new-ui/css/`)
| Datei | Zweck |
|-------|-------|
| `variables.css` | CSS Custom Properties (Farben, Spacing, Typography) |
| `components.css` | Basis-Komponenten (Buttons, Cards, Badges) |
| `ui-components.css` | Komplexe UI-Elemente (Modals, Dropdowns, Tables) |
| `main.css` | Layout, Utilities, Page-spezifische Styles |

### JavaScript (`/static/new-ui/js/`)
| Datei | Zweck |
|-------|-------|
| `app.js` | SoulSpot Global Object, Event Handlers, HTMX Integration |

### Includes (`/templates/includes/`)
| Datei | Status |
|-------|--------|
| `macros.html` | ✅ NEU - Design System Macros |
| `sidebar.html` | ✅ NEU - Sidebar Navigation |
| `_components.html` | ✅ AKTUALISIERT - Legacy Macros mit neuem Styling |
| `_skeleton.html` | ✅ AKTUALISIERT - Skeleton Loaders |
| `_navigation.html` | ❌ DEPRECATED - Löschen |
| `_theme.html` | ❌ DEPRECATED - Löschen |

---

## 🔧 Schnell-Cleanup Script

Alle obsoleten Dateien auf einmal löschen:

```bash
#!/bin/bash
# cleanup-old-ui.sh

set -e

echo "🧹 SoulSpot UI Cleanup"
echo "======================"

# Templates
rm -f src/soulspot/templates/theme-sample.html
rm -f src/soulspot/templates/ui-demo.html
echo "✓ Obsolete Templates entfernt"

# Includes
rm -f src/soulspot/templates/includes/_navigation.html
rm -f src/soulspot/templates/includes/_theme.html
echo "✓ Deprecated Includes entfernt"

# Widget-System
rm -f src/soulspot/templates/partials/widget_canvas.html
rm -f src/soulspot/templates/partials/widget_catalog_modal.html
rm -f src/soulspot/templates/partials/widget_config_modal.html
rm -rf src/soulspot/templates/partials/widgets/
echo "✓ Widget-System entfernt"

# Alte CSS
rm -rf src/soulspot/static/css/
echo "✓ Alte CSS-Dateien entfernt"

# Tests
rm -f tests/integration/test_theme.py
echo "✓ Obsolete Tests entfernt"

echo ""
echo "✅ Cleanup abgeschlossen!"
echo "   Neue UI: /static/new-ui/"
echo "   Styleguide: /styleguide"
```

---

## 🗑️ Leere API Router (können entfernt werden)

Die folgenden Router-Dateien sind leer und enthalten keine Endpoints:

```bash
# Leere Router entfernen
rm src/soulspot/api/routers/albums.py
rm src/soulspot/api/routers/dashboard.py
rm src/soulspot/api/routers/widget_templates.py
rm src/soulspot/api/routers/widgets.py
```

**Hinweis:** Nach dem Löschen müssen ggf. Imports in `routers/__init__.py` angepasst werden.

---

## 📋 TODO: Große Router aufteilen

Die folgenden Router sind sehr groß und sollten bei Gelegenheit aufgeteilt werden:

| Router | Endpoints | Vorschlag |
|--------|-----------|-----------|
| `automation.py` | 25 | Aufteilen in: `watchlists.py`, `rules.py`, `filters.py`, `discography.py` |
| `ui.py` | 26 | Aufteilen in: `ui_pages.py`, `ui_library.py`, `ui_spotify.py` |
| `library.py` | 15 | Aufteilen in: `library_scan.py`, `library_duplicates.py`, `library_import.py` |

**Priorität:** Niedrig (funktioniert, aber schwerer wartbar)

---

## 📝 Bereits erledigte Änderungen

- [x] `/theme-sample` Route aus `ui.py` entfernt
- [x] `test_theme.py` Tests durch Deprecation-Hinweis ersetzt
- [x] 21+ Templates auf neues Design migriert
- [x] 8+ Partials aktualisiert
- [x] Neue CSS-Struktur in `/static/new-ui/` erstellt
- [x] `/styleguide` Route hinzugefügt

---

## ⚠️ Hinweise

1. **Vor dem Löschen:** Sicherstellen, dass keine lokalen Änderungen an den alten Dateien existieren
2. **Nach dem Löschen:** `git status` prüfen und committen
3. **CI:** Tests sollten nach Cleanup grün bleiben (alte Tests wurden bereits entfernt/ersetzt)

---

*Diese Datei kann nach erfolgreichem Cleanup ebenfalls gelöscht werden.*
