# Hollywood Actor Co-Starring Network — Data Mining Project

A data mining pipeline built on IMDb's public datasets that models actors as a
co-starring graph, detects temporal communities with the Louvain algorithm,
enriches them with genre/profession/geographic (Wikidata) profiling, and
exposes it all through an interactive FastAPI + D3.js web dashboard.

## Repository Layout

```
.
├── pyproject.toml         # Project metadata & dependencies (managed by uv)
├── uv.lock                # Locked dependency versions
├── data/                  # Raw IMDb .tsv files (gitignored, populated by scripts/download_data.py)
├── scripts/
│   └── download_data.py   # Downloads & extracts the required IMDb datasets into data/
└── src/                    # The project source
    ├── pair_creation.py           # Builds actor_edges.tsv from raw IMDb data
    ├── popularity_calculator.py   # Computes actor "popularity" scores from ratings/votes
    ├── community_clustering.py    # Louvain community clustering + tag/genre/geo analytics
    ├── generate_pdf_visualizations.py  # Renders the PNG charts used in the report
    ├── create_report_docx.py      # Generates Hollywood_Data_Mining_Report.docx
    ├── web_app/
    │   ├── app.py          # FastAPI backend serving the dashboard + REST API
    │   └── static/          # Dark-mode dashboard UI (HTML/CSS/D3.js)
    └── processed_data/      # Generated intermediate data (created at runtime, gitignored)
```

## 1. Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (manages the Python version and dependencies — no separate Python install needed)

Install project dependencies into a local `.venv`:

```bash
uv sync
```

## 2. Get the Data

The raw datasets aren't checked into the repo (see `data/data_sets.txt`). Run
the download script to fetch and extract them from
[IMDb's public dataset mirror](https://datasets.imdbws.com/) into `data/`:

```bash
uv run scripts/download_data.py
```

This downloads and decompresses:

```
data/
├── title.basics.tsv
├── title.principals.tsv
├── name.basics.tsv
└── title.ratings.tsv
```

## 3. Build the Actor Co-Starring Graph

Run the pair creation pipeline to parse the raw IMDb data into
`src/processed_data/actor_edges.tsv`:

```bash
uv run src/pair_creation.py
```

For a quick smoke test on a subset of rows instead of the full dataset:

```bash
uv run src/pair_creation.py --sample 1000000
```

Optional flags: `--start-year` / `--end-year` restrict which movies are
considered (defaults: 1800–2026).

> **Note:** the full run streams the 4 GB `title.principals.tsv` and holds the
> complete edge map in memory — expect several GB of RAM usage and a few
> minutes of runtime.

## 4. Run Community Clustering (CLI)

Once `actor_edges.tsv` exists, you can run the temporal Louvain clustering
directly from the command line:

```bash
# Cluster the actor network for movies released up to 2010
uv run src/community_clustering.py --year 2010 --min-weight 2

# Cluster the network up to 1990, with a looser weight filter
uv run src/community_clustering.py --year 1990 --min-weight 1
```

This prints graph/community stats, modularity score, community archetypes,
top members, profession/genre breakdowns, and the inter-community connection
matrix. Nationality enrichment is fetched live from the public Wikidata SPARQL
endpoint and cached to `src/processed_data/wikidata_country_cache.json`.

## 5. Launch the Interactive Web Dashboard

```bash
uv run src/web_app/app.py
```

Then open:

👉 **http://127.0.0.1:8000**

Dashboard features:
- Temporal year slider (1920–2026) to watch communities evolve over time
- Executive stat cards: active actors, edges, communities, modularity
- Per-community tag/genre/profession profiles
- Inter-community connection heatmap
- Click "Open Community" for a full-screen D3 force-directed graph of that community

> **Note:** the server holds the edge list (and the most recently clustered
> graph) in memory — expect roughly 1–2 GB resident on the full dataset. The
> first request for a given filter combination builds the graph and runs
> Louvain, which takes seconds to minutes depending on the year range; repeat
> requests and "Open Community" for the same filters are then served from
> cache near-instantly. The first median-actors query computes shortest paths
> over the whole giant component and can take minutes; results are cached
> afterwards.

## 6. Optional: Regenerate Report Assets

The steps below must run in this order — the charts read the timeline JSON,
and the report embeds the charts.

**a. Precompute the popular-actors timeline JSON** used by the dashboard and
the timeline chart (written to `src/web_app/static/popular_actors_timeline.json`):

```bash
uv run src/popularity_calculator.py
```

(The `--data-dir` / `--processed-dir` flags exist but default to the right
locations — they are resolved relative to `src/`, not your current directory.)

**b. Generate the PNG charts** (entropy graph, popularity timeline, median
comparisons) into `src/`:

```bash
uv run src/generate_pdf_visualizations.py
```

> **Note:** the two median-comparison charts fetch their data from the running
> web dashboard at `http://127.0.0.1:8000` to reuse its cache, so start the
> server (step 5) first. The entropy graph re-runs clustering for seven decade
> windows, so expect this script to take several minutes.

**c. Generate the Word report** (`src/Hollywood_Data_Mining_Report.docx`),
which embeds the charts above:

```bash
uv run src/create_report_docx.py
```

## Notes

- All commands assume you run them from the repository root unless noted otherwise.
- `src/processed_data/`, `.venv/`, and any `.tsv`/`.csv` files are gitignored — they're regenerated locally.
