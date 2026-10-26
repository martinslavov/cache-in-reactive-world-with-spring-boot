import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3] / ".github"
WORKFLOWS = sorted((ROOT / "workflows").glob("*.yml"))
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+(\.\d+)*\S*$")
DOCKER_LOGIN_WORKFLOWS = ("ci-component-tests.yml", "ci-sanity-tests.yml")


def _steps(text):
    body = text.split("\n    steps:\n", 1)[1]
    return re.split(r"(?m)^      - ", body)[1:]


def _index(steps, predicate):
    matches = [i for i, step in enumerate(steps) if predicate(step)]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one matching step, found {len(matches)}")
    return matches[0]


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

    def test_registry_logout_happens_before_pr_code_runs(self):
        for name in DOCKER_LOGIN_WORKFLOWS:
            with self.subTest(workflow=name):
                steps = _steps((ROOT / "workflows" / name).read_text(encoding="utf-8"))
                login = _index(steps, lambda s: "docker/login-action@" in s)
                pull = _index(steps, lambda s: "docker pull" in s)
                logout = _index(steps, lambda s: "docker logout dhi.io" in s)
                checkout = _index(steps, lambda s: "actions/checkout@" in s)
                pr_code = [i for i, s in enumerate(steps) if re.search(r"run:.*\b(make|gradle|gradlew)\b", s, re.S)]
                self.assertTrue(pr_code)
                self.assertLess(login, pull)
                self.assertLess(pull, logout)
                self.assertIn("if: always()", steps[logout])
                self.assertLess(logout, checkout)
                self.assertLess(logout, min(pr_code))

    def test_pulled_images_cover_dockerfile_base_images(self):
        dockerfile = (ROOT.parent / "Dockerfile").read_text(encoding="utf-8")
        base_images = set(re.findall(r"(?m)^FROM\s+(?:--\S+\s+)*(\S+)", dockerfile))
        for name in DOCKER_LOGIN_WORKFLOWS:
            with self.subTest(workflow=name):
                text = (ROOT / "workflows" / name).read_text(encoding="utf-8")
                pulled = set(re.search(r"DHI_IMAGES:\s*(.+)", text).group(1).split())
                self.assertTrue({i for i in base_images if i.startswith("dhi.io/")} <= pulled)

    def test_dependabot_updates_github_actions(self):
        text = (ROOT / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: github-actions", text)
        self.assertRegex(text, r"directory: /\s")
        self.assertIn("interval: weekly", text)


if __name__ == "__main__":
    unittest.main()
