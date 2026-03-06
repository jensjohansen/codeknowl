"""
File: backend/src/codeknowl/findings_ingestion.py
Purpose: Findings ingestion service for SARIF/JSON pipeline.
Product/business importance: Enables Milestone 8 findings ingestion as optional enrichment linked to repos/snapshots.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from codeknowl.findings_store import create_findings_store

logger = logging.getLogger(__name__)


class FindingsIngestionService:
    """Service for ingesting scanner findings.

    Why this exists:
    - Coordinates findings ingestion pipeline as specified in Architecture & Design.
    - Provides high-level interface for findings processing.
    - Supports SARIF/JSON format ingestion with traceable file/location links.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize findings ingestion service.

        Why this exists:
        - Sets up findings store for ingestion operations.
        
        Args:
            data_dir: Data directory for storage
        """
        self._findings_store = create_findings_store(data_dir)

    def ingest_findings_from_file(
        self, file_path: Path, repo_id: str, snapshot_id: str
    ) -> Dict[str, Any]:
        """Ingest findings from a file.

        Why this exists:
        - Supports file-based findings ingestion from CI pipelines.
        - Implements Architecture & Design findings ingestion workflow.
        - Links findings to repos/snapshots with traceable file/location links.
        
        Args:
            file_path: Path to findings file (SARIF/JSON)
            repo_id: Repository identifier
            snapshot_id: Snapshot identifier
            
        Returns:
            Ingestion report
        """
        try:
            # Read and parse findings file
            with open(file_path, "r", encoding="utf-8") as f:
                import json
                findings_data = json.load(f)
            
            # Ingest findings
            report = self._findings_store.ingest_findings(findings_data, repo_id, snapshot_id)
            
            logger.info(
                "Successfully ingested findings from %s: %d ingested, %d duplicates",
                file_path, report.ingested_findings, report.duplicate_findings
            )
            
            return {
                "success": True,
                "file_path": str(file_path),
                "ingestion_report": {
                    "repo_id": report.repo_id,
                    "snapshot_id": report.snapshot_id,
                    "scanner_name": report.scanner_name,
                    "total_findings": report.total_findings,
                    "ingested_findings": report.ingested_findings,
                    "duplicate_findings": report.duplicate_findings,
                    "errors": report.errors,
                    "warnings": report.warnings,
                    "timestamp": report.timestamp.isoformat()
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to ingest findings from {file_path}: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "file_path": str(file_path),
                "error": str(e)
            }

    def ingest_findings_from_data(
        self, findings_data: Dict[str, Any], repo_id: str, snapshot_id: str, scanner_name: str
    ) -> Dict[str, Any]:
        """Ingest findings from data.

        Why this exists:
        - Supports direct data-based findings ingestion.
        - Enables API-based findings upload.
        - Provides flexible ingestion interface.
        
        Args:
            findings_data: Findings data (SARIF/JSON)
            repo_id: Repository identifier
            snapshot_id: Snapshot identifier
            scanner_name: Scanner name for tracking
            
        Returns:
            Ingestion report
        """
        try:
            # Ingest findings
            report = self._findings_store.ingest_findings(findings_data, repo_id, snapshot_id)
            
            logger.info(
                "Successfully ingested findings from %s scanner: %d ingested, %d duplicates",
                scanner_name, report.ingested_findings, report.duplicate_findings
            )
            
            return {
                "success": True,
                "scanner_name": scanner_name,
                "ingestion_report": {
                    "repo_id": report.repo_id,
                    "snapshot_id": report.snapshot_id,
                    "scanner_name": report.scanner_name,
                    "total_findings": report.total_findings,
                    "ingested_findings": report.ingested_findings,
                    "duplicate_findings": report.duplicate_findings,
                    "errors": report.errors,
                    "warnings": report.warnings,
                    "timestamp": report.timestamp.isoformat()
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to ingest findings from {scanner_name}: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "scanner_name": scanner_name,
                "error": str(e)
            }

    def query_findings(
        self,
        repo_id: str,
        snapshot_id: Optional[str] = None,
        severity_filter: Optional[list[str]] = None,
        rule_filter: Optional[list[str]] = None,
        file_filter: Optional[list[str]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Query findings with filters.

        Why this exists:
        - Provides findings query capabilities as required by Architecture & Design.
        - Supports filtering by repo/snapshot with traceable file/location links.
        - Enables flexible findings exploration and analysis.
        
        Args:
            repo_id: Repository identifier
            snapshot_id: Optional snapshot identifier
            severity_filter: Optional severity levels to include
            rule_filter: Optional rule IDs to include
            file_filter: Optional file paths to include
            limit: Optional result limit
            
        Returns:
            Query results
        """
        try:
            findings = self._findings_store.query_findings(
                repo_id=repo_id,
                snapshot_id=snapshot_id,
                severity_filter=severity_filter,
                rule_filter=rule_filter,
                file_filter=file_filter,
                limit=limit
            )
            
            logger.info(
                "Queried %d findings for repo %s, snapshot %s",
                len(findings), repo_id, snapshot_id or "all"
            )
            
            return {
                "success": True,
                "repo_id": repo_id,
                "snapshot_id": snapshot_id,
                "findings": findings,
                "total_count": len(findings)
            }
            
        except Exception as e:
            error_msg = f"Failed to query findings: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": str(e)
            }

    def get_finding_summary(
        self, repo_id: str, snapshot_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get findings summary.

        Why this exists:
        - Provides high-level findings overview.
        - Supports dashboard and monitoring needs.
        - Enables trend analysis across snapshots.
        
        Args:
            repo_id: Repository identifier
            snapshot_id: Optional snapshot identifier
            
        Returns:
            Findings summary
        """
        try:
            summary = self._findings_store.get_finding_summary(repo_id, snapshot_id)
            
            logger.info(
                "Generated findings summary for repo %s, snapshot %s: %d total findings",
                repo_id, snapshot_id or "all", summary["total_findings"]
            )
            
            return {
                "success": True,
                "summary": summary
            }
            
        except Exception as e:
            error_msg = f"Failed to get findings summary: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": str(e)
            }

    def delete_findings(
        self, repo_id: str, snapshot_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete findings.

        Why this exists:
        - Supports cleanup of old or invalid findings.
        - Enables re-ingestion with corrected data.
        
        Args:
            repo_id: Repository identifier
            snapshot_id: Optional snapshot identifier
            
        Returns:
            Deletion result
        """
        try:
            deleted_count = self._findings_store.delete_findings(repo_id, snapshot_id)
            
            logger.info(
                "Deleted %d findings for repo %s, snapshot %s",
                deleted_count, repo_id, snapshot_id or "all"
            )
            
            return {
                "success": True,
                "deleted_count": deleted_count
            }
            
        except Exception as e:
            error_msg = f"Failed to delete findings: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": str(e)
            }

    def validate_findings_format(self, findings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate findings format.

        Why this exists:
        - Provides pre-ingestion validation.
        - Helps identify format issues early.
        - Supports debugging and error reporting.
        
        Args:
            findings_data: Findings data to validate
            
        Returns:
            Validation result
        """
        try:
            # Check if it's SARIF
            if "$schema" in findings_data and "sarif" in findings_data["$schema"]:
                # Basic SARIF validation
                required_fields = ["$schema", "runs"]
                missing_fields = [field for field in required_fields if field not in findings_data]
                
                if missing_fields:
                    return {
                        "valid": False,
                        "format": "sarif",
                        "error": f"Missing required SARIF fields: {missing_fields}"
                    }
                
                runs = findings_data.get("runs", [])
                if not runs:
                    return {
                        "valid": True,
                        "format": "sarif",
                        "warning": "No runs found in SARIF data"
                    }
                
                return {
                    "valid": True,
                    "format": "sarif",
                    "runs_count": len(runs)
                }
            
            else:
                # Generic JSON validation
                if "findings" not in findings_data:
                    return {
                        "valid": False,
                        "format": "json",
                        "error": "Missing 'findings' field in JSON data"
                    }
                
                findings = findings_data.get("findings", [])
                return {
                    "valid": True,
                    "format": "json",
                    "findings_count": len(findings)
                }
                
        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation failed: {e}"
            }


def create_findings_ingestion_service(data_dir: Path) -> FindingsIngestionService:
    """Create findings ingestion service instance.

    Why this exists:
    - Factory function for creating findings ingestion service.
    
    Args:
        data_dir: Data directory for storage
        
    Returns:
        Configured findings ingestion service
    """
    return FindingsIngestionService(data_dir)
