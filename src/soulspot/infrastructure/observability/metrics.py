"""Download System Metrics - Prometheus-compatible metrics.

Hey future me - this module provides METRICS for download system monitoring!

The metrics are exposed in Prometheus text format at /api/metrics endpoint.
Compatible with Prometheus, Grafana, and other monitoring tools.

METRIC TYPES:
- Counter: Cumulative values (total downloads, errors)
- Gauge: Point-in-time values (queue size, active downloads)
- Histogram: Distribution (download times, file sizes)

LABELS:
- status: Download status (completed, failed, cancelled)
- error_code: Error classification (timeout, file_not_found, etc.)
- format: Audio format (mp3, flac, etc.)

USE CASES:
1. Grafana dashboard showing download throughput
2. Alerting on high failure rates (> 10%)
3. Capacity planning based on queue depth
4. Performance analysis via download duration histograms

NOTE: We don't use prometheus_client library to keep dependencies minimal.
Instead we implement the text exposition format directly.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Single metric value with labels.

    Hey future me - this is ONE data point with its labels!
    """

    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MetricDefinition:
    """Metric definition with name, type, help text.

    Hey future me - defines a metric before recording values!
    """

    name: str
    type: str  # "counter", "gauge", "histogram"
    help: str
    labels: list[str] = field(default_factory=list)


