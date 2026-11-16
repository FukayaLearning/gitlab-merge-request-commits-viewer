"""Git and GitLab service for inspecting local repositories."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from viewer_backend.gitlab_service import fetch_open_merge_requests
from viewer_backend.parser import parse_commit_metadata

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

    def _get_origin_remote_url(self) -> str | None:
        proc = self._run_git(["remote", "get-url", "origin"])
        if proc.returncode != 0:
            return None
        url = proc.stdout.strip()
        return url or None

    def list_mrs(
        self,
        env: Mapping[str, str] | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Return open GitLab Merge Requests via REST API, falling back to local branches."""
        repo_info = self.get_repo_info()
        default_base = repo_info["default_base"]
        default_head = repo_info["current_branch"] or "HEAD"
        remote_url = self._get_origin_remote_url()
        return fetch_open_merge_requests(
            remote_url=remote_url,
            default_base=default_base,
            default_head=default_head,
            env=env,
            opener=opener,
        )

    def get_commits(self, base: str, head: str = "HEAD") -> list[dict[str, Any]]:
        """Return chronological commits in base..head with parsed Git Trailers."""
        self._ensure_git_repo()
        safe_base = validate_git_ref(base)
        safe_head = validate_git_ref(head)

        proc = self._run_git(
            [
                "log",
                "--reverse",
                "--format=%H%x1f%h%x1f%s%x1f%b%x1f%an%x1f%aI%x1e",
                f"{safe_base}..{safe_head}",
            ]
        )
        if proc.returncode != 0:
            detail = proc.stderr.strip() or f"Failed to list commits for {safe_base}..{safe_head}"
            if _is_invalid_ref_stderr(detail):
                raise ValueError(detail)
            raise GitCommandError(detail)

        commits: list[dict[str, Any]] = []
        for raw_record in proc.stdout.split("\x1e"):
            record = raw_record.strip("\r\n")
            if not record:
                continue
            parts = record.split("\x1f")
            if len(parts) < 6:
                continue
            sha, short_sha, subject, body, author, date = parts[:6]
            metadata = parse_commit_metadata(subject, body)
            commits.append(
                {
                    "sha": sha.strip(),
                    "short_sha": short_sha.strip(),
                    "subject": subject.strip(),
                    "body": body.strip(),
                    "author": author.strip(),
                    "date": date.strip(),
                    "trailers": metadata["trailers"],
                    "task_ids": metadata["task_ids"],
                    "change_type": metadata["change_type"],
                }
            )
        return commits

    def get_commit_diff(self, sha: str, ignore_whitespace: bool = False) -> dict[str, Any]:
        """Return changed file stats and unified diff for a specific commit SHA."""
        self._ensure_git_repo()
        safe_sha = validate_commit_sha(sha)

        status_proc = self._run_git(["show", "--name-status", "--format=", safe_sha])
        if status_proc.returncode != 0:
            detail = status_proc.stderr.strip() or f"Failed to inspect commit {safe_sha}"
            if _is_invalid_ref_stderr(detail):
                raise ValueError(detail)
            raise GitCommandError(detail)

        status_map: dict[str, str] = {}
        for line in status_proc.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                status_code = parts[0].strip()
                file_path = parts[-1].strip()
                status_map[file_path] = status_code

        numstat_proc = self._run_git(["show", "--numstat", "--format=", safe_sha])
        if numstat_proc.returncode != 0:
            detail = numstat_proc.stderr.strip() or f"Failed to get numstat for {safe_sha}"
            raise GitCommandError(detail)

        files: list[dict[str, Any]] = []
        for line in numstat_proc.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            raw_add, raw_del, file_path = parts[0], parts[1], parts[-1]
            is_binary = raw_add == "-" or raw_del == "-"
            additions = 0 if is_binary else int(raw_add)
            deletions = 0 if is_binary else int(raw_del)
            files.append(
                {
                    "path": file_path,
                    "status": status_map.get(file_path, "M"),
                    "additions": additions,
                    "deletions": deletions,
                    "binary": is_binary,
                }
            )

        patch_args = ["show", "--patch", "--format="]
        if ignore_whitespace:
            patch_args.append("-w")
        patch_args.append(safe_sha)

        patch_proc = self._run_git(patch_args)
        if patch_proc.returncode != 0:
            detail = patch_proc.stderr.strip() or f"Failed to get diff for {safe_sha}"
            raise GitCommandError(detail)

        return {
            "sha": safe_sha,
            "ignore_whitespace": ignore_whitespace,
            "files": files,
            "diff": patch_proc.stdout,
        }
