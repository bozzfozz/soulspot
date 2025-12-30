# Onboarding API

**Base Path**: `/onboarding`

**Purpose**: First-time setup wizard for Spotify OAuth and Soulseek configuration. Multi-step flow with skip functionality and dashboard banner integration.

**Critical Context**: Onboarding tracks completion state in database (`onboarding.completed`, `onboarding.skipped`) to control dashboard banner visibility. Settings stored in DB (NOT `.env` files).

---

## Endpoints Overview (5 endpoints)

- `GET /onboarding/status` - Get current onboarding state + step
- `POST /onboarding/complete` - Mark onboarding as complete
- `POST /onboarding/skip` - Skip onboarding temporarily (shows dashboard banner)
- `POST /onboarding/test-slskd` - Test Soulseek connection (NO save)
- `POST /onboarding/save-slskd` - Save Soulseek credentials to database

---

## Onboarding Flow

### Multi-Step Wizard

**Steps**:
1. **Spotify OAuth** - Connect Spotify account
2. **Soulseek Config** - Configure slskd connection
3. **Done** - Mark onboarding complete

**State Restoration**: Onboarding page checks `GET /status` on load to restore current step.

**Skip Functionality**:
- User clicks "Not Now" → Sets `onboarding.skipped=true`
- Dashboard shows "Complete Setup" banner
- User can resume later from Settings

---

## Endpoints

### 1. Get Onboarding Status

**Endpoint**: `GET /onboarding/status`

**Purpose**: Retrieve current onboarding state (used by Dashboard and Onboarding page).

**Use Cases**:
- Dashboard: Decide whether to show "Complete Setup" banner
- Onboarding page: Restore wizard step on page reload

**Response**:
```json
{
  "completed": false,
  "skipped": true,
  "current_step": 2,
  "spotify_connected": true,
  "soulseek_configured": false,
  "show_banner": true
}
```

**Fields**:
- `completed` (boolean): Onboarding fully completed
- `skipped` (boolean): User skipped some steps
- `current_step` (int): Current wizard step (1=Spotify, 2=Soulseek, 3=Done)
- `spotify_connected` (boolean): Spotify OAuth token exists in database
- `soulseek_configured` (boolean): Soulseek URL + (API Key OR Username/Password) set
- `show_banner` (boolean): Dashboard should show "Complete Setup" banner (`!completed && skipped`)

**Step Determination Logic**:
```python
if completed:
    current_step = 3  # Done
elif spotify_connected and soulseek_configured:
    current_step = 3  # Ready to complete
elif spotify_connected:
    current_step = 2  # Soulseek step
else:
    current_step = 1  # Spotify step
```

**Soulseek Configuration Check**:
```python
# Requires: URL set + (API Key OR Username/Password)
soulseek_url_set = bool(slskd_creds.url and slskd_creds.url.strip())
soulseek_auth_set = bool(slskd_creds.api_key) or (
    bool(slskd_creds.username) and bool(slskd_creds.password)
)
soulseek_configured = soulseek_url_set and soulseek_auth_set
```

**Source**: `onboarding.py:69-128`

---

### 2. Complete Onboarding

**Endpoint**: `POST /onboarding/complete`

**Purpose**: Mark onboarding as finished (sets `onboarding.completed=true`).

**Request Body**:
```json
{
  "skipped": false
}
```

**Parameters**:
- `skipped` (boolean, default false): Whether user skipped some steps

**Behavior**:
- Sets `onboarding.completed=true` in database
- If `skipped=true`, also sets `onboarding.skipped=true` (enables dashboard banner)
- Commits changes to database

**Response**:
```json
{
  "success": true,
  "message": "Onboarding completed",
  "skipped": false
}
```

**Use Case**: User clicks "Finish" after completing all steps OR manually completes later from Settings.

**Source**: `onboarding.py:133-169`

---

### 3. Skip Onboarding

**Endpoint**: `POST /onboarding/skip`

**Purpose**: Skip onboarding temporarily (user can resume later).

