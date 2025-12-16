# Parameter & Naming Conventions

## Ziel
Konsistente Benennung in allen Services, Repositories und Workers für bessere Lesbarkeit und weniger Bugs.

---

## 1. Constructor Parameter Reihenfolge

**IMMER diese Reihenfolge einhalten:**

```python
def __init__(
    self,
    # 1. Database Session (required)
    session: AsyncSession,
    
    # 2. Service-spezifische Plugins (required)
    spotify_plugin: "SpotifyPlugin",  # Service-Name als Präfix!
    
    # 3. Andere required Dependencies
    token_manager: DatabaseTokenManager,
    
    # 4. Optional Dependencies (mit Default)
    image_service: "ArtworkService | None" = None,
    settings_service: "AppSettingsService | None" = None,
) -> None:
```

---

## 2. Database Session Parameter

**Standard:** `session` (NICHT `db_session`, NICHT `_session`)

```python
# ✅ RICHTIG
def __init__(self, session: AsyncSession) -> None:
    self._session = session  # Intern mit Underscore

# ❌ FALSCH
def __init__(self, db_session: AsyncSession) -> None:
def __init__(self, _session: AsyncSession) -> None:
```

**Grund:** 
- Konsistent mit SQLAlchemy-Konventionen
- Kürzer und eindeutig
- `db_session` ist redundant (wir wissen dass es DB ist)

---

## 3. Plugin Parameter Benennung

**REGEL:** Plugin-Parameter MÜSSEN den Service-Namen als Präfix haben!

```python
# ✅ RICHTIG - Service-spezifisch
class SpotifySyncService:
    def __init__(self, session: AsyncSession, spotify_plugin: "SpotifyPlugin"):
        self._plugin = spotify_plugin  # Intern kann generisch sein

class DeezerSyncService:
    def __init__(self, session: AsyncSession, deezer_plugin: "DeezerPlugin"):
        self._plugin = deezer_plugin

class ProviderSyncOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin",
        deezer_plugin: "DeezerPlugin",
    ):
        self._spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin

# ❌ FALSCH - zu generisch
class DeezerSyncService:
    def __init__(self, session: AsyncSession, plugin: "DeezerPlugin"):  # FALSCH!
```

**Grund:**
- Verhindert Verwechslungen bei Multi-Provider Services
- Call-Site ist selbst-dokumentierend: `DeezerSyncService(session=s, deezer_plugin=p)`
- IDE Autocomplete zeigt den richtigen Plugin-Typ

---

## 4. Interne vs. Externe Attribute

**REGEL:** Interne Attribute mit Underscore-Präfix

```python
class MyService:
    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin",
        public_config: dict,  # Soll public sein
    ) -> None:
        # Private (nur intern genutzt)
        self._session = session
        self._plugin = spotify_plugin
        
        # Public (API für externe Nutzung)
        self.config = public_config
```

**Convention:**
| Zugriff | Naming | Beispiel |
|---------|--------|----------|
| Private | `self._name` | `self._session`, `self._plugin` |
| Public | `self.name` | `self.config`, `self.stats` |
| Protected | `self._name` | (Python hat kein protected, nutze private) |

---

## 5. Optional Dependencies

**REGEL:** Optional = `Type | None` mit `default=None`

```python
# ✅ RICHTIG
def __init__(
    self,
    session: AsyncSession,
    image_service: "ArtworkService | None" = None,
) -> None:
    self._image_service = image_service

# ❌ FALSCH - kein Default
def __init__(
    self,
    session: AsyncSession,
    image_service: "ArtworkService | None",  # Fehlt: = None
) -> None:

# ❌ FALSCH - Optional[T] statt T | None (deprecated style)
def __init__(
    self,
    session: AsyncSession,
    image_service: Optional[ArtworkService] = None,  # Verwende: Type | None
) -> None:
```

---

## 6. Worker Parameter

**REGEL:** Worker bekommen `db: Database` (nicht `session`)

```python
# ✅ RICHTIG - Worker bekommt Database für eigene Sessions
class DeezerSyncWorker:
    def __init__(
        self,
        db: "Database",  # Database-Instanz, nicht Session!
        settings: "Settings",
        check_interval_seconds: int = 60,
    ) -> None:
        self.db = db  # Public weil Worker es für session_scope braucht
        self._settings = settings
        self.check_interval_seconds = check_interval_seconds

# ❌ FALSCH - Worker sollte keine einzelne Session bekommen
class BadWorker:
    def __init__(self, session: AsyncSession):  # FALSCH!
        # Worker läuft lange, Session kann expire!
```

**Grund:**
- Worker laufen über längere Zeit
- Sessions können expire oder werden vom Pool recycled
- Worker erstellen ihre eigenen Sessions via `db.session_scope()`

---

## 7. Service Parameter Naming Matrix

| Service-Typ | session | plugin | andere |
|-------------|---------|--------|--------|
| **SpotifySyncService** | `session` | `spotify_plugin` | `image_service=None` |
| **DeezerSyncService** | `session` | `deezer_plugin` | - |
| **ProviderOrchestrator** | `session` | `spotify_plugin`, `deezer_plugin` | `settings_service=None` |
| **AppSettingsService** | `session` | - | - |
| **Workers** | - | - | `db`, `settings` |

---

## 8. Call-Site Beispiele

**IMMER named arguments bei 2+ Parametern:**

```python
# ✅ RICHTIG - Named arguments
service = DeezerSyncService(
    session=session,
    deezer_plugin=plugin,
)

worker = DeezerSyncWorker(
    db=db,
    settings=settings,
    check_interval_seconds=60,
)

# ❌ FALSCH - Positional arguments
service = DeezerSyncService(session, plugin)  # Unklar!
worker = DeezerSyncWorker(db, settings, 60)   # Was ist 60?
```

---

## 9. TYPE_CHECKING Import Pattern

**Für Forward References:**

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

class MyService:
    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin",  # String-Annotation!
    ) -> None:
```

---

## 10. Checkliste für neue Services

- [ ] `session: AsyncSession` als erster Parameter
- [ ] Plugin mit Service-Präfix: `spotify_plugin`, `deezer_plugin`
- [ ] Optional dependencies am Ende mit `= None`
- [ ] Interne Attribute mit `_` Präfix
- [ ] TYPE_CHECKING für Forward References
- [ ] Named arguments bei Call-Sites

---

## Beispiel: Vollständiger Service

```python
"""Example service following naming conventions."""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from soulspot.application.services.artwork_service import ArtworkService
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin


class SpotifyAlbumService:
    """Service for Spotify album operations.
    
    Hey future me - this service follows the naming conventions!
    See .github/instructions/naming.instructions.md for details.
    """
    
    def __init__(
        self,
        # 1. Database session (required)
        session: AsyncSession,
        # 2. Service-specific plugin (required)
        spotify_plugin: "SpotifyPlugin",
        # 3. Optional dependencies
        artwork_service: "ArtworkService | None" = None,
    ) -> None:
        """Initialize album service.
        
        Args:
            session: Database session
            spotify_plugin: SpotifyPlugin for API calls
            artwork_service: Optional service for downloading artwork
        """
        # Private attributes with underscore
        self._session = session
        self._plugin = spotify_plugin
        self._artwork_service = artwork_service
    
    async def get_album(self, album_id: str) -> dict:
        """Get album by ID."""
        return await self._plugin.get_album(album_id)
```
