"""Ollama HTTP API client supporting streaming chat and context management."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import httpx

from orin.config.settings import LLMConfig, get_config


class OllamaClient:
    """Client for local Ollama LLM service with token streaming and context configuration."""

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        num_ctx: int | None = None,
        keep_alive: str | None = None,
        temperature: float | None = None,
    ) -> None:
        cfg: LLMConfig = get_config().llm
        self.host = (host or cfg.host).rstrip("/")
        self.model = model or cfg.model
        self.num_ctx = num_ctx or cfg.num_ctx
        self.keep_alive = keep_alive or cfg.keep_alive
        self.temperature = temperature if temperature is not None else cfg.temperature

    def is_healthy(self) -> bool:
        """Verifies if the Ollama endpoint is reachable."""
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self.host}/api/version")
                return resp.status_code == 200
        except Exception:
            return False

    def stream_chat(
        self, messages: list[dict[str, str]], timeout: float = 60.0
    ) -> Generator[str]:
        """Streams assistant reply tokens line-by-line from /api/chat.

        Yields individual token strings as they arrive from the model.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": self.num_ctx,
                "temperature": self.temperature,
            },
            "keep_alive": self.keep_alive,
        }

        url = f"{self.host}/api/chat"
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        yield f"[Ollama Error: HTTP {response.status_code}]"
                        return

                    for line in response.iter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError:
            yield f"[Error: Could not connect to Ollama at {self.host}. Is it running?]"
        except httpx.TimeoutException:
            yield "[Error: Ollama generation timed out.]"
        except Exception as e:
            yield f"[Ollama Error: {e}]"

    def chat(self, messages: list[dict[str, str]], timeout: float = 60.0) -> str:
        """Synchronous non-streaming chat request, returning complete response text."""
        tokens = list(self.stream_chat(messages, timeout=timeout))
        return "".join(tokens).strip()

    def summarize_conversation(self, turns: list[dict[str, str]]) -> str:
        """Generates a concise summary of older conversation turns for memory compression."""
        if not turns:
            return ""

        formatted_turns = "\n".join(
            f"{t.get('role', 'unknown').capitalize()}: {t.get('content', '')}" for t in turns
        )
        prompt = (
            "Summarize the key facts, user preferences, and topics discussed in this conversation "
            "in 2-3 concise bullet points or sentences:\n\n"
            f"{formatted_turns}\n\n"
            "Summary:"
        )

        messages = [
            {
                "role": "system",
                "content": "You are a concise memory summarizer. Extract only essential facts.",
            },
            {"role": "user", "content": prompt},
        ]
        return self.chat(messages, timeout=30.0)

    def extract_preference_if_any(self, user_text: str) -> tuple[str, str] | None:
        """Detects if the user is explicitly stating a personal preference or name.

        E.g. 'My name is Rohithan and I am a software engineer' -> ('user_name', 'Rohithan')
        """
        import re

        lower = user_text.lower().strip()
        for prefix in ("call me ", "my name is "):
            if prefix in lower:
                start = lower.find(prefix) + len(prefix)
                raw_name = user_text[start:].strip()
                # Split at 'and', commas, or punctuation
                parts = re.split(r"\s+and\s+|[,.!?\n]", raw_name, flags=re.IGNORECASE)
                name = parts[0].strip(" .!?'\"")
                if name and len(name.split()) <= 3:
                    return ("user_name", name)
        return None


_global_llm_client: OllamaClient | None = None


def get_llm_client() -> OllamaClient:
    """Singleton getter for OllamaClient."""
    global _global_llm_client
    if _global_llm_client is None:
        _global_llm_client = OllamaClient()
    return _global_llm_client
