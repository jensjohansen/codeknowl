"""File: backend/src/codeknowl/asgi.py
Purpose: Expose the ASGI `app` for servers like Uvicorn.
Product/business importance: Provides a stable backend runtime entrypoint for IDE integrations and on-prem deployments.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import asyncio

from codeknowl.app import create_app


def sync_app():
    """Create an app instance synchronously for ASGI servers.

    Why this exists:
    - ASGI servers expect a synchronous app object.
    """
    loop = asyncio.new_event_loop()
    app = loop.run_until_complete(create_app())
    loop.close()
    return app


app = sync_app()
