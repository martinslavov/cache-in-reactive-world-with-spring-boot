#!/usr/bin/env python3
"""Release tag helper for ci-tag.yml.

next   --labels <comma-separated PR labels>  < tags   prints the next vX.Y.Z tag
prune  --keep <n>                            < tags   prints the tags to delete (all but the n newest)
newest                                       < tags   prints the newest vX.Y.Z tag (empty if none)
existing --sha <commit>                      < refs   prints the newest vX.Y.Z tag for that commit

Tags are read from stdin, one per line; existing expects lines formatted as "tag commit-sha".
Anything that is not a plain vX.Y.Z tag is ignored.
"""
from __future__ import annotations

import argparse
import re
import sys

TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
FIRST_TAG = "v0.1.0"


def parse(tag: str) -> tuple[int, int, int] | None:
    match = TAG_RE.match(tag.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def release_tags(tags: list[str]) -> list[str]:
    """Valid vX.Y.Z tags, newest first."""
    valid = {tag.strip() for tag in tags if parse(tag)}
    return sorted(valid, key=parse, reverse=True)


def bump(labels: set[str]) -> str:
    if "major" in labels:
        return "major"
    if "enhancement" in labels:
        return "minor"
    return "patch"


def next_tag(tags: list[str], labels: set[str]) -> str:
    existing = release_tags(tags)
    if not existing:
        return FIRST_TAG
    major, minor, patch = parse(existing[0])
    kind = bump(labels)
    if kind == "major":
        return f"v{major + 1}.0.0"
    if kind == "minor":
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def tags_to_prune(tags: list[str], keep: int) -> list[str]:
    if keep < 1:
        raise ValueError("keep must be at least 1")
    return release_tags(tags)[keep:]


def tag_for_commit(refs: list[str], sha: str) -> str:
    matches = []
    for ref in refs:
        parts = ref.strip().split()
        if len(parts) == 2 and parts[1] == sha and parse(parts[0]):
            matches.append(parts[0])
    existing = release_tags(matches)
    return existing[0] if existing else ""


def main(argv: list[str], stdin=sys.stdin, stdout=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="release_tag.py")
    sub = parser.add_subparsers(dest="command", required=True)
    nxt = sub.add_parser("next")
    nxt.add_argument("--labels", default="")
    prune = sub.add_parser("prune")
    prune.add_argument("--keep", type=int, required=True)
    sub.add_parser("newest")
    existing = sub.add_parser("existing")
    existing.add_argument("--sha", required=True)
    args = parser.parse_args(argv)

    tags = stdin.read().splitlines()
    if args.command == "next":
        labels = {label.strip() for label in args.labels.split(",") if label.strip()}
        print(next_tag(tags, labels), file=stdout)
        return 0
    if args.command == "newest":
        existing = release_tags(tags)
        if existing:
            print(existing[0], file=stdout)
        return 0
    if args.command == "existing":
        tag = tag_for_commit(tags, args.sha)
        if tag:
            print(tag, file=stdout)
        return 0
    try:
        for tag in tags_to_prune(tags, args.keep):
            print(tag, file=stdout)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
