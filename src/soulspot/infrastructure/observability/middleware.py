"""Middleware for observability: logging, metrics, and tracing."""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from soulspot.infrastructure.observability.logging import (
    get_correlation_id,
    set_correlation_id,
)
from soulspot.infrastructure.observability.metrics import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
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


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting Prometheus metrics."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Collect metrics for request.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from application
        """
        method = request.method
        path = request.url.path

        # Skip metrics endpoint to avoid recursion
        if path == "/metrics":
            return await call_next(request)

        # Normalize path to avoid high cardinality
        # Replace IDs and dynamic segments with placeholders
        normalized_path = self._normalize_path(path)

        # Track request in progress
        http_requests_in_progress.labels(method=method, endpoint=normalized_path).inc()

        # Track request duration
        start_time = time.time()
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=normalized_path,
                status=response.status_code,
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=normalized_path,
            ).observe(duration)

            return response

        except Exception:
            duration = time.time() - start_time

            # Record error metrics
            http_requests_total.labels(
                method=method,
                endpoint=normalized_path,
                status=500,
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=normalized_path,
            ).observe(duration)

            raise

        finally:
            # Decrement in-progress counter
            http_requests_in_progress.labels(
                method=method, endpoint=normalized_path
            ).dec()

    def _normalize_path(self, path: str) -> str:
        """Normalize path to reduce cardinality.

        Args:
            path: Request path

        Returns:
            Normalized path with dynamic segments replaced
        """
        # Split path into segments
        segments = path.split("/")

        # Replace numeric segments and UUIDs with placeholders
        normalized = []
        for segment in segments:
            if not segment:
                continue

            # Check if segment is numeric (likely an ID)
            if segment.isdigit():
                normalized.append("{id}")
            # Check if segment looks like a UUID
            elif len(segment) == 36 and segment.count("-") == 4:
                normalized.append("{uuid}")
            else:
                normalized.append(segment)

        return "/" + "/".join(normalized) if normalized else path
