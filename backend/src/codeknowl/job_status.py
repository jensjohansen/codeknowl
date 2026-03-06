"""
File: backend/src/codeknowl/job_status.py
Purpose: Job status tracking and persistence.
Product/business importance: Provides visibility into async job execution.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from arq import ArqRedis


class JobStatusStore:
    """Store and retrieve job status information.

    Why this exists:
    - Allows operators to check job progress and failures.
    """

    def __init__(self, redis: ArqRedis) -> None:
        """Initialize the job status store with Redis connection.

        Why this exists:
        - Redis provides durable storage for job status.
        """
        self.redis = redis

    async def store_job_result(self, job_id: str, result: dict[str, Any]) -> None:
        """Store the result of a completed job.

        Why this exists:
        - Persists job outcome for status queries.
        """
        status_key = f"job_status:{job_id}"
        await self.redis.setex(
            status_key,
            86400,  # Keep for 24 hours
            json.dumps({
                "job_id": job_id,
                "status": result.get("status"),
                "repo_id": result.get("repo_id"),
                "run_id": result.get("run_id"),
                "head_commit": result.get("head_commit"),
                "error": result.get("error"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }),
        )

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get the status of a job.

        Why this exists:
        - Allows operators and the API to check job progress.
        
        Returns:
            Job status information or None if not found.
        """
        status_key = f"job_status:{job_id}"
        data = await self.redis.get(status_key)
        if not data:
            return None
        
        return json.loads(data)

    async def get_job_status_by_repo(self, repo_id: str) -> list[dict[str, Any]]:
        """Get recent job statuses for a repository.

        Why this exists:
        - Provides repository-specific job history.
        
        Returns:
            List of job status information.
        """
        # This is a simplified implementation - in production we'd want
        # more efficient querying by repo_id
        pattern = "job_status:*"
        jobs = []
        
        async for key in self.redis.iscan(match=pattern):
            data = await self.redis.get(key)
            if data:
                job_info = json.loads(data)
                if job_info.get("repo_id") == repo_id:
                    jobs.append(job_info)
        
        # Sort by completion time (newest first)
        jobs.sort(key=lambda x: x.get("completed_at", ""), reverse=True)
        return jobs[:10]  # Return last 10 jobs
