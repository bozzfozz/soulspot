# Justfile for SoulSpot Bridge
# Alternative to Makefile using Just (https://github.com/casey/just)

# Show available recipes
default:
    @just --list

# Install dependencies with pip
install:
    pip install -r requirements.txt

# Run all tests
test:
    pytest tests/ -v

# Run unit tests only
test-unit:
    pytest tests/unit/ -v

# Run tests with coverage
test-cov:
    pytest tests/ --cov=src/soulspot --cov-report=html --cov-report=term

# Run linter (ruff check)
lint:
    ruff check src/ tests/

# Format code (ruff format)
format:
    ruff format src/ tests/

# Run type checker (mypy)
type-check:
    mypy src/soulspot

# Run security checks (bandit)
security:
    bandit -r src/soulspot

# Clean generated files
clean:
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name '*.pyc' -delete
    find . -type d -name .pytest_cache -exec rm -rf {} +
    find . -type d -name .ruff_cache -exec rm -rf {} +
    find . -type d -name .mypy_cache -exec rm -rf {} +
    rm -rf htmlcov/ .coverage

# Start Docker services
docker-up:
    docker-compose -f docker/docker-compose.yml up -d

# Stop Docker services
docker-down:
    docker-compose -f docker/docker-compose.yml down

# Show Docker logs
docker-logs:
    docker-compose -f docker/docker-compose.yml logs -f

# Run database migrations
db-upgrade:
    alembic upgrade head

# Rollback last database migration
db-downgrade:
    alembic downgrade -1

# Start development environment
dev: docker-up
    @echo "Development environment started!"
    @echo "SoulSpot Bridge UI: http://localhost:8765"
    @echo "Note: Ensure slskd is running on the host at http://localhost:5030"
