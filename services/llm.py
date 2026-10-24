"""Compatibility client for Groq, xAI Responses, and NVIDIA-hosted chat APIs."""
import os
from types import SimpleNamespace
import httpx

NVIDIA_DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


def provider():
    default = "nvidia" if os.getenv("NVIDIA_API_KEY") else ("xai" if os.getenv("XAI_API_KEY") else "groq")
    selected = os.getenv("LLM_PROVIDER", default).strip().lower()
    if selected not in ("xai", "groq", "nvidia"):
        raise RuntimeError("LLM_PROVIDER must be xai, groq, or nvidia.")
    return selected


def configuration():
    selected = provider()
    key_name, model_name, default_model = {
        "xai": ("XAI_API_KEY", "XAI_MODEL", "grok-4.7"),
        "groq": ("GROQ_API_KEY", "GROQ_MODEL", "llama-3.3-70b-versatile"),
        "nvidia": ("NVIDIA_API_KEY", "NVIDIA_MODEL", NVIDIA_DEFAULT_MODEL),
    }[selected]
    return {
        "provider": selected,
        "configured": bool(os.getenv(key_name, "").strip()),
        "model": os.getenv(model_name, "").strip() or default_model,
    }


class LLMClient:
    def __init__(self, api_key="", **kwargs):
        self.selected = provider()
        if self.selected == "groq":
            self.key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
        else:
            key_name = "NVIDIA_API_KEY" if self.selected == "nvidia" else "XAI_API_KEY"
            self.key = os.getenv(key_name, "").strip()
        if not self.key:
            raise RuntimeError(f"{self.selected.upper()} API key is not configured. Open Connections for setup status.")
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        config = configuration()
        if self.selected == "groq":
            from groq import Groq
            return Groq(api_key=self.key, timeout=90, max_retries=1).chat.completions.create(**{**kwargs, "model": config["model"]})
        if self.selected == "nvidia":
            return self._create_nvidia(config["model"], **kwargs)
        messages = kwargs.get("messages", [])
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        inputs = [m for m in messages if m["role"] != "system"]
        payload = {"model": config["model"], "input": inputs, "store": False,
                   "max_output_tokens": max(512, kwargs.get("max_tokens", 2000))}
        if system:
            payload["instructions"] = system
        if kwargs.get("response_format", {}).get("type") == "json_object":
            payload["instructions"] = (payload.get("instructions", "") + "\nReturn only a valid JSON object, without Markdown fences.").strip()
        try:
            response = httpx.post("https://api.x.ai/v1/responses", headers={"Authorization": f"Bearer {self.key}"}, json=payload, timeout=120)
            if response.status_code >= 400:
                raise RuntimeError(f"xAI request failed ({response.status_code}). Check model access, API credits, and the server key.")
            data = response.json()
            text = "\n".join(c.get("text", "") for o in data.get("output", []) for c in o.get("content", []) if c.get("type") == "output_text")
            if not text:
                raise RuntimeError("xAI returned no text. Please retry or choose another XAI_MODEL.")
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
        except httpx.HTTPError as exc:
            raise RuntimeError("Could not reach xAI. Please retry.") from exc

    def _create_nvidia(self, configured_model, **kwargs):
        if kwargs.get("stream"):
            raise RuntimeError("NVIDIA streaming is not supported by this client.")
        payload = {
            "model": configured_model,
            "messages": kwargs.get("messages", []),
            "max_tokens": kwargs.get("max_tokens", 2000),
            "stream": False,
        }
        for name in ("temperature", "top_p", "response_format"):
            if name in kwargs:
                payload[name] = kwargs[name]
        # Avoid spending the completion budget on hidden reasoning for document generation.
        if configured_model == NVIDIA_DEFAULT_MODEL:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        try:
            response = httpx.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.key}"},
                json=payload, timeout=120,
            )
        except httpx.HTTPError:
            raise RuntimeError("Could not reach NVIDIA. Please retry.") from None
        if response.status_code >= 400:
            hints = {
                401: "Check NVIDIA_API_KEY in Render.",
                403: "Check your NVIDIA account and model permissions.",
                404: "Check NVIDIA_MODEL; the hosted endpoint may have been retired.",
                429: "NVIDIA's free endpoint is rate limited. Wait before trying again.",
            }
            hint = hints.get(response.status_code, "Check NVIDIA's service availability and your selected model.")
            raise RuntimeError(f"NVIDIA request failed ({response.status_code}). {hint}")
        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Missing completion text")
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError("NVIDIA returned no usable text. Retry or choose another NVIDIA_MODEL.") from None
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
