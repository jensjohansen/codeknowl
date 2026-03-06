#!/usr/bin/env bash
# File: backend/scripts/http_smoke_test.sh
# Purpose: Run repeatable local HTTP smoke tests against the backend API endpoints used by the VS Code extension.
# Product/business importance: Ensures Milestone 2 IDE flows are backed by stable, tested HTTP endpoints.
#
# Copyright (c) 2026 John K Johansen
# License: MIT (see LICENSE)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_PROJECT="$PROJECT_ROOT/backend"

REPO_PATH_DEFAULT="$PROJECT_ROOT"
REPO_PATH="${CODEKNOWL_SMOKE_REPO_PATH:-$REPO_PATH_DEFAULT}"
ACCEPTED_BRANCH="${CODEKNOWL_SMOKE_ACCEPTED_BRANCH:-main}"

DATA_DIR="${CODEKNOWL_HTTP_SMOKE_DATA_DIR:-$(mktemp -d)}"

if [[ -n "${CODEKNOWL_HTTP_SMOKE_PORT:-}" ]]; then
  PORT="$CODEKNOWL_HTTP_SMOKE_PORT"
else
  # Choose a randomized start port to reduce collisions with other local processes.
  PORT=$((20000 + (RANDOM % 20000)))
fi

pick_free_port() {
  local start_port="$1"
  local p
  for p in $(seq "$start_port" $((start_port + 20))); do
    if uv run --project "$BACKEND_PROJECT" --extra dev -- python3 - <<PY >/dev/null 2>&1
import socket
s=socket.socket()
try:
    s.bind(('127.0.0.1', $p))
    print('ok')
finally:
    s.close()
PY
    then
      echo "$p"
      return 0
    fi
  done
  return 1
}

PORT="$(pick_free_port "$PORT")"
BASE_URL="http://127.0.0.1:$PORT"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  if [[ "${CODEKNOWL_HTTP_SMOKE_KEEP_DATA_DIR:-}" != "1" ]]; then
    rm -rf "$DATA_DIR" || true
  fi
}
trap cleanup EXIT

echo "[http-smoke] repo_path=$REPO_PATH"
echo "[http-smoke] data_dir=$DATA_DIR"
echo "[http-smoke] base_url=$BASE_URL"

export BASE_URL
export REPO_PATH
export DATA_DIR
export ACCEPTED_BRANCH

uv sync --project "$BACKEND_PROJECT" --extra dev >/dev/null

mkdir -p "$DATA_DIR"

start_server() {
  (
    cd "$DATA_DIR"
    uv run --project "$BACKEND_PROJECT" --extra dev -- uvicorn codeknowl.asgi:app \
      --host 127.0.0.1 \
      --port "$PORT" \
      --log-level warning
  ) &
  SERVER_PID=$!
}

# Bind races are possible between pick_free_port and uvicorn startup. Retry a few times.
attempt=0
while true; do
  attempt=$((attempt + 1))
  start_server

  sleep 0.25
  if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    break
  fi

  if [[ $attempt -ge 5 ]]; then
    echo "[http-smoke] ERROR: server failed to start after $attempt attempts" >&2
    exit 1
  fi

  PORT="$(pick_free_port $((PORT + 1)))"
  BASE_URL="http://127.0.0.1:$PORT"
  export BASE_URL
  echo "[http-smoke] retrying with base_url=$BASE_URL" >&2
done

echo "[http-smoke] server_pid=$SERVER_PID"
echo "[http-smoke] final_base_url=$BASE_URL"

uv run --project "$BACKEND_PROJECT" --extra dev -- python - <<'PY'
import os
import time

import httpx

base_url = os.environ.get("BASE_URL")
assert base_url

deadline = time.time() + 20
last_err = None
while time.time() < deadline:
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{base_url}/health")
            r.raise_for_status()
            if r.json().get("status") == "ok":
                print("[http-smoke] backend is healthy")
                raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001
        last_err = exc
        time.sleep(0.25)

raise RuntimeError(f"backend did not become healthy: {last_err}")
PY

uv run --project "$BACKEND_PROJECT" --extra dev -- python - <<'PY'
import json
import os
from pathlib import Path

import httpx

base_url = os.environ["BASE_URL"].rstrip("/")
repo_path = os.environ["REPO_PATH"]
data_dir = Path(os.environ["DATA_DIR"])
accepted_branch = os.environ.get("ACCEPTED_BRANCH") or "main"
api_key = os.environ.get("CODEKNOWL_API_KEY")

headers = {}
if api_key:
    headers["X-CodeKnowl-Api-Key"] = api_key

with httpx.Client(timeout=60.0) as c:
    r = c.get(f"{base_url}/health")
    r.raise_for_status()

    r = c.post(
        f"{base_url}/repos",
        json={"local_path": repo_path, "accepted_branch": accepted_branch},
        headers=headers,
    )
    r.raise_for_status()
    repo = r.json()
    repo_id = repo["repo_id"]
    print(f"[http-smoke] repo_id={repo_id}")

    r = c.post(f"{base_url}/repos/{repo_id}/index", headers=headers)
    r.raise_for_status()
    idx = r.json()
    if idx.get("status") != "succeeded":
        raise RuntimeError(f"indexing did not succeed: {idx}")

    r = c.get(f"{base_url}/repos/{repo_id}/status", headers=headers)
    r.raise_for_status()
    status = r.json()
    head_commit = (status.get("latest_index_run") or {}).get("head_commit")
    if not head_commit:
        raise RuntimeError(f"missing head_commit: {status}")
    print(f"[http-smoke] head_commit={head_commit}")

    # Explain current file path (pick stable file in this repo)
    explain_path = "backend/src/codeknowl/__init__.py"
    r = c.get(
        f"{base_url}/repos/{repo_id}/qa/explain-file",
        params={"path": explain_path},
        headers=headers,
    )
    r.raise_for_status()

    # Extract first symbol from artifacts so where-defined and what-calls have a real target
    snapshot_dir = data_dir / ".codeknowl" / "artifacts" / repo_id / head_commit
    symbols_path = snapshot_dir / "symbols.json"
    if not symbols_path.exists():
        raise RuntimeError(f"missing symbols.json at {symbols_path}")
    symbols = json.loads(symbols_path.read_text(encoding="utf-8"))
    sym_name = symbols[0]["name"] if symbols else None

    if sym_name:
        r = c.get(
            f"{base_url}/repos/{repo_id}/qa/where-defined",
            params={"name": sym_name},
            headers=headers,
        )
        r.raise_for_status()

        r = c.get(
            f"{base_url}/repos/{repo_id}/qa/what-calls",
            params={"callee": sym_name},
            headers=headers,
        )
        r.raise_for_status()

    r = c.post(
        f"{base_url}/repos/{repo_id}/qa/ask",
        json={"question": f"What does {explain_path} do?"},
        headers=headers,
    )
    r.raise_for_status()

print("[http-smoke] OK")
PY
