#!/usr/bin/env bash
set -euo pipefail

REPO='paracosm17/accentsbot'

# Existing server-level restricted CI transport from the solo-vps installation.
# Override any value through the environment if the host is intentionally changed.
DEPLOY_HOST="${DEPLOY_HOST:-31.59.174.254}"
DEPLOY_SSH_USER="${DEPLOY_SSH_USER:-solo-vps-ci}"
DEPLOY_SSH_KEY_PATH="${DEPLOY_SSH_KEY_PATH:-$HOME/.ssh/prod-001-CI}"
DEPLOY_SSH_KEY_FINGERPRINT="${DEPLOY_SSH_KEY_FINGERPRINT:-SHA256:qSam7iiWgmR6MaR1o4BZbAQU0IjkRtUpYPJJ1JhFEDc}"
SSH_KNOWN_HOSTS="${SSH_KNOWN_HOSTS:-31.59.174.254 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEeipvIdUPNVRpz0wlZQHFsOXbc/u31oWmfYrgvPKG2m}"

if [[ ! -f "$DEPLOY_SSH_KEY_PATH" ]]; then
  echo "ERROR: CI private key not found: $DEPLOY_SSH_KEY_PATH" >&2
  exit 1
fi

actual_fingerprint="$(ssh-keygen -y -P '' -f "$DEPLOY_SSH_KEY_PATH" | ssh-keygen -lf - -E sha256 | awk '{print $2}')"
if [[ "$actual_fingerprint" != "$DEPLOY_SSH_KEY_FINGERPRINT" ]]; then
  echo 'ERROR: CI private key fingerprint does not match expected server transport.' >&2
  exit 1
fi

read -r known_host known_type _known_key known_extra <<< "$SSH_KNOWN_HOSTS"
if [[ "$known_host" != "$DEPLOY_HOST" || "$known_type" != 'ssh-ed25519' || -n "${known_extra:-}" ]]; then
  echo 'ERROR: SSH_KNOWN_HOSTS must be one exact <host> ssh-ed25519 <key> line.' >&2
  exit 1
fi

gh variable set DEPLOY_HOST --repo "$REPO" --body "$DEPLOY_HOST"
gh variable set DEPLOY_SSH_USER --repo "$REPO" --body "$DEPLOY_SSH_USER"
gh variable set DEPLOY_SSH_KEY_FINGERPRINT --repo "$REPO" --body "$DEPLOY_SSH_KEY_FINGERPRINT"
gh variable set SSH_KNOWN_HOSTS --repo "$REPO" --body "$SSH_KNOWN_HOSTS"
gh variable set DEPLOY_DEV_ENABLED --repo "$REPO" --body false
gh variable set DEPLOY_PRODUCTION_ENABLED --repo "$REPO" --body false

gh secret set DEPLOY_SSH_KEY --repo "$REPO" < "$DEPLOY_SSH_KEY_PATH"

echo
echo 'Enter the Coolify read/write API token when gh prompts.'
gh secret set COOLIFY_API_TOKEN_RW --repo "$REPO"

echo
echo 'Enter the separate Coolify deploy API token when gh prompts.'
gh secret set COOLIFY_API_TOKEN_DEPLOY --repo "$REPO"

echo
echo 'Common GitHub deployment configuration complete.'
echo 'DEPLOY_DEV_ENABLED=false'
echo 'DEPLOY_PRODUCTION_ENABLED=false'
