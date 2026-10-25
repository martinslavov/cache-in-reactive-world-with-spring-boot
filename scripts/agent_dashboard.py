#!/usr/bin/env python3
"""Build and publish the repository's agent-run dashboard using only Python's stdlib."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import statistics
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable

API_ROOT = "https://api.github.com"
DASHBOARD_TITLE = "Agent Workflow Dashboard"
DASHBOARD_MARKER = "<!-- agent-dashboard -->"
AGENTS = ("po", "implementation", "tests", "infrastructure")
STATUSES = {"success", "failure", "skipped", "escalated"}
FAILURE_SOURCES = set(AGENTS)
RECORD_MARKER = re.compile(r"(?m)^\s*<!--\s*agent-run:\s*([^\r\n]*?)\s*-->\s*$")
RECORD_LINE = re.compile(r"^\s*<!--\s*agent-run:", re.MULTILINE)
QA_ROUND = re.compile(r"<!--\s*qa-round:(\d+)\s*-->")
CI_ATTEMPT = re.compile(r"<!--\s*ci-fix-attempt:(\d+)\s*-->")


@dataclass(frozen=True)
class RunRecord:
    agent: str
    issue: int
    pr: int | None
    sha: str | None
    start: str
    end: str
    duration_s: int
    checks_failed: tuple[str, ...]
    retries: int
    status: str
    failure_source: str | None

    @property
    def identity(self) -> tuple[Any, ...]:
        """Exact replay key; timestamps distinguish legitimate reruns without a run_id field."""
        return (self.agent, self.issue, self.pr, self.sha, self.start, self.end)


def _utc_timestamp(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be a UTC ISO-8601 timestamp ending in Z")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp") from error
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError(f"{field} must use UTC")
    return parsed


def validate_record(raw: Any) -> RunRecord:
    if not isinstance(raw, dict):
        raise ValueError("record must be a JSON object")
    required = {
        "v", "agent", "issue", "pr", "sha", "start", "end", "duration_s",
        "checks_failed", "retries", "status", "failure_source",
    }
    missing = required - raw.keys()
    if missing:
        raise ValueError("missing fields: " + ", ".join(sorted(missing)))
    if raw["v"] != 1:
        raise ValueError("unsupported schema version")
    if not isinstance(raw["agent"], str) or not raw["agent"].strip():
        raise ValueError("agent must be a non-empty string")
    if isinstance(raw["issue"], bool) or not isinstance(raw["issue"], int) or raw["issue"] < 1:
        raise ValueError("issue must be a positive integer")
    if raw["pr"] is not None and (isinstance(raw["pr"], bool) or not isinstance(raw["pr"], int) or raw["pr"] < 1):
        raise ValueError("pr must be a positive integer or null")
    if raw["sha"] is not None and (not isinstance(raw["sha"], str) or not raw["sha"].strip()):
        raise ValueError("sha must be a non-empty string or null")
    start = _utc_timestamp(raw["start"], "start")
    end = _utc_timestamp(raw["end"], "end")
    if end < start:
        raise ValueError("end must not be before start")
    duration = raw["duration_s"]
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
        raise ValueError("duration_s must be a non-negative integer")
    if abs((end - start).total_seconds() - duration) > 1:
        raise ValueError("duration_s must agree with start and end")
    checks = raw["checks_failed"]
    if not isinstance(checks, list) or any(not isinstance(check, str) or not check.strip() for check in checks):
        raise ValueError("checks_failed must be an array of non-empty strings")
    retries = raw["retries"]
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
        raise ValueError("retries must be a non-negative integer")
    status = raw["status"]
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError("status must be success, failure, skipped or escalated")
    source = raw["failure_source"]
    if source is not None and (not isinstance(source, str) or source not in FAILURE_SOURCES):
        raise ValueError("failure_source must be po, implementation, tests, infrastructure or null")
    if raw["status"] in {"failure", "escalated"} and source is None:
        raise ValueError("failure_source is required for failure and escalated records")
    if raw["status"] in {"success", "skipped"} and source is not None:
        raise ValueError("failure_source must be null for success and skipped records")
    return RunRecord(
        agent=raw["agent"].strip(), issue=raw["issue"], pr=raw["pr"], sha=raw["sha"],
        start=raw["start"], end=raw["end"], duration_s=duration,
        checks_failed=tuple(checks), retries=retries, status=raw["status"], failure_source=source,
    )


def parse_comments(comments: Iterable[dict[str, Any]], warn: Callable[[str], None] | None = None) -> list[RunRecord]:
    warning = warn or (lambda message: print(f"warning: {message}", file=sys.stderr))
    records: list[RunRecord] = []
    for comment in comments:
        body = comment.get("body") or ""
        if not RECORD_LINE.search(body):
            continue
        matches = RECORD_MARKER.findall(body)
        if not matches:
            warning(f"comment {comment.get('html_url', comment.get('id', 'unknown'))}: malformed agent-run marker")
            continue
        for payload in matches:
            try:
                records.append(validate_record(json.loads(payload)))
            except (json.JSONDecodeError, ValueError) as error:
                warning(f"comment {comment.get('html_url', comment.get('id', 'unknown'))}: skipped malformed agent-run record ({error})")
    seen: set[tuple[Any, ...]] = set()
    unique: list[RunRecord] = []
    for record in records:
        if record.identity not in seen:
            seen.add(record.identity)
            unique.append(record)
    return unique


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _round_count(comments: Iterable[dict[str, Any]], pattern: re.Pattern[str]) -> int:
    return len({int(value) for comment in comments for value in pattern.findall(comment.get("body") or "")})


def render_dashboard(
    records: Iterable[RunRecord], comments_by_number: dict[int, list[dict[str, Any]]],
    updated_at: dt.datetime | None = None,
) -> str:
    records = sorted(records, key=lambda record: (record.issue, record.end, record.agent, record.pr or 0))
    updated_at = updated_at or dt.datetime.now(dt.timezone.utc)
    if updated_at.tzinfo is None:
        raise ValueError("updated_at must be timezone-aware")
    updated_at = updated_at.astimezone(dt.timezone.utc)
    stamp = updated_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    grouped: dict[int, list[RunRecord]] = {}
    for record in records:
        grouped.setdefault(record.issue, []).append(record)

    lines = [DASHBOARD_MARKER, "# Agent Workflow Dashboard", "", f"Last updated: {stamp}", "",
             "## Tasks", "", "| Issue | PR | Agents run | Total duration | Retries | QA rounds | CI fix attempts | Final status |",
             "|---:|---:|---|---:|---:|---:|---:|---|"]
    if not grouped:
        lines.append("| — | — | — | 0s | 0 | 0 | 0 | no records |")
    for issue, task_records in sorted(grouped.items()):
        prs = sorted({record.pr for record in task_records if record.pr is not None})
        related_comments: list[dict[str, Any]] = list(comments_by_number.get(issue, []))
        for pr in prs:
            related_comments.extend(comments_by_number.get(pr, []))
        agent_counts: dict[str, int] = {}
        for record in task_records:
            agent_counts[record.agent] = agent_counts.get(record.agent, 0) + 1
        agents = ", ".join(f"{_escape(name)} ({count})" for name, count in sorted(agent_counts.items()))
        latest = max(task_records, key=lambda record: (record.end, record.agent))
        lines.append(
            f"| #{issue} | {', '.join(f'#{pr}' for pr in prs) or '—'} | {agents} | "
            f"{sum(record.duration_s for record in task_records)}s | {sum(record.retries for record in task_records)} | "
            f"{_round_count(related_comments, QA_ROUND)} | {_round_count(related_comments, CI_ATTEMPT)} | {latest.status} |"
        )

    lines.extend(["", "## Agents", "", "| Agent | Runs | Success rate | Average duration | Median duration | Retries |",
                  "|---|---:|---:|---:|---:|---:|"])
    by_agent: dict[str, list[RunRecord]] = {}
    for record in records:
        by_agent.setdefault(record.agent, []).append(record)
    if not by_agent:
        lines.append("| — | 0 | 0% | 0s | 0s | 0 |")
    for agent, agent_records in sorted(by_agent.items()):
        durations = [record.duration_s for record in agent_records]
        rate = 100 * sum(record.status == "success" for record in agent_records) / len(agent_records)
        lines.append(f"| {_escape(agent)} | {len(agent_records)} | {rate:.1f}% | {statistics.mean(durations):.1f}s | "
                     f"{statistics.median(durations):.1f}s | {sum(record.retries for record in agent_records)} |")

    lines.extend(["", "## Failure sources", "", "Percentages use only failure/escalation records with a classified source.", "",
                  "| Source | Count | Percentage |", "|---|---:|---:|"])
    failures = [record for record in records if record.status in {"failure", "escalated"} and record.failure_source]
    denominator = len(failures)
    counts = {source: sum(record.failure_source == source for record in failures) for source in AGENTS}
    for source, count in counts.items():
        lines.append(f"| {source} | {count} | {(100 * count / denominator if denominator else 0):.1f}% |")
    lines.append(f"| **Total classified failures** | {denominator} | {100.0 if denominator else 0.0:.1f}% |")
    return "\n".join(lines) + "\n"


def find_dashboard(issues: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """The dashboard is an issue (never a PR) whose body starts with the marker; quoting it elsewhere does not count.
    If duplicates exist, the oldest wins so every run converges on the same issue."""
    matches = [item for item in issues if "pull_request" not in item
               and (item.get("body") or "").lstrip().startswith(DASHBOARD_MARKER)]
    return min(matches, key=lambda item: item.get("number", 0), default=None)


class GitHubClient:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, url: str, payload: Any = None) -> tuple[Any, dict[str, str]]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "rcas-agent-dashboard",
            "Content-Type": "application/json",
        })
        try:
            context = ssl.create_default_context()
            if sys.platform == "darwin" and not os.environ.get("SSL_CERT_FILE") and os.path.exists("/etc/ssl/cert.pem"):
                context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                raw = response.read()
                return (json.loads(raw) if raw else None), dict(response.headers.items())
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {urllib.parse.urlparse(url).path} failed ({error.code}): {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"GitHub API request failed: {error.reason}") from error

    def get_all(self, url: str) -> list[Any]:
        results: list[Any] = []
        while url:
            page, headers = self.request("GET", url)
            if not isinstance(page, list):
                raise RuntimeError("GitHub API returned an unexpected paginated response")
            results.extend(page)
            link = headers.get("Link", "")
            next_link = re.search(r'<([^>]+)>;\s*rel="next"', link)
            url = next_link.group(1) if next_link else ""
        return results

    def publish(self, repo: str, issues: list[dict[str, Any]], body: str) -> str:
        dashboard = find_dashboard(issues)
        if dashboard is None:
            dashboard, _ = self.request("POST", f"{API_ROOT}/repos/{repo}/issues", {
                "title": DASHBOARD_TITLE, "body": body,
            })
            action = "created"
        else:
            updates: dict[str, Any] = {"body": body}
            if dashboard.get("state") != "open":
                updates["state"] = "open"
            dashboard, _ = self.request("PATCH", dashboard["url"], updates)
            action = "updated"
        self.pin_if_possible(dashboard)
        return f"Dashboard issue {action}: {dashboard['html_url']}"

    def pin_if_possible(self, issue: dict[str, Any]) -> None:
        try:
            data, _ = self.request("POST", f"{API_ROOT}/graphql", {
                "query": "query($id: ID!) { node(id: $id) { ... on Issue { isPinned } } }",
                "variables": {"id": issue["node_id"]},
            })
            if data.get("errors"):
                raise RuntimeError("GraphQL rejected pin status query")
            pinned = data["data"]["node"]["isPinned"]
            if not pinned:
                result, _ = self.request("POST", f"{API_ROOT}/graphql", {
                    "query": "mutation($id: ID!) { pinIssue(input: {issueId: $id}) { issue { id } } }",
                    "variables": {"id": issue["node_id"]},
                })
                if result.get("errors"):
                    raise RuntimeError("GraphQL rejected issue pin mutation")
        except (RuntimeError, KeyError, TypeError) as error:
            print(f"warning: could not pin dashboard issue automatically; owner pin may be required: {error}", file=sys.stderr)


def collect(repo: str, client: GitHubClient) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    issues = client.get_all(f"{API_ROOT}/repos/{repo}/issues?state=all&per_page=100")
    comments: dict[int, list[dict[str, Any]]] = {}
    for issue in issues:
        number = issue["number"]
        comments[number] = client.get_all(f"{API_ROOT}/repos/{repo}/issues/{number}/comments?per_page=100")
    return issues, comments


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repository")
    parser.add_argument("--dry-run", action="store_true", help="print the rendered dashboard without writing")
    args = parser.parse_args(argv)
    if not args.repo or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo or GITHUB_REPOSITORY must be owner/repository")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("GH_TOKEN or GITHUB_TOKEN is required to read repository comments")
    try:
        client = GitHubClient(token)
        issues, comments = collect(args.repo, client)
        records = parse_comments(comment for item in comments.values() for comment in item)
        body = render_dashboard(records, comments)
        if args.dry_run:
            print(body, end="")
        else:
            print(client.publish(args.repo, issues, body))
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
