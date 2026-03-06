"""
File: backend/src/codeknowl/jobs.py
Purpose: Define async job functions for Arq worker queue.
Product/business importance: Provides durable, retryable indexing and update operations.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from arq import Worker

from codeknowl.job_status import JobStatusStore
from codeknowl.service import CodeKnowlService

logger = logging.getLogger(__name__)


async def index_repo_job(
    ctx: dict[str, Any],
    repo_id: str,
) -> dict[str, Any]:
    """Async job to index a repository.

    Why this exists:
    - Provides durable, retryable indexing operations via Arq worker queue.
    """
    data_dir = Path(ctx["data_dir"])
    service = CodeKnowlService(data_dir=data_dir)
    status_store = JobStatusStore(ctx["redis"])
    
    try:
        run = service.start_index_run(repo_id)
        completed = service.run_indexing_sync(run.run_id)
        
        result = {
            "status": completed.status,
            "run_id": completed.run_id,
            "repo_id": completed.repo_id,
            "head_commit": completed.head_commit,
            "error": completed.error,
        }
        
        # Store job result for status queries
        job_id = ctx.get("job_id", f"index-{repo_id}")
        await status_store.store_job_result(job_id, result)
        
        return result
    except Exception:
        logger.exception("Index job failed for repo %s", repo_id)
        raise


async def update_repo_job(
    ctx: dict[str, Any],
    repo_id: str,
) -> dict[str, Any]:
    """Async job to update a repository to accepted head.

    Why this exists:
    - Provides durable, retryable update operations via Arq worker queue.
    """
    data_dir = Path(ctx["data_dir"])
    service = CodeKnowlService(data_dir=data_dir)
    status_store = JobStatusStore(ctx["redis"])
    
    try:
        completed = service.update_repo_to_accepted_head_sync(repo_id)
        
        result = {
            "status": completed.status,
            "run_id": completed.run_id,
            "repo_id": completed.repo_id,
            "head_commit": completed.head_commit,
            "error": completed.error,
        }
        
        # Store job result for status queries
        job_id = ctx.get("job_id", f"update-{repo_id}")
        await status_store.store_job_result(job_id, result)
        
        return result
    except Exception:
        logger.exception("Update job failed for repo %s", repo_id)
        raise


def create_worker(data_dir: Path) -> Worker:
    """Create an Arq worker for CodeKnowl jobs.

    Why this exists:
    - Provides the worker process that executes async indexing/update jobs.
    """
    return Worker(
        functions=[index_repo_job, update_repo_job],
        redis_settings={"host": "localhost", "port": 6379, "database": 0},
        ctx={"data_dir": str(data_dir)},
        burst_mode=False,
        poll_delay=1.0,
        poll_interval=1.0,
    )
