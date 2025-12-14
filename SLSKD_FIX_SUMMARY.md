# SLSKD URL Protocol Error Fix - Summary

## Problem Statement

The SoulSpot application was failing to start properly with the following error:

```
11:00:51 │ ERROR   │ soulspot.application.workers.download_status_sync_worker:200 │ Sync cycle failed: Request URL is missing an 'http://' or 'https://' protocol.
```

This error occurred when:
1. The Docker container started without SLSKD environment variables configured
2. Background workers tried to initialize the SLSKD client
3. The client attempted to make HTTP requests with an empty or invalid URL

## Root Cause Analysis

The issue was in `src/soulspot/infrastructure/lifecycle.py` line 237:

```python
# OLD CODE (BROKEN)
slskd_client = SlskdClient(settings.slskd)  # Uses env vars directly
```

This approach had two problems:

1. **No URL Validation**: `SlskdClient.__init__()` didn't validate the URL before creating the httpx client
2. **Environment-Only Configuration**: Workers used environment variables directly instead of the database-first approach used by API endpoints

When SLSKD environment variables weren't set (common in Docker deployments), the URL would be empty or use the default `http://localhost:5030`, which might not be accessible from the container.

## Solution Implemented

### 1. URL Validation in SlskdClient

Added validation in `SlskdClient.__init__()` to catch configuration issues early:

```python
# NEW CODE
def __init__(self, settings: SlskdSettings) -> None:
    """Initialize slskd client with URL validation."""
    self.settings = settings
    
    # Validate URL has protocol before httpx tries to use it
    url = settings.url.strip()
    if not url:
        raise ValueError(
            "slskd URL is empty. Please configure slskd.url in Settings or "
            "set SLSKD_URL environment variable."
        )
    if not url.startswith(("http://", "https://")):
        raise ValueError(
            f"slskd URL '{url}' is missing http:// or https:// protocol. "
            "Please use a valid URL like 'http://localhost:5030'"
        )
    
    self.base_url = url.rstrip("/")
    self._client: httpx.AsyncClient | None = None
```

**Benefits**:
- Clear error messages guide users to fix configuration
- Fails fast at initialization, not during request
- Prevents cryptic httpx protocol errors

### 2. Database-First Credential Loading

Updated `lifecycle.py` to use the same pattern as API endpoints:

```python
# NEW CODE (FIXED)
from soulspot.application.services.credentials_service import CredentialsService
from soulspot.config.settings import SlskdSettings

# Load credentials from DB with env fallback
async with db.session_scope() as creds_session:
    creds_service = CredentialsService(
        session=creds_session,
        fallback_settings=settings,  # Enable env fallback for migration
    )
    slskd_creds = await creds_service.get_slskd_credentials()

# Create SlskdSettings from credentials
slskd_settings = SlskdSettings(
    url=slskd_creds.url,
    username=slskd_creds.username or "admin",
    password=slskd_creds.password or "changeme",
    api_key=slskd_creds.api_key,
)

# Try to create slskd client - may fail if URL is invalid
try:
    slskd_client = SlskdClient(slskd_settings)
    app.state.slskd_client = slskd_client
    
    if slskd_creds.is_configured():
        logger.info("slskd client initialized: %s", slskd_creds.url)
    else:
        logger.warning(
            "slskd credentials not fully configured - download features will be disabled"
        )
except ValueError as e:
    logger.warning(
        "slskd client initialization failed: %s - download features will be disabled",
        e,
    )
    app.state.slskd_client = None
```

**Benefits**:
- Consistent credential loading across app (DB-first, then env fallback)
- Graceful degradation when SLSKD not configured
- Clear logging to guide troubleshooting

### 3. Conditional Worker Initialization

Updated worker initialization to skip SLSKD-dependent workers when client is unavailable:

```python
# NEW CODE (GRACEFUL)
if slskd_client is not None:
    download_monitor_worker = DownloadMonitorWorker(
        job_queue=job_queue,
        slskd_client=slskd_client,
        poll_interval_seconds=10,
    )
    await download_monitor_worker.start()
    app.state.download_monitor_worker = download_monitor_worker
    logger.info("Download monitor worker started (polls every 10s)")
else:
    logger.warning("Download monitor worker skipped - slskd client not available")
    app.state.download_monitor_worker = None
```

Workers affected:
- `DownloadWorker` - Handles download jobs
- `DownloadMonitorWorker` - Tracks download progress
- `QueueDispatcherWorker` - Dispatches waiting downloads
- `DownloadStatusSyncWorker` - Syncs status from slskd to DB

**Benefits**:
- App starts successfully even without SLSKD configured
- Download-related features are disabled but app remains functional
- Easy to enable downloads later by configuring SLSKD via Settings UI

### 4. Shutdown Safety

Added None checks in shutdown handlers:

```python
# Stop download monitor worker
if hasattr(app.state, "download_monitor_worker") and app.state.download_monitor_worker is not None:
    try:
        logger.info("Stopping download monitor worker...")
        await app.state.download_monitor_worker.stop()
        logger.info("Download monitor worker stopped")
    except Exception as e:
        logger.exception("Error stopping download monitor worker: %s", e)
```

**Benefits**:
- Prevents AttributeError during shutdown when workers weren't started
- Graceful cleanup regardless of startup state

