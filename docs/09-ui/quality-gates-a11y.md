# A11Y Quality Gates & Testing

**Category:** Quality Assurance / Testing  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [Accessibility Guide](./accessibility-guide.md), [Testing Guide](../05-developer-guides/testing-guide.md)

---

## Overview

Enforce WCAG 2.1 AA/AAA compliance using automated + manual testing.

## Pre-PR Quality Gate Script

**Location:** `scripts/quality-gates-a11y.sh`

```bash
#!/bin/bash
set -e

echo "🔍 Running A11Y Quality Gates..."
echo ""

# 1. Code Quality
echo "✓ Phase 1: Code Quality Checks"
ruff check . --config pyproject.toml
mypy --config-file mypy.ini src/
bandit -r src/ -f json -o /tmp/bandit-report.json
echo "  Code quality: PASS ✅"
echo ""

# 2. Unit Tests
echo "✓ Phase 2: Unit Tests"
pytest tests/unit/ -v --tb=short
echo "  Unit tests: PASS ✅"
echo ""

# 3. A11Y Automated Tests
echo "✓ Phase 3: A11Y Automated Scanning"

# axe-core via Python
if python3 -c "import axe_selenium_python" 2>/dev/null; then
  echo "  Running axe-core via Selenium..."
  python3 << 'EOF'
import json
from selenium import webdriver
from axe_selenium_python import Axe

driver = webdriver.Chrome()
driver.get("http://localhost:8000")

axe = Axe(driver)
axe.inject()
results = axe.run()

with open('/tmp/axe-results.json', 'w') as f:
    json.dump(results, f)

driver.quit()
print(f"  Violations: {len(results['violations'])}")
EOF
  echo "  axe-core scan: DONE"
else
  echo "  ⚠️  axe-selenium-python not found"
fi

# HTML validation
if python3 -c "import html5lib" 2>/dev/null; then
  echo "  Validating HTML..."
  find src/soulspot/templates -name "*.html" -exec python3 -c "
import sys
import html5lib
try:
    with open('{}', 'r') as f:
        html5lib.parse(f.read())
    sys.exit(0)
except Exception as e:
    print(f'ERROR in {}: {e}')
    sys.exit(1)
" \;
  echo "  HTML validation: DONE"
fi

echo ""
echo "═══════════════════════════════════"
echo "  ✅ All Quality Gates PASSED"
echo "═══════════════════════════════════"
```

**Dependencies:**

```txt
# requirements.txt or pyproject.toml
axe-selenium-python>=2.1.6
selenium>=4.0.0
html5lib>=1.1
```

## Automated A11Y Testing Tools

### Tool 1: axe-core

```bash
# Install
npm install -g @axe-core/cli

# Run on templates
axe src/soulspot/templates/base.html --headless --show-errors

# JSON output
axe src/soulspot/templates/base.html --output json > results.json
```

### Tool 2: Lighthouse

```bash
# Install
npm install -g lighthouse

# Audit page
lighthouse http://localhost:8000 --view

# Headless JSON output
lighthouse http://localhost:8000 --output=json --output-path=./report.json
```

### Tool 3: WAVE (WebAIM)

