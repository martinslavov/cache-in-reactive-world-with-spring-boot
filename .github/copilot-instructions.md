# Task workflow rules

These rules apply when a task starts with a first line `TASK-NAME:<task-name>` (for example `TASK-NAME:code-review-agent` or `TASK-NAME:Code review agent`).
Tasks without that line are handled normally, without creating an issue, branch or PR.

## Agents

Three custom agents (in `.github/agents/`) do the work:

- `product-owner-agent`: Senior Product Owner, analyzes the task and creates the issue.
- `senior-java-software-engineer`: Senior Java Software Engineer, implements the issue and opens the PR.
- `senior-qa-engineer`: Senior QA Engineer, reviews and tests the PR and sets the `QA Agent` commit status.

When a task has the `TASK-NAME:` line, run them one after the other (the main agent only coordinates):

1. Delegate the whole input to `product-owner-agent`. It returns the issue number, URL and the branch name.
2. Delegate the issue (number, branch name and the original input) to `senior-java-software-engineer`. It implements the
   task, opens the PR and sets the commit status `QA Agent` to `pending` on the PR head SHA.
3. Delegate the PR number to `senior-qa-engineer`. It reviews the diff, runs the checks and sets `QA Agent` on the head SHA to
   `success` or `failure` (it must always set a final status). On `failure` it reports bugs to the engineer, who fixes them,
   pushes, sets `QA Agent` to `pending` again and hands over to QA again.
4. Report the issue and PR links, the merge status and the total elapsed time (see "Elapsed time" below) to the user. The engineer agent merges the PR by default once all checks,
   including `QA Agent`, pass and there are no comments (see the agent file); do not merge if the task says to keep the PR open (e.g. "leave the PR open", "do not merge").

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
   The `PR Issue Tracking` workflow adds the tracking issue link to the description.
   Required checks (unit, component and sanity tests and `QA Agent`) must pass before merging.
   Right after opening the PR, and after every new push, the engineer sets the QA gate to pending:
   `gh api -X POST repos/martinslavov/rcas/statuses/<head-sha> -f state=pending -f context="QA Agent" -f description="Waiting for QA"`
   (head SHA: `gh pr view <n> -R martinslavov/rcas --json headRefOid -q .headRefOid`). The QA agent then sets the same context
   to `success` (QA passed) or `failure` (with the reason) using `-f state=success|failure`.
5. **Merge (default).** Wait for all checks, then read the PR comments and reviews, ignoring automation (the `<!-- pr-tracking-link -->`
   tracking issue comment and `github-actions` bot). If all checks pass, including `QA Agent` = success, and there are no other comments, merge with
   `gh pr merge <n> -R martinslavov/rcas --merge --delete-branch`; this closes the task issue (`Closes #N`) and the tracking issue and
   moves the board item to Done. If a check fails, fix it; if checks are pending/unknown or there are comments, do not merge and report.
   If the task says to keep the PR open (e.g. "leave the PR open", "do not merge"), do not merge.

Commit messages end with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

## Elapsed time (every task)

At the very beginning of every task the main (orchestrating) agent records the start time with `date +%s` (the moment it receives the user's input).
At the end, after everything is merged and all agents are done, it runs `date +%s` again and the final report to the user MUST state the total
elapsed time (end minus start, as minutes and seconds) from the user's input until everything is merged and all agents have finished.
Sub-agents report their own durations to the main agent when asked; the total is always computed by the main agent.
