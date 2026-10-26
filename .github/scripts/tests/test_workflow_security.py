import os
import pathlib
import re
import subprocess
import tempfile
import textwrap
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


def _jobs(text):
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  ([\w-]+):\n", body)[1:]
    return dict(zip(parts[::2], parts[1::2]))


RELEASE_QUEUE = "    concurrency:\n      group: release-tag\n      queue: max\n"


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
                if match and not match.group(1).startswith("./.github/workflows/"):
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

    def test_release_tagging_is_limited_to_merged_main_prs_and_fork_fallback(self):
        text = (ROOT / "workflows" / "ci-tag.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn("types: [closed]", text)
        self.assertIn("github.event.pull_request.merged == true", text)
        self.assertIn("github.event.pull_request.base.ref == 'main'", text)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", text)
        self.assertIn("github.event_name == 'push'", text)
        self.assertIn(".head.repo.full_name != $repo", text)
        self.assertIn("pull-requests: read", text)
        self.assertIn("contents: write", text)
        self.assertEqual(text.count("github.event.pull_request.merge_commit_sha || github.sha"), 2)
        self.assertIn("git/tags/$object_sha", text)
        self.assertIn("release_tag.py existing --sha", text)
        self.assertIn("uses: ./.github/workflows/ci-release.yml", text)
        self.assertNotIn("merge_commit_sha ||", text.split("jobs:")[0])
        self.assertIn("for attempt in $(seq 1 10)", text)

    def test_release_builds_tag_and_prunes_with_job_scoped_write_permissions(self):
        text = (ROOT / "workflows" / "ci-release.yml").read_text(encoding="utf-8")
        self.assertIn('tags:\n      - "v**"', text)
        self.assertIn("workflow_call:", text)
        self.assertIn("required: true", text)
        self.assertIn("contents: write", text)
        self.assertIn("ref: refs/tags/${{ inputs.tag || github.ref_name }}", text)
        self.assertIn("./gradlew build", text)
        self.assertIn("build/libs/*.jar", text)
        self.assertIn('gh api -X DELETE "repos/$REPO/releases/$release_id"', text)
        self.assertIn('gh api -X DELETE "repos/$REPO/git/refs/tags/$tag"', text)

    def test_prune_job_does_not_execute_repository_code_with_write_token(self):
        text = (ROOT / "workflows" / "ci-release.yml").read_text(encoding="utf-8")
        prune = _jobs(text)["prune"]
        self.assertIn("contents: write", prune)
        self.assertNotIn("actions/checkout", prune)
        self.assertNotIn(".github/scripts", prune)
        self.assertNotRegex(prune, r"\bpython3?\b")

    def test_prune_lists_releases_once_and_does_not_treat_release_view_errors_as_absence(self):
        text = (ROOT / "workflows" / "ci-release.yml").read_text(encoding="utf-8")
        prune = _jobs(text)["prune"]
        self.assertEqual(prune.count('gh api "repos/$REPO/releases" --paginate'), 1)
        self.assertNotIn("gh release view", prune)
        self.assertIn("set -euo pipefail", prune)
        self.assertIn("awk -F '\\t' -v tag=\"$tag\"", prune)

    def test_prune_deletes_release_by_id_before_tag_and_fails_closed_on_release_list_error(self):
        text = (ROOT / "workflows" / "ci-release.yml").read_text(encoding="utf-8")
        step = next(
            step for step in _steps(text)
            if "name: Delete old releases and tags" in step
        )
        run_content = step.split("        run: |\n", 1)[1]
        script_lines = []
        for line in run_content.splitlines():
            if line.startswith("          "):
                script_lines.append(line[10:])
            elif not line.strip():
                script_lines.append("")
            else:
                break
        script = textwrap.dedent("\n".join(script_lines))

        mock_gh_source = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import sys

            args = sys.argv[1:]
            endpoint = next(
                (arg for arg in args if arg.startswith("repos/test/repo/")),
                "",
            )
            with open(os.environ["GH_MOCK_LOG"], "a", encoding="utf-8") as log:
                if endpoint == "repos/test/repo/releases":
                    log.write("LIST_RELEASES\\n")
                    if os.environ.get("FAIL_RELEASE_LIST") == "1":
                        sys.exit(1)
                    print("v2.10.0\\t210")
                elif endpoint == "repos/test/repo/git/matching-refs/tags/v":
                    log.write("LIST_TAGS\\n")
                    print("v1.0.0")
                    print("v2.10.0")
                    print("v3.9.0")
                    print("v4.0.0")
                    print("v1.0.0-rc.1")
                    print("v01.2.3")
                elif "-X" in args and "DELETE" in args:
                    if "/releases/" in endpoint:
                        log.write("DELETE_RELEASE:" + endpoint.rsplit("/", 1)[1] + "\\n")
                    else:
                        log.write("DELETE_TAG:" + endpoint.rsplit("/", 1)[1] + "\\n")
                else:
                    sys.exit("unexpected gh invocation: " + repr(args))
            """
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = pathlib.Path(temp_dir)
            executable = temp / "gh"
            executable.write_text(mock_gh_source, encoding="utf-8")
            executable.chmod(0o755)
            log = temp / "calls.log"
            env = os.environ | {
                "PATH": f"{temp_dir}:{os.environ['PATH']}",
                "GH_MOCK_LOG": str(log),
                "REPO": "test/repo",
                "KEEP_RELEASES": "2",
            }

            result = subprocess.run(
                ["bash", "-c", script],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                [
                    "LIST_RELEASES",
                    "LIST_TAGS",
                    "DELETE_RELEASE:210",
                    "DELETE_TAG:v2.10.0",
                    "DELETE_TAG:v1.0.0",
                ],
                result.stdout + result.stderr,
            )

            log.write_text("", encoding="utf-8")
            env["FAIL_RELEASE_LIST"] = "1"
            result = subprocess.run(
                ["bash", "-c", script],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["LIST_RELEASES"])

    def test_mutating_release_jobs_share_one_global_job_level_queue(self):
        critical = {"ci-tag.yml": ("tag",), "ci-release.yml": ("release", "prune")}
        for workflow, job_names in critical.items():
            text = (ROOT / "workflows" / workflow).read_text(encoding="utf-8")
            with self.subTest(workflow=workflow):
                self.assertNotRegex(text.split("\njobs:\n", 1)[0], r"(?m)^concurrency:")
                self.assertNotIn("cancel-in-progress", text)
                self.assertEqual(text.count("group:"), len(job_names))
            jobs = _jobs(text)
            for job in job_names:
                with self.subTest(workflow=workflow, job=job):
                    self.assertIn(RELEASE_QUEUE, jobs[job])
        caller = _jobs((ROOT / "workflows" / "ci-tag.yml").read_text(encoding="utf-8"))["release"]
        self.assertNotIn("concurrency:", caller)

    def test_tag_write_job_is_separated_from_the_read_only_plan_job(self):
        jobs = _jobs((ROOT / "workflows" / "ci-tag.yml").read_text(encoding="utf-8"))
        plan, tag = jobs["plan"], jobs["tag"]
        self.assertIn("contents: read", plan)
        self.assertIn("pull-requests: read", plan)
        self.assertNotIn("write", plan)
        self.assertNotIn("concurrency:", plan)
        self.assertIn("actions/checkout@", plan)
        self.assertIn("release_tag.py next", plan)
        self.assertIn("needs: plan", tag)
        self.assertIn("contents: write", tag)
        self.assertNotIn("pull-requests", tag)
        self.assertNotIn("actions/checkout", tag)
        self.assertNotIn("uses:", tag)
        self.assertNotIn(".github/scripts", tag)
        self.assertNotIn("release_tag.py", tag)
        self.assertNotRegex(tag, r"\bpython3?\b")

    def test_tag_write_job_validates_inputs_and_recomputes_from_live_tags(self):
        tag = _jobs((ROOT / "workflows" / "ci-tag.yml").read_text(encoding="utf-8"))["tag"]
        self.assertIn(r"semver='^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'", tag)
        self.assertIn("[[ \"$SHA\" =~ ^[0-9a-f]{40}$ ]]", tag)
        self.assertIn("[[ \"$PLAN_TAG\" =~ $semver ]]", tag)
        self.assertIn("major | minor | patch)", tag)
        self.assertIn('repos/$REPO/commits/$SHA" --jq \'.sha\'', tag)
        self.assertIn("SHA: ${{ github.event.pull_request.merge_commit_sha || github.sha }}", tag)
        self.assertNotIn("needs.plan.outputs.sha", tag)
        self.assertLess(tag.index("[[ \"$PLAN_TAG\" =~ $semver ]]"), tag.index("-X POST"))
        self.assertLess(tag.index("=~ ^[0-9a-f]{40}$"), tag.index("-X POST"))
        self.assertIn("is stale; allocating", tag)
        self.assertIn("already tagged", tag)
        self.assertIn("for attempt in $(seq 1 10)", tag)


if __name__ == "__main__":
    unittest.main()
