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
from typing import Any, Dict, List

from codeknowl.graph_extractor import create_extractor
from codeknowl.graph_store import NebulaGraphStore

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

        # Find all source files
        source_files = self._find_source_files(repo_path)
        logger.info("Found %d source files in repository", len(source_files))

        for file_path in source_files:
            try:
                file_stats = self._ingest_file(file_path, repo_id)
                stats["files_processed"] += 1
                stats["functions_ingested"] += file_stats["functions"]
                stats["classes_ingested"] += file_stats["classes"]
                stats["imports_ingested"] += file_stats["imports"]
                stats["calls_ingested"] += file_stats["calls"]
                stats["inherits_ingested"] += file_stats["inherits"]
            except Exception as e:
                logger.error("Failed to ingest file %s: %s", file_path, e)
                stats["errors"].append(f"File {file_path}: {e}")

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

    def _ingest_file(self, file_path: Path, repo_id: str) -> Dict[str, int]:
        """Ingest a single file into the graph.

        Why this exists:
        - Processes one file and stores its relationships.
        
        Args:
            file_path: Path to source file
            repo_id: Repository identifier
            
        Returns:
            File ingestion statistics
        """
        language = self._detect_language(file_path)
        extractor = create_extractor(language)

        # Extract relationships
        data = extractor.extract_from_file(file_path)
        
        if "error" in data:
            logger.error("Extraction error for %s: %s", file_path, data["error"])
            return {"functions": 0, "classes": 0, "imports": 0, "calls": 0, "inherits": 0}

        stats = {"functions": 0, "classes": 0, "imports": 0, "calls": 0, "inherits": 0}

        # Insert file entity
        file_id = data["file_id"]
        self.graph_store.insert_file(file_id, data["name"], data["path"], repo_id, data["language"])

        # Insert functions
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
            stats["functions"] += 1

        # Insert classes
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
            stats["classes"] += 1

        # Insert imports (simplified - would need module resolution)
        for _imp in data["imports"]:
            # For now, just count imports
            stats["imports"] += 1
            # TODO: Resolve module to file_id and create import relationship

        # Insert calls (simplified - would need function resolution)
        for _call in data["calls"]:
            # For now, just count calls
            stats["calls"] += 1
            # TODO: Resolve function to func_id and create call relationship

        # Insert inheritance relationships
        for _inherit in data["inherits"]:
            # Would need to resolve class IDs
            stats["inherits"] += 1
            # TODO: Resolve classes to IDs and create inheritance relationship

        return stats

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
