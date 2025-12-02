# Multi-stage build for SoulSpot Bridge
# Hey future me - Tailwind/npm was REMOVED because we use plain CSS in 
# /static/new-ui/css/ (main.css, components.css, variables.css).
# The Magic UI animations are in components.css - no build step needed!

FROM python:3.12-slim AS builder

# Hey future me – GIT_BRANCH allows building from a specific branch by cloning
# the repository, instead of using local files.
# If GIT_BRANCH is empty (default), local files are copied.
# If GIT_BRANCH is set, the repo is cloned and that branch is checked out.
# Example: docker build --build-arg GIT_BRANCH=develop .
ARG GIT_BRANCH=""
ARG GIT_REPO="https://github.com/bozzfozz/soulspot.git"

# Install build dependencies (git is always needed for poetry to detect version)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==2.2.1

# Set working directory
WORKDIR /build

# Copy local files first (always needed for COPY to work)
COPY pyproject.toml poetry.lock README.md ./
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY docker/ ./docker/

# Clone from repository if GIT_BRANCH is set, overwriting local files
# When GIT_BRANCH is set, we overwrite the locally copied files with those
# from the cloned branch. This allows building from any branch without
# needing to checkout locally first. Note: CSS has already been built in the
# css-builder stage (either from local files or from the cloned branch).
ARG GIT_BRANCH
ARG GIT_REPO
RUN if [ -n "${GIT_BRANCH}" ]; then \
        echo "=== Building from Git Branch ===" && \
        echo "Cloning branch '${GIT_BRANCH}' from ${GIT_REPO}..." && \
        git clone --depth 1 --branch "${GIT_BRANCH}" "${GIT_REPO}" /tmp/repo && \
        rm -rf ./* && \
        cp -r /tmp/repo/pyproject.toml /tmp/repo/poetry.lock /tmp/repo/README.md ./ && \
        cp -r /tmp/repo/src ./src && \
        cp -r /tmp/repo/alembic ./alembic && \
        cp /tmp/repo/alembic.ini ./ && \
        cp -r /tmp/repo/docker ./docker && \
        rm -rf /tmp/repo && \
        echo "=== Successfully cloned branch '${GIT_BRANCH}' ==="; \
    else \
        echo "=== Building from local files ==="; \
    fi

# Ensure static CSS files are included
RUN poetry config virtualenvs.create false && \
    poetry install --without dev --no-interaction --no-ansi --no-root

# Build and install the package as a wheel (non-editable)
RUN poetry build -f wheel && \
    pip install --no-cache-dir dist/*.whl

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

# Copy alembic migrations and configuration from builder (may be from git clone)
COPY --from=builder /build/alembic/ ./alembic/
COPY --from=builder /build/alembic.ini ./

# Copy entrypoint script from builder (may be from git clone)
COPY --from=builder /build/docker/docker-entrypoint.sh /usr/local/bin/
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
