"""CLI entry point: `ai-reviewer run`.

Поддерживает два режима, определяемых событием GitHub Actions:
  - pull_request: ревью изменённых файлов в PR. Если PR нацелен на
    ветку main/master, используется более глубокий режим — модель видит
    полное содержимое каждого изменённого файла, а не только diff.
  - push: ревью последнего коммита пуша вне контекста PR (например,
    прямой коммит в ветку без открытого PR).

В обоих случаях результат публикуется одним текстовым комментарием
(без создания резолвящихся тредов).
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

_DEEP_ANALYSIS_BASE_BRANCHES = {"main", "master"}


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


def _format_comment_block(all_issues: list[tuple[str, "parser.Issue"]]) -> str:
    """Собрать все найденные проблемы в один markdown-блок комментария.

    all_issues — список пар (имя_файла, Issue). Формируется один текстовый
    комментарий вместо позиционных inline-комментариев, чтобы не создавать
    резолвящиеся треды в GitHub.
    """
    if not all_issues:
        return "## 🤖 AI Code Review\n\nNO ISSUES FOUND"

    lines = ["## 🤖 AI Code Review", ""]
    for filename, issue in all_issues:
        lines.append(
            f"**{filename}:{issue.line}** — **[{issue.severity}] {issue.category}**: {issue.description}"
        )
        lines.append("")
    return "\n".join(lines).rstrip()


def _review_file(model: str, api_key: str, filename: str, content: str, mode: str) -> list:
    """Прогнать один файл (diff или полный) через модель и распарсить ответ."""
    language = _guess_language(filename)
    user_message = prompts.build_user_message(filename, language, content, mode=mode)

    try:
        raw_output = openrouter.review_with_model(
            model=model,
            system_prompt=prompts.SYSTEM_PROMPT,
            user_message=user_message,
            api_key=api_key,
        )
    except openrouter.OpenRouterError as exc:
        print(f"Review failed for {filename}: {exc}", file=sys.stderr)
        return []

    return parser.parse_issues(raw_output)


def run_pull_request() -> None:
    token = _required_env("GITHUB_TOKEN")
    owner = _required_env("GITHUB_REPOSITORY_OWNER")
    repo_full = _required_env("GITHUB_REPOSITORY")
    repo = repo_full.split("/", 1)[1]
    pull_number = _required_env("PR_NUMBER")
    api_key = _required_env("OPENROUTER_API_KEY")
    model = os.environ.get("AI_REVIEW_MODEL", "anthropic/claude-sonnet-4-5")
    base_ref = os.environ.get("PR_BASE_REF", "")

    deep_mode = base_ref.lower() in _DEEP_ANALYSIS_BASE_BRANCHES
    if deep_mode:
        print(f"PR targets '{base_ref}': using deep (full-file) analysis mode.")

    changed_files = github.get_changed_files(owner, repo, pull_number, token)
    if not changed_files:
        print("No changed files to review.")
        github.post_issue_comment(
            owner, repo, pull_number, "## 🤖 AI Code Review\n\nNO ISSUES FOUND", token
        )
        return

    commit_sha = github.get_latest_commit_sha(owner, repo, pull_number, token)

    all_issues: list[tuple[str, object]] = []

    for f in changed_files:
        if deep_mode:
            try:
                content = github.get_file_content(owner, repo, f.filename, commit_sha, token)
            except github.GitHubAPIError as exc:
                print(f"Could not fetch full content for {f.filename}: {exc}", file=sys.stderr)
                continue
            issues = _review_file(model, api_key, f.filename, content, mode="full_file")
        else:
            if not f.patch:
                print(f"Skipping {f.filename}: no diff available (binary file).")
                continue
            issues = _review_file(model, api_key, f.filename, f.patch, mode="diff")

        print(f"{f.filename}: {len(issues)} issue(s) found.")
        for issue in issues:
            all_issues.append((f.filename, issue))

    body = _format_comment_block(all_issues)
    github.post_issue_comment(owner, repo, pull_number, body, token)
    print(f"Posted a review comment with {len(all_issues)} issue(s) to PR #{pull_number}.")


def run_push() -> None:
    token = _required_env("GITHUB_TOKEN")
    owner = _required_env("GITHUB_REPOSITORY_OWNER")
    repo_full = _required_env("GITHUB_REPOSITORY")
    repo = repo_full.split("/", 1)[1]
    api_key = _required_env("OPENROUTER_API_KEY")
    model = os.environ.get("AI_REVIEW_MODEL", "anthropic/claude-sonnet-4-5")
    sha = _required_env("GITHUB_SHA")

    changed_files = github.get_commit_files(owner, repo, sha, token)
    if not changed_files:
        print("No changed files in this commit.")
        return

    all_issues: list[tuple[str, object]] = []

    for f in changed_files:
        if not f.patch:
            print(f"Skipping {f.filename}: no diff available (binary file).")
            continue
        issues = _review_file(model, api_key, f.filename, f.patch, mode="diff")
        print(f"{f.filename}: {len(issues)} issue(s) found.")
        for issue in issues:
            all_issues.append((f.filename, issue))

    if not all_issues:
        print("No issues found in this commit; skipping comment.")
        return

    body = _format_comment_block(all_issues)
    github.post_commit_comment(owner, repo, sha, body, token)
    print(f"Posted a review comment with {len(all_issues)} issue(s) to commit {sha}.")


def run() -> None:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")
    if event_name == "push":
        run_push()
    else:
        run_pull_request()


def main() -> None:
    parser_cli = argparse.ArgumentParser(prog="ai-reviewer")
    subparsers = parser_cli.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Review changed files in the current PR or push")

    args = parser_cli.parse_args()
    if args.command == "run":
        run()


if __name__ == "__main__":
    main()