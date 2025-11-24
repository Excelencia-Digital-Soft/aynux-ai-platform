#!/bin/bash

# ============================================================================
# Aynux Pytest Runner Script
# ============================================================================
#
# This script provides various pytest testing commands for the Aynux project.
#
# Usage:
#   ./run_pytest.sh [command]
#
# Commands:
#   all         - Run all tests (unit + integration)
#   unit        - Run only unit tests
#   integration - Run only integration tests
#   coverage    - Run tests with coverage report
#   markers     - Show available test markers
#   lint        - Run linting and type checking
#   format      - Format code with black and isort
#   quick       - Run quick smoke tests
#   failed      - Re-run only failed tests
#
# Examples:
#   ./run_pytest.sh unit
#   ./run_pytest.sh coverage
#   ./run_pytest.sh lint
#
# ============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored messages
print_header() {
    echo -e "${GREEN}===================================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}===================================================${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Ensure we're using uv
command -v uv >/dev/null 2>&1 || {
    print_error "uv is not installed. Please install uv first."
    exit 1
}

# Default command
COMMAND="${1:-all}"

case "$COMMAND" in
    all)
        print_header "Running All Tests"
        uv run pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing
        print_info "Coverage report generated in htmlcov/index.html"
        ;;

    unit)
        print_header "Running Unit Tests"
        uv run pytest tests/unit/ -v -m unit
        ;;

    integration)
        print_header "Running Integration Tests"
        uv run pytest tests/integration/ -v -m integration
        ;;

    coverage)
        print_header "Running Tests with Coverage"
        uv run pytest tests/ -v \
            --cov=app \
            --cov-report=html:htmlcov \
            --cov-report=term-missing \
            --cov-report=xml:coverage.xml \
            --cov-branch

        print_info "HTML coverage report: htmlcov/index.html"
        print_info "XML coverage report: coverage.xml"
        ;;

    markers)
        print_header "Available Test Markers"
        uv run pytest --markers
        ;;

    lint)
        print_header "Running Linters and Type Checking"

        print_info "Running pyright type checking..."
        uv run pyright app/ || true

        print_info "Running black format check..."
        uv run black --check app/

        print_info "Running isort import check..."
        uv run isort --check-only app/

        print_info "Running ruff linting..."
        uv run ruff check app/

        print_header "Linting Complete"
        ;;

    format)
        print_header "Formatting Code"

        print_info "Running black formatter..."
        uv run black app/

        print_info "Running isort import sorter..."
        uv run isort app/

        print_info "Running ruff auto-fix..."
        uv run ruff check app/ --fix

        print_header "Formatting Complete"
        ;;

    quick)
        print_header "Running Quick Smoke Tests"
        uv run pytest tests/unit/ -v -m "smoke or use_case" --maxfail=5
        ;;

    failed)
        print_header "Re-running Failed Tests"
        uv run pytest tests/ -v --lf
        ;;

    use-case)
        print_header "Running Use Case Tests"
        uv run pytest tests/ -v -m use_case
        ;;

    repository)
        print_header "Running Repository Tests"
        uv run pytest tests/ -v -m repository
        ;;

    clean)
        print_header "Cleaning Test Artifacts"
        rm -rf htmlcov/
        rm -rf .coverage
        rm -rf coverage.xml
        rm -rf .pytest_cache/
        rm -rf .ruff_cache/
        print_info "Cleaned test artifacts"
        ;;

    help|--help|-h)
        cat << EOF
Aynux Pytest Runner

Usage: ./run_pytest.sh [command]

Commands:
  all         - Run all tests (unit + integration)
  unit        - Run only unit tests
  integration - Run only integration tests
  coverage    - Run tests with full coverage report
  markers     - Show available test markers
  lint        - Run all linters and type checking
  format      - Auto-format code with black, isort, ruff
  quick       - Run quick smoke tests
  failed      - Re-run only previously failed tests
  use-case    - Run Use Case tests only
  repository  - Run Repository tests only
  clean       - Clean test artifacts and caches
  help        - Show this help message

Examples:
  ./run_pytest.sh unit              # Run unit tests
  ./run_pytest.sh coverage          # Generate coverage report
  ./run_pytest.sh lint              # Check code quality
  ./run_pytest.sh format            # Format code
  ./run_pytest.sh use-case          # Run use case tests

For more information, see docs/TESTING_GUIDE.md
EOF
        ;;

    *)
        print_error "Unknown command: $COMMAND"
        print_info "Run './run_pytest.sh help' for usage information"
        exit 1
        ;;
esac
