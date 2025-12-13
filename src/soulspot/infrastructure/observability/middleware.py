"""Middleware for observability: request/response logging."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from soulspot.infrastructure.observability.logging import (
    get_correlation_id,
    set_correlation_id,
)

logger = logging.getLogger(__name__)


# Hey future me, this middleware logs EVERY HTTP request/response! It runs BEFORE your route
# handlers. We extend BaseHTTPMiddleware which handles the FastAPI integration magic. The
# log_request_body param is OFF by default - turn it on for debugging but NEVER in production
# (huge log volume, potential secrets in POST bodies!). This middleware is stateless - safe for
# concurrent requests. Add it early in middleware stack so it catches everything!
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    def __init__(self, app: ASGIApp, log_request_body: bool = False) -> None:
        """Initialize middleware.

        Args:
            app: ASGI application
            log_request_body: Whether to log request body (can be verbose)
        """
        super().__init__(app)
        self.log_request_body = log_request_body

    # Yo, this dispatch() is THE request/response interceptor! Flow: 1) Extract correlation_id from
    # header (or generate one), 2) Set it in context so ALL logs for this request inherit it,
    # 3) Log request details, 4) Call next middleware/route handler, 5) Log response + duration,
    # 6) Add correlation_id to response header so client can reference it. The time.time() calls
    # measure TOTAL request duration including middleware overhead - useful for performance tracking!
    # We catch exceptions to log them with full context before re-raising. The client_ip extraction
    # handles proxies (request.client might be None if behind load balancer). The response.headers
    # modification adds correlation_id for client-side debugging (they can include it in support tickets!).
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and log details.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from application
        """
        # Set correlation ID from header or generate new one
        correlation_id = request.headers.get("X-Correlation-ID")
        set_correlation_id(correlation_id)

        # Get request details
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # Hey future me - we don't log "Request started" for static files!
        # It clutters logs. Only log actual API/page requests.
        is_static = path.startswith("/static/")

        if not is_static:
            logger.info(
                f"→ {method} {path}",
                extra={
                    "method": method,
                    "path": path,
                    "query_params": str(request.query_params),
                    "client_ip": client_ip,
                },
            )

        # Process request
        start_time = time.time()
        try:
            response = await call_next(request)

            # Log response (skip static files)
            duration = time.time() - start_time
            if not is_static:
                status_emoji = "✓" if response.status_code < 400 else "✗"
                logger.info(
                    f"{status_emoji} {method} {path} → {response.status_code} ({duration:.0f}ms)",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "duration_ms": int(duration * 1000),
                    },
                )

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = get_correlation_id()

            return response

        except Exception as e:
            # Log error with full context
            duration = time.time() - start_time
            logger.exception(
                f"Request failed: {method} {path}",
                extra={
                    "method": method,
                    "path": path,
                    "duration_seconds": duration,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            raise
