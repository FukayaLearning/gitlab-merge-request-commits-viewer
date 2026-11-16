"""Unit tests for viewer_backend.gitlab_service."""

from __future__ import annotations

import unittest

from viewer_backend.gitlab_service import parse_gitlab_remote_url, resolve_gitlab_target


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


if __name__ == "__main__":
    unittest.main()
