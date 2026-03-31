from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class FestivalMeta(BaseModel):
    """Extra metadata enriched by the Festival Agent."""

    original_time: str = ""
    agenda: str = ""
    description: str = ""
    url: str = ""
    estimated_visit_minutes: int = 120


class RawFestival(BaseModel):
    """Direct mapping of HCM_FEST.json entries."""

    name: str
    commune: str = ""
    ward: str = ""
    province: str = ""
    time: str = ""
    description: str = ""


class Festival(BaseModel):
    """Festival after enrichment – carries parsed dates, location, and meta."""

    id: str = ""
    name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: str = ""
    ward: str = ""
    district: str = ""
    province: str = ""
    types: list[str] = Field(default_factory=list)
    price_level: int = 0
    price_range: str = "Free"
    description: str = ""
    meta: FestivalMeta = Field(default_factory=FestivalMeta)
