# Advanced Data Mining Metrics & Analysis Suggestions
## Actor Network Community Explorer & Graph Analytics Project

This document outlines high-impact data mining metrics, graph analytics, statistical evaluations, and visual analysis suggestions designed to maximize project difficulty, analytical rigor, and visualization scores for the final project submission.

---

## 1. Network Centrality & Topology Metrics

| Metric Category | Formula / Definition | Project Application & Analytical Value |
| :--- | :--- | :--- |
| **Shortest Path Median & Closeness Centrality** | $C(v) = \frac{N-1}{\sum_{u \neq v} d(v, u)}$ | **Top 5 Median Actors Tab**: Identifies actors with the minimum total shortest path distance to all other connected actors in Hollywood. |
| **Distance Normal Distribution Parameters** | $\mu = \text{Mean}(d), \quad \sigma = \sqrt{\frac{1}{N}\sum(d_i - \mu)^2}, \quad \sigma^2$ | Quantifies how tightly or broadly an actor is situated relative to the rest of the network. High $\sigma$ indicates uneven distribution across peripheral sub-networks. |
| **Network Radius & Eccentricity (Max Hops)** | $E(v) = \max_{u} d(v, u)$ | Measures the maximum number of co-star hops required to reach the furthest actor in the connected component. |
| **Hop Distance Breakdown (Histogram)** | $P(h) = \frac{|\{u \mid d(v, u) = h\}|}{N} \times 100\%$ | Provides a percentage breakdown of actors accessible at 1 hop (direct co-stars), 2 hops, 3 hops, 4 hops, and 5+ hops. |
| **Betweenness Centrality & Bridge Score** | $g(v) = \sum_{s \neq v \neq t} \frac{\sigma_{st}(v)}{\sigma_{st}}$ | Identifies "bridge actors" who connect otherwise disjoint genres, franchises, or regional industries (e.g., Samuel L. Jackson connecting Tarantino films and the MCU). |
| **Weighted Degree Centrality (Strength)** | $S(v) = \sum_{u \in N(v)} w(v, u)$ | Distinguishes between actors who have many one-off co-stars vs. actors with deep, repeated collaborations across multiple films. |
| **Local Clustering Coefficient & Transitivity** | $C_v = \frac{2 e_v}{k_v(k_v - 1)}$ | Measures the density of triangles (cliques) around an actor—whether an actor's co-stars frequently act together with each other. |
| **PageRank / Eigenvector Centrality** | $PR(p_i) = \frac{1-d}{N} + d \sum_{p_j \in M(p_i)} \frac{PR(p_j)}{L(p_j)}$ | Ranks an actor's global prestige based on being connected to other highly influential and central figures in the cinema graph. |

---

## 2. Community Detection & Partition Quality Metrics

| Analysis Module | Technique / Algorithm | Analytical Value & Insights |
| :--- | :--- | :--- |
| **Louvain Modularity Score ($Q$)** | $Q = \frac{1}{2m} \sum_{ij} \left[ A_{ij} - \frac{k_i k_j}{2m} \right] \delta(c_i, c_j)$ | Numerical benchmark quantifying community partition quality ($0 \le Q \le 1$). Higher values ($Q > 0.6$) indicate dense intra-community edges and sparse inter-community links. |
| **Hierarchical Inner Sub-Communities** | Multi-level Louvain / Girvan-Newman on subgraphs | Discovers "inner circles" within large communities (e.g., isolating an "MCU Action Core" inside a broader "Hollywood Action Blockbuster" community). |
| **Inter-Community Connection Matrix** | Heatmap matrix $M_{ij} = \text{Edges}(C_i, C_j)$ | Visualizes the degree of collaboration between different detected communities, showing which genres or regional hubs frequently co-produce films. |
| **Geographical Profile Inference** | Weighted scoring over actor names, titles & genres | Automatically tags communities with regional cinema hubs (e.g., Hollywood, British Screen, European Art-House, East Asian Cinema, Bollywood). |
| **Community Archetype Tagging** | Dominant profession + top genre extraction | Generates descriptive labels for communities (e.g., "🌐 Sci-Fi Director Circle", "🇬🇧 Drama Actor Circle"). |

---

## 3. Temporal & Evolution Metrics

| Metric / Dimension | Implementation Strategy | Insights Provided |
| :--- | :--- | :--- |
| **Dual-Way Temporal Filtering** | `created_before` $\le X$ AND `active_after` $\ge Y$ | Allows slicing the network across specific eras (e.g., Golden Age 1930–1960 vs. Modern Era 2000–2026). |
| **Community Stability over Time** | Jaccard index between community partitions across decades | Evaluates whether actor communities persist across time or dissolve as cinema trends shift. |
| **Career Collaboration Span** | $\text{Span} = \text{LatestMovieYear} - \text{FirstMovieYear}$ | Measures an actor's active temporal span alongside their cumulative degree growth. |

---

## 4. Advanced Extensions & Future Work Suggestions for Report

### A. Frequent Co-Casting Motif Mining (Association Rules)
- **Method**: FP-Growth or Apriori algorithm treating each movie as a "basket" of cast members.
- **Rule Format**: $\{\text{Director: Quentin Tarantino}, \text{Actor: Samuel L. Jackson}\} \implies \{\text{Actor: Tim Roth}\}$ (Confidence: 85%, Support: 0.04).
- **Report Value**: Demonstrates pattern mining beyond standard graph clustering.

### B. Genre Entropy & Diversity Index
- **Formula**: $H(v) = -\sum_{i=1}^k p_i \log_2(p_i)$, where $p_i$ is the proportion of an actor's films in genre $i$.
- **Interpretation**: Low entropy ($H \approx 0$) indicates specialized actors (e.g., Horror/Comedy only); high entropy ($H > 2.5$) highlights versatile crossover actors.

### C. Bipartite Movie-Actor Projection
- **Method**: Bipartite graph $G = (V_{\text{actors}}, V_{\text{movies}}, E)$ projected onto unipartite actor graph weighted by Jaccard similarity of filmographies.
- **Report Value**: Provides formal mathematical grounding for edge weight construction.

---

## 5. Summary of Recommended Report Highlights

To hit maximum points on the **50% Execution** and **25% Visualization** grading rubrics:

1. **Include Formal Formulas**: Put explicit LaTeX equations for Louvain Modularity ($Q$), Closeness Centrality ($C$), Mean ($\mu$), Standard Deviation ($\sigma$), and PageRank in the report.
2. **Present Comparison Tables**: Benchmark performance across edge weights ($W \ge 1, 2, 3, 5$) showing execution time, modularity score, and total nodes.
3. **Highlight Interactive Web Features**: Emphasize the live FastAPI + D3.js web application, D3 force-directed sub-graph visualization, click-to-inspect actor deep dive, inter-community heatmap, and normal distribution path histograms.
