# Onboarding API Reference

> **Version:** 2.0  
> **Last Updated:** 9. Dezember 2025  
> **Status:** ✅ Active  
> **Related Router:** `src/soulspot/api/routers/onboarding.py`

---

## Overview

The Onboarding API manages the **first-time setup wizard** for SoulSpot. It guides new users through:

1. **Spotify OAuth** - Connect Spotify account
2. **Soulseek Configuration** - Configure slskd download server
3. **Completion** - Mark setup as done

**Key Features:**
- 🎯 **Multi-Step Wizard** - Track progress through setup steps
- 🔌 **Connection Testing** - Validate Soulseek credentials before saving
- 📢 **Dashboard Integration** - Show "Complete Setup" banner if skipped
- 💾 **Persistent State** - Resume onboarding after page reload

---

## Endpoints

### 1. GET `/api/onboarding/status`

**Purpose:** Get current onboarding state (used by dashboard to show setup banner).

**Response:**
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

**Fields:**
- `completed` - Onboarding fully finished
- `skipped` - User skipped some steps
- `current_step` - Current wizard step (1=Spotify, 2=Soulseek, 3=Done)
- `spotify_connected` - Spotify OAuth completed (token exists)
- `soulseek_configured` - Soulseek credentials saved
- `show_banner` - Show "Complete Setup" banner on dashboard

**Logic:**
```python
# show_banner is True when:
show_banner = not completed and skipped
```

**Code Reference:**
```python
# src/soulspot/api/routers/onboarding.py (lines 66-127)
@router.get("/status")
async def get_onboarding_status(
    db: AsyncSession = Depends(get_db_session),
) -> OnboardingStatus:
    """Get current onboarding status."""
    ...
```

---

### 2. POST `/api/onboarding/complete`

**Purpose:** Mark onboarding as complete.

**Request:**
```json
{
  "skipped": false
}
```

**Response:**
```json
{
  "message": "Onboarding completed successfully"
}
```

**Behavior:**
- Sets `onboarding.completed = true` in database
- If `skipped=true`, also sets `onboarding.skipped = true` (triggers dashboard banner)

**Code Reference:**
```python
# src/soulspot/api/routers/onboarding.py (lines 129-173)
@router.post("/complete")
async def complete_onboarding(
    request: OnboardingComplete,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Mark onboarding as complete."""
    ...
```

---

### 3. POST `/api/onboarding/skip`

**Purpose:** Skip onboarding wizard (show reminder banner later).

**Request:** None

**Response:**
```json
{
  "message": "Onboarding skipped - you can complete setup later from Dashboard"
}
```

**Behavior:**
- Sets `onboarding.skipped = true`
- Dashboard will show "Complete Setup" banner
- User can resume setup from dashboard

**Code Reference:**
```python
# src/soulspot/api/routers/onboarding.py (lines 175-206)
@router.post("/skip")
async def skip_onboarding(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Skip onboarding wizard."""
    ...
```

---

### 4. POST `/api/onboarding/test-slskd`

**Purpose:** Test Soulseek (slskd) connection before saving credentials.

**Request:**
```json
{
  "url": "http://localhost:5030",
  "username": "myuser",
  "password": "mypassword",
  "api_key": null
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Successfully connected to slskd",
  "version": "0.21.0",
  "error": null
}
```

**Response (Failure):**
```json
{
  "success": false,
  "message": "Failed to connect to slskd",
  "version": null,
  "error": "Connection refused - is slskd running?"
}
```

**Behavior:**
- Attempts to connect to slskd server
- Returns version number if successful
- Does **NOT** save credentials (use `/save-slskd` endpoint)

**Use Cases:**
- Validate credentials before saving
- Troubleshoot connection issues
- Verify slskd is running

**Code Reference:**
```python
# src/soulspot/api/routers/onboarding.py (lines 208-303)
@router.post("/test-slskd")
async def test_slskd_connection(
    request: SlskdTestRequest,
) -> SlskdTestResponse:
    """Test Soulseek connection."""
    ...
```

---

### 5. POST `/api/onboarding/save-slskd`

**Purpose:** Save Soulseek credentials to database.

**Request:**
```json
{
  "url": "http://localhost:5030",
  "username": "myuser",
  "password": "mypassword",
  "api_key": "optional-api-key"
}
```

**Response:**
```json
{
  "message": "Soulseek configuration saved successfully"
}
```

**Behavior:**
- Saves credentials to database
- Overrides environment variables
- Changes apply immediately (no restart required)

**Security Note:** Credentials are stored in database (not .env file).

**Code Reference:**
```python
# src/soulspot/api/routers/onboarding.py (lines 305-356)
@router.post("/save-slskd")
async def save_slskd_config(
    request: SlskdTestRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Save Soulseek configuration."""
    ...
```

---

## Data Models

### OnboardingStatus

```python
class OnboardingStatus(BaseModel):
    completed: bool              # Onboarding fully completed
    skipped: bool                # User skipped some steps
    current_step: int            # Current wizard step (1-3)
    spotify_connected: bool      # Spotify OAuth done
    soulseek_configured: bool    # Soulseek credentials saved
    show_banner: bool            # Show dashboard banner
```

### SlskdTestRequest

```python
class SlskdTestRequest(BaseModel):
    url: str                     # slskd URL (e.g., http://localhost:5030)
    username: str                # slskd username
    password: str                # slskd password
    api_key: str | None = None   # slskd API key (optional)
```

### SlskdTestResponse

```python
class SlskdTestResponse(BaseModel):
    success: bool                # Connection successful
    message: str                 # Status message
    version: str | None = None   # slskd version if connected
    error: str | None = None     # Error message if failed
```

---

## Workflow Example

```python
import httpx

async def complete_onboarding_flow():
    async with httpx.AsyncClient() as client:
        # 1. Check initial status
        status = await client.get("http://localhost:8000/api/onboarding/status")
        print(f"Current step: {status.json()['current_step']}")
        
        # 2. Test Soulseek connection
        test_result = await client.post(
            "http://localhost:8000/api/onboarding/test-slskd",
            json={
                "url": "http://localhost:5030",
                "username": "myuser",
                "password": "mypassword"
            }
        )
        if not test_result.json()["success"]:
            print(f"Connection failed: {test_result.json()['error']}")
            return
        
        # 3. Save Soulseek config
        await client.post(
            "http://localhost:8000/api/onboarding/save-slskd",
            json={
                "url": "http://localhost:5030",
                "username": "myuser",
                "password": "mypassword"
            }
        )
        
        # 4. Complete onboarding
        await client.post(
            "http://localhost:8000/api/onboarding/complete",
            json={"skipped": False}
        )
        
        print("Onboarding completed!")
```

---

## Summary

**5 Endpoints** for onboarding management:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/onboarding/status` | GET | Get onboarding state |
| `/onboarding/complete` | POST | Mark onboarding as done |
| `/onboarding/skip` | POST | Skip wizard (show banner) |
| `/onboarding/test-slskd` | POST | Test Soulseek connection |
| `/onboarding/save-slskd` | POST | Save Soulseek credentials |

**Wizard Steps:**
1. **Step 1:** Spotify OAuth (handled by `/api/auth/authorize`)
2. **Step 2:** Soulseek Configuration (`/onboarding/test-slskd` + `/onboarding/save-slskd`)
3. **Step 3:** Complete (`/onboarding/complete`)
