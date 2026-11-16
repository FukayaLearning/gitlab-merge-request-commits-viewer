"""Integration tests for server.py HTTP/API endpoints."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from server import create_server, parse_args
from tests.test_git_service import create_test_repo


class ServerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.repo = create_test_repo(self.tmp_path)
        self.static_dir = self.tmp_path / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")

        self.server = create_server(
            repo_path=self.repo,
            port=0,
            host="127.0.0.1",
            static_dir=self.static_dir,
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self._tmp.cleanup()

    def _get_json(self, path: str) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        with urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_repo_info_mrs_commits_and_diff_endpoints(self) -> None:
        status, info = self._get_json("/api/repo-info")
        self.assertEqual(status, 200)
        self.assertEqual(info["repo_name"], "sample-repo")
        self.assertEqual(info["default_base"], "main")

        status, mrs = self._get_json("/api/mrs")
        self.assertEqual(status, 200)
        self.assertTrue(mrs["fallback"])
        self.assertEqual(mrs["mrs"], [])

        status, commits_data = self._get_json("/api/commits?base=main&head=feat/demo")
        self.assertEqual(status, 200)
        self.assertEqual(len(commits_data["commits"]), 1)
        sha = commits_data["commits"][0]["sha"]

        status, diff_data = self._get_json(f"/api/commits/{sha}/diff?ignore_whitespace=true")
        self.assertEqual(status, 200)
        self.assertTrue(diff_data["ignore_whitespace"])
        self.assertEqual(diff_data["files"][0]["path"], "app.py")

    def test_invalid_ref_returns_400_and_unknown_endpoint_returns_404(self) -> None:
        with self.assertRaises(HTTPError) as ctx400:
            urlopen(f"http://127.0.0.1:{self.port}/api/commits?base=--evil&head=HEAD", timeout=5)
        self.assertEqual(ctx400.exception.code, 400)

        with self.assertRaises(HTTPError) as ctx404:
            urlopen(f"http://127.0.0.1:{self.port}/api/unknown", timeout=5)
        self.assertEqual(ctx404.exception.code, 404)

    def test_parse_args_uses_env_fallbacks_and_cli_overrides(self) -> None:
        with patch.dict(os.environ, {"REPO_PATH": "/tmp/r", "PORT": "9001", "HOST": "0.0.0.0"}):
            args = parse_args([])
            self.assertEqual(args.repo, "/tmp/r")
            self.assertEqual(args.port, 9001)
            self.assertEqual(args.host, "0.0.0.0")

            overridden = parse_args(["--port", "8765"])
            self.assertEqual(overridden.port, 8765)


if __name__ == "__main__":
    unittest.main()
