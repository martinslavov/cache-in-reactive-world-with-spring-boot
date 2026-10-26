import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3] / ".github"
WORKFLOWS = sorted((ROOT / "workflows").glob("*.yml"))
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+(\.\d+)*\S*$")


class WorkflowSecurityTest(unittest.TestCase):
    def test_workflows_found(self):
        self.assertTrue(WORKFLOWS)

    def test_top_level_permissions_are_empty(self):
        for path in WORKFLOWS:
            with self.subTest(workflow=path.name):
                self.assertRegex(path.read_text(encoding="utf-8"), r"(?m)^permissions: \{\}\s*$")

    def test_every_action_is_pinned_to_a_full_sha(self):
        for path in WORKFLOWS:
            for line in path.read_text(encoding="utf-8").splitlines():
                match = re.match(r"\s*(?:- )?uses:\s*(.+)$", line)
                if match:
                    with self.subTest(workflow=path.name, uses=match.group(1)):
                        self.assertRegex(match.group(1), PINNED)

    def test_no_privileged_untrusted_triggers(self):
        for path in WORKFLOWS:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("pull_request_target", text)
                self.assertNotIn("workflow_run", text)

    def test_dependabot_updates_github_actions(self):
        text = (ROOT / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: github-actions", text)
        self.assertRegex(text, r"directory: /\s")
        self.assertIn("interval: weekly", text)


if __name__ == "__main__":
    unittest.main()
