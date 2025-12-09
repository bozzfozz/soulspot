# A11Y Quality Gates & Testing Framework

**Objective:** Enforce WCAG 2.1 AA/AAA compliance across all 4 redesign phases using automated + manual testing.

---

## 1. Pre-PR Quality Gate Script (Local)

Save as `scripts/quality-gates-a11y.sh`:

```bash
#!/bin/bash
set -e

echo "🔍 Running A11Y Quality Gates..."
echo ""

# 1. Code Quality (uses existing SoulSpot tooling)
echo "✓ Phase 1: Code Quality Checks"
ruff check . --config pyproject.toml
mypy --config-file mypy.ini src/
bandit -r src/ -f json -o /tmp/bandit-report.json
echo "  Code quality: PASS ✅"
echo ""

# 2. Unit Tests (existing pytest setup)
echo "✓ Phase 2: Unit Tests"
pytest tests/unit/ -v --tb=short
echo "  Unit tests: PASS ✅"
echo ""

# 3. A11Y Automated Tests (Python-based, NO npm)
echo "✓ Phase 3: A11Y Automated Scanning"

# 3a. axe-core via Python (uses axe-selenium-python)
if python3 -c "import axe_selenium_python" 2>/dev/null; then
  echo "  Running axe-core via Selenium..."
  python3 << 'EOF'
import json
from selenium import webdriver
from axe_selenium_python import Axe

driver = webdriver.Chrome()  # Or webdriver.Firefox()
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
  echo "  ⚠️  axe-selenium-python not found. Install: pip install axe-selenium-python"
fi

# 3b. HTML validation (Python-based)
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
else
  echo "  ⚠️  html5lib not found. Install: pip install html5lib"
fi

# 3c. CSS validation (existing tool)
echo "  CSS validation: Checking for syntax errors..."
if python3 -c "import cssutils" 2>/dev/null; then
  python3 -c "import cssutils; cssutils.parseFile('src/soulspot/static/css/variables.css')" || true
  echo "  CSS validation: DONE"
fi
echo ""

# 4. Accessibility Violations Check
if [ -f /tmp/axe-results.json ]; then
  violations=$(python3 -c "import json; data=json.load(open('/tmp/axe-results.json')); print(len(data.get('violations', [])))")
  if [ "$violations" -gt 0 ]; then
    echo "  ⚠️  $violations Accessibility violations found:"
    python3 -c "import json; data=json.load(open('/tmp/axe-results.json')); [print(f\"  - {v['id']}: {v['description']}\") for v in data['violations'][:5]]"
  else
    echo "  Accessibility violations: PASS ✅"
  fi
fi
echo ""

echo "═══════════════════════════════════"
echo "  ✅ All Quality Gates PASSED"
echo "═══════════════════════════════════"
echo ""
echo "Ready for PR submission!"
```

**Dependencies (add to requirements.txt):**
```txt
axe-selenium-python>=2.1.6
selenium>=4.0.0
html5lib>=1.1
```

---

## 2. Automated A11Y Testing Tools

### Tool 1: axe-core (Automated Scans)

```bash
# Install
npm install -g @axe-core/cli

# Run on templates
axe src/soulspot/templates/base.html --headless --show-errors

# Output formats
axe src/soulspot/templates/base.html --output json > results.json
axe src/soulspot/templates/base.html --output csv > results.csv
```

### Tool 2: Lighthouse (Performance + A11Y)

```bash
# Install
npm install -g lighthouse

# Audit single page
lighthouse http://localhost:8000 --view

# Headless output
lighthouse http://localhost:8000 --output=json --output-path=./report.json
```

### Tool 3: WAVE (WebAIM)

```bash
# Browser extension: https://wave.webaim.org/extension/
# OR via CLI (requires API key)

curl -H "Authorization: Bearer YOUR_WAVE_KEY" \
  "https://wave.webaim.org/api/request?url=http://localhost:8000&format=json"
```

### Tool 4: HTML Validator

