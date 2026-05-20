from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class OpenAIError(RuntimeError):
    pass


def _extract_output_text(response_json: dict[str, Any]) -> str:
    # REST responses return an `output` array with `content` parts.
    out: list[str] = []
    for item in (response_json.get("output") or []):
        for part in (item.get("content") or []):
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                out.append(part["text"])
    return "".join(out).strip()


def responses_json(
    *,
    model: str,
    instructions: str,
    input_text: str,
    timeout_s: float = 25.0,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OpenAIError("Missing OPENAI_API_KEY")

    body = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (trusted host)
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = ""
        raise OpenAIError(f"OpenAI HTTP error {e.code}: {detail}") from e
    except Exception as e:
        raise OpenAIError(f"OpenAI request failed: {e}") from e

    data = json.loads(raw)
    text = _extract_output_text(data)
    if not text:
        raise OpenAIError("OpenAI returned empty output text")

    try:
        return json.loads(text)
    except Exception as e:
        raise OpenAIError(f"OpenAI did not return valid JSON: {text[:400]}") from e

