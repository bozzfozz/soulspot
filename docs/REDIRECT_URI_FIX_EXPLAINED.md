# Redirect URI Fix - Vollständige Erklärung

## Warum wurde `settings.py` geändert?

### Das Problem

Es gab einen **Konflikt zwischen dem Default-Wert und der tatsächlichen API-Route**!

#### Vorher (FALSCH):
```python
# settings.py
redirect_uri: str = Field(
    default="http://localhost:8000/auth/spotify/callback",  # ❌ FALSCH!
    ...
)
```

#### Die tatsächliche FastAPI-Route:
```python
# src/soulspot/main.py (Zeile 525)
app.include_router(api_router, prefix="/api")

# src/soulspot/api/routers/__init__.py (Zeile 32)
api_router.include_router(auth.router, prefix="/auth")

# src/soulspot/api/routers/auth.py (Zeile 79)
@router.get("/callback")
async def callback(...):
    ...
```

**Ergebnis der Route-Struktur:**
- `/api` (von main.py)
- + `/auth` (von __init__.py)
- + `/callback` (von auth.py)
- = `/api/auth/callback` ✅

Der alte Default `http://localhost:8000/auth/spotify/callback` zeigt auf `/auth/spotify/callback`, aber diese Route **existiert gar nicht**!

### Die Korrektur

```python
# settings.py (JETZT KORREKT)
redirect_uri: str = Field(
    default="http://localhost:8000/api/auth/callback",  # ✅ KORREKT!
    ...
)
```

## Wichtig: Default vs. Deine Konfiguration

### Der Default ist nur ein Fallback!

Der Default in `settings.py` wird **NUR** verwendet, wenn:
- Keine `.env` Datei existiert, ODER
- `SPOTIFY_REDIRECT_URI` nicht in der `.env` gesetzt ist

### Für Docker (Port 8765):

Du musst in deiner `.env` oder `docker-compose.yml` setzen:

```env
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/api/auth/callback
```

**ODER** wenn du von einem anderen PC im LAN zugreifst:

```env
SPOTIFY_REDIRECT_URI=http://192.168.178.100:8765/api/auth/callback
```

## Die vollständige Fix-Historie

### Problem 1: Veralteter Pfad in settings.py
- ❌ Alt: `/auth/spotify/callback`
- ✅ Neu: `/api/auth/callback`

### Problem 2: Veralteter Pfad mit `/api/v1/` in Docker-Dateien
Die Anwendung wurde früher unter `/api/v1/` laufen, wurde aber auf `/api/` umgestellt.
Viele Dokumente und Konfigurationsdateien enthielten noch den alten Pfad.

- ❌ Alt: `http://127.0.0.1:8765/api/v1/auth/callback`
- ✅ Neu: `http://127.0.0.1:8765/api/auth/callback`

### Korrigierte Dateien:
1. ✅ `src/soulspot/config/settings.py` - Default redirect_uri
2. ✅ `.env.example` - Beispiel-Konfiguration
3. ✅ `docker/docker-compose.yml` - Docker Default
4. ✅ `docker/README.md` - Docker-Dokumentation
5. ✅ `tests/unit/config/test_settings.py` - Unit-Test

## Was musst DU jetzt tun?

### Schritt 1: Überprüfe deine .env Datei

```bash
cat .env | grep SPOTIFY_REDIRECT_URI
```

### Schritt 2: Setze die korrekte redirect_uri

Füge in deiner `.env` Datei hinzu oder aktualisiere:

```env
# Wenn du lokal per localhost zugreifst:
SPOTIFY_REDIRECT_URI=http://localhost:8765/api/auth/callback

# Wenn du per IP zugreifst (z.B. von einem anderen Gerät):
SPOTIFY_REDIRECT_URI=http://192.168.178.100:8765/api/auth/callback
```

### Schritt 3: Registriere in Spotify Developer Dashboard

1. Gehe zu https://developer.spotify.com/dashboard
2. Wähle deine App aus
3. Klicke "Edit Settings"
4. Unter "Redirect URIs", füge hinzu:
   - `http://localhost:8765/api/auth/callback`
   - `http://127.0.0.1:8765/api/auth/callback`
   - `http://192.168.178.100:8765/api/auth/callback`
   
   (Du kannst mehrere gleichzeitig registrieren!)

5. Klicke "Add" und dann "Save"

### Schritt 4: Starte die Anwendung neu

```bash
# Docker
docker-compose restart

# Oder neu bauen
docker-compose down
docker-compose up -d
```

### Schritt 5: Teste

1. Öffne: `http://192.168.178.100:8765/auth` (oder localhost)
2. Klicke "Connect Spotify"
3. Du wirst zu Spotify weitergeleitet
4. Nach der Autorisierung kommst du zurück zur App

## Fehlersuche

### Fehler: "INVALID_CLIENT: Insecure redirect URI"

**Bedeutung:** Die `redirect_uri` in deiner Anfrage stimmt nicht mit Spotify Dashboard überein.

**Lösung:**
1. Kopiere die `redirect_uri` aus der Fehlermeldung (URL-dekodiert)
2. Füge **EXAKT** diese URI im Spotify Dashboard hinzu
3. Warte 30 Sekunden (Spotify braucht Zeit zum Aktualisieren)
4. Versuche es erneut

### Fehler: Alte redirect_uri wird noch verwendet

**Ursache:** `.env` Datei überschreibt die neuen Defaults

**Lösung:**
```bash
# Überprüfe deine aktuelle Konfiguration
grep SPOTIFY_REDIRECT_URI .env

# Korrigiere falls nötig
# Entferne /api/v1/ → verwende /api/
# FALSCH: http://....:8765/api/v1/auth/callback
# RICHTIG: http://....:8765/api/auth/callback
```

## Zusammenfassung

### Der korrekte Pfad ist IMMER: `/api/auth/callback`

❌ **Nicht verwenden:**
- `/auth/spotify/callback` (alte Route, existiert nicht mehr)
- `/api/v1/auth/callback` (veraltete Version)

✅ **Korrekt:**
- `/api/auth/callback`

### Port hängt von deinem Setup ab:
- Lokale Entwicklung: `:8000`
- Docker (Standard): `:8765`
- Deine Konfiguration: prüfe `docker-compose.yml` ports

### Vollständige URLs für Port 8765:
- `http://localhost:8765/api/auth/callback`
- `http://127.0.0.1:8765/api/auth/callback`
- `http://192.168.178.100:8765/api/auth/callback` (deine LAN-IP)
