from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class UserInput(BaseModel):
    """Structured user request for trip planning."""

    # Required
    interests: list[str]                  # e.g. ["Asian food", "museums", "nightlife"]
    start_date: date
    end_date: date
    start_location: tuple[float, float]   # (latitude, longitude)

    # Budget: 0=free, 1=cheap, 2=moderate, 3=expensive, 4=luxury
    budget_level: int = Field(2, ge=0, le=4)

    # Optional overrides
    daily_hours: float = 10.0             # hours available per day
    max_places_per_day: int = 8
    preferred_start_time: str = "09:00"
    preferred_end_time: str = "21:00"

    @property
    def num_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def city(self) -> str:
        """Placeholder – extend for multi-city support."""
        return "hcm"
