# DB-Busy Loading Page Pattern

**Problem:** Wenn die Datenbank busy/locked ist (z.B. große Datenmengen laden), sehen Benutzer Fehlermeldungen statt einer freundlichen Ladeanzeige.

---

## Aktuelle Situation analysiert

### Wie SoulSpot aktuell DB-Errors handelt

1. **Database Retry-Mechanismus** ([database.py#L270](src/soulspot/infrastructure/persistence/database.py#L270)):
   - `session_scope_with_retry()` - versucht bis zu 3x bei "locked"/"busy" Errors
   - Exponentielles Backoff (0.5s → 1s → 2s)
   - Nach 3 Fehlversuchen → `OperationalError` wird geworfen

2. **Exception Handlers** ([exception_handlers.py](src/soulspot/api/exception_handlers.py)):
   - SQLAlchemy `OperationalError` wird NICHT explizit gefangen!
   - Bedeutet: Wird als 500 Internal Server Error zurückgegeben

3. **HTMX Error Handling** ([modern-ui.js](src/soulspot/static/js/modern-ui.js#L187)):
   - `htmx:responseError` Event zeigt Toast-Notification
   - Keine spezielle Behandlung für DB-Busy

---

## Lösungsoptionen

### Option A: DB-Busy Exception Handler + Loading Page (EMPFOHLEN)

**Konzept:** Fange `OperationalError` (database locked/busy) und gib eine spezielle Loading-Page zurück statt Error.

```python
# src/soulspot/api/exception_handlers.py

from sqlalchemy.exc import OperationalError

@app.exception_handler(OperationalError)
async def database_busy_handler(
    request: Request, exc: OperationalError
) -> Response:
    """Handle database busy/locked errors with loading page."""
    error_msg = str(exc).lower()
    
    # Nur für "locked" oder "busy" Errors
    if "locked" in error_msg or "busy" in error_msg:
        logger.warning(
            "Database busy at %s - showing loading page",
            request.url.path,
        )
        
        # HTMX-Request? → Return HTML partial mit Auto-Retry
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                content=render_loading_partial(request.url.path),
                status_code=200,  # 200 damit HTMX den Content swappt!
                headers={
                    "HX-Trigger": "dbBusy",
                    "HX-Retarget": "#main-content",
                    "HX-Reswap": "innerHTML",
                }
            )
        
        # Normale Request? → Full Loading Page
        return templates.TemplateResponse(
            "loading.html",
            {
                "request": request,
                "message": "Datenbank wird aktualisiert...",
                "retry_url": str(request.url),
                "retry_after": 3,
            },
            status_code=503,
            headers={"Retry-After": "3"}
        )
    
    # Andere DB-Errors → Normal 500
    raise exc
```

**Loading Template:**

```html
{# templates/loading.html #}
{% extends "base.html" %}

{% block content %}
<div class="loading-container" style="min-height: 70vh; display: flex; align-items: center; justify-content: center;">
    <div style="text-align: center; max-width: 500px;">
        <!-- Animated Spinner -->
        <div class="loading-spinner lg" style="margin: 0 auto var(--space-6);"></div>
        
        <h2 style="margin-bottom: var(--space-4);">{{ message | default('Lade Daten...') }}</h2>
        
        <p style="color: var(--text-muted); margin-bottom: var(--space-6);">
            Die Datenbank verarbeitet gerade eine große Anfrage.<br>
            Die Seite wird automatisch aktualisiert.
        </p>
        
        <!-- Auto-Refresh via Meta oder JS -->
        <div 
            hx-get="{{ retry_url }}" 
            hx-trigger="load delay:{{ retry_after | default(3) }}s"
            hx-swap="outerHTML"
        >
            <noscript>
                <meta http-equiv="refresh" content="{{ retry_after | default(3) }};url={{ retry_url }}">
            </noscript>
        </div>
        
        <!-- Progress Bar Animation -->
        <div class="progress-bar" style="width: 200px; margin: 0 auto;">
            <div class="progress-bar-fill" style="animation: progress {{ retry_after | default(3) }}s linear;"></div>
        </div>
    </div>
</div>

<style>
@keyframes progress {
    from { width: 0%; }
    to { width: 100%; }
}
</style>
{% endblock %}
```

**HTMX Partial für in-place Loading:**

```html
{# templates/partials/loading_retry.html #}
<div class="db-busy-notice" 
     hx-get="{{ retry_url }}" 
     hx-trigger="load delay:{{ retry_after }}s"
     hx-swap="outerHTML"
     style="padding: var(--space-8); text-align: center;">
    
    <div class="loading-spinner" style="margin: 0 auto var(--space-4);"></div>
    <p style="color: var(--text-muted);">
        Datenbank beschäftigt - wiederhole in {{ retry_after }} Sekunden...
    </p>
</div>
```

---

### Option B: Frontend-Only Lösung (Schneller zu implementieren)

**Konzept:** HTMX Error-Events abfangen und statt Fehler einen Retry-Mechanismus einbauen.

```javascript
// src/soulspot/static/js/modern-ui.js

// DB-Busy Retry Handler
let retryAttempts = {};
const MAX_RETRIES = 5;
const RETRY_DELAYS = [1000, 2000, 3000, 5000, 8000]; // Exponential backoff

document.body.addEventListener('htmx:responseError', function(event) {
    const xhr = event.detail.xhr;
    const target = event.detail.target;
    const path = event.detail.pathInfo.requestPath;
    
    // Check for DB busy (500 error with "locked" or "busy" in response)
    if (xhr.status >= 500) {
        const responseText = xhr.responseText?.toLowerCase() || '';
        
        if (responseText.includes('locked') || responseText.includes('busy') || 
            responseText.includes('operational') || responseText.includes('database')) {
            
            // Initialize retry counter for this path
            if (!retryAttempts[path]) retryAttempts[path] = 0;
            
            if (retryAttempts[path] < MAX_RETRIES) {
                event.preventDefault(); // Don't show error toast!
                
                const delay = RETRY_DELAYS[retryAttempts[path]];
                retryAttempts[path]++;
                
                // Show loading state instead of error
                showLoadingState(target, delay);
                
                // Retry after delay
                setTimeout(() => {
                    htmx.trigger(target, 'htmx:load');
                }, delay);
                
                console.log(`DB busy - retrying ${path} in ${delay}ms (attempt ${retryAttempts[path]})`);
                return;
            }
            
            // Max retries reached - show error
            retryAttempts[path] = 0;
        }
    }
    
    // Normal error handling
    LoadingOverlay.hide(target);
    toastManager.error('Ein Fehler ist aufgetreten. Bitte versuche es später erneut.');
});

function showLoadingState(target, delay) {
    target.innerHTML = `
        <div class="db-busy-notice" style="padding: 2rem; text-align: center;">
            <div class="loading-spinner" style="margin: 0 auto 1rem;"></div>
            <p style="color: var(--text-muted);">
                Datenbank beschäftigt - wiederhole in ${delay/1000} Sekunden...
            </p>
        </div>
    `;
}
```

---

### Option C: Middleware-Lösung (Sauberste Architektur)

**Konzept:** Middleware fängt DB-Errors VOR den Exception-Handlers.

```python
# src/soulspot/infrastructure/observability/middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import OperationalError

class DatabaseBusyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle database busy/locked errors gracefully."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except OperationalError as e:
            error_msg = str(e).lower()
            
            if "locked" in error_msg or "busy" in error_msg:
                logger.warning("Database busy - returning loading response")
                
                if request.headers.get("HX-Request"):
                    # HTMX: Return partial mit auto-retry
                    return HTMLResponse(
                        content=self._render_htmx_loading(request),
                        status_code=200,
                        headers={"HX-Trigger": "dbBusy"}
                    )
                
                # Browser: Redirect to loading page
                return RedirectResponse(
                    url=f"/loading?redirect={request.url.path}",
                    status_code=303
                )
            
            # Re-raise other DB errors
            raise
```

---

## Empfohlene Lösung: Option A (Exception Handler)

### Warum?

| Kriterium | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| Implementierungsaufwand | 🟡 Mittel | 🟢 Niedrig | 🔴 Hoch |
| Server-Side Control | 🟢 Ja | 🔴 Nein | 🟢 Ja |
| Funktioniert ohne JS | 🟢 Ja | 🔴 Nein | 🟢 Ja |
| HTMX-kompatibel | 🟢 Ja | 🟢 Ja | 🟢 Ja |
| Testbarkeit | 🟢 Gut | 🟡 Mittel | 🟡 Mittel |

### Implementierungsschritte

1. **Exception Handler hinzufügen** (30 Min)
   - `OperationalError` Handler in `exception_handlers.py`
   - Unterscheidung HTMX vs. normale Requests

2. **Loading Templates erstellen** (30 Min)
   - `templates/loading.html` (Full Page)
   - `templates/partials/loading_retry.html` (HTMX Partial)

3. **CSS Animations** (15 Min)
   - Progress bar animation
   - Spinner styling

4. **Testing** (30 Min)
   - Simuliere DB-Lock mit `time.sleep` in Route
   - Teste HTMX und normale Requests

---

## Bezüglich Worker-Abhängigkeit

**Frage:** "geht es nicht weil webui auch über worker aufgebaut wird?"

**Antwort:** Die WebUI ist NICHT abhängig von Workern für das Rendering!

- **WebUI (API Routes):** Rendern Templates direkt aus der Datenbank
- **Workers:** Laufen im Hintergrund (Spotify Sync, Downloads, etc.)
- **Problem:** Wenn Workers die DB stark belasten, können API-Anfragen "locked" werden

Die Loading-Page-Lösung funktioniert, weil:
1. Der Exception Handler VOR dem Template-Rendering greift
2. Die Loading-Page selbst keine DB-Queries braucht
3. Der Auto-Retry später erfolgt, wenn die DB frei ist

**Architektur-Diagramm:**

```
Browser Request
      │
      ▼
┌─────────────────────┐
│  FastAPI Router     │
│  (API Route)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌─────────────────────┐
│  Database Session   │◄────│  Background Worker  │
│  (SELECT/INSERT)    │     │  (Spotify Sync)     │
└──────────┬──────────┘     └─────────────────────┘
           │                         │
           │ 🔒 DB LOCKED!           │
           │                         │
           ▼                         │
┌─────────────────────┐              │
│  OperationalError   │◄─────────────┘
│  "database locked"  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Exception Handler  │ ◄── NEUER CODE
│  → Loading Page     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  templates/         │ ◄── Kein DB-Zugriff!
│  loading.html       │
└─────────────────────┘
```

---

## Quick Implementation (Minimal)

Falls du eine schnelle Lösung willst, hier der minimale Code:

```python
# In exception_handlers.py, füge hinzu:

from sqlalchemy.exc import OperationalError
from fastapi.responses import HTMLResponse

@app.exception_handler(OperationalError)
async def database_error_handler(
    request: Request, exc: OperationalError
) -> Response:
    """Handle SQLAlchemy operational errors."""
    error_msg = str(exc).lower()
    
    # DB busy/locked → Loading page statt Error
    if "locked" in error_msg or "busy" in error_msg:
        logger.warning("Database busy at %s", request.url.path)
        
        retry_html = f'''
        <div style="text-align:center; padding:4rem;">
            <div style="width:40px;height:40px;border:3px solid #333;border-top-color:#fe4155;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 1rem;"></div>
            <h2>Datenbank beschäftigt</h2>
            <p style="color:#888;">Seite wird automatisch neu geladen...</p>
            <style>@keyframes spin{{to{{transform:rotate(360deg)}}}}</style>
        </div>
        <script>setTimeout(()=>location.reload(), 3000)</script>
        '''
        
        if request.headers.get("HX-Request"):
            return HTMLResponse(content=retry_html, status_code=200)
        
        # Wrap in basic HTML for non-HTMX requests
        full_html = f'''<!DOCTYPE html>
        <html><head><title>Loading...</title></head>
        <body style="background:#0f0f0f;color:#fff;font-family:system-ui;">
        {retry_html}
        </body></html>'''
        
        return HTMLResponse(content=full_html, status_code=503)
    
    # Other DB errors → 500
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error occurred"}
    )
```

---

**Dokument erstellt:** 2025-01-04  
**Status:** Ready for implementation
