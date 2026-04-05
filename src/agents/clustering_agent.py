from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.cluster import KMeans

from src.agents.base import BaseAgent
from src.models.poi import POI
from src.models.user_input import UserInput


class ClusteringAgent(BaseAgent):
    """Agent 4 — Spatial Clustering for multi-day planning.

    Groups scored candidates into N geographic clusters (one per trip day).
    Festivals are pre-assigned to eligible days, then K-Means fills the rest.
    """

    name: str = "clustering"

    async def _execute(self, **kwargs: Any) -> dict[int, list[POI]]:
        candidates: list[POI] = kwargs["candidates"]
        user_input: UserInput = kwargs["user_input"]
        n_days: int = user_input.num_days

        if not candidates:
            return {d: [] for d in range(n_days)}

        # Limit candidates to top-N by composite score to keep clusters manageable
        max_total = user_input.max_places_per_day * n_days * 3  # 3x buffer
        if len(candidates) > max_total:
            candidates = sorted(candidates, key=lambda p: p.composite_score, reverse=True)[:max_total]
            self.logger.info("Trimmed candidates to top %d for clustering.", max_total)

        # Separate festivals (with day constraints) from regular POIs
        festivals: list[POI] = [p for p in candidates if p.source == "festival"]
        regular: list[POI] = [p for p in candidates if p.source != "festival"]

        # Step 1: K-Means on regular POIs
        clusters = self._kmeans_cluster(regular, n_days)

        # Step 2: Assign festivals to the nearest compatible cluster
        self._assign_festivals(clusters, festivals, user_input)

        # Step 3: Rebalance if any cluster is too small or too large
        self._rebalance(clusters, user_input.max_places_per_day)

        self.memory.set("daily_clusters", clusters)
        return clusters

    # ── K-Means ──

    def _kmeans_cluster(self, pois: list[POI], k: int) -> dict[int, list[POI]]:
        if len(pois) <= k:
            return {i: [pois[i]] if i < len(pois) else [] for i in range(k)}

        coords = np.array([[p.latitude, p.longitude] for p in pois])
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(coords)

        clusters: dict[int, list[POI]] = {i: [] for i in range(k)}
        for poi, label in zip(pois, labels):
            clusters[int(label)].append(poi)

        # Sort each cluster by composite score descending
        for day in clusters:
            clusters[day].sort(key=lambda p: p.composite_score, reverse=True)

        return clusters

    # ── Festival assignment ──

    def _assign_festivals(
        self,
        clusters: dict[int, list[POI]],
        festivals: list[POI],
        user_input: UserInput,
    ) -> None:
        """Assign each festival to the cluster whose centroid is nearest,
        respecting the festival's date overlap with trip days."""
        if not festivals:
            return

        centroids = self._compute_centroids(clusters)

        for fest in festivals:
            best_day = self._nearest_cluster(fest, centroids)
            if best_day is not None:
                clusters[best_day].append(fest)
                self.logger.info("Assigned festival '%s' to day %d", fest.name, best_day + 1)

    @staticmethod
    def _compute_centroids(clusters: dict[int, list[POI]]) -> dict[int, tuple[float, float]]:
        centroids: dict[int, tuple[float, float]] = {}
        for day, pois in clusters.items():
            if pois:
                lat = sum(p.latitude for p in pois) / len(pois)
                lng = sum(p.longitude for p in pois) / len(pois)
                centroids[day] = (lat, lng)
        return centroids

    @staticmethod
    def _nearest_cluster(
        poi: POI, centroids: dict[int, tuple[float, float]]
    ) -> int | None:
        if not centroids:
            return 0
        best, best_dist = None, float("inf")
        for day, (lat, lng) in centroids.items():
            dist = (poi.latitude - lat) ** 2 + (poi.longitude - lng) ** 2
            if dist < best_dist:
                best, best_dist = day, dist
        return best

    # ── Rebalance ──

    def _rebalance(self, clusters: dict[int, list[POI]], max_per_day: int) -> None:
        """Move overflow POIs from large clusters to small neighbouring ones."""
        for day in list(clusters.keys()):
            while len(clusters[day]) > max_per_day:
                # Remove lowest-scored POI
                clusters[day].sort(key=lambda p: p.composite_score, reverse=True)
                overflow = clusters[day].pop()

                # Find smallest cluster to absorb it
                target = min(clusters, key=lambda d: len(clusters[d]) if d != day else float("inf"))
                clusters[target].append(overflow)
                self.logger.debug("Moved '%s' from day %d → day %d", overflow.name, day + 1, target + 1)
