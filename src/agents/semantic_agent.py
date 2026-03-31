from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent
from src.config import settings
from src.models.poi import POI
from src.models.user_input import UserInput
from src.tools.knowledge_graph import KnowledgeGraphClient


class SemanticAgent(BaseAgent):
    """Agent 2 — Knowledge-Graph Semantic Matching.

    Expands user interests via KG ontology, then scores each candidate POI
    on `interest_fit` (0–1).  Filters out POIs with zero relevance.
    """

    name: str = "semantic"

    def __init__(self, kg: KnowledgeGraphClient | None = None, **kw: Any) -> None:
        super().__init__(**kw)
        self.kg = kg or KnowledgeGraphClient()

    async def _execute(self, **kwargs: Any) -> list[POI]:
        candidates: list[POI] = kwargs["candidates"]
        user_input: UserInput = kwargs["user_input"]

        # Step 1: expand interests → low-level category set
        expanded = await self._expand_interests(user_input.interests)
        self.logger.info(
            "Expanded %d interests → %d categories.",
            len(user_input.interests),
            len(expanded),
        )

        # Step 2: score each candidate
        matched: list[POI] = []
        for poi in candidates:
            score = self._compute_interest_fit(poi, expanded)

            # Festival scarcity bonus
            if poi.source == "festival":
                score = min(1.0, score + settings.festival_scarcity_bonus)

            if score > 0.0:
                poi.interest_fit = score
                matched.append(poi)

        self.logger.info("Semantic filter: %d / %d candidates matched.", len(matched), len(candidates))
        self.memory.set("matched_candidates", matched)
        return matched

    # ── KG interest expansion ──

    async def _expand_interests(self, interests: list[str]) -> set[str]:
        """Query KG to expand high-level interests to low-level types.

        Example: 'Asian food' → {'ramen_restaurant', 'sushi_restaurant',
                 'vietnamese_restaurant', 'restaurant', 'food', …}
        """
        all_types: set[str] = set()
        for interest in interests:
            related = await self.kg.expand_category(interest)
            all_types.update(related)
        return all_types

    # ── Interest fit scoring ──

    @staticmethod
    def _compute_interest_fit(poi: POI, expanded_types: set[str]) -> float:
        """Jaccard-like overlap between POI types and expanded interest set."""
        if not poi.types or not expanded_types:
            return 0.0

        poi_set = set(poi.types)
        # Remove generic types that would inflate overlap
        generic = {"establishment", "point_of_interest"}
        poi_meaningful = poi_set - generic
        if not poi_meaningful:
            poi_meaningful = poi_set

        overlap = poi_meaningful & expanded_types
        if not overlap:
            return 0.0

        # Weighted Jaccard: |intersection| / |poi_types|
        return len(overlap) / len(poi_meaningful)
