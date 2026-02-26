"""File: backend/src/codeknowl/asgi.py
Purpose: Expose the ASGI `app` for servers like Uvicorn.
Product/business importance: Provides a stable backend runtime entrypoint for IDE integrations and on-prem deployments.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

from codeknowl.app import create_app

app = create_app()
