"""The one place that talks to a language model.

Why plain httpx on Ollama's native /api/chat (F2): the OpenAI-style /v1 endpoint cannot set
`num_ctx` per request, and a call to it reloaded the model at 32K, which spills to the CPU on an
8 GB GPU. The native endpoint also gives tool calls, a JSON-schema `format` and token counts.
"""
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.config import Settings

TIMEOUT_SECONDS = 120.0


class LLMError(Exception):
    """The model could not be reached or answered with something unusable."""


@dataclass
class LLMReply:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # [{"name": str, "arguments": dict | str}]
    prompt_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class LLM(Protocol):
    """What the graph needs from any model, real or stub."""

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             json_schema: dict | None = None) -> LLMReply: ...


class OllamaLLM:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def _payload(self, messages: list[dict], tools: list[dict] | None, json_schema: dict | None) -> dict:
        payload: dict = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
            # F3 and F4: num_ctx on every request, temperature 0 for repeatable runs.
            "options": {"num_ctx": self.settings.ollama_num_ctx, "temperature": 0},
        }
        if tools:
            payload["tools"] = tools
        if json_schema:
            payload["format"] = json_schema
        return payload

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             json_schema: dict | None = None) -> LLMReply:
        started = time.perf_counter()
        try:
            response = self.client.post(
                f"{self.settings.ollama_url}/api/chat", json=self._payload(messages, tools, json_schema)
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"model call failed: {exc}") from exc
        message = body.get("message") or {}
        calls = [
            {"name": c["function"]["name"], "arguments": c["function"].get("arguments", {})}
            for c in message.get("tool_calls") or []
            if isinstance(c.get("function"), dict) and "name" in c["function"]
        ]
        return LLMReply(
            content=message.get("content") or "",
            tool_calls=calls,
            prompt_tokens=int(body.get("prompt_eval_count") or 0),
            output_tokens=int(body.get("eval_count") or 0),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


def get_llm(settings: Settings) -> LLM:
    """The Anthropic adapter is not built (F21): it is only added if Ollama proves too slow."""
    if settings.llm_provider == "ollama":
        return OllamaLLM(settings)
    raise LLMError(f"unsupported LLM_PROVIDER '{settings.llm_provider}'")
