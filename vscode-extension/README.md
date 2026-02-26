<!--
File: vscode-extension/README.md
Purpose: Document how to develop and run the CodeKnowl VS Code extension.
Product/business importance: Ensures consistent, repeatable IDE integration workflows for contributors.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
-->

# CodeKnowl VS Code Extension

This extension provides a local-first IDE experience backed by the CodeKnowl backend.

## What this extension does (MVP)

- Exposes the `CodeKnowl: Ask` command.
- Sends a request to the backend `POST /qa/ask` endpoint.
- Displays the answer and citations in the `CodeKnowl` Output channel.

## Development

- Install dependencies:

```bash
npm install
```

- Build:

```bash
npm run compile
```

- Lint:

```bash
npm run lint
```

- Tests:

```bash
npm test
```

- Run in Extension Host:

Use the `Run Extension` launch configuration.

## Backend dependency

The extension expects the backend to be running and reachable.

Example (from repository root):

```bash
uv run --project backend --extra dev -- uvicorn codeknowl.asgi:app --host 127.0.0.1 --port 8000
```

## Configuration

- `codeknowl.backendBaseUrl`: Base URL for the CodeKnowl backend API.
