"""Re-planning and validation utilities for the orchestrator."""

from __future__ import annotations

from src.models.itinerary import DayPlan, Itinerary


def validate_itinerary(itinerary: Itinerary, daily_minutes: float) -> list[str]:
    """Return a list of warnings for an itinerary (empty = all good)."""
    warnings: list[str] = []

    for day in itinerary.days:
        if day.total_time_minutes > daily_minutes:
            warnings.append(
                f"Day {day.day_number}: over time budget by "
                f"{day.total_time_minutes - daily_minutes:.0f} min."
            )
        if not day.stops:
            warnings.append(f"Day {day.day_number}: no stops planned.")

    return warnings
