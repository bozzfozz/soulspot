"""
Centralized Rate Limiter for External API Calls.

Hey future me – das ist der ZENTRALE Rate Limiter für alle externen APIs!
Wir verwenden den Token Bucket Algorithmus mit adaptivem Backoff.

WARUM ZENTRAL?
- Spotify, Deezer, MusicBrainz haben ALLE Rate Limits
- Ohne zentrales Management: 429 Errors überall
- Mit zentralem Management: Smooth, keine Blockierung

ALGORITHMUS: Token Bucket
- Bucket hat max_tokens Kapazität
- Tokens werden mit refill_rate/sec nachgefüllt
- Jede Anfrage verbraucht 1 Token
- Wenn leer: Warten bis Tokens verfügbar

ADAPTIVE BACKOFF bei 429:
- Erste 429: 1 Sekunde warten
- Zweite 429: 2 Sekunden warten
- Dritte 429: 4 Sekunden warten (exponentiell)
- Nach Erfolg: Backoff reset

USAGE:
    limiter = RateLimiter(max_tokens=10, refill_rate=1.0)  # 10 requests/10 sec

    async with limiter:
        response = await client.get(url)

    # Bei 429:
    await limiter.handle_rate_limit_response()  # Adaptiver Backoff
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RateLimiterConfig:
    """Configuration for rate limiter.

    Hey future me – die Standard-Werte sind für Spotify optimiert!
    Spotify hat ungefähr: 180 requests / minute = 3 req/sec
    Wir sind konservativ mit 2 req/sec um Puffer zu haben.

    WICHTIG: max_backoff_seconds muss HOCH genug sein!
    Spotify kann Retry-After von 5+ Minuten senden (besonders bei heavy usage).
    Wenn wir das auf 60s cappen, ignorieren wir den Header und bekommen
    sofort wieder 429 → infinite loop!
    """

    max_tokens: int = 10  # Bucket size
    refill_rate: float = 2.0  # Tokens per second
    max_backoff_seconds: float = (
        600.0  # Max wait on 429 (10 minutes! Spotify can send long waits)
    )
    initial_backoff_seconds: float = 1.0  # First 429 wait
    backoff_multiplier: float = 2.0  # Exponential backoff factor


@dataclass
class RateLimiter:
    """Token Bucket Rate Limiter with adaptive backoff.

    Hey future me – das ist die Haupt-Klasse!
    Nutze sie als async context manager für automatisches Token-Management.

    Attributes:
        config: Rate limiter configuration
        _tokens: Current available tokens
        _last_refill: Last time tokens were refilled
        _current_backoff: Current backoff delay (resets on success)
        _lock: Async lock for thread-safety
    """

    config: RateLimiterConfig = field(default_factory=RateLimiterConfig)

    # Internal state (not in __init__ signature)
    _tokens: float = field(default=0.0, init=False)
    _last_refill: float = field(default_factory=time.monotonic, init=False)
    _current_backoff: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _name: str = field(default="default", init=False)

    def __post_init__(self) -> None:
        """Initialize tokens to max capacity."""
        self._tokens = float(self.config.max_tokens)
        self._current_backoff = self.config.initial_backoff_seconds

    @classmethod
    def for_spotify(cls) -> "RateLimiter":
        """Create rate limiter optimized for Spotify API.

        Hey future me – Spotify Rate Limits:
        - Ungefähr 180 requests / minute = 3 req/sec
        - Aber: Burst erlaubt (kurze Spitzen)
        - Konservativ: 2 req/sec sustained, 10 burst

        WICHTIG: max_backoff ist jetzt 600s (10 Minuten)!
        Spotify kann lange Retry-After Header senden (5+ Minuten).
        Wir müssen diese respektieren, sonst infinite 429 loop!
        """
        limiter = cls(
            config=RateLimiterConfig(
                max_tokens=10,  # Burst capacity
                refill_rate=2.0,  # Sustained rate
                max_backoff_seconds=600.0,  # 10 minutes - respect long Retry-After headers!
                initial_backoff_seconds=1.0,
            )
        )
        limiter._name = "spotify"
        return limiter

    @classmethod
    def for_deezer(cls) -> "RateLimiter":
        """Create rate limiter optimized for Deezer API.

        Hey future me – Deezer Rate Limits:
        - Ungefähr 50 requests / 5 seconds = 10 req/sec
        - Aber weniger Burst als Spotify
        """
        limiter = cls(
            config=RateLimiterConfig(
                max_tokens=15,  # Larger bucket for Deezer
                refill_rate=5.0,  # 5 req/sec (half of limit for safety)
                max_backoff_seconds=30.0,
                initial_backoff_seconds=0.5,
            )
        )
        limiter._name = "deezer"
        return limiter

    @classmethod
    def for_musicbrainz(cls) -> "RateLimiter":
        """Create rate limiter for MusicBrainz API.

        Hey future me – MusicBrainz ist STRENG: 1 req/sec!
        Keine Bursts erlaubt. Wir sind extra konservativ.
        """
        limiter = cls(
            config=RateLimiterConfig(
                max_tokens=1,  # No burst!
                refill_rate=1.0,  # Exactly 1 req/sec
                max_backoff_seconds=120.0,  # Long backoff (MB bans aggressive clients)
                initial_backoff_seconds=2.0,
            )
        )
        limiter._name = "musicbrainz"
        return limiter

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time.

        Hey future me – das ist der Token Bucket Algorithmus!
        Wir berechnen, wie viele Tokens seit letztem Refill dazugekommen sind.
        """
        now = time.monotonic()
        elapsed = now - self._last_refill

        # Calculate new tokens
        new_tokens = elapsed * self.config.refill_rate
        self._tokens = min(self.config.max_tokens, self._tokens + new_tokens)
        self._last_refill = now

    async def acquire(self) -> None:
        """Acquire one token, waiting if necessary.

        Hey future me – das ist die Haupt-Methode!
        Sie wartet automatisch, wenn keine Tokens verfügbar sind.
        """
        async with self._lock:
            self._refill_tokens()

            while self._tokens < 1.0:
                # Calculate wait time until 1 token available
                wait_time = (1.0 - self._tokens) / self.config.refill_rate
                logger.debug(
                    f"RateLimiter[{self._name}]: No tokens available, "
                    f"waiting {wait_time:.2f}s"
                )

                # Release lock while waiting
                self._lock.release()
                await asyncio.sleep(wait_time)
                await self._lock.acquire()

                # Refill and check again
                self._refill_tokens()

            # Consume one token
            self._tokens -= 1.0
            logger.debug(
                f"RateLimiter[{self._name}]: Token acquired, "
                f"{self._tokens:.1f} remaining"
            )

    async def handle_rate_limit_response(self, retry_after: int | None = None) -> float:
        """Handle a 429 rate limit response with adaptive backoff.

        Hey future me – WICHTIG bei 429 Errors!
        Wir warten adaptiv länger bei wiederholten 429s.

        Args:
            retry_after: Retry-After header from API response (seconds)

        Returns:
            The actual wait time used
        """
        async with self._lock:
            # Use Retry-After header if provided
            if retry_after is not None:
                wait_time = float(retry_after)
            else:
                wait_time = self._current_backoff

            # Cap at max backoff
            wait_time = min(wait_time, self.config.max_backoff_seconds)

            logger.warning(
                f"RateLimiter[{self._name}]: 429 Rate Limited! "
                f"Waiting {wait_time:.1f}s before retry "
                f"(backoff level: {self._current_backoff:.1f}s)"
            )

            # Increase backoff for next 429
            self._current_backoff = min(
                self._current_backoff * self.config.backoff_multiplier,
                self.config.max_backoff_seconds,
            )

            # Clear tokens (force wait)
            self._tokens = 0.0

        # Wait outside lock
        await asyncio.sleep(wait_time)
        return wait_time

    def reset_backoff(self) -> None:
        """Reset backoff after successful request.

        Hey future me – rufe das nach JEDEM erfolgreichen Request auf!
        Das setzt den Backoff zurück auf Initial-Wert.
        """
        self._current_backoff = self.config.initial_backoff_seconds

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[None]:
        """Context manager for rate-limited operations.

        Usage:
            async with rate_limiter():
                response = await client.get(url)
        """
        await self.acquire()
        try:
            yield
        finally:
            pass  # Token already consumed

    # Alias for async with syntax
    async def __aenter__(self) -> "RateLimiter":
        """Enter async context - acquire token."""
        await self.acquire()
        return self

    async def __aexit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: object
    ) -> None:
        """Exit async context."""
        # If no exception, reset backoff (success!)
        if exc_type is None:
            self.reset_backoff()

    @property
    def available_tokens(self) -> float:
        """Get current available tokens (for debugging)."""
        self._refill_tokens()
        return self._tokens

    @property
    def name(self) -> str:
        """Get limiter name for logging."""
        return self._name


