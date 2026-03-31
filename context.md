This is my project descriptions: 
1. Project Overview
This document outlines the research direction, technical architecture, and open questions for our trip planning system. The goal is to present our current thinking to the team, align on approach, and identify what each member should investigate before we converge on a final design.
1.1 Problem Statement
Given a set of Points of Interest (POIs) retrieved from the Google Maps API, we want to automatically generate the best possible multi-day trip itinerary for a user, based on their stated interests, budget, and trip duration.
Core Challenge No single algorithm solves all aspects of this problem. Interest matching, quality scoring, budget filtering, route optimization, and multi-day scheduling each require different techniques. Our system must integrate all of them into a coherent pipeline.
1.2 Input Data (Google Maps API Fields)
The following fields are available per POI and must be incorporated into our system:
Field Type Used For ID, name Identifier / string Entity node in Knowledge Graph latitude, longitude Numeric (float) Distance calc, spatial clustering types Array of strings Semantic matching via KG ontology rating, userRatingCount Numeric Bayesian quality scoring timezone, Period String / time ranges Opening hours filter per day priceLevel, priceRange Ordinal / string Budget constraint filtering
2. User Requirements & Priority Ranking
The user provides a structured form with the following inputs: interests/preferences, budget level, starting location, and trip duration (number of days). Our system must satisfy these requirements in the following priority order:
Priority Requirement Mapped Fields Handled By
Knowledge Graph-Based Trip Planning System | Research Proposal
Page 3
1st Match user interests / types types KG Semantic Layer 2nd Maximize place quality rating, userRatingCount Bayesian Scoring 3rd Stay within budget priceLevel, priceRange MCDM Filter 4th Minimize travel distance latitude, longitude Orienteering Problem — Fit trip duration (N days) Period, timezone MDOP + Clustering
Note: distance minimization is ranked last because users generally tolerate moderate travel if the places match their interests well. However, it remains a hard constraint within each day's time budget.
Knowledge Graph-Based Trip Planning System | Research Proposal
Page 4
3. Proposed System Architecture
We propose a four-layer pipeline. Each layer is independent and can be researched and implemented by different team members. The layers communicate through well-defined data contracts (scored candidate lists, clustered place sets, ordered itineraries).
USER INPUT Interests, budget, starting location, N-day duration LAYER 1 — Semantic Matching (Knowledge Graph) Expand user interests via ontology. Match types to categories. Filter irrelevant POIs. LAYER 2 — Scoring (MCDM) Score each POI: interest fit + quality (Bayesian) + budget fit. Produce ranked candidate list. LAYER 3 — Spatial Clustering Group candidates into N geographic clusters (one per day). Balance cluster sizes. LAYER 4 — Route Optimization (MDOP) Solve Orienteering Problem per day cluster. Apply opening hours constraints. Rebalance if needed. OUTPUT Multi-day itinerary with ordered places, estimated times, and daily routes.
4. Layer Deep Dives
Layer 1: Knowledge Graph — Semantic Matching
This is our primary research contribution. The KG solves a critical gap: if a user says they like 'Asian food,' a flat keyword search will not match a POI tagged as 'ramen_restaurant.' The KG bridges this via ontological reasoning.
Why a Knowledge Graph Here
•
Google Maps types are low-level ('ramen_restaurant', 'sushi_restaurant', 'izakaya')
•
User interests are high-level ('Japanese food', 'Asian cuisine', 'dining')
•
The KG maps low-level types upward to high-level categories through IS-A relationships
•
This enables semantic inference that SQL, vector search, and keyword matching cannot replicate
Proposed KG Schema Node Types (Place) — (Category) — (ParentCategory) — (User) — (PriceRange) — (Area/Zone)
Knowledge Graph-Based Trip Planning System | Research Proposal
Page 5
Key Relationships (Place)-[HAS_TYPE]->(Category) | (Category)-[IS_SUBCATEGORY_OF]->(ParentCategory) (Place)-[LOCATED_IN]->(Area) | (Place)-[NEAR]->(Place) [computed from lat/lng] (User)-[INTERESTED_IN]->(Category) | (User)-[HAS_BUDGET]->(PriceRange)
What to Research
•
Compare manual ontology (WordNet-based) vs. auto-extraction from Google Maps category hierarchy: KG construction
•
Neo4j vs. Amazon Neptune vs. RDF/SPARQL — compare query expressiveness and performance: KG tooling
•
How many ontology hops to allow before relevance drops? Needs empirical testing: Semantic reasoning depth
•
Can we combine KG with node2vec or TransE embeddings to handle fuzzy/novel user inputs?: Embedding integration
Layer 2: Multi-Criteria Decision Making (MCDM) Scoring
Each candidate POI is assigned a composite score that reflects all user priorities. This score is used both for filtering (remove budget violations) and ranking (prefer higher-scoring places).
Scoring Formula Composite Score Score(p) = w1 × InterestFit(p) + w2 × QualityScore(p) + w3 × BudgetFit(p) + w4 × ProximityScore(p) Weights reflect priority order: w1 > w2 > w3 > w4 (e.g., 0.40, 0.30, 0.20, 0.10)
Component Definitions
•
KG-derived similarity score between place categories and user interests (0-1): InterestFit(p)
•
Bayesian average: (rating × log(1 + userRatingCount)) — normalised to 0-1: QualityScore(p)
•
Binary or soft penalty: 1.0 if within budget, 0.5 if one level over, 0.0 if far over: BudgetFit(p)
•
Inverse of Haversine distance from starting location or cluster centroid: ProximityScore(p)
What to Research
•
Static weights vs. learned weights (AHP — Analytic Hierarchy Process) vs. user-adjusted sliders: Weight optimization
•
Compare Bayesian average vs. Wilson score confidence interval for quality scoring: Bayesian averaging
Knowledge Graph-Based Trip Planning System | Research Proposal
Page 6
•
Min-max vs. Z-score normalization for combining fields with different scales: Normalization strategy
•
How to measure contribution of each component independently — needed for thesis evaluation: Ablation study design
Knowledge Graph-Based Trip Planning System | Research Proposal
Page 7
Layer 3: Spatial Clustering for Multi-Day Planning
Before routing, we partition candidate places into N geographic groups — one per trip day. This ensures each day is geographically coherent and minimizes cross-day travel.
Approach
•
Set K = number of trip days requested by user
•
Run K-Means clustering on (latitude, longitude) coordinates of all scored candidates
•
Assign each cluster to a day; solve routing independently per cluster
•
Run a balance check: if any cluster has < minimum places, pull overflow from adjacent clusters
What to Research
•
K-Means forces exactly K clusters; DBSCAN discovers natural density groups but may not give exactly N clusters — research how to constrain it: K-Means vs. DBSCAN
•
Silhouette score and Davies-Bouldin index — use these to validate cluster coherence: Cluster quality metrics
•
What if one area has very few POIs that match user interests? Define fallback strategy: Handling sparse areas
•
Should higher-scored places have more influence on cluster centroids? Research score-weighted K-Means: Score-weighted clustering
Layer 4: Multi-Day Orienteering Problem (MDOP) — Route Optimization
The Orienteering Problem (OP) is the formal academic framing of our routing task. Unlike TSP (which visits all nodes), OP selects a subset of nodes to maximize collected score within a time/distance budget — exactly matching our use case.
Problem Formulation Orienteering Problem Definition Given a set of POIs, each with score s(p) and travel time t(i,j) between pairs, find the ordered subset that maximizes Σ s(p) subject to total travel + visit time ≤ daily_time_budget. We solve this independently per cluster (one OP per day).
Time Budget Per Place
Visit time is estimated from the types field using a lookup table (researchable and tunable):
•
90 minutes: Museum / gallery
•
60 / 30 minutes: Restaurant / cafe
•
45 minutes: Park / outdoor area
•
60 minutes: Shopping / market
Knowledge Graph-Based Trip Planning System | Research Proposal
Page 8
•
30 minutes: Landmark / temple
Role of the Period Field
The Period field (opening hours) from Google Maps is used as a hard feasibility constraint: a place is only added to a day's itinerary if it is open during the planned visit window. This is a meaningful research variable — most published trip planning papers ignore opening hours entirely.
What to Research
•
Google OR-Tools (exact) vs. greedy insertion heuristic vs. genetic algorithm — compare solution quality vs. computation time: Solver choice
•
Research whether solving all days simultaneously (MDOP) vs. independently (per-day OP) produces better overall itineraries: MDOP vs. per-day OP
•
Time-window Orienteering Problem (TWOP) — look for existing formulations: Opening hours handling
•
After per-day OP, design and justify the rebalancing strategy when clusters are imbalanced: Rebalancing heuristic
Knowledge Graph-Based Trip Planning System | Research Proposal
Page 9
5. Research Agenda by Team Member
Below is a suggested split of research areas. Each person should investigate the open questions in their layer and bring findings to the next team meeting. Priority items are marked.
Layer Technique Options What to Research Input Fields Used KG / Layer 1 Neo4j, RDF/SPARQL, node2vec, TransE KG ontology construction methods; semantic similarity metrics; embedding vs. symbolic reasoning tradeoffs types, name Scoring / Layer 2 MCDM, AHP, Bayesian avg, Wilson score Weight learning methods; normalization strategies; ablation study design for thesis rating, userRatingCount, priceLevel, priceRange Clustering / Layer 3 K-Means, DBSCAN, score-weighted clustering Cluster validation metrics; handling sparse POI areas; constraining DBSCAN to exactly N clusters latitude, longitude Routing / Layer 4 OR-Tools, genetic algorithm, TWOP MDOP solver comparison; opening hours as time windows; rebalancing heuristics Period, timezone, latitude, longitude
6. Key Open Questions
These are cross-cutting questions that the whole team should discuss and resolve together:
1.
KG vs. embeddings: Should semantic matching rely purely on KG ontology reasoning, or should we add vector embeddings as a fallback for unmapped user inputs? What is the best hybrid strategy?
2.
Weight tuning: Should scoring weights be static (researcher-defined), user-adjustable (sliders), or learned (AHP / user feedback)? What is most defensible for a thesis?
3.
Evaluation metrics: How do we measure itinerary quality? User studies? Simulated preference models? Comparison against manually curated ground truth?
4.
Baseline system: What is our comparison baseline? Random selection? Popularity-only ranking? Existing apps (TripAdvisor, Google Trips)?
5.
Data scale: How many POIs per city do we work with in experiments? Does the system remain efficient at 500+ candidates? Need complexity analysis for Layer 3 and 4.


