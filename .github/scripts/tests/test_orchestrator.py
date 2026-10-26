import json
import unittest
from unittest.mock import Mock

from orchestrator import (
    ACTIVE_STATES,
    ATTEMPT_LOOPS,
    STATE_TABLE,
    Orchestrator,
    OrchestratorError,
    default_record,
    parse_record,
    serialize_record,
    transition_record,
    validate_transition,
)


class OrchestratorStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.now = "2026-10-26T09:00:00Z"

    def record(self, state="implementation"):
        return default_record(101, state, "human", self.now)

    def test_every_allowed_edge(self):
        for source, (owner, targets) in STATE_TABLE.items():
            for target in targets:
                with self.subTest(source=source, target=target):
                    actor = owner or "human"
                    record = self.record(source)
                    updated = transition_record(record, target, actor, now=self.now)
                    self.assertEqual(updated["state"], target)
            if source in ACTIVE_STATES:
                for target in ("blocked", "human-review"):
                    with self.subTest(source=source, target=target, actor="stage owner"):
                        actor = owner or "human"
                        updated = transition_record(self.record(source), target, actor, now=self.now)
                        self.assertEqual(updated["resume_state"], source)
                    with self.subTest(source=source, target=target, actor="human"):
                        updated = transition_record(self.record(source), target, "human", now=self.now)
                        self.assertEqual(updated["resume_state"], source)

    def test_blocked_and_human_review_resume_only_to_saved_state(self):
        for exceptional in ("blocked", "human-review"):
            with self.subTest(state=exceptional):
                paused = transition_record(self.record("implementation"), exceptional, "human", now=self.now)
                self.assertEqual(paused["resume_state"], "implementation")
                resumed = transition_record(paused, "implementation", "human", now=self.now)
                self.assertIsNone(resumed["resume_state"])
                self.assertEqual(resumed["owner_agent"], "senior-java-software-engineer")
                with self.assertRaisesRegex(OrchestratorError, "saved resume_state"):
                    transition_record(paused, "pr-review", "human", now=self.now)
                with self.assertRaisesRegex(OrchestratorError, "only human"):
                    transition_record(paused, "implementation", "senior-java-software-engineer", now=self.now)

    def test_rejected_edges(self):
        for source, (_, targets) in STATE_TABLE.items():
            allowed = set(targets)
            if source in ACTIVE_STATES:
                allowed.update({"blocked", "human-review"})
            for target in STATE_TABLE:
                if target not in allowed and source not in {"blocked", "human-review"}:
                    with self.subTest(source=source, target=target):
                        with self.assertRaises(OrchestratorError):
                            validate_transition(self.record(source), target, STATE_TABLE[source][0] or "human")

    def test_wrong_agent_is_rejected(self):
        with self.assertRaisesRegex(OrchestratorError, "cannot transition"):
            validate_transition(self.record("implementation"), "pr-review", "pr-review-agent")
        with self.assertRaisesRegex(OrchestratorError, "cannot transition"):
            validate_transition(self.record("architecture"), "implementation", "senior-java-software-engineer")

    def test_rejected_pure_requests_make_zero_gh_calls(self):
        runner = Mock()
        orchestrator = Orchestrator(runner)
        with self.assertRaises(OrchestratorError):
            orchestrator.prepare_transition(self.record("implementation"), "done", "senior-java-software-engineer")
        with self.assertRaises(OrchestratorError):
            orchestrator.prepare_transition(self.record("implementation"), "pr-review", "qa-agent")
        runner.assert_not_called()

    def test_approval_pending_requires_an_explicit_owner_approval_comment(self):
        approval_record = self.record("approval-pending")
        body = serialize_record(approval_record)
        runner = Mock(return_value=json.dumps({"id": 101, "body": body, "author": "martinslavov"}))
        orchestrator = Orchestrator(runner)
        with self.assertRaisesRegex(OrchestratorError, "architecture-approved"):
            orchestrator.transition(101, "implementation", "human", None, dry_run=False)
        self.assertEqual(runner.call_count, 2)
        self.assertTrue(all("-X" not in call.args[0] for call in runner.call_args_list))

    def test_record_serialization_and_parse_round_trip(self):
        record = self.record()
        encoded = serialize_record(record)
        self.assertTrue(encoded.startswith("<!-- task-state: {"))
        self.assertTrue(encoded.endswith("} -->"))
        self.assertEqual(parse_record(encoded), record)
        self.assertEqual(record["lock"]["ttl_s"], 1800)
        self.assertEqual(record["actions"], {})
        self.assertEqual(set(record["attempts"]), set(ATTEMPT_LOOPS))
        self.assertTrue(all(v == {"count": 0, "last_reason": None, "last_signature": None}
                            for v in record["attempts"].values()))

    def test_parse_requires_exactly_one_valid_record(self):
        with self.assertRaisesRegex(OrchestratorError, "found 0"):
            parse_record("no state here")
        encoded = serialize_record(self.record())
        with self.assertRaisesRegex(OrchestratorError, "found 2"):
            parse_record(encoded + "\n" + encoded)
        malformed = "<!-- task-state: {not-json} -->"
        with self.assertRaisesRegex(OrchestratorError, "invalid task-state JSON"):
            parse_record(malformed)

    def test_transition_edits_canonical_comment_before_label_and_board_projection(self):
        record = self.record()
        calls = []

        def runner(args):
            calls.append(args)
            if args[-1] == f"repos/martinslavov/rcas/issues/101/comments":
                return json.dumps({"id": 987, "body": serialize_record(record), "author": "martinslavov"})
            if args[-1] == "repos/martinslavov/rcas/issues/101/labels":
                return "state:implementation"
            return ""

        orchestrator = Orchestrator(runner)
        updated = orchestrator.transition(101, "pr-review", "senior-java-software-engineer", None, False)
        self.assertEqual(updated["state"], "pr-review")
        patch_index = next(i for i, call in enumerate(calls) if "-X" in call and "PATCH" in call)
        label_index = next(i for i, call in enumerate(calls) if call[:3] == ["gh", "label", "create"])
        board_index = next(i for i, call in enumerate(calls) if call[-3:] == ["move", "101", "In Progress"])
        self.assertLess(patch_index, label_index)
        self.assertLess(label_index, board_index)
        self.assertTrue(any("-X" in call and "POST" in call for call in calls))
        self.assertTrue(any("-X" in call and "DELETE" in call and call[-1].endswith("state:implementation")
                            for call in calls))

    def test_projection_failure_reports_comment_is_already_canonical(self):
        record = self.record()
        calls = []

        def runner(args):
            calls.append(args)
            if args[-1] == "repos/martinslavov/rcas/issues/101/comments":
                return json.dumps({"id": 987, "body": serialize_record(record), "author": "martinslavov"})
            if args[:3] == ["gh", "label", "create"]:
                raise RuntimeError("label service unavailable")
            return ""

        orchestrator = Orchestrator(runner)
        with self.assertRaisesRegex(OrchestratorError, "state comment was updated, but projection failed"):
            orchestrator.transition(101, "pr-review", "senior-java-software-engineer", None, False)
        self.assertTrue(any("PATCH" in call for call in calls))
        self.assertFalse(any("task_queue.sh" in call[0] for call in calls))

    def test_transition_updates_head_sha_and_metadata(self):
        updated = transition_record(
            self.record(), "pr-review", "senior-java-software-engineer",
            "0123456789abcdef", now=self.now,
        )
        self.assertEqual(updated["head_sha"], "0123456789abcdef")
        self.assertEqual(updated["updated_by"], "senior-java-software-engineer")
        self.assertEqual(updated["updated_at"], self.now)


if __name__ == "__main__":
    unittest.main()
