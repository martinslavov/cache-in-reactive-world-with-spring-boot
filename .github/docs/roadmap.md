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

## Improvement tasks

The roadmap is delivered as five improvement tasks. Each task is one EPIC (label `epic`) with sub-issues in `Backlog`;
parts that the current plan cannot support become `requires-pro` backlog issues listed in
[`pro-plan.md`](pro-plan.md).

| Task | Scope | EPIC | Status |
|------|-------|------|--------|
| 1 | Central Workflow Orchestrator (level 1) | #107 | In progress |
| 2 | P0 – fix critical risks in the current process (level 1) | #119 | In progress |
| 3 | Planned | – | Planned |
| 4 | Planned | – | Planned |
| 5 | Planned | – | Planned |

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

Migrating in-flight tasks to later states is out of scope for #101: its `init` seeds only `backlog` or `todo`, and later
states are reached only through validated transitions. A verified migration is a separate, human-performed rollout step
to be designed later (for example, as part of the remaining EPIC #107 work).

## Task 2 – P0: fix critical risks in the current process

Fix the critical risks before adding new agents (EPIC #119).

| Item | Scope | Sub-issue | Plan |
|------|-------|-----------|------|
| 2.1 | Bind every gate result to a commit SHA (`reviewed_sha` / `tested_sha`, compare-and-set before `success`) | #115 | Free |
| 2.2 | Idempotent automations: stable run key `repo#issue:stage:sha`, upsert, re-run audit | #116 | Free |
| 2.3 | Separate agent attestations from real CI: CI checks bound to GitHub Actions, no self-attestation | #117 | Free |
| 2.4 | Least privilege: job-level permissions, SHA-pinned actions, Dependabot, token scopes, fork PRs (see [security.md](security.md)) | #118 | Free |
| 2.3 / 2.4 | Agent statuses only from a trusted workflow, separate identity per agent | #114 | `requires-pro` |

Overlaps with EPIC #107: #104 keeps the pending reset on push and the branch-behind-main check, #105 enforces 2.1 and 2.3
at merge time, and #103 stays the orchestrator-level ledger while 2.2 covers workflows, scripts and agent reports.

## Deferred features (plan limitations)

The full list of work deferred until a paid plan, with order and prerequisites, is in [`pro-plan.md`](pro-plan.md).


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
