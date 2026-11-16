"""Unit tests for viewer_backend.git_service."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from viewer_backend.git_service import (
    GitRepositoryError,
    GitService,
    validate_commit_sha,
    validate_git_ref,
)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        shell=False,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.stdout.strip()


def create_test_repo(root: Path) -> Path:
    """Create a temporary Git repository with main and feature branches."""
    repo = root / "sample-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")

    (repo / "README.md").write_text("# Sample\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "chore: initial commit")

    _git(repo, "checkout", "-b", "feat/demo")
    (repo / "app.py").write_text("print('hello')\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    _git(
        repo,
        "commit",
        "-m",
        "feat(app): add hello script",
        "-m",
        "Why: 動作確認のため\nWhat: app.py を追加\n\nIssue: #1\nTask: 1.1 [S01-01-01]\nVerification: python3 app.py\nExecuted-Command: manual",
    )
    return repo


class GitServiceValidationAndRepoInfoTests(unittest.TestCase):
    def test_validate_git_ref_rejects_flag_injection_and_invalid_chars(self) -> None:
        self.assertEqual(validate_git_ref("feat/issue-1"), "feat/issue-1")
        self.assertEqual(validate_git_ref("origin/main~1"), "origin/main~1")
        with self.assertRaises(ValueError):
            validate_git_ref("")
        with self.assertRaises(ValueError):
            validate_git_ref("--exec=evil")
        with self.assertRaises(ValueError):
            validate_git_ref("main;rm -rf /")

    def test_validate_commit_sha_accepts_hex_only(self) -> None:
        self.assertEqual(validate_commit_sha("abc1234"), "abc1234")
        with self.assertRaises(ValueError):
            validate_commit_sha("--patch")
        with self.assertRaises(ValueError):
            validate_commit_sha("xyz")

    def test_get_repo_info_returns_metadata_and_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = create_test_repo(Path(tmp))
            service = GitService(repo)
            info = service.get_repo_info()
            self.assertEqual(info["repo_name"], "sample-repo")
            self.assertEqual(info["current_branch"], "feat/demo")
            self.assertEqual(info["default_base"], "main")
            self.assertIn("main", info["branches"])
            self.assertIn("feat/demo", info["branches"])

    def test_get_repo_info_raises_for_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            non_repo = Path(tmp) / "plain"
            non_repo.mkdir()
            service = GitService(non_repo)
            with self.assertRaises(GitRepositoryError):
                service.get_repo_info()

            missing = Path(tmp) / "does-not-exist"
            with self.assertRaises(GitRepositoryError):
                GitService(missing).get_repo_info()


class _FakeHttpResponse:
    def __init__(self, body: str) -> None:
        self._bytes = body.encode("utf-8")

    def read(self) -> bytes:
        return self._bytes

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class GitServiceCommitsDiffAndMrTests(unittest.TestCase):
    def test_get_commits_returns_chronological_commits_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = create_test_repo(Path(tmp))
            (repo / "fmt.py").write_text("x = 1\n", encoding="utf-8")
            _git(repo, "add", "fmt.py")
            _git(
                repo,
                "commit",
                "-m",
                "style: format code",
                "-m",
                "Why: フォーマット統一\nWhat: fmt.py整形\n\nTask: 2.1 [S01-02-01]\nExecuted-Command: ruff format .",
            )

            service = GitService(repo)
            commits = service.get_commits(base="main", head="feat/demo")
            self.assertEqual(len(commits), 2)
            self.assertEqual(commits[0]["subject"], "feat(app): add hello script")
            self.assertEqual(commits[0]["change_type"], "manual")
            self.assertEqual(commits[0]["task_ids"], ["S01-01-01"])
            self.assertEqual(commits[1]["subject"], "style: format code")
            self.assertEqual(commits[1]["change_type"], "command")
            self.assertEqual(commits[1]["trailers"]["executed_command"], "ruff format .")

    def test_get_commit_diff_and_ignore_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = create_test_repo(Path(tmp))
            (repo / "app.py").write_text("print('hello')   \n", encoding="utf-8")
            _git(repo, "add", "app.py")
            _git(repo, "commit", "-m", "style: trailing spaces")

            service = GitService(repo)
            commits = service.get_commits(base="main", head="feat/demo")
            ws_sha = commits[-1]["sha"]

            normal_diff = service.get_commit_diff(ws_sha, ignore_whitespace=False)
            self.assertEqual(normal_diff["files"][0]["path"], "app.py")
            self.assertEqual(normal_diff["files"][0]["status"], "M")
            self.assertIn("print('hello')   ", normal_diff["diff"])

            ws_diff = service.get_commit_diff(ws_sha, ignore_whitespace=True)
            self.assertTrue(ws_diff["ignore_whitespace"])
            self.assertNotIn("+print('hello')   ", ws_diff["diff"])

    def test_list_mrs_uses_origin_remote_and_falls_back_when_unset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = create_test_repo(Path(tmp))
            service = GitService(repo)

            fallback_res = service.list_mrs(env={})
            self.assertTrue(fallback_res["fallback"])
            self.assertEqual(fallback_res["default_base"], "main")
            self.assertEqual(fallback_res["default_head"], "feat/demo")

            _git(repo, "remote", "add", "origin", "git@gitlab.com:team/sample-repo.git")
            mr_payload = [
                {
                    "iid": 5,
                    "title": "Demo MR",
                    "source_branch": "feat/demo",
                    "target_branch": "main",
                    "web_url": "https://gitlab.com/team/sample-repo/-/merge_requests/5",
                }
            ]
            ok_res = service.list_mrs(
                env={},
                opener=lambda req, timeout=5.0: _FakeHttpResponse(json.dumps(mr_payload)),
            )
            self.assertFalse(ok_res["fallback"])
            self.assertEqual(ok_res["mrs"][0]["iid"], 5)


if __name__ == "__main__":
    unittest.main()