First you read it and we already have the data in hcm_poi.json and poi.xlsx (they are the same data but different format), read all for me, dont generate anything 




Let me read both data files for you.

I've read both the project description and the full dataset. Here's a summary of what's in hcm_poi.json:

Dataset: 1,021 POIs in Ho Chi Minh City

Fields per POI (16 fields):
id, name, latitude, longitude, address, ward, district, province, primaryType, types (array), rating, userRatingCount, timezone, openingHours, priceLevel, priceRange

Key statistics:

Metric	Value
Total POIs	1,021
Unique primaryTypes	22
Unique flattened types	62
POIs with rating	903 (118 null)
Rating range	1.0 – 5.0 (avg 4.29)
POIs with opening hours	784 (237 null)
userRatingCount range	1 – 81,185 (avg 1,170)
primaryType distribution (top categories):
department_store (60), bakery (60), supermarket (60), meal_delivery (60), shopping_mall (60), art_gallery (60), park (60), gym (60), night_club (59), museum (58), spa (55), lodging (55), meal_takeaway (55), cafe (54), tourist_attraction (44), market (43), bar (42), restaurant (39), zoo (14), amusement_park (12), campground (8), aquarium (3)

Price distribution:

Free / priceLevel 0: 216
50k–150k / level 1: 290
150k–400k / level 2: 260
400k–800k / level 3: 217
800k+ / level 4: 2
Missing: 36
Geographic coverage:

