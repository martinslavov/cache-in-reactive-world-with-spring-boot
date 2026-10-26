import json
import os
import pathlib
import subprocess
import tempfile
import textwrap
import unittest

from tests.test_workflow_security import ROOT, _jobs, _steps

SHA_A = "a" * 40
SHA_B = "b" * 40

# Mock GitHub CLI backed by a JSON file so refs/releases persist across invocations.
MOCK_GH = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json
    import os
    import sys

    args = sys.argv[1:]
    state_path = os.environ["GH_MOCK_STATE"]
    with open(state_path, encoding="utf-8") as handle:
        state = json.load(handle)

    def save():
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)

    def log(entry):
        state["calls"].append(entry)
        save()

    def flag(name):
        return args[args.index(name) + 1]

    if args[:2] == ["release", "view"]:
        sys.exit(0 if args[2] in state["releases"] else 1)
    if args[:2] == ["release", "create"]:
        tag = args[2]
        log(["release-create", tag] + [a for a in args[3:] if a.endswith(".jar")])
        state["releases"].append(tag)
        save()
        sys.exit(0)
    endpoint = next((a for a in args if a.startswith("repos/test/repo/")), "")
    if endpoint == "repos/test/repo/commits/" + state["commit"]:
        print(state["commit"])
    elif endpoint == "repos/test/repo/git/matching-refs/tags/v":
        for tag, sha in state["refs"].items():
            print(tag + "\\tcommit\\t" + sha)
    elif "-X" in args and "POST" in args and endpoint == "repos/test/repo/git/refs":
        fields = dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "-f")
        log(["post", fields["ref"], fields["sha"]])
        if state.get("fail_posts", 0) > 0:
            state["fail_posts"] -= 1
            save()
            sys.exit(1)
        state["refs"][fields["ref"].removeprefix("refs/tags/")] = fields["sha"]
        save()
        print(fields["ref"])
    else:
        sys.exit("unexpected gh invocation: " + repr(args))
    """
)


def _run_script(step):
    run_content = step.split("        run: |\n", 1)[1]
    lines = []
    for line in run_content.splitlines():
        if line.startswith("          "):
            lines.append(line[10:])
        elif not line.strip():
            lines.append("")
        else:
            break
    return textwrap.dedent("\n".join(lines))


def _step(workflow, name, job=None):
    text = (ROOT / "workflows" / workflow).read_text(encoding="utf-8")
    if job:
        text = _jobs(text)[job]
    return _run_script(next(s for s in _steps(text) if f"name: {name}" in s))


class MockedGh:
    def __init__(self, test, refs=None, releases=None, commit=SHA_A, fail_posts=0):
        self.temp = tempfile.TemporaryDirectory()
        test.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name)
        gh = self.path / "gh"
        gh.write_text(MOCK_GH, encoding="utf-8")
        gh.chmod(0o755)
        self.state_file = self.path / "state.json"
        self.state_file.write_text(json.dumps({
            "refs": refs or {}, "releases": releases or [], "calls": [],
            "commit": commit, "fail_posts": fail_posts,
        }), encoding="utf-8")
        self.output = self.path / "output"
        self.output.write_text("", encoding="utf-8")

    def state(self):
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def run(self, script, **env):
        merged = os.environ | {
            "PATH": f"{self.temp.name}:{os.environ['PATH']}",
            "GH_MOCK_STATE": str(self.state_file),
            "GITHUB_OUTPUT": str(self.output),
            "REPO": "test/repo",
        } | env
        return subprocess.run(["bash", "-c", script], cwd=self.temp.name, check=False,
                              capture_output=True, text=True, env=merged)

    def posts(self):
        return [c for c in self.state()["calls"] if c[0] == "post"]


class TagStepBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-tag.yml", "Create tag", job="tag")

    def tag(self, gh, plan_tag="v0.1.0", bump="minor", sha=SHA_A):
        return gh.run(self.script, SHA=sha, PLAN_TAG=plan_tag, PLAN_BUMP=bump)

    def test_first_run_creates_planned_tag_at_event_sha_and_rerun_creates_no_duplicate(self):
        gh = MockedGh(self)
        first = self.tag(gh)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(gh.state()["refs"], {"v0.1.0": SHA_A})
        self.assertEqual(gh.posts(), [["post", "refs/tags/v0.1.0", SHA_A]])
        self.assertIn("tag=v0.1.0", gh.output.read_text(encoding="utf-8"))

        gh.output.write_text("", encoding="utf-8")
        second = self.tag(gh)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(gh.posts()), 1, "second run must not POST a duplicate tag")
        self.assertEqual(gh.state()["refs"], {"v0.1.0": SHA_A})
        self.assertIn("already tagged v0.1.0", second.stdout)
        self.assertEqual(gh.output.read_text(encoding="utf-8"), "tag=v0.1.0\n")

    def test_stale_plan_is_recomputed_from_live_tags(self):
        gh = MockedGh(self, refs={"v0.1.0": SHA_B, "v0.2.0": SHA_B})
        result = self.tag(gh, plan_tag="v0.1.0", bump="minor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(gh.posts(), [["post", "refs/tags/v0.3.0", SHA_A]])
        self.assertIn("stale", result.stdout)

    def test_major_bump_is_recomputed_from_newest_stable_tag(self):
        gh = MockedGh(self, refs={"v1.9.4": SHA_B, "v1.10.0": SHA_B, "v2.0.0-rc.1": SHA_B})
        result = self.tag(gh, plan_tag="v2.0.0", bump="major")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(gh.posts(), [["post", "refs/tags/v2.0.0", SHA_A]])

    def test_conflicting_ref_creation_is_retried(self):
        gh = MockedGh(self, fail_posts=1)
        result = self.tag(gh)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(gh.posts()), 2)
        self.assertEqual(gh.state()["refs"], {"v0.1.0": SHA_A})

    def test_malicious_plan_outputs_and_sha_are_rejected_without_posting(self):
        cases = [
            {"plan_tag": "v1.0.0; touch pwned", "bump": "patch"},
            {"plan_tag": "v1.0.0-rc.1", "bump": "patch"},
            {"plan_tag": "v01.0.0", "bump": "patch"},
            {"plan_tag": "v0.1.0", "bump": "huge"},
            {"plan_tag": "v0.1.0", "bump": "patch", "sha": "main"},
            {"plan_tag": "v0.1.0", "bump": "patch", "sha": SHA_B},
        ]
        for case in cases:
            with self.subTest(case=case):
                gh = MockedGh(self)
                result = self.tag(gh, **case)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(gh.posts(), [])
                self.assertFalse((gh.path / "pwned").exists())


class ReleaseStepBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-release.yml", "Create GitHub release", job="release")

    def prepare(self, gh):
        libs = gh.path / "build" / "libs"
        libs.mkdir(parents=True)
        (libs / "rcas-0.0.1.jar").write_text("jar", encoding="utf-8")

    def test_creates_release_only_when_absent_with_tag_and_jar(self):
        gh = MockedGh(self)
        self.prepare(gh)
        result = gh.run(self.script, TAG="v0.1.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        state = gh.state()
        self.assertEqual(state["releases"], ["v0.1.0"])
        self.assertEqual(state["calls"], [["release-create", "v0.1.0", "build/libs/rcas-0.0.1.jar"]])
        self.assertTrue((gh.path / "build/libs/rcas-0.0.1.jar").is_file())

    def test_existing_release_is_left_unchanged(self):
        gh = MockedGh(self, releases=["v0.1.0"])
        self.prepare(gh)
        result = gh.run(self.script, TAG="v0.1.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        state = gh.state()
        self.assertEqual(state["releases"], ["v0.1.0"])
        self.assertEqual(state["calls"], [])
        self.assertIn("already exists", result.stdout)


if __name__ == "__main__":
    unittest.main()
