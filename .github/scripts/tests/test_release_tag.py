import io
import unittest
from contextlib import redirect_stderr

from release_tag import FIRST_TAG, main, next_tag, release_tags, tag_for_commit, tags_to_prune


class NextTagTest(unittest.TestCase):
    def test_first_tag_when_none_exist(self):
        self.assertEqual(next_tag([], set()), FIRST_TAG)
        self.assertEqual(next_tag(["latest", "v1", "v1.2"], {"major"}), FIRST_TAG)

    def test_patch_by_default(self):
        self.assertEqual(next_tag(["v0.1.0"], {"bug", "minor"}), "v0.1.1")
        self.assertEqual(next_tag(["v0.1.0"], {"documentation"}), "v0.1.1")

    def test_minor_for_enhancement(self):
        self.assertEqual(next_tag(["v0.1.3"], {"enhancement", "minor"}), "v0.2.0")

    def test_major_wins(self):
        self.assertEqual(next_tag(["v0.4.2"], {"enhancement", "major"}), "v1.0.0")

    def test_uses_semver_not_lexical_order(self):
        self.assertEqual(next_tag(["v0.9.0", "v0.10.0", "v0.2.0"], set()), "v0.10.1")


class PruneTest(unittest.TestCase):
    def test_keeps_two_newest(self):
        tags = ["v0.1.0", "v0.10.0", "v0.2.0", "v0.9.1", "other"]
        self.assertEqual(tags_to_prune(tags, 2), ["v0.2.0", "v0.1.0"])

    def test_nothing_to_prune(self):
        self.assertEqual(tags_to_prune(["v0.1.0", "v0.1.1"], 2), [])
        self.assertEqual(tags_to_prune([], 2), [])

    def test_ignores_invalid_and_duplicates(self):
        self.assertEqual(release_tags(["v1.0.0", "v1.0.0", "v01.0.0", "v1.0.0-rc1", " v2.0.0 "]), ["v2.0.0", "v1.0.0"])

    def test_keep_must_be_positive(self):
        with self.assertRaises(ValueError):
            tags_to_prune(["v1.0.0"], 0)


class ExistingTagTest(unittest.TestCase):
    def test_finds_newest_tag_for_commit(self):
        refs = ["v0.1.0 aa", "v0.2.0 bb", "v1.0.0 aa", "v1.1.0-rc1 aa"]
        self.assertEqual(tag_for_commit(refs, "aa"), "v1.0.0")

    def test_returns_empty_when_commit_is_untagged(self):
        self.assertEqual(tag_for_commit(["v1.0.0 aa"], "bb"), "")


class CliTest(unittest.TestCase):
    def run_cli(self, argv, stdin):
        out = io.StringIO()
        with redirect_stderr(io.StringIO()):
            code = main(argv, stdin=io.StringIO(stdin), stdout=out)
        return code, out.getvalue()

    def test_next(self):
        self.assertEqual(self.run_cli(["next", "--labels", "enhancement,minor"], "v0.1.0\n"), (0, "v0.2.0\n"))

    def test_prune(self):
        self.assertEqual(self.run_cli(["prune", "--keep", "2"], "v0.1.0\nv0.1.1\nv0.1.2\n"), (0, "v0.1.0\n"))

    def test_newest(self):
        self.assertEqual(self.run_cli(["newest"], "v0.9.0\nv0.10.0\nfoo\n"), (0, "v0.10.0\n"))
        self.assertEqual(self.run_cli(["newest"], ""), (0, ""))

    def test_existing(self):
        self.assertEqual(self.run_cli(["existing", "--sha", "aa"], "v1.0.0 aa\nv1.1.0 aa\n"), (0, "v1.1.0\n"))
        self.assertEqual(self.run_cli(["existing", "--sha", "bb"], "v1.0.0 aa\n"), (0, ""))

    def test_prune_rejects_zero(self):
        self.assertEqual(self.run_cli(["prune", "--keep", "0"], "v0.1.0\n")[0], 2)


if __name__ == "__main__":
    unittest.main()
