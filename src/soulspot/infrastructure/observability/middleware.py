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

        # Log incoming request
        logger.info(
            f"Request started: {method} {path}",
            extra={
                "method": method,
                "path": path,
                "query_params": str(request.query_params),
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
            },
        )

        # Process request
        start_time = time.time()
        try:
            response = await call_next(request)

            # Log response
            duration = time.time() - start_time
            logger.info(
                f"Request completed: {method} {path} - {response.status_code}",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_seconds": duration,
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
