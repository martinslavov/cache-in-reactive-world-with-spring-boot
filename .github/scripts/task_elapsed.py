#!/usr/bin/env python3
"""Record a task's elapsed time on its issue and PR.

Upserts an "Elapsed time" block at the top of the issue and PR descriptions and one
`<!-- task-elapsed -->` comment on each. Re-running replaces both instead of duplicating.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

COMMENT_MARKER = "<!-- task-elapsed -->"
BLOCK_BEGIN = "<!-- task-elapsed:begin -->"
BLOCK_END = "<!-- task-elapsed:end -->"
BLOCK_RE = re.compile(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END) + r"\n*", re.DOTALL)
USAGE = "Usage: post_task_elapsed.sh <issue> <pr> <start-epoch> [end-epoch]"


def utc(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def summary(issue: int, pr: int, start: int, end: int) -> str:
    elapsed = end - start
    return (
        f"**Task elapsed time:** {elapsed // 60} min {elapsed % 60} s ({elapsed} s)\n\n"
        "| Start (user input) | End (merged, all agents done) | Issue | PR |\n"
        "|---|---|---|---|\n"
        f"| {utc(start)} | {utc(end)} | #{issue} | #{pr} |"
    )


def comment_body(text: str) -> str:
    return f"{COMMENT_MARKER}\n{text}"


def upsert_block(body: str | None, text: str) -> str:
    """Put the elapsed block at the top of a description, replacing an existing one."""
    block = f"{BLOCK_BEGIN}\n> [!NOTE]\n> {text.replace(chr(10), chr(10) + '> ')}\n{BLOCK_END}\n\n"
    rest = BLOCK_RE.sub("", body or "", count=1).lstrip("\n")
    return (block + rest).rstrip("\n") + "\n"


def parse_args(argv: list[str]) -> tuple[int, int, int, int]:
    if len(argv) not in (3, 4):
        raise ValueError(USAGE)
    issue, pr = argv[0], argv[1]
    for value in (issue, pr):
        if not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError("Issue and PR must be positive integers")
    epochs = argv[2:] if len(argv) == 4 else [argv[2], str(int(time.time()))]
    for value in epochs:
        if not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Epochs must be non-negative integers")
    start, end = int(epochs[0]), int(epochs[1])
    if end < start:
        raise ValueError("end-epoch is before start-epoch")
    return int(issue), int(pr), start, end


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def patch_body(path: str, body: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump({"body": body}, handle)
    try:
        gh("api", "-X", "PATCH", path, "--input", handle.name, "--jq", ".html_url")
    finally:
        os.unlink(handle.name)


def main(argv: list[str]) -> int:
    try:
        issue, pr, start, end = parse_args(argv)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    repo = os.environ.get("RCAS_REPO", "martinslavov/rcas")
    text = summary(issue, pr, start, end)

    # Resolve both targets before writing so an invalid one leaves nothing half-updated.
    pr_body = json.loads(gh("api", f"repos/{repo}/pulls/{pr}", "--jq", "{body}"))["body"]
    issue_body = json.loads(gh("api", f"repos/{repo}/issues/{issue}", "--jq", "{body}"))["body"]

    patch_body(f"repos/{repo}/issues/{issue}", upsert_block(issue_body, text))
    patch_body(f"repos/{repo}/pulls/{pr}", upsert_block(pr_body, text))

    for number in (issue, pr):
        existing = gh(
            "api", f"repos/{repo}/issues/{number}/comments", "--paginate",
            "--jq", f'[.[] | select(.body | startswith("{COMMENT_MARKER}"))][0].id // empty',
        ).split()
        if existing:
            url = gh("api", "-X", "PATCH", f"repos/{repo}/issues/comments/{existing[0]}",
                     "-f", f"body={comment_body(text)}", "--jq", ".html_url")
        else:
            url = gh("api", "-X", "POST", f"repos/{repo}/issues/{number}/comments",
                     "-f", f"body={comment_body(text)}", "--jq", ".html_url")
        print(url.strip())
    print(f"https://github.com/{repo}/issues/{issue} and /pull/{pr}: description updated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