**Behavior**:
- Sets `onboarding.skipped=true` in database
- **Does NOT** set `onboarding.completed` (user can continue later)
- Dashboard shows "Complete Setup" banner on next visit

**Response**:
```json
{
  "success": true,
  "message": "Onboarding skipped. You can complete setup later in Settings."
}
```

**Use Case**: User clicks "Not Now" button to postpone setup.

**Source**: `onboarding.py:174-195`

---

### 4. Test Soulseek Connection

**Endpoint**: `POST /onboarding/test-slskd`

**Purpose**: Test slskd connection **BEFORE** saving credentials.

**Request Body**:
```json
{
  "url": "http://localhost:5030",
  "username": "user",
  "password": "pass",
  "api_key": null
}
```

**Authentication Methods**:
- **Prefer API Key**: If `api_key` provided, uses `X-API-Key` header
- **Fallback**: Basic auth with `username`/`password`

**Behavior**:
- Hits slskd `/api/v0/application` endpoint to verify connection
- Returns version info if successful
- **IMPORTANT**: Does NOT save credentials - only tests them!

**Response** (Success):
```json
{
  "success": true,
  "message": "Verbindung erfolgreich! slskd Version: 0.18.1",
  "version": "0.18.1",
  "error": null
}
```

**Response** (Failure - Auth):
```json
{
  "success": false,
  "message": "Authentifizierung fehlgeschlagen",
  "version": null,
  "error": "Ungültiger API-Key oder Benutzername/Passwort"
}
```

**Response** (Failure - Connection):
```json
{
  "success": false,
  "message": "Verbindung fehlgeschlagen",
  "version": null,
  "error": "Kann nicht zu http://localhost:5030 verbinden. Ist slskd gestartet?"
}
```

**HTTP Status Codes Handled**:
- `200 OK`: Successful connection
- `401 Unauthorized`: Invalid API key or username/password
- `403 Forbidden`: API key/user lacks permissions
- `ConnectError`: Server unreachable
- `TimeoutException`: Server not responding

**slskd API Version**: Uses `/api/v0/application` (current slskd API version).

**Source**: `onboarding.py:202-285`

---

### 5. Save Soulseek Credentials

**Endpoint**: `POST /onboarding/save-slskd`

**Purpose**: Save Soulseek credentials to database (after successful test).

**Request Body**: Same as test endpoint:
```json
{
  "url": "http://localhost:5030",
  "username": "user",
  "password": "pass",
  "api_key": "optional-key"
}
```

**Behavior**:
- Saves credentials to `app_settings` table
- **NOT** `.env` file - database-first configuration
- Loaded on app startup
- Changes take effect immediately (no restart required)

**Response**:
```json
{
  "success": true,
  "message": "Soulseek-Einstellungen gespeichert"
}
```

**Database Keys**:
- `slskd.url`
- `slskd.username`
- `slskd.password`
- `slskd.api_key` (if provided)

**Source**: `onboarding.py:291-329`

---

## Architecture Notes

### Database-First Configuration

**Critical Design**: Credentials stored in database, NOT `.env` files.

**Rationale**: Allows user to change credentials without server restart (runtime updates).

**Storage**: `app_settings` table with key-value pairs.

**Loading**: `AppSettingsService` loads from DB at runtime.

---

### Dashboard Banner Integration

**Banner Display Logic**:
```python
# Dashboard checks:
status = await get_onboarding_status()
if status.show_banner:
    # Show "Complete Setup" banner with link to /onboarding
```

**Banner Triggers**:
- `onboarding.skipped=true` AND `onboarding.completed=false`

**Dismissing Banner**:
- User completes onboarding → `onboarding.completed=true` → banner disappears
- User dismisses banner → UI sets `onboarding.skipped=false` (optional UX improvement)

---

### Wizard State Restoration

**Flow**:
1. User starts onboarding
2. User navigates away (accidentally or intentionally)
3. User returns to `/onboarding`
4. Page calls `GET /onboarding/status` → `current_step` determines where to resume

