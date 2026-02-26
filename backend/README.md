<!--
File: backend/README.md
Purpose: Document how to run and verify the CodeKnowl Python backend.
Product/business importance: Provides the core indexing and Q&A services used by the CLI and VS Code extension.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
-->

# CodeKnowl (Backend)

This folder contains the Python backend components for CodeKnowl.

For overall project documentation, see the repository root `README.md`.

## Development

From the repository root:

- Install dependencies:

```bash
uv sync --project backend --extra dev
```

- Run formatting and linting:

```bash
uv run --project backend --extra dev -- ruff format backend/src
uv run --project backend --extra dev -- ruff check backend/src
```

- Run the backend smoke test:

```bash
./backend/scripts/smoke_test.sh
```

## Run the API server

```bash
uv run --project backend --extra dev -- uvicorn codeknowl.asgi:app --host 127.0.0.1 --port 8000
```
