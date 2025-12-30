# 📋 Code-Validierungs Quick Reference

> **Für die Dokumentations-Migration Phase 3**  
> **Ziel:** Sicherstellen dass ALLE Doku mit echtem Code synchron ist

---

## 🎯 Kritische Regeln

### ❌ VERBOTEN:
- ❌ Dokumentation einfach kopieren ohne Code-Check
- ❌ Pseudo-Code oder "Example Code" in Docs
- ❌ Veraltete Line Numbers
- ❌ Endpoints dokumentieren die nicht existieren
- ❌ Services dokumentieren die nicht implementiert sind

### ✅ PFLICHT:
- ✅ Jedes Code-Beispiel ist ein ECHTER Snippet aus `src/`
- ✅ Jeder dokumentierte Endpoint existiert im Router
- ✅ Jeder dokumentierte Service existiert in `application/services/`
- ✅ Line numbers mit `grep -n` verifiziert
- ✅ "Code Verified: YYYY-MM-DD" Header in jedem Doc

---

## 📚 Validierungs-Workflows

### 1. API Documentation Validation

**Für jede Datei in `03-api-reference/`:**

```bash
# Beispiel: auth.md validieren

# 1. Router-Datei finden
ROUTER="src/soulspot/api/routers/auth.py"

# 2. Alle Endpoints auflisten
grep -n "@router\." "$ROUTER"

# Ausgabe sollte sein:
# 50:@router.get("/authorize")
# 87:@router.get("/callback") 
# 152:@router.get("/session")
# ...

# 3. Mit Dokumentation vergleichen
# In auth.md müssen ALLE diese Endpoints dokumentiert sein!

# 4. Request/Response Models prüfen
grep -n "def.*request\|def.*response\|:.*DTO" "$ROUTER"

# 5. Code-Beispiel extrahieren (echte Zeilen!)
sed -n '50,65p' "$ROUTER"  # Zeilen 50-65 anzeigen
```

**Template für API Doc:**

```markdown
### GET `/api/auth/authorize`

**Purpose:** Initiate Spotify OAuth flow

**Code:**
```python
# src/soulspot/api/routers/auth.py (lines 50-65)
@router.get("/authorize")
async def authorize(
    request: Request,
    settings: AppSettingsService = Depends(get_app_settings_service)
) -> Response:
    """Initiate Spotify OAuth flow."""
    # [EXACT CODE FROM SOURCE - NO MODIFICATIONS!]
\`\`\`
```

### 2. Feature Documentation Validation

**Für jede Datei in `06-features/`:**

```bash
# Beispiel: spotify-sync.md validieren

# 1. Service-Datei finden
SERVICE="src/soulspot/application/services/spotify_sync_service.py"

# 2. Klasse und Methoden auflisten
grep -n "class\|def " "$SERVICE" | head -20

# 3. Beschriebene Features prüfen
# "Auto-sync every 6 hours" → Worker in lifecycle.py?
grep -n "spotify_sync" src/soulspot/infrastructure/lifecycle.py

# 4. Database Models prüfen
grep -n "class SpotifySession" src/soulspot/infrastructure/persistence/models.py

# 5. Use Cases prüfen
ls -la src/soulspot/application/use_cases/ | grep -i spotify
```

**Validation Checklist:**

```markdown
## Spotify Sync Feature

> **Code Verified:** 2025-12-30 ✅

- [x] Service exists: `application/services/spotify_sync_service.py`
- [x] Worker configured: `infrastructure/lifecycle.py` line 234
- [x] Database model: `SpotifySessionModel` in `models.py` line 633
- [x] Use case: `SyncSpotifyPlaylistsUseCase` exists
- [x] Code examples extracted from real source
```

### 3. Architecture Documentation Validation

**Für jede Datei in `04-architecture/`:**

```bash
# Beispiel: data-layer-patterns.md validieren

# 1. Repository Pattern Code finden
grep -n "class.*Repository" src/soulspot/infrastructure/persistence/repositories.py

# 2. Interface Definition prüfen
grep -n "class I.*Repository" src/soulspot/domain/ports/__init__.py

# 3. Code-Beispiel extrahieren
# Für "TrackRepository.add()" Pattern:
sed -n '1350,1380p' src/soulspot/infrastructure/persistence/repositories.py
```

---

## 🛠️ Validation Tools

### Script Usage

```bash
# Gesamte Validierung
./scripts/validate-docs.sh docs-new

# Ausgabe:
# ✅ Router 'auth': 9 endpoints (documented ✓)
# ⚠️  Service 'notification_service' not documented in features/
# ✅ Model 'TrackModel': documented
# ...
```

### Manual Checks

