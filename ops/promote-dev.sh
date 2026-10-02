#!/usr/bin/env bash
set -Eeuo pipefail

REPO='paracosm17/accentsbot'

if [[ "${DEV_VALIDATED:-}" != YES ]]; then
  echo 'ERROR: set DEV_VALIDATED=YES only after live Coolify DEV, DB, webhook and bot-flow checks pass.' >&2
  exit 2
fi

DEV_SHA="$(gh api "repos/${REPO}/git/ref/heads/dev" --jq '.object.sha')"
MAIN_SHA="$(gh api "repos/${REPO}/git/ref/heads/main" --jq '.object.sha')"

echo "dev=$DEV_SHA"
echo "main=$MAIN_SHA"

if [[ "$DEV_SHA" == "$MAIN_SHA" ]]; then
  echo 'main already equals dev; nothing to promote.'
  exit 0
fi

PR_URL="$(
  gh pr list --repo "$REPO" --state open --base main --head dev --json url --jq '.[0].url // empty'
)"

if [[ -z "$PR_URL" ]]; then
  PR_URL="$(gh pr create \
    --repo "$REPO" \
    --base main \
    --head dev \
    --title 'Promote validated DEV release to production branch' \
    --body 'Promote the release that has completed Coolify DEV smoke/data/webhook/user-flow validation. Production automatic deploy remains independently gated by DEPLOY_PRODUCTION_ENABLED.')"
fi

echo "PR_URL=$PR_URL"
gh pr checks "$PR_URL" --repo "$REPO" --watch --fail-fast
gh pr merge "$PR_URL" --repo "$REPO" --merge

echo 'DEV_TO_MAIN_PROMOTION=COMPLETE'
