"""
File: backend/src/codeknowl/worker.py
Purpose: CLI entrypoint for running the Arq worker.
Product/business importance: Provides durable, retryable indexing and update operations.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from codeknowl.jobs import create_worker


@click.command()
@click.option(
    "--data-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Directory where CodeKnowl data is stored",
)
def main(data_dir: Path) -> None:
    """Run the CodeKnowl worker process.

    Why this exists:
    - Executes async indexing and update jobs from the Redis queue.
    """
    worker = create_worker(data_dir)
    
    # Run the worker
    asyncio.run(worker.async_run())


if __name__ == "__main__":
    main()
