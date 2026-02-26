from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codeknowl.artifacts import repo_snapshot_dir


@dataclass(frozen=True)
class QueryCitation:
    file_path: str
    start_line: int
    end_line: int


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_snapshot_artifacts(data_dir: Path, repo_id: str, head_commit: str) -> dict[str, Any]:
    root = repo_snapshot_dir(data_dir, repo_id, head_commit)
    return {
        "files": _load_json(root / "files.json"),
        "symbols": _load_json(root / "symbols.json"),
        "calls": _load_json(root / "calls.json"),
    }


def where_is_symbol_defined(artifacts: dict[str, Any], symbol_name: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for sym in artifacts.get("symbols", []):
        if sym.get("name") == symbol_name:
            r = sym.get("range") or {}
            matches.append(
                {
                    "symbol_id": sym.get("symbol_id"),
                    "kind": sym.get("kind"),
                    "name": sym.get("name"),
                    "citation": {
                        "file_path": sym.get("file_path"),
                        "start_line": r.get("start_line"),
                        "end_line": r.get("end_line"),
                    },
                }
            )
    return matches


def _callee_matches(callee_expr: str, requested: str) -> bool:
    if callee_expr == requested:
        return True

    if callee_expr.endswith(f".{requested}"):
        return True

    if callee_expr.endswith(f"::{requested}"):
        return True

    if callee_expr.endswith(f"/{requested}"):
        return True

    if requested in callee_expr:
        return True

    return False


def find_callers_best_effort(artifacts: dict[str, Any], callee_name: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for call in artifacts.get("calls", []):
        callee_expr = call.get("callee_name") or ""
        if not _callee_matches(callee_expr, callee_name):
            continue

        r = call.get("range") or {}
        results.append(
            {
                "callee_expr_preview": (callee_expr[:200] + "…") if len(callee_expr) > 200 else callee_expr,
                "citation": {
                    "file_path": call.get("file_path"),
                    "start_line": r.get("start_line"),
                    "end_line": r.get("end_line"),
                },
            }
        )

    return results


def explain_file_stub(artifacts: dict[str, Any], file_path: str) -> dict[str, Any]:
    file_rec = None
    for f in artifacts.get("files", []):
        if f.get("path") == file_path:
            file_rec = f
            break

    if file_rec is None:
        raise KeyError(f"File not found in snapshot: {file_path}")

    symbols = [s for s in artifacts.get("symbols", []) if s.get("file_path") == file_path]
    symbols.sort(key=lambda s: (s.get("range", {}).get("start_line") or 0, s.get("name") or ""))

    return {
        "file": file_rec,
        "top_symbols": [
            {
                "symbol_id": s.get("symbol_id"),
                "kind": s.get("kind"),
                "name": s.get("name"),
                "citation": {
                    "file_path": file_path,
                    "start_line": (s.get("range") or {}).get("start_line"),
                    "end_line": (s.get("range") or {}).get("end_line"),
                },
            }
            for s in symbols[:25]
        ],
        "note": "Deterministic stub; LLM-backed explanation will be added later.",
        "citations": [
            {
                "file_path": file_path,
                "start_line": 1,
                "end_line": 1,
            }
        ],
    }