```bash
# 1. Endpoint Count
echo "Code Endpoints:"
grep -r "@router\." src/soulspot/api/routers/*.py | wc -l

echo "Documented Endpoints:"
grep -r "^### \(GET\|POST\|PUT\|DELETE\)" docs-new/03-api-reference/*.md | wc -l

# Should match!

# 2. Service Coverage
echo "Services in code:"
ls src/soulspot/application/services/*.py | grep -v __init__ | wc -l

echo "Services documented:"
grep -r "^## " docs-new/06-features/*.md | grep -i service | wc -l

# 3. Undocumented Endpoints
for router in src/soulspot/api/routers/*.py; do
    echo "=== $(basename $router) ==="
    grep "@router\." "$router" | sed 's/.*@router\.\([a-z]*\)("\([^"]*\)".*/\1 \2/'
done
```

---

## 📊 Validation Checklist per Document

### API Reference Doc Checklist

```markdown
**File:** docs-new/03-api-reference/[name].md

- [ ] Router file path verified (src/soulspot/api/routers/[name].py)
- [ ] All endpoints from router listed
- [ ] No endpoints listed that don't exist in code
- [ ] HTTP methods correct (GET/POST/PUT/DELETE)
- [ ] Path parameters documented match code
- [ ] Request/Response schemas verified against DTOs
- [ ] Code examples are REAL snippets (with line numbers)
- [ ] Error responses documented from actual code
- [ ] Authentication requirements verified
- [ ] Header has "Code Verified: YYYY-MM-DD"
```

### Feature Doc Checklist

```markdown
**File:** docs-new/06-features/[name].md

- [ ] Service file exists (application/services/[name]_service.py)
- [ ] All described methods exist in service class
- [ ] Database models verified (models.py)
- [ ] Worker configuration checked (lifecycle.py)
- [ ] Use cases verified (application/use_cases/)
- [ ] Integration with other services verified
- [ ] Code examples from real source
- [ ] No outdated feature descriptions
- [ ] Header has "Code Verified: YYYY-MM-DD"
```

### Architecture Doc Checklist

```markdown
**File:** docs-new/04-architecture/[name].md

- [ ] All code patterns extracted from real source
- [ ] Repository examples from repositories.py
- [ ] Interface examples from domain/ports/
- [ ] Entity examples from domain/entities/
- [ ] Model examples from models.py
- [ ] DTO examples from infrastructure/plugins/dto.py
- [ ] No pseudo-code or theoretical examples
- [ ] Line numbers accurate
- [ ] Header has "Code Verified: YYYY-MM-DD"
```

---

## 🔍 Common Issues & Solutions

### Issue: Endpoint Count Mismatch

```bash
# Problem: Router has 14 endpoints, doc shows 12

# Solution:
# 1. List all endpoints in router
grep -n "@router\." src/soulspot/api/routers/playlists.py

# 2. Check which are missing in docs
# Add missing endpoints to documentation
```

### Issue: Outdated Code Example

```bash
# Problem: Code example shows deprecated pattern

# Solution:
# 1. Find current implementation
grep -n "def add_track" src/soulspot/infrastructure/persistence/repositories.py

# 2. Extract exact code
sed -n '1350,1380p' src/soulspot/infrastructure/persistence/repositories.py

# 3. Replace in documentation (with line numbers!)
```

### Issue: Service Not Documented

```bash
# Problem: validate-docs.sh shows undocumented service

# Solution:
# 1. Check what service does
head -50 src/soulspot/application/services/notification_service.py

# 2. Create feature doc or add to existing
# docs-new/06-features/notifications.md

# 3. Document all public methods
```

---

## ✅ Quality Gates

**Before marking Phase 3 complete:**

```bash
# 1. Run validation script
./scripts/validate-docs.sh docs-new

# Should show:
# ✅ All validations passed! Documentation is in sync with code.

# 2. Manual spot checks (sample 5 random docs)
# - Open doc
# - Open referenced source file
# - Verify code examples match exactly
# - Verify line numbers are current

# 3. Endpoint coverage check
# Code: 200 endpoints
# Docs: 200 endpoints
# ✅ Match!

# 4. Service coverage check  
# Code: 18 services
# Docs: 18 services documented
# ✅ Match!
```

---

## 🎯 Success Criteria

**Phase 3 is complete when:**

- ✅ `./scripts/validate-docs.sh docs-new` passes with 0 errors
- ✅ All API docs have "Code Verified" header
- ✅ All Feature docs have "Code Verified" header
- ✅ All Architecture docs have "Code Verified" header
- ✅ Random sample of 10 docs verified manually
- ✅ Endpoint count matches exactly (200/200)
- ✅ Service count matches exactly (18/18)
- ✅ No pseudo-code in any documentation
- ✅ All code examples have source file path + line numbers

---

**Remember:** 

> "Documentation that lies is worse than no documentation."  
> — Every Developer Ever

**Daher:** Lieber ein Endpoint weglassen als falsch dokumentieren!
