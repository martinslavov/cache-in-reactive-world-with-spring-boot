# Task workflow rules

These rules apply when a task starts with a first line `NAME:<task-name>` (for example `NAME:add-redis-metrics`).
Tasks without that line are handled normally, without creating an issue, branch or PR.

1. **Issue.** Create a GitHub issue for the task with `gh issue create` (title from the task name and a short description of the goal).
   The issue form is `.github/ISSUE_TEMPLATE/issue.yml`; the `CI Issue Board` workflow puts it on the board as `Assessment`.
2. **Branch.** Create the branch `feature/<task-name>` from an up to date `main` and work only there.
   `<task-name>` is the value after `NAME:`, lowercase, words separated by `-`. Only `feature/*` and `hotfix/*` branches can be created.
3. **Work.** Do the task. Commit the changes with clear messages. Never push to `main` directly.
4. **Pull request.** When done, push the branch and open a PR against `main` using `.github/pull_request_template.md`.
   Reference the issue from step 1 under "Pull-request relations" (`Related to: #N`).
   The `PR Issue Tracking` workflow adds the tracking issue link to the description.
   Required checks (unit, component and sanity tests) must pass before merging; do not merge unless asked.

Commit messages end with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
