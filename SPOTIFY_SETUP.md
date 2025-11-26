# Spotify Integration - Setup Guide

## Quick Start

Die Spotify-Integration ist bereits vollständig implementiert! Sie müssen nur noch die Konfiguration abschließen.

## Schritt 1: Spotify Developer App erstellen

1. Gehen Sie zu https://developer.spotify.com/dashboard
2. Melden Sie sich mit Ihrem Spotify-Account an
3. Klicken Sie auf "Create app"
4. Füllen Sie das Formular aus:
   - **App name:** SoulSpot Bridge (oder ein Name Ihrer Wahl)
   - **App description:** Music downloader and library manager
   - **Redirect URI:** `http://localhost:8000/api/auth/callback`
   - **Which API/SDKs are you planning to use:** Web API
5. Akzeptieren Sie die Terms of Service
6. Klicken Sie auf "Save"

## Schritt 2: Client ID und Secret erhalten

1. Öffnen Sie Ihre neu erstellte App im Dashboard
2. Klicken Sie auf "Settings"
3. Kopieren Sie die **Client ID**
4. Klicken Sie auf "View client secret" und kopieren Sie das **Client Secret**

## Schritt 3: .env Datei konfigurieren

Die `.env` Datei wurde bereits erstellt. Öffnen Sie sie und tragen Sie Ihre Spotify-Credentials ein:

```bash
# Spotify Configuration (OAuth PKCE) - REQUIRED
SPOTIFY_CLIENT_ID=<ihre_client_id_hier>
SPOTIFY_CLIENT_SECRET=<ihr_client_secret_hier>
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

**Wichtig:** Die `SPOTIFY_REDIRECT_URI` muss EXAKT mit der URI übereinstimmen, die Sie im Spotify Developer Dashboard registriert haben!

## Schritt 4: Anwendung starten

### Option A: Mit Docker (empfohlen)

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### Option B: Lokal (für Entwicklung)

```bash
# Virtuelle Umgebung erstellen
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Datenbank initialisieren
alembic upgrade head

# Anwendung starten
python -m soulspot.main
```

## Schritt 5: Spotify verbinden

1. Öffnen Sie http://localhost:8000 im Browser
2. Klicken Sie auf "Connect Spotify" oder navigieren Sie zu `/api/auth/authorize`
3. Sie werden zu Spotify weitergeleitet
4. Autorisieren Sie die Anwendung
5. Sie werden zurück zu SoulSpot weitergeleitet
6. ✅ Fertig! Spotify ist jetzt verbunden

## Schritt 6: Funktionen testen

### Playlists importieren

```bash
# API-Endpunkt aufrufen (ersetzen Sie <access_token> mit Ihrem Token)
curl -X POST http://localhost:8000/api/playlists/import \
  -H "Content-Type: application/json" \
  -d '{
    "playlist_id": "<spotify_playlist_id>",
    "access_token": "<access_token>"
  }'
```

### Followed Artists synchronisieren

Die Anwendung synchronisiert automatisch Ihre gefolgten Artists von Spotify.

### Tracks suchen

Verwenden Sie die Web-UI oder API-Endpunkte, um nach Tracks zu suchen.

## Verfügbare Spotify-Funktionen

### ✅ Implementiert und einsatzbereit

1. **OAuth PKCE Authentifizierung**
   - Sicherer Login-Flow
   - Automatische Token-Erneuerung
   - Session-Persistenz

2. **Playlist-Management**
   - Playlists abrufen (`GET /api/playlists`)
   - Playlist-Details (`GET /api/playlists/{id}`)
   - Playlist importieren (`POST /api/playlists/import`)
   - Pagination für große Playlists

3. **Track-Operationen**
   - Track-Details abrufen
   - Track-Suche
   - Metadaten-Import

4. **Artist-Operationen**
   - Gefolgte Artists abrufen
   - Artist-Alben abrufen
   - Pagination für viele Artists

5. **Session-Management**
   - Datenbank-basierte Sessions
   - Automatische Token-Erneuerung
   - Logout-Funktionalität

## Troubleshooting

### "redirect_uri mismatch" Fehler

**Problem:** Die Redirect URI stimmt nicht überein.

**Lösung:**
1. Überprüfen Sie die `SPOTIFY_REDIRECT_URI` in `.env`
2. Stellen Sie sicher, dass sie EXAKT mit der URI im Spotify Dashboard übereinstimmt
3. Achten Sie auf:
   - `http` vs `https`
   - `localhost` vs `127.0.0.1`
   - Port-Nummer
   - Trailing slash

### "invalid_client" Fehler

**Problem:** Client ID oder Secret sind falsch.

**Lösung:**
1. Überprüfen Sie `SPOTIFY_CLIENT_ID` und `SPOTIFY_CLIENT_SECRET` in `.env`
2. Kopieren Sie die Werte erneut aus dem Spotify Dashboard
3. Stellen Sie sicher, dass keine Leerzeichen am Anfang/Ende sind

### Token läuft ab

**Problem:** Access Token ist abgelaufen.

**Lösung:**
- Die Anwendung erneuert Tokens automatisch
- Rufen Sie `/api/auth/refresh` auf, wenn nötig
- Bei Problemen: Logout und erneut einloggen

### Keine Playlists sichtbar

**Problem:** Playlists werden nicht angezeigt.

**Lösung:**
1. Überprüfen Sie, ob Sie bei Spotify eingeloggt sind
2. Stellen Sie sicher, dass die App die richtigen Scopes hat:
   - `playlist-read-private`
   - `playlist-read-collaborative`
3. Autorisieren Sie die App erneut

## Nächste Schritte

Nach erfolgreicher Konfiguration können Sie:

1. **Playlists importieren** - Ihre Spotify-Playlists in SoulSpot importieren
2. **Tracks herunterladen** - Automatisch über Soulseek herunterladen
3. **Bibliothek verwalten** - Ihre Musiksammlung organisieren
4. **Metadaten anreichern** - Automatisch mit MusicBrainz und Last.fm

## Support

Bei Problemen:
1. Überprüfen Sie die Logs: `docker-compose logs -f soulspot`
2. Prüfen Sie die Konfiguration in `.env`
3. Testen Sie die OAuth-Flow manuell
4. Konsultieren Sie die Spotify API Dokumentation: https://developer.spotify.com/documentation/web-api

---

**Status:** ✅ Spotify-Integration ist vollständig implementiert und einsatzbereit!
