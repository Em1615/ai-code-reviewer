"""CLI entry point: `ai-reviewer run`.

Reads configuration from environment variables (so it drops straight into
a GitHub Actions step), fetches the PR's changed files, reviews each
file's diff via OpenRouter, and posts the results as inline PR comments.
"""

from __future__ import annotations

import argparse
import os
import sys

from ai_reviewer import github, openrouter, parser, prompts

_EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".rs": "rust",
    ".sh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
}


def _guess_language(filename: str) -> str:
    for ext, lang in _EXTENSION_TO_LANGUAGE.items():
        if filename.endswith(ext):
            return lang
    return "unknown"


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def run() -> None:
    token = _required_env("GITHUB_TOKEN")
    owner = _required_env("GITHUB_REPOSITORY_OWNER")
    repo_full = _required_env("GITHUB_REPOSITORY")  # "owner/repo"
    repo = repo_full.split("/", 1)[1]
    pull_number = _required_env("PR_NUMBER")
    api_key = _required_env("OPENROUTER_API_KEY")
    model = os.environ.get("AI_REVIEW_MODEL", "anthropic/claude-sonnet-4-5")

    changed_files = github.get_changed_files(owner, repo, pull_number, token)
    if not changed_files:
        print("No changed files to review.")
        return

    all_comments: list[github.InlineComment] = []

    for f in changed_files:
        if not f.patch:
            print(f"Skipping {f.filename}: no diff available (binary file).")
            continue

        language = _guess_language(f.filename)
        user_message = prompts.build_user_message(f.filename, language, f.patch)

        try:
            raw_output = openrouter.review_with_model(
                model=model,
                system_prompt=prompts.SYSTEM_PROMPT,
                user_message=user_message,
                api_key=api_key,
            )
        except openrouter.OpenRouterError as exc:
            print(f"Review failed for {f.filename}: {exc}", file=sys.stderr)
            continue

        issues = parser.parse_issues(raw_output)
        print(f"{f.filename}: {len(issues)} issue(s) found.")

        for issue in issues:
            all_comments.append(
                github.InlineComment(
                    path=f.filename,
                    line=issue.line,
                    body=issue.format_comment(),
                )
            )

    commit_sha = github.get_latest_commit_sha(owner, repo, pull_number, token)
    github.post_review_comments(
        owner, repo, pull_number, commit_sha, token, all_comments
    )
    print(f"Posted {len(all_comments)} inline comment(s) to PR #{pull_number}.")


def main() -> None:
    parser_cli = argparse.ArgumentParser(prog="ai-reviewer")
    subparsers = parser_cli.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Review changed files in the current PR")

    args = parser_cli.parse_args()
    if args.command == "run":
        run()


if __name__ == "__main__":
    main()