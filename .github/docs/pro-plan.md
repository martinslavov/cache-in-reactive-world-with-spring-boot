# Work deferred until a paid Copilot plan

The project runs on **GitHub Free and Copilot Free**. Everything below is blocked by the plan (or by the repository being
user-owned) and is implemented after upgrading to **Copilot Pro / Pro+**. Every item is an issue in `Backlog` with the
label `requires-pro`; when a roadmap task produces a new plan-limited item, it is added here.

## Issues

| Order | Issue | What | Why deferred | Prerequisites |
|-------|-------|------|--------------|---------------|
| 1 | #99 | Copilot cloud agent: assign an issue to Copilot and let it work asynchronously in GitHub | Cloud agent is not available on Copilot Free | Copilot Pro / Pro+ |
| 2 | #100 item 2 | Agent gates (PR Review, QA, DoD) run by Copilot CLI in GitHub Actions instead of the local session | Needs a Copilot token with premium requests in Actions | #99 |
| 3 | #114 | Trusted agent execution: agent statuses published only by a trusted workflow / GitHub App; separate least-privilege identity per agent and for merge/release; no self-attestation | Agents must run in Actions to have their own identity; today they all use the personal token (deferred part of task 2, items 2.3 and 2.4) | #99, #100 item 2 |
| 4 | #100 item 3 | Automatic Copilot code review on every PR as an extra reviewer | Paid Copilot feature | Copilot Pro / Pro+ |
| 5 | #100 item 4 | Parallel agent sessions and premium models | Copilot Free has a small premium-request quota | Copilot Pro+ (recommended) |
| 6 | #100 item 5 | Merge queue (re-test against the latest `main` before merge) | Needs an organization-owned repository (not a Copilot plan) | Move the repo to an organization |
| 7 | #100 item 6 | Dedicated orchestrator service | Not a plan limit; only at higher scale | Level 2 parallel work in production |

## After upgrading

1. Enable the cloud agent (#99) and verify it on one small `TODO` issue.
2. Move the agent gates to GitHub Actions (#100 item 2) and keep the local gates as a fallback until they are stable.
3. Implement #114: create a GitHub App, bind `PR Review`, `QA Agent` and `Definition of Done` to it in the ruleset and
   split the agent identities.
4. Turn on Copilot code review and parallel sessions (#100 items 3 and 4).
5. Re-evaluate items 6 and 7 and update this document and `.github/docs/roadmap.md` when an item is done or dropped.

## Free-plan workarounds in use

| Deferred item | Workaround now |
|---------------|----------------|
| #99 | The local Copilot session processes the `TODO` queue (`.github/scripts/task_queue.sh`) |
| #100 item 2, #114 | Gates run in the local session; results are bound to the commit SHA and checked for self-attestation (EPIC #119) |
| #100 item 3 | `pr-review-agent` |
| #100 item 4 | One task at a time |
| #100 item 5 | Freshness gate (#104) |
| #100 item 6 | Orchestrator v1 on GitHub Actions and scripts (#107) |