**Example**:
```javascript
// Onboarding page loads
const status = await fetch('/api/onboarding/status').then(r => r.json());
if (status.current_step === 2) {
  // Skip Spotify step (already connected), show Soulseek step
  navigateToStep(2);
}
```

---

## Testing Workflow

### Recommended Flow

1. **Step 1: Spotify OAuth**
   - User clicks "Connect Spotify" button
   - Redirects to `/api/auth/spotify/authorize` (OAuth flow)
   - After success, returns to onboarding page
   - Page calls `GET /onboarding/status` → `spotify_connected=true`
   - Wizard advances to Step 2

2. **Step 2: Soulseek Config**
   - User enters slskd URL + credentials
   - User clicks "Test Connection"
   - Frontend calls `POST /onboarding/test-slskd`
   - If success (`success=true`), enable "Save" button
   - User clicks "Save"
   - Frontend calls `POST /onboarding/save-slskd`
   - Wizard advances to Step 3

3. **Step 3: Complete**
   - User clicks "Finish"
   - Frontend calls `POST /onboarding/complete` with `skipped=false`
   - Redirects to Dashboard

**Skip Flow**:
- User clicks "Not Now" at any step
- Frontend calls `POST /onboarding/skip`
- Redirects to Dashboard
- Dashboard shows "Complete Setup" banner

---

## Security Considerations

### Credential Storage

**Database Security**:
- Credentials stored in `app_settings` table (plaintext - **security improvement TODO**)
- Recommendation: Encrypt `slskd.password` and `slskd.api_key` at rest

**Transport Security**:
- Test endpoint sends credentials in request body → **Use HTTPS in production!**

**Credential Masking**:
- Settings API masks passwords with `"***"` in responses
- Onboarding API does NOT mask (only returns success/failure, no credential echo)

---

### Test Endpoint Abuse

**Issue**: `POST /onboarding/test-slskd` could be abused for credential brute-forcing.

**Mitigations**:
1. Rate limiting (implement via middleware)
2. IP-based throttling (max 5 attempts per 5 minutes)
3. CAPTCHA for repeated failures

**Current State**: No rate limiting implemented (TODO).

---

## Error Handling

### Test Connection Errors

**HTTP Errors**:
- `401 Unauthorized`: Wrong API key or username/password
- `403 Forbidden`: Correct credentials but insufficient permissions
- `ConnectError`: Server unreachable (slskd not running or wrong URL)
- `TimeoutException`: Server not responding (firewall/network issue)

**User-Friendly Messages**:
```python
if response.status_code == 401:
    return SlskdTestResponse(
        success=False,
        message="Authentifizierung fehlgeschlagen",
        error="Ungültiger API-Key oder Benutzername/Passwort",
    )
```

---

## Common Pitfalls

### 1. Forgetting to Test Before Save

**Wrong Flow**:
```
User enters credentials → Clicks "Save" → Connection fails → Bad UX
```

**Right Flow**:
```
User enters credentials → Clicks "Test" → Success → Clicks "Save"
```

**UI Recommendation**: Disable "Save" button until test succeeds.

---

### 2. Mixing .env and DB Credentials

**Wrong**:
```python
# Load from .env
from soulspot.config.settings import get_settings
url = get_settings().slskd.url  # Ignores DB-stored URL!
```

**Right**:
```python
# Load from DB
settings_service = AppSettingsService(session)
url = await settings_service.get_string("slskd.url")
```

---

### 3. Not Checking Current Step

**Issue**: User refreshes page mid-onboarding → starts from Step 1 again (confusing UX).

**Solution**: Always call `GET /onboarding/status` on page load to restore correct step.

---

## Related Documentation

- **Settings API**: `docs-new/03-api-reference/settings.md`
- **Auth Flow**: `docs-new/03-api-reference/auth.md`
- **Configuration**: `docs/architecture/CONFIGURATION.md`
- **Database**: `docs/architecture/DATA_LAYER_PATTERNS.md`

---

**Validation Status**: ✅ All 5 endpoints validated against source code (329 lines analyzed)
