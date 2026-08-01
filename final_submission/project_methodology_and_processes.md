# System Architecture & Methodology

This document outlines the end-to-end data processing pipeline, algorithmic methodology, and system architecture for the Hollywood Actor Network and Community Explorer project.

---

## 1. Data Ingestion & Edge Formation (`pair_creation.py`)

The foundational step of our process involves converting the raw IMDb TSV files (`title.basics.tsv`, `title.principals.tsv`) into a high-performance network edge list.

### Process:
1. **Chunked Memory Loading:** To bypass RAM constraints, the script streams the principal cast dataset in chunks.
2. **Actor Co-Star Combinations:** For every movie ID (`tconst`), we extract all credited actors and use `itertools.combinations` to generate every unique pairing.
3. **Weight Accumulation:** If an actor pair collaborates across multiple movies (e.g., Robert Downey Jr. & Chris Evans in Marvel films), their edge weight increases by 1 for each shared movie.
4. **Temporal Tagging:** We cross-reference `title.basics.tsv` to tag each edge with the `startYear` (the year of their first collaboration) and record the list of shared movie IDs.
5. **Output Generation:** The resulting network is serialized into `actor_edges.tsv`, an optimized edge-list used by the clustering engine.

---

## 2. Temporal Graph Construction & Community Detection (`community_clustering.py`)

The core analytical engine builds network topologies constrained by time (active windows) and detects dense actor communities.

### Process:
1. **Dynamic Edge Filtering:** The engine ingests `actor_edges.tsv` and rapidly filters edges using `polars` based on a temporal window (e.g., Created <= 2026, Active >= 2000). 
2. **Graph Build (`networkx`):** The filtered edges are loaded into a `networkx` undirected graph structure.
3. **Louvain Modularity Optimization:** We apply the Louvain community detection algorithm to heuristically partition the graph into communities by maximizing the Modularity Score (Q), effectively grouping actors who work together far more often than with the rest of Hollywood.
4. **Heuristic Profiling:**
   - **Professions & Genres:** We extract the primary professions and movie genres of the community's top actors to classify the community archetype (e.g., "Drama Actors Circle").
   - **Geographic Inference:** By analyzing regional name conventions and genre distributions, the engine assigns a primary global hub (e.g., "Hollywood", "Bollywood") and a representative flag.

---

## 3. Actor Popularity & Network Centrality (`popularity_calculator.py`)

To distinguish true global impact from sheer movie volume, we apply strict algorithmic scoring constraints.

### Process:
1. **Popularity Score Generation:**
   - Instead of looking at *all* movies an actor is in, the algorithm identifies their **Top 3 Roles** (sorted by movie popularity).
   - The impact of each role is calculated using `log10(numVotes)` from IMDb ratings and `log2(Cast Size)`.
   - The score is heavily penalized by the actor's billing order (a lead actor in a blockbuster gains massive points; a background extra gains nearly zero).
2. **Shortest-Path Median Centrality:**
   - We extract the Largest Connected Component (LCC) of the network.
   - Using Breadth-First Search (BFS), we calculate the absolute shortest path from a candidate actor to *every other actor in Hollywood*.
   - The actor with the smallest total distance (the shortest average path to anyone in the industry) is crowned the **True Median Actor**.

---

## 4. Interactive Web Dashboard (`app.py`, `app.js`, `graph_viz.js`)

The final layer serves the processed insights through an interactive, browser-based UI.

### Process:
1. **FastAPI Backend:** A lightweight asynchronous server (`app.py`) serves the HTML and exposes REST API endpoints (`/api/cluster`, `/api/median_actors`) that execute the Python analytics on demand.
2. **Caching Layer:** Because graph analytics are mathematically heavy O(V+E), the backend caches results in memory (RAM) so that repeated timeline requests execute in milliseconds.
3. **Frontend State Management (`app.js`):** Manages the sliding timeline bar, fetching updated JSON payloads and re-rendering the metric dashboards without page reloads.
4. **D3.js Graph Visualizer:** When a user inspects a community, `graph_viz.js` dynamically renders a physics-based, force-directed node graph mapping out the top 50 actors and their interlocking collaborations within that sub-network.
