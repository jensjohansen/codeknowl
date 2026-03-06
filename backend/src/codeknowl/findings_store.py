"""
File: backend/src/codeknowl/findings_store.py
Purpose: Findings storage and query service for SARIF/JSON ingestion.
Product/business importance: Enables Milestone 8 findings ingestion with traceable file/location links.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from codeknowl import db
from codeknowl.findings import Finding, FindingsIngestionReport, create_findings_normalizer

logger = logging.getLogger(__name__)


class FindingsStore:
    """Storage and query service for findings.

    Why this exists:
    - Implements findings storage and query semantics as required by ITD-19.
    - Provides traceable file/location links as required by PRD.
    - Supports findings ingestion pipeline from Architecture & Design.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize findings store.

        Why this exists:
        - Sets up database connection for findings storage.
        
        Args:
            data_dir: Data directory for database
        """
        self._data_dir = data_dir
        self._conn = db.connect(data_dir)
        self._normalizer = create_findings_normalizer()
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize findings database schema.

        Why this exists:
        - Creates tables for findings storage.
        - Ensures proper indexes for query performance.
        """
        cursor = self._conn.cursor()
        
        # Findings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                finding_id TEXT PRIMARY KEY,
                repo_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                scanner_name TEXT NOT NULL,
                scanner_version TEXT,
                rule_id TEXT NOT NULL,
                rule_name TEXT,
                rule_description TEXT,
                rule_help_uri TEXT,
                rule_category TEXT,
                rule_tags TEXT,  -- JSON array
                message TEXT NOT NULL,
                severity_level TEXT NOT NULL,
                severity_score REAL,
                file_path TEXT NOT NULL,
                line_number INTEGER,
                column_number INTEGER,
                end_line INTEGER,
                end_column INTEGER,
                snippet TEXT,
                timestamp TEXT NOT NULL,  -- ISO 8601
                fingerprint TEXT,
                additional_data TEXT  -- JSON
            )
        """)
        
        # Indexes for query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_findings_repo_snapshot 
            ON findings(repo_id, snapshot_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_findings_repo_file 
            ON findings(repo_id, file_path)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_findings_severity 
            ON findings(severity_level)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_findings_fingerprint 
            ON findings(fingerprint)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_findings_timestamp 
            ON findings(timestamp)
        """)
        
        self._conn.commit()

    def ingest_findings(
        self, findings_data: Dict[str, Any], repo_id: str, snapshot_id: str
    ) -> FindingsIngestionReport:
        """Ingest findings from scanner output.

        Why this exists:
        - Implements SARIF/JSON ingestion pipeline as required by Architecture & Design.
        - Normalizes findings into consistent schema.
        - Links findings to repos/snapshots with traceable file/location links.
        
        Args:
            findings_data: Scanner output data (SARIF/JSON)
            repo_id: Repository identifier
            snapshot_id: Snapshot identifier
            
        Returns:
            Ingestion report with statistics
        """
        # Determine format and normalize
        if "$schema" in findings_data and "sarif" in findings_data["$schema"]:
            findings = self._normalizer.normalize_sarif(findings_data, repo_id, snapshot_id)
            scanner_name = "sarif"
        else:
            findings = self._normalizer.normalize_json(findings_data, repo_id, snapshot_id)
            scanner_name = findings_data.get("scanner", "json")
        
        # Create ingestion report
        report = FindingsIngestionReport(
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            scanner_name=scanner_name,
            total_findings=len(findings),
            ingested_findings=0,
            duplicate_findings=0
        )
        
        # Ingest findings
        cursor = self._conn.cursor()
        
        for finding in findings:
            try:
                # Check for duplicates using fingerprint
                if self._is_duplicate_finding(cursor, finding):
                    report.duplicate_findings += 1
                    continue
                
                # Insert finding
                self._insert_finding(cursor, finding)
                report.ingested_findings += 1
                
            except Exception as e:
                error_msg = f"Failed to insert finding {finding.finding_id}: {e}"
                logger.error(error_msg)
                report.errors.append(error_msg)
        
        self._conn.commit()
        
        logger.info(
            "Ingested %d findings for repo %s, snapshot %s (%d duplicates)",
            report.ingested_findings, repo_id, snapshot_id, report.duplicate_findings
        )
        
        return report

    def _is_duplicate_finding(self, cursor, finding: Finding) -> bool:
        """Check if finding is a duplicate.

        Why this exists:
        - Prevents duplicate findings across ingestions.
        - Uses fingerprint for efficient deduplication.
        
        Args:
            cursor: Database cursor
            finding: Finding to check
            
        Returns:
            True if finding is duplicate
        """
        if not finding.fingerprint:
            return False
        
        cursor.execute(
            "SELECT 1 FROM findings WHERE fingerprint = ? AND repo_id = ? AND snapshot_id = ?",
            (finding.fingerprint, finding.repo_id, finding.snapshot_id)
        )
        return cursor.fetchone() is not None

    def _insert_finding(self, cursor, finding: Finding) -> None:
        """Insert a finding into the database.

        Why this exists:
        - Stores normalized finding with all metadata.
        - Preserves traceable file/location links.
        
        Args:
            cursor: Database cursor
            finding: Finding to insert
        """
        import json
        
        cursor.execute("""
            INSERT INTO findings (
                finding_id, repo_id, snapshot_id, scanner_name, scanner_version,
                rule_id, rule_name, rule_description, rule_help_uri, rule_category, rule_tags,
                message, severity_level, severity_score,
                file_path, line_number, column_number, end_line, end_column, snippet,
                timestamp, fingerprint, additional_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            finding.finding_id,
            finding.repo_id,
            finding.snapshot_id,
            finding.scanner_name,
            finding.scanner_version,
            finding.rule.rule_id,
            finding.rule.name,
            finding.rule.description,
            finding.rule.help_uri,
            finding.rule.category,
            json.dumps(finding.rule.tags),
            finding.message,
            finding.severity.level,
            finding.severity.score,
            finding.location.file_path,
            finding.location.line_number,
            finding.location.column_number,
            finding.location.end_line,
            finding.location.end_column,
            finding.location.snippet,
            finding.timestamp.isoformat(),
            finding.fingerprint,
            json.dumps(finding.additional_data)
        ))

    def query_findings(
        self,
        repo_id: str,
        snapshot_id: Optional[str] = None,
        severity_filter: Optional[List[str]] = None,
        rule_filter: Optional[List[str]] = None,
        file_filter: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
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
            List of findings
        """
        cursor = self._conn.cursor()
        
        # Build query
        query = "SELECT * FROM findings WHERE repo_id = ?"
        params = [repo_id]
        
        if snapshot_id:
            query += " AND snapshot_id = ?"
            params.append(snapshot_id)
        
        if severity_filter:
            placeholders = ",".join("?" * len(severity_filter))
            query += f" AND severity_level IN ({placeholders})"
            params.extend(severity_filter)
        
        if rule_filter:
            placeholders = ",".join("?" * len(rule_filter))
            query += f" AND rule_id IN ({placeholders})"
            params.extend(rule_filter)
        
        if file_filter:
            placeholders = ",".join("?" * len(file_filter))
            query += f" AND file_path IN ({placeholders})"
            params.extend(file_filter)
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert rows to dictionaries
        findings = []
        columns = [desc[0] for desc in cursor.description]
        
        for row in rows:
            finding = dict(zip(columns, row, strict=True))
            # Parse JSON fields
            import json
            if finding["rule_tags"]:
                finding["rule_tags"] = json.loads(finding["rule_tags"])
            if finding["additional_data"]:
                finding["additional_data"] = json.loads(finding["additional_data"])
            findings.append(finding)
        
        return findings

    def get_finding_summary(self, repo_id: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        """Get summary statistics for findings.

        Why this exists:
        - Provides high-level findings overview.
        - Supports dashboard and monitoring needs.
        - Enables trend analysis across snapshots.
        
        Args:
            repo_id: Repository identifier
            snapshot_id: Optional snapshot identifier
            
        Returns:
            Findings summary statistics
        """
        cursor = self._conn.cursor()
        
        # Base query
        base_query = "WHERE repo_id = ?"
        params = [repo_id]
        
        if snapshot_id:
            base_query += " AND snapshot_id = ?"
            params.append(snapshot_id)
        
        # Total findings
        cursor.execute(f"SELECT COUNT(*) FROM findings {base_query}", params)
        total_findings = cursor.fetchone()[0]
        
        # Findings by severity
        cursor.execute(f"""
            SELECT severity_level, COUNT(*) 
            FROM findings {base_query} 
            GROUP BY severity_level
        """, params)
        severity_counts = dict(cursor.fetchall())
        
        # Findings by rule
        cursor.execute(f"""
            SELECT rule_id, rule_name, COUNT(*) 
            FROM findings {base_query} 
            GROUP BY rule_id, rule_name 
            ORDER BY COUNT(*) DESC 
            LIMIT 10
        """, params)
        top_rules = [
            {"rule_id": row[0], "rule_name": row[1], "count": row[2]}
            for row in cursor.fetchall()
        ]
        
        # Findings by file
        cursor.execute(f"""
            SELECT file_path, COUNT(*) 
            FROM findings {base_query} 
            GROUP BY file_path 
            ORDER BY COUNT(*) DESC 
            LIMIT 10
        """, params)
        top_files = [
            {"file_path": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]
        
        return {
            "repo_id": repo_id,
            "snapshot_id": snapshot_id,
            "total_findings": total_findings,
            "severity_counts": severity_counts,
            "top_rules": top_rules,
            "top_files": top_files
        }

    def delete_findings(self, repo_id: str, snapshot_id: Optional[str] = None) -> int:
        """Delete findings for repo/snapshot.

        Why this exists:
        - Supports cleanup of old or invalid findings.
        - Enables re-ingestion with corrected data.
        
        Args:
            repo_id: Repository identifier
            snapshot_id: Optional snapshot identifier
            
        Returns:
            Number of findings deleted
        """
        cursor = self._conn.cursor()
        
        if snapshot_id:
            cursor.execute(
                "DELETE FROM findings WHERE repo_id = ? AND snapshot_id = ?",
                (repo_id, snapshot_id)
            )
        else:
            cursor.execute(
                "DELETE FROM findings WHERE repo_id = ?",
                (repo_id,)
            )
        
        deleted_count = cursor.rowcount
        self._conn.commit()
        
        logger.info("Deleted %d findings for repo %s, snapshot %s", deleted_count, repo_id, snapshot_id)
        
        return deleted_count


def create_findings_store(data_dir: Path) -> FindingsStore:
    """Create findings store instance.

    Why this exists:
    - Factory function for creating findings store.
    
    Args:
        data_dir: Data directory for database
        
    Returns:
        Configured findings store
    """
    return FindingsStore(data_dir)
