"""Shared HTTP client pool for connection reuse across services.

Hey future me - this is the CENTRAL http client pool! Instead of creating new httpx.AsyncClient
instances everywhere (which wastes TCP connections and ignores keep-alive), services should use
this shared pool. The pool manages connection limits, keep-alive, and proper cleanup.

Benefits:
- Connection reuse via keep-alive (faster subsequent requests)
- Controlled concurrency (max_connections prevents overwhelming APIs)
- Single cleanup point at app shutdown
- Consistent timeout and retry configuration

Usage in services:
    from soulspot.infrastructure.integrations.http_pool import HttpClientPool

    client = await HttpClientPool.get_client()
    response = await client.get("https://api.example.com/data")

Don't forget to call HttpClientPool.close() at app shutdown (see lifecycle.py)!
"""

import asyncio
import logging
from typing import ClassVar

import httpx

logger = logging.getLogger(__name__)


class HttpClientPool:
    """Singleton HTTP client pool for connection reuse.

    This class manages a shared httpx.AsyncClient instance that's reused across
    all services, enabling TCP connection pooling and keep-alive.

    Features:
    - Lazy initialization (created on first use)
    - Thread-safe via asyncio.Lock
    - Configurable limits (connections, timeouts)
    - Proper cleanup at shutdown
    """

    # Hey future me, these are CLASS VARIABLES (shared across all instances/calls)!
    # _client is the singleton AsyncClient. _lock ensures thread-safe initialization.
    # _initialized tracks if we've set up the client (avoids race conditions on first use).
    _client: ClassVar[httpx.AsyncClient | None] = None
    _lock: ClassVar[asyncio.Lock | None] = None
    _initialized: ClassVar[bool] = False

    # Default configuration - adjust based on your API rate limits!
    # max_keepalive_connections: How many idle connections to keep open
    # max_connections: Total concurrent connections (active + idle)
    # If you hit rate limits, LOWER max_connections. If requests are slow, RAISE it.
    DEFAULT_TIMEOUT: ClassVar[float] = 30.0
    DEFAULT_MAX_KEEPALIVE: ClassVar[int] = 20
    DEFAULT_MAX_CONNECTIONS: ClassVar[int] = 50

    @classmethod
    async def _ensure_lock(cls) -> asyncio.Lock:
        """Ensure lock exists (lazy initialization for event loop safety).

        Why lazy? Because asyncio.Lock() needs an active event loop. If we create
        it at class definition time, there might not be a loop yet. This pattern
        ensures the lock is created in the right event loop context.
        """
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    async def get_client(
        cls,
        timeout: float | None = None,
        max_keepalive: int | None = None,
        max_connections: int | None = None,
    ) -> httpx.AsyncClient:
        """Get the shared HTTP client instance.

        Creates the client on first call with the provided configuration.
        Subsequent calls return the same instance (ignoring new config values).

        Args:
            timeout: Request timeout in seconds (default: 30.0)
            max_keepalive: Max idle connections to keep open (default: 20)
            max_connections: Max total concurrent connections (default: 50)

        Returns:
            Shared httpx.AsyncClient instance

        Note:
            Config params only apply on FIRST call. If you need different configs
            for different use cases, consider separate client pools.
        """
        lock = await cls._ensure_lock()

        async with lock:
            if cls._client is None:
                # First initialization - apply configuration
                effective_timeout = timeout or cls.DEFAULT_TIMEOUT
                effective_keepalive = max_keepalive or cls.DEFAULT_MAX_KEEPALIVE
                effective_max_conn = max_connections or cls.DEFAULT_MAX_CONNECTIONS

                cls._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(effective_timeout),
                    limits=httpx.Limits(
                        max_keepalive_connections=effective_keepalive,
                        max_connections=effective_max_conn,
                    ),
                    # Enable HTTP/2 for APIs that support it (better multiplexing)
                    http2=True,
                    # Follow redirects automatically (common for CDNs)
                    follow_redirects=True,
                )
                cls._initialized = True
                logger.info(
                    "HTTP client pool initialized (timeout=%.1fs, keepalive=%d, max_conn=%d)",
                    effective_timeout,
                    effective_keepalive,
                    effective_max_conn,
                )

            return cls._client

    @classmethod
    async def close(cls) -> None:
        """Close the shared HTTP client and release all connections.

        Call this during application shutdown to properly close TCP connections.
        After calling close(), get_client() will create a new client instance.
        """
        lock = await cls._ensure_lock()

        async with lock:
            if cls._client is not None:
                await cls._client.aclose()
                cls._client = None
                cls._initialized = False
                logger.info("HTTP client pool closed")

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the client pool has been initialized.

        Useful for health checks and debugging.
        """
        return cls._initialized

    @classmethod
    async def get_pool_stats(cls) -> dict:
        """Get current connection pool statistics.

        Returns:
            Dict with pool status information for monitoring/debugging
        """
        if cls._client is None:
            return {
                "initialized": False,
                "active_connections": 0,
                "idle_connections": 0,
            }

        # httpx doesn't expose detailed pool stats, but we can check basic state
        pool = (
            cls._client._transport._pool if hasattr(cls._client, "_transport") else None
        )

        return {
            "initialized": True,
            "http2_enabled": cls._client._http2,
            "timeout": cls._client.timeout.connect,
            "max_connections": cls.DEFAULT_MAX_CONNECTIONS,
            "max_keepalive": cls.DEFAULT_MAX_KEEPALIVE,
            # Note: Detailed connection counts require internal httpx access
            "pool_available": pool is not None,
        }
