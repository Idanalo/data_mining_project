import polars as pl
import networkx as nx
import networkx.algorithms.community as nx_comm
from pathlib import Path
from collections import Counter, defaultdict
import argparse
import json
import time

# Paths
base_dir = (Path(__file__).parent / "..").resolve()
data_dir = base_dir / "data"
processed_dir = base_dir / "processed_data"

# Fallback to local processed_data if main processed_data isn't populated
local_edges_path = Path(__file__).parent / "processed_data" / "actor_edges.tsv"
main_edges_path = processed_dir / "actor_edges.tsv"

edges_file_path = main_edges_path if main_edges_path.exists() else local_edges_path
names_file_path = data_dir / "name.basics.tsv"
titles_file_path = data_dir / "title.basics.tsv"

class CommunityClusterer:
    def __init__(self, edges_path=None, names_path=None, titles_path=None):
        self.edges_path = Path(edges_path) if edges_path else edges_file_path
        self.names_path = Path(names_path) if names_path else names_file_path
        self.titles_path = Path(titles_path) if titles_path else titles_file_path
        
        self.actor_names_cache = {}
        self.actor_professions_cache = {}
        self.movie_genres_cache = {}

    def fetch_metadata_for_targets(self, target_nconsts, target_tconsts):
        """Lazily fetches metadata only for specified actors and movies to keep execution blazingly fast."""
        t0 = time.time()
        
        # Fetch Actor names & professions for target nodes
        missing_nconsts = [n for n in target_nconsts if n not in self.actor_names_cache]
        if missing_nconsts and self.names_path.exists():
            names_df = pl.read_csv(
                self.names_path,
                separator='\t',
                columns=['nconst', 'primaryName', 'primaryProfession'],
                quote_char=None,
                schema_overrides={'nconst': pl.Utf8, 'primaryName': pl.Utf8, 'primaryProfession': pl.Utf8},
                null_values=['\\N']
            ).filter(pl.col('nconst').is_in(missing_nconsts))
            
            for row in names_df.iter_rows():
                nconst, name, prof = row
                if nconst:
                    self.actor_names_cache[nconst] = name or nconst
                    if prof:
                        profs = [p.strip() for p in prof.split(',') if p.strip()]
                        self.actor_professions_cache[nconst] = profs
                        
        # Fetch Movie genres for target titles
        missing_tconsts = [t for t in target_tconsts if t not in self.movie_genres_cache]
        if missing_tconsts and self.titles_path.exists():
            titles_df = pl.read_csv(
                self.titles_path,
                separator='\t',
                columns=['tconst', 'genres'],
                quote_char=None,
                schema_overrides={'tconst': pl.Utf8, 'genres': pl.Utf8},
                null_values=['\\N']
            ).filter(pl.col('tconst').is_in(missing_tconsts))
            
            for row in titles_df.iter_rows():
                tconst, genres = row
                if tconst and genres:
                    self.movie_genres_cache[tconst] = [g.strip() for g in genres.split(',') if g.strip()]
                    
        print(f"[Clustering Engine] Lazily loaded metadata for {len(missing_nconsts):,} actors & {len(missing_tconsts):,} titles in {time.time() - t0:.2f}s")

    def run_clustering(self, target_year, min_weight=1, max_communities=15, min_community_size=3):
        """
        Filters edges where startYear <= target_year, builds graph G, executes Louvain community detection,
        and calculates in-community & between-community analytics with tag prevalence.
        """
        t0 = time.time()
        
        print(f"\n[Clustering Engine] Processing Graph for Target Year <= {target_year} (Min Weight: {min_weight})...")
        
        # 1. Temporal Edge Filtering using Polars
        df_edges = pl.read_csv(
            self.edges_path,
            separator='\t',
            columns=['actor1', 'actor2', 'shared_movies', 'startYear', 'weight'],
            quote_char=None,
            schema_overrides={'actor1': pl.Utf8, 'actor2': pl.Utf8, 'shared_movies': pl.Utf8, 'startYear': pl.Utf8, 'weight': pl.Int32},
            null_values=['\\N']
        )
        
        filtered = df_edges.filter(
            (pl.col('startYear').cast(pl.Int32, strict=False) <= target_year) &
            (pl.col('weight') >= min_weight)
        )
        
        total_filtered_edges = len(filtered)
        print(f"  -> Extracted {total_filtered_edges:,} edges created in or before {target_year}")
        
        if total_filtered_edges == 0:
            return {"error": f"No edges found for year <= {target_year} with min weight {min_weight}"}

        # 2. Build NetworkX Graph
        G = nx.Graph()
        for row in filtered.iter_rows():
            a1, a2, movies_str, year, weight = row
            G.add_edge(a1, a2, weight=weight, movies=movies_str.split(',') if movies_str else [])
            
        print(f"  -> Built Graph: {G.number_of_nodes():,} nodes (actors), {G.number_of_edges():,} edges")
        
        # 3. Community Detection (Louvain)
        print("  -> Running Louvain Community Detection...")
        try:
            communities_raw = nx_comm.louvain_communities(G, weight='weight', seed=42)
        except Exception as e:
            print(f"  -> Louvain fallback to greedy modularity: {e}")
            communities_raw = list(nx_comm.greedy_modularity_communities(G, weight='weight'))
            
        # Calculate overall graph modularity
        modularity_score = nx_comm.modularity(G, communities_raw, weight='weight')
        print(f"  -> Detected {len(communities_raw):,} total communities (Modularity: {modularity_score:.4f})")

        # Sort communities by size descending
        communities_sorted = sorted(communities_raw, key=len, reverse=True)
        
        # Filter communities with size >= min_community_size
        valid_communities = [c for c in communities_sorted if len(c) >= min_community_size]
        selected_communities = valid_communities[:max_communities]
        
        # Collect target nodes and movies across selected communities for lazy metadata lookup
        all_target_nodes = set()
        all_target_movies = set()
        for comm in selected_communities:
            all_target_nodes.update(comm)
            subG = G.subgraph(set(comm))
            for u, v, data in subG.edges(data=True):
                all_target_movies.update(data.get('movies', []))
                
        self.fetch_metadata_for_targets(all_target_nodes, all_target_movies)
        
        # Map node -> community_id
        node_to_comm = {}
        for comm_idx, comm_nodes in enumerate(selected_communities, start=1):
            for n in comm_nodes:
                node_to_comm[n] = comm_idx
                
        # 4. Inter-Community Connections Matrix
        # matrix[i][j] = count of edges between community i and community j
        inter_comm_matrix = defaultdict(lambda: defaultdict(int))
        intra_comm_edges = defaultdict(int)
        
        for u, v, data in G.edges(data=True):
            c_u = node_to_comm.get(u)
            c_v = node_to_comm.get(v)
            if c_u and c_v:
                if c_u == c_v:
                    intra_comm_edges[c_u] += 1
                else:
                    inter_comm_matrix[c_u][c_v] += 1
                    inter_comm_matrix[c_v][c_u] += 1

        # 5. Process detailed analytics per selected community
        community_details = []
        
        for comm_idx, comm_nodes in enumerate(selected_communities, start=1):
            nodes_set = set(comm_nodes)
            subG = G.subgraph(nodes_set)
            
            internal_edges = subG.number_of_edges()
            node_count = len(comm_nodes)
            possible_edges = (node_count * (node_count - 1)) / 2 if node_count > 1 else 1
            internal_density = internal_edges / possible_edges
            
            # Top connected actors in this community
            degrees = dict(subG.degree(weight='weight'))
            top_actors_ids = sorted(degrees.keys(), key=lambda x: degrees[x], reverse=True)[:10]
            
            top_actors = [
                {
                    "nconst": actor_id,
                    "name": self.actor_names_cache.get(actor_id, actor_id),
                    "degree": degrees[actor_id],
                    "professions": self.actor_professions_cache.get(actor_id, [])
                }
                for actor_id in top_actors_ids
            ]
            
            # Tag & Profession Prevalence
            profession_counter = Counter()
            for actor_id in comm_nodes:
                profs = self.actor_professions_cache.get(actor_id, [])
                for p in profs:
                    profession_counter[p] += 1
                    
            profession_stats = []
            for prof, count in profession_counter.most_common(6):
                pct = round((count / node_count) * 100, 1)
                profession_stats.append({"tag": prof, "count": count, "percentage": pct})
                
            # Movie Genre Distribution
            genre_counter = Counter()
            community_movies = set()
            for u, v, data in subG.edges(data=True):
                movies = data.get('movies', [])
                community_movies.update(movies)
                
            for m in community_movies:
                genres = self.movie_genres_cache.get(m, [])
                for g in genres:
                    genre_counter[g] += 1
                    
            total_genres = sum(genre_counter.values()) or 1
            genre_stats = [
                {"genre": g, "count": cnt, "percentage": round((cnt / total_genres) * 100, 1)}
                for g, cnt in genre_counter.most_common(5)
            ]
            
            # Generate Archetype Label
            top_prof = profession_stats[0]['tag'].capitalize() if profession_stats else 'Actors'
            top_genre = genre_stats[0]['genre'] if genre_stats else 'Cinema'
            archetype = f"{top_genre} {top_prof} Circle"
            
            # Inter-community connections for this community
            bridges = []
            for other_idx in range(1, len(selected_communities) + 1):
                if other_idx != comm_idx and inter_comm_matrix[comm_idx][other_idx] > 0:
                    bridges.append({
                        "target_community": other_idx,
                        "connection_count": inter_comm_matrix[comm_idx][other_idx]
                    })
            bridges.sort(key=lambda x: x['connection_count'], reverse=True)
            
            community_details.append({
                "id": comm_idx,
                "node_count": node_count,
                "internal_edges": internal_edges,
                "internal_density": round(internal_density, 4),
                "archetype": archetype,
                "top_actors": top_actors,
                "profession_tags": profession_stats,
                "top_genres": genre_stats,
                "bridges": bridges
            })
            
        elapsed = time.time() - t0
        
        # Build inter-community matrix data for response
        matrix_list = []
        for i in range(1, len(selected_communities) + 1):
            row_data = {"source": i, "targets": []}
            for j in range(1, len(selected_communities) + 1):
                row_data["targets"].append({
                    "target": j,
                    "count": inter_comm_matrix[i][j] if i != j else intra_comm_edges[i]
                })
            matrix_list.append(row_data)

        result = {
            "target_year": target_year,
            "min_weight": min_weight,
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "total_communities_found": len(communities_raw),
            "modularity_score": round(modularity_score, 4),
            "execution_time_seconds": round(elapsed, 2),
            "communities": community_details,
            "inter_community_matrix": matrix_list
        }
        
        print(f"[Clustering Engine] Completed analysis in {elapsed:.2f}s")
        return result

    def get_community_graph_details(self, target_year, community_id, min_weight=1, max_nodes=150):
        """Returns node and edge details for interactive D3 graph rendering of a specific community."""
        res = self.run_clustering(target_year=target_year, min_weight=min_weight, max_communities=20)
        if "error" in res:
            return res
            
        target_comm = None
        for c in res['communities']:
            if c['id'] == community_id:
                target_comm = c
                break
                
        if not target_comm:
            return {"error": f"Community {community_id} not found."}
            
        # Re-run temporal graph to extract sub-graph nodes and edges
        df_edges = pl.read_csv(
            self.edges_path,
            separator='\t',
            columns=['actor1', 'actor2', 'shared_movies', 'startYear', 'weight'],
            quote_char=None,
            schema_overrides={'actor1': pl.Utf8, 'actor2': pl.Utf8, 'shared_movies': pl.Utf8, 'startYear': pl.Utf8, 'weight': pl.Int32},
            null_values=['\\N']
        )
        filtered = df_edges.filter(
            (pl.col('startYear').cast(pl.Int32, strict=False) <= target_year) &
            (pl.col('weight') >= min_weight)
        )
        
        G = nx.Graph()
        for row in filtered.iter_rows():
            a1, a2, movies_str, year, weight = row
            G.add_edge(a1, a2, weight=weight)
            
        communities_raw = sorted(nx_comm.louvain_communities(G, weight='weight', seed=42), key=len, reverse=True)
        valid_communities = [c for c in communities_raw if len(c) >= 3][:20]
        
        if community_id > len(valid_communities):
            return {"error": "Invalid community index"}
            
        comm_nodes = list(valid_communities[community_id - 1])
        
        # Sort nodes by degree within community to pick top max_nodes
        subG = G.subgraph(comm_nodes)
        degrees = dict(subG.degree(weight='weight'))
        selected_nodes = sorted(comm_nodes, key=lambda x: degrees[x], reverse=True)[:max_nodes]
        selected_set = set(selected_nodes)
        
        subG_selected = G.subgraph(selected_set)
        
        nodes_payload = []
        for n in selected_set:
            nodes_payload.append({
                "id": n,
                "label": self.actor_names_cache.get(n, n),
                "degree": degrees[n],
                "professions": self.actor_professions_cache.get(n, [])
            })
            
        edges_payload = []
        for u, v, d in subG_selected.edges(data=True):
            edges_payload.append({
                "source": u,
                "target": v,
                "weight": d.get('weight', 1)
            })
            
        return {
            "community_summary": target_comm,
            "nodes": nodes_payload,
            "edges": edges_payload
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Temporal Graph Community Clustering Tool")
    parser.add_argument("--year", type=int, default=2010, help="Target cutoff year")
    parser.add_argument("--min-weight", type=int, default=1, help="Minimum edge weight filter")
    parser.add_argument("--max-communities", type=int, default=10, help="Max communities to analyze in detail")
    args = parser.parse_args()
    
    clusterer = CommunityClusterer()
    results = clusterer.run_clustering(target_year=args.year, min_weight=args.min_weight, max_communities=args.max_communities)
    print("\n" + json.dumps(results, indent=2))
