# Spotify OAuth Troubleshooting

**Category:** User Guide  
**Version:** 1.0  
**Last Updated:** 2025-01  
**Audience:** Users, System Administrators

---

## Common Error: "INVALID_CLIENT: Insecure redirect URI"

This error occurs when `redirect_uri` doesn't **exactly match** Spotify Developer Dashboard configuration OR when using non-localhost HTTP URL.

---

## Spotify's HTTPS Requirement

**Spotify accepts:**
- ✅ `http://localhost:...` or `http://127.0.0.1:...` (HTTP without HTTPS)
- ✅ `https://...` (HTTPS with valid certificate)
- ❌ `http://192.168.x.x:...` (LAN IPs without HTTPS REJECTED)

**Solution for Docker:** Use `127.0.0.1` and access via SSH tunnel or directly from Docker host!

---

## Quick Fix Checklist

**1. Check current redirect_uri**
- Look at authorization URL error message
- Example: `redirect_uri=http%3A%2F%2F192.168.178.100%3A8765%2Fauth%2Fspotify%2Fcallback`
- URL-decoded: `http://192.168.178.100:8765/auth/spotify/callback`

**2. Identify correct path**
- ❌ WRONG: `/auth/spotify/callback` (old path)
- ✅ CORRECT: `/api/auth/callback` (current FastAPI route)

**3. Update Spotify Developer Dashboard**
- Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- Select your application → "Edit Settings"
- Under "Redirect URIs", add EXACT callback URL
- Click "Add" → "Save"

---

## Configuration Examples

### Local Development
```env
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

### Docker Deployment
**ALWAYS use 127.0.0.1 for Docker:**
```env
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/api/auth/callback
```

### ❌ DON'T Use LAN IP Addresses
**This REJECTED by Spotify:**
```env
SPOTIFY_REDIRECT_URI=http://192.168.178.100:8765/api/auth/callback
```

**Use SSH tunnel instead (see below).**

---

## Step-by-Step Fix

### Step 1: Identify Access Method

**How do you access the application?**
- ✅ Local only: `http://localhost:8000` or `http://127.0.0.1:8000`
- ✅ Docker on same machine: `http://127.0.0.1:8765`
- ✅ Remote via SSH tunnel: `http://127.0.0.1:8765` (tunneled)
- ✅ Custom domain with HTTPS: `https://yourdomain.com`
- ❌ LAN IP without HTTPS: NOT SUPPORTED by Spotify

---

### Step 2: Build redirect_uri

**Format:** `{YOUR_ACCESS_URL}/api/auth/callback`

**Valid Examples:**
- `http://localhost:8000/api/auth/callback`
- `http://127.0.0.1:8765/api/auth/callback`
- `https://yourdomain.com/api/auth/callback`

**Invalid Examples:**
- ❌ `http://192.168.178.100:8765/api/auth/callback` (no HTTPS)
- ❌ `http://localhost:8765/auth/spotify/callback` (wrong path)

---

### Step 3: Register in Spotify Dashboard

1. Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Login with Spotify account
3. Select your application (or create if needed)
4. Click **"Edit Settings"**
5. Scroll to **"Redirect URIs"**
6. Enter your `redirect_uri` (e.g., `http://127.0.0.1:8765/api/auth/callback`)
7. Click **"Add"**
8. Click **"Save"** at bottom

⚠️ **IMPORTANT:** You can add **multiple** redirect URIs! Add all URLs you might use:
- `http://localhost:8000/api/auth/callback` (local development)
- `http://localhost:8765/api/auth/callback` (Docker local)
- `http://127.0.0.1:8765/api/auth/callback` (Docker explicit)

---

### Step 4: Update .env File

**Edit `.env` file:**
```bash
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/api/auth/callback
```

**Must match EXACTLY** one of the URIs registered in Step 3!

---

### Step 5: Restart Application

```bash
# If running directly
python -m soulspot.main

# If using Docker
docker-compose restart
```

---

### Step 6: Test Authorization

