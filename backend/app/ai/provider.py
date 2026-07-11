"""Pluggable LLM provider (PRD AI-010).

`get_provider()` auto-selects: OpenAI if a key is configured, else Anthropic,
else the deterministic EchoProvider (keeps the app and tests working with no
key). Swapping the underlying model = one env var; swapping the provider = one
class. Cost guards: cheap default models + `ai_max_tokens` cap per answer.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod

import httpx

from ..config import settings


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return the model's answer as a JSON string with keys
        answer / reason / recommended_action."""
        raise NotImplementedError


class EchoProvider(LLMProvider):
    """No external calls. Deterministic, so tests and no-key dev both work."""

    name = "echo"

    def complete(self, system: str, user: str) -> str:
        return json.dumps({
            "answer": "AI answers are disabled — no AI API key is set. "
                      "The evidence below was retrieved from IO's data.",
            "reason": "Running the built-in EchoProvider; no LLM was called.",
            "recommended_action": "Set OPENAI_API_KEY or ANTHROPIC_API_KEY to "
                                  "enable live Ask IO answers.",
        })


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions with JSON mode. Token-capped for cost control."""

    name = "openai"

    def complete(self, system: str, user: str) -> str:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "max_tokens": settings.ai_max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API via the official SDK."""

    name = "anthropic"

    def __init__(self) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=settings.anthropic_api_key)

    def complete(self, system: str, user: str) -> str:
        msg = self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.ai_max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")


def get_provider() -> LLMProvider:
    if settings.openai_api_key:
        return OpenAIProvider()
    if settings.anthropic_api_key:
        return AnthropicProvider()
    return EchoProvider()
