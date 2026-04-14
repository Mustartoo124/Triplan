from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env file."""

    # ── Paths ──
    project_root: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    # ── LLM ──
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # Provider: "ollama" uses local Ollama server; "openai" uses OpenAI API
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434/v1"
    # Model used by the conversational ChatAgent (can differ from planning model)
    chat_model: str = "llama3.2"

    # ── Neo4j ──
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # ── Web Search ──
    search_api_key: str = ""
    search_provider: str = "tavily"  # "tavily" | "serpapi"

    # ── Geocoding ──
    google_maps_api_key: str = ""

    # ── App ──
    app_env: str = "development"
    log_level: str = "INFO"

    # ── Trip defaults ──
    default_daily_hours: float = 10.0  # hours available per day
    max_candidates_per_day: int = 8

    # ── Scoring weights (priority order: interest > quality > budget > proximity) ──
    w_interest: float = 0.40
    w_quality: float = 0.30
    w_budget: float = 0.20
    w_proximity: float = 0.10

    # ── Festival bonus ──
    festival_scarcity_bonus: float = 0.10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton – import this everywhere
settings = Settings()
