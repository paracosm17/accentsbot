#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <coolify-resource-uuid> <ghcr-image@sha256:digest>" >&2
  exit 2
fi

RESOURCE_UUID="$1"
IMAGE_REF="$2"

: "${DEPLOY_HOST:?DEPLOY_HOST is required}"
: "${DEPLOY_SSH_USER:?DEPLOY_SSH_USER is required}"
: "${DEPLOY_SSH_KEY_FINGERPRINT:?DEPLOY_SSH_KEY_FINGERPRINT is required}"
: "${SSH_KNOWN_HOSTS:?SSH_KNOWN_HOSTS is required}"
: "${DEPLOY_SSH_KEY:?DEPLOY_SSH_KEY is required}"
: "${COOLIFY_API_TOKEN_RW:?COOLIFY_API_TOKEN_RW is required}"
: "${COOLIFY_API_TOKEN_DEPLOY:?COOLIFY_API_TOKEN_DEPLOY is required}"

[[ "$RESOURCE_UUID" =~ ^[a-z0-9]{8,64}$ ]] || {
  echo 'ERROR: invalid Coolify resource UUID' >&2
  exit 2
}
[[ "$IMAGE_REF" =~ ^ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+@sha256:[0-9a-f]{64}$ ]] || {
  echo 'ERROR: IMAGE_REF must be an immutable lowercase GHCR sha256 digest' >&2
  exit 2
}
[[ "$DEPLOY_HOST" =~ ^[A-Za-z0-9.-]+$ ]] || {
  echo 'ERROR: invalid DEPLOY_HOST' >&2
  exit 2
}
[[ "$DEPLOY_SSH_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || {
  echo 'ERROR: invalid DEPLOY_SSH_USER' >&2
  exit 2
}
[[ "$DEPLOY_SSH_KEY_FINGERPRINT" =~ ^SHA256:[A-Za-z0-9+/]+$ ]] || {
  echo 'ERROR: invalid SSH key fingerprint' >&2
  exit 2
}
[[ "$SSH_KNOWN_HOSTS" != *$'\n'* ]] || {
  echo 'ERROR: SSH_KNOWN_HOSTS must be exactly one line' >&2
  exit 2
}

read -r known_host known_type known_key known_extra <<< "$SSH_KNOWN_HOSTS"
[[ "$known_host" == "$DEPLOY_HOST" ]] || {
  echo 'ERROR: SSH known-host address does not match DEPLOY_HOST' >&2
  exit 2
}
[[ "$known_type" == 'ssh-ed25519' ]] || {
  echo 'ERROR: SSH known-host key must be ed25519' >&2
  exit 2
}
[[ "$known_key" =~ ^AAAAC3NzaC1lZDI1NTE5AAAAI[A-Za-z0-9+/=]+$ ]] || {
  echo 'ERROR: invalid ed25519 known-host key' >&2
  exit 2
}
[[ -z "${known_extra:-}" ]] || {
  echo 'ERROR: SSH_KNOWN_HOSTS contains unexpected extra fields' >&2
  exit 2
}

umask 077
TMP_DIR="$(mktemp -d)"
KEY_PATH="$TMP_DIR/deploy-key"
PUB_PATH="$TMP_DIR/deploy-key.pub"
KNOWN_HOSTS_PATH="$TMP_DIR/known_hosts"
SSH_PID=''

cleanup() {
  if [[ -n "$SSH_PID" ]] && kill -0 "$SSH_PID" 2>/dev/null; then
    kill "$SSH_PID" 2>/dev/null || true
    wait "$SSH_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

printf '%s\n' "$DEPLOY_SSH_KEY" | tr -d '\r' > "$KEY_PATH"
printf '%s\n' "$SSH_KNOWN_HOSTS" > "$KNOWN_HOSTS_PATH"
chmod 600 "$KEY_PATH" "$KNOWN_HOSTS_PATH"

ssh-keygen -y -P '' -f "$KEY_PATH" > "$PUB_PATH"
ACTUAL_FINGERPRINT="$(ssh-keygen -lf "$PUB_PATH" -E sha256 | awk '{print $2}')"
if [[ "$ACTUAL_FINGERPRINT" != "$DEPLOY_SSH_KEY_FINGERPRINT" ]]; then
  echo 'ERROR: DEPLOY_SSH_KEY does not match DEPLOY_SSH_KEY_FINGERPRINT' >&2
  exit 1
fi

ssh -F /dev/null -N -T \
  -o BatchMode=yes \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no \
  -o KbdInteractiveAuthentication=no \
  -o IdentitiesOnly=yes \
  -o IdentityFile="$KEY_PATH" \
  -o UserKnownHostsFile="$KNOWN_HOSTS_PATH" \
  -o GlobalKnownHostsFile=/dev/null \
  -o StrictHostKeyChecking=yes \
  -o HostKeyAlgorithms=ssh-ed25519 \
  -o ExitOnForwardFailure=yes \
  -o ForwardAgent=no \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:18000:127.0.0.1:8000 \
  "${DEPLOY_SSH_USER}@${DEPLOY_HOST}" &
SSH_PID=$!

TUNNEL_READY=0
for _ in $(seq 1 30); do
  if ! kill -0 "$SSH_PID" 2>/dev/null; then
    wait "$SSH_PID" || true
    echo 'ERROR: restricted SSH tunnel exited before Coolify became reachable' >&2
    exit 1
  fi
  if RESPONSE="$(curl --fail --silent --show-error --max-time 2 http://127.0.0.1:18000/api/health 2>/dev/null)" \
    && [[ "$RESPONSE" == 'OK' ]]; then
    TUNNEL_READY=1
    break
  fi
  sleep 1
done
[[ "$TUNNEL_READY" == 1 ]] || {
  echo 'ERROR: Coolify loopback API did not become reachable through the SSH tunnel' >&2
  exit 1
}

echo 'Restricted Coolify SSH tunnel is ready.'

export COOLIFY_API_TOKEN_RW COOLIFY_API_TOKEN_DEPLOY
export COOLIFY_API_DEPLOY_CONFIRM='I_HAVE_REVIEWED_THE_LOOPBACK_COOLIFY_API_DEPLOYMENT'

python3 -m scripts.coolify_deploy_api \
  --base-url http://127.0.0.1:18000/api/v1 \
  --resource-uuid "$RESOURCE_UUID" \
  --image-ref "$IMAGE_REF" \
  --expected-port 8080 \
  --allow-domain \
  --check

python3 -m scripts.coolify_deploy_api \
  --base-url http://127.0.0.1:18000/api/v1 \
  --resource-uuid "$RESOURCE_UUID" \
  --image-ref "$IMAGE_REF" \
  --expected-port 8080 \
  --allow-domain \
  --apply \
  --poll-timeout 300 \
  --poll-interval 3
