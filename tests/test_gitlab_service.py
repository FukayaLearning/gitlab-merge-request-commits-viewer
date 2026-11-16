"""Unit tests for viewer_backend.gitlab_service."""

from __future__ import annotations

import io
import json
import unittest
from urllib.error import HTTPError, URLError

from viewer_backend.gitlab_service import (
    fetch_open_merge_requests,
    get_gitlab_token,
    parse_gitlab_remote_url,
    resolve_gitlab_target,
)


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._bytes = body.encode("utf-8")

    def read(self) -> bytes:
        return self._bytes

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class GitLabUrlResolutionTests(unittest.TestCase):
    def test_parse_https_and_subgroup_urls(self) -> None:
        self.assertEqual(
            parse_gitlab_remote_url("https://gitlab.com/org/repo.git"),
            ("https://gitlab.com", "org/repo"),
        )
        self.assertEqual(
            parse_gitlab_remote_url("https://gitlab.example.com:8443/group/subgroup/repo.git"),
            ("https://gitlab.example.com:8443", "group/subgroup/repo"),
        )
        self.assertEqual(
            parse_gitlab_remote_url("https://oauth2:secret@gitlab.example.com/group/repo"),
            ("https://gitlab.example.com", "group/repo"),
        )

    def test_parse_ssh_urls(self) -> None:
        self.assertEqual(
            parse_gitlab_remote_url("git@gitlab.com:group/subgroup/repo.git"),
            ("https://gitlab.com", "group/subgroup/repo"),
        )
        self.assertEqual(
            parse_gitlab_remote_url("ssh://git@gitlab.example.com:2222/team/service.git"),
            ("https://gitlab.example.com", "team/service"),
        )

    def test_parse_invalid_urls_return_none(self) -> None:
        self.assertIsNone(parse_gitlab_remote_url(""))
        self.assertIsNone(parse_gitlab_remote_url(None))
        self.assertIsNone(parse_gitlab_remote_url("/local/path/repo.git"))
        self.assertIsNone(parse_gitlab_remote_url("https://gitlab.com/single-segment"))

    def test_resolve_gitlab_target_prefers_env_overrides(self) -> None:
        resolved = resolve_gitlab_target(
            "git@gitlab.com:org/repo.git",
            env={
                "GITLAB_URL": "https://gitlab.internal.local/",
                "GITLAB_PROJECT_ID": "42",
            },
        )
        self.assertEqual(resolved, ("https://gitlab.internal.local", "42"))

        resolved_partial = resolve_gitlab_target(
            "git@gitlab.com:org/sub/repo.git",
            env={"GITLAB_URL": "https://git.corp.local"},
        )
        self.assertEqual(resolved_partial, ("https://git.corp.local", "org/sub/repo"))

        self.assertIsNone(resolve_gitlab_target(None, env={}))


class GitLabApiFetchTests(unittest.TestCase):
    def test_get_gitlab_token_priority(self) -> None:
        self.assertEqual(
            get_gitlab_token({"GITLAB_TOKEN": "tok-primary", "GITLAB_PRIVATE_TOKEN": "tok-alt"}),
            "tok-primary",
        )
        self.assertEqual(
            get_gitlab_token({"GITLAB_PRIVATE_TOKEN": "tok-alt"}),
            "tok-alt",
        )
        self.assertIsNone(get_gitlab_token({}))

    def test_fetch_open_merge_requests_success_with_token_and_encoding(self) -> None:
        captured: dict[str, object] = {}

        def fake_opener(req, timeout=5.0):
            captured["url"] = req.full_url
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}
            captured["timeout"] = timeout
            payload = [
                {
                    "iid": 12,
                    "title": "feat: add viewer",
                    "source_branch": "feat/viewer",
                    "target_branch": "main",
                    "web_url": "https://gitlab.example.com/group/sub/repo/-/merge_requests/12",
                }
            ]
            return _FakeResponse(json.dumps(payload))

        result = fetch_open_merge_requests(
            remote_url="git@gitlab.example.com:group/sub/repo.git",
            default_base="main",
            default_head="HEAD",
            env={"GITLAB_TOKEN": "glpat-secret-123"},
            opener=fake_opener,
        )

        self.assertFalse(result["fallback"])
        self.assertIsNone(result["reason"])
        self.assertEqual(
            captured["url"],
            "https://gitlab.example.com/api/v4/projects/group%2Fsub%2Frepo/merge_requests?state=opened&per_page=50",
        )
        self.assertEqual(captured["headers"]["private-token"], "glpat-secret-123")
        self.assertEqual(len(result["mrs"]), 1)
        self.assertEqual(result["mrs"][0]["iid"], 12)
        self.assertEqual(result["mrs"][0]["source_branch"], "feat/viewer")
        self.assertEqual(result["mrs"][0]["target_branch"], "main")

    def test_fetch_open_merge_requests_auth_failure_does_not_leak_token(self) -> None:
        secret = "glpat-super-secret-value"

        def fake_opener(req, timeout=5.0):
            raise HTTPError(
                url=req.full_url,
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=io.BytesIO(b""),
            )

        result = fetch_open_merge_requests(
            remote_url="https://gitlab.com/org/repo.git",
            default_base="main",
            default_head="feat/x",
            env={"GITLAB_TOKEN": secret},
            opener=fake_opener,
        )

        self.assertTrue(result["fallback"])
        self.assertEqual(result["mrs"], [])
        self.assertIn("401", result["reason"])
        self.assertNotIn(secret, result["reason"])

    def test_fetch_open_merge_requests_network_error_and_empty_list_fallback(self) -> None:
        secret = "glpat-leak-test"

        def failing_opener(req, timeout=5.0):
            raise URLError(f"connection failed with {secret}")

        net_res = fetch_open_merge_requests(
            remote_url="https://gitlab.com/org/repo.git",
            default_base="main",
            default_head="HEAD",
            env={"GITLAB_TOKEN": secret},
            opener=failing_opener,
        )
        self.assertTrue(net_res["fallback"])
        self.assertNotIn(secret, net_res["reason"])

        empty_res = fetch_open_merge_requests(
            remote_url="https://gitlab.com/org/repo.git",
            default_base="main",
            default_head="HEAD",
            env={},
            opener=lambda req, timeout=5.0: _FakeResponse("[]"),
        )
        self.assertTrue(empty_res["fallback"])
        self.assertEqual(empty_res["reason"], "No open merge requests found")


if __name__ == "__main__":
    unittest.main()
