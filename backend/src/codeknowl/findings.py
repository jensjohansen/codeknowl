"""
File: backend/src/codeknowl/findings.py
Purpose: Findings data model and schema for SARIF/JSON ingestion.
Product/business importance: Enables Milestone 8 findings ingestion as optional enrichment linked to repos/snapshots.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class FindingLocation:
    """Location information for a finding.

    Why this exists:
    - Provides traceable file/location links as required by PRD.
    - Normalizes location data across different scanner formats.
    - Supports precise positioning within source files.
    """
    file_path: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    snippet: Optional[str] = None


@dataclass
class FindingSeverity:
    """Severity classification for findings.

    Why this exists:
    - Normalizes severity levels across different scanners.
    - Provides consistent severity semantics for querying.
    - Supports filtering and prioritization.
    """
    level: str  # "error", "warning", "note", "info"
    score: Optional[float] = None  # 0.0-10.0 if available


@dataclass
class FindingRule:
    """Rule information for a finding.

    Why this exists:
    - Tracks which rule generated the finding.
    - Provides rule metadata for context.
    - Supports rule-based filtering and analysis.
    """
    rule_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    help_uri: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class Finding:
    """Normalized finding representation.

    Why this exists:
    - Core data model for findings ingestion as specified in Architecture & Design.
    - Normalizes SARIF/JSON findings into consistent schema.
    - Enables linking findings to repos/snapshots with traceable file/location links.
    """
    repo_id: str
    snapshot_id: str
    scanner_name: str
    rule: FindingRule
    message: str
    severity: FindingSeverity
    location: FindingLocation
    finding_id: str = field(default_factory=lambda: str(uuid4()))
    scanner_version: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fingerprint: Optional[str] = None  # For deduplication
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FindingsIngestionReport:
    """Report for findings ingestion process.

    Why this exists:
    - Tracks ingestion statistics and errors.
    - Provides feedback on scanner output processing.
    - Supports monitoring and debugging.
    """
    repo_id: str
    snapshot_id: str
    scanner_name: str
    total_findings: int
    ingested_findings: int
    duplicate_findings: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FindingsSchemaError(Exception):
    """Exception raised for findings schema validation errors.

    Why this exists:
    - Provides specific error handling for schema issues.
    - Enables detailed error reporting for ingestion failures.
    """
    pass


class FindingsNormalizer:
    """Normalizes scanner outputs into CodeKnowl findings schema.

    Why this exists:
    - Implements Architecture & Design requirement to normalize findings.
    - Handles SARIF/JSON format conversion.
    - Ensures consistent data model across different scanners.
    """

    def normalize_sarif(self, sarif_data: Dict[str, Any], repo_id: str, snapshot_id: str) -> List[Finding]:
        """Normalize SARIF format findings.

        Why this exists:
        - SARIF is the standard format for security/static analysis findings.
        - Converts SARIF to CodeKnowl findings schema.
        - Preserves all relevant information for traceability.
        
        Args:
            sarif_data: SARIF format data
            repo_id: Repository identifier
            snapshot_id: Snapshot identifier
            
        Returns:
            List of normalized findings
            
        Raises:
            FindingsSchemaError: If SARIF format is invalid
        """
        findings = []
        
        try:
            # Validate SARIF structure
            if not isinstance(sarif_data, dict) or "$schema" not in sarif_data:
                raise FindingsSchemaError("Invalid SARIF format: missing schema")
            
            runs = sarif_data.get("runs", [])
            if not runs:
                return findings  # No findings to process
            
            for run in runs:
                scanner_info = run.get("tool", {}).get("driver", {})
                scanner_name = scanner_info.get("name", "unknown")
                scanner_version = scanner_info.get("version")
                
                results = run.get("results", [])
                
                for result in results:
                    try:
                        finding = self._normalize_sarif_result(
                            result, scanner_name, scanner_version, repo_id, snapshot_id
                        )
                        findings.append(finding)
                    except Exception as e:
                        # Log error but continue processing other results
                        print(f"Error normalizing SARIF result: {e}")
                        continue
                        
        except Exception as e:
            raise FindingsSchemaError(f"Failed to normalize SARIF: {e}") from e
        
        return findings

    def _normalize_sarif_result(
        self, result: Dict[str, Any], scanner_name: str, scanner_version: Optional[str],
        repo_id: str, snapshot_id: str
    ) -> Finding:
        """Normalize a single SARIF result.

        Why this exists:
        - Converts individual SARIF result to Finding object.
        - Extracts and normalizes all relevant fields.
        
        Args:
            result: SARIF result data
            scanner_name: Scanner name
            scanner_version: Scanner version
            repo_id: Repository identifier
            snapshot_id: Snapshot identifier
            
        Returns:
            Normalized Finding object
        """
        # Extract rule information
        rule_info = result.get("rule", {})
        rule = FindingRule(
            rule_id=rule_info.get("id", "unknown"),
            name=rule_info.get("name"),
            description=rule_info.get("shortDescription", {}).get("text"),
            help_uri=rule_info.get("helpUri"),
            category=rule_info.get("properties", {}).get("category"),
            tags=rule_info.get("properties", {}).get("tags", [])
        )
        
        # Extract message
        message_text = result.get("message", {}).get("text", "No message")
        
        # Extract severity
        level = result.get("level", "warning")
        severity = FindingSeverity(level=level)
        
        # Extract location
        locations = result.get("locations", [])
        if not locations:
            raise FindingsSchemaError("Finding has no location information")
        
        location = self._normalize_sarif_location(locations[0])
        
        # Generate fingerprint for deduplication
        fingerprint = self._generate_fingerprint(
            rule.rule_id, location.file_path, location.line_number
        )
        
        return Finding(
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            scanner_name=scanner_name,
            scanner_version=scanner_version,
            rule=rule,
            message=message_text,
            severity=severity,
            location=location,
            fingerprint=fingerprint,
            additional_data={"sarif_result": result}
        )

    def _normalize_sarif_location(self, location: Dict[str, Any]) -> FindingLocation:
        """Normalize SARIF location to FindingLocation.

        Why this exists:
        - Converts SARIF location format to standardized location.
        - Handles different SARIF location structures.
        
        Args:
            location: SARIF location data
            
        Returns:
            Normalized FindingLocation
        """
        physical_location = location.get("physicalLocation", {})
        artifact_location = physical_location.get("artifactLocation", {})
        uri = artifact_location.get("uri", "")
        
        # Extract region information
        region = physical_location.get("region", {})
        start_line = region.get("startLine")
        start_column = region.get("startColumn")
        end_line = region.get("endLine")
        end_column = region.get("endColumn")
        
        # Extract snippet if available
        snippet = None
        if "snippet" in region:
            snippet = region["snippet"].get("text")
        
        return FindingLocation(
            file_path=uri,
            line_number=start_line,
            column_number=start_column,
            end_line=end_line,
            end_column=end_column,
            snippet=snippet
        )

    def normalize_json(self, json_data: Dict[str, Any], repo_id: str, snapshot_id: str) -> List[Finding]:
        """Normalize generic JSON format findings.

        Why this exists:
        - Handles non-SARIF JSON formats from various scanners.
        - Provides flexible normalization for different schemas.
        - Ensures consistent data model regardless of input format.
        
        Args:
            json_data: Generic JSON findings data
            repo_id: Repository identifier
            snapshot_id: Snapshot identifier
            
        Returns:
            List of normalized findings
        """
        findings = []
        
        # This is a basic implementation - would be extended based on specific scanner formats
        scanner_name = json_data.get("scanner", "unknown")
        scanner_version = json_data.get("version")
        
        results = json_data.get("findings", [])
        
        for result in results:
            try:
                finding = self._normalize_json_result(
                    result, scanner_name, scanner_version, repo_id, snapshot_id
                )
                findings.append(finding)
            except Exception as e:
                print(f"Error normalizing JSON result: {e}")
                continue
        
        return findings

    def _normalize_json_result(
        self, result: Dict[str, Any], scanner_name: str, scanner_version: Optional[str],
        repo_id: str, snapshot_id: str
    ) -> Finding:
        """Normalize a single JSON result.

        Why this exists:
        - Converts generic JSON result to Finding object.
        - Handles flexible JSON schema variations.
        
        Args:
            result: JSON result data
            scanner_name: Scanner name
            scanner_version: Scanner version
            repo_id: Repository identifier
            snapshot_id: Snapshot identifier
            
        Returns:
            Normalized Finding object
        """
        rule = FindingRule(
            rule_id=result.get("rule_id", "unknown"),
            name=result.get("rule_name"),
            description=result.get("description"),
            category=result.get("category")
        )
        
        severity = FindingSeverity(
            level=result.get("severity", "warning"),
            score=result.get("score")
        )
        
        location = FindingLocation(
            file_path=result.get("file", ""),
            line_number=result.get("line"),
            column_number=result.get("column"),
            snippet=result.get("snippet")
        )
        
        fingerprint = self._generate_fingerprint(
            rule.rule_id, location.file_path, location.line_number
        )
        
        return Finding(
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            scanner_name=scanner_name,
            scanner_version=scanner_version,
            rule=rule,
            message=result.get("message", ""),
            severity=severity,
            location=location,
            fingerprint=fingerprint,
            additional_data={"original_result": result}
        )

    def _generate_fingerprint(self, rule_id: str, file_path: str, line_number: Optional[int]) -> str:
        """Generate fingerprint for finding deduplication.

        Why this exists:
        - Enables detection of duplicate findings across snapshots.
        - Supports incremental ingestion without duplicates.
        - Uses rule, file, and line for stable fingerprinting.
        
        Args:
            rule_id: Rule identifier
            file_path: File path
            line_number: Line number
            
        Returns:
            Fingerprint string
        """
        import hashlib
        
        fingerprint_data = f"{rule_id}:{file_path}:{line_number or 0}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]


def create_findings_normalizer() -> FindingsNormalizer:
    """Create findings normalizer instance.

    Why this exists:
    - Factory function for creating normalizer.
    
    Returns:
        Configured findings normalizer
    """
    return FindingsNormalizer()
