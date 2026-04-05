from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from src.agents.base import BaseAgent
from src.models.festival import Festival, FestivalMeta, RawFestival
from src.models.poi import POI, OpeningHours
from src.models.user_input import UserInput
from src.tools.geocoder import geocode_address
from src.tools.web_search import search_web


class FestivalAgent(BaseAgent):
    """Agent 1 — Festival Enrichment.

    Takes raw festival JSON + user trip dates.
    1. Parses time strings → (start_date, end_date)
    2. Filters festivals overlapping with trip dates
    3. Enriches each festival via web search (location, agenda, …)
    4. Geocodes to (lat, lng)
    5. Assigns Google-Maps-compatible types via LLM
    6. Returns list[POI] with source="festival"
    """

    name: str = "festival"

    async def _execute(self, **kwargs: Any) -> list[POI]:
        raw_festivals: list[dict] = kwargs["raw_festivals"]
        user_input: UserInput = kwargs["user_input"]
        year: int = user_input.start_date.year

        # Step 1+2: parse dates and filter
        temporally_valid: list[tuple[RawFestival, date, date]] = []
        for raw in raw_festivals:
            fest = RawFestival(**raw)
            start, end = self._parse_time(fest.time, year)
            if start is None:
                continue
            if self._overlaps(start, end, user_input.start_date, user_input.end_date):
                temporally_valid.append((fest, start, end))

        self.logger.info(
            "Temporal filter: %d / %d festivals overlap with trip dates.",
            len(temporally_valid),
            len(raw_festivals),
        )

        # Step 3-6: enrich each valid festival
        enriched_pois: list[POI] = []
        for fest, start_dt, end_dt in temporally_valid:
            poi = await self._enrich_festival(fest, start_dt, end_dt, user_input)
            if poi is not None:
                enriched_pois.append(poi)

        self.memory.set("enriched_festivals", enriched_pois)
        return enriched_pois

    # ── Time parsing ──

    def _parse_time(self, time_str: str, default_year: int) -> tuple[date | None, date | None]:
        """Parse festival time strings like '26 - 29/3', '6/11', '15/10/2025 - 28/2/2026'."""
        if not time_str.strip():
            return None, None

        time_str = time_str.strip()

        # Pattern: "15/10/2025 - 28/2/2026"  (full dates with year on both sides)
        m = re.match(
            r"(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})", time_str
        )
        if m:
            d1, m1, y1, d2, m2, y2 = (int(x) for x in m.groups())
            return date(y1, m1, d1), date(y2, m2, d2)

        # Pattern: "26 - 29/3"  (day range within one month)
        m = re.match(r"(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})$", time_str)
        if m:
            d1, d2, month = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(default_year, month, d1), date(default_year, month, d2)

        # Pattern: "4 - 6/12/2025"  (day range within one month with year)
        m = re.match(r"(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})$", time_str)
        if m:
            d1, d2, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            return date(year, month, d1), date(year, month, d2)

        # Pattern: "31/12/2025"  (single day with explicit year)
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", time_str)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(year, month, day), date(year, month, day)

        # Pattern: "6/11"  (single day, default year)
        m = re.match(r"^(\d{1,2})/(\d{1,2})$", time_str)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            return date(default_year, month, day), date(default_year, month, day)

        # Pattern: "24/2 - 31/3"  (cross-month range, no year)
        m = re.match(r"(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})$", time_str)
        if m:
            d1, m1, d2, m2 = (int(x) for x in m.groups())
            return date(default_year, m1, d1), date(default_year, m2, d2)

        # Pattern: "23/9 - 5/10/2025"  (cross-month range with year on end)
        m = re.match(r"(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})$", time_str)
        if m:
            d1, m1, d2, m2, year = (int(x) for x in m.groups())
            return date(year, m1, d1), date(year, m2, d2)

        # Pattern: "31/10 - 11/12/2025"  (cross-month with year, DD/MM - DD/MM/YYYY)
        m = re.match(r"(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})$", time_str)
        if m:
            d1, m1, d2, m2, year = (int(x) for x in m.groups())
            return date(year, m1, d1), date(year, m2, d2)

        self.logger.warning("Could not parse time string: '%s'", time_str)
        return None, None

    @staticmethod
    def _overlaps(
        fest_start: date, fest_end: date, trip_start: date, trip_end: date
    ) -> bool:
        return fest_start <= trip_end and fest_end >= trip_start

    # ── Enrichment pipeline ──

    async def _enrich_festival(
        self,
        fest: RawFestival,
        start_dt: date,
        end_dt: date,
        user_input: UserInput,
    ) -> POI | None:
        """Enrich a single festival: web search → geocode → categorise."""

        # Check long-term cache first
        cached = self.memory.cache_get("festivals", fest.name)
        if cached:
            self.logger.info("Cache hit for '%s'", fest.name)
            return POI(**cached["value"])

        # 3a. Web search for details (non-fatal on failure)
        try:
            search_results = await search_web(
                query=f"{fest.name} {fest.province} {start_dt.year} venue address agenda schedule",
            )
        except Exception as e:
            self.logger.warning("Web search failed for '%s': %s", fest.name, e)
            search_results = ""

        # 3b. Geocode
        location_query = " ".join(
            filter(None, [fest.ward, fest.commune, fest.province])
        )
        lat, lng = await geocode_address(location_query)

        # 3c. LLM categorisation + extraction (non-fatal on failure)
        types, visit_min, agenda = await self._categorise(fest, search_results)

        if lat is None or lng is None:
            self.logger.warning("Could not geocode festival '%s', skipping.", fest.name)
            return None

        fest_id = f"FEST_{'_'.join(fest.name.lower().split()[:4])}_{start_dt.year}"

        poi = POI(
            id=fest_id,
            name=fest.name,
            latitude=lat,
            longitude=lng,
            address=location_query,
            ward=fest.ward,
            district=fest.commune,
            province=fest.province,
            primaryType="tourist_attraction",
            types=types,
            rating=None,
            userRatingCount=None,
            timezone="Asia/Ho_Chi_Minh",
            openingHours=[OpeningHours(days=f"{start_dt} - {end_dt}", open="09:00", close="21:00")],
            priceLevel=0,
            priceRange="Free",
            source="festival",
            estimated_visit_minutes=visit_min,
        )

        # Cache for future runs
        self.memory.cache_set("festivals", fest.name, poi.model_dump())
        return poi

    async def _categorise(
        self, fest: RawFestival, search_results: str
    ) -> tuple[list[str], int, str]:
        """Use LLM to assign types, estimate visit duration, extract agenda."""

        system = (
            "You are a travel data analyst. Given a festival's name and description, "
            "return a JSON object with:\n"
            '  "types": list of Google Maps compatible types '
            '(e.g. "food", "tourist_attraction", "art_gallery", "night_club", "shopping_mall"),\n'
            '  "estimated_visit_minutes": integer (30-240),\n'
            '  "agenda": short summary of the festival agenda if available, else ""\n'
            "Return ONLY valid JSON, no markdown."
        )

        user = (
            f"Festival: {fest.name}\n"
            f"Description: {fest.description}\n"
            f"Web search results:\n{search_results[:2000]}"
        )

        try:
            raw = await self.llm_call(system, user, temperature=0.1)
            data = json.loads(raw)
            return (
                data.get("types", ["tourist_attraction"]),
                data.get("estimated_visit_minutes", 120),
                data.get("agenda", ""),
            )
        except Exception as e:
            self.logger.warning("LLM categorisation failed for '%s': %s", fest.name, e)
            # Fallback: infer types from description keywords
            return self._fallback_categorise(fest)

    @staticmethod
    def _fallback_categorise(fest: RawFestival) -> tuple[list[str], int, str]:
        """Keyword-based type inference when LLM is unavailable."""
        desc = (fest.name + " " + fest.description).lower()
        types = ["tourist_attraction"]
        visit_min = 120

        keyword_map = {
            "food": "food",
            "culinary": "food",
            "cuisine": "food",
            "restaurant": "restaurant",
            "art": "art_gallery",
            "exhibition": "art_gallery",
            "painting": "art_gallery",
            "photo": "art_gallery",
            "music": "night_club",
            "festival": "tourist_attraction",
            "flower": "park",
            "garden": "park",
            "market": "market",
            "fair": "market",
            "book": "book_store",
            "museum": "museum",
            "culture": "tourist_attraction",
            "fashion": "clothing_store",
            "textile": "store",
            "shop": "shopping_mall",
        }

        for keyword, gtype in keyword_map.items():
            if keyword in desc and gtype not in types:
                types.append(gtype)

        if "food" in types or "restaurant" in types:
            visit_min = 90
        elif "art_gallery" in types:
            visit_min = 60

        return types, visit_min, ""
