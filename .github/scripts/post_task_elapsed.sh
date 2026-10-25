#!/usr/bin/env bash
# Posts (or updates) the task elapsed-time comment on the task issue and the PR.
# Usage: .github/scripts/post_task_elapsed.sh <issue> <pr> <start-epoch> [end-epoch]
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 <issue> <pr> <start-epoch> [end-epoch]" >&2
  exit 2
fi

issue=$1
pr=$2
start=$3
end=${4:-$(date +%s)}
repo=${RCAS_REPO:-martinslavov/rcas}
marker='<!-- task-elapsed -->'

for n in "$issue" "$pr"; do
  [[ $n =~ ^[1-9][0-9]*$ ]] || { echo "Issue and PR must be positive integers" >&2; exit 2; }
done
for n in "$start" "$end"; do
  [[ $n =~ ^[0-9]+$ ]] || { echo "Epochs must be non-negative integers" >&2; exit 2; }
done
(( end >= start )) || { echo "end-epoch is before start-epoch" >&2; exit 2; }

elapsed=$((end - start))
utc() { date -u -r "$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }

body="${marker}
**Task elapsed time:** $((elapsed / 60)) min $((elapsed % 60)) s (${elapsed} s)

| Start (user input) | End (merged, all agents done) | Issue | PR |
|---|---|---|---|
| $(utc "$start") | $(utc "$end") | #${issue} | #${pr} |"

# Resolve both targets before writing so an invalid one leaves nothing half-updated.
gh api "repos/${repo}/pulls/${pr}" --jq .number >/dev/null
gh api "repos/${repo}/issues/${issue}" --jq .number >/dev/null
ids=()
for n in "$issue" "$pr"; do
  ids+=("$(gh api "repos/${repo}/issues/${n}/comments" --paginate \
    --jq "[.[] | select(.body | startswith(\"${marker}\"))][0].id // empty" | head -n1)")
done

for i in 0 1; do
  n=$([[ $i == 0 ]] && echo "$issue" || echo "$pr")
  id=${ids[$i]}
  if [[ -n $id ]]; then
    gh api -X PATCH "repos/${repo}/issues/comments/${id}" -f body="$body" --jq .html_url
  else
    gh api -X POST "repos/${repo}/issues/${n}/comments" -f body="$body" --jq .html_url
  fi
done
