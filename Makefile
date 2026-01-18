.PHONY: help install test test-unit test-integration test-all lint format clean docker-build docker-test

# Use bash and source venv for all commands
SHELL := /bin/bash
VENV := . venv/bin/activate

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	$(VENV) && pip install -r requirements.txt

install-dev:  ## Install development dependencies
	$(VENV) && pip install -r requirements.txt
	$(VENV) && pip install pytest pytest-cov black ruff mypy pre-commit

test:  ## Run all tests (unit + integration, excluding Notion)
	$(VENV) && REPOSITORY_TYPE=sqlite pytest tests/ -v -m "not notion"

test-unit:  ## Run unit tests only
	$(VENV) && pytest tests/test_domain/ tests/test_application/ -v

test-integration:  ## Run integration tests (SQLite only)
	$(VENV) && REPOSITORY_TYPE=sqlite pytest tests/test_integration/ -v -m "not notion"

test-notion:  ## Run Notion integration tests (requires credentials)
	$(VENV) && REPOSITORY_TYPE=notion pytest tests/test_integration/ -v -m "notion"

test-all:  ## Run all tests including Notion
	$(VENV) && pytest tests/ -v

test-fast:  ## Run tests without coverage (faster)
	$(VENV) && REPOSITORY_TYPE=sqlite pytest tests/ -v -m "not notion" --no-cov

test-watch:  ## Run tests in watch mode
	$(VENV) && REPOSITORY_TYPE=sqlite pytest-watch tests/ -v -m "not notion"

coverage:  ## Generate coverage report
	$(VENV) && pytest tests/ -v -m "not notion"
	@echo "Coverage report generated in htmlcov/index.html"

lint:  ## Run linters
	$(VENV) && black --check src/ tests/
	$(VENV) && ruff check src/ tests/
	$(VENV) && mypy src/

format:  ## Format code with black
	$(VENV) && black src/ tests/

fix:  ## Auto-fix linting issues
	$(VENV) && black src/ tests/
	$(VENV) && ruff check --fix src/ tests/

type-check:  ## Run type checking with mypy
	$(VENV) && mypy src/

clean:  ## Clean up generated files
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov/ .coverage coverage.xml
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.db" -delete

docker-build:  ## Build Docker image
	docker build -f docker/Dockerfile -t budget-notion:latest .

docker-test:  ## Test Docker image
	docker run --rm budget-notion:latest python -c "from src.domain.entities import Transaction; print('Docker image OK')"

docker-run:  ## Run Docker container interactively
	docker run -it --rm \
		-v $(PWD)/data:/app/data \
		--env-file .env \
		budget-notion:latest \
		/bin/bash

ci-test:  ## Run tests like CI pipeline
	@echo "=== Code Quality Checks ==="
	$(VENV) && black --check src/ tests/
	$(VENV) && ruff check src/ tests/
	@echo "\n=== Unit Tests ==="
	$(VENV) && pytest tests/test_domain/ tests/test_application/ -v
	@echo "\n=== Integration Tests ==="
	$(VENV) && REPOSITORY_TYPE=sqlite pytest tests/test_integration/ -v -m "not notion"
	@echo "\n=== Docker Build ==="
	docker build -f docker/Dockerfile -t budget-notion:test .
	@echo "\n✅ All CI checks passed!"

pre-commit:  ## Install pre-commit hooks
	$(VENV) && pre-commit install
	$(VENV) && pre-commit run --all-files

update-deps:  ## Update dependencies
	$(VENV) && pip install --upgrade pip
	$(VENV) && pip install --upgrade -r requirements.txt

requirements:  ## Regenerate requirements.txt from pyproject.toml
	pip-compile pyproject.toml -o requirements.txt

.DEFAULT_GOAL := help
