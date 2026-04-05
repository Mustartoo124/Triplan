"""Test all 5 agents end-to-end.

Simulates the orchestrator pipeline:
  User Input → Agent 1 (Festival) → Agent 2 (Semantic) → Agent 3 (Scoring)
             → Agent 4 (Clustering) → Agent 5 (Routing) → Itinerary

Usage:
    python scripts/test_agents.py
"""

import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.memory.store import MemoryStore
from src.models.poi import POI
from src.models.user_input import UserInput
from src.tools.knowledge_graph import KnowledgeGraphClient

# ── Logging setup ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_agents")


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def load_pois() -> list[POI]:
    """Load POIs from JSON and parse into Pydantic models."""
    poi_path = settings.data_dir / "hcm_poi.json"
    with open(poi_path, encoding="utf-8") as f:
        raw = json.load(f)
    pois = []
    for entry in raw:
        try:
            pois.append(POI(**entry))
        except Exception as e:
            logger.debug("Skipping POI: %s", e)
    return pois


def load_festivals() -> list[dict]:
    fest_path = settings.data_dir / "HCM_FEST.json"
    with open(fest_path, encoding="utf-8") as f:
        return json.load(f)


def print_header(title: str):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print(f"{'═' * 70}")


def print_poi_table(pois: list[POI], limit: int = 10, title: str = ""):
    if title:
        print(f"\n  {title}")
    print(f"  {'Name':<35} {'Type':<20} {'Score':>6} {'IntFit':>6} {'Qual':>6} {'Budg':>6} {'Prox':>6}")
    print(f"  {'-'*35} {'-'*20} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
    for p in pois[:limit]:
        src_tag = " [F]" if p.source == "festival" else ""
        print(
            f"  {(p.name[:32] + src_tag):<35} {p.primary_type:<20} "
            f"{p.composite_score:>6.3f} {p.interest_fit:>6.3f} {p.quality_score:>6.3f} "
            f"{p.budget_fit:>6.3f} {p.proximity_score:>6.3f}"
        )
    if len(pois) > limit:
        print(f"  ... and {len(pois) - limit} more")


# ═══════════════════════════════════════════════════════════════
# Main test
# ═══════════════════════════════════════════════════════════════

async def main():
    # ── Shared resources ──
    memory = MemoryStore()
    kg = KnowledgeGraphClient()

    # ── User Input ──
    user_input = UserInput(
        interests=["Vietnamese food", "museum", "coffee", "nightlife"],
        start_date=date(2026, 3, 26),
        end_date=date(2026, 3, 28),
        start_location=(10.7769, 106.7009),  # Ben Thanh Market area
        budget_level=2,  # moderate
        daily_hours=10.0,
        max_places_per_day=8,
        preferred_start_time="09:00",
    )

    print_header("USER INPUT")
    print(f"  Interests:     {user_input.interests}")
    print(f"  Trip:          {user_input.start_date} → {user_input.end_date} ({user_input.num_days} days)")
    print(f"  Budget level:  {user_input.budget_level} (moderate)")
    print(f"  Start:         {user_input.start_location}")
    print(f"  Daily hours:   {user_input.daily_hours}h")

    # ── Load data ──
    pois = load_pois()
    raw_festivals = load_festivals()
    logger.info("Loaded %d POIs and %d festivals", len(pois), len(raw_festivals))

    # ══════════════════════════════════════════════════════════
    # AGENT 1: Festival Enrichment
    # ══════════════════════════════════════════════════════════
    print_header("AGENT 1: Festival Enrichment")

    from src.agents.festival_agent import FestivalAgent

    fest_agent = FestivalAgent(memory=memory)
    enriched_festivals = await fest_agent.run(
        raw_festivals=raw_festivals,
        user_input=user_input,
    )

    print(f"\n  Festivals overlapping trip dates: {len(enriched_festivals)}")
    for f in enriched_festivals:
        print(f"    • {f.name[:50]:<52} lat={f.latitude:.4f} lng={f.longitude:.4f}  types={f.types[:3]}")

    # Merge into unified candidate pool
    candidates = pois + enriched_festivals
    print(f"\n  Total candidate pool: {len(candidates)} ({len(pois)} POIs + {len(enriched_festivals)} festivals)")

    # ══════════════════════════════════════════════════════════
    # AGENT 2: Semantic Matching
    # ══════════════════════════════════════════════════════════
    print_header("AGENT 2: Semantic Matching (KG)")

    from src.agents.semantic_agent import SemanticAgent

    sem_agent = SemanticAgent(kg=kg, memory=memory)
    matched = await sem_agent.run(
        candidates=candidates,
        user_input=user_input,
    )

    print(f"\n  Matched candidates: {len(matched)} / {len(candidates)}")

    # Show interest_fit distribution
    bins = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for p in matched:
        if p.interest_fit < 0.2: bins["0.0-0.2"] += 1
        elif p.interest_fit < 0.4: bins["0.2-0.4"] += 1
        elif p.interest_fit < 0.6: bins["0.4-0.6"] += 1
        elif p.interest_fit < 0.8: bins["0.6-0.8"] += 1
        else: bins["0.8-1.0"] += 1
    print(f"  Interest fit distribution: {bins}")

    top_matched = sorted(matched, key=lambda p: p.interest_fit, reverse=True)
    print_poi_table(top_matched, limit=10, title="Top 10 by interest fit:")

    # ══════════════════════════════════════════════════════════
    # AGENT 3: MCDM Scoring
    # ══════════════════════════════════════════════════════════
    print_header("AGENT 3: MCDM Scoring")

    from src.agents.scoring_agent import ScoringAgent

    score_agent = ScoringAgent(memory=memory)
    scored = await score_agent.run(
        candidates=matched,
        user_input=user_input,
    )

    print(f"\n  Scored candidates: {len(scored)}")
    scores = [p.composite_score for p in scored]
    print(f"  Score range: {min(scores):.3f} → {max(scores):.3f}")
    print(f"  Score mean:  {sum(scores)/len(scores):.3f}")

    print_poi_table(scored, limit=15, title="Top 15 by composite score:")

    # ══════════════════════════════════════════════════════════
    # AGENT 4: Spatial Clustering
    # ══════════════════════════════════════════════════════════
    print_header("AGENT 4: Spatial Clustering")

    from src.agents.clustering_agent import ClusteringAgent

    cluster_agent = ClusteringAgent(memory=memory)
    daily_clusters = await cluster_agent.run(
        candidates=scored,
        user_input=user_input,
    )

    for day_idx in sorted(daily_clusters.keys()):
        cluster = daily_clusters[day_idx]
        if cluster:
            lats = [p.latitude for p in cluster]
            lngs = [p.longitude for p in cluster]
            avg_score = sum(p.composite_score for p in cluster) / len(cluster)
            fest_count = sum(1 for p in cluster if p.source == "festival")
            print(
                f"  Day {day_idx + 1}: {len(cluster):>3} places | "
                f"avg_score={avg_score:.3f} | "
                f"lat=[{min(lats):.4f}, {max(lats):.4f}] | "
                f"festivals={fest_count}"
            )
            # Show top 3 per day
            for p in cluster[:3]:
                tag = " [FEST]" if p.source == "festival" else ""
                print(f"         • {p.name[:40]}{tag} (score={p.composite_score:.3f})")
        else:
            print(f"  Day {day_idx + 1}:   0 places (EMPTY)")

    # ══════════════════════════════════════════════════════════
    # AGENT 5: Route Optimization
    # ══════════════════════════════════════════════════════════
    print_header("AGENT 5: Route Optimization")

    from src.agents.routing_agent import RoutingAgent

    route_agent = RoutingAgent(memory=memory)
    itinerary = await route_agent.run(
        daily_clusters=daily_clusters,
        user_input=user_input,
    )

    print(f"\n  Total itinerary score: {itinerary.total_score:.3f}")
    print()

    for day in itinerary.days:
        trip_date = day.date
        print(f"  ┌─── Day {day.day_number} ({trip_date}) ───────────────────────────────────────────┐")
        print(f"  │  Stops: {len(day.stops)}  |  Travel: {day.total_travel_minutes:.0f} min  |  Visit: {day.total_visit_minutes:.0f} min  |  Score: {day.total_score:.3f}")
        print(f"  ├─────────────────────────────────────────────────────────────────┤")

        for stop in day.stops:
            arr = stop.arrival_time.strftime("%H:%M") if stop.arrival_time else "?"
            dep = stop.departure_time.strftime("%H:%M") if stop.departure_time else "?"
            tag = " 🎪" if stop.poi.source == "festival" else ""
            print(
                f"  │  {stop.order:>2}. [{arr}-{dep}] {stop.poi.name[:35]:<35}{tag}"
                f"  +{stop.travel_minutes_from_prev:.0f}m travel, {stop.visit_minutes}m visit"
            )

        print(f"  └─────────────────────────────────────────────────────────────────┘\n")

    # ── Cleanup ──
    await kg.close()

    print_header("ALL 5 AGENTS PASSED ✓")
    print(f"  Pipeline: {len(pois)} POIs + {len(raw_festivals)} festivals")
    print(f"         → {len(enriched_festivals)} enriched festivals")
    print(f"         → {len(matched)} semantic matches")
    print(f"         → {len(scored)} scored candidates")
    print(f"         → {user_input.num_days} day clusters")
    print(f"         → {sum(len(d.stops) for d in itinerary.days)} itinerary stops")
    print()


if __name__ == "__main__":
    asyncio.run(main())
