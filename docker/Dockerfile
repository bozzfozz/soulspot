# Multi-stage build for SoulSpot Bridge
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==2.2.1

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml poetry.lock README.md ./
COPY src/ ./src/

# Install dependencies (without dev dependencies)
RUN poetry config virtualenvs.create false && \
    poetry install --without dev --no-interaction --no-ansi

# Production stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gosu \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create app user (will be overridden by PUID/PGID at runtime)
RUN groupadd -g 1000 soulspot && \
    useradd -u 1000 -g soulspot -s /bin/bash -m soulspot

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Copy entrypoint script
COPY docker/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create volume mount points
RUN mkdir -p /downloads /music /config && \
    chown -R soulspot:soulspot /downloads /music /config /app

# Expose port
EXPOSE 8765

# Set environment variables with defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    API_HOST=0.0.0.0 \
    API_PORT=8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Use entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "soulspot.main:app", "--host", "0.0.0.0", "--port", "8765"]
