"""OpenTelemetry distributed tracing configuration."""

import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)


def configure_tracing(
    service_name: str = "soulspot-bridge",
    environment: str = "development",
    otlp_endpoint: str | None = None,
    enable_console_exporter: bool = False,
) -> TracerProvider:
    """Configure OpenTelemetry tracing.

    Args:
        service_name: Name of the service for tracing
        environment: Environment name (development, staging, production)
        otlp_endpoint: OTLP exporter endpoint (e.g., "http://localhost:4317")
                      If None, only console exporter will be used in dev mode
        enable_console_exporter: Enable console exporter for debugging

    Returns:
        Configured tracer provider
    """
    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.1.0",
            "deployment.environment": environment,
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter if endpoint is provided
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP trace exporter configured: {otlp_endpoint}")
        except Exception as e:
            logger.warning(f"Failed to configure OTLP exporter: {e}")

    # Add console exporter for development/debugging
    if enable_console_exporter or (not otlp_endpoint and environment == "development"):
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("Console trace exporter enabled")

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    logger.info(
        "Tracing configured",
        extra={
            "service_name": service_name,
            "environment": environment,
            "otlp_endpoint": otlp_endpoint,
        },
    )

    return provider


def instrument_fastapi(app: Any) -> None:
    """Instrument FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application instance
    """
    FastAPIInstrumentor.instrument_app(app)
    logger.info("FastAPI instrumented with OpenTelemetry")


def instrument_httpx() -> None:
    """Instrument HTTPX client with OpenTelemetry."""
    HTTPXClientInstrumentor().instrument()
    logger.info("HTTPX client instrumented with OpenTelemetry")


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance.

    Args:
        name: Name of the tracer (typically module name)

    Returns:
        OpenTelemetry tracer instance
    """
    return trace.get_tracer(name)
