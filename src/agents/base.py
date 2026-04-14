from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.config import settings
from src.memory.store import MemoryStore


class BaseAgent(ABC):
    """Abstract base for every agent in the pipeline.

    Provides:
    - A shared memory store (injected by orchestrator)
    - A logger scoped to the agent name
    - A standard run() interface
    - LLM call helper (override _get_llm_client for custom providers)
    """

    name: str = "base"

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or MemoryStore()
        self.logger = logging.getLogger(f"agent.{self.name}")

    # ── Public interface ──

    async def run(self, **kwargs: Any) -> Any:
        """Execute the agent's task. Wraps _execute with logging."""
        self.logger.info("[%s] Starting …", self.name)
        try:
            result = await self._execute(**kwargs)
            self.logger.info("[%s] Finished.", self.name)
            return result
        except Exception:
            self.logger.exception("[%s] Failed.", self.name)
            raise

    @abstractmethod
    async def _execute(self, **kwargs: Any) -> Any:
        """Subclasses implement their logic here."""
        ...

    # ── LLM helper ──

    @staticmethod
    def _make_llm_client():
        """Return an AsyncOpenAI client pointed at Ollama or OpenAI."""
        from openai import AsyncOpenAI

        if settings.llm_provider == "ollama":
            return AsyncOpenAI(base_url=settings.ollama_base_url, api_key="ollama")
        return AsyncOpenAI(api_key=settings.openai_api_key)

    async def llm_call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        response_format: Any = None,
    ) -> str:
        """Call the configured LLM.  Returns the assistant message content."""
        client = self._make_llm_client()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        resp = await client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""
        self.memory.append_message("assistant", content)
        return content
