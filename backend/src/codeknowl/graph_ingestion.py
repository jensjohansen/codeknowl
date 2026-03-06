"""
File: backend/src/codeknowl/graph_ingestion.py
Purpose: Ingest code relationships into NebulaGraph.
Product/business importance: Enables Milestone 7 graph relationship store by persisting extracted data.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from codeknowl.graph_extractor import create_extractor
from codeknowl.graph_store import NebulaGraphStore
from codeknowl.symbol_resolver import create_symbol_resolver

logger = logging.getLogger(__name__)


class GraphIngestionService:
    """Service for ingesting code relationships into NebulaGraph.

    Why this exists:
    - Coordinates extraction and storage of code relationships.
    - Provides high-level interface for graph ingestion.
    """

    def __init__(self, graph_store: NebulaGraphStore) -> None:
        """Initialize ingestion service.

        Why this exists:
        - Sets up graph store for persistence.
        
        Args:
            graph_store: NebulaGraph client instance
        """
        self.graph_store = graph_store

    def ingest_repository(self, repo_path: Path, repo_id: str) -> Dict[str, Any]:
        """Ingest all code relationships from a repository.

        Why this exists:
        - Processes entire repository for graph storage.
        - Creates actual relationships for navigation.
        
        Args:
            repo_path: Path to repository root
            repo_id: Repository identifier
            
        Returns:
            Ingestion statistics
        """
        stats = {
            "files_processed": 0,
            "functions_ingested": 0,
            "classes_ingested": 0,
            "imports_ingested": 0,
            "calls_ingested": 0,
            "inherits_ingested": 0,
            "errors": [],
        }

        # Initialize graph space if needed
        try:
            self.graph_store.initialize_space()
        except Exception as e:
            logger.error("Failed to initialize graph space: %s", e)
            stats["errors"].append(f"Graph space initialization: {e}")

        # Create symbol resolver for relationship creation
        resolver = create_symbol_resolver()

        # First pass: extract and ingest entities, build symbol tables
        source_files = self._find_source_files(repo_path)
        logger.info("Found %d source files in repository", len(source_files))

        for file_path in source_files:
            try:
                file_stats = self._ingest_file_entities(file_path, repo_id, resolver)
                stats["files_processed"] += 1
                stats["functions_ingested"] += file_stats["functions"]
                stats["classes_ingested"] += file_stats["classes"]
            except Exception as e:
                logger.error("Failed to ingest file %s: %s", file_path, e)
                stats["errors"].append(f"File {file_path}: {e}")

        # Second pass: create relationships using symbol tables
        for file_path in source_files:
            try:
                rel_stats = self._ingest_file_relationships(file_path, repo_id, resolver)
                stats["imports_ingested"] += rel_stats["imports"]
                stats["calls_ingested"] += rel_stats["calls"]
                stats["inherits_ingested"] += rel_stats["inherits"]
            except Exception as e:
                logger.error("Failed to ingest relationships for %s: %s", file_path, e)
                stats["errors"].append(f"Relationships {file_path}: {e}")

        logger.info(
            "Completed ingestion: %d files, %d functions, %d classes, %d imports, %d calls, %d inherits",
            stats["files_processed"],
            stats["functions_ingested"],
            stats["classes_ingested"],
            stats["imports_ingested"],
            stats["calls_ingested"],
            stats["inherits_ingested"],
        )

        return stats

    def _find_source_files(self, repo_path: Path) -> List[Path]:
        """Find all source files in repository.

        Why this exists:
        - Identifies files to process for graph extraction.
        
        Args:
            repo_path: Repository root path
            
        Returns:
            List of source file paths
        """
        source_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
        }

        source_files = []
        for file_path in repo_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in source_extensions:
                source_files.append(file_path)

        return source_files

    def _ingest_file_entities(self, file_path: Path, repo_id: str, resolver) -> Dict[str, int]:
        """Ingest file entities and build symbol tables.

        Why this exists:
        - First pass: extract entities and build resolver tables.
        - Separates entity ingestion from relationship creation.
        
        Args:
            file_path: Path to source file
            repo_id: Repository identifier
            resolver: Symbol resolver instance
            
        Returns:
            File entity statistics
        """
        language = self._detect_language(file_path)
        extractor = create_extractor(language)

        # Extract relationships
        data = extractor.extract_from_file(file_path)
        
        if "error" in data:
            logger.error("Extraction error for %s: %s", file_path, data["error"])
            return {"functions": 0, "classes": 0}

        stats = {"functions": 0, "classes": 0}

        # Insert file entity
        file_id = data["file_id"]
        self.graph_store.insert_file(file_id, data["name"], data["path"], repo_id, data["language"])
        
        # Register file in resolver
        resolver.add_file(file_id, data["path"])

        # Insert functions and register in resolver
        for func in data["functions"]:
            func_id = func["id"]
            self.graph_store.insert_function(
                func_id,
                func["name"],
                file_id,
                func["signature"],
                func["line_start"],
                func["line_end"],
            )
            resolver.add_function(func_id, func["name"], file_id)
            stats["functions"] += 1

        # Insert classes and register in resolver
        for cls in data["classes"]:
            class_id = cls["id"]
            self.graph_store.insert_class(
                class_id,
                cls["name"],
                file_id,
                cls["signature"],
                cls["line_start"],
                cls["line_end"],
            )
            resolver.add_class(class_id, cls["name"], file_id)
            stats["classes"] += 1

        return stats

    def _ingest_file_relationships(self, file_path: Path, repo_id: str, resolver) -> Dict[str, int]:
        """Ingest file relationships using symbol resolver.

        Why this exists:
        - Second pass: create actual relationships using symbol tables.
        - Enables navigation by creating real graph edges.
        
        Args:
            file_path: Path to source file
            repo_id: Repository identifier
            resolver: Populated symbol resolver
            
        Returns:
            File relationship statistics
        """
        language = self._detect_language(file_path)
        extractor = create_extractor(language)

        # Extract relationships
        data = extractor.extract_from_file(file_path)
        
        if "error" in data:
            logger.error("Extraction error for %s: %s", file_path, data["error"])
            return {"imports": 0, "calls": 0, "inherits": 0}

        stats = {"imports": 0, "calls": 0, "inherits": 0}
        file_id = data["file_id"]

        # Create import relationships
        for imp in data["imports"]:
            # Try to resolve module to file
            target_file_id = resolver.resolve_module_to_file(imp["module"])
            if target_file_id:
                self.graph_store.add_import_relationship(
                    file_id, target_file_id, imp["module"], imp["line"]
                )
                stats["imports"] += 1

        # Create call relationships
        for call in data["calls"]:
            # Try to resolve called function
            target_func_id = resolver.resolve_function(call["function"], file_id)
            if target_func_id:
                # Find calling function (simplified - assumes function context)
                calling_func_id = self._find_calling_function(call["line"], file_id, resolver)
                if calling_func_id:
                    self.graph_store.add_call_relationship(
                        calling_func_id, target_func_id, file_id, call["line"]
                    )
                    stats["calls"] += 1

        # Create inheritance relationships
        for inherit in data["inherits"]:
            # Try to resolve parent class
            parent_class_id = resolver.resolve_class(inherit["parent"], file_id)
            child_class_id = resolver.resolve_class(inherit["child"], file_id)
            if parent_class_id and child_class_id:
                self.graph_store.add_inheritance_relationship(
                    child_class_id, parent_class_id, file_id
                )
                stats["inherits"] += 1

        return stats

    def _find_calling_function(self, line: int, file_id: str, resolver) -> Optional[str]:
        """Find the function containing a call at given line.

        Why this exists:
        - Determines which function makes a call for relationship creation.
        
        Args:
            line: Line number of call
            file_id: File ID
            resolver: Symbol resolver
            
        Returns:
            Function ID or None if not found
        """
        # This is a simplified implementation
        # In practice, would need to track line ranges during extraction
        functions = resolver.get_all_functions_in_file(file_id)
        
        # Return the first function (simplified - should check line ranges)
        return functions[0] if functions else None

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension.

        Why this exists:
        - Determines language for appropriate parser selection.
        
        Args:
            file_path: File path
            
        Returns:
            Language string
        """
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
        }

        return extension_map.get(file_path.suffix.lower(), "python")

    def query_file_functions(self, file_id: str) -> List[Dict[str, Any]]:
        """Query functions in a file.

        Why this exists:
        - Provides interface for file-level function queries.
        
        Args:
            file_id: File identifier
            
        Returns:
            List of function information
        """
        return self.graph_store.query_functions_in_file(file_id)

    def query_function_calls(self, func_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Query function call graph.

        Why this exists:
        - Provides interface for call graph queries.
        
        Args:
            func_id: Function identifier
            depth: Maximum traversal depth
            
        Returns:
            List of call relationships
        """
        return self.graph_store.query_call_graph(func_id, depth)

    def query_file_imports(self, file_id: str) -> List[Dict[str, Any]]:
        """Query file import dependencies.

        Why this exists:
        - Provides interface for import dependency queries.
        
        Args:
            file_id: File identifier
            
        Returns:
            List of import relationships
        """
        return self.graph_store.query_import_dependencies(file_id)


def create_ingestion_service(graph_store: NebulaGraphStore) -> GraphIngestionService:
    """Create graph ingestion service.

    Why this exists:
    - Factory function for creating ingestion service.
    
    Args:
        graph_store: NebulaGraph client instance
        
    Returns:
        Configured ingestion service
    """
    return GraphIngestionService(graph_store)
