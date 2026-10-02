#!/usr/bin/env bash
set -euo pipefail

REPO='paracosm17/accentsbot'

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <dev|production> <true|false>" >&2
  exit 2
fi

ENV_NAME="$1"
VALUE="$2"

if [[ "$VALUE" != true && "$VALUE" != false ]]; then
  echo 'ERROR: value must be true or false' >&2
  exit 2
fi

case "$ENV_NAME" in
  dev) VARIABLE='DEPLOY_DEV_ENABLED' ;;
  production) VARIABLE='DEPLOY_PRODUCTION_ENABLED' ;;
  *) echo 'ERROR: environment must be dev or production' >&2; exit 2 ;;
esac

gh variable set "$VARIABLE" --repo "$REPO" --body "$VALUE"
echo "$VARIABLE=$VALUE"
