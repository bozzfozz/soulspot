"""Unit tests for RequestLoggingMiddleware."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from soulspot.infrastructure.observability.middleware import RequestLoggingMiddleware


class TestRequestLoggingMiddleware:
    """Test suite for RequestLoggingMiddleware."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a FastAPI app with middleware for testing."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware, log_request_body=False)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @app.post("/test")
        async def test_post_endpoint():
            return {"message": "post test"}

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_middleware_initialization_default(self):
        """Test middleware initialization with default parameters."""
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app=app)

        assert middleware.log_request_body is False
        assert isinstance(middleware, BaseHTTPMiddleware)

    def test_middleware_initialization_with_logging(self):
        """Test middleware initialization with request body logging enabled."""
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app=app, log_request_body=True)

        assert middleware.log_request_body is True

    def test_successful_request_logs_start_and_completion(self, client: TestClient):
        """Test that successful requests log start and completion."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            response = client.get("/test")

            assert response.status_code == 200
            assert response.json() == {"message": "test"}

            # Verify logger.info was called twice (start and completion)
            assert mock_logger.info.call_count == 2

            # Check first call (request started)
            first_call_args = mock_logger.info.call_args_list[0]
            assert "Request started" in first_call_args[0][0]
            assert first_call_args[1]["extra"]["method"] == "GET"
            assert first_call_args[1]["extra"]["path"] == "/test"

            # Check second call (request completed)
            second_call_args = mock_logger.info.call_args_list[1]
            assert "Request completed" in second_call_args[0][0]
            assert second_call_args[1]["extra"]["status_code"] == 200
            assert "duration_seconds" in second_call_args[1]["extra"]

    def test_request_with_correlation_id_header(self, client: TestClient):
        """Test request with X-Correlation-ID header."""
        with (
            patch(
                "soulspot.infrastructure.observability.middleware.set_correlation_id"
            ) as mock_set_correlation_id,
            patch(
                "soulspot.infrastructure.observability.middleware.get_correlation_id",
                return_value="test-correlation-id",
            ),
        ):
            response = client.get(
                "/test", headers={"X-Correlation-ID": "custom-correlation-id"}
            )

            assert response.status_code == 200

            # Verify correlation ID was set from header
            mock_set_correlation_id.assert_called_once_with("custom-correlation-id")

            # Verify response includes correlation ID header
            assert "X-Correlation-ID" in response.headers
            assert response.headers["X-Correlation-ID"] == "test-correlation-id"

    def test_request_without_correlation_id_header(self, client: TestClient):
        """Test request without X-Correlation-ID header generates one."""
        with (
            patch(
                "soulspot.infrastructure.observability.middleware.set_correlation_id"
            ) as mock_set_correlation_id,
            patch(
                "soulspot.infrastructure.observability.middleware.get_correlation_id",
                return_value="generated-correlation-id",
            ),
        ):
            response = client.get("/test")

            assert response.status_code == 200

            # Verify correlation ID was set (with None, which triggers generation)
            mock_set_correlation_id.assert_called_once_with(None)

            # Verify response includes correlation ID header
            assert "X-Correlation-ID" in response.headers
            assert response.headers["X-Correlation-ID"] == "generated-correlation-id"

    def test_request_logs_client_ip(self, client: TestClient):
        """Test that client IP is logged."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            client.get("/test")

            # Check first call (request started)
            first_call = mock_logger.info.call_args_list[0]
            assert "client_ip" in first_call[1]["extra"]
            # TestClient uses "testclient" as the host
            assert first_call[1]["extra"]["client_ip"] == "testclient"

    def test_request_logs_user_agent(self, client: TestClient):
        """Test that user agent is logged."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            client.get("/test", headers={"user-agent": "test-agent/1.0"})

            # Check first call (request started)
            first_call = mock_logger.info.call_args_list[0]
            assert first_call[1]["extra"]["user_agent"] == "test-agent/1.0"

    def test_request_logs_query_params(self, client: TestClient):
        """Test that query parameters are logged."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            client.get("/test?param1=value1&param2=value2")

            # Check first call (request started)
            first_call = mock_logger.info.call_args_list[0]
            query_params = first_call[1]["extra"]["query_params"]
            assert "param1=value1" in query_params
            assert "param2=value2" in query_params

    def test_request_measures_duration(self, client: TestClient):
        """Test that request duration is measured."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            client.get("/test")

            # Check second call (request completed)
            second_call = mock_logger.info.call_args_list[1]
            assert "duration_seconds" in second_call[1]["extra"]
            # Duration should be a small positive number
            duration = second_call[1]["extra"]["duration_seconds"]
            assert isinstance(duration, float)
            assert duration >= 0

    def test_error_request_logs_exception(self, client: TestClient):
        """Test that failed requests log exception details."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            # Make request to error endpoint (should raise exception)
            with pytest.raises(ValueError):
                client.get("/error")

            # Verify logger.exception was called
            assert mock_logger.exception.call_count == 1

            # Check exception log details
            exception_call = mock_logger.exception.call_args
            assert "Request failed: GET /error" in exception_call[0][0]
            assert exception_call[1]["extra"]["method"] == "GET"
            assert exception_call[1]["extra"]["path"] == "/error"
            assert "duration_seconds" in exception_call[1]["extra"]
            # Duration should be a small positive number
            duration = exception_call[1]["extra"]["duration_seconds"]
            assert isinstance(duration, float)
            assert duration >= 0
            assert exception_call[1]["extra"]["error_type"] == "ValueError"
            assert exception_call[1]["extra"]["error_message"] == "Test error"

    def test_post_request_logging(self, client: TestClient):
        """Test logging for POST requests."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            response = client.post("/test", json={"data": "test"})

            assert response.status_code == 200

            # Check first call (request started)
            first_call = mock_logger.info.call_args_list[0]
            assert first_call[1]["extra"]["method"] == "POST"
            assert first_call[1]["extra"]["path"] == "/test"

    def test_multiple_requests_independent_logging(self, client: TestClient):
        """Test that multiple requests are logged independently."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            # Make multiple requests
            client.get("/test")
            client.post("/test")
            client.get("/test?param=value")

            # Each request should log start and completion (2 logs per request)
            assert mock_logger.info.call_count == 6

    def test_request_without_client(self):
        """Test middleware handles requests without client information."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            # Create mock request without client
            mock_request = MagicMock(spec=Request)
            mock_request.method = "GET"
            mock_request.url.path = "/test"
            mock_request.client = None
            mock_request.headers.get = MagicMock(return_value=None)
            mock_request.query_params = {}

            middleware = RequestLoggingMiddleware(app=app)

            # Mock call_next
            async def mock_call_next(request):
                return Response(status_code=200)

            # Run dispatch
            import asyncio

            response = asyncio.run(middleware.dispatch(mock_request, mock_call_next))

            assert response.status_code == 200

            # Verify client_ip is "unknown"
            first_call = mock_logger.info.call_args_list[0]
            assert first_call[1]["extra"]["client_ip"] == "unknown"

    def test_request_without_user_agent(self, client: TestClient):
        """Test that requests without user-agent header are handled."""
        with patch(
            "soulspot.infrastructure.observability.middleware.logger"
        ) as mock_logger:
            # TestClient sets a default user-agent of "testclient"
            client.get("/test")

            # Check first call (request started)
            first_call = mock_logger.info.call_args_list[0]
            # TestClient provides "testclient" as default user agent
            assert "user_agent" in first_call[1]["extra"]
            # The middleware should handle missing user-agent with empty string,
            # but TestClient always provides one
            assert first_call[1]["extra"]["user_agent"] != ""


class TestRequestLoggingMiddlewareEdgeCases:
    """Test edge cases and special scenarios."""

    def test_middleware_with_log_request_body_enabled(self):
        """Test middleware initialization with request body logging enabled."""
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app=app, log_request_body=True)

        # This option is saved but not currently used in the middleware
        # In a future enhancement, this could log request bodies
        assert middleware.log_request_body is True

    def test_concurrent_requests_correlation_ids(self):
        """Test that concurrent requests maintain separate correlation IDs."""
        # This is a conceptual test - in practice, correlation IDs are managed
        # per-request context. The actual implementation uses contextvars.
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        client = TestClient(app)

        with patch(
            "soulspot.infrastructure.observability.middleware.get_correlation_id"
        ) as mock_get_correlation_id:
            mock_get_correlation_id.side_effect = ["id-1", "id-2", "id-3"]

            # Make multiple requests
            r1 = client.get("/test", headers={"X-Correlation-ID": "req-1"})
            r2 = client.get("/test", headers={"X-Correlation-ID": "req-2"})
            r3 = client.get("/test", headers={"X-Correlation-ID": "req-3"})

            # Each should have its own correlation ID in response
            assert r1.headers["X-Correlation-ID"] == "id-1"
            assert r2.headers["X-Correlation-ID"] == "id-2"
            assert r3.headers["X-Correlation-ID"] == "id-3"
