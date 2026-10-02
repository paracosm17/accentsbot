from __future__ import annotations

import pytest

from scripts.check_release_revision import wait_for_revision
from scripts.coolify_deploy_api import (
    TUNNEL_BASE_URL,
    CoolifyDeployError,
    normalize_base_url,
    parse_image_reference,
    validate_application,
)


def image_ref() -> str:
    return f"ghcr.io/paracosm17/accentsbot@sha256:{'a' * 64}"


def healthy_application() -> dict:
    return {
        "uuid": "abcdefgh1234",
        "build_pack": "dockerimage",
        "ports_exposes": "8080",
        "ports_mappings": "",
        "fqdn": "https://accents-dev.example.com",
        "docker_registry_image_name": "ghcr.io/paracosm17/accentsbot",
        "docker_registry_image_tag": f"sha256-{'b' * 64}",
        "status": "running:healthy",
    }


def test_parse_exact_sha256_image_reference() -> None:
    image = parse_image_reference(image_ref())
    assert image.name == "ghcr.io/paracosm17/accentsbot"
    assert image.coolify_tag == f"sha256-{'a' * 64}"


def test_parse_image_reference_rejects_mutable_tag() -> None:
    with pytest.raises(ValueError, match="exact"):
        parse_image_reference("ghcr.io/paracosm17/accentsbot:dev")


def test_coolify_api_rejects_public_management_url() -> None:
    assert normalize_base_url(TUNNEL_BASE_URL) == TUNNEL_BASE_URL
    with pytest.raises(ValueError, match="loopback"):
        normalize_base_url("https://coolify.example.com/api/v1")


def test_application_contract_rejects_host_port_mapping() -> None:
    app = healthy_application()
    app["ports_mappings"] = "8080:8080"
    with pytest.raises(CoolifyDeployError, match="host port"):
        validate_application(
            app,
            resource_uuid="abcdefgh1234",
            image=parse_image_reference(image_ref()),
            expected_port="8080",
            allow_domain=True,
        )


def test_application_contract_accepts_expected_docker_image_resource() -> None:
    validate_application(
        healthy_application(),
        resource_uuid="abcdefgh1234",
        image=parse_image_reference(image_ref()),
        expected_port="8080",
        allow_domain=True,
    )


def test_release_waiter_observes_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import check_release_revision

    monkeypatch.setattr(
        check_release_revision,
        "fetch_json",
        lambda *_args, **_kwargs: {"status": "ok", "release_revision": "abc"},
    )
    assert (
        wait_for_revision("https://example.test", "abc", timeout_seconds=1, interval_seconds=0)[
            "release_revision"
        ]
        == "abc"
    )
