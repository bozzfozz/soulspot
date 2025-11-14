.PHONY: help install test lint format type-check security clean docker-up docker-down

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with pip
	pip install -r requirements.txt

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-cov: ## Run tests with coverage
	pytest tests/ --cov=src/soulspot --cov-report=html --cov-report=term

lint: ## Run linter (ruff check)
	ruff check src/ tests/

format: ## Format code (ruff format)
	ruff format src/ tests/

type-check: ## Run type checker (mypy)
	mypy src/soulspot

security: ## Run security checks (bandit)
	bandit -r src/soulspot

clean: ## Clean generated files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	rm -rf htmlcov/ .coverage

docker-up: ## Start Docker services
	docker-compose -f docker/docker-compose.yml up -d

docker-down: ## Stop Docker services
	docker-compose -f docker/docker-compose.yml down

docker-logs: ## Show Docker logs
	docker-compose -f docker/docker-compose.yml logs -f

db-upgrade: ## Run database migrations
	alembic upgrade head

db-downgrade: ## Rollback last database migration
	alembic downgrade -1

dev: docker-up ## Start development environment
	@echo "Development environment started!"
	@echo "slskd UI: http://localhost:5030"
