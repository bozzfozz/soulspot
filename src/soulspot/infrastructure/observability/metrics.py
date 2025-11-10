"""Prometheus metrics collection and exposition."""

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Default registry instance
_metrics_registry: CollectorRegistry | None = None


def get_metrics_registry() -> CollectorRegistry:
    """Get the metrics registry instance.

    Returns:
        Prometheus metrics registry
    """
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = REGISTRY
    return _metrics_registry


# HTTP Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=get_metrics_registry(),
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    registry=get_metrics_registry(),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method", "endpoint"],
    registry=get_metrics_registry(),
)

# Business metrics - Downloads
downloads_started_total = Counter(
    "downloads_started_total",
    "Total number of downloads started",
    ["source"],
    registry=get_metrics_registry(),
)

downloads_completed_total = Counter(
    "downloads_completed_total",
    "Total number of downloads completed",
    ["source", "status"],
    registry=get_metrics_registry(),
)

downloads_failed_total = Counter(
    "downloads_failed_total",
    "Total number of failed downloads",
    ["source", "reason"],
    registry=get_metrics_registry(),
)

downloads_in_progress = Gauge(
    "downloads_in_progress",
    "Number of downloads currently in progress",
    registry=get_metrics_registry(),
)

download_duration_seconds = Histogram(
    "download_duration_seconds",
    "Download duration in seconds",
    ["source"],
    registry=get_metrics_registry(),
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
)

# Business metrics - Playlist imports
playlist_imports_total = Counter(
    "playlist_imports_total",
    "Total number of playlist imports",
    ["source"],
    registry=get_metrics_registry(),
)

playlist_tracks_imported_total = Counter(
    "playlist_tracks_imported_total",
    "Total number of tracks imported from playlists",
    ["source"],
    registry=get_metrics_registry(),
)

# Business metrics - API calls
external_api_calls_total = Counter(
    "external_api_calls_total",
    "Total external API calls",
    ["service", "endpoint", "status"],
    registry=get_metrics_registry(),
)

external_api_call_duration_seconds = Histogram(
    "external_api_call_duration_seconds",
    "External API call duration in seconds",
    ["service", "endpoint"],
    registry=get_metrics_registry(),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

external_api_errors_total = Counter(
    "external_api_errors_total",
    "Total external API errors",
    ["service", "endpoint", "error_type"],
    registry=get_metrics_registry(),
)

# Database metrics
database_connections_active = Gauge(
    "database_connections_active",
    "Number of active database connections",
    registry=get_metrics_registry(),
)

database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    registry=get_metrics_registry(),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

database_errors_total = Counter(
    "database_errors_total",
    "Total database errors",
    ["operation", "error_type"],
    registry=get_metrics_registry(),
)

# Job queue metrics
job_queue_length = Gauge(
    "job_queue_length",
    "Number of jobs in queue",
    ["queue_name"],
    registry=get_metrics_registry(),
)

jobs_processed_total = Counter(
    "jobs_processed_total",
    "Total number of jobs processed",
    ["queue_name", "status"],
    registry=get_metrics_registry(),
)

job_processing_duration_seconds = Histogram(
    "job_processing_duration_seconds",
    "Job processing duration in seconds",
    ["queue_name", "job_type"],
    registry=get_metrics_registry(),
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
)


def init_metrics() -> None:
    """Initialize metrics system.

    This function can be used to perform any necessary setup
    for the metrics system. Currently, metrics are initialized
    on import, so this is a placeholder for future use.
    """
    pass


def get_latest_metrics() -> bytes:
    """Get the latest metrics in Prometheus format.

    Returns:
        Metrics data in Prometheus text format
    """
    return generate_latest(get_metrics_registry())
