"""
File: backend/src/codeknowl/queue.py
Purpose: Arq queue client for enqueueing async jobs.
Product/business importance: Provides durable job submission with retry capabilities.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from typing import Any

from arq import ArqRedis, create_pool

from codeknowl.job_status import JobStatusStore

logger = logging.getLogger(__name__)


class JobQueue:
    """Arq-based job queue for CodeKnowl.

    Why this exists:
    - Provides durable, retryable job execution for indexing and updates.
    """

    def __init__(self, redis: ArqRedis) -> None:
        """Initialize the job queue with a Redis connection.

        Why this exists:
        - Redis provides the backend storage for Arq jobs.
        """
        self.redis = redis
        self.status_store = JobStatusStore(redis)

    async def enqueue_index_job(self, repo_id: str) -> str:
        """Enqueue an indexing job for a repository.

        Why this exists:
        - Triggers async indexing with retries and durable state.
        
        Returns:
            The job ID.
        """
        job_id = await self.redis.enqueue_job(
            "index_repo_job",
            repo_id,
            _job_id=f"index-{repo_id}",
        )
        if not job_id:
            raise RuntimeError(f"Failed to enqueue index job for repo {repo_id}")
        
        logger.info("Enqueued index job %s for repo %s", job_id, repo_id)
        return job_id

    async def enqueue_update_job(self, repo_id: str) -> str:
        """Enqueue an update job for a repository.

        Why this exists:
        - Triggers async incremental updates with retries and durable state.
        
        Returns:
            The job ID.
        """
        job_id = await self.redis.enqueue_job(
            "update_repo_job",
            repo_id,
            _job_id=f"update-{repo_id}",
        )
        if not job_id:
            raise RuntimeError(f"Failed to enqueue update job for repo {repo_id}")
        
        logger.info("Enqueued update job %s for repo %s", job_id, repo_id)
        return job_id

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get the status of a job.

        Why this exists:
        - Allows operators and the API to check job progress.
        
        Returns:
            Job status information or None if not found.
        """
        return await self.status_store.get_job_status(job_id)

    async def get_job_status_by_repo(self, repo_id: str) -> list[dict[str, Any]]:
        """Get recent job statuses for a repository.

        Why this exists:
        - Provides repository-specific job history.
        
        Returns:
            List of job status information.
        """
        return await self.status_store.get_job_status_by_repo(repo_id)


async def create_queue() -> JobQueue:
    """Create a job queue connected to Redis.

    Why this exists:
    - Provides the queue client for submitting async jobs.
    """
    from arq.connections import RedisSettings
    settings = RedisSettings(host="localhost", port=6379, database=0)
    redis = await create_pool(settings)
    return JobQueue(redis)
