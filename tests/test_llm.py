import json
from dataclasses import replace

import httpx
import pytest

from app.config import load_settings
from app.llm import LLMError, OllamaLLM, get_llm

SETTINGS = load_settings()


def make_llm(handler) -> tuple[OllamaLLM, list[dict]]:
    sent: list[dict] = []

    def wrapper(request: httpx.Request) -> httpx.Response:
        sent.append({"url": str(request.url), "body": json.loads(request.content)})
        return handler(request)

    return OllamaLLM(SETTINGS, httpx.Client(transport=httpx.MockTransport(wrapper))), sent


def ok(message: dict, **extra) -> httpx.Response:
    return httpx.Response(200, json={"message": message, **extra})


def test_every_request_sends_num_ctx_and_temperature_zero():
    llm, sent = make_llm(lambda r: ok({"content": "hi"}))
    llm.chat([{"role": "user", "content": "hello"}])
    body = sent[0]["body"]
    assert sent[0]["url"].endswith("/api/chat")
    assert body["options"] == {"num_ctx": SETTINGS.ollama_num_ctx, "temperature": 0}
    assert body["stream"] is False
    assert "tools" not in body and "format" not in body


def test_tools_and_json_schema_are_forwarded():
    llm, sent = make_llm(lambda r: ok({"content": "{}"}))
    llm.chat([], tools=[{"type": "function"}], json_schema={"type": "object"})
    assert sent[0]["body"]["tools"] == [{"type": "function"}]
    assert sent[0]["body"]["format"] == {"type": "object"}


def test_reply_parses_content_tool_calls_and_token_counts():
    message = {"content": "", "tool_calls": [{"function": {"name": "search_jobs", "arguments": {"query": "ml"}}}]}
    llm, _ = make_llm(lambda r: ok(message, prompt_eval_count=120, eval_count=15))
    reply = llm.chat([])
    assert reply.tool_calls == [{"name": "search_jobs", "arguments": {"query": "ml"}}]
    assert (reply.prompt_tokens, reply.output_tokens) == (120, 15)
    assert reply.latency_ms >= 0


def test_http_error_becomes_llm_error():
    llm, _ = make_llm(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(LLMError):
        llm.chat([])


def test_connection_error_becomes_llm_error():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no server")

    llm, _ = make_llm(refuse)
    with pytest.raises(LLMError):
        llm.chat([])


def test_connect_has_its_own_short_timeout():
    timeout = OllamaLLM(SETTINGS).client.timeout
    assert timeout.connect == 5.0 and timeout.read == 120.0


def test_default_url_uses_ipv4_not_localhost(monkeypatch):
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    assert load_settings().ollama_url == "http://127.0.0.1:11434"


def test_unsupported_provider_is_rejected():
    with pytest.raises(LLMError):
        get_llm(replace(SETTINGS, llm_provider="nope"))
