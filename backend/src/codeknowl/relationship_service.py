"""
File: backend/src/codeknowl/relationship_service.py
Purpose: Relationship Service for CPG traversal and navigation.
Product/business importance: Enables Milestone 7 relationship navigation as specified in Architecture & Design.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from codeknowl.graph_store import NebulaGraphStore

logger = logging.getLogger(__name__)


class RelationshipService:
    """Service for code property graph relationship traversal and navigation.

    Why this exists:
    - Architecture & Design specifies a distinct "Relationship Service" component
    - Provides CPG pattern traversal-based retrieval
    - Enables "Jump from symbol to dependents/callers/callees" user experience
    - Separates relationship logic from graph storage concerns
    """

    def __init__(self, graph_store: NebulaGraphStore) -> None:
        """Initialize relationship service.

        Why this exists:
        - Sets up graph store for relationship queries.
        
        Args:
            graph_store: NebulaGraph client instance
        """
        self.graph_store = graph_store

    def find_symbol_definition(self, symbol_name: str, repo_id: str | None = None) -> Optional[Dict[str, Any]]:
        """Find where a symbol is defined.

        Why this exists:
        - Enables "where is this function/class defined" navigation.
        - Supports IDE "go to definition" functionality.
        
        Args:
            symbol_name: Symbol name to search for
            repo_id: Optional repository filter
            
        Returns:
            Symbol definition metadata or None if not found
        """
        repo_filter = f"AND v.repo_id == '{repo_id}'" if repo_id else ""
        
        query = f"""
        MATCH (v:function)
        WHERE v.name == '{symbol_name}' {repo_filter}
        RETURN v.name AS name, v.file_id AS file_id, v.line_start AS line_start, 
               v.signature AS signature, 'function' AS type
        UNION
        MATCH (v:class)
        WHERE v.name == '{symbol_name}' {repo_filter}
        RETURN v.name AS name, v.file_id AS file_id, v.line_start AS line_start, 
               v.signature AS signature, 'class' AS type
        """
        
        try:
            result = self.graph_store.execute_query(query)
            if result.is_succeeded() and result.row_size() > 0:
                row = result.row_values(0)
                return {
                    "name": row[0].as_string(),
                    "file_id": row[1].as_string(),
                    "line_start": row[2].as_int(),
                    "signature": row[3].as_string(),
                    "type": row[4].as_string(),
                }
        except Exception as e:
            logger.error("Failed to find symbol definition: %s", e)
        
        return None

    def find_callers(self, symbol_name: str, repo_id: str | None = None, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Find all callers of a symbol (reverse call graph).

        Why this exists:
        - Enables "who calls this function" navigation.
        - Supports impact analysis ("what will break if I change this").
        - Implements PRD requirement for relationship navigation.
        
        Args:
            symbol_name: Symbol to find callers for
            repo_id: Optional repository filter
            max_depth: Maximum traversal depth
            
        Returns:
            List of caller relationships
        """
        repo_filter = f"AND v.repo_id == '{repo_id}'" if repo_id else ""
        
        query = f"""
        MATCH (caller:function)-[:calls*1..{max_depth}]->(target:function)
        WHERE target.name == '{symbol_name}' {repo_filter}
        RETURN caller.name AS caller_name, caller.file_id AS caller_file, 
               caller.line_start AS caller_line, length(path) AS distance
        ORDER BY distance, caller_name
        """
        
        callers = []
        try:
            result = self.graph_store.execute_query(query)
            if result.is_succeeded():
                for i in range(result.row_size()):
                    row = result.row_values(i)
                    callers.append({
                        "caller_name": row[0].as_string(),
                        "caller_file": row[1].as_string(),
                        "caller_line": row[2].as_int(),
                        "distance": row[3].as_int(),
                    })
        except Exception as e:
            logger.error("Failed to find callers: %s", e)
        
        return callers

    def find_callees(self, symbol_name: str, repo_id: str | None = None, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Find all functions called by a symbol (forward call graph).

        Why this exists:
        - Enables "what does this function call" navigation.
        - Supports understanding of function dependencies.
        - Implements PRD requirement for relationship navigation.
        
        Args:
            symbol_name: Symbol to find callees for
            repo_id: Optional repository filter
            max_depth: Maximum traversal depth
            
        Returns:
            List of callee relationships
        """
        repo_filter = f"AND v.repo_id == '{repo_id}'" if repo_id else ""
        
        query = f"""
        MATCH (source:function)-[:calls*1..{max_depth}]->(callee:function)
        WHERE source.name == '{symbol_name}' {repo_filter}
        RETURN callee.name AS callee_name, callee.file_id AS callee_file, 
               callee.line_start AS callee_line, length(path) AS distance
        ORDER BY distance, callee_name
        """
        
        callees = []
        try:
            result = self.graph_store.execute_query(query)
            if result.is_succeeded():
                for i in range(result.row_size()):
                    row = result.row_values(i)
                    callees.append({
                        "callee_name": row[0].as_string(),
                        "callee_file": row[1].as_string(),
                        "callee_line": row[2].as_int(),
                        "distance": row[3].as_int(),
                    })
        except Exception as e:
            logger.error("Failed to find callees: %s", e)
        
        return callees

    def find_class_hierarchy(self, class_name: str, repo_id: str | None = None) -> Dict[str, Any]:
        """Find class inheritance hierarchy.

        Why this exists:
        - Enables "what does this class inherit from" navigation.
        - Supports understanding of class relationships.
        - Implements CPG pattern for class relationships.
        
        Args:
            class_name: Class to analyze
            repo_id: Optional repository filter
            
        Returns:
            Class hierarchy with parents and children
        """
        repo_filter = f"AND v.repo_id == '{repo_id}'" if repo_id else ""
        
        # Find parent classes
        parent_query = f"""
        MATCH (child:class)-[:inherits]->(parent:class)
        WHERE child.name == '{class_name}' {repo_filter}
        RETURN parent.name AS parent_name, parent.file_id AS parent_file
        """
        
        # Find child classes
        child_query = f"""
        MATCH (parent:class)<-[:inherits]-(child:class)
        WHERE parent.name == '{class_name}' {repo_filter}
        RETURN child.name AS child_name, child.file_id AS child_file
        """
        
        hierarchy = {"class_name": class_name, "parents": [], "children": []}
        
        try:
            # Get parents
            result = self.graph_store.execute_query(parent_query)
            if result.is_succeeded():
                for i in range(result.row_size()):
                    row = result.row_values(i)
                    hierarchy["parents"].append({
                        "parent_name": row[0].as_string(),
                        "parent_file": row[1].as_string(),
                    })
            
            # Get children
            result = self.graph_store.execute_query(child_query)
            if result.is_succeeded():
                for i in range(result.row_size()):
                    row = result.row_values(i)
                    hierarchy["children"].append({
                        "child_name": row[0].as_string(),
                        "child_file": row[1].as_string(),
                    })
                    
        except Exception as e:
            logger.error("Failed to find class hierarchy: %s", e)
        
        return hierarchy

    def find_file_dependencies(self, file_id: str, direction: str = "both") -> Dict[str, Any]:
        """Find file import dependencies.

        Why this exists:
        - Enables "what files does this file depend on" navigation.
        - Supports dependency analysis and impact assessment.
        - Implements CPG pattern for file relationships.
        
        Args:
            file_id: File to analyze
            direction: "imports", "imported_by", or "both"
            
        Returns:
            File dependencies
        """
        dependencies = {"file_id": file_id, "imports": [], "imported_by": []}
        
        try:
            if direction in ["imports", "both"]:
                # Files this file imports
                query = f"""
                MATCH (source:file)-[:imports]->(target:file)
                WHERE id(source) == '{file_id}'
                RETURN target.path AS target_path, target.name AS target_name
                """
                result = self.graph_store.execute_query(query)
                if result.is_succeeded():
                    for i in range(result.row_size()):
                        row = result.row_values(i)
                        dependencies["imports"].append({
                            "target_path": row[0].as_string(),
                            "target_name": row[1].as_string(),
                        })
            
            if direction in ["imported_by", "both"]:
                # Files that import this file
                query = f"""
                MATCH (source:file)-[:imports]->(target:file)
                WHERE id(target) == '{file_id}'
                RETURN source.path AS source_path, source.name AS source_name
                """
                result = self.graph_store.execute_query(query)
                if result.is_succeeded():
                    for i in range(result.row_size()):
                        row = result.row_values(i)
                        dependencies["imported_by"].append({
                            "source_path": row[0].as_string(),
                            "source_name": row[1].as_string(),
                        })
                        
        except Exception as e:
            logger.error("Failed to find file dependencies: %s", e)
        
        return dependencies

    def get_symbol_summary(self, symbol_name: str, repo_id: str | None = None) -> Dict[str, Any]:
        """Get comprehensive symbol summary with relationships.

        Why this exists:
        - Provides complete symbol context for IDE navigation.
        - Combines multiple relationship queries for efficiency.
        - Supports comprehensive symbol understanding.
        
        Args:
            symbol_name: Symbol to summarize
            repo_id: Optional repository filter
            
        Returns:
            Complete symbol summary
        """
        definition = self.find_symbol_definition(symbol_name, repo_id)
        if not definition:
            return {"error": f"Symbol '{symbol_name}' not found"}
        
        callers = self.find_callers(symbol_name, repo_id, max_depth=2)
        callees = self.find_callees(symbol_name, repo_id, max_depth=2)
        
        summary = {
            "definition": definition,
            "relationships": {
                "callers": callers[:10],  # Limit for performance
                "callees": callees[:10],
                "total_callers": len(callers),
                "total_callees": len(callees),
            },
        }
        
        # Add class hierarchy if it's a class
        if definition["type"] == "class":
            hierarchy = self.find_class_hierarchy(symbol_name, repo_id)
            summary["hierarchy"] = hierarchy
        
        return summary


def create_relationship_service(graph_store: NebulaGraphStore) -> RelationshipService:
    """Create relationship service instance.

    Why this exists:
    - Factory function for creating relationship service.
    
    Args:
        graph_store: NebulaGraph client instance
        
    Returns:
        Configured relationship service
    """
    return RelationshipService(graph_store)
