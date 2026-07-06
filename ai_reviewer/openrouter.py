"""OpenRouter API client.

OpenRouter exposes an OpenAI-compatible /chat/completions endpoint that
proxies to dozens of models (proprietary and open source) under one API
key. This is the only LLM backend the tool talks to — keeping the
package dependency-light and provider-agnostic by design.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

class OpenRouterError(RuntimeError):
    """Raised when the OpenRouter API call fails or returns no content."""

def review_with_model(
        model: str,
        system_prompt:str,
        user_messege: str,
        api_key: str,
        timeout: int = 120,
) -> str:
    """Send a single review request and return the raw model output text.

    temperature=0 is fixed deliberately: the reviewer must be deterministic
    given the same diff, not creative. See prompts.py for the full rationale.
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_messege},
        ],
        "temperature": 0,
        "max_tokens": 2048,
    }

    req = urllib.request.Request(
        OPENROUTER_URL,
        data = json.dumps(payload).encode("utf-8"),
        method = "POST",
    )
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("HTTP-Referer", "https://github.com/")
    req.add_header("X-Title", "ai-code-reviewer")

    try:
        with urllib.request.urlopen(req, timeout = timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc
    
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from exc