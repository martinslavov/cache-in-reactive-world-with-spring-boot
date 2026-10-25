import datetime as dt
import json
import pathlib
import unittest

from scripts.agent_dashboard import parse_comments, render_dashboard, validate_record


FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class AgentDashboardTests(unittest.TestCase):
    def test_parses_valid_records_and_deduplicates_exact_replays(self):
        comments = load_fixture("valid_comments.json")
        records = parse_comments(comments + [comments[0]])

        self.assertEqual(["product-owner-agent", "senior-qa-engineer"], [record.agent for record in records])
        self.assertEqual(("unit-tests",), records[1].checks_failed)
        self.assertEqual(1, records[1].retries)

    def test_warns_and_skips_malformed_records(self):
        warnings = []
        records = parse_comments(load_fixture("malformed_comments.json"), warnings.append)

        self.assertEqual([], records)
        self.assertEqual(2, len(warnings))
        self.assertTrue(all("skipped malformed" in warning for warning in warnings))

    def test_missing_records_are_silently_ignored(self):
        warnings = []
        records = parse_comments(load_fixture("missing_comments.json"), warnings.append)

        self.assertEqual([], records)
        self.assertEqual([], warnings)

    def test_rejects_inconsistent_duration_and_failure_without_source(self):
        valid = {
            "v": 1, "agent": "qa", "issue": 2, "pr": 3, "sha": "abc",
            "start": "2026-10-25T20:00:00Z", "end": "2026-10-25T20:01:00Z",
            "duration_s": 10, "checks_failed": [], "retries": 0,
            "status": "failure", "failure_source": None,
        }
        with self.assertRaisesRegex(ValueError, "duration_s"):
            validate_record(valid)
        valid["duration_s"] = 60
        with self.assertRaisesRegex(ValueError, "failure_source is required"):
            validate_record(valid)

    def test_renders_task_agent_failure_and_timestamp_aggregates(self):
        records = parse_comments(load_fixture("valid_comments.json"))
        comments = {
            63: [{"body": "<!-- qa-round:1 -->"}],
            64: [{"body": "<!-- qa-round:1 -->\n<!-- ci-fix-attempt:1 -->"}],
        }
        markdown = render_dashboard(records, comments, dt.datetime(2026, 10, 25, 21, tzinfo=dt.timezone.utc))

        self.assertIn("<!-- agent-dashboard -->", markdown)
        self.assertIn("Last updated: 2026-10-25T21:00:00Z", markdown)
        self.assertIn("| #63 | #64 |", markdown)
        self.assertIn("product-owner-agent (1), senior-qa-engineer (1)", markdown)
        self.assertIn("420s | 1 | 1 | 1 | failure", markdown)
        self.assertIn("| senior-qa-engineer | 1 | 0.0% | 330.0s | 330.0s | 1 |", markdown)
        self.assertIn("| tests | 1 | 100.0% |", markdown)
        self.assertIn("| infrastructure | 0 | 0.0% |", markdown)

    def test_renders_empty_dashboard_without_records(self):
        markdown = render_dashboard([], {}, dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc))

        self.assertIn("| — | — | — | 0s | 0 | 0 | 0 | no records |", markdown)
        self.assertIn("| **Total classified failures** | 0 | 0.0% |", markdown)

    def test_every_agent_documents_run_record_posting(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        agent_names = {
            "product-owner-agent", "architect-agent", "senior-java-software-engineer",
            "pr-review-agent", "senior-qa-engineer", "dod-validator-agent",
        }
        files = {path.stem.removesuffix(".agent"): path for path in (root / ".github/agents").glob("*.agent.md")}
        self.assertEqual(agent_names, set(files))
        for name, path in files.items():
            with self.subTest(agent=name):
                content = path.read_text(encoding="utf-8")
                self.assertIn("agent-run:", content)
                self.assertIn("date -u +%Y-%m-%dT%H:%M:%SZ", content)
                self.assertIn("gh issue comment", content)

    def test_dashboard_and_board_workflows_have_expected_guards_and_permissions(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        dashboard = (root / ".github/workflows/ci-agent-dashboard.yml").read_text(encoding="utf-8")
        board = (root / ".github/workflows/ci-issue-board.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", dashboard)
        self.assertIn("types: [closed]", dashboard)
        self.assertIn("workflow_dispatch:", dashboard)
        self.assertIn("schedule:", dashboard)
        self.assertIn("contents: read", dashboard)
        self.assertIn("pull-requests: read", dashboard)
        self.assertIn("issues: write", dashboard)
        self.assertIn("concurrency:", dashboard)
        self.assertIn("agent-dashboard", board)


if __name__ == "__main__":
    unittest.main()