# Module-level rate limiters (singleton pattern)
# Hey future me – diese werden von den Clients importiert!
# Ein Limiter pro Service, geteilt über alle Requests.
_spotify_limiter: RateLimiter | None = None
_deezer_limiter: RateLimiter | None = None
_musicbrainz_limiter: RateLimiter | None = None


def get_spotify_limiter() -> RateLimiter:
    """Get singleton Spotify rate limiter."""
    global _spotify_limiter
    if _spotify_limiter is None:
        _spotify_limiter = RateLimiter.for_spotify()
    return _spotify_limiter


def get_deezer_limiter() -> RateLimiter:
    """Get singleton Deezer rate limiter."""
    global _deezer_limiter
    if _deezer_limiter is None:
        _deezer_limiter = RateLimiter.for_deezer()
    return _deezer_limiter


def get_musicbrainz_limiter() -> RateLimiter:
    """Get singleton MusicBrainz rate limiter."""
    global _musicbrainz_limiter
    if _musicbrainz_limiter is None:
        _musicbrainz_limiter = RateLimiter.for_musicbrainz()
    return _musicbrainz_limiter


__all__ = [
    "RateLimiter",
    "RateLimiterConfig",
    "get_spotify_limiter",
    "get_deezer_limiter",
    "get_musicbrainz_limiter",
]
