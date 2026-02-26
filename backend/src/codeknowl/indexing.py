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
        if ".git" in p.parts:
            continue
        try:
            size_bytes = p.stat().st_size
        except OSError:
            continue
        records.append(FileRecord(path=str(p.relative_to(repo_path)), language=_file_language(p), size_bytes=size_bytes))

    records.sort(key=lambda r: r.path)
    return records


def _stable_symbol_id(repo_rel_path: str, kind: str, name: str, start_line: int) -> str:
    raw = f"{repo_rel_path}:{kind}:{name}:{start_line}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def extract_symbols_and_calls(repo_path: Path) -> tuple[list[SymbolRecord], list[CallRecord]]:
    symbols: list[SymbolRecord] = []
    calls: list[CallRecord] = []

    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        if ".git" in p.parts:
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

        stack = [root]
        while stack:
            node = stack.pop()

            # symbol defs
            if lang == "python" and node.type in {"function_definition", "class_definition"}:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    name = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
                    r = _range_from_node(node)
                    kind = "function" if node.type == "function_definition" else "class"
                    symbol_id = _stable_symbol_id(rel_path, kind, name, r.start_line)
                    symbols.append(SymbolRecord(symbol_id=symbol_id, kind=kind, name=name, file_path=rel_path, range=r))

            if lang in {"javascript", "typescript"}:
                # function declarations
                if node.type == "function_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        name = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
                        r = _range_from_node(node)
                        symbol_id = _stable_symbol_id(rel_path, "function", name, r.start_line)
                        symbols.append(SymbolRecord(symbol_id=symbol_id, kind="function", name=name, file_path=rel_path, range=r))

                # class declarations
                if node.type == "class_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        name = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
                        r = _range_from_node(node)
                        symbol_id = _stable_symbol_id(rel_path, "class", name, r.start_line)
                        symbols.append(SymbolRecord(symbol_id=symbol_id, kind="class", name=name, file_path=rel_path, range=r))

            if lang == "java" and node.type in {"method_declaration", "class_declaration"}:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    name = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
                    r = _range_from_node(node)
                    kind = "method" if node.type == "method_declaration" else "class"
                    symbol_id = _stable_symbol_id(rel_path, kind, name, r.start_line)
                    symbols.append(SymbolRecord(symbol_id=symbol_id, kind=kind, name=name, file_path=rel_path, range=r))

            # calls: best-effort name extraction
            if lang == "python" and node.type == "call":
                func_node = node.child_by_field_name("function")
                if func_node is not None:
                    callee = code_bytes[func_node.start_byte : func_node.end_byte].decode("utf-8", errors="replace")
                    r = _range_from_node(node)
                    calls.append(CallRecord(caller_symbol_id="", callee_name=callee, file_path=rel_path, range=r))

            if lang in {"javascript", "typescript"} and node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node is not None:
                    callee = code_bytes[func_node.start_byte : func_node.end_byte].decode("utf-8", errors="replace")
                    r = _range_from_node(node)
                    calls.append(CallRecord(caller_symbol_id="", callee_name=callee, file_path=rel_path, range=r))

            if lang == "java" and node.type == "method_invocation":
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    callee = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
                    r = _range_from_node(node)
                    calls.append(CallRecord(caller_symbol_id="", callee_name=callee, file_path=rel_path, range=r))

            for child in reversed(node.children):
                stack.append(child)

    return symbols, calls
