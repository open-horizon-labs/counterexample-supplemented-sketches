"""Small OpenAI-compatible chat client with auditable token accounting."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import requests


DEFAULT_BASE_URL = os.environ.get("CATSYNTH_LLM_BASE_URL", "http://127.0.0.1:8080/v1")
DEFAULT_MODEL = os.environ.get("CATSYNTH_LLM_MODEL", "local-model")
DEFAULT_API_KEY = os.environ.get("CATSYNTH_LLM_API_KEY", "local")
DEFAULT_DIALECT = os.environ.get("CATSYNTH_LLM_DIALECT", "standard")


@dataclass
class ChatResult:
    content: str
    reasoning: str
    usage: dict[str, int]
    request: dict[str, Any]
    response: dict[str, Any]


class OpenAICompatibleClient:
    provider = "openai-compatible"

    def __init__(self, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL,
                 api_key: str = DEFAULT_API_KEY, timeout: int = 300,
                 dialect: str = DEFAULT_DIALECT):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.dialect = dialect

    def list_models(self) -> list[str]:
        response = requests.get(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=min(self.timeout, 15),
        )
        response.raise_for_status()
        return [item["id"] for item in response.json().get("data", [])]

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 4096,
             temperature: float = 0, extra: Optional[dict[str, Any]] = None) -> ChatResult:
        extra = dict(extra or {})
        output_schema = extra.pop("output_schema", None)
        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.dialect == "ollama":
            # Optional Ollama extensions inside the otherwise standard
            # Chat Completions envelope.
            request.update({
                "think": False,
                "reasoning_effort": "low",
                "options": {"num_ctx": 16384},
            })
        if output_schema:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "catsynth_result", "strict": True,
                                "schema": output_schema},
            }
        request.update(extra)
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=request,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        usage = payload.get("usage") or {}
        normalized_usage = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }
        return ChatResult(
            content=(message.get("content") or "").strip(),
            reasoning=(message.get("reasoning") or "").strip(),
            usage=normalized_usage,
            request=request,
            response=payload,
        )

    def close(self) -> None:
        """Match the lifecycle exposed by other experiment backends."""
