#!/usr/bin/env python3
"""
Check that all public Python functions/classes/modules have docstrings and all exported TS functions have JSDoc.
"""

import ast
import sys
from pathlib import Path

def iter_py_files(root: Path):
    for path in root.rglob('*.py'):
        if path.name == '__init__.py':
            continue
        yield path

def iter_ts_files(root: Path):
    for path in root.rglob('*.ts'):
        if path.name.endswith('.d.ts'):
            continue
        yield path

def is_public(name: str) -> bool:
    return not name.startswith('_')

def has_docstring(node) -> bool:
    return bool(ast.get_docstring(node))

def check_python(root: Path) -> int:
    missing = 0
    for file_path in iter_py_files(root):
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(file_path))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if is_public(node.name) and not has_docstring(node):
                    print(f'{file_path}:{node.lineno}: missing docstring for function {node.name}')
                    missing += 1
            elif isinstance(node, ast.ClassDef):
                if is_public(node.name) and not has_docstring(node):
                    print(f'{file_path}:{node.lineno}: missing docstring for class {node.name}')
                    missing += 1
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if is_public(item.name) and not has_docstring(item):
                            print(f'{file_path}:{item.lineno}: missing docstring for method {node.name}.{item.name}')
                            missing += 1
    return missing

def check_ts(root: Path) -> int:
    missing = 0
    for file_path in iter_ts_files(root):
        source = file_path.read_text(encoding='utf-8')
        lines = source.splitlines()
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Heuristic: look for exported function declarations
            if stripped.startswith('export function ') or stripped.startswith('export async function '):
                # Look backward for a JSDoc comment block ending with */
                found_jsdoc = False
                for j in range(i - 2, -1, -1):
                    prev = lines[j].strip()
                    if not prev:
                        continue
                    if prev == '*/':
                        # Now look for the matching /** above
                        for k in range(j - 1, -1, -1):
                            above = lines[k].strip()
                            if not above:
                                continue
                            if above == '/**':
                                found_jsdoc = True
                                break
                        break
                    else:
                        # If we hit a non-empty line that isn't */, no JSDoc
                        break
                if not found_jsdoc:
                    print(f'{file_path}:{i}: missing JSDoc for exported function')
                    missing += 1
    return missing

def main() -> None:
    backend_root = Path('backend/src/codeknowl')
    vscode_root = Path('vscode-extension/src')
    missing = 0
    missing += check_python(backend_root)
    missing += check_ts(vscode_root)
    if missing:
        print(f'Found {missing} missing docstring(s)', file=sys.stderr)
        sys.exit(1)
    else:
        print('All public symbols have docstrings/JSDoc')

if __name__ == '__main__':
    main()
