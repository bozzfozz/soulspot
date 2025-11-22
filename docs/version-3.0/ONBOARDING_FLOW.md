# Onboarding Flow - Version 3.0

## Overview

Version 3.0 **completely removes .env configuration** and replaces it with a **guided, interactive onboarding flow**. All critical credentials (Spotify, Soulseek, etc.) are collected through the UI with **real-time connection testing** to ensure everything works before proceeding.

## Design Philosophy

**Core Principles:**
- **Zero configuration files**: No .env editing required
- **Guided experience**: Step-by-step wizard with clear instructions
- **Instant validation**: Test connections immediately as credentials are entered
- **Clear feedback**: Explicit success/error messages with actionable guidance
- **Progressive disclosure**: Only show what's needed when it's needed
- **Recoverable**: Can skip optional modules, reconfigure later

**User Experience Goals:**
- First-time user can get system running in &lt;5 minutes
- Clear explanation of what each credential is and how to get it
- Visual confirmation when connections succeed
- Helpful error messages when connections fail
- Easy to reconfigure after initial setup

---

## Onboarding Steps

### Step 0: Welcome Screen

**Purpose**: Introduce the system and set expectations.

**UI:**
```
┌─────────────────────────────────────────────────────────┐
│                  Welcome to SoulSpot Bridge             │
│                                                         │
│  🎵 A modular music bridge connecting Spotify,         │
│      Soulseek, and your local library.                  │
│                                                         │
│  This wizard will guide you through connecting:        │
│  • Spotify (for playlist syncing)                       │
│  • Soulseek (for downloading)                           │
│  • MusicBrainz (for metadata enrichment)                │
│                                                         │
│  ⏱️  Estimated time: 5 minutes                          │
│                                                         │
│  [Get Started] [Skip Setup]                             │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
```html
<div class="onboarding">
  <div class="onboarding__container">
    <div class="card card--onboarding">
      <div class="card__body text-center">
        <h1>Welcome to SoulSpot Bridge</h1>
        
        <div class="onboarding__hero">
          <svg class="onboarding__icon"><!-- music icon --></svg>
          <p class="text-lg">
            A modular music bridge connecting Spotify, Soulseek, 
            and your local library.
          </p>
        </div>
        
        <div class="onboarding__checklist">
          <p>This wizard will guide you through connecting:</p>
          <ul>
            <li>• Spotify (for playlist syncing)</li>
            <li>• Soulseek (for downloading)</li>
            <li>• MusicBrainz (for metadata enrichment)</li>
          </ul>
        </div>
        
        <div class="onboarding__estimate">
          <span class="badge badge--info">⏱️ Estimated time: 5 minutes</span>
        </div>
      </div>
      
      <div class="card__footer">
        <button class="btn btn--ghost" 
                hx-get="/onboarding/skip">
          Skip Setup
        </button>
        <button class="btn btn--primary btn--lg"
                hx-get="/onboarding/step/1"
                hx-target="#onboarding-container"
                hx-swap="innerHTML">
          Get Started
        </button>
      </div>
    </div>
  </div>
  
  <div class="onboarding__progress">
    <div class="progress-steps">
      <div class="progress-step progress-step--active">Welcome</div>
      <div class="progress-step">Spotify</div>
      <div class="progress-step">Soulseek</div>
      <div class="progress-step">Optional</div>
      <div class="progress-step">Complete</div>
    </div>
  </div>
