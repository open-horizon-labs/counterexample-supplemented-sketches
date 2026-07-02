from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from generated.parse_task_line import TaskRecord, parse_task_line
from known_code.result import Err, Ok


class ParseTaskLineTests(unittest.TestCase):
    def assert_ok_record(
        self,
        line: str,
        *,
        status: str,
        title: str,
        reason: str | None = None,
    ) -> None:
        result = parse_task_line(line)

        self.assertIsInstance(result, Ok)
        self.assertTrue(result.ok)
        self.assertEqual(
            TaskRecord(status=status, title=title, reason=reason),
            result.value,
        )

    def assert_err_code(self, line: object, expected_code: str) -> None:
        result = parse_task_line(line)  # type: ignore[arg-type]

        self.assertIsInstance(result, Err)
        self.assertFalse(result.ok)
        self.assertEqual(expected_code, result.error.code)

    def test_supported_statuses_parse_expected_records(self) -> None:
        cases = [
            ("todo: write parser tests", "todo", "write parser tests", None),
            ("done: ship first slice", "done", "ship first slice", None),
            (
                "blocked: deploy app | waiting on credentials",
                "blocked",
                "deploy app",
                "waiting on credentials",
            ),
        ]

        for line, status, title, reason in cases:
            with self.subTest(line=line):
                self.assert_ok_record(
                    line,
                    status=status,
                    title=title,
                    reason=reason,
                )

    def test_only_first_colon_separates_status_from_title(self) -> None:
        self.assert_ok_record(
            "done: blocked: deploy app",
            status="done",
            title="blocked: deploy app",
        )

    def test_pipe_is_title_text_for_unblocked_statuses(self) -> None:
        cases = [
            ("done: deploy app | checked by Sam", "done"),
            ("todo: deploy app | after code review", "todo"),
        ]

        for line, status in cases:
            with self.subTest(line=line):
                self.assert_ok_record(
                    line,
                    status=status,
                    title=line.split(":", 1)[1].strip(),
                )

    def test_blocked_tasks_require_non_empty_reason_after_pipe(self) -> None:
        cases = [
            ("blocked: deploy app", "missing_reason"),
            ("blocked: deploy app | ", "empty_reason"),
        ]

        for line, expected_code in cases:
            with self.subTest(line=line):
                self.assert_err_code(line, expected_code)

    def test_rejects_missing_empty_or_unknown_status_prefix(self) -> None:
        cases = [
            ("deploy app", "missing_status"),
            ("later: deploy app", "unknown_status"),
            (": deploy app", "unknown_status"),
        ]

        for line, expected_code in cases:
            with self.subTest(line=line):
                self.assert_err_code(line, expected_code)

    def test_rejects_empty_titles_before_accepting_status_specific_syntax(self) -> None:
        cases = [
            ("todo:   ", "empty_title"),
            ("done:   ", "empty_title"),
            ("blocked: | waiting on credentials", "empty_title"),
        ]

        for line, expected_code in cases:
            with self.subTest(line=line):
                self.assert_err_code(line, expected_code)

    def test_rejects_non_string_input_as_invalid_type(self) -> None:
        self.assert_err_code(None, "invalid_type")


if __name__ == "__main__":
    unittest.main()