1. Go to: `http://127.0.0.1:8765/auth` (or your URL)
2. Click "Connect Spotify"
3. Should redirect to Spotify authorization page
4. After authorizing, should redirect back successfully

---

## Common Mistakes

### ❌ Using OLD path
```env
SPOTIFY_REDIRECT_URI=http://localhost:8000/auth/spotify/callback
```
Old path `/auth/spotify/callback` NO LONGER EXISTS!

### ✅ Use CURRENT path
```env
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

---

### ❌ Mismatch between .env and Dashboard
- .env: `http://localhost:8000/api/auth/callback`
- Dashboard: `http://192.168.178.100:8765/api/auth/callback`

### ✅ EXACT match
- .env: `http://127.0.0.1:8765/api/auth/callback`
- Dashboard: `http://127.0.0.1:8765/api/auth/callback` ✓

---

### ❌ Wrong protocol
- .env: `http://...`
- Dashboard: `https://...`

### ✅ Same protocol
- .env: `http://127.0.0.1:8765/api/auth/callback`
- Dashboard: `http://127.0.0.1:8765/api/auth/callback` ✓

---

## Remote Access via SSH Tunnel

**Why SSH Tunnel?**

Spotify only allows HTTP for `localhost`/`127.0.0.1`. For remote access:
- ✅ HTTPS with valid certificate, OR
- ✅ SSH tunnel (makes remote access appear as localhost)

**Setup SSH Tunnel:**

On your client device (laptop, tablet, etc.):

```bash
# Create tunnel to Docker host
ssh -L 8765:localhost:8765 user@192.168.178.100

# Keep connection open
```

**Access via SSH Tunnel:**

1. SSH tunnel active
2. Open browser on client device
3. Go to: `http://127.0.0.1:8765/auth`
4. Connection tunnels through SSH to Docker host
5. OAuth works because Spotify sees `127.0.0.1`

**Alternative: Setup HTTPS**

For permanent remote access, setup reverse proxy (nginx/traefik) with Let's Encrypt. Then use `https://yourdomain.com/api/auth/callback`.

---

## Debugging Tips

### See actual redirect_uri being used

1. Click "Connect Spotify" button
2. Look at authorization URL in browser (before Spotify loads)
3. Find `redirect_uri=` parameter
4. URL-decode to see actual value

### Check .env loaded

```bash
# In terminal where you run app
echo $SPOTIFY_REDIRECT_URI
```

### Test configuration

```python
python3 << 'EOF'
from soulspot.config import get_settings
settings = get_settings()
print(f"redirect_uri: {settings.spotify.redirect_uri}")
EOF
```

---

## Still Having Issues?

**If still seeing "INVALID_CLIENT: Insecure redirect URI":**

**1. Double-check Spotify Dashboard**
- Is `redirect_uri` saved? (Click Edit Settings to verify)
- Any typos?
- Did you click "Save" after adding?

**2. Check for trailing slashes**
- ❌ `http://localhost:8000/api/auth/callback/`
- ✅ `http://localhost:8000/api/auth/callback`

**3. Verify CLIENT_ID matches**
- `client_id` in URL must match app in Spotify Dashboard
- Check `.env` file's `SPOTIFY_CLIENT_ID`

**4. Clear browser cache**
- Old authorization attempts might be cached
- Try incognito/private mode

**5. Wait a moment**
- Spotify might take seconds to propagate changes
- Wait 30 seconds after saving, then retry

---

## Security Note

**HTTP vs HTTPS:**
- ✅ `http://localhost` ALLOWED by Spotify (development)
- ✅ `http://127.0.0.1` ALLOWED by Spotify (development)
- ❌ `http://192.168.x.x` REJECTED by Spotify (requires HTTPS)
- ✅ `https://` REQUIRED for production domains

---

## Related Documentation

- [Setup Guide](./setup-guide.md) - Initial configuration
- [Troubleshooting Guide](./troubleshooting-guide.md) - General issues
- [User Guide](./user-guide.md) - Feature documentation

---

**Version:** 1.0  
**Last Updated:** 2025-01
