## Project Overview

Aynux is an intelligent, multi-domain conversational AI platform built for WhatsApp Business. It uses specialized AI agents to handle different business domains (e-commerce, healthcare, finance) in a single unified system, with support for custom domain configuration and RAG-based knowledge.

**Core Technologies:**

*   Python 3.13+
*   FastAPI
*   LangGraph
*   Docker
*   PostgreSQL with pgvector
*   Redis
*   Ollama

**Architecture:**

The project follows Clean Architecture principles with Domain-Driven Design (DDD) and features a multi-tenant architecture.

## Building and Running

### Docker (Recommended)

1.  **Build the development image:**
    ```bash
    docker build --target development -t aynux-app:dev .
    ```
2.  **Start all services:**
    ```bash
    docker compose --profile ollama --profile tools up -d
    ```
3.  **Verify:**
    ```bash
    curl http://localhost:8001/health
    ```

### Manual Installation

1.  **Install dependencies:**
    ```bash
    uv sync
    ```
2.  **Run the development server:**
    ```bash
    ./dev-uv.sh
    ```
    Or:
    ```bash
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
    ```

## Development Conventions

*   **Testing:** The project uses `pytest`. Run the test suite with `uv run pytest -v`.
*   **Linting and Formatting:** The project uses `ruff` for linting and `black` for formatting.
*   **CI/CD:** A GitHub Actions workflow is set up to run tests on push and pull requests.
*   **Dependency Management:** The project uses `uv` for package management.
*   **Type Hinting:** The project uses modern Python type hints. A script to modernize type hints is available in `scripts/modernize_type_hints.py`.
