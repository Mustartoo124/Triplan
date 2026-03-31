from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.models.itinerary import Itinerary
from src.models.user_input import UserInput
from src.orchestrator import Orchestrator
from src.orchestrator.planner import validate_itinerary

router = APIRouter(tags=["trip"])
logger = logging.getLogger(__name__)


@router.post("/plan", response_model=Itinerary)
async def plan_trip(user_input: UserInput) -> Itinerary:
    """Generate a multi-day trip itinerary.

    Accepts user preferences and returns an optimised itinerary
    with ordered stops, estimated times, and festival highlights.
    """
    try:
        orchestrator = Orchestrator()
        itinerary = await orchestrator.plan_trip(user_input)

        warnings = validate_itinerary(itinerary, user_input.daily_hours * 60)
        if warnings:
            itinerary.metadata["warnings"] = warnings

        return itinerary
    except Exception as e:
        logger.exception("Trip planning failed.")
        raise HTTPException(status_code=500, detail=str(e))
