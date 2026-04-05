"""Seed the Neo4j Knowledge Graph with the category ontology.

This script builds the IS_SUBCATEGORY_OF hierarchy that powers
semantic matching in Layer 1.  It also loads POI nodes with their
HAS_TYPE relationships so the KG can answer queries like:
  "Which Google Maps types match 'Asian food'?"

Run:
    python scripts/seed_knowledge_graph.py

Schema created:
    (:ParentCategory {name})
    (:Category {name})
    (:PlaceType {name})
    (:PlaceType)-[:BELONGS_TO]->(:Category)
    (:Category)-[:IS_SUBCATEGORY_OF]->(:ParentCategory)
    (:ParentCategory)-[:IS_SUBCATEGORY_OF]->(:ParentCategory)  # multi-level
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo4j import GraphDatabase
from src.config import settings


# ══════════════════════════════════════════════════════════════
# ONTOLOGY DEFINITION
# ══════════════════════════════════════════════════════════════
# This is the hand-crafted ontology mapping Google Maps types
# upward to human-level interest categories.
#
# Structure: {ParentCategory: {Category: [PlaceType, ...]}}
# where PlaceType values are actual Google Maps type strings
# found in your hcm_poi.json data.
# ══════════════════════════════════════════════════════════════

ONTOLOGY = {
    # ── Level 0: Top-level interest groups ──
    "Dining": {
        "Vietnamese Food": [
            "restaurant",
            "food",
        ],
        "Asian Food": [
            "restaurant",
            "food",
        ],
        "Japanese Food": [
            "restaurant",
            "food",
        ],
        "Western Food": [
            "restaurant",
            "food",
        ],
        "Street Food": [
            "restaurant",
            "food",
            "meal_takeaway",
        ],
        "Fine Dining": [
            "restaurant",
            "food",
        ],
        "Fast Food": [
            "restaurant",
            "food",
            "meal_delivery",
            "meal_takeaway",
        ],
        "Bakery & Dessert": [
            "bakery",
            "food",
            "store",
        ],
        "Coffee & Cafe": [
            "cafe",
            "food",
            "store",
        ],
        "Delivery Food": [
            "meal_delivery",
            "meal_takeaway",
        ],
    },
    "Nightlife": {
        "Bar & Pub": [
            "bar",
            "food",
        ],
        "Club & Lounge": [
            "night_club",
            "bar",
        ],
        "Cocktail Bar": [
            "bar",
        ],
    },
    "Culture & History": {
        "Museum": [
            "museum",
        ],
        "Art Gallery": [
            "art_gallery",
        ],
        "Religious Site": [
            "place_of_worship",
            "church",
            "mosque",
        ],
        "Historical Landmark": [
            "tourist_attraction",
            "museum",
        ],
    },
    "Shopping": {
        "Mall & Department Store": [
            "shopping_mall",
            "department_store",
        ],
        "Market & Bazaar": [
            "market",
        ],
        "Grocery & Supermarket": [
            "supermarket",
            "grocery_or_supermarket",
            "convenience_store",
        ],
        "Fashion & Clothing": [
            "clothing_store",
            "shoe_store",
            "store",
        ],
        "Electronics": [
            "electronics_store",
            "store",
        ],
        "Books & Media": [
            "book_store",
            "store",
        ],
        "Home & Furniture": [
            "home_goods_store",
            "furniture_store",
        ],
        "Jewelry": [
            "jewelry_store",
            "store",
        ],
    },
    "Nature & Outdoors": {
        "Park & Garden": [
            "park",
        ],
        "Zoo & Aquarium": [
            "zoo",
            "aquarium",
        ],
        "Amusement Park": [
            "amusement_park",
        ],
        "Camping": [
            "campground",
        ],
    },
    "Wellness & Relaxation": {
        "Spa & Massage": [
            "spa",
            "beauty_salon",
            "health",
        ],
        "Fitness": [
            "gym",
            "health",
        ],
        "Hair & Beauty": [
            "hair_care",
            "beauty_salon",
        ],
    },
    "Accommodation": {
        "Hotel & Resort": [
            "lodging",
        ],
    },
    "Tourism & Sightseeing": {
        "Tourist Attraction": [
            "tourist_attraction",
        ],
        "Tour & Travel Agency": [
            "travel_agency",
        ],
    },
    "Entertainment": {
        "Casino & Gaming": [
            "casino",
        ],
        "Theme Park": [
            "amusement_park",
        ],
    },
}

# Additional cross-category synonym mappings:
# These let users say things like "seafood", "ramen", "sushi"
# and still match even though Google Maps lacks those exact types.
INTEREST_SYNONYMS = {
    "seafood": ["restaurant", "food"],
    "ramen": ["restaurant", "food"],
    "sushi": ["restaurant", "food"],
    "pho": ["restaurant", "food"],
    "banh mi": ["restaurant", "food", "bakery"],
    "bubble tea": ["cafe", "food"],
    "beer": ["bar", "food"],
    "wine": ["bar", "restaurant"],
    "temple": ["place_of_worship"],
    "pagoda": ["place_of_worship"],
    "church": ["church", "place_of_worship"],
    "mosque": ["mosque", "place_of_worship"],
    "cinema": ["establishment"],
    "library": ["library"],
    "bookstore": ["book_store"],
    "souvenir": ["store", "market"],
    "local market": ["market"],
    "food court": ["restaurant", "food", "shopping_mall"],
    "family fun": ["amusement_park", "zoo", "aquarium", "park"],
    "photography": ["tourist_attraction", "park", "art_gallery"],
    "architecture": ["tourist_attraction", "museum", "place_of_worship"],
    "romantic": ["restaurant", "cafe", "park", "spa"],
    "kid friendly": ["zoo", "aquarium", "amusement_park", "park"],
}


def create_constraints(tx):
    """Create uniqueness constraints for node types."""
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:ParentCategory) REQUIRE n.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Category) REQUIRE n.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:PlaceType) REQUIRE n.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Synonym) REQUIRE n.name IS UNIQUE")


def clear_graph(tx):
    """Remove all existing ontology nodes and relationships."""
    tx.run("MATCH (n) WHERE n:ParentCategory OR n:Category OR n:PlaceType OR n:Synonym DETACH DELETE n")


def seed_ontology(tx):
    """Create the full ontology tree."""
    for parent_name, categories in ONTOLOGY.items():
        # Create ParentCategory
        tx.run(
            "MERGE (p:ParentCategory {name: $name})",
            name=parent_name,
        )

        for cat_name, place_types in categories.items():
            # Create Category
            tx.run(
                "MERGE (c:Category {name: $name})",
                name=cat_name,
            )
            # Link Category -> ParentCategory
            tx.run(
                """
                MATCH (c:Category {name: $cat}), (p:ParentCategory {name: $parent})
                MERGE (c)-[:IS_SUBCATEGORY_OF]->(p)
                """,
                cat=cat_name,
                parent=parent_name,
            )

            for pt in place_types:
                # Create PlaceType
                tx.run(
                    "MERGE (t:PlaceType {name: $name})",
                    name=pt,
                )
                # Link PlaceType -> Category
                tx.run(
                    """
                    MATCH (t:PlaceType {name: $type}), (c:Category {name: $cat})
                    MERGE (t)-[:BELONGS_TO]->(c)
                    """,
                    type=pt,
                    cat=cat_name,
                )


def seed_synonyms(tx):
    """Create synonym nodes for fuzzy user input matching."""
    for synonym, place_types in INTEREST_SYNONYMS.items():
        tx.run(
            "MERGE (s:Synonym {name: $name})",
            name=synonym,
        )
        for pt in place_types:
            tx.run(
                "MERGE (t:PlaceType {name: $pt_name})",
                pt_name=pt,
            )
            tx.run(
                """
                MATCH (s:Synonym {name: $syn}), (t:PlaceType {name: $pt_name})
                MERGE (s)-[:MAPS_TO]->(t)
                """,
                syn=synonym,
                pt_name=pt,
            )


def print_stats(session):
    """Print what was created."""
    counts = {}
    for label in ["ParentCategory", "Category", "PlaceType", "Synonym"]:
        result = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
        counts[label] = result.single()["cnt"]

    rel_count = session.run(
        "MATCH ()-[r]->() WHERE type(r) IN ['IS_SUBCATEGORY_OF', 'BELONGS_TO', 'MAPS_TO'] RETURN count(r) AS cnt"
    ).single()["cnt"]

    print("\n═══ Knowledge Graph Stats ═══")
    print(f"  ParentCategories : {counts['ParentCategory']}")
    print(f"  Categories       : {counts['Category']}")
    print(f"  PlaceTypes       : {counts['PlaceType']}")
    print(f"  Synonyms         : {counts['Synonym']}")
    print(f"  Relationships    : {rel_count}")
    print("═════════════════════════════\n")


def test_expansion(session, interest: str):
    """Test an expansion query — same logic the agent will use."""
    # Try Category match first
    result = session.run(
        """
        MATCH (c:Category)
        WHERE toLower(c.name) CONTAINS toLower($interest)
        MATCH (t:PlaceType)-[:BELONGS_TO]->(c)
        RETURN collect(DISTINCT t.name) AS types, collect(DISTINCT c.name) AS categories
        """,
        interest=interest,
    )
    record = result.single()
    types = record["types"]
    cats = record["categories"]

    if types:
        print(f'  "{interest}" → categories: {cats} → types: {types}')
        return

    # Try ParentCategory
    result = session.run(
        """
        MATCH (p:ParentCategory)
        WHERE toLower(p.name) CONTAINS toLower($interest)
        MATCH (c:Category)-[:IS_SUBCATEGORY_OF]->(p)
        MATCH (t:PlaceType)-[:BELONGS_TO]->(c)
        RETURN collect(DISTINCT t.name) AS types,
               collect(DISTINCT c.name) AS categories,
               collect(DISTINCT p.name) AS parents
        """,
        interest=interest,
    )
    record = result.single()
    types = record["types"]

    if types:
        print(f'  "{interest}" → parents: {record["parents"]} → categories: {record["categories"]} → types: {types}')
        return

    # Try Synonym
    result = session.run(
        """
        MATCH (s:Synonym)
        WHERE toLower(s.name) = toLower($interest)
        MATCH (s)-[:MAPS_TO]->(t:PlaceType)
        RETURN collect(DISTINCT t.name) AS types
        """,
        interest=interest,
    )
    record = result.single()
    types = record["types"]

    if types:
        print(f'  "{interest}" (synonym) → types: {types}')
    else:
        print(f'  "{interest}" → NO MATCH')


def main():
    print("Connecting to Neo4j at", settings.neo4j_uri, "...")
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    driver.verify_connectivity()
    print("Connected!\n")

    with driver.session() as session:
        print("Creating constraints...")
        session.execute_write(create_constraints)

        print("Clearing existing ontology...")
        session.execute_write(clear_graph)

        print("Seeding ontology tree...")
        session.execute_write(seed_ontology)

        print("Seeding synonym mappings...")
        session.execute_write(seed_synonyms)

        print_stats(session)

        # ── Test queries ──
        print("Testing category expansion queries:")
        test_interests = [
            "food",           # top-level → should expand to many types
            "Asian food",     # mid-level category
            "coffee",         # mid-level category
            "nightlife",      # parent category → all bars + clubs
            "museum",         # specific category
            "shopping",       # parent category
            "nature",         # parent category
            "sushi",          # synonym
            "pho",            # synonym
            "temple",         # synonym
            "romantic",       # synonym
            "kid friendly",   # synonym
            "Korean food",    # no match expected
        ]

        for interest in test_interests:
            test_expansion(session, interest)

    driver.close()
    print("\nDone! Knowledge Graph is ready.")


if __name__ == "__main__":
    main()