class DownloadMetrics:
    """Prometheus-compatible metrics for download system.

    Hey future me - this is the CENTRAL metrics collector!

    Usage:
        metrics = DownloadMetrics()

        # Record metrics
        metrics.inc_downloads_total(status="completed")
        metrics.set_queue_size(42)
        metrics.observe_download_duration(15.5, format="flac")

        # Expose metrics
        text = metrics.to_prometheus_format()

    The to_prometheus_format() method returns text in Prometheus exposition format:
        # HELP soulspot_downloads_total Total number of downloads
        # TYPE soulspot_downloads_total counter
        soulspot_downloads_total{status="completed"} 123
        soulspot_downloads_total{status="failed"} 5
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._lock = Lock()
        self._prefix = "soulspot_download"

        # Define metrics
        self._definitions: dict[str, MetricDefinition] = {
            "total": MetricDefinition(
                name="total",
                type="counter",
                help="Total number of downloads",
                labels=["status"],
            ),
            "errors_total": MetricDefinition(
                name="errors_total",
                type="counter",
                help="Total number of download errors by code",
                labels=["error_code"],
            ),
            "retries_total": MetricDefinition(
                name="retries_total",
                type="counter",
                help="Total number of download retries",
            ),
            "queue_size": MetricDefinition(
                name="queue_size",
                type="gauge",
                help="Current number of downloads in queue",
                labels=["status"],
            ),
            "active": MetricDefinition(
                name="active",
                type="gauge",
                help="Number of currently active downloads",
            ),
            "duration_seconds": MetricDefinition(
                name="duration_seconds",
                type="histogram",
                help="Download duration in seconds",
                labels=["format"],
            ),
            "file_size_bytes": MetricDefinition(
                name="file_size_bytes",
                type="histogram",
                help="Downloaded file size in bytes",
                labels=["format"],
            ),
            "search_cache_hits": MetricDefinition(
                name="search_cache_hits",
                type="counter",
                help="Number of search cache hits",
            ),
            "search_cache_misses": MetricDefinition(
                name="search_cache_misses",
                type="counter",
                help="Number of search cache misses",
            ),
            "workers_running": MetricDefinition(
                name="workers_running",
                type="gauge",
                help="Number of workers running",
                labels=["worker_type"],
            ),
        }

        # Store metric values
        self._counters: dict[str, dict[str, float]] = {}
        self._gauges: dict[str, dict[str, float]] = {}
        self._histograms: dict[str, list[tuple[dict[str, str], float]]] = {}

        # Histogram buckets (in seconds for duration, bytes for file size)
        self._duration_buckets = [1, 5, 10, 30, 60, 120, 300, 600, float("inf")]
        self._size_buckets = [
            1024 * 1024,  # 1 MB
            5 * 1024 * 1024,  # 5 MB
            10 * 1024 * 1024,  # 10 MB
            25 * 1024 * 1024,  # 25 MB
            50 * 1024 * 1024,  # 50 MB
            100 * 1024 * 1024,  # 100 MB
            float("inf"),
        ]

    def _make_label_key(self, labels: dict[str, str]) -> str:
        """Create a sortable key from labels dict."""
        return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))

    # ==========================================================================
    # COUNTER METHODS
    # ==========================================================================

    def inc_downloads_total(self, status: str = "completed") -> None:
        """Increment total downloads counter.

        Args:
            status: Download status (completed, failed, cancelled)
        """
        with self._lock:
            key = self._make_label_key({"status": status})
            if "total" not in self._counters:
                self._counters["total"] = {}
            self._counters["total"][key] = self._counters["total"].get(key, 0) + 1

    def inc_errors_total(self, error_code: str) -> None:
        """Increment errors counter.

        Args:
            error_code: Error code (timeout, file_not_found, etc.)
        """
        with self._lock:
            key = self._make_label_key({"error_code": error_code})
            if "errors_total" not in self._counters:
                self._counters["errors_total"] = {}
            self._counters["errors_total"][key] = (
                self._counters["errors_total"].get(key, 0) + 1
            )

    def inc_retries_total(self) -> None:
        """Increment retries counter."""
        with self._lock:
            key = ""  # No labels
            if "retries_total" not in self._counters:
                self._counters["retries_total"] = {}
            self._counters["retries_total"][key] = (
                self._counters["retries_total"].get(key, 0) + 1
            )

    def inc_search_cache_hits(self) -> None:
        """Increment search cache hits counter."""
        with self._lock:
            key = ""
            if "search_cache_hits" not in self._counters:
                self._counters["search_cache_hits"] = {}
            self._counters["search_cache_hits"][key] = (
                self._counters["search_cache_hits"].get(key, 0) + 1
            )

    def inc_search_cache_misses(self) -> None:
        """Increment search cache misses counter."""
        with self._lock:
            key = ""
            if "search_cache_misses" not in self._counters:
                self._counters["search_cache_misses"] = {}
            self._counters["search_cache_misses"][key] = (
                self._counters["search_cache_misses"].get(key, 0) + 1
            )

    # ==========================================================================
    # GAUGE METHODS
    # ==========================================================================

    def set_queue_size(self, value: int, status: str = "waiting") -> None:
        """Set current queue size.

        Args:
            value: Number of items in queue
            status: Queue status filter (waiting, pending, downloading)
        """
        with self._lock:
            key = self._make_label_key({"status": status})
            if "queue_size" not in self._gauges:
                self._gauges["queue_size"] = {}
            self._gauges["queue_size"][key] = float(value)

    def set_active_downloads(self, value: int) -> None:
        """Set number of active downloads.

        Args:
            value: Number of active downloads
        """
        with self._lock:
            key = ""
            if "active" not in self._gauges:
                self._gauges["active"] = {}
            self._gauges["active"][key] = float(value)

    def set_workers_running(self, worker_type: str, value: int) -> None:
        """Set number of running workers.

        Args:
            worker_type: Type of worker (download, sync, cleanup)
            value: 1 if running, 0 if stopped
        """
        with self._lock:
            key = self._make_label_key({"worker_type": worker_type})
            if "workers_running" not in self._gauges:
                self._gauges["workers_running"] = {}
            self._gauges["workers_running"][key] = float(value)

    # ==========================================================================
    # HISTOGRAM METHODS
    # ==========================================================================

    def observe_download_duration(
        self, duration_seconds: float, audio_format: str = "unknown"
    ) -> None:
        """Record a download duration observation.

        Args:
            duration_seconds: How long the download took
            audio_format: Audio format (mp3, flac, etc.)
        """
        with self._lock:
            if "duration_seconds" not in self._histograms:
                self._histograms["duration_seconds"] = []
            self._histograms["duration_seconds"].append(
                ({"format": audio_format}, duration_seconds)
            )

    def observe_file_size(
        self, size_bytes: int, audio_format: str = "unknown"
    ) -> None:
        """Record a file size observation.

        Args:
            size_bytes: File size in bytes
            audio_format: Audio format (mp3, flac, etc.)
        """
        with self._lock:
            if "file_size_bytes" not in self._histograms:
                self._histograms["file_size_bytes"] = []
            self._histograms["file_size_bytes"].append(
                ({"format": audio_format}, float(size_bytes))
            )

    # ==========================================================================
    # PROMETHEUS EXPOSITION FORMAT
    # ==========================================================================

    def _format_labels(self, labels: dict[str, str]) -> str:
        """Format labels as Prometheus label string."""
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(parts) + "}"

    def _parse_label_key(self, key: str) -> dict[str, str]:
        """Parse label key back to dict."""
        if not key:
            return {}
        labels = {}
        for part in key.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                labels[k] = v
        return labels

    def to_prometheus_format(self) -> str:
        """Export all metrics in Prometheus text exposition format.

        Hey future me - this is what /api/metrics returns!

        Returns:
            Prometheus-formatted metrics text
        """
        lines = []

        with self._lock:
            # Export counters
            for metric_name, values in self._counters.items():
                defn = self._definitions.get(metric_name)
                if defn:
                    full_name = f"{self._prefix}_{defn.name}"
                    lines.append(f"# HELP {full_name} {defn.help}")
                    lines.append(f"# TYPE {full_name} counter")

                    for label_key, value in values.items():
                        labels = self._parse_label_key(label_key)
                        label_str = self._format_labels(labels)
                        lines.append(f"{full_name}{label_str} {value}")

            # Export gauges
            for metric_name, values in self._gauges.items():
                defn = self._definitions.get(metric_name)
                if defn:
                    full_name = f"{self._prefix}_{defn.name}"
                    lines.append(f"# HELP {full_name} {defn.help}")
                    lines.append(f"# TYPE {full_name} gauge")

                    for label_key, value in values.items():
                        labels = self._parse_label_key(label_key)
                        label_str = self._format_labels(labels)
                        lines.append(f"{full_name}{label_str} {value}")

            # Export histograms (simplified - just _count and _sum)
            for metric_name, observations in self._histograms.items():
                defn = self._definitions.get(metric_name)
                if defn:
                    full_name = f"{self._prefix}_{defn.name}"
                    lines.append(f"# HELP {full_name} {defn.help}")
                    lines.append(f"# TYPE {full_name} histogram")

                    # Group by labels
                    by_labels: dict[str, list[float]] = {}
                    for labels, value in observations:
                        key = self._make_label_key(labels)
                        if key not in by_labels:
                            by_labels[key] = []
                        by_labels[key].append(value)

                    for label_key, values_list in by_labels.items():
                        labels = self._parse_label_key(label_key)
                        label_str = self._format_labels(labels)

                        # Calculate histogram stats
                        count = len(values_list)
                        total = sum(values_list)

                        lines.append(f"{full_name}_count{label_str} {count}")
                        lines.append(f"{full_name}_sum{label_str} {total}")

        return "\n".join(lines) + "\n"

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary as JSON.

        Hey future me - alternative to Prometheus format for simple display!
        """
        with self._lock:
            return {
                "counters": {
                    name: dict(values) for name, values in self._counters.items()
                },
                "gauges": {name: dict(values) for name, values in self._gauges.items()},
                "histograms": {
                    name: {
                        "count": len(obs),
                        "sum": sum(v for _, v in obs),
                    }
                    for name, obs in self._histograms.items()
                },
            }


# =============================================================================
# GLOBAL METRICS INSTANCE
# =============================================================================

_download_metrics: DownloadMetrics | None = None


def get_download_metrics() -> DownloadMetrics:
    """Get the global metrics instance.

    Hey future me - creates on first call (lazy init)!
    """
    global _download_metrics
    if _download_metrics is None:
        _download_metrics = DownloadMetrics()
    return _download_metrics


def reset_download_metrics() -> None:
    """Reset the global metrics (for testing)."""
    global _download_metrics
    _download_metrics = None
