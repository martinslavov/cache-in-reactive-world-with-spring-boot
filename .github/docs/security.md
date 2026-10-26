# Security and permissions

Least-privilege rules for workflows, tokens and agents (EPIC #119, task 2.4, issue #118).

## Workflow permissions

Every workflow sets `permissions: {}` at the top level; each job declares only the grants it needs.

| Workflow | Job | Job permissions | Secrets used |
|----------|-----|-----------------|--------------|
| `ci-unit-tests.yml` | `unit-tests` | `contents: read` | none |
| `ci-component-tests.yml` | `component-tests` | `contents: read` | `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` (login step only, before checkout) |
| `ci-sanity-tests.yml` | `sanity-tests` | `contents: read` | `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` (login step only, before checkout) |
| `ci-static-review.yml` | `static-review` | `contents: read` | none |
| `ci-secret-scan.yml` | `secret-scan` | `contents: read` | none |
| `ci-dependency-review.yml` | `dependency-review` | `contents: read` | none |
| `ci-code-review.yml` (CodeQL) | `analyze` | `contents: read`, `actions: read`, `security-events: write` | none |
| `ci-agent-dashboard.yml` | `update-dashboard` | `contents: read`, `pull-requests: read`, `issues: write` | none |
| `ci-pr-issue-tracking.yml` | `create-issue` | `contents: read`, `issues: write`, `pull-requests: write` | `PROJECT_TOKEN` (board step only) |
| `ci-pr-issue-close.yml` | `close-issue` | `contents: read`, `issues: write`, `pull-requests: read` | `PROJECT_TOKEN` (board step only) |
| `ci-issue-board.yml` | `add-to-board` | none (`permissions: {}`) | `PROJECT_TOKEN` |
| `ci-tag.yml` | `plan` | `contents: read`, `pull-requests: read` | `GITHUB_TOKEN` (read-only; checks out and runs the release helper) |
| `ci-tag.yml` | `tag` | `contents: write` | `GITHUB_TOKEN` (create tag; no checkout, runs no repository code) |
| `ci-release.yml` | `release`, `prune` | `contents: write` | `GITHUB_TOKEN` (create release and delete old releases/tags) |

`ci-tag.yml` writes a tag only for a merged PR targeting `main`; the push fallback verifies that the commit is associated
with a merged PR from a fork. It does not execute PR code. Privilege is separated: the read-only `plan` job looks up the PR and calculates the tag with the checked-out helper, while the `contents: write` `tag` job does not check out the repository or run repository scripts. It treats the plan outputs as untrusted: the tag must match strict stable SemVer `^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`, the bump must be `major`, `minor` or `patch`, and the commit (taken from the event context, never from a job output) must be a 40-hex SHA that exists in the repository. It recomputes the version from the live tags on each attempt, so a plan that raced or went stale cannot allocate a wrong or duplicate version, and returns the existing tag when the commit is already tagged. The mutating jobs (`ci-tag.yml` `tag`, `ci-release.yml` `release` and `prune`) use one job-level concurrency group
`release-tag` with `queue: max` and no cancellation, so automatic and manual tag-push releases are serialized in FIFO
order and pending jobs are not replaced; there is no workflow-level group, so the reusable call cannot block its caller; the ref creation retries against the latest tags to handle simultaneous version
allocation. The reusable release workflow checks out the selected tag, builds/tests it, creates the release with the
jar, and prunes only strict stable `vX.Y.Z` tags/releases. The tag job dereferences annotated Git tags before checking
whether the merge commit already has a tag.

Checkout steps use `persist-credentials: false`, so the job token is not left in `.git/config` while build and test
code runs. `pull_request_target` and `workflow_run` are not used; do not add them without a separate security review,
because they run with secrets and a write token.

### Docker registry credential boundary

`docker/login-action` stores the registry credential in the runner Docker config (`~/.docker/config.json`), where
any later step could read it; `persist-credentials: false` does not affect it. Component and sanity tests therefore
keep the credential away from PR-controlled code:

1. Log in to `dhi.io` (only when the secrets are available).
2. Pull the fixed image list in `DHI_IMAGES`, defined in the workflow file itself (not read from the Dockerfile or
   any other PR file); keep it in sync with the Dockerfile `FROM` lines (enforced by `test_workflow_security.py`).
3. `docker logout dhi.io` (`if: always()`), then fail the job if `dhi.io` is still listed under `auths` or
   `credHelpers` in the Docker config.
4. Only then check out the repository and run `make build`, `make up` and the tests. `make up` builds the image
   without `--pull` and the compose `build:` has no `pull: true`, so the cached base image is reused without registry
   auth. PostgreSQL and Redis are public Docker Hub images pulled anonymously.

No PR-controlled code (make, gradle, scripts, compose) runs while the credential is stored. The workflow file itself is
still part of a same-repository PR, so changes to these steps need review like any other secret-handling change.

## SHA pinning and Dependabot

- Every `uses:` reference is pinned to a full 40-character commit SHA with the release tag as a trailing comment,
  e.g. `actions/checkout@<sha> # v7.0.1`. Tags are mutable, SHAs are not.
- `.github/dependabot.yml` enables the `github-actions` ecosystem (directory `/`, weekly), so Dependabot opens PRs that
  bump the SHA and the version comment. Review these PRs like code changes (release notes, new permissions).
- Resolve a SHA with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>`; for an annotated tag (`type: tag`) dereference
  it with `gh api repos/<owner>/<repo>/git/tags/<sha>` and use the commit SHA.

## Fork pull requests

Workflows triggered by `pull_request` from a fork get a read-only token and no repository secrets.

- Nothing runs PR code with secrets or a write token (no `pull_request_target` / `workflow_run`).
- Component and sanity tests check whether the Docker Hub secrets exist and skip only the login and base-image
  pull steps when they do not; the build, `make up` and the tests still run (a missing login is never a reason to skip
  tests). Hardened-image (`dhi.io`) pulls may fail without credentials; the job then fails visibly instead of passing.
- Dependabot PRs get Dependabot secrets, not Actions secrets; the same rule applies.
- PR Issue Tracking cannot create issues for fork PRs (read-only token).

## Token scopes

| Secret | Used by | Minimum scope |
|--------|---------|---------------|
| `PROJECT_TOKEN` | `ci-issue-board.yml`, `ci-pr-issue-tracking.yml`, `ci-pr-issue-close.yml` (GraphQL: read the user project `RCAS Tracking`, add items, update the `Status` field) | Fine-grained personal access token owned by the project owner, **user permission "Projects": read and write**; no repository permissions are needed because issue and PR access comes from the job `GITHUB_TOKEN`. Set a short expiry and rotate. |
| `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` | `ci-component-tests.yml`, `ci-sanity-tests.yml` (login to `dhi.io` to pull hardened images) | Docker Hub access token with **read-only (public repo read)** permission. Never a password or a read/write token. |
| `GITHUB_TOKEN` | all workflows | Per job, see the table above. |

Secrets are exposed only to the step that needs them, never at workflow or job level.

## Agent permissions

Agents run locally under the user's `gh` identity; `tools:` in `.github/agents/*.agent.md` limits the editor tooling,
it does not replace GitHub authorization. Separate identities per agent are deferred (#114, `requires-pro`).

| Agent | `tools:` | May change |
|-------|----------|------------|
| `product-owner-agent` | read, search, execute | Creates/updates GitHub issues only; no code |
| `architect-agent` | read, search, execute | Issue comments and the approval label only; no code |
| `senior-java-software-engineer` | read, edit, search, execute | Source, tests, docs and workflows on a `feature/*` branch; opens the PR; sets only `pending` agent statuses; merges only when every gate passes |
| `pr-review-agent` | read, search, execute | PR comments and the `PR Review` status; no code |
| `senior-qa-engineer` | read, edit, search, execute | Adds or improves tests on the PR branch (`edit` is needed for that), PR comments, the `QA Agent` status; no production code |
| `dod-validator-agent` | read, search, execute | PR comments and the `Definition of Done` status; no code |

Analysing agents (product owner, architect, PR review, DoD) already have no `edit` tool, so `tools:` was left unchanged.
`execute` is required by all agents because they use the `gh` CLI.
