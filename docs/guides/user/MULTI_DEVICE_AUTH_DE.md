# Multi-Device Authentifizierung - Schnellanleitung (Deutsch)

## Zusammenfassung

Alle Ihre Fragen sind jetzt **JA** ✅

1. **Werden die Auth-Tokens serverseitig gespeichert?**
   - ✅ **JA** - Alle Spotify OAuth-Tokens werden in SQLite-Datenbank gespeichert
   - Überleben Server-Neustarts (Docker-Restarts, Updates etc.)
   - Keine erneute Authentifizierung nach Neustart nötig

2. **Kann ich mich von einem anderen PC zugreifen ohne Authentifizierung zu wiederholen?**
   - ✅ **JA** - Multi-Device-Zugriff jetzt möglich!
   - Session-ID exportieren und auf anderem Gerät importieren
   - ODER Session-ID als Bearer-Token verwenden

3. **Können nachfolgende Authentifizierungen automatisch durchgeführt werden?**
   - ✅ **JA** - Token-Refresh ist vollautomatisch
   - Spotify Access-Tokens erneuern sich automatisch
   - Keine menschliche Interaktion nötig

---

## Schnellstart: Multi-Device Zugriff

### Schritt 1: Session-ID exportieren (Gerät A)

```bash
curl http://localhost:8000/api/auth/session/export
```

Ergebnis:
```json
{
  "session_id": "ihre-lange-session-id-hier",
  "warning": "⚠️ Session-ID geheim halten!"
}
```

**Wichtig:** Session-ID kopieren (lange zufällige Zeichenkette)

### Schritt 2: Session auf anderem Gerät nutzen

#### Option A: Cookie importieren (Browser auf Gerät B)

```bash
curl -X POST "http://localhost:8000/api/auth/session/import?import_session_id=IHRE_SESSION_ID"
```

Oder im Browser:
1. DevTools öffnen (F12)
2. Application → Cookies
3. Cookie hinzufügen: `session_id` = `<ihre-session-id>`
4. Seite neu laden - Sie sind eingeloggt!

#### Option B: Bearer-Token verwenden (API/CLI)

```bash
curl -H "Authorization: Bearer IHRE_SESSION_ID" \
     http://localhost:8000/api/playlists
```

---

## Praktische Beispiele

### Spotify-Playlists von anderem PC abrufen

```bash
# Session-ID als Bearer-Token
SESSION_ID="ihre-session-id"

# Playlists abrufen
curl -H "Authorization: Bearer $SESSION_ID" \
     http://localhost:8000/api/playlists

# Playlist synchronisieren
curl -X POST \
  -H "Authorization: Bearer $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"spotify_uri":"spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"}' \
  http://localhost:8000/api/playlists/sync
```

### Python-Skript für Automatisierung

```python
import os
import requests

# Session-ID aus Umgebungsvariable (sicher!)
session_id = os.environ["SOULSPOT_SESSION_ID"]
headers = {"Authorization": f"Bearer {session_id}"}

# Playlists abrufen
response = requests.get(
    "http://localhost:8000/api/playlists",
    headers=headers
)

for playlist in response.json():
    print(f"Playlist: {playlist['name']}")
```

### Session-Status prüfen

```bash
curl -H "Authorization: Bearer $SESSION_ID" \
     http://localhost:8000/api/auth/session
```

Antwort:
```json
{
  "has_access_token": true,
  "has_refresh_token": true,
  "token_expired": false,
  "created_at": "2025-11-24T10:00:00Z"
}
```

---

## Sicherheit: Wichtige Hinweise ⚠️

### Session-ID = Passwort!

Die Session-ID ist **genauso sensibel wie ein Passwort**. Jeder mit Ihrer Session-ID kann auf Ihren Spotify-Account via SoulSpot zugreifen!

### Sicher ✅

- HTTPS in Produktion verwenden
- Session-ID geheim halten
- Nur über verschlüsselte Kanäle teilen (Signal, WhatsApp, verschlüsselte Email)
- Session widerrufen bei Kompromittierung: `curl -X POST ... /api/auth/logout`

