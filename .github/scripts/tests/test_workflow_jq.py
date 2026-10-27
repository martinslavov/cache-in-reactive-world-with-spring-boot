"""Runs every gh `--jq` / `-q` filter of the release workflows through the real jq binary.

The mocked gh used by test_workflow_behavior does not evaluate filters, so a syntactically valid but
semantically wrong filter (e.g. a pipe binding over a comma) would only fail in GitHub Actions.
"""

import json
import re
import shutil
import subprocess
import unittest

from tests.test_workflow_security import ROOT

RELEASE_WORKFLOWS = ("ci-tag.yml", "ci-release.yml")
JQ = shutil.which("jq")

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40

TAG_REFS_FILTER = '.[] | [(.ref | sub("^refs/tags/"; "")), .object.type, .object.sha] | @tsv'
OLD_TAG_REFS_FILTER = '.[] | [.ref | sub("^refs/tags/"; ""), .object.type, .object.sha] | @tsv'

# GET repos/{repo}/git/matching-refs/tags/v with one lightweight and one annotated tag.
MATCHING_REFS = [
    {"ref": "refs/tags/v0.1.0", "object": {"type": "commit", "sha": SHA_A}},
    {"ref": "refs/tags/v0.2.0", "object": {"type": "tag", "sha": SHA_B}},
]
# GET repos/{repo}/releases (one page).
RELEASES = [
    {"id": 3, "tag_name": "v0.3.0-rc.1", "draft": False, "prerelease": True},
    {"id": 2, "tag_name": "v0.2.0", "draft": False, "prerelease": False},
    {"id": 4, "tag_name": "v0.4.0", "draft": True, "prerelease": False},
    {"id": 1, "tag_name": "v0.1.0", "draft": False, "prerelease": False},
]

# filter -> [(API payload, expected stdout of `jq -r <filter>`)]; gh --jq prints strings raw like jq -r.
CASES = {
    TAG_REFS_FILTER: [
        (MATCHING_REFS, f"v0.1.0\tcommit\t{SHA_A}\nv0.2.0\ttag\t{SHA_B}\n"),
        ([], ""),
    ],
    # GET repos/{repo}/git/tags/{sha} for an annotated tag.
    "[.object.type, .object.sha] | @tsv": [
        ({"sha": SHA_B, "tag": "v0.2.0", "object": {"type": "commit", "sha": SHA_C}}, f"commit\t{SHA_C}\n"),
    ],
    # GET repos/{repo}/commits/{sha}.
    ".sha": [({"sha": SHA_A, "commit": {"message": "m"}}, f"{SHA_A}\n")],
    # POST repos/{repo}/git/refs.
    ".ref": [({"ref": "refs/tags/v0.2.0", "object": {"type": "commit", "sha": SHA_A}}, "refs/tags/v0.2.0\n")],
    # POST repos/{repo}/releases/generate-notes.
    ".body": [({"name": "v0.2.0", "body": "## Changes\n- fix"}, "## Changes\n- fix\n")],
    ".[] | select(.draft == false and .prerelease == false) | .tag_name": [
        (RELEASES, "v0.2.0\nv0.1.0\n"),
        ([], ""),
    ],
    ".[] | [.tag_name, (.id | tostring)] | @tsv": [
        (RELEASES, "v0.3.0-rc.1\t3\nv0.2.0\t2\nv0.4.0\t4\nv0.1.0\t1\n"),
        ([], ""),
    ],
    '.[].ref | sub("^refs/tags/"; "")': [
        (MATCHING_REFS, "v0.1.0\nv0.2.0\n"),
        ([], ""),
    ],
}

_FLAG = re.compile(r"""(?<![\w-])(?:--jq|-q)\s+(?:'([^']*)'|"([^"]*)"|([^\s'";|)]+))""")


def extract_filters(text):
    """Returns the filters passed to gh via --jq/-q, joining backslash-continued shell lines."""
    filters = []
    for line in re.sub(r"\\\n\s*", " ", text).splitlines():
        for match in _FLAG.finditer(line):
            prefix = line[: match.start()]
            gh = [m.end() for m in re.finditer(r"(?<![\w-])gh\s", prefix)]
            if gh and "grep" not in prefix[gh[-1]:]:
                filters.append(next(group for group in match.groups() if group is not None))
    return filters


def run_jq(jq_filter, payload):
    return subprocess.run(
        [JQ, "-r", jq_filter], input=json.dumps(payload), capture_output=True, text=True, check=False
    )


def workflow_filters():
    return {name: extract_filters((ROOT / "workflows" / name).read_text()) for name in RELEASE_WORKFLOWS}


class WorkflowJqFilterExtractionTest(unittest.TestCase):
    def test_extracts_quoted_and_bare_gh_filters_but_not_grep_quiet(self):
        text = (
            'refs=$(gh api "x" --paginate \\\n            --jq \'.[] | .ref\')\n'
            "gh api -X POST y --jq .body > notes\n"
            "gh pr view 1 -q '.number'\n"
            "elif grep -q 'HTTP 404' err; then\n"
        )

        self.assertEqual(extract_filters(text), [".[] | .ref", ".body", ".number"])

    def test_every_release_workflow_filter_has_jq_cases(self):
        for name, filters in workflow_filters().items():
            with self.subTest(workflow=name):
                self.assertTrue(filters, f"no gh --jq filters found in {name}")
                missing = sorted(set(filters) - set(CASES))
                self.assertEqual(missing, [], f"{name}: add representative payloads to CASES for {missing}")

    def test_tag_workflow_uses_fixed_matching_refs_filter_in_both_jobs(self):
        filters = workflow_filters()["ci-tag.yml"]

        self.assertEqual(filters.count(TAG_REFS_FILTER), 2)
        self.assertNotIn(OLD_TAG_REFS_FILTER, filters)


@unittest.skipUnless(JQ, "jq binary not available")
class WorkflowJqFilterExecutionTest(unittest.TestCase):
    def test_release_workflow_filters_produce_expected_output_with_real_jq(self):
        for name, filters in workflow_filters().items():
            for jq_filter in dict.fromkeys(filters):
                for index, (payload, expected) in enumerate(CASES.get(jq_filter, [])):
                    with self.subTest(workflow=name, filter=jq_filter, case=index):
                        result = run_jq(jq_filter, payload)

                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, expected)

    def test_old_matching_refs_filter_fails_on_existing_tags(self):
        result = run_jq(OLD_TAG_REFS_FILTER, MATCHING_REFS)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Cannot index string with string "object"', result.stderr)


if __name__ == "__main__":
    unittest.main()
