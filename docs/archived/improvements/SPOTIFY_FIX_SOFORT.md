# SOFORT-ANLEITUNG: Spotify OAuth Fehler beheben

## Dein aktueller Fehler

```
INVALID_CLIENT: Insecure redirect URI
```

## ⚠️ WICHTIG: Spotify erfordert HTTPS oder localhost!

**Spotify akzeptiert nur:**
- ✅ `http://localhost:...` oder `http://127.0.0.1:...` (ohne HTTPS)
- ✅ `https://...` (mit HTTPS und gültigem Zertifikat)
- ❌ `http://192.168.x.x:...` (LAN-IPs ohne HTTPS werden ABGELEHNT)

**Lösung für Docker:** Verwende `127.0.0.1` und greife über SSH-Tunnel oder direkt vom Docker-Host zu!

## Die Lösung (3 einfache Schritte)

### Schritt 1: Deine .env Datei anpassen

Öffne die `.env` Datei im `docker/` Verzeichnis und setze:

```env
SPOTIFY_CLIENT_ID=bad2ac519cd042d89cd061b1cbe1b99f
SPOTIFY_CLIENT_SECRET=dein_secret_hier
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/api/auth/callback
```

**WICHTIG:** 
- ❌ Nicht: `http://192.168.178.100:8765/...` (wird von Spotify abgelehnt!)
- ❌ Nicht: `http://127.0.0.1:8765/auth/spotify/callback` (alter Pfad)
- ✅ Richtig: `http://127.0.0.1:8765/api/auth/callback`

### Schritt 2: Spotify Developer Dashboard aktualisieren

1. Gehe zu: https://developer.spotify.com/dashboard
2. Melde dich an
3. Klicke auf deine App (mit Client-ID `bad2ac519cd042d89cd061b1cbe1b99f`)
4. Klicke **"Edit Settings"**
5. Scrolle zu **"Redirect URIs"**
6. Gib ein: `http://127.0.0.1:8765/api/auth/callback`
7. Klicke **"Add"**
8. Klicke **"Save"** ganz unten

**WICHTIG:** Nur localhost/127.0.0.1 funktioniert ohne HTTPS!
- ✅ `http://localhost:8765/api/auth/callback`
- ✅ `http://127.0.0.1:8765/api/auth/callback`  
- ❌ `http://192.168.178.100:8765/api/auth/callback` (NICHT erlaubt von Spotify!)

### Schritt 3: Docker Container neu starten

```bash
cd docker
docker-compose restart
```

**ODER** komplett neu bauen:

```bash
docker-compose down
docker-compose up -d
```

### Schritt 4: Zugriff auf die Anwendung

**Option A: Vom Docker-Host selbst**
1. Öffne Browser auf dem Docker-Host-Rechner
2. Gehe zu: `http://127.0.0.1:8765/auth`
3. Klicke "Connect Spotify"
4. Du wirst zu Spotify weitergeleitet
5. Autorisiere die App
6. Du kommst zurück zur App - **FERTIG!**

**Option B: Von einem anderen Gerät (SSH-Tunnel)**

Siehe die ausführliche Anleitung weiter unten im Abschnitt "SSH-Tunnel für Remote-Zugriff".

## Was wurde gefixt?

### Problem 1: Falscher Pfad
- **Alt:** `/auth/spotify/callback` ❌
- **Neu:** `/api/auth/callback` ✅

### Problem 2: Veraltete Version
- **Alt:** `/api/v1/auth/callback` ❌
- **Neu:** `/api/auth/callback` ✅

### Problem 3: Redirect URI nicht registriert
- Die URI muss **EXAKT** in Spotify Dashboard eingetragen sein
- Jedes Detail zählt: Protokoll (http), IP, Port, Pfad

## Checkliste

- [ ] `.env` Datei aktualisiert mit korrekter redirect_uri
- [ ] Spotify Dashboard: redirect_uri hinzugefügt
- [ ] Spotify Dashboard: "Save" geklickt
- [ ] Docker Container neu gestartet
- [ ] Browser-Test erfolgreich

## Wenn es immer noch nicht funktioniert

### Debug: Welche redirect_uri wird verwendet?

```bash
# Überprüfe deine .env
cat docker/.env | grep SPOTIFY_REDIRECT_URI

# Sollte zeigen:
# SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/api/auth/callback
```

### Debug: Ist die redirect_uri in Spotify registriert?

1. Gehe zu Spotify Dashboard
2. Öffne deine App
3. Klicke "Edit Settings"
4. Schaue unter "Redirect URIs"
5. Muss exakt enthalten sein: `http://127.0.0.1:8765/api/auth/callback`

### Warte 30 Sekunden

Spotify braucht manchmal ein paar Sekunden, um Änderungen zu übernehmen.

### Probiere Inkognito-Modus

Alte authorization-Versuche können im Browser-Cache sein.

## SSH-Tunnel für Remote-Zugriff

Wenn du von einem anderen Gerät (nicht vom Docker-Host) zugreifen möchtest:

### Warum SSH-Tunnel?

Spotify erlaubt HTTP nur für `localhost`/`127.0.0.1`. Wenn du von einem anderen Gerät zugreifst, benötigst du entweder:
- ✅ HTTPS mit gültigem Zertifikat, ODER
- ✅ SSH-Tunnel, um Remote-Zugriff wie localhost erscheinen zu lassen

### SSH-Tunnel einrichten

**Auf deinem Client-Gerät** (Laptop, Tablet, etc.):

```bash
# Tunnel zum Docker-Host aufbauen
ssh -L 8765:localhost:8765 user@192.168.178.100

# Beispiel mit deinem Setup:
ssh -L 8765:localhost:8765 dein_benutzer@192.168.178.100
```

**Halte diese SSH-Verbindung offen!**

### Zugriff über SSH-Tunnel

1. SSH-Tunnel ist aktiv
2. Öffne Browser auf deinem Client-Gerät
3. Gehe zu: `http://127.0.0.1:8765/auth`
4. Die Verbindung wird durch den SSH-Tunnel zum Docker-Host geleitet
5. OAuth funktioniert, da Spotify `127.0.0.1` sieht

### Alternative: HTTPS einrichten

Für dauerhafte Remote-Zugriffe ohne SSH-Tunnel kannst du einen Reverse-Proxy (nginx/traefik) mit Let's Encrypt einrichten. Dann funktioniert auch `https://deine-domain.de/api/auth/callback`.

## Weitere Hilfe

Siehe die ausführliche Dokumentation:
- `docs/REDIRECT_URI_FIX_EXPLAINED.md` (auf Deutsch)
- `docs/SPOTIFY_AUTH_TROUBLESHOOTING.md` (auf Englisch)
