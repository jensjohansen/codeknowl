"""
Tests for findings ingestion and query functionality.

Why this exists:
- Tests required by Definition of Done for Milestone 8
- Validates SARIF/JSON ingestion pipeline
- Ensures traceable file/location links work correctly
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from codeknowl.findings import (
    FindingsIngestionReport,
    FindingsSchemaError,
    create_findings_normalizer,
)
from codeknowl.findings_ingestion import create_findings_ingestion_service
from codeknowl.findings_store import create_findings_store


class TestFindingsNormalizer(unittest.TestCase):
    """Test findings normalization functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.normalizer = create_findings_normalizer()

    def test_normalize_sarif(self) -> None:
        """Test SARIF format normalization."""
        sarif_data = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "test-scanner",
                            "version": "1.0.0"
                        }
                    },
                    "results": [
                        {
                            "rule": {
                                "id": "test-rule",
                                "name": "Test Rule",
                                "shortDescription": {"text": "Test rule description"}
                            },
                            "message": {"text": "Test finding message"},
                            "level": "warning",
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "test.py"},
                                        "region": {
                                            "startLine": 10,
                                            "startColumn": 5,
                                            "endLine": 10,
                                            "endColumn": 15
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        findings = self.normalizer.normalize_sarif(sarif_data, "test-repo", "test-snapshot")
        
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        
        self.assertEqual(finding.repo_id, "test-repo")
        self.assertEqual(finding.snapshot_id, "test-snapshot")
        self.assertEqual(finding.scanner_name, "test-scanner")
        self.assertEqual(finding.scanner_version, "1.0.0")
        self.assertEqual(finding.rule.rule_id, "test-rule")
        self.assertEqual(finding.rule.name, "Test Rule")
        self.assertEqual(finding.message, "Test finding message")
        self.assertEqual(finding.severity.level, "warning")
        self.assertEqual(finding.location.file_path, "test.py")
        self.assertEqual(finding.location.line_number, 10)
        self.assertEqual(finding.location.column_number, 5)

    def test_normalize_sarif_invalid_schema(self) -> None:
        """Test SARIF normalization with invalid schema."""
        invalid_sarif = {"invalid": "data"}
        
        with self.assertRaises(FindingsSchemaError):
            self.normalizer.normalize_sarif(invalid_sarif, "test-repo", "test-snapshot")

    def test_normalize_json(self) -> None:
        """Test generic JSON format normalization."""
        json_data = {
            "scanner": "test-scanner",
            "version": "1.0.0",
            "findings": [
                {
                    "rule_id": "test-rule",
                    "rule_name": "Test Rule",
                    "description": "Test rule description",
                    "message": "Test finding message",
                    "severity": "error",
                    "score": 8.5,
                    "file": "test.py",
                    "line": 20,
                    "column": 10,
                    "snippet": "test code snippet"
                }
            ]
        }
        
        findings = self.normalizer.normalize_json(json_data, "test-repo", "test-snapshot")
        
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        
        self.assertEqual(finding.repo_id, "test-repo")
        self.assertEqual(finding.snapshot_id, "test-snapshot")
        self.assertEqual(finding.scanner_name, "test-scanner")
        self.assertEqual(finding.rule.rule_id, "test-rule")
        self.assertEqual(finding.message, "Test finding message")
        self.assertEqual(finding.severity.level, "error")
        self.assertEqual(finding.severity.score, 8.5)
        self.assertEqual(finding.location.file_path, "test.py")
        self.assertEqual(finding.location.line_number, 20)

    def test_fingerprint_generation(self) -> None:
        """Test fingerprint generation for deduplication."""
        fingerprint1 = self.normalizer._generate_fingerprint("rule-1", "file.py", 10)
        fingerprint2 = self.normalizer._generate_fingerprint("rule-1", "file.py", 10)
        fingerprint3 = self.normalizer._generate_fingerprint("rule-1", "file.py", 20)
        
        self.assertEqual(fingerprint1, fingerprint2)  # Same finding should have same fingerprint
        self.assertNotEqual(fingerprint1, fingerprint3)  # Different line should have different fingerprint


class TestFindingsStore(unittest.TestCase):
    """Test findings storage functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = create_findings_store(Path(self.temp_dir.name))

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_ingest_findings(self) -> None:
        """Test findings ingestion."""
        findings_data = {
            "scanner": "test-scanner",
            "findings": [
                {
                    "rule_id": "test-rule",
                    "message": "Test finding",
                    "severity": "warning",
                    "file": "test.py",
                    "line": 10
                }
            ]
        }
        
        report = self.store.ingest_findings(findings_data, "test-repo", "test-snapshot")
        
        self.assertIsInstance(report, FindingsIngestionReport)
        self.assertEqual(report.repo_id, "test-repo")
        self.assertEqual(report.snapshot_id, "test-snapshot")
        self.assertEqual(report.scanner_name, "test-scanner")
        self.assertEqual(report.total_findings, 1)
        self.assertEqual(report.ingested_findings, 1)
        self.assertEqual(report.duplicate_findings, 0)

    def test_query_findings(self) -> None:
        """Test findings querying."""
        # First ingest some findings
        findings_data = {
            "scanner": "test-scanner",
            "findings": [
                {
                    "rule_id": "rule-1",
                    "message": "Finding 1",
                    "severity": "error",
                    "file": "file1.py",
                    "line": 10
                },
                {
                    "rule_id": "rule-2",
                    "message": "Finding 2",
                    "severity": "warning",
                    "file": "file2.py",
                    "line": 20
                }
            ]
        }
        
        self.store.ingest_findings(findings_data, "test-repo", "test-snapshot")
        
        # Query all findings
        findings = self.store.query_findings("test-repo", "test-snapshot")
        self.assertEqual(len(findings), 2)
        
        # Query by severity
        error_findings = self.store.query_findings(
            "test-repo", "test-snapshot", severity_filter=["error"]
        )
        self.assertEqual(len(error_findings), 1)
        self.assertEqual(error_findings[0]["severity_level"], "error")
        
        # Query by file
        file_findings = self.store.query_findings(
            "test-repo", "test-snapshot", file_filter=["file1.py"]
        )
        self.assertEqual(len(file_findings), 1)
        self.assertEqual(file_findings[0]["file_path"], "file1.py")

    def test_finding_summary(self) -> None:
        """Test findings summary generation."""
        findings_data = {
            "scanner": "test-scanner",
            "findings": [
                {
                    "rule_id": "rule-1",
                    "message": "Finding 1",
                    "severity": "error",
                    "file": "file1.py",
                    "line": 10
                },
                {
                    "rule_id": "rule-2",
                    "message": "Finding 2",
                    "severity": "warning",
                    "file": "file2.py",
                    "line": 20
                },
                {
                    "rule_id": "rule-1",
                    "message": "Finding 3",
                    "severity": "warning",
                    "file": "file1.py",
                    "line": 30
                }
            ]
        }
        
        self.store.ingest_findings(findings_data, "test-repo", "test-snapshot")
        
        summary = self.store.get_finding_summary("test-repo", "test-snapshot")
        
        self.assertEqual(summary["repo_id"], "test-repo")
        self.assertEqual(summary["snapshot_id"], "test-snapshot")
        self.assertEqual(summary["total_findings"], 3)
        self.assertEqual(summary["severity_counts"]["error"], 1)
        self.assertEqual(summary["severity_counts"]["warning"], 2)

    def test_delete_findings(self) -> None:
        """Test findings deletion."""
        # Ingest findings
        findings_data = {
            "scanner": "test-scanner",
            "findings": [
                {
                    "rule_id": "test-rule",
                    "message": "Test finding",
                    "severity": "warning",
                    "file": "test.py",
                    "line": 10
                }
            ]
        }
        
        self.store.ingest_findings(findings_data, "test-repo", "test-snapshot")
        
        # Verify findings exist
        findings = self.store.query_findings("test-repo", "test-snapshot")
        self.assertEqual(len(findings), 1)
        
        # Delete findings
        deleted_count = self.store.delete_findings("test-repo", "test-snapshot")
        self.assertEqual(deleted_count, 1)
        
        # Verify findings are gone
        findings = self.store.query_findings("test-repo", "test-snapshot")
        self.assertEqual(len(findings), 0)


class TestFindingsIngestionService(unittest.TestCase):
    """Test findings ingestion service functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.service = create_findings_ingestion_service(Path(self.temp_dir.name))

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_ingest_findings_from_data(self) -> None:
        """Test findings ingestion from data."""
        findings_data = {
            "scanner": "test-scanner",
            "findings": [
                {
                    "rule_id": "test-rule",
                    "message": "Test finding",
                    "severity": "warning",
                    "file": "test.py",
                    "line": 10
                }
            ]
        }
        
        result = self.service.ingest_findings_from_data(
            findings_data, "test-repo", "test-snapshot", "test-scanner"
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["scanner_name"], "test-scanner")
        self.assertEqual(result["ingestion_report"]["total_findings"], 1)
        self.assertEqual(result["ingestion_report"]["ingested_findings"], 1)

    def test_query_findings(self) -> None:
        """Test findings querying through service."""
        # Ingest findings first
        findings_data = {
            "scanner": "test-scanner",
            "findings": [
                {
                    "rule_id": "test-rule",
                    "message": "Test finding",
                    "severity": "warning",
                    "file": "test.py",
                    "line": 10
                }
            ]
        }
        
        self.service.ingest_findings_from_data(
            findings_data, "test-repo", "test-snapshot", "test-scanner"
        )
        
        # Query findings
        result = self.service.query_findings("test-repo", "test-snapshot")
        
        self.assertTrue(result["success"])
        self.assertEqual(result["total_count"], 1)
        self.assertEqual(len(result["findings"]), 1)

    def test_validate_findings_format(self) -> None:
        """Test findings format validation."""
        # Valid SARIF
        valid_sarif = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0",
            "runs": []
        }
        
        result = self.service.validate_findings_format(valid_sarif)
        self.assertTrue(result["valid"])
        self.assertEqual(result["format"], "sarif")
        
        # Valid JSON
        valid_json = {
            "findings": []
        }
        
        result = self.service.validate_findings_format(valid_json)
        self.assertTrue(result["valid"])
        self.assertEqual(result["format"], "json")
        
        # Invalid format
        invalid = {"invalid": "data"}
        
        result = self.service.validate_findings_format(invalid)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
