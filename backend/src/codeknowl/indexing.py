"""File: backend/src/codeknowl/indexing.py
Purpose: Extract a minimal set of symbols and call sites from repositories using Tree-sitter.
Product/business importance: Index-time extraction provides deterministic evidence used for citations and navigation,
and supports Milestone 1 Q&A.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from tree_sitter_languages import get_parser

from codeknowl.artifacts import (
    CallRecord,
    FileRecord,
    SourceRange,
    SymbolRecord,
)

_EXT_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".vue": "vue",
}


_IGNORED_DIR_NAMES: set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
}


def _should_ignore_path(path: Path) -> bool:
    for part in path.parts:
        if part in _IGNORED_DIR_NAMES:
            return True
        if part.startswith(".codeknowl"):
            return True
    return False


def _range_from_node(node) -> SourceRange:
    start = node.start_point  # (row, column), 0-based
    end = node.end_point
    return SourceRange(
        start_line=int(start[0]) + 1,
        start_col=int(start[1]) + 1,
        end_line=int(end[0]) + 1,
        end_col=int(end[1]) + 1,
    )


def _file_language(path: Path) -> str:
    return _EXT_LANGUAGE.get(path.suffix.lower(), "unknown")


def build_file_inventory(repo_path: Path) -> list[FileRecord]:
    records: list[FileRecord] = []
    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        if _should_ignore_path(p):
            continue
        try:
            size_bytes = p.stat().st_size
        except OSError:
            continue
        records.append(
            FileRecord(path=str(p.relative_to(repo_path)), language=_file_language(p), size_bytes=size_bytes)
        )

    records.sort(key=lambda r: r.path)
    return records


def _stable_symbol_id(repo_rel_path: str, kind: str, name: str, start_line: int) -> str:
    raw = f"{repo_rel_path}:{kind}:{name}:{start_line}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _add_python_symbols(symbols: list[SymbolRecord], *, node, code_bytes: bytes, rel_path: str) -> None:
    if node.type not in {"function_definition", "class_definition"}:
        return

    name_node = node.child_by_field_name("name")
    if name_node is None:
        return

    name = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
    r = _range_from_node(node)
    kind = "function" if node.type == "function_definition" else "class"
    symbol_id = _stable_symbol_id(rel_path, kind, name, r.start_line)
    symbols.append(SymbolRecord(symbol_id=symbol_id, kind=kind, name=name, file_path=rel_path, range=r))


def _add_js_ts_symbols(symbols: list[SymbolRecord], *, node, code_bytes: bytes, rel_path: str) -> None:
    if node.type == "function_declaration":
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
        r = _range_from_node(node)
        symbol_id = _stable_symbol_id(rel_path, "function", name, r.start_line)
        symbols.append(SymbolRecord(symbol_id=symbol_id, kind="function", name=name, file_path=rel_path, range=r))
        return

    if node.type == "class_declaration":
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
        r = _range_from_node(node)
        symbol_id = _stable_symbol_id(rel_path, "class", name, r.start_line)
        symbols.append(SymbolRecord(symbol_id=symbol_id, kind="class", name=name, file_path=rel_path, range=r))


def _add_java_symbols(symbols: list[SymbolRecord], *, node, code_bytes: bytes, rel_path: str) -> None:
    if node.type not in {"method_declaration", "class_declaration"}:
        return

    name_node = node.child_by_field_name("name")
    if name_node is None:
        return

    name = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
    r = _range_from_node(node)
    kind = "method" if node.type == "method_declaration" else "class"
    symbol_id = _stable_symbol_id(rel_path, kind, name, r.start_line)
    symbols.append(SymbolRecord(symbol_id=symbol_id, kind=kind, name=name, file_path=rel_path, range=r))


def _add_python_calls(calls: list[CallRecord], *, node, code_bytes: bytes, rel_path: str) -> None:
    if node.type != "call":
        return
    func_node = node.child_by_field_name("function")
    if func_node is None:
        return
    callee = code_bytes[func_node.start_byte : func_node.end_byte].decode("utf-8", errors="replace")
    r = _range_from_node(node)
    calls.append(CallRecord(caller_symbol_id="", callee_name=callee, file_path=rel_path, range=r))


def _add_js_ts_calls(calls: list[CallRecord], *, node, code_bytes: bytes, rel_path: str) -> None:
    if node.type != "call_expression":
        return
    func_node = node.child_by_field_name("function")
    if func_node is None:
        return
    callee = code_bytes[func_node.start_byte : func_node.end_byte].decode("utf-8", errors="replace")
    r = _range_from_node(node)
    calls.append(CallRecord(caller_symbol_id="", callee_name=callee, file_path=rel_path, range=r))


def _add_java_calls(calls: list[CallRecord], *, node, code_bytes: bytes, rel_path: str) -> None:
    if node.type != "method_invocation":
        return
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return
    callee = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
    r = _range_from_node(node)
    calls.append(CallRecord(caller_symbol_id="", callee_name=callee, file_path=rel_path, range=r))


def _walk_tree(root) -> list:
    stack = [root]
    out = []
    while stack:
        node = stack.pop()
        out.append(node)
        for child in reversed(node.children):
            stack.append(child)
    return out


def extract_symbols_and_calls(repo_path: Path) -> tuple[list[SymbolRecord], list[CallRecord]]:
    """Extract a minimal set of symbol definitions and call sites.

    This is a best-effort MVP extractor driven by Tree-sitter.
    """
    symbols: list[SymbolRecord] = []
    calls: list[CallRecord] = []

    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        if _should_ignore_path(p):
            continue

        lang = _file_language(p)
        if lang not in {"python", "javascript", "typescript", "java"}:
            continue

        try:
            code_bytes = p.read_bytes()
        except OSError:
            continue

        parser = get_parser(lang)
        tree = parser.parse(code_bytes)
        root = tree.root_node
        rel_path = str(p.relative_to(repo_path))

        nodes = _walk_tree(root)
        for node in nodes:
            if lang == "python":
                _add_python_symbols(symbols, node=node, code_bytes=code_bytes, rel_path=rel_path)
                _add_python_calls(calls, node=node, code_bytes=code_bytes, rel_path=rel_path)
            elif lang in {"javascript", "typescript"}:
                _add_js_ts_symbols(symbols, node=node, code_bytes=code_bytes, rel_path=rel_path)
                _add_js_ts_calls(calls, node=node, code_bytes=code_bytes, rel_path=rel_path)
            elif lang == "java":
                _add_java_symbols(symbols, node=node, code_bytes=code_bytes, rel_path=rel_path)
                _add_java_calls(calls, node=node, code_bytes=code_bytes, rel_path=rel_path)

    return symbols, calls