Latitude: 10.732 – 10.823
Longitude: 106.630 – 106.743
Concentrated in Quận 1 (473), Quận 3 (100), Bình Thạnh (71), Quận 4 (59), Phú Nhuận (57)
Top POIs by popularity:
Ben Thanh Market (81k reviews), Independence Palace (45k), War Remnants Museum (40k), Saigon Zoo (34k), Notre Dame Cathedral (28k), Pizza 4P's (28k), Bui Vien Walking Street (25k)

The poi.xlsx file contains the same data in Excel format. The dataset maps well to all four layers of your proposed architecture — types for KG semantic matching, rating/userRatingCount for Bayesian scoring, priceLevel/priceRange for MCDM budget filtering, latitude/longitude for spatial clustering, and openingHours/timezone for the orienteering problem time-window constraints.




Outside the designed structure i give you, i have an idea of having the data of festival/event in the place i'm going to visit to add to the trip plan, the idea for this part is checking if the time of the festival within the user plan, you can add it to the plan if it is appropriate with the user attraction they provided us in the input. We first check the data provided in the json file then have a search on internet to find more information about it as: start time, end time, where will it held, agenda,... to provide to the user. So with the whole system, how should i design it to adapt with all the requirements, remember i will create Agentic AI to do this. 



This is a great extension. Let me analyze the festival data structure first, then propose the full agentic system design.

