"""Bounded Codex App Server client for the CatSynth experiment.

This is deliberately not presented as an OpenAI Chat Completions endpoint.
It speaks the App Server's newline-delimited JSON-RPC protocol and preserves
the complete wire transcript returned by the installed Codex version.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from .openai_compat import ChatResult


DEFAULT_CODEX_MODEL = os.environ.get(
    "CATSYNTH_CODEX_MODEL", "gpt-5.3-codex-spark"
)


class CodexAppServerError(RuntimeError):
    def __init__(self, message: str, *, transcript: Optional[list[dict[str, Any]]] = None):
        super().__init__(message)
        self.transcript = transcript or []


class CodexAppServerClient:
    """One App Server process; one isolated ephemeral thread per model call."""

    provider = "codex-app-server"
    endpoint = "codex app-server --stdio"
    effort = "low"
    summary = "none"
    personality = "none"

    def __init__(self, model: str = DEFAULT_CODEX_MODEL, *, cwd: Optional[Path] = None,
                 command: Optional[list[str]] = None, timeout: int = 300):
        self.model = model
        self.cwd = str((cwd or Path.cwd()).resolve())
        self.command = command or ["codex", "app-server", "--stdio"]
        self.timeout = timeout
        self._next_id = 1
        self._read_buffer = b""
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self.initialization_transcript: list[dict[str, Any]] = []
        response = self._rpc("initialize", {
            "clientInfo": {
                "name": "catsynth-experiment",
                "title": "CatSynth Experiment",
                "version": "0.1.0",
            },
            "capabilities": {"experimentalApi": True},
        }, self.initialization_transcript)
        if "result" not in response:
            raise CodexAppServerError(f"App Server initialize failed: {response}")
        self._send(
            {"method": "initialized", "params": {}},
            self.initialization_transcript,
        )

    def _send(self, message: dict[str, Any],
              transcript: list[dict[str, Any]]) -> None:
        if not self._process.stdin:
            raise CodexAppServerError("App Server stdin is unavailable")
        transcript.append({"direction": "client", "message": message})
        self._process.stdin.write(
            json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        )
        self._process.stdin.flush()

    def _read(self, timeout: Optional[float] = None) -> dict[str, Any]:
        if not self._process.stdout:
            raise CodexAppServerError("App Server stdout is unavailable")
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        fd = self._process.stdout.fileno()
        while b"\n" not in self._read_buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("timed out waiting for Codex App Server")
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                raise TimeoutError("timed out waiting for Codex App Server")
            chunk = os.read(fd, 65536)
            if not chunk:
                raise CodexAppServerError(
                    f"App Server exited with {self._process.poll()}"
                )
            self._read_buffer += chunk
        line, self._read_buffer = self._read_buffer.split(b"\n", 1)
        return json.loads(line)

    def _decline_server_request(self, message: dict[str, Any],
                                transcript: list[dict[str, Any]]) -> None:
        if message.get("method") == "item/tool/call":
            result: dict[str, Any] = {
                "contentItems": [{"type": "inputText", "text": "Tools are disabled."}],
                "success": False,
            }
        else:
            result = {"decision": "decline"}
        self._send({"id": message["id"], "result": result}, transcript)

    def _rpc(self, method: str, params: dict[str, Any],
             transcript: list[dict[str, Any]]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"method": method, "id": request_id, "params": params}, transcript)
        while True:
            message = self._read()
            transcript.append({"direction": "server", "message": message})
            if "id" in message and "method" in message:
                self._decline_server_request(message, transcript)
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise CodexAppServerError(f"{method} failed: {message['error']}")
                return message

    def list_models(self) -> list[str]:
        transcript: list[dict[str, Any]] = []
        response = self._rpc(
            "model/list", {"limit": 100, "includeHidden": False}, transcript
        )
        result = response.get("result", {})
        models = result.get("data", result.get("models", []))
        return [item.get("id") or item.get("model") for item in models]

    @staticmethod
    def _split_messages(messages: list[dict[str, str]]) -> tuple[str, str]:
        system = "\n\n".join(
            item["content"] for item in messages if item.get("role") == "system"
        )
        user_parts = []
        for item in messages:
            if item.get("role") != "system":
                user_parts.append(f"[{item.get('role', 'user')}]\n{item['content']}")
        return system, "\n\n".join(user_parts)

    @staticmethod
    def _usage(value: Optional[dict[str, Any]]) -> dict[str, int]:
        value = value or {}
        return {
            "prompt_tokens": int(value.get("inputTokens", 0)),
            "completion_tokens": int(value.get("outputTokens", 0)),
            "total_tokens": int(value.get("totalTokens", 0)),
            "cached_prompt_tokens": int(value.get("cachedInputTokens", 0)),
            "reasoning_tokens": int(value.get("reasoningOutputTokens", 0)),
        }

    @staticmethod
    def _terminal_error(transcript: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        for row in reversed(transcript):
            message = row.get("message", {})
            if message.get("method") == "error":
                error = message.get("params", {}).get("error")
                if isinstance(error, dict):
                    return error
            if message.get("method") == "turn/completed":
                error = message.get("params", {}).get("turn", {}).get("error")
                if isinstance(error, dict):
                    return error
        return None

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 4096,
             temperature: float = 0, extra: Optional[dict[str, Any]] = None) -> ChatResult:
        extra = dict(extra or {})
        output_schema = extra.pop("output_schema", None)
        system, user = self._split_messages(messages)
        transcript: list[dict[str, Any]] = []
        thread_params = {
            "ephemeral": True,
            "cwd": self.cwd,
            "model": self.model,
            "allowProviderModelFallback": False,
            "approvalPolicy": "never",
            "permissions": ":read-only",
            "environments": [],
            "dynamicTools": [],
            "personality": self.personality,
            "baseInstructions": (
                "Return only the requested final value. Do not call tools, inspect files, "
                "or use the environment."
            ),
            "developerInstructions": system or "Return only the requested value.",
        }
        thread_response = self._rpc("thread/start", thread_params, transcript)
        thread_id = thread_response["result"]["thread"]["id"]
        turn_params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": user}],
            "model": self.model,
            "effort": self.effort,
            "summary": self.summary,
            "personality": self.personality,
            "approvalPolicy": "never",
            "permissions": ":read-only",
            "environments": [],
        }
        if output_schema:
            turn_params["outputSchema"] = output_schema
        turn_response = self._rpc("turn/start", turn_params, transcript)
        turn_id = turn_response["result"]["turn"]["id"]

        content = ""
        reasoning_parts: list[str] = []
        usage_value: Optional[dict[str, Any]] = None
        terminal = None
        while True:
            try:
                message = self._read(timeout=5 if content and usage_value else None)
            except TimeoutError:
                # Some App Server builds omit turn/completed after the final
                # message and token event. The two events are sufficient to
                # preserve output and exact usage; interrupt the idle turn.
                if content and usage_value:
                    terminal = "agent-message-and-token-usage"
                    try:
                        self._rpc(
                            "turn/interrupt",
                            {"threadId": thread_id, "turnId": turn_id},
                            transcript,
                        )
                    except CodexAppServerError:
                        pass
                    break
                raise
            transcript.append({"direction": "server", "message": message})
            if "id" in message and "method" in message:
                self._decline_server_request(message, transcript)
                continue
            method = message.get("method")
            params = message.get("params", {})
            if method == "item/completed":
                item = params.get("item", {})
                if item.get("type") == "agentMessage":
                    content = item.get("text") or ""
                elif item.get("type") == "reasoning":
                    reasoning_parts.extend(item.get("summary") or [])
                    reasoning_parts.extend(item.get("content") or [])
            elif method == "thread/tokenUsage/updated":
                usage_value = params.get("tokenUsage", {}).get("last")
            elif method == "turn/completed":
                terminal = "turn-completed"
                break

        terminal_error = self._terminal_error(transcript)
        if terminal_error:
            code = terminal_error.get("codexErrorInfo") or "unknown"
            message = terminal_error.get("message") or str(terminal_error)
            raise CodexAppServerError(
                f"Codex turn failed [{code}]: {message}", transcript=transcript
            )

        tool_events = [
            row for row in transcript
            if row["direction"] == "server"
            and any(token in str(row["message"].get("method", "")).lower()
                    for token in ("tool", "commandexecution", "requestapproval"))
        ]
        if tool_events:
            raise CodexAppServerError(
                f"bounded turn emitted forbidden tool/approval events: {tool_events}"
            )
        request = {
            "provider": self.provider,
            "model": self.model,
            "messages": messages,
            "max_tokens_requested_but_unsupported": max_tokens,
            "temperature_requested_but_unsupported": temperature,
            "fixed_inference": {
                "effort": self.effort,
                "summary": self.summary,
                "personality": self.personality,
                "collaborationMode": None,
                "multiAgentMode": None,
            },
            "thread_start": thread_params,
            "turn_start": turn_params,
        }
        response = {
            "initialization": self.initialization_transcript,
            "transcript": transcript,
            "terminal": terminal,
            "usage": usage_value,
        }
        return ChatResult(
            content=content.strip(),
            reasoning="\n".join(str(part) for part in reasoning_parts).strip(),
            usage=self._usage(usage_value),
            request=request,
            response=response,
        )

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)

    def __enter__(self) -> "CodexAppServerClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()
