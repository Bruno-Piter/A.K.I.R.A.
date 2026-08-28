"""Routines LLM helper. Never hardcodes secrets; reads app.core.settings."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.settings import settings

logger = logging.getLogger(__name__)


class LLMConfigError(RuntimeError):
    """Raised when the configured LLM cannot be constructed (nodes must catch)."""


def get_chat_model(*, temperature: float = 0.0) -> ChatOpenAI:
    provider = (settings.llm_provider or "openai").strip().lower()
    if provider == "ollama":
        base = (settings.ollama_base_url or "http://localhost:11434").rstrip("/")
        return ChatOpenAI(
            model=settings.ollama_model,
            api_key="ollama",
            base_url=f"{base}/v1",
            temperature=temperature,
        )
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise LLMConfigError("OpenAI API key is not configured")
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=key,
        base_url=settings.openai_base_url or "https://api.openai.com/v1",
        temperature=temperature,
    )


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "".join(parts)
    return str(content)


def invoke_text(prompt: str, *, system: str | None = None, temperature: float = 0.0) -> str:
    model = get_chat_model(temperature=temperature)
    messages: list[Any] = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    result = model.invoke(messages)
    return content_to_text(getattr(result, "content", result))


def complete(prompt: str, *, system: str | None = None) -> str:
    return invoke_text(prompt, system=system)


def complete_json(prompt: str, *, system: str | None = None) -> dict[str, Any]:
    raw = invoke_text(prompt, system=system)
    parsed = _parse_json(raw)
    if parsed is None:
        raise RuntimeError(f"LLM did not return JSON: {raw[:400]!r}")
    return parsed


def stream_tokens(prompt: str, *, system: str | None = None) -> Iterator[str]:
    try:
        model = get_chat_model()
        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        for chunk in model.stream(messages):
            text = content_to_text(getattr(chunk, "content", None))
            if text:
                yield text
        return
    except Exception as exc:
        logger.info("token stream failed, falling back to invoke_text: %s", exc)
    yield invoke_text(prompt, system=system)


def _parse_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None