## Testing

### Unit Tests Added

Added comprehensive tests for URL validation in `tests/unit/infrastructure/integrations/test_slskd_client.py`:

```python
def test_init_rejects_empty_url(self) -> None:
    """Test that empty URL raises ValueError."""
    settings = SlskdSettings(url="", username="testuser", password="testpass")
    with pytest.raises(ValueError, match="slskd URL is empty"):
        SlskdClient(settings)

def test_init_rejects_url_without_protocol(self) -> None:
    """Test that URL without http:// or https:// raises ValueError."""
    settings = SlskdSettings(url="localhost:5030", username="testuser", password="testpass")
    with pytest.raises(ValueError, match="missing http:// or https:// protocol"):
        SlskdClient(settings)

def test_init_accepts_https_url(self) -> None:
    """Test that https:// URLs are accepted."""
    settings = SlskdSettings(url="https://slskd.example.com:5030", username="testuser", password="testpass")
    client = SlskdClient(settings)
    assert client.base_url == "https://slskd.example.com:5030"
```

**Test Results**: All 5 initialization tests pass ✅

### Manual Validation

Verified the fix handles all scenarios correctly:

```python
# Test 1: Empty URL
✓ Correctly raised ValueError: slskd URL is empty. Please configure slskd.url in Settings or set SLSKD_URL environment variable.

# Test 2: URL without protocol
✓ Correctly raised ValueError: slskd URL 'localhost:5030' is missing http:// or https:// protocol. Please use a valid URL like 'http://localhost:5030'

# Test 3: Valid URL
✓ Successfully created client with base_url: http://localhost:5030
```

## Impact & Benefits

### Before Fix
- ❌ App failed to start with cryptic "missing protocol" error
- ❌ No clear guidance on how to fix the issue
- ❌ Workers crashed continuously, filling logs with errors
- ❌ Inconsistent credential loading (env-only vs DB-first)

### After Fix
- ✅ App starts successfully even without SLSKD configured
- ✅ Clear warning messages guide users to configure SLSKD
- ✅ Workers gracefully skip initialization with explicit logging
- ✅ Consistent credential loading pattern across entire app
- ✅ Download features can be enabled later via Settings UI
- ✅ No error spam in logs

## Configuration Workflow

### For Users

**Option 1: Database Configuration (Recommended)**
1. Start app without SLSKD env vars
2. Navigate to Settings UI
3. Configure SLSKD URL, API key/credentials
4. Restart app or configure via Settings API
5. Workers automatically use DB credentials

**Option 2: Environment Variables (Legacy)**
1. Set environment variables:
   ```bash
   SLSKD_URL=http://localhost:5030
   SLSKD_API_KEY=your-api-key
   # OR
   SLSKD_USERNAME=admin
   SLSKD_PASSWORD=your-password
   ```
2. Start app
3. CredentialsService falls back to env vars if DB empty

**Option 3: Mixed Approach**
- Use env vars for initial setup
- Override via Settings UI for runtime changes
- DB values take precedence over env vars

## Related Issues

### HTTP/2 Warnings (Separate Issue)
The logs also showed warnings about missing `h2` package:
```
WARNING: Using http2=True, but the 'h2' package is not installed. Make sure to install httpx using `pip install httpx[http2]`.
```

This is a **non-blocking warning** caused by:
- `http_pool.py` enables HTTP/2 by default (`http2=True`)
- The `h2` package is not in `requirements.txt`

**Solution** (optional optimization):
```bash
# Update requirements.txt
httpx[http2]>=0.28.0
```

**Impact**: HTTP/2 provides better performance for APIs that support it, but app works fine with HTTP/1.1.

## Files Changed

1. `src/soulspot/infrastructure/integrations/slskd_client.py`
   - Added URL validation in `__init__()`
   - Updated docstrings

2. `src/soulspot/infrastructure/lifecycle.py`
   - Changed to DB-first credential loading via `CredentialsService`
   - Added graceful error handling for SlskdClient creation
   - Added conditional worker initialization based on client availability
   - Added None checks in shutdown handlers

3. `tests/unit/infrastructure/integrations/test_slskd_client.py`
   - Added 3 new tests for URL validation
   - All tests pass

## Migration Path

For existing deployments:

1. **No Breaking Changes**: Environment variables still work via fallback
2. **Gradual Migration**: Users can migrate to DB config at their own pace
3. **Clear Warnings**: App logs guide users to configure SLSKD
4. **Graceful Degradation**: App remains functional without SLSKD

## Future Improvements

1. **Health Check**: Add `/health` endpoint that reports SLSKD availability
2. **Dynamic Reconnection**: Allow enabling SLSKD at runtime without restart
3. **Configuration Wizard**: Add UI onboarding flow for first-time setup
4. **HTTP/2 Optimization**: Add `httpx[http2]` to requirements for better performance
5. **Credential Validation**: Add test connection before saving to DB

## Conclusion

This fix resolves the startup failure by:
1. Adding clear validation and error messages
2. Implementing graceful degradation when SLSKD unavailable
3. Aligning credential loading with the rest of the app
4. Ensuring safe shutdown regardless of startup state

The app now starts successfully in all scenarios and provides clear guidance for configuration.
