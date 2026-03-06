# Milestone 2 — IDE MVP Validation Runbook

## Purpose
Validate the end-to-end Milestone 2 experience (VS Code extension + backend HTTP API) for CodeKnowl.

This runbook is intentionally minimal and local-first.

## Prerequisites
- Backend Python dependencies available via `uv`.
- VS Code with the CodeKnowl extension running in Extension Development Host.

## Backend validation (HTTP)
1. Run backend HTTP smoke test:
   - `bash backend/scripts/http_smoke_test.sh`

Expected:
- Logs include:
  - `[http-smoke] backend is healthy`
  - `[http-smoke] OK`

## Extension validation (manual)
1. Configure backend base URL in VS Code settings:
   - `codeknowl.backendBaseUrl` = `http://127.0.0.1:<port>`

2. Open a workspace folder that is a Git repository.

3. Run `CodeKnowl: Index Current Workspace`.

Expected:
- Output channel `CodeKnowl` shows:
  - `repo_id=...`
  - indexing status and `head_commit=...`

4. Open a file in the workspace.

5. Run `CodeKnowl: Explain Current File`.

Expected:
- A citations picker appears.
- Selecting a citation opens the correct file and jumps to the cited line.

6. Run `CodeKnowl: Where Is Symbol Defined?` and enter a known symbol name.

Expected:
- A citations picker appears.
- Selecting a citation opens the defining file at the cited line.

7. Run `CodeKnowl: What Calls Symbol?` and enter a known callee name.

Expected:
- A citations picker appears.
- Selecting a citation opens a call site.

8. Run `CodeKnowl: Ask` and ask a question that includes a file path or symbol name.

Expected:
- An answer is printed in the output channel.
- Citations are printed.
- A citations picker appears and opens the file when selected.

## Notes
- If LLM environment variables are not configured, the backend returns a deterministic fallback response with an evidence bundle and citations.
