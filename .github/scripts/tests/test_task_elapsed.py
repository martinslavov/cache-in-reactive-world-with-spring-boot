import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import task_elapsed
from task_elapsed import BLOCK_BEGIN, BLOCK_END, COMMENT_MARKER, parse_args, summary, upsert_block


class SummaryTest(unittest.TestCase):
    def test_summary_formats_minutes_seconds_and_utc(self):
        text = summary(118, 123, 0, 125)
        self.assertIn("**Task elapsed time:** 2 min 5 s (125 s)", text)
        self.assertIn("| 1970-01-01T00:00:00Z | 1970-01-01T00:02:05Z | #118 | #123 |", text)


class UpsertBlockTest(unittest.TestCase):
    def test_inserts_block_at_top_and_keeps_body(self):
        result = upsert_block("### Type\nBug\n", summary(1, 2, 0, 60))
        self.assertTrue(result.startswith(BLOCK_BEGIN))
        self.assertIn("> **Task elapsed time:** 1 min 0 s (60 s)", result)
        self.assertTrue(result.endswith(f"{BLOCK_END}\n\n### Type\nBug\n"))

    def test_rerun_replaces_existing_block(self):
        first = upsert_block("Body text", summary(1, 2, 0, 60))
        second = upsert_block(first, summary(1, 2, 0, 120))
        self.assertEqual(second.count(BLOCK_BEGIN), 1)
        self.assertIn("2 min 0 s", second)
        self.assertNotIn("1 min 0 s", second)
        self.assertTrue(second.endswith(f"{BLOCK_END}\n\nBody text\n"))

    def test_rerun_is_idempotent(self):
        once = upsert_block("Body", summary(1, 2, 0, 60))
        self.assertEqual(upsert_block(once, summary(1, 2, 0, 60)), once)

    def test_empty_or_missing_body(self):
        for body in (None, ""):
            result = upsert_block(body, summary(1, 2, 0, 1))
            self.assertTrue(result.startswith(BLOCK_BEGIN))
            self.assertTrue(result.endswith(f"{BLOCK_END}\n"))


class ParseArgsTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_args(["5", "6", "10", "20"]), (5, 6, 10, 20))

    def test_invalid(self):
        for argv in (["5", "6"], ["0", "6", "1"], ["5", "x", "1"], ["5", "6", "-1"], ["5", "6", "20", "10"]):
            with self.assertRaises(ValueError):
                parse_args(argv)

    def test_main_returns_2_on_bad_args(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(task_elapsed.main(["1"]), 2)


class MainTest(unittest.TestCase):
    def test_updates_descriptions_and_upserts_comments(self):
        calls, patched = [], {}

        def fake_gh(*args):
            calls.append(args)
            path = args[1] if args[0] == "api" and not args[1].startswith("-") else args[3]
            if args[:2] == ("api", "repos/o/r/pulls/2"):
                return json.dumps({"body": "PR body"})
            if args[:2] == ("api", "repos/o/r/issues/1"):
                return json.dumps({"body": None})
            if path.endswith("/1/comments") and "--paginate" in args:
                return "77\n"
            if path.endswith("/2/comments") and "--paginate" in args:
                return ""
            return "url\n"

        def fake_patch(path, body):
            patched[path] = body

        with patch.dict("os.environ", {"RCAS_REPO": "o/r"}), \
                patch.object(task_elapsed, "gh", side_effect=fake_gh), \
                patch.object(task_elapsed, "patch_body", side_effect=fake_patch), \
                redirect_stderr(io.StringIO()), patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(task_elapsed.main(["1", "2", "0", "90"]), 0)

        self.assertTrue(patched["repos/o/r/issues/1"].startswith(BLOCK_BEGIN))
        self.assertTrue(patched["repos/o/r/pulls/2"].endswith("PR body\n"))
        writes = [c for c in calls if "-X" in c]
        self.assertIn(("api", "-X", "PATCH", "repos/o/r/issues/comments/77"), [c[:4] for c in writes])
        self.assertIn(("api", "-X", "POST", "repos/o/r/issues/2/comments"), [c[:4] for c in writes])
        self.assertTrue(all(f"body={COMMENT_MARKER}" in " ".join(c) for c in writes))


if __name__ == "__main__":
    unittest.main()
