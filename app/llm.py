import base64
import json
import re
import time

import httpx

from .config import settings


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> dict:
    """Parse model output into a dict, tolerating code fences and stray prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise LLMError("Model did not return valid JSON")


def _image_part(data: bytes) -> dict:
    b64 = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}


def generate(prompt: str, images: list[bytes]) -> tuple[dict, dict]:
    """Call the model and retry once if its response is invalid JSON."""
    headers = {"Authorization": f"Bearer {settings.api_key}"}
    started = time.perf_counter()
    last_error = None

    for attempt in range(2):
        retry_instruction = (
            "\n\nIMPORTANT JSON REQUIREMENT: Return exactly one valid JSON "
            "object matching the requested structure. Do not include Markdown "
            "fences, commentary, or text outside the JSON. Escape quotes and "
            "special characters correctly inside JSON strings."
        ) if attempt == 1 else ""

        content = [
            {"type": "text", "text": prompt + retry_instruction}
        ] + [_image_part(i) for i in images]

        body = {
            "model": settings.model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {"type": "json_object"},
            "temperature": 0.4 if attempt == 0 else 0.0,
        }

        try:
            r = httpx.post(
                f"{settings.base_url.rstrip('/')}/chat/completions",
                json=body,
                headers=headers,
                timeout=settings.timeout_s,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"Model server error: {e}") from e

        data = r.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(
                "Unexpected response shape from model server"
            ) from e

        if not isinstance(text, str) or not text.strip():
            last_error = LLMError("Model returned empty content")
            continue

        try:
            parsed = extract_json(text)
        except LLMError as e:
            last_error = e
            continue

        usage = data.get("usage") or {}
        meta = {
            "model": settings.model,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }
        return parsed, meta

    raise LLMError(
        "Model did not return valid JSON after one retry"
    ) from last_error
