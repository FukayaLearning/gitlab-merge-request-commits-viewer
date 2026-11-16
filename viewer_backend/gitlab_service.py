"""GitLab REST API v4 service for resolving projects and listing open Merge Requests."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

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


def get_gitlab_token(env: Mapping[str, str] | None = None) -> str | None:
    """Return GitLab personal/project access token from environment variables."""
    environ = env if env is not None else os.environ
    for key in ("GITLAB_TOKEN", "GITLAB_PRIVATE_TOKEN"):
        value = (environ.get(key) or "").strip()
        if value:
            return value
    return None


def _sanitize_reason(message: str, token: str | None) -> str:
    if token and token in message:
        return message.replace(token, "[REDACTED]")
    return message


def _fallback_response(
    reason: str,
    default_base: str,
    default_head: str,
    token: str | None = None,
) -> dict[str, Any]:
    return {
        "mrs": [],
        "fallback": True,
        "reason": _sanitize_reason(reason, token),
        "default_base": default_base,
        "default_head": default_head,
    }


def fetch_open_merge_requests(
    remote_url: str | None,
    default_base: str,
    default_head: str,
    env: Mapping[str, str] | None = None,
    opener: Callable[..., Any] | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Fetch open GitLab Merge Requests via REST API v4 with automatic fallback."""
    environ = env if env is not None else os.environ
    token = get_gitlab_token(environ)
    target = resolve_gitlab_target(remote_url, env=environ)
    if target is None:
        return _fallback_response(
            "GitLab remote URL is not configured",
            default_base=default_base,
            default_head=default_head,
            token=token,
        )

    gitlab_url, project_id = target
    encoded_project = quote(project_id, safe="")
    api_url = (
        f"{gitlab_url}/api/v4/projects/{encoded_project}"
        "/merge_requests?state=opened&per_page=50"
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": "gitlab-merge-request-commits-viewer",
    }
    if token:
        headers["PRIVATE-TOKEN"] = token

    request = Request(api_url, headers=headers, method="GET")
    open_fn = opener if opener is not None else urlopen

    try:
        with open_fn(request, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code in (401, 403):
            reason = f"GitLab API authentication failed (HTTP {exc.code})"
        elif exc.code == 404:
            reason = "GitLab project or API endpoint not found (HTTP 404)"
        else:
            reason = f"GitLab API error (HTTP {exc.code})"
        return _fallback_response(reason, default_base, default_head, token=token)
    except (URLError, TimeoutError, OSError) as exc:
        return _fallback_response(
            f"GitLab API unavailable: {exc}",
            default_base,
            default_head,
            token=token,
        )

    try:
        payload = json.loads(raw_body or "[]")
    except json.JSONDecodeError as exc:
        return _fallback_response(
            f"Invalid GitLab API response: {exc}",
            default_base,
            default_head,
            token=token,
        )

    if not isinstance(payload, list) or len(payload) == 0:
        return _fallback_response(
            "No open merge requests found",
            default_base,
            default_head,
            token=token,
        )

    mrs: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        iid = item.get("iid")
        if iid is None:
            continue
        mrs.append(
            {
                "iid": iid,
                "title": str(item.get("title") or ""),
                "source_branch": str(item.get("source_branch") or ""),
                "target_branch": str(item.get("target_branch") or ""),
                "web_url": str(item.get("web_url") or ""),
            }
        )

    if not mrs:
        return _fallback_response(
            "No open merge requests found",
            default_base,
            default_head,
            token=token,
        )

    return {
        "mrs": mrs,
        "fallback": False,
        "reason": None,
        "default_base": default_base,
        "default_head": default_head,
    }
