from __future__ import annotations

import math
from typing import Any

from src.agents.base import BaseAgent
from src.config import settings
from src.models.poi import POI
from src.models.user_input import UserInput
from src.tools.distance import haversine_km


class ScoringAgent(BaseAgent):
    """Agent 3 — Multi-Criteria Decision Making (MCDM) Scoring.

    Computes composite score per POI:
        Score(p) = w1·InterestFit + w2·QualityScore + w3·BudgetFit + w4·ProximityScore
    """

    name: str = "scoring"

    async def _execute(self, **kwargs: Any) -> list[POI]:
        candidates: list[POI] = kwargs["candidates"]
        user_input: UserInput = kwargs["user_input"]

        if not candidates:
            return []

        # Pre-compute normalisation bounds
        max_dist = self._max_distance(candidates, user_input.start_location)

        for poi in candidates:
            poi.quality_score = self._quality_score(poi)
            poi.budget_fit = self._budget_fit(poi, user_input.budget_level)
            poi.proximity_score = self._proximity_score(
                poi, user_input.start_location, max_dist
            )
            poi.composite_score = (
                settings.w_interest * poi.interest_fit
                + settings.w_quality * poi.quality_score
                + settings.w_budget * poi.budget_fit
                + settings.w_proximity * poi.proximity_score
            )

        # Sort descending by composite score
        candidates.sort(key=lambda p: p.composite_score, reverse=True)

        self.memory.set("scored_candidates", candidates)
        return candidates

    # ── Quality: Bayesian average ──

    @staticmethod
    def _quality_score(poi: POI) -> float:
        """Bayesian-style quality: rating × log(1 + count), normalised to 0–1."""
        if poi.rating is None or poi.user_rating_count is None:
            return 0.3  # neutral default for festivals / unrated POIs

        raw = poi.rating * math.log(1 + poi.user_rating_count)
        # Empirical max ≈ 5 × log(1+80000) ≈ 56.5
        return min(raw / 56.5, 1.0)

    # ── Budget fit ──

    @staticmethod
    def _budget_fit(poi: POI, user_budget: int) -> float:
        """1.0 if within budget, 0.5 if one level over, 0.0 if far over."""
        if poi.price_level is None:
            return 0.8  # assume moderate for unknowns
        diff = poi.price_level - user_budget
        if diff <= 0:
            return 1.0
        if diff == 1:
            return 0.5
        return 0.0

    # ── Proximity ──

    @staticmethod
    def _proximity_score(
        poi: POI, start: tuple[float, float], max_dist: float
    ) -> float:
        """Inverse normalised distance from start location."""
        if max_dist == 0:
            return 1.0
        dist = haversine_km(start[0], start[1], poi.latitude, poi.longitude)
        return 1.0 - (dist / max_dist)

    @staticmethod
    def _max_distance(pois: list[POI], start: tuple[float, float]) -> float:
        if not pois:
            return 1.0
        return max(
            haversine_km(start[0], start[1], p.latitude, p.longitude)
            for p in pois
        )