Read HCM_FEST.json, lines 1 to 50

Now I have full context. Here's the integrated agentic system design:

Full Agentic AI Trip Planning System — Integrated Design
The Problem with Festivals
Your festival data has critical gaps compared to POI data:

No coordinates (only ward/commune — many are empty)
No categories/types (only free-text description)
Imprecise time ("26 - 29/3" vs structured openingHours)
Missing details (no agenda, exact venue address, ticket price)
This means festivals can't just be injected into your existing 4-layer pipeline — they need a preprocessing stage powered by AI agents before they can participate in scoring, clustering, and routing.

┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR AGENT                      │
│  Receives user input, coordinates all agents, assembles      │
│  final itinerary, handles replanning & fallback              │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┘
       │          │          │          │          │
  ┌────▼───┐ ┌───▼────┐ ┌───▼───┐ ┌───▼───┐ ┌───▼────────┐
  │ Agent 1│ │Agent 2 │ │Agent 3│ │Agent 4│ │  Agent 5   │
  │Festival│ │Semantic│ │Scoring│ │Spatial│ │  Routing   │
  │Enricher│ │Matcher │ │(MCDM) │ │Cluster│ │  (MDOP)    │
  └────┬───┘ └───┬────┘ └───┬───┘ └───┬───┘ └───┬────────┘
       │         │          │         │          │
       ▼         ▼          ▼         ▼          ▼
   Web Search   KG Query   Score    K-Means   OR-Tools/
   + Geocode    Neo4j      Matrix   Assign    Greedy OP

   Agent 1: Festival Enrichment Agent (NEW)
Trigger: Runs first, in parallel with POI loading. Only activated when festival data exists for the destination city.

Input: Raw festival JSON + user trip dates + user interests

Step-by-step workflow:

1. TEMPORAL FILTER
   Parse "time" field → (start_date, end_date)
   Keep only festivals where [fest_start, fest_end] ∩ [trip_start, trip_end] ≠ ∅
   
   Examples from your data (if user trips March 25-30, 2026):
   ✓ "Saigontourist Culinary Festival" — 26-29/3
   ✓ "12th Ao Dai Festival" — 24/2-31/3
   ✗ "Vietnam Foodexpo" — 11-14/11
   
