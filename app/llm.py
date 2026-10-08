"""Thin OpenAI-compatible client for the multimodal model (glm-5.3-flash)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT

log = logging.getLogger("copilot.llm")


class LLMError(RuntimeError):
    """Raised when the model call fails or returns unusable output."""


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }


async def vision_json(
    image_data_url: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Send one image + text prompt, expect a strict JSON object back."""
    payload = {
        "model": LLM_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                    {"type": "text", "text": user_prompt},
                ],
            },
        ],
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        r = await client.post(
            f"{LLM_BASE_URL}/chat/completions", json=payload, headers=_headers()
        )
    if r.status_code >= 400:
        raise LLMError(f"model http {r.status_code}: {r.text[:400]}")
    body = r.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:  # pragma: no cover
        raise LLMError(f"unexpected response shape: {str(body)[:300]}") from exc
    return extract_json(content)


async def text_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    payload = {
        "model": LLM_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        r = await client.post(
            f"{LLM_BASE_URL}/chat/completions", json=payload, headers=_headers()
        )
    if r.status_code >= 400:
        raise LLMError(f"model http {r.status_code}: {r.text[:400]}")
    body = r.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:  # pragma: no cover
        raise LLMError(f"unexpected response shape: {str(body)[:300]}") from exc
    return extract_json(content)


async def chat_text(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    payload = {
        "model": LLM_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        r = await client.post(
            f"{LLM_BASE_URL}/chat/completions", json=payload, headers=_headers()
        )
    if r.status_code >= 400:
        raise LLMError(f"model http {r.status_code}: {r.text[:400]}")
    body = r.json()
    return body["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply (tolerates fences)."""
    if not text:
        raise LLMError("empty model reply")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise LLMError(f"no json object in reply: {cleaned[:200]}")
    snippet = cleaned[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as exc:
        raise LLMError(f"bad json: {exc}; snippet={snippet[:200]}") from exc
