"""Knowledge Graph client — wraps Neo4j for ontological queries.

This is the interface that the SemanticAgent uses.  The actual KG schema
(nodes, relationships) should be constructed separately via a data-loading
script.  This module only reads from the graph.

Expected KG schema:
    (:Category {name})
    (:Category)-[:IS_SUBCATEGORY_OF]->(:ParentCategory)
    (:PlaceType {name})-[:BELONGS_TO]->(:Category)
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


class KnowledgeGraphClient:
    """Thin wrapper over Neo4j for category expansion queries."""

    def __init__(self) -> None:
        self._driver = None

    # ── Lazy connection ──

    def _get_driver(self) -> Any:
        if self._driver is None:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
            except Exception as e:
                logger.warning("Neo4j connection failed: %s. Using fallback.", e)
                return None
        return self._driver

    async def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None

    # ── Queries ──

    async def expand_category(
        self, interest: str, max_depth: int = 3
    ) -> set[str]:
        """Expand a user interest into low-level Google Maps types.

        Traverses IS_SUBCATEGORY_OF relationships up to max_depth hops.
        Falls back to a static mapping when Neo4j is unavailable.
        """
        driver = self._get_driver()
        if driver is None:
            return self._fallback_expand(interest)

        try:
            query = """
            MATCH (start:Category)
            WHERE toLower(start.name) CONTAINS toLower($interest)
            CALL apoc.path.subgraphNodes(start, {
                relationshipFilter: '<IS_SUBCATEGORY_OF',
                maxLevel: $depth
            }) YIELD node
            RETURN collect(DISTINCT node.name) AS types
            """
            with driver.session() as session:
                result = session.run(query, interest=interest, depth=max_depth)
                record = result.single()
                if record:
                    return set(record["types"])
        except Exception as e:
            logger.warning("KG query failed: %s. Using fallback.", e)

        return self._fallback_expand(interest)

    # ── Static fallback ontology ──

    @staticmethod
    def _fallback_expand(interest: str) -> set[str]:
        """Hardcoded ontology for when Neo4j is not available.

        This keeps the system functional during development.
        Extend this mapping as you build out the KG.
        """
        interest_lower = interest.lower()

        ONTOLOGY: dict[str, set[str]] = {
            "food": {
                "restaurant", "cafe", "bakery", "bar", "food",
                "meal_delivery", "meal_takeaway", "supermarket",
            },
            "asian food": {
                "restaurant", "food", "meal_delivery", "meal_takeaway",
            },
            "vietnamese food": {
                "restaurant", "food", "meal_delivery", "meal_takeaway",
            },
            "japanese food": {
                "restaurant", "food",
            },
            "nightlife": {
                "bar", "night_club",
            },
            "culture": {
                "museum", "art_gallery", "tourist_attraction",
                "place_of_worship",
            },
            "art": {
                "art_gallery", "museum",
            },
            "museum": {
                "museum",
            },
            "shopping": {
                "shopping_mall", "department_store", "market",
                "clothing_store", "store", "supermarket",
            },
            "nature": {
                "park", "zoo", "amusement_park", "aquarium",
                "campground",
            },
            "park": {
                "park",
            },
            "relaxation": {
                "spa", "beauty_salon", "park", "cafe",
            },
            "coffee": {
                "cafe",
            },
            "history": {
                "museum", "tourist_attraction", "place_of_worship",
            },
            "adventure": {
                "amusement_park", "zoo", "aquarium", "campground",
            },
        }

        # Direct match
        if interest_lower in ONTOLOGY:
            return ONTOLOGY[interest_lower]

        # Partial match
        for key, types in ONTOLOGY.items():
            if key in interest_lower or interest_lower in key:
                return types

        # Default: return the interest itself as a type
        return {interest_lower.replace(" ", "_")}
