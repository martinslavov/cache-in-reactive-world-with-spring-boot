import json
import os
import pathlib
import subprocess
import tarfile
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
        state["releases"][tag] = max(state["releases"].values(), default=0) + 1
        save()
        sys.exit(0)
    endpoint = next((a for a in args if a.startswith("repos/test/repo/")), "")
    jq = flag("--jq") if "--jq" in args else ""
    if "-X" in args and "DELETE" in args:
        if endpoint.startswith("repos/test/repo/releases/"):
            release_id = int(endpoint.rsplit("/", 1)[1])
            tag = next((t for t, i in state["releases"].items() if i == release_id), None)
            if tag is None:
                sys.exit("404 release " + str(release_id))
            del state["releases"][tag]
            log(["delete-release", tag])
        elif endpoint.startswith("repos/test/repo/git/refs/tags/"):
            tag = endpoint.removeprefix("repos/test/repo/git/refs/tags/")
            if tag not in state["refs"]:
                sys.exit("422 reference does not exist: " + tag)
            if tag in state["releases"]:
                sys.exit("tag " + tag + " deleted while its release still exists")
            del state["refs"][tag]
            log(["delete-tag", tag])
        else:
            sys.exit("unexpected gh invocation: " + repr(args))
    elif endpoint == "repos/test/repo/releases":
        log(["list-releases"])
        if state.get("fail_release_list"):
            sys.exit("502 release list failed")
        for tag, release_id in state["releases"].items():
            print(tag + "\t" + str(release_id))
    elif endpoint == "repos/test/repo/commits/" + state["commit"]:
        print(state["commit"])
    elif endpoint == "repos/test/repo/git/matching-refs/tags/v":
        log(["list-tags"])
        for tag, sha in state["refs"].items():
            if tag.startswith("v"):
                print(tag + "\tcommit\t" + sha if ".object.type" in jq else tag)
    elif "-X" in args and "POST" in args and endpoint == "repos/test/repo/git/refs":
        fields = dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "-f")
        tag = fields["ref"].removeprefix("refs/tags/")
        log(["post", fields["ref"], fields["sha"]])
        # A competing run creates the same ref between our tag listing and our POST.
        if tag in state.get("race", {}):
            state["refs"][tag] = state["race"].pop(tag)
            save()
        if tag in state["refs"]:
            sys.exit("422 Reference already exists: " + tag)
        state["refs"][tag] = fields["sha"]
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
    def __init__(self, test, refs=None, releases=None, commit=SHA_A, race=None, fail_release_list=False):
        self.temp = tempfile.TemporaryDirectory()
        test.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name)
        gh = self.path / "gh"
        gh.write_text(MOCK_GH, encoding="utf-8")
        gh.chmod(0o755)
        self.state_file = self.path / "state.json"
        self.state_file.write_text(json.dumps({
            "refs": refs or {}, "releases": releases or {}, "calls": [],
            "commit": commit, "race": race or {}, "fail_release_list": fail_release_list,
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

    def deletes(self):
        return [c for c in self.state()["calls"] if c[0].startswith("delete-")]


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

    def test_competing_ref_conflict_refreshes_tags_and_allocates_next_version(self):
        gh = MockedGh(self, race={"v0.1.0": SHA_B})
        result = self.tag(gh)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(gh.posts(), [["post", "refs/tags/v0.1.0", SHA_A], ["post", "refs/tags/v0.2.0", SHA_A]])
        self.assertEqual(gh.state()["refs"], {"v0.1.0": SHA_B, "v0.2.0": SHA_A})
        self.assertEqual(gh.output.read_text(encoding="utf-8"), "tag=v0.2.0\n")

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


MOCK_RELEASE_GH = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, pathlib, sys
    args = sys.argv[1:]
    path = pathlib.Path(os.environ["GH_MOCK_STATE"])
    state = json.loads(path.read_text(encoding="utf-8"))
    def save(): path.write_text(json.dumps(state), encoding="utf-8")
    def log(value): state.setdefault("calls", []).append(value); save()
    endpoint = next((a for a in args if a.startswith(("repos/test/repo/", "user/"))), "")
    if args[:2] == ["release", "create"]:
        tag = args[2]
        note_path = pathlib.Path(args[args.index("--notes-file") + 1])
        state["releases"][tag] = {"id": 99, "body": note_path.read_text(encoding="utf-8"), "assets": [a for a in args[3:] if a.endswith(".jar")]}
        log(["create-release", tag, state["releases"][tag]["assets"]])
    elif args[:1] == ["api"] and endpoint.startswith("repos/test/repo/git/ref/tags/"):
        tag = endpoint.rsplit("/", 1)[1]
        if tag not in state["refs"]:
            print("HTTP 404: Not Found", file=sys.stderr); sys.exit(1)
        print(json.dumps({"object": {"type": "commit", "sha": state["refs"][tag]}}))
    elif args[:1] == ["api"] and endpoint.startswith("repos/test/repo/releases/tags/"):
        tag = endpoint.rsplit("/", 1)[1]
        if tag not in state["releases"]:
            print("HTTP 404: Not Found", file=sys.stderr); sys.exit(1)
        print(json.dumps(state["releases"][tag]))
    elif args[:1] == ["api"] and "-X" in args and "PATCH" in args:
        release_id = int(endpoint.rsplit("/", 1)[1])
        release = next(r for r in state["releases"].values() if r["id"] == release_id)
        field = args[args.index("-F") + 1]
        release["body"] = pathlib.Path(field.split("=", 1)[1][1:]).read_text(encoding="utf-8")
        log(["patch-release", release_id])
    elif args[:1] == ["api"] and "generate-notes" in endpoint:
        print("Generated release notes")
    elif args[:1] == ["api"] and endpoint.endswith("releases?per_page=100"):
        jq = args[args.index("--jq") + 1] if "--jq" in args else ""
        if "select(.draft" in jq:
            for tag in state.get("release_tags", []): print(tag)
        else:
            for tag, release in state["releases"].items(): print(f"{tag}\\t{release['id']}")
    elif args[:1] == ["api"] and "matching-refs/tags/v" in endpoint:
        for tag in state.get("refs", {}): print(tag)
    elif args[:1] == ["api"] and "packages/container/rcas/versions?" in endpoint:
        print(json.dumps([state.get("packages", [])]))
    elif args[:1] == ["api"] and "-X" in args and "DELETE" in args and "/packages/container/rcas/versions/" in endpoint:
        if state.get("deny_package_delete"):
            print("403 package version deletion denied", file=sys.stderr); sys.exit(1)
        version_id = int(endpoint.rsplit("/", 1)[1])
        state["packages"] = [v for v in state["packages"] if v["id"] != version_id]
        log(["delete-image", version_id])
    elif args[:1] == ["api"] and "-X" in args and "DELETE" in args and "/releases/" in endpoint:
        release_id = int(endpoint.rsplit("/", 1)[1])
        tag = next(t for t, r in state["releases"].items() if r["id"] == release_id)
        del state["releases"][tag]; log(["delete-release", tag])
    elif args[:1] == ["api"] and "-X" in args and "DELETE" in args and "/git/refs/tags/" in endpoint:
        tag = endpoint.rsplit("/", 1)[1]
        if tag in state["releases"]: sys.exit("tag deleted before release")
        state["refs"].pop(tag, None); log(["delete-tag", tag])
    else:
        print("unexpected gh invocation: " + repr(args), file=sys.stderr); sys.exit(2)
    """
)


MOCK_DOCKER = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    path = os.environ["GH_MOCK_STATE"]
    state = json.load(open(path, encoding="utf-8"))
    args = sys.argv[1:]
    state.setdefault("docker", []).append(args)
    if args[:1] == ["build"]:
        if state.get("fail_build"):
            json.dump(state, open(path, "w", encoding="utf-8")); print("build denied", file=sys.stderr); sys.exit(1)
        build_args = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--build-arg"]
        state["image_labels"] = {"org.opencontainers.image." + item.split("=", 1)[0][4:].lower(): item.split("=", 1)[1] for item in build_args}
        label_args = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--label"]
        state["image_labels"].update(item.split("=", 1) for item in label_args)
    elif args[:1] == ["push"]:
        if state.get("fail_push"):
            json.dump(state, open(path, "w", encoding="utf-8")); print("push denied", file=sys.stderr); sys.exit(1)
        state["image_exists"] = True
    elif args[:1] == ["pull"] and not state.get("image_exists"):
        json.dump(state, open(path, "w", encoding="utf-8")); print("manifest unknown", file=sys.stderr); sys.exit(1)
    elif args[:2] == ["image", "inspect"]:
        template = args[args.index("--format") + 1]
        if "RepoDigests" in template: print("ghcr.io/test/repo@sha256:" + "a" * 64)
        else:
            label = template.split('"')[1]
            print(state.get("image_labels", {}).get(label, ""))
    json.dump(state, open(path, "w", encoding="utf-8"))
    """
)


class WorkflowMock:
    def __init__(self, test, **state):
        self.temp = tempfile.TemporaryDirectory()
        test.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name)
        for name, body in (("gh", MOCK_RELEASE_GH), ("docker", MOCK_DOCKER)):
            command = self.path / name
            command.write_text(body, encoding="utf-8")
            command.chmod(0o755)
        defaults = {"releases": {}, "release_tags": [], "refs": {}, "packages": [], "calls": []}
        defaults.update(state)
        if "image_revision" in defaults:
            defaults["image_labels"] = {
                "org.opencontainers.image.source": "https://github.com/test/repo",
                "org.opencontainers.image.version": "v0.1.0",
                "org.opencontainers.image.revision": defaults["image_revision"],
            }
        self.state_file = self.path / "state.json"
        self.state_file.write_text(json.dumps(defaults), encoding="utf-8")
        self.runner_temp = self.path / "runner-temp"
        self.runner_temp.mkdir()
        self.jar_dir = self.path / "build" / "libs"
        self.jar_dir.mkdir(parents=True)
        (self.jar_dir / "rcas-0.0.1.jar").write_text("jar", encoding="utf-8")
        healthcheck = self.path / "build" / "healthcheck" / "HealthCheck.class"
        healthcheck.parent.mkdir(parents=True)
        healthcheck.write_text("class", encoding="utf-8")
        self.output = self.path / "github-output"
        self.output.write_text("", encoding="utf-8")

    def state(self):
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def run(self, script, **env):
        environment = os.environ | {
            "PATH": f"{self.path}:{os.environ['PATH']}",
            "GH_MOCK_STATE": str(self.state_file),
            "RUNNER_TEMP": str(self.runner_temp),
            "GITHUB_OUTPUT": str(self.output),
            "REPO": "test/repo",
            "TAG": "v0.1.0",
            "IMAGE": "ghcr.io/test/repo:v0.1.0",
            "DIGEST": "sha256:" + "a" * 64,
            "KEEP_RELEASES": "2",
        } | env
        return subprocess.run(["bash", "-c", script], cwd=self.path, check=False,
                              capture_output=True, text=True, env=environment)


class BuildArtifactBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-release.yml", "Package jar and health-check class", job="build")

    def test_packages_the_single_boot_jar_and_health_check_class(self):
        gh = WorkflowMock(self)
        result = gh.run(self.script)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with tarfile.open(gh.path / "release-image-context.tar.gz", "r:gz") as archive:
            self.assertTrue({
                "build/libs/rcas-0.0.1.jar", "build/healthcheck/HealthCheck.class"
            } <= set(archive.getnames()))

    def test_rejects_multiple_boot_jar_candidates(self):
        gh = WorkflowMock(self)
        (gh.jar_dir / "rcas-plain.jar").write_text("plain", encoding="utf-8")
        result = gh.run(self.script)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected exactly one boot jar", result.stderr)


class ReleaseStepBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-release.yml", "Create or update release notes", job="release")

    def test_creates_release_with_image_reference_and_digest_after_image_job(self):
        gh = WorkflowMock(self)
        result = gh.run(self.script)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        release = gh.state()["releases"]["v0.1.0"]
        self.assertIn("ghcr.io/test/repo:v0.1.0", release["body"])
        self.assertIn("sha256:" + "a" * 64, release["body"])
        self.assertEqual(release["assets"], ["build/libs/rcas-0.0.1.jar"])

    def test_existing_release_notes_are_updated_idempotently_without_changing_assets(self):
        original = {"id": 7, "body": "Original release notes", "assets": ["original.jar"]}
        gh = WorkflowMock(self, releases={"v0.1.0": original})
        for _ in range(2):
            result = gh.run(self.script)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        release = gh.state()["releases"]["v0.1.0"]
        self.assertEqual(release["assets"], ["original.jar"])
        self.assertIn("Original release notes", release["body"])
        self.assertEqual(release["body"].count("<!-- rcas-image-reference -->"), 1)
        self.assertEqual(len([c for c in gh.state()["calls"] if c[0] == "patch-release"]), 2)


class PublishImageBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-release.yml", "Build or verify release image", job="publish")

    def publish(self, gh, **env):
        return gh.run(self.script, COMMIT=SHA_A, TAG="v0.1.0", REPO="test/repo", **env)

    def test_builds_and_pushes_same_run_artifacts_with_oci_labels_and_digest(self):
        gh = WorkflowMock(self)
        result = self.publish(gh)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = gh.state()
        build = next(call for call in state["docker"] if call[0] == "build")
        self.assertIn("OCI_SOURCE=https://github.com/test/repo", build)
        self.assertIn("OCI_VERSION=v0.1.0", build)
        self.assertIn(f"OCI_REVISION={SHA_A}", build)
        self.assertIn("org.opencontainers.image.source=https://github.com/test/repo", build)
        self.assertIn("org.opencontainers.image.version=v0.1.0", build)
        self.assertIn(f"org.opencontainers.image.revision={SHA_A}", build)
        self.assertIn(["push", "ghcr.io/test/repo:v0.1.0"], state["docker"])
        self.assertIn("digest=sha256:" + "a" * 64, gh.output.read_text(encoding="utf-8"))
        self.assertTrue((gh.path / "build" / "libs" / "rcas-0.0.1.jar").is_file())
        self.assertTrue((gh.path / "build" / "healthcheck" / "HealthCheck.class").is_file())

    def test_matching_existing_image_is_reused_and_mismatched_revision_is_rejected(self):
        package = [{"id": 4, "metadata": {"container": {"tags": ["v0.1.0"]}}}]
        matching = WorkflowMock(self, packages=package, image_exists=True, image_revision=SHA_A)
        result = self.publish(matching)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = matching.state()["docker"]
        self.assertIn(["pull", "ghcr.io/test/repo:v0.1.0"], calls)
        self.assertFalse(any(call[0] in ("build", "push") for call in calls))

        mismatch = WorkflowMock(self, packages=package, image_exists=True, image_revision=SHA_B)
        result = self.publish(mismatch)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OCI labels do not match", result.stderr)
        self.assertFalse(any(call[0] in ("build", "push") for call in mismatch.state()["docker"]))

    def test_push_failure_is_visible_and_publishes_no_digest(self):
        gh = WorkflowMock(self, fail_push=True)
        result = self.publish(gh)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("push denied", result.stderr)
        self.assertNotIn("digest=", gh.output.read_text(encoding="utf-8"))

    def test_build_failure_is_visible_and_does_not_push_or_publish_a_digest(self):
        gh = WorkflowMock(self, fail_build=True)
        result = self.publish(gh)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("build denied", result.stderr)
        self.assertFalse(any(call[0] == "push" for call in gh.state()["docker"]))
        self.assertNotIn("digest=", gh.output.read_text(encoding="utf-8"))


class ResolveTagBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-release.yml", "Validate tag and resolve its commit", job="resolve")

    def test_rejects_malformed_and_nonexistent_dispatch_tags(self):
        malformed = WorkflowMock(self)
        result = malformed.run(self.script, TAG="v01.0.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(malformed.state()["calls"], [])

        missing = WorkflowMock(self)
        result = missing.run(self.script, TAG="v1.0.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("tag=v1.0.0", missing.output.read_text(encoding="utf-8"))

        existing = WorkflowMock(self, refs={"v0.1.0": SHA_A})
        result = existing.run(self.script, TAG="v0.1.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"commit={SHA_A}", existing.output.read_text(encoding="utf-8"))

class BackfillExistingReleaseEndToEndTest(unittest.TestCase):
    """Runs the extracted resolve -> publish -> release steps for a workflow_dispatch backfill."""

    @classmethod
    def setUpClass(cls):
        cls.resolve = _step("ci-release.yml", "Validate tag and resolve its commit", job="resolve")
        cls.publish = _step("ci-release.yml", "Build or verify release image", job="publish")
        cls.release = _step("ci-release.yml", "Create or update release notes", job="release")

    def test_dispatch_tag_input_feeds_the_resolve_step(self):
        text = (ROOT / "workflows" / "ci-release.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:\n    inputs:\n      tag:", text)
        self.assertIn("TAG: ${{ inputs.tag || github.event.inputs.tag || github.ref_name }}", text)

    def test_dispatch_rejects_non_strict_tags_without_calling_gh(self):
        for tag in ("v1.2", "1.2.3", "v1.2.3-rc.1", "v01.2.3", "v1.2.3\nx", "main", "v1.2.3; touch pwned"):
            with self.subTest(tag=tag):
                gh = WorkflowMock(self, refs={"v1.2.3": SHA_A})
                result = gh.run(self.resolve, TAG=tag)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(gh.state()["calls"], [])
                self.assertEqual(gh.output.read_text(encoding="utf-8"), "")
                self.assertFalse((gh.path / "pwned").exists())

    def test_backfill_of_existing_release_publishes_image_and_keeps_jar_asset(self):
        original = {"id": 7, "body": "Original release notes", "assets": ["original.jar"]}
        gh = WorkflowMock(self, refs={"v0.1.0": SHA_A}, releases={"v0.1.0": original})

        resolved = gh.run(self.resolve, TAG="v0.1.0")
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        outputs = dict(line.split("=", 1) for line in gh.output.read_text(encoding="utf-8").splitlines())
        self.assertEqual(outputs, {"tag": "v0.1.0", "commit": SHA_A})

        gh.output.write_text("", encoding="utf-8")
        published = gh.run(self.publish, TAG=outputs["tag"], COMMIT=outputs["commit"])
        self.assertEqual(published.returncode, 0, published.stdout + published.stderr)
        state = gh.state()
        self.assertIn(["push", "ghcr.io/test/repo:v0.1.0"], state["docker"])
        self.assertEqual(state["image_labels"]["org.opencontainers.image.revision"], SHA_A)
        digest = dict(line.split("=", 1) for line in gh.output.read_text(encoding="utf-8").splitlines())["digest"]
        self.assertEqual(digest, "sha256:" + "a" * 64)

        for _ in range(2):
            released = gh.run(self.release, TAG=outputs["tag"], DIGEST=digest,
                              IMAGE=f"ghcr.io/test/repo:{outputs['tag']}")
            self.assertEqual(released.returncode, 0, released.stdout + released.stderr)
        state = gh.state()
        release = state["releases"]["v0.1.0"]
        self.assertEqual(release["assets"], ["original.jar"])
        self.assertIn("Original release notes", release["body"])
        self.assertEqual(release["body"].count("ghcr.io/test/repo:v0.1.0"), 1)
        self.assertEqual(release["body"].count(digest), 1)
        self.assertFalse([c for c in state["calls"] if c[0] == "create-release"])
        self.assertEqual(len(state["releases"]), 1)


class DocumentationBehaviorTest(unittest.TestCase):
    def test_readme_documents_image_tags_latest_retention_and_run_configuration(self):
        readme = (ROOT.parent / "README.md").read_text(encoding="utf-8")
        for evidence in (
            "ghcr.io/martinslavov/rcas:vX.Y.Z",
            "latest",
            "newest two stable releases",
            "workflow_dispatch",
            "SPRING_R2DBC_URL",
            "SPRING_DATA_REDIS_HOST",
            "docker compose up -d",
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, readme)

class LatestImageBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-release.yml", "Point latest at the highest stable release", job="latest")

    def test_latest_uses_numeric_highest_release_even_when_an_older_tag_is_dispatched(self):
        gh = WorkflowMock(self, release_tags=["v2.9.0", "v2.10.0", "v10.0.0", "v11.0.0-rc.1", "v01.0.0"], image_exists=True)
        result = gh.run(self.script, IMAGE="ghcr.io/test/repo")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(gh.state()["docker"], [
            ["pull", "ghcr.io/test/repo:v10.0.0"],
            ["tag", "ghcr.io/test/repo:v10.0.0", "ghcr.io/test/repo:latest"],
            ["push", "ghcr.io/test/repo:latest"],
        ])


class PruneStepBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-release.yml", "Prune stale images before releases and tags", job="prune")

    def inventory(self, deny=False):
        tags = ["v1.0.0", "v2.9.0", "v2.10.0", "v10.0.0"]
        releases = {tag: {"id": i + 1, "body": "", "assets": []} for i, tag in enumerate(tags)}
        versions = [
            {"id": 10, "metadata": {"container": {"tags": ["v1.0.0"]}}},
            {"id": 29, "metadata": {"container": {"tags": ["v2.9.0"]}}},
            {"id": 210, "metadata": {"container": {"tags": ["v2.10.0", "latest"]}}},
            {"id": 100, "metadata": {"container": {"tags": ["v10.0.0"]}}},
            {"id": 50, "metadata": {"container": {"tags": ["v1.0.0", "manual"]}}},
        ]
        return WorkflowMock(self, refs={tag: SHA_B for tag in tags}, releases=releases,
                            packages=versions, deny_package_delete=deny)

    def test_prunes_only_images_for_evicted_tags_before_releases_and_tags(self):
        gh = self.inventory()
        result = gh.run(self.script)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = gh.state()
        self.assertEqual(set(state["refs"]), {"v2.10.0", "v10.0.0"})
        self.assertEqual(set(state["releases"]), {"v2.10.0", "v10.0.0"})
        remaining_ids = {version["id"] for version in state["packages"]}
        self.assertEqual(remaining_ids, {210, 100, 50})
        calls = state["calls"]
        for tag, version_id in (("v1.0.0", 10), ("v2.9.0", 29)):
            self.assertLess(calls.index(["delete-image", version_id]), calls.index(["delete-release", tag]))
        self.assertFalse(any(call[0] == "delete-image" and call[1] == 210 for call in calls))

    def test_denied_image_deletion_fails_closed_and_keeps_release_and_tag(self):
        gh = self.inventory(deny=True)
        result = gh.run(self.script)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grant package-version deletion access", result.stderr)
        state = gh.state()
        self.assertEqual(len(state["releases"]), 4)
        self.assertEqual(len(state["refs"]), 4)
        self.assertFalse(any(call[0] in ("delete-release", "delete-tag") for call in state["calls"]))


class ProjectBoardTokenBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _step("ci-pr-issue-tracking.yml", "Add tracking issue to RCAS Tracking board", job="create-issue")

    MOCK_GH = """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_LOG"
case "$*" in
  *"user(login"*) echo '{"id":"PROJ","field":{"id":"FIELD","options":[{"id":"O1","name":"Todo"},{"id":"O2","name":"Assessment"}]}}' ;;
  *addProjectV2ItemById*) echo ITEM ;;
  *updateProjectV2ItemFieldValue*) ;;
  *"repos/"*) echo ISSUE_NODE ;;
  *) exit 98 ;;
esac
"""

    def run_step(self, token):
        with tempfile.TemporaryDirectory() as directory:
            gh = pathlib.Path(directory) / "gh"
            gh.write_text(self.MOCK_GH, encoding="utf-8")
            gh.chmod(0o755)
            log = pathlib.Path(directory) / "gh.log"
            result = subprocess.run(
                ["/bin/bash", "-c", self.script],
                check=False,
                capture_output=True,
                text=True,
                env=os.environ | {
                    "PATH": directory + os.pathsep + os.environ["PATH"],
                    "GH_TOKEN": token,
                    "GH_LOG": str(log),
                    "GITHUB_REPOSITORY": "martinslavov/rcas",
                    "ISSUE_URL": "https://github.com/martinslavov/rcas/issues/141",
                },
            )
            calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return result, calls

    def test_empty_token_warns_and_skips_gh(self):
        result, calls = self.run_step("")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("::warning::PROJECT_TOKEN is unavailable; skipping the RCAS Tracking board step.", result.stdout)
        self.assertEqual(calls, [])

    def test_nonempty_token_runs_existing_board_operations(self):
        result, calls = self.run_step("token")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("::warning::", result.stdout)
        self.assertEqual(len(calls), 4, calls)
        self.assertIn("user(login", calls[0])
        self.assertIn("projectV2(number: 1)", calls[0])
        self.assertEqual(calls[1], "api repos/martinslavov/rcas/issues/141 --jq .node_id")
        self.assertIn("addProjectV2ItemById", calls[2])
        self.assertIn("-f project=PROJ -f content=ISSUE_NODE", calls[2])
        self.assertIn("updateProjectV2ItemFieldValue", calls[3])
        self.assertIn("-f project=PROJ -f item=ITEM -f field=FIELD -f option=O2", calls[3])


if __name__ == "__main__":
    unittest.main()
