"""Git and GitLab service for inspecting local repositories."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

_VALID_REF_RE = re.compile(r"^[A-Za-z0-9._/~^@{}-]+$")
_VALID_SHA_RE = re.compile(r"^[0-9a-fA-F]{4,40}$")
_DEFAULT_BASE_CANDIDATES = ("main", "master", "develop", "origin/main", "origin/master")


class GitRepositoryError(Exception):
    """Raised when the target directory is not a valid Git repository."""


class GitCommandError(Exception):
    """Raised when executing a git subprocess fails unexpectedly."""


_INVALID_REF_STDERR_TOKENS = (
    "unknown revision",
    "bad revision",
    "ambiguous argument",
    "bad object",
)


def _is_invalid_ref_stderr(stderr: str) -> bool:
    lower = stderr.lower()
    return any(token in lower for token in _INVALID_REF_STDERR_TOKENS)


def validate_git_ref(ref: str) -> str:
    """Validate that a git ref is non-empty, does not start with '-', and has safe characters."""
    cleaned = (ref or "").strip()
    if not cleaned:
        raise ValueError("Git reference must not be empty.")
    if cleaned.startswith("-"):
        raise ValueError(f"Invalid git reference (cannot start with '-'): {cleaned}")
    if not _VALID_REF_RE.match(cleaned):
        raise ValueError(f"Invalid git reference characters: {cleaned}")
    return cleaned


def validate_commit_sha(sha: str) -> str:
    """Validate that a commit SHA is a safe hexadecimal string."""
    cleaned = (sha or "").strip()
    if not _VALID_SHA_RE.match(cleaned):
        raise ValueError(f"Invalid commit SHA: {cleaned}")
    return cleaned


class GitService:
    """Executes git commands safely against a local repository."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path).resolve()

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if not self.repo_path.exists() or not self.repo_path.is_dir():
            raise GitRepositoryError(f"Repository path does not exist: {self.repo_path}")
        try:
            return subprocess.run(
                ["git", "-C", str(self.repo_path), *args],
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
        except OSError as exc:
            raise GitCommandError(f"Failed to execute git: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitCommandError(f"Git command timed out: {exc}") from exc

    def _ensure_git_repo(self) -> Path:
        proc = self._run_git(["rev-parse", "--show-toplevel"])
        if proc.returncode != 0:
            detail = proc.stderr.strip() or "Not a git repository"
            raise GitRepositoryError(f"{detail}: {self.repo_path}")
        return Path(proc.stdout.strip())

    def get_repo_info(self) -> dict[str, Any]:
        """Return repository name, current branch, default base candidate, and branch list."""
        toplevel = self._ensure_git_repo()

        branch_proc = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if branch_proc.returncode == 0 and branch_proc.stdout.strip():
            current_branch = branch_proc.stdout.strip()
        else:
            sym_proc = self._run_git(["symbolic-ref", "--short", "HEAD"])
            current_branch = sym_proc.stdout.strip() if sym_proc.returncode == 0 else "HEAD"

        branches_proc = self._run_git(["branch", "-a", "--format=%(refname:short)"])
        branches: list[str] = []
        seen: set[str] = set()
        if branches_proc.returncode == 0:
            for line in branches_proc.stdout.splitlines():
                name = line.strip()
                if not name or name.endswith("/HEAD") or " -> " in name:
                    continue
                if name not in seen:
                    seen.add(name)
                    branches.append(name)

        default_base = next(
            (candidate for candidate in _DEFAULT_BASE_CANDIDATES if candidate in seen),
            branches[0] if branches else "main",
        )

        return {
            "repo_name": toplevel.name,
            "repo_path": str(toplevel),
            "current_branch": current_branch,
            "default_base": default_base,
            "branches": branches,
        }