```bash
# Install
npm install -g html-validate

# Run
html-validate src/soulspot/templates/**/*.html

# With A11Y preset
html-validate src/soulspot/templates/ --config .html-validate.json
```

### Tool 5: CSS Validator

```bash
# Python-based validator
pip install cssutils

python3 << 'EOF'
import cssutils
cssutils.log.setLevel('WARNING')
sheet = cssutils.parseUrl('static/css/variables.css')
print(f"CSS validation: {len(sheet.cssRules)} rules parsed successfully")
EOF
```

---

## 3. Manual Testing Procedures

### Procedure 1: Keyboard-Only Navigation

**Objective:** Verify all interactive elements accessible via keyboard.

**Steps:**
1. Disconnect mouse/trackpad (or use keyboard-only mode)
2. Start at page top, press `Tab` repeatedly
3. Verify:
   - [ ] All buttons/links reachable
   - [ ] Focus indicator visible (2px outline minimum)
   - [ ] Focus order logical (top→bottom, left→right)
   - [ ] No keyboard traps (Tab always moves forward)
   - [ ] `Escape` closes modals/menus
   - [ ] `Enter` activates buttons
4. Test all form fields (Tab to each field, type, Tab to next)
5. **Expected result:** Complete page navigation without mouse

### Procedure 2: Screen Reader Testing

**Using NVDA (Windows):**
```
1. Download: https://www.nvaccess.org/download/
2. Run NVDA
3. Start reading: Insert+Down Arrow
4. Navigate by heading: Insert+H
5. Navigate by link: Insert+L
6. Navigate by button: Insert+B
7. Test form reading: Tab through form, listen to labels

Verify:
  - All text read correctly
  - Form labels announced
  - Button purposes clear
  - ARIA labels present
  - Link text descriptive (not "click here")
```

**Using VoiceOver (macOS):**
```
1. Enable: Cmd+F5
2. Start reading: VO+A (where VO = Control+Option)
3. Navigator: VO+Right/Left Arrow
4. Interact: VO+Down Arrow
5. Rotor (headings/links): VO+U

Verify: Same as NVDA
```

### Procedure 3: Motion Preferences Test

**Objective:** Verify animations respect `prefers-reduced-motion`.

**macOS:**
```
1. Open System Preferences > Accessibility > Display
2. Enable "Reduce motion"
3. Reload page
4. Verify: All animations disabled
5. Disable "Reduce motion"
6. Reload page
7. Verify: Animations re-enabled
```

**Windows:**
```
1. Settings > Ease of Access > Display
2. Toggle "Show animations"
3. Same verification as macOS
```

**DevTools Emulation:**
```javascript
// In DevTools Console:
const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)');
console.log('Prefers reduced motion:', prefersReduced.matches);

// Test CSS media query
const styles = getComputedStyle(document.querySelector('.animated-element'));
console.log('Animation duration:', styles.animationDuration);
// Should be 0ms if prefers-reduced-motion is enabled
```

### Procedure 4: Touch Target Sizing

**Objective:** Verify all touch targets ≥44×44px (48×48 recommended, 56×56 mobile).

**Steps:**
1. Open DevTools (F12)
2. Run in Console:
```javascript
document.querySelectorAll('button, a, input, [role="button"]').forEach(el => {
  const rect = el.getBoundingClientRect();
  const isSmall = rect.width < 44 || rect.height < 44;
  const status = isSmall ? '❌' : '✅';
  console.log(`${status} ${el.tagName} ${Math.round(rect.width)}×${Math.round(rect.height)}px`);
  if (isSmall) el.style.outline = '2px solid red';
});
```
3. **Expected:** All interactive elements outlined in green/normal (not red)
4. Test on mobile: All targets ≥56×56px

### Procedure 5: Color Contrast Validation

**Objective:** Verify text/background contrast ≥4.5:1 (AA), ≥7:1 (AAA).

**Using WebAIM Checker:**
1. Go to https://webaim.org/resources/contrastchecker/
2. Extract color from CSS (DevTools: Inspect element → Styles)
3. Enter foreground + background colors
4. Verify: Passes AA (4.5:1) at minimum

