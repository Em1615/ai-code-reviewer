"""Manual testing script: run the same diff through several models on
OpenRouter and compare their output side by side.

Not part of the pip package — this is a dev tool for evaluating the
prompt's behavior across models before picking a default in CI.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    python tests/test_models.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_reviewer import openrouter, parser, prompts

# A deliberately buggy sample diff covering several issue categories:
# SQL injection (SECURITY), missing exception handling (RELIABILITY),
# N+1 query (PERFORMANCE), and an off-by-one (BUG).
SAMPLE_DIFF = """\
@@ -10,6 +10,16 @@ def get_user(user_id):
     return db.execute(f"SELECT * FROM users WHERE id = {user_id}")
+
+def get_orders_for_users(user_ids):
+    orders = []
+    for uid in user_ids:
+        result = db.execute(f"SELECT * FROM orders WHERE user_id = {uid}")
+        orders.append(result)
+    return orders
+
+def fetch_remote_config():
+    response = requests.get("https://config.example.com/settings.json")
+    return response.json()
+
+def last_n_items(items, n):
+    return items[len(items) - n - 1:]
"""

MODELS_TO_TEST = [
    "openai/gpt-oss-20b:free",
    "deepseek/deepseek-r1:free",
]


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Set OPENROUTER_API_KEY before running this script.", file = sys.stderr)
        sys.exit(1)

    user_message = prompts.build_user_message(
        filename = "sample.py", language = "python", diff = SAMPLE_DIFF
    )

    for model in MODELS_TO_TEST:
        print("=" * 70)
        print(f"MODEL: {model}")
        print("=" * 70)
        try:
            raw_output = openrouter.review_with_model(
                model = model,
                system_prompt = prompts.SYSTEM_PROMPT,
                user_messege = user_message,
                api_key = api_key,
            )
        except openrouter.OpenouterError as exc:
            print(f"  ERROR: {exc}\n")
            continue

        issues = parser.parse_issues(raw_output)

        print(f"  Raw output:\n {raw_output}\n")
        print(f"  Parsed issues: {len(issues)}")
        for issue in issues:
            print(f"    - [{issue.severity}] {issue.category}: {issue.description}")
        print()


if __name__ == "__main__":
    main()