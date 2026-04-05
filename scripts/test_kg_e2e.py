"""End-to-end test: KG expansion → POI matching.

Simulates what the SemanticAgent will do:
  1. Expand user interests via KG
  2. Match expanded types against POI data
  3. Show how many POIs match and sample results
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.knowledge_graph import KnowledgeGraphClient
from src.config import settings


def load_pois():
    poi_path = settings.data_dir / "hcm_poi.json"
    with open(poi_path, encoding="utf-8") as f:
        return json.load(f)


def match_pois(pois: list[dict], target_types: set[str]) -> list[dict]:
    """Return POIs where at least one of their types matches target_types."""
    matched = []
    for poi in pois:
        poi_types = set(poi.get("types", []))
        overlap = poi_types & target_types
        if overlap:
            matched.append({**poi, "_matched_types": list(overlap)})
    return matched


async def test_e2e():
    kg = KnowledgeGraphClient()
    pois = load_pois()
    print(f"Loaded {len(pois)} POIs from hcm_poi.json\n")

    # Simulate user interests
    user_interests = ["nightlife", "museum", "coffee", "kid friendly", "sushi"]

    for interest in user_interests:
        result = await kg.expand_interest(interest)
        target_types = result["types"]

        matched = match_pois(pois, target_types)

        # Sort by rating (descending), filter nulls
        rated = [p for p in matched if p.get("rating") is not None]
        rated.sort(key=lambda p: (p["rating"], p.get("userRatingCount", 0)), reverse=True)

        print(f'═══ Interest: "{interest}" ═══')
        print(f'  KG source: {result["source"]}')
        print(f"  Expanded types: {sorted(target_types)}")
        print(f"  Matched POIs: {len(matched)} / {len(pois)}")
        print(f"  Top 5 matches:")

        for p in rated[:5]:
            name = p["name"][:35]
            rating = p.get("rating", "?")
            count = p.get("userRatingCount", 0)
            ptype = p.get("primaryType", "?")
            matched_t = p["_matched_types"]
            print(f"    {name:<36} | {ptype:<20} | ★{rating} ({count:>5} reviews) | matched: {matched_t}")

        print()

    await kg.close()
    print("End-to-end test complete!")


if __name__ == "__main__":
    asyncio.run(test_e2e())
