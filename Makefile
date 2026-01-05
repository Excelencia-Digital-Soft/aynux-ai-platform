.PHONY: dev run test lint format check clean

# Development server with hot reload
dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Production-like run (no reload)
run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8080

# Run tests
test:
	uv run pytest -v

# Run tests with coverage
test-cov:
	uv run pytest --cov=app --cov-report=html --cov-report=term

# Linting
lint:
	uv run ruff check app

# Format code
format:
	uv run black app && uv run isort app

# Type checking
typecheck:
	uv run pyright

# Full quality check (format + lint + typecheck)
check: format lint typecheck

# Clean generated files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

# Database migrations
migrate:
	uv run alembic upgrade head

# Create new migration
migration:
	@read -p "Migration message: " msg; \
	uv run alembic revision --autogenerate -m "$$msg"
