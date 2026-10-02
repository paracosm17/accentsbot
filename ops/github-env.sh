#!/usr/bin/env bash
set -euo pipefail

REPO='paracosm17/accentsbot'

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <dev|production> <coolify-app-uuid> <https-public-url>" >&2
  exit 2
fi

ENV_NAME="$1"
APP_UUID="$2"
PUBLIC_URL="${3%/}"

if [[ "$ENV_NAME" != dev && "$ENV_NAME" != production ]]; then
  echo 'ERROR: environment must be dev or production' >&2
  exit 2
fi

if [[ "$PUBLIC_URL" != https://* ]]; then
  echo 'ERROR: public URL must start with https://' >&2
  exit 2
fi

gh api --method PUT "repos/${REPO}/environments/${ENV_NAME}" >/dev/null
gh variable set COOLIFY_RESOURCE_UUID --repo "$REPO" --env "$ENV_NAME" --body "$APP_UUID"
gh variable set APP_PUBLIC_URL --repo "$REPO" --env "$ENV_NAME" --body "$PUBLIC_URL"

echo "Configured GitHub environment=${ENV_NAME} app_uuid=${APP_UUID} public_url=${PUBLIC_URL}"