2. WEB SEARCH (Tool-using agent)
   For each temporally-valid festival, search for:
   - Exact venue address → geocode to (lat, lng)
   - Daily agenda / schedule
   - Ticket price (free / paid / range)
   - Expected duration of visit
   - Official website or social media link
   
3. CATEGORIZATION (LLM inference)
   From description + search results, assign:
   - types[] compatible with Google Maps taxonomy
     e.g., "Culinary Festival" → ["food", "restaurant", "tourist_attraction"]
     e.g., "Ao Dai Festival" → ["tourist_attraction", "art_gallery"]
   - Estimated visit duration
   - priceLevel (0-4 scale, matching POI schema)
   
4. OUTPUT: Normalized festival objects matching POI schema

Output schema (festivals become POI-compatible):
{
  "id": "FEST_saigontourist_culinary_2026",
  "name": "Saigontourist Culinary Culture Festival",
  "latitude": 10.7825,        // ← from geocoding
  "longitude": 106.6943,
  "address": "...",            // ← from web search
  "district": "...",
  "province": "Hồ Chí Minh",
  "primaryType": "tourist_attraction",
  "types": ["food", "tourist_attraction", "establishment"],
  "rating": null,              // no rating for festivals
  "userRatingCount": null,
  "timezone": "Asia/Ho_Chi_Minh",
  "openingHours": [{"days": "26-29/3", "open": "09:00", "close": "21:00"}],
  "priceLevel": 0,
  "priceRange": "Free",
  "source": "festival",        // ← flag to distinguish from POI
  "festivalMeta": {            // ← extra context for the user
    "originalTime": "26 - 29/3",
    "agenda": "...",           // from web search
    "description": "...",
    "url": "...",
    "estimatedVisitMinutes": 120
  }
}

Agent 2: Semantic Matching Agent (Layer 1 — enhanced)
What changes: Now receives POIs + normalized festivals as a unified candidate pool.
Input:  1021 POIs + N enriched festivals (all same schema)
        + user interests via KG

Process:
  - KG expansion: "Asian food" → ramen_restaurant, sushi_restaurant, ...
  - For POIs: match types[] against expanded interest set
  - For festivals: match LLM-assigned types[] the same way
  - Festival bonus: festivals get a small relevance boost (+0.1)
    because they are time-limited / unique experiences

Output: Filtered candidate list with InterestFit scores
Key design decision: Festivals with source: "festival" carry a scarcity bonus in the interest score because they are ephemeral — a user can visit a restaurant any time, but a festival only during their trip.

Agent 3: Scoring Agent (Layer 2 — enhanced)
Modified scoring formula:
For regular POIs:
  Score(p) = w1×InterestFit + w2×QualityScore + w3×BudgetFit + w4×ProximityScore

For festivals:
  Score(f) = w1×InterestFit + w2×FestivalQuality + w3×BudgetFit + w4×ProximityScore
                              ↑
                    Since festivals have no rating/userRatingCount,
                    substitute with:
                    - LLM-estimated quality (from description richness,
                      organizer reputation, scale indicators like
                      "450 booths", "100,000 visitors")
                    - Normalized to 0-1

Component	POI	Festival
InterestFit	KG similarity	KG similarity + scarcity bonus
QualityScore	Bayesian avg of rating × log(1+count)	LLM-estimated from description + web data
BudgetFit	priceLevel vs user budget	Inferred priceLevel vs user budget
ProximityScore	Haversine from start	Haversine from start (geocoded)


Agent 4: Spatial Clustering Agent (Layer 3 — enhanced)
What changes: Festivals have a temporal hard constraint that POIs don't.

Constraint: If festival runs on days 2-3 of a 5-day trip,
            it MUST be assigned to cluster for day 2 or day 3.