</div>
```

---

### Step 1: Spotify Configuration

**Purpose**: Collect and test Spotify API credentials.

**UI:**
```
┌─────────────────────────────────────────────────────────┐
│  Step 1 of 4: Connect Spotify                          │
│                                                         │
│  🎧 Spotify lets you sync your playlists and discover  │
│     new music.                                          │
│                                                         │
│  ─────────────────────────────────────────────────     │
│                                                         │
│  Client ID *                                            │
│  ┌─────────────────────────────────────────────────┐  │
│  │ abc123...                                        │  │
│  └─────────────────────────────────────────────────┘  │
│  💡 Get this from Spotify Developer Dashboard          │
│     [How to get credentials?]                           │
│                                                         │
│  Client Secret *                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │ ••••••••••••••••                                │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  ✅ Connection successful! Found 42 playlists.         │
│                                                         │
│  [Back] [Test Connection] [Next]                        │
└─────────────────────────────────────────────────────────┘
```

**States:**
1. **Initial**: Empty form, "Test Connection" disabled
2. **Filled**: Both fields filled, "Test Connection" enabled
3. **Testing**: Spinner showing, buttons disabled
4. **Success**: Green checkmark, success message, "Next" enabled
5. **Error**: Red X, error message with help text, retry enabled

**Implementation:**
```html
<div class="card card--onboarding">
  <div class="card__header">
    <h2>Step 1 of 4: Connect Spotify</h2>
    <div class="step-indicator">1/4</div>
  </div>
  
  <div class="card__body">
    <div class="onboarding__info">
      <div class="info-box">
        <span class="info-box__icon">🎧</span>
        <p>Spotify lets you sync your playlists and discover new music.</p>
      </div>
    </div>
    
    <form id="spotify-config-form"
          hx-post="/api/onboarding/spotify/test"
          hx-target="#spotify-result"
          hx-indicator="#spotify-spinner">
      
      <div class="form-group">
        <label for="spotify-client-id" class="form-label">
          Client ID <span class="required">*</span>
        </label>
        <input type="text" 
               id="spotify-client-id"
               name="client_id"
               class="input"
               placeholder="abc123..."
               required
               hx-on::input="updateTestButtonState()">
        
        <div class="form-hint">
          <span class="hint-icon">💡</span>
          Get this from 
          <a href="https://developer.spotify.com/dashboard" 
             target="_blank" 
             class="link">
            Spotify Developer Dashboard
          </a>
          <button type="button" 
                  class="btn btn--link btn--sm"
                  hx-get="/onboarding/help/spotify-credentials"
                  hx-target="#help-modal">
            How to get credentials?
          </button>
        </div>
      </div>
      
      <div class="form-group">
        <label for="spotify-client-secret" class="form-label">
          Client Secret <span class="required">*</span>
        </label>
        <input type="password" 
               id="spotify-client-secret"
               name="client_secret"
               class="input"
               placeholder="••••••••••••••••"
               required
               hx-on::input="updateTestButtonState()">
      </div>
      
      <div id="spotify-result" class="onboarding__result">
        <!-- Connection test results appear here -->
      </div>
      
      <div id="spotify-spinner" class="htmx-indicator">
        <div class="spinner"></div>
        <p>Testing connection...</p>
      </div>
    </form>
  </div>
  
  <div class="card__footer">
    <button class="btn btn--ghost"
            hx-get="/onboarding/step/0"
            hx-target="#onboarding-container">
      Back
    </button>
    
    <button type="button" 
            id="test-spotify-btn"
            class="btn btn--secondary"
            disabled
            hx-post="/api/onboarding/spotify/test"
            hx-include="#spotify-config-form"
            hx-target="#spotify-result">
      Test Connection
    </button>
    
    <button id="next-spotify-btn"
            class="btn btn--primary"
            disabled
            hx-get="/onboarding/step/2"
            hx-target="#onboarding-container">
      Next
    </button>
  </div>
