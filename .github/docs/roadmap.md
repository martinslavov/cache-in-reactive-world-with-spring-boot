# AI engineering roadmap

From an AI development workflow to an autonomous engineering system.

The foundation is in place: separate responsibilities for PO, Architect, Engineer, PR Review, QA and Definition of Done,
CI/CD checks, protection of `main`, retry limits and human intervention on problems. The next step is not more agents but
making the existing agents more **reliable, coordinated and measurable**, and able to work on many tasks without constant
supervision.

## Five levels

| # | Level | Goal | Status |
|---|-------|------|--------|
| 1 | Reliability and control | Protection against endless loops, repeated execution, stale results and unauthorized merges | In progress – EPIC #107 |
| 2 | Orchestration and parallel work | Task queue, dependencies, priorities, concurrent execution and recovery after interruption | Planned |
| 3 | Intelligent agents | Context-aware planning, selection of relevant tests, quality checks and automatic failure diagnosis | Planned |
| 4 | Observability and optimization | Metrics for success, Copilot cost, execution time, retries and code quality | Planned |
| 5 | Autonomous delivery | From backlog to a production-ready change, including release, rollback strategy and post-release monitoring | Planned |

Already available as groundwork: the Backlog/TODO queue (`.github/scripts/task_queue.sh`, level 2), the agent run records
and dashboard (level 4) and the elapsed-time records (level 4).

## Level 1 – Reliability and control: Workflow Orchestrator v1

Today the process is a combination of GitHub Actions, agent instructions, issue labels and PR statuses. As the number of
tasks grows, these components risk making conflicting decisions. Level 1 introduces one central mechanism that owns the
state of every task.

```text
Task intake / PO agent          issue, acceptance criteria, priority
        │
Workflow Orchestrator           state machine · queue · locks · retry policy
        │
Architect                       design, risks, approval gates
        │
Engineer                        branch, implementation, tests
        │
Quality gates                   Review → QA → DoD → Freshness check
        │
Merge                           only when every condition holds
        └─ Human review         on risk, conflict or exhausted limit
```

The orchestrator controls:

- which agent may work on the task right now;
- whether the previous stage finished successfully;
- whether the current result refers to the latest commit;
- whether the task is blocked by another task (dependencies are delivered in level 2);
- how many attempts were used and why they failed;
- whether human approval is required;
- whether an action was already performed, so it is not executed twice.

Architectural decision: no separate server for now. Version 1 is built with GitHub Actions, labels, issue/PR metadata and
small scripts and reusable workflows. A dedicated orchestrator becomes worthwhile when more complex scheduling, parallelism
or durable state across many runs is needed.

| Sub-issue | Scope |
|-----------|-------|
| #101 | Task state machine and state record (foundation) — In progress |
| #102 | Task locks: a single active agent per task |
| #103 | Idempotent action ledger |
| #104 | Freshness gate: reject stale results and stale branches |
| #105 | Merge Gate: one required check that authorizes merge |
| #106 | Unified retry policy |

## Deferred features (plan limitations)

The project runs on **GitHub Free and Copilot Free**. The following features need a paid Copilot plan (Pro / Pro+) or an
organization-owned repository and are deferred. They are tracked in the backlog issue #100; re-evaluate them when the plan
changes.

| # | Feature | Needs | Current workaround |
|---|---------|-------|--------------------|
| 1 | Copilot cloud agent: async task execution in GitHub (#99) | Copilot Pro / Pro+ | Local Copilot session processes the TODO queue |
| 2 | Agent gates (PR Review, QA, DoD) run by Copilot CLI in GitHub Actions | Copilot Pro / Pro+ and a `Copilot Requests` token | Gates run in the local session |
| 3 | Automatic Copilot code review on PRs | Paid Copilot plan | `pr-review-agent` |
| 4 | Parallel agent sessions and premium models | Larger premium-request quota (Pro+) | One task at a time |
| 5 | Merge queue (re-test against the latest `main` before merge) | Organization-owned repository | Freshness gate (#104) |
| 6 | Dedicated orchestrator service | Not a plan limit; needed only at higher scale | Orchestrator v1 on GitHub Actions (#107) |
