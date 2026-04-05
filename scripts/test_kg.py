"""Quick test for KnowledgeGraphClient against live Neo4j."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.knowledge_graph import KnowledgeGraphClient


async def test():
    kg = KnowledgeGraphClient()

    test_cases = [
        "food",
        "Asian food",
        "nightlife",
        "museum",
        "shopping",
        "nature",
        "coffee",
        "sushi",
        "pho",
        "temple",
        "romantic",
        "kid friendly",
        "Korean food",
        "wellness",
        "bar",
        "Fine Dining",
    ]

    print(f"{'Interest':<16} | {'Source':<18} | {'Categories':<40} | Types")
    print("-" * 130)

    for interest in test_cases:
        result = await kg.expand_interest(interest)
        src = result["source"]
        cats = ", ".join(result["categories"][:3]) or "-"
        types = ", ".join(sorted(result["types"]))
        print(f"{interest:<16} | {src:<18} | {cats:<40} | {types}")

    await kg.close()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(test())
