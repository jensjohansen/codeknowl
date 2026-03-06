"""
File: backend/src/codeknowl/graph_extractor.py
Purpose: Extract code relationships for graph storage.
Product/business importance: Enables Milestone 7 graph relationship store by analyzing code structure.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from tree_sitter import Language, Node, Parser

try:
    import tree_sitter_python
except ImportError:
    tree_sitter_python = None

try:
    import tree_sitter_javascript
except ImportError:
    tree_sitter_javascript = None

try:
    import tree_sitter_java
except ImportError:
    tree_sitter_java = None

try:
    import tree_sitter_go
except ImportError:
    tree_sitter_go = None

try:
    import tree_sitter_rust
except ImportError:
    tree_sitter_rust = None

try:
    import tree_sitter_cpp
except ImportError:
    tree_sitter_cpp = None

logger = logging.getLogger(__name__)


class CodeGraphExtractor:
    """Extracts code relationships for graph storage.

    Why this exists:
    - Analyzes AST to find functions, classes, imports, and relationships.
    - Provides structured data for NebulaGraph ingestion.
    """

    def __init__(self, language: str) -> None:
        """Initialize extractor for a specific language.

        Why this exists:
        - Sets up tree-sitter parser for the target language.
        
        Args:
            language: Programming language (python, javascript, etc.)
        """
        self.language = language.lower()
        self.parser = self._get_parser()

    def _get_parser(self) -> Parser:
        """Get tree-sitter parser for the language.

        Why this exists:
        - Initializes the appropriate parser based on language.
        
        Returns:
            Configured tree-sitter parser
        """
        parser = Parser()
        
        try:
            if self.language == "python" and tree_sitter_python:
                parser.set_language(Language(tree_sitter_python.language()))
            elif self.language in ["javascript", "typescript"] and tree_sitter_javascript:
                parser.set_language(Language(tree_sitter_javascript.language()))
            elif self.language == "java" and tree_sitter_java:
                parser.set_language(Language(tree_sitter_java.language()))
            elif self.language == "go" and tree_sitter_go:
                parser.set_language(Language(tree_sitter_go.language()))
            elif self.language == "rust" and tree_sitter_rust:
                parser.set_language(Language(tree_sitter_rust.language()))
            elif self.language == "cpp" and tree_sitter_cpp:
                parser.set_language(Language(tree_sitter_cpp.language()))
            else:
                logger.warning("Unsupported language: %s", self.language)
                if tree_sitter_python:
                    parser.set_language(Language(tree_sitter_python.language()))
        except Exception as e:
            logger.error("Failed to load language parser for %s: %s", self.language, e)
            if tree_sitter_python:
                parser.set_language(Language(tree_sitter_python.language()))
        
        return parser

    def extract_from_file(self, file_path: Path) -> Dict[str, Any]:
        """Extract graph data from a source file.

        Why this exists:
        - Analyzes a file to extract entities and relationships.
        
        Args:
            file_path: Path to source file
            
        Returns:
            Dictionary containing extracted graph data
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
        except Exception as e:
            logger.error("Failed to read file %s: %s", file_path, e)
            return {"error": str(e)}

        tree = self.parser.parse(bytes(source_code, "utf-8"))
        
        file_id = str(file_path)
        result = {
            "file_id": file_id,
            "name": file_path.name,
            "path": str(file_path),
            "language": self.language,
            "functions": [],
            "classes": [],
            "imports": [],
            "calls": [],
            "inherits": [],
        }

        # Extract different types of entities
        self._extract_functions(tree.root_node, file_path, result["functions"])
        self._extract_classes(tree.root_node, file_path, result["classes"])
        self._extract_imports(tree.root_node, file_path, result["imports"])
        self._extract_calls(tree.root_node, file_path, result["calls"])
        self._extract_inheritance(tree.root_node, file_path, result["inherits"])

        return result

    def _extract_functions(self, node: Node, file_path: Path, functions: List[Dict[str, Any]]) -> None:
        """Extract function definitions.

        Why this exists:
        - Finds all function/method definitions in the AST.
        
        Args:
            node: AST node to analyze
            file_path: Source file path
            functions: List to append function data to
        """
        if self.language == "python":
            self._extract_python_functions(node, file_path, functions)
        elif self.language in ["javascript", "typescript"]:
            self._extract_js_functions(node, file_path, functions)
        else:
            # Generic extraction for other languages
            if node.type == "function_definition" or node.type == "function_declaration":
                func_data = self._extract_function_data(node, file_path)
                if func_data:
                    functions.append(func_data)

        # Recursively check child nodes
        for child in node.children:
            self._extract_functions(child, file_path, functions)

    def _extract_python_functions(self, node: Node, file_path: Path, functions: List[Dict[str, Any]]) -> None:
        """Extract Python function definitions.

        Why this exists:
        - Handles Python-specific function syntax.
        """
        if node.type == "function_definition":
            func_data = self._extract_function_data(node, file_path)
            if func_data:
                functions.append(func_data)

    def _extract_js_functions(self, node: Node, file_path: Path, functions: List[Dict[str, Any]]) -> None:
        """Extract JavaScript/TypeScript function definitions.

        Why this exists:
        - Handles JavaScript/TypeScript function syntax.
        """
        if node.type in ["function_declaration", "function_expression", "method_definition"]:
            func_data = self._extract_function_data(node, file_path)
            if func_data:
                functions.append(func_data)

    def _extract_function_data(self, node: Node, file_path: Path) -> Dict[str, Any] | None:
        """Extract function metadata from AST node.

        Why this exists:
        - Common function data extraction logic.
        
        Returns:
            Function metadata dictionary or None
        """
        try:
            # Find function name
            name_node = None
            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                    break

            if not name_node:
                return None

            name = name_node.text.decode("utf-8")
            line_start = node.start_point[0] + 1  # 1-based line numbers
            line_end = node.end_point[0] + 1

            # Extract signature (simplified)
            signature = f"{name}()"

            return {
                "id": f"{file_path}:{name}:{line_start}",
                "name": name,
                "signature": signature,
                "line_start": line_start,
                "line_end": line_end,
                "file_path": str(file_path),
            }
        except Exception as e:
            logger.error("Failed to extract function data: %s", e)
            return None

    def _extract_classes(self, node: Node, file_path: Path, classes: List[Dict[str, Any]]) -> None:
        """Extract class definitions.

        Why this exists:
        - Finds all class definitions in the AST.
        
        Args:
            node: AST node to analyze
            file_path: Source file path
            classes: List to append class data to
        """
        if self.language == "python":
            self._extract_python_classes(node, file_path, classes)
        elif self.language in ["javascript", "typescript"]:
            self._extract_js_classes(node, file_path, classes)
        else:
            # Generic extraction
            if node.type == "class_definition" or node.type == "class_declaration":
                class_data = self._extract_class_data(node, file_path)
                if class_data:
                    classes.append(class_data)

        # Recursively check child nodes
        for child in node.children:
            self._extract_classes(child, file_path, classes)

    def _extract_python_classes(self, node: Node, file_path: Path, classes: List[Dict[str, Any]]) -> None:
        """Extract Python class definitions.

        Why this exists:
        - Handles Python-specific class syntax.
        """
        if node.type == "class_definition":
            class_data = self._extract_class_data(node, file_path)
            if class_data:
                classes.append(class_data)

    def _extract_js_classes(self, node: Node, file_path: Path, classes: List[Dict[str, Any]]) -> None:
        """Extract JavaScript/TypeScript class definitions.

        Why this exists:
        - Handles JavaScript/TypeScript class syntax.
        """
        if node.type == "class_declaration":
            class_data = self._extract_class_data(node, file_path)
            if class_data:
                classes.append(class_data)

    def _extract_class_data(self, node: Node, file_path: Path) -> Dict[str, Any] | None:
        """Extract class metadata from AST node.

        Why this exists:
        - Common class data extraction logic.
        
        Returns:
            Class metadata dictionary or None
        """
        try:
            # Find class name
            name_node = None
            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                    break

            if not name_node:
                return None

            name = name_node.text.decode("utf-8")
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1

            # Extract inheritance
            parents = []
            if self.language == "python":
                for child in node.children:
                    if child.type == "argument_list":
                        for arg in child.children:
                            if arg.type == "identifier":
                                parents.append(arg.text.decode("utf-8"))

            signature = f"class {name}({', '.join(parents)})" if parents else f"class {name}"

            return {
                "id": f"{file_path}:{name}:{line_start}",
                "name": name,
                "signature": signature,
                "line_start": line_start,
                "line_end": line_end,
                "file_path": str(file_path),
                "parents": parents,
            }
        except Exception as e:
            logger.error("Failed to extract class data: %s", e)
            return None

    def _extract_imports(self, node: Node, file_path: Path, imports: List[Dict[str, Any]]) -> None:
        """Extract import statements.

        Why this exists:
        - Finds all import statements for dependency tracking.
        
        Args:
            node: AST node to analyze
            file_path: Source file path
            imports: List to append import data to
        """
        if self.language == "python":
            self._extract_python_imports(node, file_path, imports)
        elif self.language in ["javascript", "typescript"]:
            self._extract_js_imports(node, file_path, imports)

        # Recursively check child nodes
        for child in node.children:
            self._extract_imports(child, file_path, imports)

    def _extract_python_imports(self, node: Node, file_path: Path, imports: List[Dict[str, Any]]) -> None:
        """Extract Python import statements.

        Why this exists:
        - Handles Python import syntax.
        """
        if node.type == "import_statement":
            # Handle "import module" statements
            for child in node.children:
                if child.type == "dotted_name":
                    module = child.text.decode("utf-8")
                    imports.append({
                        "module": module,
                        "line": node.start_point[0] + 1,
                        "type": "import",
                    })
        elif node.type == "import_from_statement":
            # Handle "from module import name" statements
            module_node = None
            for child in node.children:
                if child.type == "dotted_name":
                    module_node = child
                    break
            
            if module_node:
                module = module_node.text.decode("utf-8")
                imports.append({
                    "module": module,
                    "line": node.start_point[0] + 1,
                    "type": "from_import",
                })

    def _extract_js_imports(self, node: Node, file_path: Path, imports: List[Dict[str, Any]]) -> None:
        """Extract JavaScript/TypeScript import statements.

        Why this exists:
        - Handles JavaScript/TypeScript import syntax.
        """
        if node.type == "import_statement":
            line = node.start_point[0] + 1
            text = node.text.decode("utf-8")
            
            if "from" in text:
                # ES6 import: import ... from "module"
                parts = text.split("from")
                if len(parts) > 1:
                    module = parts[1].strip().strip('"\'')
                    imports.append({
                        "module": module,
                        "line": line,
                        "type": "es6_import",
                    })
            elif "require" in text:
                # CommonJS: require("module")
                start = text.find("require(") + 9
                end = text.find(")", start)
                if start > 8 and end > start:
                    module = text[start:end].strip('"\'')
                    imports.append({
                        "module": module,
                        "line": line,
                        "type": "require",
                    })

    def _extract_calls(self, node: Node, file_path: Path, calls: List[Dict[str, Any]]) -> None:
        """Extract function calls.

        Why this exists:
        - Finds function calls for call graph analysis.
        
        Args:
            node: AST node to analyze
            file_path: Source file path
            calls: List to append call data to
        """
        if node.type == "call_expression":
            call_data = self._extract_call_data(node, file_path)
            if call_data:
                calls.append(call_data)

        # Recursively check child nodes
        for child in node.children:
            self._extract_calls(child, file_path, calls)

    def _extract_call_data(self, node: Node, file_path: Path) -> Dict[str, Any] | None:
        """Extract call metadata from AST node.

        Why this exists:
        - Common call data extraction logic.
        
        Returns:
            Call metadata dictionary or None
        """
        try:
            # Find function name
            func_node = node.child_by_field_name("function")
            if not func_node:
                return None

            # Handle different types of function references
            if func_node.type == "identifier":
                func_name = func_node.text.decode("utf-8")
            elif func_node.type == "member_expression":
                # Handle method calls like obj.method()
                func_name = func_node.text.decode("utf-8")
            else:
                func_name = func_node.text.decode("utf-8")

            line = node.start_point[0] + 1

            return {
                "function": func_name,
                "line": line,
                "file_path": str(file_path),
            }
        except Exception as e:
            logger.error("Failed to extract call data: %s", e)
            return None

    def _extract_inheritance(self, node: Node, file_path: Path, inherits: List[Dict[str, Any]]) -> None:
        """Extract inheritance relationships.

        Why this exists:
        - Finds class inheritance for hierarchy analysis.
        
        Args:
            node: AST node to analyze
            file_path: Source file path
            inherits: List to append inheritance data to
        """
        if self.language == "python":
            self._extract_python_inheritance(node, file_path, inherits)

        # Recursively check child nodes
        for child in node.children:
            self._extract_inheritance(child, file_path, inherits)

    def _extract_python_inheritance(self, node: Node, file_path: Path, inherits: List[Dict[str, Any]]) -> None:
        """Extract Python inheritance relationships.

        Why this exists:
        - Handles Python inheritance syntax.
        """
        if node.type == "class_definition":
            class_name = None
            parent_classes = []
            
            for child in node.children:
                if child.type == "identifier" and class_name is None:
                    class_name = child.text.decode("utf-8")
                elif child.type == "argument_list":
                    for arg in child.children:
                        if arg.type == "identifier":
                            parent_classes.append(arg.text.decode("utf-8"))
            
            if class_name and parent_classes:
                for parent in parent_classes:
                    inherits.append({
                        "child": class_name,
                        "parent": parent,
                        "line": node.start_point[0] + 1,
                        "file_path": str(file_path),
                    })


def create_extractor(language: str) -> CodeGraphExtractor:
    """Create graph extractor for a language.

    Why this exists:
    - Factory function for creating extractors.
    
    Args:
        language: Programming language
        
    Returns:
        Configured graph extractor
    """
    return CodeGraphExtractor(language)
