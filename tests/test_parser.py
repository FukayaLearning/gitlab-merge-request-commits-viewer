"""Unit tests for viewer_backend.parser."""

from __future__ import annotations

import unittest

from viewer_backend.parser import (
    classify_change_type,
    extract_task_ids,
    extract_trailers,
    parse_commit_metadata,
)


class ParserTests(unittest.TestCase):
    def test_extract_trailers_case_insensitive_and_empty_values(self) -> None:
        body = (
            "why: 構造化メタデータを抽出するため\n"
            "WHAT: parser.py を実装\n"
            "Issue: #1\n"
            "Task: 1.1 [S01-02-02, S01-02-03]\n"
            "Verification: python3 -m unittest tests/test_parser.py -v\n"
            "Executed-Command:   \n"
        )
        trailers = extract_trailers(body)
        self.assertEqual(trailers["why"], "構造化メタデータを抽出するため")
        self.assertEqual(trailers["what"], "parser.py を実装")
        self.assertEqual(trailers["issue"], "#1")
        self.assertEqual(trailers["task"], "1.1 [S01-02-02, S01-02-03]")
        self.assertEqual(trailers["verification"], "python3 -m unittest tests/test_parser.py -v")
        self.assertIsNone(trailers["executed_command"])

    def test_extract_task_ids_unique_preserving_order(self) -> None:
        subject = "feat(parser): implement S01-02-03 and S04-01"
        body = "Task: 1.1 [S01-02-02, S01-02-03]\nRelated: S04-01 and S02-01"
        trailers = extract_trailers(body)
        task_ids = extract_task_ids(subject, body, trailers)
        self.assertEqual(task_ids, ["S01-02-02", "S01-02-03", "S04-01", "S02-01"])

    def test_classify_change_type_command_test_and_manual(self) -> None:
        self.assertEqual(
            classify_change_type(
                "chore(lint): run ruff",
                "",
                {"executed_command": "ruff check --fix ."},
            ),
            "command",
        )
        self.assertEqual(
            classify_change_type(
                "test(parser): add unit tests",
                "",
                {"executed_command": "manual"},
            ),
            "test",
        )
        self.assertEqual(
            classify_change_type(
                "chore: add test files",
                "",
                {"executed_command": "manual"},
                files=["tests/test_parser.py", "src/foo.test.js"],
            ),
            "test",
        )
        self.assertEqual(
            classify_change_type(
                "feat(parser): add parser",
                "",
                {"executed_command": "manual"},
                files=["viewer_backend/parser.py"],
            ),
            "manual",
        )

    def test_parse_commit_metadata_combines_fields(self) -> None:
        result = parse_commit_metadata(
            subject="feat(parser): add metadata parser",
            body=(
                "Why: Parse trailers\n"
                "What: Add parser module\n"
                "Task: 1.1 [S01-02-02]\n"
                "Executed-Command: manual\n"
            ),
        )
        self.assertEqual(result["change_type"], "manual")
        self.assertEqual(result["task_ids"], ["S01-02-02"])
        self.assertEqual(result["trailers"]["why"], "Parse trailers")


if __name__ == "__main__":
    unittest.main()
