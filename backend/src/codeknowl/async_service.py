"""
File: backend/src/codeknowl/async_service.py
Purpose: Async service layer that enqueues jobs instead of running them synchronously.
Product/business importance: Provides durable, retryable indexing and update operations.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import logging
from pathlib import Path

from codeknowl.queue import JobQueue, create_queue
from codeknowl.service import CodeKnowlService

logger = logging.getLogger(__name__)


class AsyncCodeKnowlService:
    """Async wrapper for CodeKnowl service that uses job queues.

    Why this exists:
    - Provides durable, retryable operations by enqueueing jobs instead of running them synchronously.
    """

    def __init__(self, data_dir: Path, queue: JobQueue) -> None:
        """Initialize the async service with data directory and job queue.

        Why this exists:
        - The service needs access to both the data directory and the job queue.
        """
        self.data_dir = data_dir
        self.queue = queue
        self._sync_service = CodeKnowlService(data_dir=data_dir)

    async def enqueue_index_job(self, repo_id: str) -> str:
        """Enqueue an indexing job for a repository.

        Why this exists:
        - Triggers async indexing with retries and durable state.
        
        Returns:
            The job ID.
        """
        # Verify repo exists before enqueuing
        self._sync_service.get_repo(repo_id)
        
        job_id = await self.queue.enqueue_index_job(repo_id)
        logger.info("Enqueued index job %s for repo %s", job_id, repo_id)
        return job_id

    async def enqueue_update_job(self, repo_id: str) -> str:
        """Enqueue an update job for a repository.

        Why this exists:
        - Triggers async incremental updates with retries and durable state.
        
        Returns:
            The job ID.
        """
        # Verify repo exists before enqueuing
        self._sync_service.get_repo(repo_id)
        
        job_id = await self.queue.enqueue_update_job(repo_id)
        logger.info("Enqueued update job %s for repo %s", job_id, repo_id)
        return job_id

    # Delegate read-only operations to sync service
    def list_repos(self):
        """List all registered repositories.

        Why this exists:
        - The IDE needs to show available repositories.
        """
        return self._sync_service.list_repos()

    def get_repo(self, repo_id: str):
        """Get a repository by ID.

        Why this exists:
        - Needed for validation and metadata access.
        """
        return self._sync_service.get_repo(repo_id)

    def register_repo_local_path(
        self,
        local_path: Path,
        *,
        accepted_branch: str,
        preferred_remote: str | None = None,
    ):
        """Register a repository by local path.

        Why this exists:
        - The IDE needs to register new repositories for indexing.
        """
        return self._sync_service.register_repo_local_path(
            local_path,
            accepted_branch=accepted_branch,
            preferred_remote=preferred_remote,
        )

    def delete_repo(self, repo_id: str) -> None:
        """Delete a repository and all its data.

        Why this exists:
        - Operators need to offboard repositories.
        """
        return self._sync_service.delete_repo(repo_id)

    def repo_status(self, repo_id: str):
        """Get the status of a repository.

        Why this exists:
        - The IDE needs to display indexing status.
        """
        return self._sync_service.repo_status(repo_id)

    # QA operations remain synchronous for now
    def qa_where_is_symbol_defined(self, repo_id: str, name: str):
        """Find where a symbol is defined.

        Why this exists:
        - The IDE needs deterministic symbol definition answers.
        """
        return self._sync_service.qa_where_is_symbol_defined(repo_id, name)

    def qa_what_calls_symbol_best_effort(self, repo_id: str, callee: str):
        """Find what calls a symbol (best effort).

        Why this exists:
        - The IDE needs to find all callers of a symbol.
        """
        return self._sync_service.qa_what_calls_symbol_best_effort(repo_id, callee)

    def qa_explain_file_stub(self, repo_id: str, path: str):
        """Provide a deterministic file summary without using an LLM.

        Why this exists:
        - The IDE needs a file summary without LLM latency.
        """
        return self._sync_service.qa_explain_file_stub(repo_id, path)

    def qa_find_occurrences(self, repo_id: str, needle: str, max_results: int = 200):
        """Find all occurrences of a string in a repo.

        Why this exists:
        - The IDE needs to locate all occurrences of a string.
        """
        return self._sync_service.qa_find_occurrences(repo_id, needle, max_results)

    async def qa_ask_llm(self, repo_id: str, question: str):
        """Ask a question with LLM-backed answers.

        Why this exists:
        - The IDE needs natural language Q&A with LLM-generated answers.
        """
        # This remains synchronous for now but could be made async later
        return self._sync_service.qa_ask_llm(repo_id, question)


async def create_async_service(data_dir: Path) -> AsyncCodeKnowlService:
    """Create an async CodeKnowl service with job queue.

    Why this exists:
    - Provides the async service instance for the web app.
    """
    queue = await create_queue()
    return AsyncCodeKnowlService(data_dir=data_dir, queue=queue)
