"""Knowledge Graph client — wraps Neo4j for ontological queries.

This is the interface that the SemanticAgent uses.  The actual KG schema
(nodes, relationships) is constructed by scripts/seed_knowledge_graph.py.
This module only reads from the graph.

Schema:
    (:ParentCategory {name})
    (:Category {name})-[:IS_SUBCATEGORY_OF]->(:ParentCategory)
    (:PlaceType {name})-[:BELONGS_TO]->(:Category)
    (:Synonym {name})-[:MAPS_TO]->(:PlaceType)
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
                self._driver.verify_connectivity()
            except Exception as e:
                logger.warning("Neo4j connection failed: %s. Using fallback.", e)
                return None
        return self._driver

    async def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None

    # ── Queries ──

    async def expand_interest(self, interest: str) -> dict:
        """Expand a user interest into Google Maps types.

        Tries in order:
          1. Category match  (e.g., "Asian Food" → types)
          2. ParentCategory match (e.g., "Nightlife" → all child types)
          3. Synonym match   (e.g., "sushi" → types)
          4. Fallback static ontology

        Returns dict with keys: types (set), categories (list), source (str)
        """
        driver = self._get_driver()
        if driver is None:
            return {
                "types": self._fallback_expand(interest),
                "categories": [],
                "source": "fallback",
            }

        try:
            # 1. Try Category match
            result = self._query_category(driver, interest)
            if result["types"]:
                result["source"] = "category"
                return result

            # 2. Try ParentCategory match
            result = self._query_parent_category(driver, interest)
            if result["types"]:
                result["source"] = "parent_category"
                return result

            # 3. Try Synonym match
            result = self._query_synonym(driver, interest)
            if result["types"]:
                result["source"] = "synonym"
                return result

        except Exception as e:
            logger.warning("KG query failed: %s. Using fallback.", e)

        return {
            "types": self._fallback_expand(interest),
            "categories": [],
            "source": "fallback",
        }

    async def expand_category(
        self, interest: str, max_depth: int = 3
    ) -> set[str]:
        """Simplified interface — returns just the set of types."""
        result = await self.expand_interest(interest)
        return result["types"]

    # ── Private query methods ──

    @staticmethod
    def _query_category(driver, interest: str) -> dict:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (c:Category)
                WHERE toLower(c.name) CONTAINS toLower($interest)
                MATCH (t:PlaceType)-[:BELONGS_TO]->(c)
                RETURN collect(DISTINCT t.name) AS types,
                       collect(DISTINCT c.name) AS categories
                """,
                interest=interest,
            ).single()
            return {
                "types": set(record["types"]),
                "categories": record["categories"],
            }

    @staticmethod
    def _query_parent_category(driver, interest: str) -> dict:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (p:ParentCategory)
                WHERE toLower(p.name) CONTAINS toLower($interest)
                MATCH (c:Category)-[:IS_SUBCATEGORY_OF]->(p)
                MATCH (t:PlaceType)-[:BELONGS_TO]->(c)
                RETURN collect(DISTINCT t.name) AS types,
                       collect(DISTINCT c.name) AS categories
                """,
                interest=interest,
            ).single()
            return {
                "types": set(record["types"]),
                "categories": record["categories"],
            }

    @staticmethod
    def _query_synonym(driver, interest: str) -> dict:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (s:Synonym)
                WHERE toLower(s.name) = toLower($interest)
                MATCH (s)-[:MAPS_TO]->(t:PlaceType)
                RETURN collect(DISTINCT t.name) AS types
                """,
                interest=interest,
            ).single()
            return {
                "types": set(record["types"]),
                "categories": [],
            }

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
