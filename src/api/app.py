from __future__ import annotations

import logging

from fastapi import FastAPI

from src.api.middleware import setup_middleware
from src.api.routes import chat, health, trip
from src.config import settings


def create_app() -> FastAPI:
    """Application factory — build and return the FastAPI instance."""

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    )

    app = FastAPI(
        title="Triplan — AI Trip Planner",
        version="0.1.0",
        description="Agentic AI system for multi-day trip itinerary generation.",
    )

    setup_middleware(app)
    app.include_router(health.router)
    app.include_router(trip.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")

    return app
