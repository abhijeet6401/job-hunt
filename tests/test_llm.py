"""Offline contract tests for NVIDIA's hosted chat adapter; no real keys or calls."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.llm import LLMClient, configuration, provider, NVIDIA_DEFAULT_MODEL


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    for name in ("LLM_PROVIDER", "NVIDIA_API_KEY", "NVIDIA_MODEL", "XAI_API_KEY",
                 "XAI_MODEL", "GROQ_API_KEY", "GROQ_MODEL"):
        monkeypatch.delenv(name, raising=False)


def nvidia(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia-key")


def test_nvidia_configuration_omits_secret_and_uses_default(monkeypatch):
    nvidia(monkeypatch)
    assert configuration() == {"provider": "nvidia", "configured": True, "model": NVIDIA_DEFAULT_MODEL}
    assert "test-nvidia-key" not in json.dumps(configuration())


def test_provider_auto_detects_nvidia_but_respects_explicit_choice(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia-key")
    assert provider() == "nvidia"
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    assert provider() == "groq"


def test_nvidia_requires_own_key_despite_legacy_groq_argument(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    assert not configuration()["configured"]
    with pytest.raises(RuntimeError, match="NVIDIA API key"):
        LLMClient(api_key="legacy-groq-key")


def test_missing_nvidia_key_never_falls_back_to_xai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("XAI_API_KEY", "paid-provider-key")
    with pytest.raises(RuntimeError, match="NVIDIA API key"):
        LLMClient()


def test_nvidia_request_and_legacy_response_shape(monkeypatch):
    nvidia(monkeypatch)
    def post(url, **kwargs):
        assert url == "https://integrate.api.nvidia.com/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-nvidia-key"
        payload = kwargs["json"]
        assert payload["model"] == NVIDIA_DEFAULT_MODEL
        assert payload["messages"] == [{"role": "user", "content": "Hi"}]
        assert payload["stream"] is False
        assert payload["max_tokens"] == 700
        assert payload["temperature"] == 0.2
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello"}}]})
    monkeypatch.setattr("services.llm.httpx.post", post)
    assert LLMClient(api_key="legacy-groq-key").chat.completions.create(
        model="legacy-groq-model", messages=[{"role": "user", "content": "Hi"}],
        max_tokens=700, temperature=0.2,
    ).choices[0].message.content == "Hello"


def test_custom_model_and_json_format(monkeypatch):
    nvidia(monkeypatch)
    monkeypatch.setenv("NVIDIA_MODEL", "another/model")
    def post(url, **kwargs):
        assert kwargs["json"]["model"] == "another/model"
        assert kwargs["json"]["response_format"] == {"type": "json_object"}
        assert "chat_template_kwargs" not in kwargs["json"]
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})
    monkeypatch.setattr("services.llm.httpx.post", post)
    result = LLMClient().chat.completions.create(messages=[], response_format={"type": "json_object"})
    assert json.loads(result.choices[0].message.content) == {"ok": True}


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_nvidia_errors_sanitized_and_no_provider_fallback(monkeypatch, status):
    nvidia(monkeypatch)
    urls = []
    def post(url, **kwargs):
        urls.append(url)
        return httpx.Response(status, text="sensitive provider detail test-nvidia-key")
    monkeypatch.setattr("services.llm.httpx.post", post)
    with pytest.raises(RuntimeError) as error:
        LLMClient().create(messages=[])
    assert str(status) in str(error.value)
    assert "test-nvidia-key" not in str(error.value)
    assert "sensitive provider detail" not in str(error.value)
    assert urls == ["https://integrate.api.nvidia.com/v1/chat/completions"]


@pytest.mark.parametrize("data", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]},
                                  {"choices": [{"message": {"content": ""}}]}, {"choices": [{"message": {"content": ["wrong-type"]}}]}])
def test_invalid_completions_fail_clearly(monkeypatch, data):
    nvidia(monkeypatch)
    monkeypatch.setattr("services.llm.httpx.post", lambda *a, **k: httpx.Response(200, json=data))
    with pytest.raises(RuntimeError, match="no usable text"):
        LLMClient().create(messages=[])


def test_invalid_json_sanitized(monkeypatch):
    nvidia(monkeypatch)
    monkeypatch.setattr("services.llm.httpx.post", lambda *a, **k: httpx.Response(200, text="not json"))
    with pytest.raises(RuntimeError, match="no usable text"):
        LLMClient().create(messages=[])


def test_network_errors_sanitized(monkeypatch):
    nvidia(monkeypatch)
    def post(*args, **kwargs):
        raise httpx.ConnectError("test-nvidia-key must not be exposed")
    monkeypatch.setattr("services.llm.httpx.post", post)
    with pytest.raises(RuntimeError, match="Could not reach NVIDIA") as error:
        LLMClient().create(messages=[])
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True


def test_streaming_is_rejected_without_request(monkeypatch):
    nvidia(monkeypatch)
    with pytest.raises(RuntimeError, match="streaming"):
        LLMClient().create(messages=[], stream=True)


def test_xai_responses_unchanged(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "xai")
    monkeypatch.setenv("XAI_API_KEY", "test-xai-key")
    monkeypatch.setenv("XAI_MODEL", "selected-model")
    def post(url, **kwargs):
        assert url == "https://api.x.ai/v1/responses"
        assert kwargs["json"]["model"] == "selected-model"
        assert kwargs["json"]["store"] is False
        return SimpleNamespace(status_code=200, json=lambda: {"output": [{"content": [{"type": "output_text", "text": "Hello"}]}]})
    monkeypatch.setattr("services.llm.httpx.post", post)
    assert LLMClient().create(messages=[{"role": "user", "content": "Hi"}]).choices[0].message.content == "Hello"
