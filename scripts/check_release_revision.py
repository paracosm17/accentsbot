from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def fetch_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "accentsbot-release-check/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status: {response.status}")
        return json.load(response)


def wait_for_revision(
    base_url: str,
    expected_revision: str,
    *,
    timeout_seconds: int,
    interval_seconds: int,
) -> dict:
    health_url = f"{base_url.rstrip('/')}/healthz"
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            payload = fetch_json(health_url, timeout=min(10.0, interval_seconds + 5.0))
            if (
                payload.get("status") == "ok"
                and payload.get("release_revision") == expected_revision
            ):
                return payload
            last_error = RuntimeError(
                "health endpoint is up but revision is not active yet: "
                f"status={payload.get('status')!r} revision={payload.get('release_revision')!r}"
            )
        except (OSError, ValueError, urllib.error.URLError, RuntimeError) as exc:
            last_error = exc
        time.sleep(interval_seconds)

    raise TimeoutError(
        f"release revision {expected_revision!r} was not observed at {health_url}: {last_error}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wait for a deployed release revision on /healthz."
    )
    parser.add_argument("--url", required=True, help="Public application base URL")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    payload = wait_for_revision(
        args.url,
        args.expected_revision,
        timeout_seconds=args.timeout,
        interval_seconds=args.interval,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    print("RELEASE_REVISION_VERIFY=OK")


if __name__ == "__main__":
    main()
