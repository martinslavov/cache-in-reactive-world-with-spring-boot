import datetime as dt
import json
import pathlib
import unittest

from scripts.agent_dashboard import (
    DASHBOARD_MARKER, GitHubClient, find_dashboard, parse_comments, render_dashboard, validate_record,
)


FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def top_level_block(text, key):
    lines = text.splitlines()
    start = lines.index(f"{key}:")
    block = []
    for line in lines[start + 1:]:
        if line and not line.startswith(" "):
            break
        if line.strip():
            block.append(line)
    return block


class FakeClient(GitHubClient):
    def __init__(self, pages=None):
        super().__init__("token")
        self.pages = pages or {}
        self.calls = []

    def request(self, method, url, payload=None):
        self.calls.append((method, url, payload))
        if method == "GET":
            body, link = self.pages[url]
            return body, ({"Link": f'<{link}>; rel="next"'} if link else {})
        if method == "POST" and url.endswith("/issues"):
            return {"number": 7, "html_url": "https://x/7", "url": "https://api/7", "node_id": "N", "state": "open"}, {}
        if method == "PATCH":
            return {"number": 7, "html_url": "https://x/7", "url": url, "node_id": "N", "state": "open"}, {}
        return {"data": {"node": {"isPinned": True}}}, {}


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
        # No YAML parser in the stdlib: check top-level blocks by indentation instead of substrings.
        on_block = top_level_block(dashboard, "on")
        self.assertEqual(["push:", "schedule:", "workflow_dispatch:"],
                         [line.strip() for line in on_block if line.startswith("  ") and not line.startswith("   ")])
        self.assertIn("    branches: [main]", on_block)
        self.assertNotIn("pull_request", dashboard)
        self.assertEqual(["contents: read", "pull-requests: read", "issues: write"],
                         [line.strip() for line in top_level_block(dashboard, "permissions")])
        self.assertTrue(any("cancel-in-progress: false" in line for line in top_level_block(dashboard, "concurrency")))
        self.assertIn("if: github.ref == 'refs/heads/main'", dashboard)
        self.assertIn("agent-dashboard", board)


    def test_get_all_follows_pagination_links(self):
        client = FakeClient({"u1": ([1, 2], "u2"), "u2": ([3], "")})
        self.assertEqual([1, 2, 3], client.get_all("u1"))
        self.assertEqual(["u1", "u2"], [call[1] for call in client.calls])

    def test_publish_creates_when_missing_and_updates_in_place(self):
        client = FakeClient()
        self.assertIn("created", client.publish("o/r", [{"number": 1, "body": "other"}], "body"))
        self.assertEqual("POST", client.calls[0][0])
        client = FakeClient()
        existing = {"number": 7, "url": "https://api/7", "state": "open", "body": DASHBOARD_MARKER + "\nold"}
        self.assertIn("updated", client.publish("o/r", [existing], "new"))
        writes = [call for call in client.calls if call[0] in {"POST", "PATCH"} and "graphql" not in call[1]]
        self.assertEqual([("PATCH", "https://api/7", {"body": "new"})], writes)

    def test_publish_reopens_closed_dashboard(self):
        client = FakeClient()
        closed = {"number": 7, "url": "https://api/7", "state": "closed", "body": DASHBOARD_MARKER}
        client.publish("o/r", [closed], "new")
        self.assertEqual({"body": "new", "state": "open"}, client.calls[0][2])

    def test_dashboard_lookup_ignores_pull_requests_and_quoted_markers(self):
        quoted = {"number": 1, "body": f"mentions {DASHBOARD_MARKER} in prose"}
        pull = {"number": 2, "body": DASHBOARD_MARKER, "pull_request": {}}
        real = {"number": 3, "body": DASHBOARD_MARKER + "\n# Agent Workflow Dashboard"}
        self.assertIsNone(find_dashboard([quoted, pull]))
        self.assertIs(real, find_dashboard([quoted, pull, real]))
        newer = {"number": 9, "body": DASHBOARD_MARKER}
        self.assertIs(real, find_dashboard([newer, real]))


if __name__ == "__main__":
    unittest.main()