Algorithm modification:
  1. Pre-assign festivals to eligible day(s) based on their date overlap
  2. Run K-Means on remaining POIs
  3. Assign each pre-placed festival to the nearest cluster
     that falls on an eligible day
  4. Rebalance if needed

This is a constrained clustering problem — festivals act as anchors.

Agent 5: Routing Agent (Layer 4 — enhanced)
What changes: Festivals add time-window constraints similar to openingHours but stricter.

For each day's cluster:
  - POIs: soft constraint (openingHours preference)
  - Festivals: hard constraint (must visit during festival hours on that day)
  
  Solve as Time-Window Orienteering Problem (TWOP):
    maximize Σ score(p)
    subject to:
      - total_time ≤ daily_budget
      - visit festival f during [fest_open, fest_close]
      - visit POI p during [poi_open, poi_close] (soft)

Orchestrator Agent (the brain)
This is the master agent that coordinates everything:

class OrchestratorAgent:
    """
    Agentic AI coordinator - plans, delegates, reassembles
    """
    
    def plan_trip(self, user_input):
        # ── Phase 0: Parallel data loading ──
        pois = load_pois(user_input.city)
        raw_festivals = load_festivals(user_input.city)
        
        # ── Phase 1: Festival enrichment (Agent 1) ──
        # Only festivals overlapping user dates
        enriched_festivals = festival_agent.enrich(
            festivals=raw_festivals,
            trip_start=user_input.start_date,
            trip_end=user_input.end_date,
            user_interests=user_input.interests,
            tools=[web_search, geocoder, llm]
        )
        
        # ── Phase 2: Merge into unified candidate pool ──
        candidates = pois + enriched_festivals  # same schema
        
        # ── Phase 3: Semantic matching (Agent 2) ──
        matched = semantic_agent.match(
            candidates=candidates,
            user_interests=user_input.interests,
            knowledge_graph=kg
        )
        
        # ── Phase 4: MCDM Scoring (Agent 3) ──
        scored = scoring_agent.score(
            candidates=matched,
            user_budget=user_input.budget,
            start_location=user_input.start_location
        )
        
        # ── Phase 5: Spatial clustering (Agent 4) ──
        clusters = clustering_agent.cluster(
            candidates=scored,
            n_days=user_input.duration,
            festival_constraints=enriched_festivals  # anchor dates
        )
        
        # ── Phase 6: Route optimization (Agent 5) ──
        itinerary = routing_agent.optimize(
            daily_clusters=clusters,
            time_budget_per_day=user_input.daily_hours,
            trip_dates=user_input.date_range
        )
        
        # ── Phase 7: Validate & present ──
        return self.format_itinerary(itinerary)

Agent Communication — Data Contracts

User Input
    │
    ▼
┌──────────────────────────────┐
│ { interests, budget,         │
│   start_loc, duration,       │
│   start_date, end_date }     │
└──────────┬───────────────────┘
           │
     ┌─────▼─────┐
     │  Agent 1   │──→ List[NormalizedFestival]  (POI-schema compatible)
     └─────┬─────┘
           │ merge with POIs
     ┌─────▼─────┐
     │  Agent 2   │──→ List[Candidate] with InterestFit score
     └─────┬─────┘
     ┌─────▼─────┐
     │  Agent 3   │──→ List[ScoredCandidate] with composite score
     └─────┬─────┘
     ┌─────▼─────┐
     │  Agent 4   │──→ Dict[day_num → List[ScoredCandidate]]
     └─────┬─────┘         + festival anchoring constraints
     ┌─────▼─────┐
     │  Agent 5   │──→ Dict[day_num → OrderedRoute]
     └─────┬─────┘         with times, distances, scores
           │
     ┌─────▼──────────┐
     │  Orchestrator   │──→ Final multi-day itinerary
     │  (format +      │     with festival highlights marked
     │   validate)     │
     └────────────────┘


