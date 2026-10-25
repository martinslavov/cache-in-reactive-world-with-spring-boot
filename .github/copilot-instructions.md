# Task workflow rules

These rules apply when a task starts with a first line `TASK-NAME:<task-name>` (for example `TASK-NAME:code-review-agent` or `TASK-NAME:Code review agent`).
Tasks without that line are handled normally, without creating an issue, branch or PR.

## Agents

Two custom agents (in `.github/agents/`) do the work:

- `product-owner-agent`: Senior Product Owner, analyzes the task and creates the issue.
- `senior-java-software-engineer`: Senior Java Software Engineer, implements the issue and opens the PR.

When a task has the `TASK-NAME:` line, run them one after the other (the main agent only coordinates):

1. Delegate the whole input to `product-owner-agent`. It returns the issue number, URL and the branch name.
2. Delegate the issue (number, branch name and the original input) to `senior-java-software-engineer`. It implements the
   task and opens the PR.
3. Report the issue and PR links and the merge status to the user. The engineer agent merges the PR by default once all checks
   pass and there are no comments (see the agent file); do not merge if the task says to keep the PR open (e.g. "leave the PR open", "do not merge").

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
   Required checks (unit, component and sanity tests) must pass before merging.
5. **Merge (default).** Wait for all checks, then read the PR comments and reviews, ignoring automation (the `<!-- pr-tracking-link -->`
   tracking issue comment and `github-actions` bot). If all checks pass and there are no other comments, merge with
   `gh pr merge <n> -R martinslavov/rcas --merge --delete-branch`; this closes the task issue (`Closes #N`) and the tracking issue and
   moves the board item to Done. If a check fails, fix it; if checks are pending/unknown or there are comments, do not merge and report.
   If the task says to keep the PR open (e.g. "leave the PR open", "do not merge"), do not merge.

Commit messages end with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
