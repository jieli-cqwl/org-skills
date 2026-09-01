#!/usr/bin/env bash
set -euo pipefail

OWNER="${1:-jieli-cqwl}"
REPO="${2:-org-skills}"
BRANCH="${3:-main}"

echo "[guard] applying branch protection: ${OWNER}/${REPO}:${BRANCH}"

gh api -X PUT \
  -H 'Accept: application/vnd.github+json' \
  "repos/${OWNER}/${REPO}/branches/${BRANCH}/protection" \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      {
        "context": "validate",
        "app_id": 15368
      }
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON

echo "[guard] branch protection applied"