### Unsicher ❌

- Session-ID in Git committen
- In öffentlichen Channels teilen (Discord, Slack, GitHub)
- Per unverschlüsselter Email senden
- Im Code hardcoden (stattdessen Umgebungsvariablen)

---

## Token-Automatik erklärt

### Wie funktioniert der automatische Token-Refresh?

1. **Spotify Access Token läuft ab** (nach 1 Stunde)
2. **SoulSpot merkt das automatisch** bei nächster API-Anfrage
3. **Refresh Token wird verwendet** um neuen Access Token zu holen
4. **Neuer Access Token wird in Datenbank gespeichert**
5. **API-Anfrage wird mit neuem Token ausgeführt**

**Alles passiert transparent - Sie merken nichts!**

### Manuelle Token-Aktualisierung

Normalerweise nicht nötig, aber möglich:

```bash
curl -X POST \
  -H "Authorization: Bearer $SESSION_ID" \
  http://localhost:8000/api/auth/refresh
```

---

## Häufige Probleme

### "No session found"

**Ursache:** Session-ID fehlt oder falsch

**Lösung:**
```bash
# Cookie prüfen (Browser)
# - DevTools → Application → Cookies → session_id vorhanden?

# Header prüfen (API)
# Format: "Authorization: Bearer <session-id>"
# OHNE Anführungszeichen, NUR die Session-ID!
```

### "Invalid or expired session"

**Ursache:** Session abgelaufen (1 Stunde Inaktivität)

**Lösung:**
```bash
# Session-Status prüfen
curl http://localhost:8000/api/auth/session

# Wenn wirklich abgelaufen: Neu authentifizieren
# http://localhost:8000/api/auth/authorize im Browser
```

### Token-Refresh schlägt fehl

**Ursache:** Refresh-Token von Spotify widerrufen

**Lösung:**
1. Spotify-App-Berechtigungen prüfen: https://www.spotify.com/account/apps/
2. SoulSpot neu autorisieren
3. Komplette Neu-Authentifizierung durchführen

---

## Umgebungsvariablen für Skripte

### Empfohlene Konfiguration

```bash
# .env Datei (NIE committen!)
SOULSPOT_SESSION_ID=ihre-session-id-hier
SOULSPOT_BASE_URL=http://localhost:8000
```

### Nutzung in Bash

```bash
#!/bin/bash
source .env

curl -H "Authorization: Bearer $SOULSPOT_SESSION_ID" \
     "$SOULSPOT_BASE_URL/api/playlists"
```

### Nutzung in Python

```python
import os
from dotenv import load_dotenv
import requests

load_dotenv()

session_id = os.getenv("SOULSPOT_SESSION_ID")
base_url = os.getenv("SOULSPOT_BASE_URL")

response = requests.get(
    f"{base_url}/api/playlists",
    headers={"Authorization": f"Bearer {session_id}"}
)
```

---

## Produktions-Deployment

### HTTPS ist PFLICHT in Produktion!

```bash
# .env (Produktion)
API_SECURE_COOKIES=true  # Nur HTTPS-Cookies
API_SESSION_MAX_AGE=3600 # Session-Timeout (Sekunden)
```

### Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name soulspot.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

---

## Zusammenfassung

| Feature | Cookie-Auth | Bearer-Token |
|---------|------------|--------------|
| Sicherheit | ✅ Hoch | ⚠️ Mittel |
| Benutzerfreundlichkeit | ✅ Automatisch | ⚠️ Manuell |
| Multi-Device | ⚠️ Import nötig | ✅ Sofort nutzbar |
| API/CLI | ❌ Unpraktisch | ✅ Perfekt |
| Empfohlen für | Browser/Web-UI | Skripte/Automatisierung |

**Best Practice:**
- Browser → Cookie-Auth (automatisch, sicher)
- API/CLI → Bearer-Token (flexibel, praktisch)

---

## Weitere Dokumentation

- Ausführliche englische Anleitung: `docs/MULTI_DEVICE_AUTH.md`
- API-Dokumentation: http://localhost:8000/docs
- Haupt-README: `README.md`
