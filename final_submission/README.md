# Final Submission: Actor Co-Starring Network & Community Explorer

This folder contains the complete, self-contained implementation of the actor graph network analysis pipeline, temporal community clustering engine, tag analytics, and interactive web application.

---

## 📁 Repository Structure

```
final_submission/
├── README.md                           # Documentation & usage guide
├── pair_creation.py                    # Pair creation pipeline (title.basics + title.principals -> actor_edges.tsv)
├── community_clustering.py            # Temporal community clustering engine (Louvain + Tag Analytics)
├── processed_data/                     # Directory housing actor_edges.tsv
└── web_app/                            # Interactive Web Application
    ├── app.py                          # FastAPI backend REST API server
    └── static/
        ├── index.html                  # Responsive Dark-Mode Dashboard
        ├── css/
        │   └── style.css               # Glassmorphic aesthetic design system
        └── js/
            ├── app.js                  # Application logic & state manager
            └── graph_viz.js            # D3.js force-directed graph rendering engine
```

---

## 🚀 Quick Start Guide

### 1. Generating Actor Pair Combinations (`pair_creation.py`)
To build `actor_edges.tsv` from the raw IMDb datasets in `../data/`:

```bash
# Run full pair creation pipeline
python final_submission/pair_creation.py

# Or test with a quick sample of 1,000,000 rows
python final_submission/pair_creation.py --sample 1000000
```

---

### 2. Running Temporal Graph Community Clustering (`community_clustering.py`)
To run temporal Louvain graph clustering directly from the command line for a target cutoff year:

```bash
# Cluster the actor network for movies released up to 2010
python final_submission/community_clustering.py --year 2010 --min-weight 2

# Cluster network up to year 1990
python final_submission/community_clustering.py --year 1990 --min-weight 1
```

**Key Analytics Outputted**:
- Graph node/edge counts & Louvain modularity score.
- Community archetype labels & top celebrity members.
- Profession & tag prevalence percentages (`actor`, `actress`, `producer`, `director`, etc.).
- Movie genre breakdown for each community (`Action`, `Drama`, `Comedy`, etc.).
- Inter-community connection matrix (edges bridging different communities).

---

### 3. Launching the Interactive Web Application (`web_app/app.py`)
To start the web application dashboard:

```bash
# Run FastAPI server
python final_submission/web_app/app.py
```

Then open your browser and navigate to:
👉 **`http://127.0.0.1:8000`**

### Web Application Features:
- 🎚️ **Temporal Year Slider**: Interactively slide through release years (1920 to 2026) to watch communities form and evolve.
- 📊 **Executive Dashboard Cards**: Live stats for total active actors, total edges, communities found, and graph modularity.
- 🏷️ **Tag & Genre Profiles**: View profession tag pills, prevalence percentages, and genre progress bars for every community.
- 🔗 **Inter-Community Connection Matrix**: Heatmap matrix showing collaboration density between macro communities.
- 🔍 **Interactive Community Inspector Modal**: Click **"Open Community"** to open a full-screen D3 force-directed node graph for exploring intra-community connections and bridge nodes.