</div>
```

**Backend Endpoint:**
```python
@router.post("/api/onboarding/spotify/test")
async def test_spotify_connection(
    client_id: str = Form(...),
    client_secret: str = Form(...),
    db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """
    Test Spotify connection and save credentials if successful.
    
    Returns HTMX partial with result (success/error message).
    """
    try:
        # Test connection
        spotify_client = SpotifyClient(client_id, client_secret)
        user_profile = await spotify_client.get_user_profile()
        playlists = await spotify_client.get_user_playlists()
        
        # Save credentials to database (encrypted)
        await save_module_config(
            db=db,
            module_name="spotify",
            config={
                "client_id": client_id,
                "client_secret": encrypt(client_secret),
                "enabled": True
            }
        )
        
        # Return success partial
        return HTMLResponse(f"""
            <div class="alert alert--success">
                <div class="alert__icon">✅</div>
                <div class="alert__content">
                    <h4>Connection successful!</h4>
                    <p>Connected as <strong>{user_profile.display_name}</strong></p>
                    <p>Found {len(playlists)} playlists</p>
                </div>
            </div>
            <script>
                document.getElementById('next-spotify-btn').disabled = false;
            </script>
        """)
        
    except SpotifyAuthError as e:
        return HTMLResponse(f"""
            <div class="alert alert--error">
                <div class="alert__icon">❌</div>
                <div class="alert__content">
                    <h4>Connection failed</h4>
                    <p>{str(e)}</p>
                    <details class="alert__details">
                        <summary>Troubleshooting</summary>
                        <ul>
                            <li>Verify credentials are correct</li>
                            <li>Check that redirect URI is configured</li>
                            <li>Ensure app is not in development mode restrictions</li>
                        </ul>
                    </details>
                </div>
            </div>
        """)
```

**Help Modal (How to get credentials):**
```html
<div class="modal" id="help-modal">
  <div class="modal__backdrop"></div>
  <div class="card modal__content">
    <div class="card__header">
      <h3>How to get Spotify credentials</h3>
      <button class="card__close">×</button>
    </div>
    
    <div class="card__body">
      <ol class="help-steps">
        <li>
          <strong>Go to Spotify Developer Dashboard</strong>
          <a href="https://developer.spotify.com/dashboard" target="_blank">
            https://developer.spotify.com/dashboard
          </a>
        </li>
        <li>
          <strong>Create a new app</strong>
          <ul>
            <li>Click "Create app"</li>
            <li>Name: "SoulSpot Bridge"</li>
            <li>Description: "Personal music bridge"</li>
          </ul>
        </li>
        <li>
          <strong>Configure Redirect URI</strong>
          <ul>
            <li>Go to app settings</li>
            <li>Add redirect URI: <code>http://localhost:8765/callback</code></li>
          </ul>
        </li>
        <li>
          <strong>Copy credentials</strong>
          <ul>
            <li>Client ID: visible on dashboard</li>
            <li>Client Secret: click "Show Client Secret"</li>
          </ul>
        </li>
      </ol>
      
      <div class="help-video">
        <img src="/static/img/spotify-credentials-guide.png" 
             alt="Spotify credentials guide">
      </div>
    </div>
  </div>
</div>
```

---

### Step 2: Soulseek Configuration

**Purpose**: Collect and test Soulseek (slskd) connection details.

**UI:**
```
┌─────────────────────────────────────────────────────────┐
│  Step 2 of 4: Connect Soulseek                         │
│                                                         │
│  📥 Soulseek enables downloading music from the        │
│     peer-to-peer network.                               │
│                                                         │
│  ─────────────────────────────────────────────────     │
│                                                         │
│  slskd Server URL *                                     │
│  ┌─────────────────────────────────────────────────┐  │
│  │ http://localhost:5030                            │  │
│  └─────────────────────────────────────────────────┘  │
│  💡 Default: http://localhost:5030                      │
│                                                         │
│  API Key (if enabled)                                   │
│  ┌─────────────────────────────────────────────────┐  │
│  │ optional_api_key                                 │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  OR                                                     │
│                                                         │
│  Username                                               │
│  ┌─────────────────────────────────────────────────┐  │
│  │ your_username                                    │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  Password                                               │
│  ┌─────────────────────────────────────────────────┐  │
│  │ ••••••••••                                       │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  ✅ Connected! slskd v0.19.5 running.                  │
│     Username: your_username (logged in)                 │
│                                                         │
│  [Back] [Test Connection] [Next]                        │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
```html
<div class="card card--onboarding">
  <div class="card__header">
    <h2>Step 2 of 4: Connect Soulseek</h2>
    <div class="step-indicator">2/4</div>
  </div>
  
  <div class="card__body">
    <div class="onboarding__info">
      <div class="info-box">
        <span class="info-box__icon">📥</span>
        <p>Soulseek enables downloading music from the peer-to-peer network.</p>
      </div>
    </div>
    
    <form id="soulseek-config-form">
      <div class="form-group">
        <label for="slskd-url" class="form-label">
          slskd Server URL <span class="required">*</span>
        </label>
        <input type="url" 
               id="slskd-url"
               name="slskd_url"
               class="input"
               value="http://localhost:5030"
               placeholder="http://localhost:5030"
               required>
        
        <div class="form-hint">
          <span class="hint-icon">💡</span>
          Default: <code>http://localhost:5030</code>
          <button type="button" 
                  class="btn btn--link btn--sm"
                  hx-get="/onboarding/help/slskd-setup"
                  hx-target="#help-modal">
            How to set up slskd?
          </button>
        </div>
      </div>
      
      <div class="form-group">
        <label for="slskd-api-key" class="form-label">
          API Key (if enabled)
        </label>
        <input type="text" 
               id="slskd-api-key"
               name="api_key"
               class="input"
               placeholder="optional_api_key">
      </div>
      
      <div class="form-divider">
        <span>OR</span>
      </div>
      
      <div class="form-group">
        <label for="slskd-username" class="form-label">
          Username
        </label>
        <input type="text" 
               id="slskd-username"
               name="username"
               class="input"
               placeholder="your_username">
      </div>
      
      <div class="form-group">
        <label for="slskd-password" class="form-label">
          Password
        </label>
        <input type="password" 
               id="slskd-password"
               name="password"
               class="input"
               placeholder="••••••••••">
      </div>
      
      <div id="soulseek-result" class="onboarding__result"></div>
    </form>
  </div>
  
  <div class="card__footer">
    <button class="btn btn--ghost"
            hx-get="/onboarding/step/1"
            hx-target="#onboarding-container">
      Back
    </button>
    
    <button type="button" 
            class="btn btn--secondary"
            hx-post="/api/onboarding/soulseek/test"
            hx-include="#soulseek-config-form"
            hx-target="#soulseek-result">
      Test Connection
    </button>
    
    <button id="next-soulseek-btn"
            class="btn btn--primary"
            disabled
            hx-get="/onboarding/step/3"
            hx-target="#onboarding-container">
      Next
    </button>
  </div>
</div>
```

**Backend Endpoint:**
```python
@router.post("/api/onboarding/soulseek/test")
async def test_soulseek_connection(
    slskd_url: str = Form(...),
    api_key: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """Test slskd connection and save credentials if successful."""
    try:
        # Create client with credentials
        client = SlskdClient(
            base_url=slskd_url,
            api_key=api_key,
            username=username,
            password=password
        )
        
        # Test connection
        server_info = await client.get_server_info()
        session_info = await client.get_session()
        
        # Save configuration
        await save_module_config(
            db=db,
            module_name="soulseek",
            config={
                "slskd_url": slskd_url,
                "api_key": encrypt(api_key) if api_key else None,
                "username": username,
                "password": encrypt(password) if password else None,
                "enabled": True
            }
        )
        
        # Return success
        return HTMLResponse(f"""
            <div class="alert alert--success">
                <div class="alert__icon">✅</div>
                <div class="alert__content">
                    <h4>Connected!</h4>
                    <p>slskd {server_info.version} running</p>
                    <p>Username: <strong>{session_info.username}</strong> 
                       ({session_info.state})</p>
                </div>
            </div>
            <script>
                document.getElementById('next-soulseek-btn').disabled = false;
            </script>
        """)
        
    except Exception as e:
        return HTMLResponse(f"""
            <div class="alert alert--error">
                <div class="alert__icon">❌</div>
                <div class="alert__content">
                    <h4>Connection failed</h4>
                    <p>{str(e)}</p>
                    <details class="alert__details">
                        <summary>Troubleshooting</summary>
                        <ul>
                            <li>Ensure slskd is running on {slskd_url}</li>
                            <li>Check firewall settings</li>
                            <li>Verify credentials if authentication enabled</li>
                        </ul>
                    </details>
                </div>
            </div>
        """)
```

---

### Step 3: Optional Modules

**Purpose**: Configure optional enhancements (MusicBrainz, Last.fm, etc.).

**UI:**
```
┌─────────────────────────────────────────────────────────┐
│  Step 3 of 4: Optional Modules                         │
│                                                         │
│  These modules enhance your experience but are          │
│  optional. You can skip and configure later.            │
│                                                         │
│  ─────────────────────────────────────────────────     │
│                                                         │
│  ☑️ MusicBrainz (Metadata enrichment)                  │
│     No configuration needed - uses public API           │
│     [Enable]                                            │
│                                                         │
│  ☐ Last.fm (Scrobbling)                                │
│     API Key: ┌──────────────────────────┐             │
│              │                           │             │
│              └──────────────────────────┘             │
│     [Enable]                                            │
│                                                         │
│  ☐ Notifications (Desktop/email alerts)                │
│     Email: ┌────────────────────────────┐             │
│            │ user@example.com            │             │
│            └────────────────────────────┘             │
│     [Enable]                                            │
│                                                         │
│  [Back] [Skip All] [Next]                               │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
```html
<div class="card card--onboarding">
  <div class="card__header">
    <h2>Step 3 of 4: Optional Modules</h2>
    <div class="step-indicator">3/4</div>
  </div>
  
  <div class="card__body">
    <p class="text-muted">
      These modules enhance your experience but are optional. 
      You can skip and configure later.
    </p>
    
    <div class="module-options">
      <!-- MusicBrainz -->
      <div class="module-option">
        <div class="module-option__header">
          <input type="checkbox" 
                 id="enable-musicbrainz"
                 checked>
          <label for="enable-musicbrainz">
            <strong>MusicBrainz</strong>
            <span class="badge badge--info">Recommended</span>
          </label>
        </div>
        <p class="module-option__description">
          Enriches tracks with accurate metadata (artist, album, year, etc.)
        </p>
        <div class="module-option__config">
          <p class="text-sm text-success">
            ✓ No configuration needed - uses public API
          </p>
        </div>
      </div>
      
      <!-- Last.fm -->
      <div class="module-option">
        <div class="module-option__header">
          <input type="checkbox" 
                 id="enable-lastfm"
                 hx-on::change="toggleLastfmConfig()">
          <label for="enable-lastfm">
            <strong>Last.fm</strong>
          </label>
        </div>
        <p class="module-option__description">
          Scrobble your listening history and get recommendations
        </p>
        <div id="lastfm-config" class="module-option__config" hidden>
          <div class="form-group">
            <label for="lastfm-api-key">API Key</label>
            <input type="text" 
                   id="lastfm-api-key"
                   name="lastfm_api_key"
                   class="input">
            <a href="https://www.last.fm/api/account/create" 
               target="_blank"
               class="form-hint">
              Get API key →
            </a>
          </div>
        </div>
      </div>
      
      <!-- Notifications -->
      <div class="module-option">
        <div class="module-option__header">
          <input type="checkbox" 
                 id="enable-notifications"
                 hx-on::change="toggleNotificationsConfig()">
          <label for="enable-notifications">
            <strong>Notifications</strong>
          </label>
        </div>
        <p class="module-option__description">
          Get alerts for completed downloads and errors
        </p>
        <div id="notifications-config" class="module-option__config" hidden>
          <div class="form-group">
            <label for="notification-email">Email</label>
            <input type="email" 
                   id="notification-email"
                   name="notification_email"
                   class="input"
                   placeholder="user@example.com">
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <div class="card__footer">
    <button class="btn btn--ghost"
            hx-get="/onboarding/step/2"
            hx-target="#onboarding-container">
      Back
    </button>
    
    <button class="btn btn--ghost"
            hx-post="/api/onboarding/optional/skip"
            hx-target="#onboarding-container">
      Skip All
    </button>
    
    <button class="btn btn--primary"
            hx-post="/api/onboarding/optional/save"
            hx-include=".module-option__config"
            hx-target="#onboarding-container">
      Next
    </button>
  </div>
</div>
```

---

### Step 4: Complete & Summary

**Purpose**: Confirm setup and provide next steps.

**UI:**
```
┌─────────────────────────────────────────────────────────┐
│  🎉 Setup Complete!                                     │
│                                                         │
│  Your SoulSpot Bridge is ready to use.                 │
│                                                         │
│  ─────────────────────────────────────────────────     │
│                                                         │
│  ✅ Connected Modules:                                 │
│     • Spotify (42 playlists)                            │
│     • Soulseek (v0.19.5)                                │
│     • MusicBrainz                                       │
│                                                         │
│  📋 Next Steps:                                         │
│     1. Sync your first playlist                         │
│     2. Search and download tracks                       │
│     3. Explore your library                             │
│                                                         │
│  [Go to Dashboard]                                      │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
```html
<div class="card card--onboarding card--success">
  <div class="card__body text-center">
    <div class="onboarding__celebration">
      <svg class="celebration__icon">🎉</svg>
      <h1>Setup Complete!</h1>
      <p class="text-lg">Your SoulSpot Bridge is ready to use.</p>
    </div>
    
    <div class="onboarding__summary">
      <h3>✅ Connected Modules:</h3>
      <ul class="module-summary">
        <li>
          <span class="module-icon">🎧</span>
          <strong>Spotify</strong>
          <span class="text-muted">(42 playlists)</span>
        </li>
        <li>
          <span class="module-icon">📥</span>
          <strong>Soulseek</strong>
          <span class="text-muted">(v0.19.5)</span>
        </li>
        <li>
          <span class="module-icon">📊</span>
          <strong>MusicBrainz</strong>
        </li>
      </ul>
    </div>
    
    <div class="onboarding__next-steps">
      <h3>📋 Next Steps:</h3>
      <ol>
        <li>Sync your first playlist</li>
        <li>Search and download tracks</li>
        <li>Explore your library</li>
      </ol>
    </div>
  </div>
  
  <div class="card__footer">
    <button class="btn btn--primary btn--lg"
            hx-get="/dashboard"
            hx-push-url="true">
      Go to Dashboard
    </button>
  </div>
</div>
```

---

## Credential Storage

**Security Requirements:**

1. **Encryption**: All secrets encrypted at rest using Fernet (symmetric encryption)
2. **Database Storage**: Credentials stored in `module_configurations` table
3. **No .env files**: Never write credentials to disk as plaintext
4. **Runtime Loading**: Decrypt on module initialization
5. **Audit Trail**: Log all credential access attempts

**Database Schema:**
```sql
CREATE TABLE module_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_name VARCHAR(100) NOT NULL,
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT NOT NULL,  -- Encrypted if sensitive
    is_sensitive BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(module_name, config_key)
);
```

**Backend Implementation:**
```python
from cryptography.fernet import Fernet
from sqlalchemy import select

class ConfigurationService:
    """Secure configuration management for modules."""
    
    def __init__(self, db: AsyncSession, encryption_key: str):
        self.db = db
        self.fernet = Fernet(encryption_key.encode())
    
    async def save_config(
        self,
        module_name: str,
        config: dict[str, Any],
        sensitive_keys: list[str]
    ) -> None:
        """Save module configuration with encryption for sensitive values."""
        for key, value in config.items():
            is_sensitive = key in sensitive_keys
            
            # Encrypt sensitive values
            if is_sensitive and value:
                value = self.fernet.encrypt(str(value).encode()).decode()
            
            # Upsert configuration
            stmt = insert(ModuleConfiguration).values(
                module_name=module_name,
                config_key=key,
                config_value=value,
                is_sensitive=is_sensitive
            ).on_conflict_do_update(
                index_elements=["module_name", "config_key"],
                set_={"config_value": value, "updated_at": func.now()}
            )
            await self.db.execute(stmt)
        
        await self.db.commit()
    
    async def get_config(
        self,
        module_name: str,
        decrypt: bool = True
    ) -> dict[str, Any]:
        """Retrieve module configuration with optional decryption."""
        stmt = select(ModuleConfiguration).where(
            ModuleConfiguration.module_name == module_name
        )
        result = await self.db.execute(stmt)
        configs = result.scalars().all()
        
        config_dict = {}
        for config in configs:
            value = config.config_value
            
            # Decrypt if needed
            if decrypt and config.is_sensitive:
                value = self.fernet.decrypt(value.encode()).decode()
            
            config_dict[config.config_key] = value
        
        return config_dict
```

---

## Reconfiguration Flow

**Purpose**: Allow users to reconfigure modules after initial setup.

**Access:**
- Settings page: `/settings/modules`
- Per-module: `/settings/modules/{module_name}`
- Quick action: Module status card → "Configure"

**UI:**
```html
<div class="card card--form">
  <div class="card__header">
    <h3>Reconfigure Spotify</h3>
    <span class="badge badge--success">Currently Active</span>
  </div>
  
  <div class="card__body">
    <div class="alert alert--warning">
      <div class="alert__icon">⚠️</div>
      <div class="alert__content">
        <p>Changing credentials will disconnect existing sessions.</p>
      </div>
    </div>
    
    <form hx-post="/api/modules/spotify/reconfigure">
      <!-- Same form fields as onboarding -->
      
      <div class="form-actions">
        <button type="button" class="btn btn--secondary"
                hx-post="/api/modules/spotify/test"
                hx-include="closest form">
          Test New Credentials
        </button>
        <button type="submit" class="btn btn--primary">
          Save Changes
        </button>
      </div>
    </form>
  </div>
</div>
```

---

## Migration from .env

**For Existing Users:**

1. **Auto-detect .env**: On first startup of v3.0, check for existing `.env`
2. **Import wizard**: Offer to import credentials from `.env`
3. **Delete .env**: After successful import, offer to delete `.env`
4. **Backup**: Create encrypted backup before deletion

**Implementation:**
```python
@router.get("/api/onboarding/migrate")
async def migrate_from_env(db: AsyncSession):
    """Detect and import credentials from .env file."""
    env_path = Path(".env")
    
    if not env_path.exists():
        return {"status": "no_migration_needed"}
    
    # Parse .env
    env_vars = dotenv_values(env_path)
    
    # Map to new configuration
    migrations = {
        "spotify": {
            "client_id": env_vars.get("SPOTIFY_CLIENT_ID"),
            "client_secret": env_vars.get("SPOTIFY_CLIENT_SECRET"),
        },
        "soulseek": {
            "slskd_url": env_vars.get("SLSKD_URL"),
            "api_key": env_vars.get("SLSKD_API_KEY"),
            "username": env_vars.get("SLSKD_USERNAME"),
            "password": env_vars.get("SLSKD_PASSWORD"),
        }
    }
    
    # Save to database
    config_service = ConfigurationService(db, get_encryption_key())
    for module, config in migrations.items():
        await config_service.save_config(
            module_name=module,
            config={k: v for k, v in config.items() if v},
            sensitive_keys=["client_secret", "api_key", "password"]
        )
    
    # Create backup
    backup_path = env_path.with_suffix(".env.backup")
    shutil.copy(env_path, backup_path)
    
    return {
        "status": "migrated",
        "modules": list(migrations.keys()),
        "backup_path": str(backup_path)
    }
```

---

## Testing Strategy

**Onboarding E2E Tests:**
```python
@pytest.mark.asyncio
async def test_onboarding_flow_complete(async_client, mock_spotify, mock_slskd):
    """Test complete onboarding flow from start to finish."""
    
    # Step 0: Welcome
    response = await async_client.get("/onboarding")
    assert response.status_code == 200
    assert "Welcome to SoulSpot Bridge" in response.text
    
    # Step 1: Spotify configuration
    response = await async_client.post(
        "/api/onboarding/spotify/test",
        data={
            "client_id": "test_client_id",
            "client_secret": "test_secret"
        }
    )
    assert response.status_code == 200
    assert "Connection successful" in response.text
    
    # Verify credentials saved encrypted
    config = await get_module_config(db, "spotify")
    assert config["client_id"] == "test_client_id"
    assert config["client_secret"] != "test_secret"  # Encrypted
    
    # Step 2: Soulseek configuration
    response = await async_client.post(
        "/api/onboarding/soulseek/test",
        data={"slskd_url": "http://localhost:5030"}
    )
    assert response.status_code == 200
    
    # Step 3: Optional modules
    response = await async_client.post(
        "/api/onboarding/optional/save",
        data={"enable_musicbrainz": "true"}
    )
    assert response.status_code == 200
    
    # Step 4: Complete
    response = await async_client.get("/onboarding/complete")
    assert "Setup Complete" in response.text
```

---

## Accessibility

**WCAG 2.1 AA Compliance:**
- ✅ Keyboard navigation (tab order)
- ✅ Screen reader announcements for validation errors
- ✅ ARIA labels for all inputs
- ✅ Focus indicators
- ✅ Sufficient color contrast

**Example:**
```html
<div class="form-group" role="group" aria-labelledby="client-id-label">
  <label id="client-id-label" for="client-id" class="form-label">
    Client ID <span class="required" aria-label="required">*</span>
  </label>
  <input type="text" 
         id="client-id"
         name="client_id"
         class="input"
         aria-required="true"
         aria-describedby="client-id-hint client-id-error"
         aria-invalid="false">
  <span id="client-id-hint" class="form-hint">
    Get this from Spotify Developer Dashboard
  </span>
  <span id="client-id-error" class="form-error" role="alert" hidden>
    <!-- Error message appears here -->
  </span>
</div>
```

---

## Summary

**Version 3.0 Onboarding:**
- ✅ **No .env files**: All configuration via UI
- ✅ **Real-time testing**: Instant validation of credentials
- ✅ **Secure storage**: Encrypted credentials in database
- ✅ **Clear guidance**: Help modals and troubleshooting tips
- ✅ **Optional modules**: Skip and configure later
- ✅ **Migration support**: Auto-import from existing .env
- ✅ **Reconfiguration**: Easy to update credentials post-setup
- ✅ **Accessible**: Full keyboard and screen reader support

**Implementation Checklist:**
- [ ] Design onboarding card UI
- [ ] Implement secure configuration storage
- [ ] Create test endpoints for each module
- [ ] Build step-by-step wizard flow
- [ ] Add help modals with credential guides
- [ ] Implement .env migration tool
- [ ] Test complete flow end-to-end
- [ ] Ensure accessibility compliance
