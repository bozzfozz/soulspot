# Multi-Device Authentication Guide

## Overview

SoulSpot supports accessing your authenticated session from multiple devices or browsers. This guide explains how authentication works and how to use your account across different devices.

## Table of Contents

1. [How Authentication Works](#how-authentication-works)
2. [Single Device (Default)](#single-device-default)
3. [Multi-Device Access](#multi-device-access)
4. [Security Best Practices](#security-best-practices)
5. [API Usage Examples](#api-usage-examples)
6. [Troubleshooting](#troubleshooting)

---

## How Authentication Works

### Token Storage

**Yes, all authentication tokens are stored server-side!**

- ✅ **Spotify OAuth tokens** (access + refresh tokens) are persisted in the SQLite database
- ✅ **Sessions survive server restarts** - no need to re-authenticate after updates/reboots
- ✅ **Automatic token refresh** - Spotify access tokens expire after 1 hour but are automatically renewed using the refresh token (no human interaction required)

### Authentication Methods

SoulSpot supports **two authentication methods**:

1. **Cookie-based (Default)** - Most secure, automatically managed by browser
2. **Bearer Token** - For API clients, curl, or cross-device access

---

## Single Device (Default)

### Initial Setup

1. **Start OAuth Flow**
   ```bash
   # Visit in your browser
   http://localhost:8000/api/auth/authorize
   ```

2. **Authorize with Spotify**
   - You'll be redirected to Spotify's authorization page
   - Grant permissions to SoulSpot
   - Automatically redirected back with tokens stored

3. **Session Cookie Set**
   - Browser automatically receives a `session_id` cookie (HttpOnly, Secure)
   - All subsequent API requests use this cookie for authentication
   - No manual token management required!

### Token Refresh (Automatic)

- Spotify access tokens expire after **1 hour**
- SoulSpot automatically refreshes tokens when needed
- **No human interaction required** - completely transparent
- Refresh tokens don't expire (unless revoked by Spotify)

---

## Multi-Device Access

### Use Cases

- Access SoulSpot from work laptop and home desktop
- Use API clients (curl, Postman, custom scripts) alongside web UI
- Share access with trusted household members (same Spotify account)

### How Multi-Device Works

SoulSpot stores all authentication tokens **server-side**. Once you authenticate on one device:

1. Your Spotify tokens are stored in the database
2. The same account can be accessed from any device on the local network
3. Simply log in again on the new device - the server maintains your Spotify connection

### Accessing from Another Device

**On any device in your local network:**

1. Open your browser and navigate to SoulSpot (e.g., `http://192.168.1.100:8000`)
2. Start the OAuth flow via `/api/auth/authorize`
3. Log in with your Spotify credentials
4. You're now authenticated on this device!

> **Note:** Each device gets its own session, but all sessions share the same server-side Spotify tokens. This means you don't need to re-authorize with Spotify - just log in.

### Using Bearer Tokens for API Access

For API clients, scripts, or automation, you can use your session ID as a Bearer token:

**Example: List playlists with curl**
```bash
# First, get your session ID from your browser (DevTools → Application → Cookies → session_id)
SESSION_ID="your-session-id-from-browser"

curl -H "Authorization: Bearer $SESSION_ID" \
     http://localhost:8000/api/playlists
```

**Example: Python script**
```python
import os
import requests

# Get session ID from environment variable
session_id = os.environ.get("SOULSPOT_SESSION_ID")
headers = {"Authorization": f"Bearer {session_id}"}

# Get playlists
response = requests.get(
    "http://localhost:8000/api/playlists",
    headers=headers
)
print(response.json())

# Sync playlist
response = requests.post(
    "http://localhost:8000/api/playlists/sync",
    headers=headers,
    json={"spotify_uri": "spotify:playlist:..."}
)
```

**Example: JavaScript fetch**
```javascript
const sessionId = "your-session-id-from-browser";

fetch("http://localhost:8000/api/playlists", {
  headers: {
    "Authorization": `Bearer ${sessionId}`
  }
})
.then(response => response.json())
.then(data => console.log(data));
```

---

## Security Best Practices

### ⚠️ Session ID is a Sensitive Credential

**The session ID grants access to your SoulSpot session!**

### DO ✅

- **Use HTTPS in production** - Never send session IDs over unencrypted connections
- **Keep session IDs secret** - Treat them like passwords
- **Revoke compromised sessions** - Use `/api/auth/logout` if session ID is leaked
- **Use cookie-based auth when possible** - More secure than bearer tokens (HttpOnly protection)

### DON'T ❌

- **Don't commit session IDs to git** - Add `.env` to `.gitignore`
- **Don't share in public channels** - Slack, Discord, GitHub issues, etc.
- **Don't hardcode in scripts** - Use environment variables instead

### Recommended Practices

1. **Use environment variables for scripts**
   ```bash
   # .env file (never commit this!)
   SOULSPOT_SESSION_ID=your-session-id-here
   ```

   ```python
   import os
   session_id = os.environ["SOULSPOT_SESSION_ID"]
   ```

2. **Rotate sessions periodically**
   ```bash
   # Logout old session
   curl -X POST http://localhost:8000/api/auth/logout

   # Re-authenticate
   # Visit http://localhost:8000/api/auth/authorize
   ```

3. **Monitor session activity**
   ```bash
   # Check current session info
   curl http://localhost:8000/api/auth/session
   ```

---

## API Usage Examples

### Check Authentication Status

```bash
# With cookie (browser)
curl -b cookies.txt http://localhost:8000/api/auth/session

# With bearer token
curl -H "Authorization: Bearer YOUR_SESSION_ID" \
     http://localhost:8000/api/auth/session
```

Response:
```json
{
  "session_id": "abc123...",
  "has_access_token": true,
  "has_refresh_token": true,
  "token_expired": false,
  "created_at": "2025-11-24T10:00:00Z",
  "last_accessed_at": "2025-11-24T12:30:00Z"
}
```

### Manual Token Refresh

Normally automatic, but you can trigger manually:

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  http://localhost:8000/api/auth/refresh
```

### Logout (Revoke Session)

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  http://localhost:8000/api/auth/logout
```

---

## Troubleshooting

### "No session found" Error

**Cause:** Session ID missing or incorrect

**Solutions:**
1. Check cookie is set correctly (browser DevTools → Application → Cookies)
2. Verify Authorization header format: `Authorization: Bearer <session_id>`
3. Re-authenticate via `/api/auth/authorize`

### "Invalid or expired session" Error

**Cause:** Session expired due to inactivity or server restart (if not using DatabaseSessionStore)

**Solutions:**
1. Check session expiry: `curl http://localhost:8000/api/auth/session`
2. Re-authenticate via `/api/auth/authorize`

### Token Refresh Fails

**Cause:** Refresh token invalid or revoked by Spotify

**Solutions:**
1. Check Spotify app permissions: https://www.spotify.com/account/apps/
2. Revoke and re-grant access to SoulSpot
3. Full re-authentication required (cannot recover from invalid refresh token)

### Session Doesn't Work on Device B

**Checklist:**
- ✅ Both devices can reach SoulSpot server (check network/firewall)
- ✅ Cookie domain matches (use IP address or hostname consistently)
- ✅ Cookie path is `/`
- ✅ For API clients: Authorization header format is correct

### Bearer Token Works but Cookie Doesn't

**Cause:** Cookie security settings mismatch

**Solutions:**
1. Check `API_SECURE_COOKIES` setting in `.env`
   - `false` for HTTP (local development)
   - `true` for HTTPS (production)
2. Ensure browser and server domain match
3. Check SameSite policy allows cookies

---

## Production Deployment

### Required Settings

```bash
# .env (production)
API_SECURE_COOKIES=true  # Require HTTPS for cookies
API_SESSION_MAX_AGE=3600  # Session lifetime (seconds)
```

### HTTPS Setup

**Session IDs MUST be transmitted over HTTPS in production!**

Use a reverse proxy (nginx, Traefik, Caddy) to terminate SSL:

```nginx
# nginx example
server {
    listen 443 ssl;
    server_name soulspot.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

---

## FAQs

**Q: Do I need to re-authenticate after server restarts?**  
A: **No!** Sessions are persisted in SQLite database and survive restarts.

**Q: Can I access from my phone using the same account?**  
A: **Yes!** Open SoulSpot in your mobile browser and authenticate. The server maintains your Spotify connection.

**Q: How long do sessions last?**  
A: Sessions are active as long as you use them. Default timeout is 1 hour of **inactivity**. Each request refreshes the timeout.

**Q: Can multiple people use the same account?**  
A: **Technically yes**, but **not recommended**. Each person should authenticate separately for security and audit trails.

**Q: What happens if someone steals my session ID?**  
A: They can access your Spotify account via SoulSpot. **Immediately logout** to revoke the session:
```bash
curl -X POST -H "Authorization: Bearer STOLEN_SESSION_ID" \
     http://localhost:8000/api/auth/logout
```

**Q: Can I have multiple active sessions?**  
A: **Yes!** Each device/browser can have its own session.

---

## Summary

| Feature | Cookie-based Auth | Bearer Token Auth |
|---------|------------------|-------------------|
| Security | ✅ High (HttpOnly, Secure) | ⚠️ Medium (must handle securely) |
| Ease of Use | ✅ Automatic (browser) | ⚠️ Manual header management |
| Multi-device | ✅ Each device authenticates | ✅ Native support |
| API Clients | ❌ Not ideal | ✅ Perfect fit |
| Recommended For | Web UI, browsers | CLI, scripts, automation |

**Best Practice:** Use cookie-based auth in browsers, bearer tokens for API clients/automation.