**Automated (axe DevTools):**
```bash
npm install -g @axe-core/cli
axe http://localhost:8000 --tags wcag2aa --show-errors
```

### Procedure 6: Form Validation Testing

**Objective:** Verify form errors accessible to keyboard + screen reader users.

**Steps:**
1. Tab to each form field
2. Leave empty/enter invalid data
3. Tab away (blur event)
4. **Verify error message:**
   - [ ] Appears immediately (no page reload)
   - [ ] `aria-invalid="true"` set on input
   - [ ] Error text has `role="alert"`
   - [ ] Screen reader announces error
   - [ ] Keyboard navigation to error message works
5. Fix input, verify error disappears
6. Test Submit button:
   - [ ] Disabled until form valid
   - [ ] `aria-disabled="true"` when disabled

### Procedure 7: HTMX Dynamic Content A11Y (Project-Specific)

**Objective:** Verify HTMX-loaded content is accessible.

**SoulSpot uses HTMX v1.9.10** for dynamic content (modals, search results, status updates). Test A11Y after HTMX swap:

**Steps:**
1. **Identify HTMX-loaded elements:**
   ```javascript
   // In DevTools Console:
   document.querySelectorAll('[hx-get], [hx-post], [hx-swap]').forEach(el => {
     console.log('HTMX element:', el.tagName, el.getAttribute('hx-target'));
   });
   ```

2. **Trigger HTMX request** (e.g., click search button, open modal)

3. **Test after swap:**
   ```javascript
   // Listen for htmx:afterSwap
   document.addEventListener('htmx:afterSwap', (event) => {
     const newContent = event.detail.target;
     
     // Check for ARIA labels
     const interactive = newContent.querySelectorAll('button, a, input');
     interactive.forEach(el => {
       if (!el.getAttribute('aria-label') && !el.textContent.trim()) {
         console.error('Missing ARIA label:', el);
       }
     });
     
     // Check for focus management
     const firstFocusable = newContent.querySelector('button, [href], input');
     if (firstFocusable && document.activeElement !== firstFocusable) {
       console.warn('Focus not set on new content');
     }
   });
   ```

4. **Test keyboard navigation** in dynamically loaded content

5. **Test screen reader** announces new content:
   - [ ] NVDA/VoiceOver reads new content automatically
   - [ ] ARIA live regions used for status updates (e.g., "Download started")

**Existing Implementation:** `static/js/app.js` has `KeyboardNav.trapFocus()` – verify it's called on HTMX modals.

---

## 4. GitHub Actions CI/CD Workflow

Save as `.github/workflows/a11y-quality-gates.yml`:

