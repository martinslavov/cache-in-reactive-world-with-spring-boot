<!-- The tracking issue link is added automatically at the top of this description when the PR is opened. -->

# Description

_Summarize the change with the relevant motivation and context. State any breaking changes clearly._

# Pull-request relations

_List the links to issues, pull requests or dependencies related to or required by this change._

- Tracking issue: added automatically (workflow `PR Issue Tracking`); it is closed when this PR is merged.
- Closes: #<issue> (the issue created for the task; closed and moved to Done on merge)
- Related to:
  - (# other issues, # other pull requests, dependencies)

# How has this been tested?

_Describe the tests you ran to verify the change and how to reproduce them._

- Commands you ran and their result, e.g. `./gradlew build` (passed), `make up && make component-tests && make down` (passed)
- Test A

# Checklist

_Place `NA` between brackets when an activity is not applicable._

- [ ] I have identified any breaking changes in the description above.
- [ ] I have performed a self-review of my own code.
- [ ] I have added tests that prove my fix is effective or that my feature works.
- [ ] New and existing tests pass locally (`./gradlew build`; component tests: `make build && make up && make component-tests && make down`).
- [ ] Required checks pass: unit tests, component tests, sanity tests.
- [ ] Documentation is updated accordingly (_e.g._, README, API, configuration).
- [ ] Pull request is categorized with labels:
  - **type**: `bug`, `documentation` or `enhancement`.
  - **impact**: `minor` or `major` (`major` = breaking change in API, behavior, configuration, data format or dependencies).

# Additional context

_Add any other context or screenshots about the change, if applicable._
