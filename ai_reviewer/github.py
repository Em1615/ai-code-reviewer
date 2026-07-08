"""GitHub API client.

Responsible for:
  - fetching the list of changed files in a pull request (with their diffs)
  - fetching the full content of a file (for deep/full-file review mode)
  - fetching the files changed in a single commit (for push-event review)
  - posting a single, non-threaded review comment on a PR or a commit

Uses only the standard library (urllib) so the package has zero extra
HTTP dependencies beyond what's declared in pyproject.toml.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

GITHUB_API_URL = "https://api.github.com"


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API returns a non-2xx response."""


@dataclass
class ChangedFile:
    filename: str
    status: str          # "added" | "modified" | "removed" | "renamed"
    patch: str | None     # unified diff for this file; None for binary files


def _request(method: str, url: str, token: str, body: dict | None = None) -> dict | list:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GitHubAPIError(
            f"GitHub API {method} {url} failed with {exc.code}: {detail}"
        ) from exc


def get_changed_files(
    owner: str, repo: str, pull_number: str, token: str
) -> list[ChangedFile]:
    """Return changed files for a PR, skipping removed files."""
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pull_number}/files?per_page=100"
    raw_files = _request("GET", url, token)

    files: list[ChangedFile] = []
    for f in raw_files:
        if f.get("status") == "removed":
            continue
        files.append(
            ChangedFile(
                filename=f["filename"],
                status=f["status"],
                patch=f.get("patch"),
            )
        )
    return files


def get_commit_files(owner: str, repo: str, sha: str, token: str) -> list[ChangedFile]:
    """Return the files changed in a single commit.

    Used for push-event review, when a commit is reviewed outside of any
    pull request. Same shape as get_changed_files, but sourced from the
    commit endpoint instead of the PR files endpoint.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/commits/{sha}"
    data = _request("GET", url, token)

    files: list[ChangedFile] = []
    for f in data.get("files", []):
        if f.get("status") == "removed":
            continue
        files.append(
            ChangedFile(
                filename=f["filename"],
                status=f["status"],
                patch=f.get("patch"),
            )
        )
    return files


def get_latest_commit_sha(owner: str, repo: str, pull_number: str, token: str) -> str:
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pull_number}"
    pr = _request("GET", url, token)
    return pr["head"]["sha"]


def get_file_content(owner: str, repo: str, path: str, ref: str, token: str) -> str:
    """Fetch the full content of a file at a specific ref (branch or commit SHA).

    Used for the deep-analysis mode: when a PR targets main/master, we
    review each changed file's complete content instead of just its diff.
    """
    encoded_path = urllib.parse.quote(path)
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{encoded_path}?ref={ref}"
    data = _request("GET", url, token)

    if data.get("encoding") != "base64":
        raise GitHubAPIError(f"Unexpected encoding for {path}: {data.get('encoding')}")

    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


def post_issue_comment(owner: str, repo: str, issue_number: str, body: str, token: str) -> None:
    """Post a single top-level comment on a pull request.

    Pull requests are addressable as 'issues' in the GitHub REST API for
    comment purposes. Deliberately NOT using the Reviews API here: that
    API creates one resolvable inline conversation thread per comment.
    This posts one plain, non-threaded comment instead.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    _request("POST", url, token, {"body": body})


def post_commit_comment(owner: str, repo: str, sha: str, body: str, token: str) -> None:
    """Post a single, non-threaded comment on a commit.

    Used for push-event review, when a commit is reviewed outside of any
    pull request context.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/commits/{sha}/comments"
    _request("POST", url, token, {"body": body})