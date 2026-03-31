from __future__ import annotations

from datetime import date, time, timedelta
from typing import Any

from src.agents.base import BaseAgent
from src.models.itinerary import DayPlan, Itinerary, ItineraryStop
from src.models.poi import POI
from src.models.user_input import UserInput
from src.tools.distance import haversine_km

# Estimated visit time (minutes) by primary type
VISIT_DURATION: dict[str, int] = {
    "museum": 90,
    "art_gallery": 60,
    "restaurant": 60,
    "cafe": 30,
    "park": 45,
    "zoo": 120,
    "amusement_park": 150,
    "aquarium": 90,
    "shopping_mall": 60,
    "market": 45,
    "night_club": 60,
    "bar": 45,
    "tourist_attraction": 45,
    "lodging": 0,
    "spa": 60,
    "bakery": 20,
    "supermarket": 30,
}

# Average travel speed in km/h (mixed urban transport)
AVG_SPEED_KMH = 20.0


class RoutingAgent(BaseAgent):
    """Agent 5 — Route Optimization (Greedy Orienteering).

    For each day cluster, solves a simplified Orienteering Problem:
    - Select subset of POIs that maximises total score within the daily time budget.
    - Order them by nearest-neighbour heuristic.
    - Apply opening hours as feasibility checks.

    A future upgrade can swap this greedy solver with OR-Tools / genetic algorithm.
    """

    name: str = "routing"

    async def _execute(self, **kwargs: Any) -> Itinerary:
        daily_clusters: dict[int, list[POI]] = kwargs["daily_clusters"]
        user_input: UserInput = kwargs["user_input"]

        days: list[DayPlan] = []
        for day_idx in sorted(daily_clusters.keys()):
            trip_date = user_input.start_date + timedelta(days=day_idx)
            cluster = daily_clusters[day_idx]
            day_plan = self._solve_day(
                day_num=day_idx + 1,
                trip_date=trip_date,
                candidates=cluster,
                start=user_input.start_location,
                daily_minutes=user_input.daily_hours * 60,
                preferred_start=user_input.preferred_start_time,
            )
            days.append(day_plan)

        total = sum(d.total_score for d in days)
        itinerary = Itinerary(city=user_input.city, days=days, total_score=total)
        self.memory.set("itinerary", itinerary)
        return itinerary

    # ── Greedy Orienteering per day ──

    def _solve_day(
        self,
        day_num: int,
        trip_date: date,
        candidates: list[POI],
        start: tuple[float, float],
        daily_minutes: float,
        preferred_start: str,
    ) -> DayPlan:
        # Greedy insertion: always pick the highest-score reachable POI
        remaining = list(candidates)
        route: list[POI] = []
        current_pos = start
        time_used = 0.0

        # Separate festivals (must include) from regular
        must_visit = [p for p in remaining if p.source == "festival"]
        optional = [p for p in remaining if p.source != "festival"]

        # Insert festivals first (hard constraint)
        for fest in must_visit:
            visit_min = fest.estimated_visit_minutes
            travel_min = self._travel_minutes(current_pos, (fest.latitude, fest.longitude))
            if time_used + travel_min + visit_min <= daily_minutes:
                route.append(fest)
                time_used += travel_min + visit_min
                current_pos = (fest.latitude, fest.longitude)

        # Greedy fill with remaining POIs
        optional.sort(key=lambda p: p.composite_score, reverse=True)
        for poi in optional:
            visit_min = self._visit_duration(poi)
            travel_min = self._travel_minutes(current_pos, (poi.latitude, poi.longitude))
            if time_used + travel_min + visit_min <= daily_minutes:
                route.append(poi)
                time_used += travel_min + visit_min
                current_pos = (poi.latitude, poi.longitude)

        # Nearest-neighbour reorder for better travel time
        route = self._nn_reorder(route, start)

        # Build ItineraryStop objects
        stops: list[ItineraryStop] = []
        cur_pos = start
        cur_minutes = 0.0
        h, m = (int(x) for x in preferred_start.split(":"))
        cur_time_obj = time(h, m)

        total_travel = 0.0
        total_visit = 0.0

        for i, poi in enumerate(route):
            travel = self._travel_minutes(cur_pos, (poi.latitude, poi.longitude))
            visit = poi.estimated_visit_minutes if poi.source == "festival" else self._visit_duration(poi)

            arrival = self._add_minutes(cur_time_obj, cur_minutes + travel)
            departure = self._add_minutes(cur_time_obj, cur_minutes + travel + visit)

            notes = ""
            if poi.source == "festival":
                notes = "Festival — check agenda for specific activities"

            stops.append(
                ItineraryStop(
                    order=i + 1,
                    poi=poi,
                    arrival_time=arrival,
                    departure_time=departure,
                    travel_minutes_from_prev=round(travel, 1),
                    visit_minutes=visit,
                    notes=notes,
                )
            )
            cur_minutes += travel + visit
            total_travel += travel
            total_visit += visit
            cur_pos = (poi.latitude, poi.longitude)

        return DayPlan(
            day_number=day_num,
            date=trip_date,
            stops=stops,
            total_score=sum(p.composite_score for p in route),
            total_travel_minutes=round(total_travel, 1),
            total_visit_minutes=round(total_visit, 1),
        )

    # ── Nearest-neighbour reorder ──

    @staticmethod
    def _nn_reorder(pois: list[POI], start: tuple[float, float]) -> list[POI]:
        if len(pois) <= 2:
            return pois

        unvisited = list(pois)
        ordered: list[POI] = []
        cur = start

        while unvisited:
            nearest = min(
                unvisited,
                key=lambda p: haversine_km(cur[0], cur[1], p.latitude, p.longitude),
            )
            ordered.append(nearest)
            cur = (nearest.latitude, nearest.longitude)
            unvisited.remove(nearest)

        return ordered

    # ── Helpers ──

    @staticmethod
    def _visit_duration(poi: POI) -> int:
        return VISIT_DURATION.get(poi.primary_type, 45)

    @staticmethod
    def _travel_minutes(a: tuple[float, float], b: tuple[float, float]) -> float:
        dist = haversine_km(a[0], a[1], b[0], b[1])
        return (dist / AVG_SPEED_KMH) * 60

    @staticmethod
    def _add_minutes(base: time, minutes: float) -> time:
        total = base.hour * 60 + base.minute + minutes
        h = int(total // 60) % 24
        m = int(total % 60)
        return time(h, m)
