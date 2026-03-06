"""File: backend/tests/test_http_authz.py
Purpose: HTTP-level auth/RBAC integration tests exercising middleware + route guards.
Product/business importance: Confirms Milestone 4 access control works end-to-end at the API layer.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
sys.path.insert(0, str(_SRC))

from blacksheep.testing import JSONContent, TestClient  # noqa: E402

from codeknowl.auth import AuthContext  # noqa: E402
from codeknowl.config import AppConfig  # noqa: E402
from codeknowl.service import CodeKnowlService, IndexRunRecord  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestHttpAuthz(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = TemporaryDirectory(prefix="codeknowl-test-authz-")
        self._data_dir = Path(self._tmp.name) / "data"
        self._data_dir.mkdir(parents=True, exist_ok=True)

    async def asyncTearDown(self) -> None:
        self._tmp.cleanup()

    async def test_oidc_auth_and_repo_rbac_enforced(self) -> None:
        current_groups: set[str] = set()

        def fake_verify_bearer_token(_self, _token: str) -> AuthContext:  # noqa: ANN001
            return AuthContext(subject="sub", username="u", groups=set(current_groups))

        def fake_update_repo_to_accepted_head_sync(self, repo_id: str):  # noqa: ANN001
            return IndexRunRecord(
                run_id="run",
                repo_id=repo_id,
                status="succeeded",
                started_at_utc=_utc_now_iso(),
                finished_at_utc=_utc_now_iso(),
                error=None,
                head_commit="deadbeef",
            )

        env = {
            "CODEKNOWL_AUTH_MODE": "oidc",
            "CODEKNOWL_OIDC_ISSUER_URL": "https://example.invalid/issuer",
            "CODEKNOWL_EMBED_MODE": "hash",
            "CODEKNOWL_VECTOR_MODE": "file",
        }

        with (
            patch.dict(os.environ, env, clear=False),
            patch("codeknowl.auth.OidcVerifier.verify_bearer_token", new=fake_verify_bearer_token),
            patch.object(
                CodeKnowlService,
                "update_repo_to_accepted_head_sync",
                new=fake_update_repo_to_accepted_head_sync,
            ),
        ):
            from codeknowl.app import create_app  # noqa: E402

            app = create_app(AppConfig(data_dir=self._data_dir))
            await app.start()
            try:
                client = TestClient(app)

                # No bearer token => 401
                response = await client.get("/repos")
                self.assertEqual(response.status, 401)

                # Admin can register a repo.
                current_groups = {"/codeknowl/admin"}
                repo_path = Path(self._tmp.name) / "repo"
                repo_path.mkdir(parents=True, exist_ok=True)

                response = await client.post(
                    "/repos",
                    headers={"authorization": "Bearer admin"},
                    content=JSONContent(
                        {
                            "local_path": str(repo_path),
                            "accepted_branch": "main",
                            "preferred_remote": None,
                        }
                    ),
                )
                self.assertEqual(response.status, 201)
                payload = json.loads((await response.read() or b"{}").decode("utf-8"))
                repo_id = payload["repo_id"]

                # Non-admin cannot delete.
                current_groups = set()
                response = await client.delete(f"/repos/{repo_id}", headers={"authorization": "Bearer none"})
                self.assertEqual(response.status, 403)

                # Read-only group cannot update.
                current_groups = {f"/codeknowl/repos/{repo_id}/read"}
                response = await client.post(
                    f"/repos/{repo_id}/update",
                    headers={"authorization": "Bearer read"},
                )
                self.assertEqual(response.status, 403)

                # Write group can update.
                current_groups = {f"/codeknowl/repos/{repo_id}/write"}
                response = await client.post(
                    f"/repos/{repo_id}/update",
                    headers={"authorization": "Bearer write"},
                )
                self.assertEqual(response.status, 200)
            finally:
                await app.stop()


if __name__ == "__main__":
    unittest.main()
