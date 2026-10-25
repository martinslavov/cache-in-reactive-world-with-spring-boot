# Task workflow rules

These rules apply when a task starts with a first line `TASK-NAME:<task-name>` (for example `TASK-NAME:code-review-agent` or `TASK-NAME:Code review agent`).
Tasks without that line are handled normally, without creating an issue, branch or PR.

## Agents

Four custom agents (in `.github/agents/`) do the work:

- `product-owner-agent`: Senior Product Owner, analyzes the task and creates the issue.
- `senior-java-software-engineer`: Senior Java Software Engineer, implements the issue and opens the PR.
- `pr-review-agent`: independent PR Reviewer, reviews the complete diff, posts severity-ranked findings and sets `PR Review`.
- `senior-qa-engineer`: Senior QA Engineer, reviews and tests the PR and sets the `QA Agent` commit status.

When a task has the `TASK-NAME:` line, run them one after the other (the main agent only coordinates):

1. Delegate the whole input to `product-owner-agent`. It returns the issue number, URL and the branch name.
2. Delegate the issue (number, branch name and the original input) to `senior-java-software-engineer`. It implements the
   task, opens the PR, and immediately sets both `PR Review` and `QA Agent` to `pending` on the PR head SHA.
3. Delegate the PR number to `pr-review-agent`. It independently reads the issue and full diff, posts its findings, and always
   sets a final `PR Review` status on the current head SHA. On blocker/major findings, the engineer fixes them, pushes, resets both
   `PR Review` and `QA Agent` to `pending`, and hands the updated PR back to PR Review. The loop is bounded at five rounds; on a
   round-5 failure, the agent applies `needs-human-review` and escalates to the user. Only a human removing the label resumes it.
4. Only after `PR Review` is `success` on the current head SHA, delegate the PR number to `senior-qa-engineer`. QA reviews the
   change, runs the relevant checks and sets `QA Agent` on the head SHA to `success` or `failure` (it must always set a final
   status). On QA failures before round 5, the engineer fixes and pushes, resets both statuses to `pending`, and hands over to PR
   Review first, then QA after PR Review succeeds. QA round-5 failure has the same human-review stop and resumption semantics.
5. Report the issue and PR links, merge status and total elapsed time (see "Elapsed time" below). The engineer merges by default
   only when all required checks pass, both `PR Review` and `QA Agent` are `success` on the current head SHA, `needs-human-review`
   is absent, and no human comments or unresolved blocker/major findings remain. Resolved findings do not block after the relevant current-head
   status succeeds. Do not merge if the user asks to keep the PR open.

The steps below are what the agents follow:

1. **Issue.** Create a GitHub issue for the task with `gh issue create` (title from the task name, written as readable text and a short description of the goal).
   The issue form is `.github/ISSUE_TEMPLATE/issue.yml`; the `CI Issue Board` workflow puts it on the board as `Assessment`.
2. **Branch.** Create the branch `feature/<task-name>` from an up to date `main` and work only there.
   If the value after `TASK-NAME:` is already a slug (lowercase, words separated by `-`), use it as is. Otherwise (free text such as `Code review agent`),
   derive a short, meaningful slug yourself: lowercase, ASCII letters, digits and `-` only, fixing obvious typos, e.g. `feature/code-review-agent`.
   Only `feature/*` and `hotfix/*` branches can be created.
3. **Work.** Do the task. Commit the changes with clear messages. Never push to `main` directly.
4. **Pull request.** When done, push the branch and open a PR against `main` using `.github/pull_request_template.md`.
   Reference the issue from step 1 under "Pull-request relations" as `Closes #N`: GitHub closes it on merge and `PR Issue Close` moves it to Done.
   The `PR Issue Tracking` workflow adds the tracking issue link to the description. Required checks (unit, component and sanity tests and
   both agent statuses) must pass before merging. Right after opening the PR, and after every new push, the engineer sets both agent
   gates to pending:
   `gh api -X POST repos/martinslavov/rcas/statuses/<head-sha> -f state=pending -f context="PR Review" -f description="Waiting for PR review"`
   `gh api -X POST repos/martinslavov/rcas/statuses/<head-sha> -f state=pending -f context="QA Agent" -f description="Waiting for QA"`
   (head SHA: `gh pr view <n> -R martinslavov/rcas --json headRefOid -q .headRefOid`). PR Review runs before QA.
   On blocker/major findings, the engineer fixes, pushes, resets both statuses to pending and hands back to PR Review. Minor/nit
   findings are reported but do not block QA. Count rounds from PR comments containing `<!-- pr-review-round:N -->`; on round 5
   failure apply `needs-human-review`, mention `@martinslavov`, and stop. Only a human removing the label resumes; retain all markers.
5. **Bounded PR Review loop.** Every PR Review report includes `<!-- pr-review-round:N -->`. Derive the round from all PR comments:
   `gh api repos/martinslavov/rcas/issues/<pr>/comments --paginate --slurp -q '[.[][] | select(.body | contains("<!-- pr-review-round:"))] | length'`
   Round = marker count + 1. Blocker/major findings fail the status; the engineer fixes and pushes, resets both statuses, then PR Review
   repeats before QA. Minor/nit findings do not block QA. On round 5 failure, apply `needs-human-review`, mention `@martinslavov`,
   and stop agent work. Only a human removing the label resumes the loop; retain markers and continue counting above round 5.
