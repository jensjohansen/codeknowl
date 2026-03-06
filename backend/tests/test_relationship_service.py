"""
Tests for relationship service functionality.

Why this exists:
- Tests required by Definition of Done for Milestone 7
- Validates relationship navigation functionality
- Ensures CPG pattern implementation works correctly
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from codeknowl.relationship_service import RelationshipService, create_relationship_service


class TestRelationshipService(unittest.IsolatedAsyncioTestCase):
    """Test relationship service functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_graph_store = MagicMock()
        self.service = RelationshipService(self.mock_graph_store)

    def test_find_symbol_definition_function(self) -> None:
        """Test finding function definitions."""
        # Mock successful query result
        mock_result = MagicMock()
        mock_result.is_succeeded.return_value = True
        mock_result.row_size.return_value = 1
        
        # Create proper mock objects
        mock_row = MagicMock()
        values = ["test_function", "/test/file.py", "def test_function()", "function"]
        mock_row.as_string.side_effect = lambda idx: values[idx]
        mock_row.as_int.return_value = 10
        mock_result.row_values.return_value = [mock_row]
        
        self.mock_graph_store.execute_query.return_value = mock_result
        
        result = self.service.find_symbol_definition("test_function", "test_repo")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "test_function")
        self.assertEqual(result["type"], "function")
        self.assertEqual(result["line_start"], 10)

    def test_find_symbol_definition_class(self) -> None:
        """Test finding class definitions."""
        mock_result = MagicMock()
        mock_result.is_succeeded.return_value = True
        mock_result.row_size.return_value = 1
        
        mock_row = MagicMock()
        mock_row.as_string.side_effect = lambda idx: ["TestClass", "/test/file.py", "class TestClass", "class"][idx]
        mock_row.as_int.return_value = 5
        mock_result.row_values.return_value = [mock_row]
        
        self.mock_graph_store.execute_query.return_value = mock_result

        result = self.service.find_symbol_definition("TestClass", "test_repo")

        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "TestClass")
        self.assertEqual(result["type"], "class")
        self.assertEqual(result["line_start"], 5)

    def test_find_symbol_definition_not_found(self) -> None:
        """Test symbol not found."""
        mock_result = MagicMock()
        mock_result.is_succeeded.return_value = True
        mock_result.row_size.return_value = 0
        self.mock_graph_store.execute_query.return_value = mock_result

        result = self.service.find_symbol_definition("nonexistent", "test_repo")

        self.assertIsNone(result)

    def test_find_callers(self) -> None:
        """Test finding callers of a symbol."""
        mock_result = MagicMock()
        mock_result.is_succeeded.return_value = True
        mock_result.row_size.return_value = 2
        mock_result.row_values.side_effect = [
            [
                MagicMock(as_string=MagicMock(return_value="caller1")),
                MagicMock(as_string=MagicMock(return_value="/file1.py")),
                MagicMock(as_int=MagicMock(return_value=20)),
                MagicMock(as_int=MagicMock(return_value=1)),
            ],
            [
                MagicMock(as_string=MagicMock(return_value="caller2")),
                MagicMock(as_string=MagicMock(return_value="/file2.py")),
                MagicMock(as_int=MagicMock(return_value=30)),
                MagicMock(as_int=MagicMock(return_value=2)),
            ],
        ]
        self.mock_graph_store.execute_query.return_value = mock_result

        callers = self.service.find_callers("test_function", "test_repo")

        self.assertEqual(len(callers), 2)
        self.assertEqual(callers[0]["caller_name"], "caller1")
        self.assertEqual(callers[0]["distance"], 1)
        self.assertEqual(callers[1]["caller_name"], "caller2")
        self.assertEqual(callers[1]["distance"], 2)

    def test_find_callees(self) -> None:
        """Test finding callees of a symbol."""
        mock_result = MagicMock()
        mock_result.is_succeeded.return_value = True
        mock_result.row_size.return_value = 1
        mock_result.row_values.return_value = [
            MagicMock(as_string=MagicMock(return_value="callee_func")),
            MagicMock(as_string=MagicMock(return_value="/callee.py")),
            MagicMock(as_int=MagicMock(return_value=15)),
            MagicMock(as_int=MagicMock(return_value=1)),
        ]
        self.mock_graph_store.execute_query.return_value = mock_result

        callees = self.service.find_callees("test_function", "test_repo")

        self.assertEqual(len(callees), 1)
        self.assertEqual(callees[0]["callee_name"], "callee_func")
        self.assertEqual(callees[0]["callee_line"], 15)

    def test_find_class_hierarchy(self) -> None:
        """Test finding class inheritance hierarchy."""
        # Mock parent query
        mock_parent_result = MagicMock()
        mock_parent_result.is_succeeded.return_value = True
        mock_parent_result.row_size.return_value = 1
        mock_parent_result.row_values.return_value = [
            MagicMock(as_string=MagicMock(return_value="ParentClass")),
            MagicMock(as_string=MagicMock(return_value="/parent.py")),
        ]

        # Mock child query
        mock_child_result = MagicMock()
        mock_child_result.is_succeeded.return_value = True
        mock_child_result.row_size.return_value = 1
        mock_child_result.row_values.return_value = [
            MagicMock(as_string=MagicMock(return_value="ChildClass")),
            MagicMock(as_string=MagicMock(return_value="/child.py")),
        ]

        self.mock_graph_store.execute_query.side_effect = [mock_parent_result, mock_child_result]

        hierarchy = self.service.find_class_hierarchy("TestClass", "test_repo")

        self.assertEqual(hierarchy["class_name"], "TestClass")
        self.assertEqual(len(hierarchy["parents"]), 1)
        self.assertEqual(hierarchy["parents"][0]["parent_name"], "ParentClass")
        self.assertEqual(len(hierarchy["children"]), 1)
        self.assertEqual(hierarchy["children"][0]["child_name"], "ChildClass")

    def test_find_file_dependencies(self) -> None:
        """Test finding file import dependencies."""
        # Mock imports query
        mock_imports_result = MagicMock()
        mock_imports_result.is_succeeded.return_value = True
        mock_imports_result.row_size.return_value = 1
        mock_imports_result.row_values.return_value = [
            MagicMock(as_string=MagicMock(return_value="/target/module.py")),
            MagicMock(as_string=MagicMock(return_value="module.py")),
        ]

        # Mock imported_by query
        mock_imported_by_result = MagicMock()
        mock_imported_by_result.is_succeeded.return_value = True
        mock_imported_by_result.row_size.return_value = 1
        mock_imported_by_result.row_values.return_value = [
            MagicMock(as_string=MagicMock(return_value="/source/main.py")),
            MagicMock(as_string=MagicMock(return_value="main.py")),
        ]

        self.mock_graph_store.execute_query.side_effect = [mock_imports_result, mock_imported_by_result]

        deps = self.service.find_file_dependencies("file123", "both")

        self.assertEqual(deps["file_id"], "file123")
        self.assertEqual(len(deps["imports"]), 1)
        self.assertEqual(deps["imports"][0]["target_name"], "module.py")
        self.assertEqual(len(deps["imported_by"]), 1)
        self.assertEqual(deps["imported_by"][0]["source_name"], "main.py")

    def test_get_symbol_summary(self) -> None:
        """Test comprehensive symbol summary."""
        # Mock definition query
        mock_def_result = MagicMock()
        mock_def_result.is_succeeded.return_value = True
        mock_def_result.row_size.return_value = 1
        mock_def_result.row_values.return_value = [
            MagicMock(as_string=MagicMock(return_value="test_func")),
            MagicMock(as_string=MagicMock(return_value="/test.py")),
            MagicMock(as_int=MagicMock(return_value=10)),
            MagicMock(as_string=MagicMock(return_value="def test_func()")),
            MagicMock(as_string=MagicMock(return_value="function")),
        ]

        # Mock callers query
        mock_callers_result = MagicMock()
        mock_callers_result.is_succeeded.return_value = True
        mock_callers_result.row_size.return_value = 2
        mock_callers_result.row_values.return_value = [
            [MagicMock(as_string=MagicMock(return_value="caller1")), MagicMock(), MagicMock(), MagicMock()],
            [MagicMock(as_string=MagicMock(return_value="caller2")), MagicMock(), MagicMock(), MagicMock()],
        ]

        # Mock callees query
        mock_callees_result = MagicMock()
        mock_callees_result.is_succeeded.return_value = True
        mock_callees_result.row_size.return_value = 1
        mock_callees_result.row_values.return_value = [
            [MagicMock(as_string=MagicMock(return_value="callee1")), MagicMock(), MagicMock(), MagicMock()],
        ]

        self.mock_graph_store.execute_query.side_effect = [
            mock_def_result, mock_callers_result, mock_callees_result
        ]

        summary = self.service.get_symbol_summary("test_func", "test_repo")

        self.assertIsNotNone(summary)
        self.assertEqual(summary["definition"]["name"], "test_func")
        self.assertEqual(summary["relationships"]["total_callers"], 2)
        self.assertEqual(summary["relationships"]["total_callees"], 1)

    def test_get_symbol_summary_not_found(self) -> None:
        """Test symbol summary for non-existent symbol."""
        mock_result = MagicMock()
        mock_result.is_succeeded.return_value = True
        mock_result.row_size.return_value = 0
        self.mock_graph_store.execute_query.return_value = mock_result

        summary = self.service.get_symbol_summary("nonexistent", "test_repo")

        self.assertIn("error", summary)
        self.assertIn("nonexistent", summary["error"])

    def test_query_error_handling(self) -> None:
        """Test error handling in queries."""
        self.mock_graph_store.execute_query.side_effect = Exception("Database error")

        result = self.service.find_symbol_definition("test_func", "test_repo")
        self.assertIsNone(result)

        callers = self.service.find_callers("test_func", "test_repo")
        self.assertEqual(callers, [])

    def test_create_relationship_service(self) -> None:
        """Test factory function."""
        mock_graph_store = MagicMock()
        service = create_relationship_service(mock_graph_store)

        self.assertIsInstance(service, RelationshipService)
        self.assertEqual(service.graph_store, mock_graph_store)


if __name__ == "__main__":
    unittest.main()
