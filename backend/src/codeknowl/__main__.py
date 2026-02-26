"""File: backend/src/codeknowl/__main__.py
Purpose: Provide `python -m codeknowl` entrypoint that forwards to the CLI.
Product/business importance: Enables simple local-first invocation for developer/operator workflows.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

from codeknowl.cli import main

if __name__ == "__main__":
    main()
