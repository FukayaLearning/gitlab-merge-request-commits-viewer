"""Unit tests for viewer_backend.git_service."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
