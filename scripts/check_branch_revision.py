from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request


def remote_head(repository: str, branch: str, token: str) -> str:
    url = f"https://api.github.com/repos/{repository}/git/ref/heads/{branch}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "accentsbot-release-guard/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub ref lookup failed with HTTP {exc.code}") from exc
    return str(payload["object"]["sha"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail/skip if this workflow is not branch HEAD.")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", ""))
    parser.add_argument("--revision", default=os.environ.get("GITHUB_SHA", ""))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not all((args.repository, args.branch, args.revision, token)):
        raise SystemExit("repository, branch, revision and GITHUB_TOKEN are required")

    head = remote_head(args.repository, args.branch, token)
    print(f"branch={args.branch} remote_head={head} workflow_revision={args.revision}")
    if head != args.revision:
        print("RELEASE_REVISION_STALE=YES")
        return 3
    print("RELEASE_REVISION_STALE=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