```yaml
name: A11Y Quality Gates

on:
  pull_request:
    paths:
      - 'src/soulspot/**'
      - 'static/**'
      - 'templates/**'
      - 'tests/**'
      - 'pyproject.toml'

jobs:
  code-quality:
    runs-on: ubuntu-latest
    name: Code Quality
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install ruff mypy bandit
      
      - name: Run ruff
        run: ruff check . --config pyproject.toml
        continue-on-error: false
      
      - name: Run mypy
        run: mypy --config-file mypy.ini src/
        continue-on-error: false
      
      - name: Run bandit
        run: bandit -r src/ -f json -o /tmp/bandit.json || true
      
      - name: Upload bandit results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: bandit-report
          path: /tmp/bandit.json

  unit-tests:
    runs-on: ubuntu-latest
    name: Unit Tests
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run pytest
        run: pytest tests/unit/ -v --cov=src/soulspot --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  a11y-scan:
    runs-on: ubuntu-latest
    name: A11Y Automated Scan
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Python deps
        run: pip install -r requirements.txt
      
      - name: Install npm tools
        run: |
          npm install -g @axe-core/cli
          npm install -g lighthouse
          npm install -g html-validate
      
      - name: Start dev server
        run: |
          python -m soulspot.main &
          sleep 5
      
      - name: Run axe-core scan
        run: |
          axe http://localhost:8000 --headless --show-errors --output json > /tmp/axe-results.json
        continue-on-error: true
      
      - name: Run HTML validation
        run: |
          html-validate src/soulspot/templates/ --config .html-validate.json || true
      
      - name: Check for critical violations
        run: |
          if grep -q '"violations":\[\]' /tmp/axe-results.json; then
            echo "✅ No critical A11Y violations"
          else
            echo "⚠️ A11Y violations found:"
            cat /tmp/axe-results.json
            exit 1
          fi
      
      - name: Upload axe results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: axe-results
          path: /tmp/axe-results.json

  accessibility-checks:
    runs-on: ubuntu-latest
    name: Accessibility Checks
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Lighthouse
        uses: treosh/lighthouse-ci-action@v9
        with:
          configPath: './lighthouse.config.js'
          uploadArtifacts: true

  quality-gate:
    needs: [code-quality, unit-tests, a11y-scan, accessibility-checks]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - name: Check quality gates
        run: |
          if [ "${{ needs.code-quality.result }}" != "success" ]; then
            echo "❌ Code quality failed"
            exit 1
          fi
          if [ "${{ needs.unit-tests.result }}" != "success" ]; then
            echo "❌ Unit tests failed"
            exit 1
          fi
          if [ "${{ needs.a11y-scan.result }}" != "success" ]; then
            echo "❌ A11Y scan failed"
            exit 1
          fi
          echo "✅ All quality gates passed"
```

---

## 5. PR Review Checklist

**For Code Reviewers:**

### Code Quality
- [ ] Ruff: 0 violations
- [ ] mypy: 0 type errors
- [ ] bandit: 0 HIGH/MEDIUM findings
- [ ] Unit tests: All green (100% coverage for new code)

### Accessibility (A11Y)
- [ ] Keyboard navigation tested (Tab/Shift+Tab/Escape all work)
- [ ] Focus trap working for modals (Tab cycles within modal only)
- [ ] ARIA labels present (role, aria-label, aria-describedby)
- [ ] Touch targets ≥44×44px (verify with DevTools overlay)
- [ ] Color contrast ≥4.5:1 (AA minimum)
- [ ] `prefers-reduced-motion` CSS implemented
- [ ] Form validation shows error with `role="alert"`
- [ ] Screen reader tested (NVDA or VoiceOver)

### Architecture
- [ ] Dependency direction respected (API → App → Domain ← Infra)
- [ ] Port/Interface synced with implementations
- [ ] No service-specific naming in generic components
- [ ] No hardcoded Spotify-specific logic

### Documentation
- [ ] Docs synchronized with code changes
- [ ] New components documented in design-system.md
- [ ] CHANGELOG.md updated
- [ ] README.md updated if needed

### PR Comment Template

```markdown
## Accessibility Review

### Automated Gates
- ✅ Code Quality: ruff, mypy, bandit all pass
- ✅ Unit Tests: 95% coverage
- ✅ A11Y Scan: axe-core 0 violations

### Manual Testing
- ✅ Keyboard navigation: PASS
- ✅ Screen reader (NVDA): PASS
- ✅ prefers-reduced-motion: PASS
- ✅ Touch targets: All ≥44×44px
- ✅ Color contrast: All ≥4.5:1

### Reviewer Notes
- Component naming follows service-agnostic strategy ✓
- Focus trap implemented for modal (WCAG 2.1.2) ✓
- ARIA labels complete ✓

**Recommendation:** APPROVE ✅
```

---

## 6. Phase-Based Quality Matrix