6. **Bounded QA loop.** Every QA failure report comment includes a hidden `<!-- qa-round:N -->` marker. QA derives the next round from the
   count of these markers on that PR (not agent memory; the count is per PR), using this exact command with `<pr>` replaced by the PR number:
   `gh api repos/martinslavov/rcas/issues/<pr>/comments --paginate -q '[.[] | select(.body | contains("<!-- qa-round:"))] | length'`.
   Below round 5, QA sets `QA Agent` to `failure` with actionable findings; the engineer fixes, pushes, resets both statuses and sends the PR through PR Review before QA retests. A human removing the label resumes this loop; thereafter, continue it for subsequent rounds, retaining all markers. On round 5 failure,
   QA sets failure with description `QA iteration limit (5) reached – human review required`, applies `needs-human-review`, and posts an
   escalation comment mentioning `@martinslavov` that summarizes open findings and the round count. Create the label if missing using:
   `gh label create needs-human-review -R martinslavov/rcas --color B60205 --description "QA iteration limit reached; human review required" 2>/dev/null || true`.
   Add it via `gh api -X POST repos/martinslavov/rcas/issues/<pr>/labels -f 'labels[]=needs-human-review'`; do not use `gh pr edit` because it
   fails with a Projects classic error. The engineer makes no further fix commits or merge while the label is present. Automated agents never
   remove it; only a human removing it explicitly resumes the loop. Existing round markers remain the source of truth after resumption.
7. **Merge (default).** Wait for all checks and both `PR Review` and `QA Agent` success on the current head SHA. Before any auto-merge, check the review label with
   `gh api repos/martinslavov/rcas/issues/<pr>/labels -q '.[].name | select(. == "needs-human-review")'`; if present, do not merge.
   Ignore tracking/workflow automation comments. Resolved QA findings do not by themselves block auto-merge after QA succeeds on the current
   head SHA; unresolved blocker/major findings and any human (non-agent/non-automation) comment continue to block it. If all checks pass, the label is absent,
   and no human comments or unresolved blocker/major findings remain, merge with `gh pr merge <n> -R martinslavov/rcas --merge --delete-branch`; this closes
   the task issue (`Closes #N`) and tracking issue and moves the board item to Done. If checks fail, are pending/unknown, the label is present,
   or status/comments cannot be determined, do not merge and report/escalate. Honor an explicit request to keep the PR open.

Commit messages end with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

### Required checks

The `Main protection` ruleset currently requires these status checks: `unit-tests`, `Component Tests (make up && make component-tests)`, `Sanity Tests (make up && make sanity-tests)`, `Static Review (checkstyle)`, `QA Agent`, `analyze` (CodeQL), `dependency-review` and `secret-scan`. `PR Review` is an additional workflow gate that must be `success` on the current head SHA before QA or merge; it is intentionally not yet in the ruleset. **No agent may merge unless every ruleset-required check and both agent statuses (`PR Review`, `QA Agent`) are successful on the current head SHA** (pending, skipped, unknown or failed means do not merge).
Check the current head SHA with `gh pr checks <n> -R martinslavov/rcas`. The unit-tests job also enforces the JaCoCo coverage minimums
(`./gradlew build`; report with `./gradlew jacocoTestReport`). Dependabot security-update PRs get no `QA Agent` status automatically:
they need the normal agent flow or a human.

### QA test scope and status

- A PR is docs-only only if every changed file matches `*.md`, `.github/agents/**`, `.github/copilot-instructions.md`, `.github/pull_request_template.md`, or `.github/ISSUE_TEMPLATE/**`. QA reviews the documentation and its consistency; tests are not required. Any other changed file means the PR is not docs-only.
- For any change under `src/**`, `component-tests/**`, or `config/**`, or to `build.gradle`, `settings.gradle`, `gradle/**`, `Dockerfile`, `docker-compose.yml`, `docker/**`, `Makefile`, `.github/workflows/**`, or `db.migration/**`, QA runs the relevant tests, at minimum `./gradlew build` with JDK 25.
- For runtime-affecting changes (application source or configuration, runtime dependencies or packaging, database migrations, or Docker/Compose runtime setup; including changes in `src/**`, `config/**`, `db.migration/**`, `Dockerfile`, `docker-compose.yml`, and `docker/**`), QA additionally runs `make build && make up && make component-tests && make sanity-tests && make down`.
- When in doubt, QA runs the tests.
- The `QA Agent` status description identifies the checks actually executed and their results, e.g. `docs-only review`, `build passed`, or `build+component+sanity passed`. It includes failures and never implies an unrun check passed.

## Elapsed time (every task)

At the very beginning of every task the main (orchestrating) agent records the start time with `date +%s` (the moment it receives the user's input).
At the end, after everything is merged and all agents are done, it runs `date +%s` again and the final report to the user MUST state the total
elapsed time (end minus start, as minutes and seconds) from the user's input until everything is merged and all agents have finished.
Sub-agents report their own durations to the main agent when asked; the total is always computed by the main agent.
