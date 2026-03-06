"""
File: backend/src/codeknowl/metrics.py
Purpose: Prometheus metrics export for observability.
Product/business importance: Enables Milestone 6 observability with Loki + Prometheus/Grafana.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


class PrometheusMetrics:
    """Prometheus metrics for CodeKnowl observability.

    Why this exists:
    - Provides Prometheus-compatible metrics for indexing throughput, failures, and latency.
    """

    def __init__(self) -> None:
        """Initialize Prometheus metrics.

        Why this exists:
        - Sets up counters and histograms for key operations.
        """
        # HTTP request counters
        self.http_requests_total = Counter(
            "codeknowl_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        
        # Indexing operations
        self.index_operations_total = Counter(
            "codeknowl_index_operations_total",
            "Total indexing operations",
            ["status"],
        )
        
        self.index_duration_seconds = Histogram(
            "codeknowl_index_duration_seconds",
            "Time spent indexing repositories",
            ["status"],
        )
        
        # Update operations
        self.update_operations_total = Counter(
            "codeknowl_update_operations_total",
            "Total update operations",
            ["status"],
        )
        
        self.update_duration_seconds = Histogram(
            "codeknowl_update_duration_seconds",
            "Time spent updating repositories",
            ["status"],
        )
        
        # Job queue metrics
        self.jobs_queued_total = Counter(
            "codeknowl_jobs_queued_total",
            "Total jobs queued",
            ["job_type"],
        )
        
        self.jobs_completed_total = Counter(
            "codeknowl_jobs_completed_total",
            "Total jobs completed",
            ["job_type", "status"],
        )
        
        # QA operations
        self.qa_requests_total = Counter(
            "codeknowl_qa_requests_total",
            "Total QA requests",
            ["type", "status"],
        )

    def inc_http_request(self, method: str, endpoint: str, status: int) -> None:
        """Increment HTTP request counter.

        Why this exists:
        - Track HTTP request volume by method, endpoint, and status.
        """
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()

    def inc_index_operation(self, status: str, duration_seconds: float | None = None) -> None:
        """Record indexing operation.

        Why this exists:
        - Track indexing operations and their duration.
        """
        self.index_operations_total.labels(status=status).inc()
        if duration_seconds is not None:
            self.index_duration_seconds.labels(status=status).observe(duration_seconds)

    def inc_update_operation(self, status: str, duration_seconds: float | None = None) -> None:
        """Record update operation.

        Why this exists:
        - Track update operations and their duration.
        """
        self.update_operations_total.labels(status=status).inc()
        if duration_seconds is not None:
            self.update_duration_seconds.labels(status=status).observe(duration_seconds)

    def inc_job_queued(self, job_type: str) -> None:
        """Record job enqueued.

        Why this exists:
        - Track jobs submitted to the queue.
        """
        self.jobs_queued_total.labels(job_type=job_type).inc()

    def inc_job_completed(self, job_type: str, status: str) -> None:
        """Record job completion.

        Why this exists:
        - Track job completion status.
        """
        self.jobs_completed_total.labels(job_type=job_type, status=status).inc()

    def inc_qa_request(self, qa_type: str, status: str) -> None:
        """Record QA request.

        Why this exists:
        - Track QA operations by type and status.
        """
        self.qa_requests_total.labels(type=qa_type, status=status).inc()

    def export(self) -> tuple[str, bytes]:
        """Export metrics in Prometheus format.

        Why this exists:
        - Provides Prometheus-compatible metrics endpoint.
        
        Returns:
            Content type and metrics data.
        """
        return CONTENT_TYPE_LATEST, generate_latest()


# Global metrics instance
METRICS = PrometheusMetrics()
