import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
sys.path.insert(0, str(_SRC))


from codeknowl.auth import AuthContext, GroupAuthzConfig, is_admin, is_allowed_for_repo  # noqa: E402


class TestGroupAuthorization(unittest.TestCase):
    def test_admin_group_allows_all(self) -> None:
        group_config = GroupAuthzConfig(
            group_prefix="/codeknowl/repos",
            read_suffix="read",
            write_suffix="write",
            admin_group="/codeknowl/admin",
        )
        auth_context = AuthContext(subject="s", username="u", groups={"/codeknowl/admin"})

        self.assertTrue(is_admin(group_config=group_config, auth_context=auth_context))
        self.assertTrue(
            is_allowed_for_repo(group_config=group_config, auth_context=auth_context, repo_id="r1", op="read")
        )
        self.assertTrue(
            is_allowed_for_repo(group_config=group_config, auth_context=auth_context, repo_id="r1", op="write")
        )

    def test_repo_group_enforced(self) -> None:
        group_config = GroupAuthzConfig(
            group_prefix="/codeknowl/repos",
            read_suffix="read",
            write_suffix="write",
            admin_group="/codeknowl/admin",
        )

        auth_context = AuthContext(
            subject="s",
            username="u",
            groups={"/codeknowl/repos/abc/read"},
        )

        self.assertTrue(
            is_allowed_for_repo(group_config=group_config, auth_context=auth_context, repo_id="abc", op="read")
        )
        self.assertFalse(
            is_allowed_for_repo(group_config=group_config, auth_context=auth_context, repo_id="abc", op="write")
        )
        self.assertFalse(
            is_allowed_for_repo(group_config=group_config, auth_context=auth_context, repo_id="other", op="read")
        )


if __name__ == "__main__":
    unittest.main()
