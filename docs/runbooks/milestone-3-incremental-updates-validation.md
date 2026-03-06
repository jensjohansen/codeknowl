# Milestone 3 — Incremental Updates (Accepted-Code-First) Validation Runbook

## Purpose
Validate Milestone 3 incremental updates behavior where CodeKnowl tracks a **single accepted branch per repo** and updates indexes via:
- **manual update trigger** (`repo-update` / `POST /repos/{repo_id}/update`)
- **polling** (`CODEKNOWL_POLL_INTERVAL_SECONDS`)

This runbook validates behavior without requiring an LLM.

## Preconditions
- A local Git repository checkout exists.
- You know the single accepted branch name for the repo (e.g. `main`).

## 1) Manual update via CLI
1. Register the repo with accepted branch:
   - `uv run --project backend -- python -m codeknowl --data-dir .codeknowl-m3 repo-register <LOCAL_PATH> <ACCEPTED_BRANCH>`

2. Index once (baseline snapshot):
   - `uv run --project backend -- python -m codeknowl --data-dir .codeknowl-m3 repo-index <REPO_ID>`

3. Advance accepted branch head (simulate a merge/push):
   - Make a commit on the accepted branch, or fetch a new remote commit into the local clone.

4. Run manual update:
   - `uv run --project backend -- python -m codeknowl --data-dir .codeknowl-m3 repo-update <REPO_ID>`

Expected:
- A new index run is recorded.
- `head_commit` changes to the new accepted-head commit.
- Artifacts exist at `.<data-dir>/artifacts/<repo_id>/<head_commit>/{files.json,symbols.json,calls.json}`.
- Only changed files are re-extracted (implementation detail), but correctness is validated by:
  - `repo-status` reflecting the new `head_commit`.

## 2) Manual update via HTTP
1. Start backend:
   - `uv run --project backend -- uvicorn codeknowl.asgi:app --host 127.0.0.1 --port 8000`

2. Register repo:
   - `POST /repos {"local_path": "...", "accepted_branch": "main"}`

3. Index baseline:
   - `POST /repos/{repo_id}/index`

4. After accepted branch advances, update:
   - `POST /repos/{repo_id}/update`

Expected:
- Response status is `succeeded` and `head_commit` matches accepted branch head.

## 3) Polling behavior
1. Start backend with polling enabled:
   - `CODEKNOWL_POLL_INTERVAL_SECONDS=30 uv run --project backend -- uvicorn codeknowl.asgi:app --host 127.0.0.1 --port 8000`

2. Register + index baseline.

3. Advance accepted branch head.

Expected:
- Within the polling interval, a new index run appears in `GET /repos/{repo_id}/status`.

## Non-goals (explicit)
- No multi-branch monitoring per repo.
- No feature-branch tracking.
- No dirty working-tree / local unpushed commit analysis.
- If you want multiple branches tracked, register them as separate repos (`repo_id`).
