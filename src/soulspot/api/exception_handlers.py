"""Custom exception handlers for FastAPI application.

This module registers global exception handlers that convert domain exceptions
and validation errors into proper HTTP responses with appropriate status codes.
"""

import json
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from soulspot.domain.exceptions import (
    DuplicateEntityException,
    EntityNotFoundException,
    InvalidStateException,
    ValidationException,
)

logger = logging.getLogger(__name__)


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
        """Handle Pydantic request validation errors with 422 Unprocessable Entity."""
        logger.warning(
            "Request validation error at %s: %s",
            request.url.path,
            exc.errors(),
            extra={"path": request.url.path, "errors": exc.errors()},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
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
