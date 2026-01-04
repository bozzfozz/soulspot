"""Custom exception handlers for FastAPI application.

This module registers global exception handlers that convert domain exceptions
and validation errors into proper HTTP responses with appropriate status codes.

Hey future me - we also handle SQLAlchemy OperationalError here! When the database
is busy/locked (e.g., during heavy background sync), instead of showing an ugly
Starlette error page, we show a friendly loading page that auto-retries. This
provides a much better UX than "database is locked" errors!
"""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from soulspot.domain.exceptions import (
    # New exception names (Dec 2025)
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolation,
    ConfigurationError,
    # Old exception names (kept for backwards compatibility)
    DuplicateEntityException,
    EntityNotFoundException,
    ExternalServiceError,
    InvalidStateException,
    RateLimitExceededError,
    ValidationError,
    ValidationException,
)

logger = logging.getLogger(__name__)


# Hey future me - this helper converts bytes to strings in validation error dicts!
# Pydantic's exc.errors() can include raw request body as bytes in the 'input' field,
# which causes "TypeError: Object of type bytes is not JSON serializable" when we
# try to return it in a JSONResponse. We recursively walk the error structure and
# decode any bytes we find. Also handles nested dicts and lists. Called from
# request_validation_exception_handler before building the JSON response.
def _sanitize_validation_errors(
    errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sanitize validation errors by converting bytes to strings.

    Args:
        errors: List of validation error dictionaries from Pydantic

    Returns:
        Sanitized list where bytes are converted to strings
    """

    def _sanitize_value(value: Any) -> Any:
        """Recursively sanitize a value, converting bytes to strings."""
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.decode("latin-1")
        elif isinstance(value, dict):
            return {k: _sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_sanitize_value(item) for item in value]
        elif isinstance(value, tuple):
            return tuple(_sanitize_value(item) for item in value)
        return value

    return [_sanitize_value(error) for error in errors]


# Hey future me, this registers GLOBAL exception handlers for the entire app! FastAPI will call
# these whenever matching exceptions are raised in ANY endpoint. We convert domain exceptions
# (ValidationException, EntityNotFoundException, etc.) into proper HTTP responses with correct
# status codes. Without this, domain exceptions would leak as 500 errors with stack traces to
# clients! The @app.exception_handler decorator MUST be called during app setup BEFORE any
# requests arrive. Don't try to register handlers after app starts - won't work!
def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers for domain and validation exceptions.

    This function registers handlers for:
    - Domain exceptions (ValidationException, EntityNotFoundException, etc.)
    - Pydantic validation errors (RequestValidationError)
    - JSON decode errors
    - Standard Python ValueError
    - HTTP exceptions with proper logging

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(ValidationException)
    async def validation_exception_handler(
        request: Request, exc: ValidationException
    ) -> JSONResponse:
        """Handle domain validation exceptions with 422 Unprocessable Entity."""
        logger.warning(
            "Validation error at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.message},
        )

    @app.exception_handler(EntityNotFoundException)
    async def entity_not_found_exception_handler(
        request: Request, exc: EntityNotFoundException
    ) -> JSONResponse:
        """Handle entity not found exceptions with 404 Not Found."""
        logger.info(
            "Entity not found at %s: %s %s",
            request.url.path,
            exc.entity_type,
            exc.entity_id,
            extra={
                "path": request.url.path,
                "entity_type": exc.entity_type,
                "entity_id": exc.entity_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message},
        )

    @app.exception_handler(DuplicateEntityException)
    async def duplicate_entity_exception_handler(
        request: Request, exc: DuplicateEntityException
    ) -> JSONResponse:
        """Handle duplicate entity exceptions with 409 Conflict."""
        logger.warning(
            "Duplicate entity at %s: %s %s",
            request.url.path,
            exc.entity_type,
            exc.entity_id,
            extra={
                "path": request.url.path,
                "entity_type": exc.entity_type,
                "entity_id": exc.entity_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message},
        )

    @app.exception_handler(InvalidStateException)
    async def invalid_state_exception_handler(
        request: Request, exc: InvalidStateException
    ) -> JSONResponse:
        """Handle invalid state exceptions with 400 Bad Request."""
        logger.warning(
            "Invalid state at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic request validation errors with 422 Unprocessable Entity.

        Hey future me - this handler converts validation errors to JSON responses.
        IMPORTANT: exc.errors() can contain bytes objects (e.g., raw request body)
        which are NOT JSON-serializable! We must sanitize them first by converting
        bytes to strings. Without this, you get "TypeError: Object of type bytes
        is not JSON serializable" which crashes the error response itself!
        """
        # Sanitize errors - convert bytes to strings for JSON serialization
        # Note: exc.errors() returns Sequence[Any] but is always a list in practice
        sanitized_errors = _sanitize_validation_errors(list(exc.errors()))

        logger.warning(
            "Request validation error at %s: %s",
            request.url.path,
            sanitized_errors,
            extra={"path": request.url.path, "errors": sanitized_errors},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": sanitized_errors},
        )

    @app.exception_handler(json.JSONDecodeError)
    async def json_decode_error_handler(
        request: Request, exc: json.JSONDecodeError
    ) -> JSONResponse:
        """Handle malformed JSON with 400 Bad Request."""
        logger.warning(
            "Malformed JSON at %s: %s",
            request.url.path,
            str(exc),
            extra={"path": request.url.path, "error": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Malformed JSON: {exc.msg}"},
        )

    @app.exception_handler(ValueError)
    async def value_error_exception_handler(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        """Handle ValueError with 422 Unprocessable Entity for validation-related errors."""
        logger.warning(
            "Value error at %s: %s",
            request.url.path,
            str(exc),
            extra={"path": request.url.path, "error": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle HTTP exceptions with proper logging."""
        if exc.status_code >= 500:
            logger.error(
                "HTTP error %d at %s: %s",
                exc.status_code,
                request.url.path,
                exc.detail,
                extra={
                    "path": request.url.path,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
        else:
            logger.info(
                "HTTP error %d at %s: %s",
                exc.status_code,
                request.url.path,
                exc.detail,
                extra={
                    "path": request.url.path,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # =========================================================================
    # New Exception Handlers (Dec 2025)
    # These provide proper HTTP status codes for the new domain exceptions.
    # =========================================================================

    @app.exception_handler(BusinessRuleViolation)
    async def business_rule_violation_handler(
        request: Request, exc: BusinessRuleViolation
    ) -> JSONResponse:
        """Handle business rule violations with 400 Bad Request."""
        logger.warning(
            "Business rule violation at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        """Handle validation errors with 422 Unprocessable Entity."""
        logger.warning(
            "Validation error at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.message},
        )

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(
        request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        """Handle configuration errors with 503 Service Unavailable."""
        logger.error(
            "Configuration error at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": exc.message},
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        """Handle authentication errors with 401 Unauthorized."""
        logger.warning(
            "Authentication error at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": exc.message},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        """Handle authorization errors with 403 Forbidden."""
        logger.warning(
            "Authorization error at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": exc.message},
        )

    @app.exception_handler(ExternalServiceError)
    async def external_service_error_handler(
        request: Request, exc: ExternalServiceError
    ) -> JSONResponse:
        """Handle external service errors with 502 Bad Gateway."""
        logger.error(
            "External service error at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": exc.message},
        )

    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_exceeded_handler(
        request: Request, exc: RateLimitExceededError
    ) -> JSONResponse:
        """Handle rate limit errors with 429 Too Many Requests."""
        logger.warning(
            "Rate limit exceeded at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": exc.message},
        )

    # =========================================================================
    # Database Busy/Locked Handler (Jan 2025)
    # Shows a friendly loading page instead of Starlette error when DB is busy.
    # =========================================================================

    # Hey future me - we need templates for the loading page. Initialize here
    # instead of at module level to avoid import order issues.
    _templates_dir = Path(__file__).parent.parent / "templates"
    _db_templates = Jinja2Templates(directory=str(_templates_dir))

    @app.exception_handler(OperationalError)
    async def database_operational_error_handler(
        request: Request, exc: OperationalError
    ) -> Response:
        """Handle SQLAlchemy OperationalError with special handling for DB busy/locked.

        Hey future me - when the database is busy (locked by background workers like
        Spotify sync, download processing, etc.), we show a friendly loading page
        instead of the ugly Starlette debug page. The loading page auto-retries after
        a few seconds, providing a much better UX!

        For HTMX requests, we return a partial that swaps in-place and retries.
        For normal requests, we return a full loading page.

        Other OperationalErrors (connection failed, etc.) still get 500 errors.
        """
        error_msg = str(exc).lower()

        # Check if this is a "database locked" or "database busy" error
        if "locked" in error_msg or "busy" in error_msg:
            logger.warning(
                "Database busy at %s - showing loading page (will auto-retry)",
                request.url.path,
                extra={"path": request.url.path, "error": str(exc)[:200]},
            )

            retry_url = str(request.url)
            retry_after = 3  # seconds

            # HTMX request? Return a partial that retries automatically
            if request.headers.get("HX-Request"):
                return _db_templates.TemplateResponse(
                    request,
                    "partials/db_loading.html",
                    context={
                        "retry_url": retry_url,
                        "retry_after": retry_after,
                        "message": "Datenbank beschäftigt",
                    },
                    status_code=200,  # 200 so HTMX swaps the content!
                    headers={
                        "HX-Trigger": "dbBusy",
                        "HX-Retarget": "this",
                        "HX-Reswap": "outerHTML",
                    },
                )

            # Normal request? Return full loading page
            return _db_templates.TemplateResponse(
                request,
                "db_loading.html",
                context={
                    "retry_url": retry_url,
                    "retry_after": retry_after,
                    "message": "Datenbank wird aktualisiert",
                },
                status_code=503,
                headers={"Retry-After": str(retry_after)},
            )

        # Other database errors (connection failed, etc.) - return 500
        logger.error(
            "Database error at %s: %s",
            request.url.path,
            str(exc)[:500],
            extra={"path": request.url.path, "error": str(exc)[:500]},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Database error occurred. Please try again."},
        )
