#!/usr/bin/env python3
"""Safely deploy one immutable accentsbot image through loopback-only Coolify API.

The GitHub runner reaches Coolify through the server's restricted SSH transport.
This helper refuses public management API URLs, validates the target Docker Image
application, deploys an exact GHCR sha256 digest, and restores the previous
immutable image when a candidate deployment fails with a known terminal state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

DIRECT_BASE_URL = "http://127.0.0.1:8000/api/v1"
TUNNEL_BASE_URL = "http://127.0.0.1:18000/api/v1"
ALLOWED_BASE_URLS = {DIRECT_BASE_URL, TUNNEL_BASE_URL}
APPLY_CONFIRMATION = "I_HAVE_REVIEWED_THE_LOOPBACK_COOLIFY_API_DEPLOYMENT"
RESOURCE_UUID_RE = re.compile(r"^[a-z0-9]{8,64}$")
GHCR_DIGEST_RE = re.compile(r"^(ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+)@sha256:([0-9a-f]{64})$")
COOLIFY_DIGEST_TAG_RE = re.compile(r"^sha256-([0-9a-f]{64})$")
TERMINAL_STATUSES = {"finished", "failed", "cancelled-by-user"}


class CoolifyDeployError(RuntimeError):
    pass


class DeploymentStateUnknown(CoolifyDeployError):
    """Do not start a rollback while another deployment may still be running."""


class DeploymentNotStarted(CoolifyDeployError):
    """The candidate PATCH failed before a desired-state mutation was confirmed."""


@dataclass(frozen=True, slots=True)
class ImmutableImage:
    name: str
    digest: str

    @property
    def image_ref(self) -> str:
        return f"{self.name}@sha256:{self.digest}"

    @property
    def coolify_tag(self) -> str:
        return f"sha256-{self.digest}"

    @property
    def update_payload(self) -> dict[str, str]:
        return {
            "docker_registry_image_name": self.name,
            "docker_registry_image_tag": self.coolify_tag,
        }


def parse_image_reference(reference: str) -> ImmutableImage:
    match = GHCR_DIGEST_RE.fullmatch(reference.strip())
    if match is None:
        raise ValueError("image must be an exact lowercase ghcr.io/...@sha256:<64 hex> reference")
    return ImmutableImage(name=match.group(1), digest=match.group(2))


def normalize_base_url(value: str) -> str:
    normalized = value.rstrip("/")
    parsed = urlparse(normalized)
    if normalized not in ALLOWED_BASE_URLS:
        raise ValueError(
            "Coolify API must be the loopback endpoint 127.0.0.1:8000 or the fixed "
            "runner-side SSH tunnel 127.0.0.1:18000"
        )
    if parsed.scheme != "http" or parsed.path != "/api/v1" or parsed.query or parsed.fragment:
        raise ValueError("invalid loopback Coolify API URL")
    return normalized


def previous_image(application: dict[str, Any], expected_repository: str) -> ImmutableImage:
    if _clean(application.get("status")).lower() != "running:healthy":
        raise CoolifyDeployError(
            "automatic deploy requires a healthy previous application; inspect Coolify first"
        )
    name = str(application.get("docker_registry_image_name") or "").strip()
    tag = str(application.get("docker_registry_image_tag") or "").strip()
    match = COOLIFY_DIGEST_TAG_RE.fullmatch(tag)
    if name != expected_repository or match is None:
        raise CoolifyDeployError(
            "automatic deploy requires the current desired image to be the same GHCR repository "
            "and an immutable sha256-<digest>; bootstrap DEV manually first"
        )
    return ImmutableImage(name=name, digest=match.group(1))


class CoolifyClient:
    def __init__(self, base_url: str, token: str, *, timeout: float = 15.0):
        self.base_url = normalize_base_url(base_url)
        if not token or token != token.strip():
            raise CoolifyDeployError("Coolify API token is empty or contains whitespace")
        self.token = token
        self.timeout = timeout

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            # Do not echo a potentially sensitive Coolify response body into Actions logs.
            raise CoolifyDeployError(
                f"Coolify API {method} {path} returned HTTP {exc.code}; inspect Coolify logs"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise CoolifyDeployError(f"Coolify API {method} {path} failed: {exc}") from exc

        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CoolifyDeployError("Coolify API returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise CoolifyDeployError("Coolify API returned a non-object response")
        return value


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def application_path(resource_uuid: str) -> str:
    return f"/applications/{urllib.parse.quote(resource_uuid, safe='')}"


def validate_application(
    application: dict[str, Any],
    *,
    resource_uuid: str,
    image: ImmutableImage,
    expected_port: str,
    allow_domain: bool,
) -> None:
    if _clean(application.get("uuid")) != resource_uuid:
        raise CoolifyDeployError("Coolify returned a different application UUID")
    if _clean(application.get("build_pack")) != "dockerimage":
        raise CoolifyDeployError("target must already be a Coolify Docker Image application")

    ports = {
        part.strip() for part in _clean(application.get("ports_exposes")).split(",") if part.strip()
    }
    if expected_port not in ports:
        raise CoolifyDeployError(f"target application must expose internal port {expected_port}")
    if _clean(application.get("ports_mappings")):
        raise CoolifyDeployError("target application must not publish a host port mapping")
    if not allow_domain and _clean(application.get("fqdn")):
        raise CoolifyDeployError("target has a public domain but --allow-domain was not supplied")

    current_repo = _clean(application.get("docker_registry_image_name"))
    if current_repo and current_repo != image.name:
        raise CoolifyDeployError("target application points to a different image repository")


def read_application(
    client: CoolifyClient,
    *,
    resource_uuid: str,
    image: ImmutableImage,
    expected_port: str,
    allow_domain: bool,
) -> dict[str, Any]:
    application = client.request("GET", application_path(resource_uuid))
    validate_application(
        application,
        resource_uuid=resource_uuid,
        image=image,
        expected_port=expected_port,
        allow_domain=allow_domain,
    )
    return application


def validate_persisted_image(application: dict[str, Any], image: ImmutableImage) -> None:
    if _clean(application.get("docker_registry_image_name")) != image.name:
        raise CoolifyDeployError("Coolify did not persist the expected image repository")
    if _clean(application.get("docker_registry_image_tag")) != image.coolify_tag:
        raise CoolifyDeployError("Coolify did not persist the expected immutable digest")


def wait_for_deployment(
    read_client: CoolifyClient,
    *,
    resource_uuid: str,
    deployment_uuid: str,
    image: ImmutableImage,
    expected_port: str,
    allow_domain: bool,
    timeout_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    quoted = urllib.parse.quote(deployment_uuid, safe="")
    deadline = time.monotonic() + timeout_seconds
    deployment: dict[str, Any] = {}

    while time.monotonic() < deadline:
        try:
            deployment = read_client.request("GET", f"/deployments/{quoted}")
        except CoolifyDeployError as exc:
            raise DeploymentStateUnknown(
                f"cannot determine deployment {deployment_uuid} state; inspect Coolify before retrying"
            ) from exc

        status = _clean(deployment.get("status")).lower()
        print(f"deployment={deployment_uuid} status={status or 'unknown'}", flush=True)
        if status in TERMINAL_STATUSES:
            break
        if status not in {"queued", "in_progress"}:
            raise DeploymentStateUnknown(f"unexpected deployment state: {status or '<empty>'}")
        time.sleep(interval_seconds)
    else:
        raise DeploymentStateUnknown(
            f"deployment {deployment_uuid} timeout; it may still be running in Coolify"
        )

    if _clean(deployment.get("status")).lower() != "finished":
        raise CoolifyDeployError(
            f"deployment {deployment_uuid} ended with status={_clean(deployment.get('status'))}"
        )

    health_deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < health_deadline:
        application = read_application(
            read_client,
            resource_uuid=resource_uuid,
            image=image,
            expected_port=expected_port,
            allow_domain=allow_domain,
        )
        validate_persisted_image(application, image)
        status = _clean(application.get("status")).lower()
        if status == "running:healthy":
            return deployment
        if (
            status.startswith(("exited", "stopped", "dead", "failed"))
            or status == "running:unhealthy"
        ):
            raise CoolifyDeployError(f"application became unhealthy after deployment: {status}")
        time.sleep(interval_seconds)

    raise CoolifyDeployError("application did not become running:healthy before timeout")


def deploy_image(
    read_client: CoolifyClient,
    deploy_client: CoolifyClient,
    *,
    resource_uuid: str,
    image: ImmutableImage,
    expected_port: str,
    allow_domain: bool,
    timeout_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    path = application_path(resource_uuid)
    try:
        response = read_client.request("PATCH", path, image.update_payload)
    except CoolifyDeployError as exc:
        raise DeploymentNotStarted(
            "Coolify rejected the desired-image PATCH before mutation was confirmed"
        ) from exc
    if _clean(response.get("uuid")) not in {"", resource_uuid}:
        raise CoolifyDeployError("Coolify PATCH response did not confirm the target application")

    persisted = read_client.request("GET", path)
    validate_application(
        persisted,
        resource_uuid=resource_uuid,
        image=image,
        expected_port=expected_port,
        allow_domain=allow_domain,
    )
    validate_persisted_image(persisted, image)

    try:
        started = deploy_client.request("POST", f"{path}/start")
    except CoolifyDeployError as exc:
        raise DeploymentStateUnknown(
            "deployment start outcome is unknown; inspect Coolify before retrying"
        ) from exc

    deployment_uuid = _clean(started.get("deployment_uuid"))
    if not RESOURCE_UUID_RE.fullmatch(deployment_uuid):
        raise DeploymentStateUnknown(
            "Coolify start response did not include a valid deployment UUID"
        )

    wait_for_deployment(
        read_client,
        resource_uuid=resource_uuid,
        deployment_uuid=deployment_uuid,
        image=image,
        expected_port=expected_port,
        allow_domain=allow_domain,
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
    )
    return {"deployment_uuid": deployment_uuid, "image_ref": image.image_ref}


def require_confirmation() -> None:
    if os.environ.get("COOLIFY_API_DEPLOY_CONFIRM") != APPLY_CONFIRMATION:
        raise CoolifyDeployError(
            f"--apply requires COOLIFY_API_DEPLOY_CONFIRM={APPLY_CONFIRMATION}"
        )


def env_token(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise CoolifyDeployError(f"{name} is required in the environment")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=TUNNEL_BASE_URL)
    parser.add_argument("--resource-uuid", required=True)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--expected-port", default="8080")
    parser.add_argument("--allow-domain", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--poll-timeout", type=float, default=300.0)
    parser.add_argument("--poll-interval", type=float, default=3.0)
    args = parser.parse_args()

    if not RESOURCE_UUID_RE.fullmatch(args.resource_uuid):
        raise SystemExit("invalid Coolify resource UUID")
    if not args.expected_port.isdigit() or not 1 <= int(args.expected_port) <= 65535:
        raise SystemExit("invalid expected port")
    if args.poll_timeout <= 0 or args.poll_interval < 0:
        raise SystemExit("invalid polling interval/timeout")

    image = parse_image_reference(args.image_ref)
    base_url = normalize_base_url(args.base_url)
    read_client = CoolifyClient(base_url, env_token("COOLIFY_API_TOKEN_RW"))
    before = read_application(
        read_client,
        resource_uuid=args.resource_uuid,
        image=image,
        expected_port=args.expected_port,
        allow_domain=args.allow_domain,
    )

    if args.check:
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "mode": "check",
                    "resource_uuid": args.resource_uuid,
                    "application_status": _clean(before.get("status")),
                    "image_ref": image.image_ref,
                },
                sort_keys=True,
            )
        )
        return 0

    require_confirmation()
    previous = previous_image(before, image.name)
    if previous == image:
        print(
            json.dumps({"status": "PASS", "mode": "already-current", "image_ref": image.image_ref})
        )
        return 0

    deploy_client = CoolifyClient(base_url, env_token("COOLIFY_API_TOKEN_DEPLOY"))
    try:
        result = deploy_image(
            read_client,
            deploy_client,
            resource_uuid=args.resource_uuid,
            image=image,
            expected_port=args.expected_port,
            allow_domain=args.allow_domain,
            timeout_seconds=args.poll_timeout,
            interval_seconds=args.poll_interval,
        )
    except (DeploymentStateUnknown, DeploymentNotStarted):
        # Unknown outcomes may still be running, and a rejected PATCH did not confirm
        # a mutation. Neither case should start an automatic second deployment.
        raise
    except CoolifyDeployError as candidate_error:
        print(
            f"candidate failed with known state; restoring previous image {previous.image_ref}",
            flush=True,
        )
        try:
            deploy_image(
                read_client,
                deploy_client,
                resource_uuid=args.resource_uuid,
                image=previous,
                expected_port=args.expected_port,
                allow_domain=args.allow_domain,
                timeout_seconds=args.poll_timeout,
                interval_seconds=args.poll_interval,
            )
        except CoolifyDeployError as rollback_error:
            raise CoolifyDeployError(
                "candidate failed and automatic image rollback also failed; "
                f"candidate_error={candidate_error}; rollback_error={rollback_error}"
            ) from rollback_error
        raise CoolifyDeployError(
            f"candidate deployment failed; previous immutable image restored: {candidate_error}"
        ) from candidate_error

    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": "apply",
                "resource_uuid": args.resource_uuid,
                "image_ref": image.image_ref,
                "previous_image_ref": previous.image_ref,
                **result,
            },
            sort_keys=True,
        )
    )
    print("COOLIFY_DEPLOY=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
