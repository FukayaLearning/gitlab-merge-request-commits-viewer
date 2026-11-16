"""GitLab REST API v4 service for resolving projects and listing open Merge Requests."""

from __future__ import annotations

import os
import re
from typing import Mapping
from urllib.parse import urlparse

_SCP_SSH_RE = re.compile(r"^(?:[^@]+@)?([^:/]+):(.+)$")


def _strip_git_suffix(path: str) -> str:
    cleaned = path.strip().strip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    return cleaned.strip("/")


def parse_gitlab_remote_url(remote_url: str | None) -> tuple[str, str] | None:
    """Extract (base_url, project_path) from an HTTPS or SSH GitLab remote URL."""
    raw = (remote_url or "").strip()
    if not raw:
        return None

    if "://" in raw:
        parsed = urlparse(raw)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        if not hostname:
            return None

        if scheme in {"http", "https"}:
            port_part = f":{parsed.port}" if parsed.port else ""
            base_url = f"{scheme}://{hostname}{port_part}"
        elif scheme == "ssh":
            base_url = f"https://{hostname}"
        else:
            return None

        project_path = _strip_git_suffix(parsed.path)
        if "/" not in project_path:
            return None
        return base_url, project_path

    scp_match = _SCP_SSH_RE.match(raw)
    if not scp_match:
        return None

    host, raw_path = scp_match.group(1).strip(), scp_match.group(2)
    project_path = _strip_git_suffix(raw_path)
    if not host or "/" not in project_path:
        return None
    return f"https://{host}", project_path


def resolve_gitlab_target(
    remote_url: str | None,
    env: Mapping[str, str] | None = None,
) -> tuple[str, str] | None:
    """Resolve (gitlab_url, project_id_or_path) with environment variable overrides."""
    environ = env if env is not None else os.environ
    parsed = parse_gitlab_remote_url(remote_url)

    env_url = (environ.get("GITLAB_URL") or "").strip().rstrip("/")
    env_project = (environ.get("GITLAB_PROJECT_ID") or "").strip().strip("/")

    gitlab_url = env_url or (parsed[0] if parsed else "")
    project_id = env_project or (parsed[1] if parsed else "")

    if not gitlab_url or not project_id:
        return None
    return gitlab_url, project_id
