"""Tests for metrics collection."""


from soulspot.infrastructure.observability.metrics import (
    downloads_completed_total,
    downloads_started_total,
    external_api_calls_total,
    get_latest_metrics,
    http_request_duration_seconds,
    http_requests_total,
    init_metrics,
    playlist_imports_total,
)


class TestMetricsInitialization:
    """Test metrics initialization."""

    def test_init_metrics(self):
        """Test metrics initialization."""
        # Should not raise any errors
        init_metrics()

    def test_get_latest_metrics(self):
        """Test getting latest metrics."""
        metrics = get_latest_metrics()
        assert metrics is not None
        assert isinstance(metrics, bytes)
        # Should contain prometheus format
        assert b"# HELP" in metrics or b"# TYPE" in metrics


class TestHTTPMetrics:
    """Test HTTP metrics."""

    def test_http_requests_total_counter(self):
        """Test HTTP requests total counter."""
        before = http_requests_total.labels(
            method="GET", endpoint="/test", status="200"
        )._value.get()

        http_requests_total.labels(method="GET", endpoint="/test", status="200").inc()

        after = http_requests_total.labels(
            method="GET", endpoint="/test", status="200"
        )._value.get()

        assert after > before

    def test_http_request_duration_histogram(self):
        """Test HTTP request duration histogram."""
        http_request_duration_seconds.labels(method="GET", endpoint="/test").observe(
            0.5
        )
        http_request_duration_seconds.labels(method="GET", endpoint="/test").observe(
            1.0
        )

        # Should not raise errors
        metrics = get_latest_metrics()
        assert b"http_request_duration_seconds" in metrics


class TestBusinessMetrics:
    """Test business metrics."""

    def test_downloads_started_total(self):
        """Test downloads started counter."""
        before = downloads_started_total.labels(source="slskd")._value.get()
        downloads_started_total.labels(source="slskd").inc()
        after = downloads_started_total.labels(source="slskd")._value.get()
        assert after > before

    def test_downloads_completed_total(self):
        """Test downloads completed counter."""
        before = downloads_completed_total.labels(
            source="slskd", status="success"
        )._value.get()
        downloads_completed_total.labels(source="slskd", status="success").inc()
        after = downloads_completed_total.labels(
            source="slskd", status="success"
        )._value.get()
        assert after > before

    def test_playlist_imports_total(self):
        """Test playlist imports counter."""
        before = playlist_imports_total.labels(source="spotify")._value.get()
        playlist_imports_total.labels(source="spotify").inc()
        after = playlist_imports_total.labels(source="spotify")._value.get()
        assert after > before

    def test_external_api_calls_total(self):
        """Test external API calls counter."""
        before = external_api_calls_total.labels(
            service="spotify", endpoint="/tracks", status="200"
        )._value.get()
        external_api_calls_total.labels(
            service="spotify", endpoint="/tracks", status="200"
        ).inc()
        after = external_api_calls_total.labels(
            service="spotify", endpoint="/tracks", status="200"
        )._value.get()
        assert after > before


class TestMetricsEndpoint:
    """Test metrics endpoint output."""

    def test_metrics_output_format(self):
        """Test that metrics are in Prometheus format."""
        metrics = get_latest_metrics()

        # Verify Prometheus text format
        metrics_str = metrics.decode("utf-8")

        # Should contain metric definitions
        assert "http_requests_total" in metrics_str or "# TYPE" in metrics_str

    def test_metrics_contain_expected_metrics(self):
        """Test that metrics contain expected metric names."""
        # Record some metrics
        http_requests_total.labels(method="GET", endpoint="/test", status="200").inc()
        downloads_started_total.labels(source="test").inc()

        metrics = get_latest_metrics()
        metrics_str = metrics.decode("utf-8")

        # Verify presence of key metrics
        assert "http_requests_total" in metrics_str
        assert "downloads_started_total" in metrics_str
