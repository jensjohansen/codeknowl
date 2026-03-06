"""
File: backend/src/codeknowl/graph_store.py
Purpose: NebulaGraph integration for persistent code relationship storage.
Product/business importance: Enables Milestone 7 graph relationship store for code navigation.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from nebula3.common import *
from nebula3.Config import Config
from nebula3.data.ResultSet import ResultSet
from nebula3.gclient.net import ConnectionPool

logger = logging.getLogger(__name__)


class NebulaGraphStore:
    """NebulaGraph client for code relationship storage.

    Why this exists:
    - Provides persistent graph storage for code entities and relationships.
    - Enables relationship navigation queries across codebases.
    """

    def __init__(self, hosts: List[str], port: int, username: str, password: str, space_name: str) -> None:
        """Initialize NebulaGraph connection.

        Why this exists:
        - Sets up connection pool for NebulaGraph cluster.
        
        Args:
            hosts: List of NebulaGraph host addresses
            port: NebulaGraph port
            username: Authentication username
            password: Authentication password
            space_name: Graph space name for CodeKnowl
        """
        self.space_name = space_name
        
        # Configure connection pool
        config = Config()
        config.max_connection_pool_size = 10
        config.timeout = 3000  # 3 seconds
        
        # Create connection pool
        self.connection_pool = ConnectionPool()
        
        # Initialize connection to hosts
        addresses = [(host, port) for host in hosts]
        if not self.connection_pool.init([(address, config) for address in addresses]):
            raise RuntimeError("Failed to initialize NebulaGraph connection pool")
        
        # Get session for queries
        self.session = self.connection_pool.get_session(username, password)
        
        logger.info("Connected to NebulaGraph at %s:%d", hosts[0], port)

    def close(self) -> None:
        """Close NebulaGraph connections.

        Why this exists:
        - Properly cleanup resources when shutting down.
        """
        if self.session:
            self.session.release()
        if self.connection_pool:
            self.connection_pool.close()
        logger.info("Closed NebulaGraph connection")

    def execute_query(self, query: str) -> ResultSet:
        """Execute nGQL query.

        Why this exists:
        - Provides a simple interface for running nGQL queries.
        
        Args:
            query: nGQL query string
            
        Returns:
            Query result set
        """
        try:
            result = self.session.execute(query)
            if not result.is_succeeded():
                raise RuntimeError(f"Query failed: {result.error_msg()}")
            return result
        except Exception:
            logger.exception("Failed to execute query: %s", query)
            raise

    def initialize_space(self) -> None:
        """Initialize CodeKnowl graph space and schema.

        Why this exists:
        - Creates the necessary space and tag types for code entities.
        """
        # Create space if not exists
        create_space_query = f"CREATE SPACE IF NOT EXISTS {self.space_name} (partition_num=10, replica_factor=1)"
        self.execute_query(create_space_query)
        
        # Use the space
        use_space_query = f"USE {self.space_name}"
        self.execute_query(use_space_query)
        
        # Create tag types for different entities
        tags = {
            "file": "string name, string path, string repo_id, string language",
            "function": "string name, string file_id, string signature, int line_start, int line_end",
            "class": "string name, string file_id, string signature, int line_start, int line_end",
            "import": "string from_file, string to_file, string module, int line",
            "call": "string from_function, string to_function, string file_id, int line",
            "inherits": "string child_class, string parent_class, string file_id",
            "variable": "string name, string type, string file_id, int line",
        }
        
        for tag_name, properties in tags.items():
            create_tag_query = f"CREATE TAG IF NOT EXISTS {tag_name} ({properties})"
            self.execute_query(create_tag_query)
        
        # Create edge types for relationships
        edges = {
            "imports": "string module, int line",
            "calls": "string file_id, int line",
            "inherits": "string file_id",
            "defines": "string type",  # function, class, variable
            "contains": "string type",  # file contains functions/classes
        }
        
        for edge_name, properties in edges.items():
            create_edge_query = f"CREATE EDGE IF NOT EXISTS {edge_name} ({properties})"
            self.execute_query(create_edge_query)
        
        logger.info("Initialized NebulaGraph space and schema")

    def insert_file(self, file_id: str, name: str, path: str, repo_id: str, language: str) -> None:
        """Insert a file entity.

        Why this exists:
        - Stores file metadata in the graph.
        
        Args:
            file_id: Unique file identifier
            name: File name
            path: File path
            repo_id: Repository identifier
            language: Programming language
        """
        query = f"""
        INSERT VERTEX file (name, path, repo_id, language)
        VALUES "{file_id}":("{name}", "{path}", "{repo_id}", "{language}")
        """
        self.execute_query(query)

    def insert_function(self, func_id: str, name: str, file_id: str, signature: str, line_start: int, line_end: int) -> None:
        """Insert a function entity.

        Why this exists:
        - Stores function metadata in the graph.
        
        Args:
            func_id: Unique function identifier
            name: Function name
            file_id: File identifier
            signature: Function signature
            line_start: Start line number
            line_end: End line number
        """
        query = f"""
        INSERT VERTEX function (name, file_id, signature, line_start, line_end)
        VALUES "{func_id}":("{name}", "{file_id}", "{signature}", {line_start}, {line_end})
        """
        self.execute_query(query)

    def insert_class(self, class_id: str, name: str, file_id: str, signature: str, line_start: int, line_end: int) -> None:
        """Insert a class entity.

        Why this exists:
        - Stores class metadata in the graph.
        
        Args:
            class_id: Unique class identifier
            name: Class name
            file_id: File identifier
            signature: Class signature
            line_start: Start line number
            line_end: End line number
        """
        query = f"""
        INSERT VERTEX class (name, file_id, signature, line_start, line_end)
        VALUES "{class_id}":("{name}", "{file_id}", "{signature}", {line_start}, {line_end})
        """
        self.execute_query(query)

    def add_import_relationship(self, from_file: str, to_file: str, module: str, line: int) -> None:
        """Add import relationship between files.

        Why this exists:
        - Tracks module imports for dependency analysis.
        
        Args:
            from_file: Source file ID
            to_file: Target file/module ID
            module: Module name
            line: Line number of import
        """
        query = f"""
        INSERT EDGE imports (module, line)
        VALUES "{from_file}"->"{to_file}":("{module}", {line})
        """
        self.execute_query(query)

    def add_call_relationship(self, from_func: str, to_func: str, file_id: str, line: int) -> None:
        """Add function call relationship.

        Why this exists:
        - Tracks function calls for call graph analysis.
        
        Args:
            from_func: Caller function ID
            to_func: Callee function ID
            file_id: File ID where call occurs
            line: Line number of call
        """
        query = f"""
        INSERT EDGE calls (file_id, line)
        VALUES "{from_func}"->"{to_func}":("{file_id}", {line})
        """
        self.execute_query(query)

    def query_functions_in_file(self, file_id: str) -> List[Dict[str, Any]]:
        """Query all functions in a file.

        Why this exists:
        - Enables navigation to functions within a file.
        
        Args:
            file_id: File identifier
            
        Returns:
            List of function dictionaries
        """
        query = f"""
        MATCH (v:function)-[:defines]->(f:file) 
        WHERE id(f) == "{file_id}"
        RETURN v.name AS name, v.signature AS signature, v.line_start AS line_start, v.line_end AS line_end
        """
        result = self.execute_query(query)
        
        functions = []
        if result.is_succeeded():
            for row in result:
                func = {
                    "name": row.values[0].as_string(),
                    "signature": row.values[1].as_string(),
                    "line_start": row.values[2].as_int(),
                    "line_end": row.values[3].as_int(),
                }
                functions.append(func)
        
        return functions

    def query_call_graph(self, func_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Query call graph for a function.

        Why this exists:
        - Enables navigation of function call relationships.
        
        Args:
            func_id: Function identifier
            depth: Maximum traversal depth
            
        Returns:
            List of call relationships
        """
        query = f"""
        MATCH (v:function)-[:calls*1..{depth}]->(c:function)
        WHERE id(v) == "{func_id}"
        RETURN v.name AS caller, c.name AS callee, length(path) AS distance
        ORDER BY distance, caller, callee
        """
        result = self.execute_query(query)
        
        calls = []
        if result.is_succeeded():
            for row in result:
                call = {
                    "caller": row.values[0].as_string(),
                    "callee": row.values[1].as_string(),
                    "distance": row.values[2].as_int(),
                }
                calls.append(call)
        
        return calls

    def query_import_dependencies(self, file_id: str) -> List[Dict[str, Any]]:
        """Query import dependencies for a file.

        Why this exists:
        - Enables analysis of module dependencies.
        
        Args:
            file_id: File identifier
            
        Returns:
            List of import relationships
        """
        query = f"""
        MATCH (f:file)-[:imports]->(m:file)
        WHERE id(f) == "{file_id}"
        RETURN m.path AS module_path, m.name AS module_name, r.module AS import_module, r.line AS line
        """
        result = self.execute_query(query)
        
        imports = []
        if result.is_succeeded():
            for row in result:
                imp = {
                    "module_path": row.values[0].as_string(),
                    "module_name": row.values[1].as_string(),
                    "import_module": row.values[2].as_string(),
                    "line": row.values[3].as_int(),
                }
                imports.append(imp)
        
        return imports


def create_graph_store() -> NebulaGraphStore:
    """Create NebulaGraph store instance.

    Why this exists:
    - Provides factory function for graph store initialization.
    
    Returns:
        Configured NebulaGraph store instance
    """
    # Configuration from environment
    hosts = os.environ.get("CODEKNOWL_NEBULA_HOSTS", "localhost:9669").split(",")
    port = int(os.environ.get("CODEKNOWL_NEBULA_PORT", "9669"))
    username = os.environ.get("CODEKNOWL_NEBULA_USERNAME", "root")
    password = os.environ.get("CODEKNOWL_NEBULA_PASSWORD", "nebula")
    space_name = os.environ.get("CODEKNOWL_NEBULA_SPACE", "codeknowl")
    
    return NebulaGraphStore(hosts, port, username, password, space_name)
