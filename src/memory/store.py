from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MemoryStore:
    """Lightweight agent memory with short-term and long-term storage.

    Short-term: per-request scratchpad (lives only during one planning run).
    Long-term:  persisted to a JSON file so agents can learn across runs
                (e.g. cached geocoding results, festival enrichment cache).
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        # Short-term: reset every planning run
        self._short_term: dict[str, Any] = {}
        # Long-term: loaded from / saved to disk
        self._persist_path = persist_path
        self._long_term: dict[str, Any] = self._load_long_term()

    # ── Short-term (per-request) ──

    def set(self, key: str, value: Any) -> None:
        self._short_term[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._short_term.get(key, default)

    def clear_short_term(self) -> None:
        self._short_term.clear()

    # ── Long-term (persisted) ──

    def cache_get(self, namespace: str, key: str) -> Any | None:
        return self._long_term.get(namespace, {}).get(key)

    def cache_set(self, namespace: str, key: str, value: Any) -> None:
        self._long_term.setdefault(namespace, {})[key] = {
            "value": value,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_long_term()

    # ── Conversation history (for LLM agents) ──

    def append_message(self, role: str, content: str) -> None:
        history = self._short_term.setdefault("messages", [])
        history.append({"role": role, "content": content})

    def get_messages(self) -> list[dict]:
        return self._short_term.get("messages", [])

    def clear_messages(self) -> None:
        self._short_term["messages"] = []

    # ── Persistence helpers ──

    def _load_long_term(self) -> dict[str, Any]:
        if self._persist_path and self._persist_path.exists():
            try:
                return json.loads(self._persist_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not load long-term memory from %s", self._persist_path)
        return {}

    def _save_long_term(self) -> None:
        if self._persist_path:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(
                json.dumps(self._long_term, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