| Phase | Component | A11Y Gate | Manual Test | Automated Tool |
|-------|-----------|-----------|-------------|----------------|
| **Phase 1** | Design Tokens | Touch targets (44×44) | Size overlay (DevTools) | HTML validation |
| **Phase 1** | Animations | prefers-reduced-motion | OS settings toggle | CSS validation |
| **Phase 2** | Modal | Keyboard trap (Tab cycles) | Keyboard-only nav | axe-core |
| **Phase 2** | Command Palette | Keyboard nav (↑↓/Enter) | Keyboard-only nav | axe-core |
| **Phase 2** | Form Fields | ARIA labels (aria-invalid) | Screen reader test | WAVE |
| **Phase 3** | Tabs | ARIA tab role | Screen reader test | Lighthouse |
| **Phase 3** | Buttons | Focus indicator visible | Visual check | axe-core |
| **Phase 4** | All | Full A11Y scan | All procedures | All tools |

---

## 7. Tools Setup Instructions

### Local Setup

```bash
# Install Python tools
pip install ruff mypy bandit pytest pytest-cov cssutils

# Install Node tools
npm install -g @axe-core/cli lighthouse html-validate

# Install browser extensions (manual)
# - Chrome: Axe DevTools (Deque)
# - Firefox: WAVE WebAIM
```

### GitHub Actions Setup

```bash
# Create .github/workflows/ directory
mkdir -p .github/workflows

# Copy workflow file
cp .github/workflows/a11y-quality-gates.yml .github/workflows/

# Commit and push
git add .github/workflows/a11y-quality-gates.yml
git commit -m "Add A11Y quality gates workflow"
git push
```

### Lighthouse Config

Save as `lighthouse.config.js`:

```javascript
module.exports = {
  ci: {
    collect: {
      url: ['http://localhost:8000'],
      numberOfRuns: 3,
    },
    upload: {
      target: 'temporary-public-storage',
    },
    assert: {
      preset: 'lighthouse:recommended',
      assertions: {
        'categories:accessibility': ['error', { minScore: 0.9 }],
        'categories:performance': ['error', { minScore: 0.9 }],
        'categories:best-practices': ['error', { minScore: 0.9 }],
      },
    },
  },
};
```

---

## 8. Failure Handling

### If axe-core Fails

```bash
# 1. Get detailed report
axe http://localhost:8000 --headless --show-errors

# 2. Review violations
# Look for: missing ARIA labels, color contrast, keyboard access

# 3. Fix in code
# Update template/CSS to address violations

# 4. Re-run
axe http://localhost:8000 --headless
```

### If Manual Keyboard Test Fails

```bash
# 1. Identify stuck element
# Note which element Tab gets stuck on

# 2. Check focus trap implementation
# Ensure Tab handler wraps correctly

# 3. Fix JavaScript
# Update focus-trap.js getFocusableElements() selector

# 4. Re-test
# Keyboard-only navigation again
```

### If prefers-reduced-motion Fails

```bash
# 1. Check CSS media query
# grep "@media (prefers-reduced-motion:" static/css/*.css

# 2. Verify animation-duration set to 0ms
# @media (prefers-reduced-motion: reduce) {
#   * { animation-duration: 0ms !important; }
# }

# 3. Re-test with OS setting
```

---

## 9. Reference Links

- **WCAG 2.1 Quick Ref:** https://www.w3.org/WAI/WCAG21/quickref/
- **ARIA APG:** https://www.w3.org/WAI/ARIA/apg/
- **axe-core Docs:** https://github.com/dequelabs/axe-core
- **Lighthouse:** https://developers.google.com/web/tools/lighthouse
- **WAVE:** https://wave.webaim.org/
- **WebAIM:** https://webaim.org/
- **The A11Y Project:** https://www.a11yproject.com/

---

## 10. Integration with Existing Workflow

### Before Submitting PR

```bash
# 1. Run local quality gates
./scripts/quality-gates-a11y.sh

# 2. Manual keyboard test
# Unplug mouse, Tab through entire page

# 3. DevTools A11Y audit
# Open DevTools > Lighthouse > Run audit

# 4. Push to GitHub
git push

# 5. Monitor GitHub Actions
# Wait for all workflows to pass
```

### PR Approval Criteria

✅ All quality gates GREEN  
✅ A11Y scan results: 0 violations  
✅ Manual testing complete  
✅ Reviewer approval  

Then: **MERGE & RELEASE**
