#!/usr/bin/env bash
# File: backend/scripts/smoke_test.sh
# Purpose: Run repeatable local smoke tests (ruff + indexing + deterministic QA), with optional LLM test when configured.
# Product/business importance: Prevents pushing broken code by providing a fast, automated verification gate for CodeKnowl.
#
# Copyright (c) 2026 John K Johansen
# License: MIT (see LICENSE)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_PROJECT="$PROJECT_ROOT/backend"

REPO_PATH_DEFAULT="$PROJECT_ROOT"
REPO_PATH="${CODEKNOWL_SMOKE_REPO_PATH:-$REPO_PATH_DEFAULT}"
DATA_DIR="${CODEKNOWL_SMOKE_DATA_DIR:-$PROJECT_ROOT/.codeknowl-smoke}"

echo "[smoke] repo_path=$REPO_PATH"
echo "[smoke] data_dir=$DATA_DIR"

rm -rf "$DATA_DIR"

uv sync --project "$BACKEND_PROJECT" --extra dev >/dev/null

uv run --project "$BACKEND_PROJECT" --extra dev -- ruff format --check backend/src >/dev/null
uv run --project "$BACKEND_PROJECT" --extra dev -- ruff check backend/src >/dev/null

REPO_ID="$(uv run --project "$BACKEND_PROJECT" -- python -m codeknowl --data-dir "$DATA_DIR" repo-register "$REPO_PATH" | uv run --project "$BACKEND_PROJECT" -- python -c 'import json,sys; print(json.load(sys.stdin)["repo_id"])')"

echo "[smoke] repo_id=$REPO_ID"

uv run --project "$BACKEND_PROJECT" -- python -m codeknowl --data-dir "$DATA_DIR" repo-index "$REPO_ID" >/dev/null

STATUS_JSON="$(uv run --project "$BACKEND_PROJECT" -- python -m codeknowl --data-dir "$DATA_DIR" repo-status "$REPO_ID")"
HEAD_COMMIT="$(uv run --project "$BACKEND_PROJECT" -- python -c 'import json,sys; s=json.loads(sys.argv[1]); print((s.get("latest_index_run") or {}).get("head_commit") or "")' "$STATUS_JSON")"

if [[ -z "$HEAD_COMMIT" ]]; then
  echo "[smoke] ERROR: missing head_commit in status"
  exit 1
fi

echo "[smoke] head_commit=$HEAD_COMMIT"

ART_DIR="$DATA_DIR/artifacts/$REPO_ID/$HEAD_COMMIT"

test -f "$ART_DIR/files.json"
test -f "$ART_DIR/symbols.json"
test -f "$ART_DIR/calls.json"

echo "[smoke] artifacts exist"

# Deterministic QA: pick first JS/PY file and first symbol
FIRST_FILE="$(uv run --project "$BACKEND_PROJECT" -- python -c 'import json,sys; p=sys.argv[1];
files=json.load(open(p));
preferred=[f for f in files if f.get("language") in ("python","javascript","typescript")];
print((preferred[0] if preferred else files[0])["path"] if files else "")' "$ART_DIR/files.json")"

if [[ -z "$FIRST_FILE" ]]; then
  echo "[smoke] ERROR: no files in inventory"
  exit 1
fi

echo "[smoke] first_file=$FIRST_FILE"

uv run --project "$BACKEND_PROJECT" -- python -m codeknowl --data-dir "$DATA_DIR" qa-explain-file "$REPO_ID" "$FIRST_FILE" >/dev/null

FIRST_SYMBOL="$(uv run --project "$BACKEND_PROJECT" -- python -c 'import json,sys; syms=json.load(open(sys.argv[1])); print((syms[0]["name"] if syms else ""))' "$ART_DIR/symbols.json")"

if [[ -n "$FIRST_SYMBOL" ]]; then
  uv run --project "$BACKEND_PROJECT" -- python -m codeknowl --data-dir "$DATA_DIR" qa-where-defined "$REPO_ID" "$FIRST_SYMBOL" >/dev/null
  uv run --project "$BACKEND_PROJECT" -- python -m codeknowl --data-dir "$DATA_DIR" qa-what-calls "$REPO_ID" "$FIRST_SYMBOL" >/dev/null
fi

echo "[smoke] deterministic QA passed"

# Optional LLM-backed ask if configured
if [[ -n "${CODEKNOWL_LLM_BASE_URL:-}" && -n "${CODEKNOWL_LLM_MODEL:-}" ]]; then
  echo "[smoke] running LLM-backed qa-ask"
  uv run --project "$BACKEND_PROJECT" -- python -m codeknowl --data-dir "$DATA_DIR" qa-ask "$REPO_ID" "What does $FIRST_FILE do?" >/dev/null
fi

echo "[smoke] OK"
