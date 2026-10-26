#!/usr/bin/env bash
# Records the task elapsed time on the task issue and the PR: an "Elapsed time" block at the top of both descriptions
# and one <!-- task-elapsed --> comment on each. Re-running updates both instead of duplicating.
# Usage: .github/scripts/post_task_elapsed.sh <issue> <pr> <start-epoch> [end-epoch]
set -euo pipefail
exec python3 "$(dirname "$0")/task_elapsed.py" "$@"
