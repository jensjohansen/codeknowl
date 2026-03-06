"""
File: backend/src/codeknowl/symbol_resolver.py
Purpose: Resolve symbol names to graph IDs for relationship creation.
Product/business importance: Enables Milestone 7 relationship navigation by creating actual graph edges.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SymbolResolver:
    """Resolves symbol names to graph IDs for relationship creation.

    Why this exists:
    - Enables actual relationship creation instead of just counting
    - Maps function/class names to their graph vertex IDs
    - Supports cross-file symbol resolution
    - Required for CPG pattern implementation
    """

    def __init__(self) -> None:
        """Initialize symbol resolver.

        Why this exists:
        - Sets up symbol tables for resolution.
        """
        self.function_symbols: Dict[str, str] = {}  # name -> id
        self.class_symbols: Dict[str, str] = {}     # name -> id
        self.file_symbols: Dict[str, str] = {}      # path -> id
        self.module_to_file: Dict[str, str] = {}     # module -> file_id

    def add_function(self, func_id: str, name: str, file_id: str) -> None:
        """Register a function symbol.

        Why this exists:
        - Builds symbol table for function resolution.
        
        Args:
            func_id: Graph vertex ID
            name: Function name
            file_id: File ID where function is defined
        """
        # Use qualified name to avoid conflicts
        qualified_name = f"{file_id}:{name}"
        self.function_symbols[qualified_name] = func_id
        self.function_symbols[name] = func_id  # Also store simple name for fallback

    def add_class(self, class_id: str, name: str, file_id: str) -> None:
        """Register a class symbol.

        Why this exists:
        - Builds symbol table for class resolution.
        
        Args:
            class_id: Graph vertex ID
            name: Class name
            file_id: File ID where class is defined
        """
        qualified_name = f"{file_id}:{name}"
        self.class_symbols[qualified_name] = class_id
        self.class_symbols[name] = class_id

    def add_file(self, file_id: str, path: str, module: str | None = None) -> None:
        """Register a file symbol.

        Why this exists:
        - Builds symbol table for file resolution.
        
        Args:
            file_id: Graph vertex ID
            path: File path
            module: Optional module name
        """
        self.file_symbols[path] = file_id
        if module:
            self.module_to_file[module] = file_id

    def resolve_function(self, name: str, source_file_id: str | None = None) -> Optional[str]:
        """Resolve function name to graph ID.

        Why this exists:
        - Enables creation of actual call relationships.
        
        Args:
            name: Function name to resolve
            source_file_id: Source file ID for context
            
        Returns:
            Graph vertex ID or None if not found
        """
        # Try qualified name first
        if source_file_id:
            qualified_name = f"{source_file_id}:{name}"
            if qualified_name in self.function_symbols:
                return self.function_symbols[qualified_name]
        
        # Try simple name (may have conflicts)
        if name in self.function_symbols:
            return self.function_symbols[name]
        
        return None

    def resolve_class(self, name: str, source_file_id: str | None = None) -> Optional[str]:
        """Resolve class name to graph ID.

        Why this exists:
        - Enables creation of actual inheritance relationships.
        
        Args:
            name: Class name to resolve
            source_file_id: Source file ID for context
            
        Returns:
            Graph vertex ID or None if not found
        """
        # Try qualified name first
        if source_file_id:
            qualified_name = f"{source_file_id}:{name}"
            if qualified_name in self.class_symbols:
                return self.class_symbols[qualified_name]
        
        # Try simple name
        if name in self.class_symbols:
            return self.class_symbols[name]
        
        return None

    def resolve_module_to_file(self, module: str) -> Optional[str]:
        """Resolve module name to file ID.

        Why this exists:
        - Enables creation of actual import relationships.
        
        Args:
            module: Module name to resolve
            
        Returns:
            File vertex ID or None if not found
        """
        return self.module_to_file.get(module)

    def get_all_functions_in_file(self, file_id: str) -> List[str]:
        """Get all function IDs in a file.

        Why this exists:
        - Supports file-level relationship queries.
        
        Args:
            file_id: File ID
            
        Returns:
            List of function vertex IDs
        """
        functions = []
        for qualified_name, func_id in self.function_symbols.items():
            if qualified_name.startswith(f"{file_id}:"):
                functions.append(func_id)
        return functions

    def get_all_classes_in_file(self, file_id: str) -> List[str]:
        """Get all class IDs in a file.

        Why this exists:
        - Supports file-level relationship queries.
        
        Args:
            file_id: File ID
            
        Returns:
            List of class vertex IDs
        """
        classes = []
        for qualified_name, class_id in self.class_symbols.items():
            if qualified_name.startswith(f"{file_id}:"):
                classes.append(class_id)
        return classes

    def clear(self) -> None:
        """Clear all symbol tables.

        Why this exists:
        - Resets resolver for new ingestion batch.
        """
        self.function_symbols.clear()
        self.class_symbols.clear()
        self.file_symbols.clear()
        self.module_to_file.clear()


def create_symbol_resolver() -> SymbolResolver:
    """Create symbol resolver instance.

    Why this exists:
    - Factory function for creating symbol resolver.
    
    Returns:
        Configured symbol resolver
    """
    return SymbolResolver()