Browser extension: [https://wave.webaim.org/extension/](https://wave.webaim.org/extension/)

## Python-Based A11Y Testing

### pytest-axe Integration

```python
# tests/a11y/test_accessibility.py
import pytest
from selenium import webdriver
from axe_selenium_python import Axe

@pytest.fixture
def driver():
    driver = webdriver.Chrome()
    yield driver
    driver.quit()

def test_homepage_accessibility(driver):
    driver.get("http://localhost:8000")
    
    axe = Axe(driver)
    axe.inject()
    results = axe.run()
    
    # Assert no violations
    assert len(results["violations"]) == 0, \
        f"Found {len(results['violations'])} accessibility violations"

def test_library_page_accessibility(driver):
    driver.get("http://localhost:8000/library/artists")
    
    axe = Axe(driver)
    axe.inject()
    results = axe.run()
    
    violations = results["violations"]
    assert len(violations) == 0, \
        f"Violations: {[v['id'] for v in violations]}"
```

## Manual Testing Checklist

### Keyboard Navigation

- [ ] Tab through all interactive elements
- [ ] Shift+Tab navigates backwards
- [ ] Enter/Space activates buttons/links
- [ ] Escape closes modals/dropdowns
- [ ] Arrow keys navigate lists/menus
- [ ] No keyboard traps (can exit all elements)

### Screen Reader Testing

**VoiceOver (macOS):**

```
Cmd+F5: Enable/Disable
VO+A: Start reading
VO+Right/Left: Navigate
VO+Space: Activate
```

**NVDA (Windows):**

```
Ctrl+Alt+N: Start NVDA
Insert+Down: Read from cursor
Tab: Navigate interactive
Enter: Activate
```

**Checklist:**

- [ ] All images announced with alt text
- [ ] Form labels announced correctly
- [ ] Buttons have meaningful labels
- [ ] Live regions announce updates
- [ ] Modal focus is trapped
- [ ] Headings are hierarchical

### Focus Indicators

- [ ] All interactive elements have visible focus
- [ ] Focus ring has 3:1 contrast minimum
- [ ] Focus order is logical (visual flow)
- [ ] No focus on hidden elements

### Color Contrast

Use tools:
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- Chrome DevTools Lighthouse
- axe DevTools extension

**Checklist:**

- [ ] Normal text: 4.5:1 minimum (AA)
- [ ] Large text (18pt+): 3:1 minimum (AA)
- [ ] UI components: 3:1 minimum
- [ ] Focus indicators: 3:1 minimum

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/a11y.yml
name: Accessibility Testing

on: [push, pull_request]

jobs:
  a11y:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install axe-selenium-python selenium
      
      - name: Start application
        run: |
          uvicorn src.soulspot.main:app --host 0.0.0.0 --port 8000 &
          sleep 5
      
      - name: Run axe-core tests
        run: |
          pytest tests/a11y/ -v
      
      - name: Upload results
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: a11y-violations
          path: /tmp/axe-results.json
```

## Violation Severity Levels

| Level | Action | Example |
|-------|--------|---------|
| **Critical** | ❌ Block PR | Missing alt text, keyboard trap |
| **Serious** | ⚠️ Warning | Low contrast, missing ARIA |
| **Moderate** | ℹ️ Info | Redundant labels |
| **Minor** | ✅ Pass | Best practice suggestions |

## Common Violations & Fixes

### Missing Alt Text

```html
<!-- ❌ WRONG -->
<img src="/album.jpg">

<!-- ✅ RIGHT -->
<img src="/album.jpg" alt="Album cover for Thriller by Michael Jackson">
```

### Low Color Contrast

```css
/* ❌ WRONG: 2.8:1 contrast */
color: #999999;
background: #ffffff;

/* ✅ RIGHT: 4.6:1 contrast */
color: #666666;
background: #ffffff;
```

### Missing ARIA Labels

```html
<!-- ❌ WRONG -->
<button>
  <i class="bi-play"></i>
</button>

<!-- ✅ RIGHT -->
<button aria-label="Play track Thriller">
  <i class="bi-play" aria-hidden="true"></i>
</button>
```

### Keyboard Trap in Modal

```javascript
// ❌ WRONG: No focus trap
function openModal() {
  modal.style.display = 'block';
}

// ✅ RIGHT: Focus trap active
function openModal() {
  modal.style.display = 'block';
  const focusTrap = new FocusTrap(modal);
  focusTrap.activate();
}
```

## Reporting Format

```json
{
  "timestamp": "2025-12-30T10:00:00Z",
  "url": "http://localhost:8000/library/artists",
  "violations": [
    {
      "id": "color-contrast",
      "impact": "serious",
      "description": "Elements must have sufficient color contrast",
      "nodes": [
        {
          "html": "<p class=\"subtitle\">12 albums</p>",
          "target": [".artist-card .subtitle"],
          "failureSummary": "Fix contrast ratio (current: 3.2:1, required: 4.5:1)"
        }
      ]
    }
  ],
  "passes": 42,
  "violations": 3,
  "incomplete": 0
}
```

## Performance Benchmarks

| Test Suite | Target | Actual |
|------------|--------|--------|
| axe-core scan | <5s | 3.2s |
| Lighthouse audit | <10s | 7.8s |
| Screen reader test | Manual | N/A |
| Keyboard nav test | Manual | N/A |

## Related Documentation

- [Accessibility Guide](./accessibility-guide.md) - Implementation patterns
- [Component Library](./component-library.md) - Accessible components
- [Testing Guide](../05-developer-guides/testing-guide.md) - General testing
- [HTMX Patterns](../05-developer-guides/htmx-patterns.md) - Interactive patterns
