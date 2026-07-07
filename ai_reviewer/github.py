"""GitHub API client.
Responsible for:
- fetching the list of changed files in a pull request (with their diffs)
- posting inline review comments back onto the pull request

Uses only the standard library (urllib) so the package has zero extra
HTTP dependencies beyond what's declared in pyproject.toml.

"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable

GITHUB_API_URL = "https://api.github.com"

class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API returns a non-2xx response."""

@dataclass
class ChangedFile:
    filename: str
    status: str
    patch: str | None

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
            f"Github API {method} {url} failed with status {exc.code}: {detail}"
        ) from exc
    

def get_changed_files(
        owner: str, repo: str, pull_number: str, token: str
) -> list[ChangedFile]:
    """Return changed files for a PR, skipping removed files.

    Removed files are excluded by design: there is nothing meaningful to
    review in code that no longer exists (see prompt rationale).
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pull_number}/files?per_page=100"
    raw_files = _request("GET", url, token)

    files: list[ChangedFile] = []
    for f in raw_files:
        if f['status'] == 'removed':
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

@dataclass
class InlineComment:
    path: str
    line: int
    body: str

def post_review_comments(
        owner: str,
        repo: str,
        pull_number: str,
        commit_sha: str,
        token: str,
        comments: Iterable[InlineComment],
) -> None:
    """Post a single PR review containing all inline comments at once.

    Posting as one review (rather than one comment per call) avoids
    hitting secondary rate limits and produces a single, clean review
    event instead of a flood of individual notifications.
    """
    comments_payload = [
        {"path": c.path, "line": c.line, "side": "RIGHT", "body": c.body}
        for c in comments
    ]

    if not comments_payload:
        body = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": "AI Review: NO ISSUES FOUND",
        }
    else: 
        body = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": f"AI Review found {len(comments_payload)} issue(s).",
            "comments": comments_payload,
        }
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
    _request("POST", url, token, body)