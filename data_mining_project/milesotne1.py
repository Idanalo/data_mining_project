import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from pathlib import Path
from collections import defaultdict
import itertools

# ========================================================
# 1. SETUP & PATHS
# ========================================================
base_dir = (Path(__file__).parent / "..").resolve()
data_dir = base_dir / "data"
processed_dir = base_dir / "processed_data"
vis_dir = base_dir / "visualizations"

# Create necessary folders
processed_dir.mkdir(exist_ok=True)
vis_dir.mkdir(exist_ok=True)

basics_path = data_dir / "title.basics.tsv"
principals_path = data_dir / "title.principals.tsv"
edges_output_path = processed_dir / "actor_edges.tsv"

def run_master_pipeline(start_year=2000, end_year=2026, core_network_cutoff=10):
    print("="*60)
    print(f" INITIATING MASTER PIPELINE: {start_year} - {end_year}")
    print("="*60)

    # ========================================================
    # PHASE 1: FIND VALID MOVIES & YEARS (OPTIMIZED)
    # ========================================================
    print("\n[Phase 1] Scanning basics for valid movies...")
    if not basics_path.exists():
        print(f"Error: Could not find {basics_path}")
        return

    valid_movies = {}
    basics_rows = 0

    basics_reader = pd.read_csv(
        basics_path, sep='\t', usecols=['tconst', 'titleType', 'startYear'], 
        dtype=str, chunksize=1000000 
    )

    for chunk in basics_reader:
        basics_rows += len(chunk)
        
        movies_chunk = chunk[chunk['titleType'].isin(['movie', 'tvMovie'])].copy()
        movies_chunk.drop(columns=['titleType'], inplace=True)
        
        movies_chunk['startYear'] = pd.to_numeric(movies_chunk['startYear'], errors='coerce')
        movies_chunk = movies_chunk[(movies_chunk['startYear'] >= start_year) & (movies_chunk['startYear'] <= end_year)]
            
        chunk_dict = movies_chunk.set_index('tconst')['startYear'].to_dict()
        valid_movies.update(chunk_dict)
        
        print(f"  -> Processed {basics_rows:,} rows... (Found {len(valid_movies):,} valid movies)")
        
        del chunk
        del movies_chunk

    # ========================================================
    # PHASE 2: MAP ACTORS TO MOVIES (MEMORY OPTIMIZED)
    # ========================================================
    print("\n[Phase 2] Reading principals and grouping casts...")
    if not principals_path.exists():
        print(f"Error: Could not find {principals_path}")
        return

    movie_cast = defaultdict(list)
    principals_rows = 0

    principals_reader = pd.read_csv(
        principals_path, sep='\t', usecols=['tconst', 'nconst', 'category'],
        dtype=str, chunksize=2000000 
    )

    for chunk in principals_reader:
        mask = (chunk['tconst'].isin(valid_movies)) & (chunk['category'].isin(['actor', 'actress']))
        valid_rows = chunk[mask][['tconst', 'nconst']]
        
        grouped = valid_rows.groupby('tconst')['nconst'].agg(list)
        
        for tconst, actors in grouped.items():
            movie_cast[tconst].extend(actors)
            
        principals_rows += len(chunk)
        print(f"  -> Processed {principals_rows:,} rows from principals...")
        
        del chunk
        del mask
        del valid_rows
        del grouped

   # ========================================================
    # PHASE 3: BUILD THE UNDIRECTED GRAPH EDGES
    # ========================================================
    print("\n[Phase 3] Calculating actor combinations (Edge Building)...")
    edges = defaultdict(list)
    
    # NEW: Dictionary to keep track of every movie's unique cast size
    cast_sizes = {}
    
    for tconst, actors in movie_cast.items():
        # THE PERMANENT FIX: Convert list to set to delete duplicate roles
        unique_actors = list(set(actors))
        
        # Store the cast size for our leaderboard
        cast_sizes[tconst] = len(unique_actors)
        
        if len(unique_actors) < 2:
            continue
            
        for actor1, actor2 in itertools.combinations(unique_actors, 2):
            edge = tuple(sorted([actor1, actor2]))
            edges[edge].append(tconst)

    # --------------------------------------------------------
    # NEW: PRINT TOP 10 BIGGEST CASTS
    # --------------------------------------------------------
    print("\n  🎬 TRIVIA: Top 10 Movies with the Biggest Unique Casts:")
    
    # Sort the dictionary by size (descending) and grab the top 10
    top_10_movies = sorted(cast_sizes.items(), key=lambda item: item[1], reverse=True)[:10]
    
    for rank, (tconst, size) in enumerate(top_10_movies, start=1):
        print(f"     {rank}. Cast Size: {size} actors | Link: https://www.imdb.com/title/{tconst}/")
    print("-" * 50)
    # --------------------------------------------------------
    
    # ========================================================
    # PHASE 4: PREPARE DATAFRAME & SAVE TO DISK
    # ========================================================
    print(f"\n[Phase 4] Calculating temporal weights and generating DataFrame...")
    output_data = []
    
    for (actor1, actor2), shared_movies in edges.items():
        movies_str = ",".join(shared_movies)
        
        years = [valid_movies[tconst] for tconst in shared_movies if pd.notna(valid_movies.get(tconst))]
        earliest_year = int(min(years)) if years else '\\N'
        
        edge_weight = len(shared_movies) 
        
        output_data.append([actor1, actor2, movies_str, earliest_year, edge_weight])
        
    df = pd.DataFrame(output_data, columns=['actor1', 'actor2', 'shared_movies', 'startYear', 'weight'])
    
    # Save the physical file for your records
    df.to_csv(edges_output_path, sep='\t', index=False)
    print(f"  -> Saved {len(df):,} edges to {edges_output_path.name}")

    # ========================================================
    # PHASE 5: VISUALIZATION (DIRECT RAM HANDOFF)
    # ========================================================
    print("\n[Phase 5] Generating Visualizations from live data...")
    sns.set_theme(style="whitegrid")

    # Plot A: Actor Degree Distribution
    print("  -> Drawing Plot 1: Node Degrees...")
    degrees = pd.concat([df['actor1'], df['actor2']]).value_counts()
    
    # --------------------------------------------------------
    # NEW: FIND THE MOST CONNECTED ACTOR
    # --------------------------------------------------------
    max_actor_id = degrees.idxmax()
    max_costars = degrees.max()
    print(f"\n  🏆 TRIVIA: The most connected actor is {max_actor_id} with {max_costars:,} unique co-stars!")
    print(f"     Look them up here: https://www.imdb.com/name/{max_actor_id}/\n")
    # --------------------------------------------------------

    plt.figure(figsize=(10, 6))
    ax = sns.histplot(degrees, bins=50, color='royalblue')
    ax.set_yscale("log")
    plt.title("Actor Connectness (Node Degree Distribution)", fontsize=14)
    plt.xlabel("Number of Unique Co-Stars")
    plt.ylabel("Number of Actors (Log Scale)")
    plt.tight_layout()
    plt.savefig(vis_dir / "plot_1_degree_distribution.png", dpi=300)
    plt.close()

    # Plot B: Edge Weight Distribution
    print("  -> Drawing Plot 2: Edge Weights...")
    plt.figure(figsize=(10, 6))
    ax2 = sns.histplot(data=df, x='weight', discrete=True, color='coral')
    ax2.set_yscale("log")
    plt.xlim(0, 50)
    plt.title("Distribution of Collaboration Counts (Log Scale)", fontsize=14)
    plt.xlabel("Number of Shared Movies (Edge Weight)")
    plt.ylabel("Number of Actor Pairs (Log Scale)")
    plt.tight_layout()
    plt.savefig(vis_dir / "plot_2_edge_weights.png", dpi=300)
    plt.close()

    # Plot C: Network Graph (CLEANED UP & EXPORTED)
    print(f"  -> Drawing Plot 3: Core Network Graph (Weight >= {core_network_cutoff})...")
    core_df = df[df['weight'] >= core_network_cutoff]
    
    G = nx.from_pandas_edgelist(core_df, source='actor1', target='actor2', edge_attr=['weight'])
    
    # THE PRUNE: Remove nodes that only have 1 connection to clean the messy fringe
    degrees_dict = dict(G.degree())
    nodes_to_keep = [n for n, d in degrees_dict.items() if d >= 2]
    G = G.subgraph(nodes_to_keep)
    
    # EXPORT: Save the cleaned edges to a file
    cleaned_edges_df = nx.to_pandas_edgelist(G)
    cleaned_edges_df.rename(columns={'source': 'actor1', 'target': 'actor2'}, inplace=True)
    core_export_path = vis_dir / "plot_3_core_edges.tsv"
    cleaned_edges_df.to_csv(core_export_path, sep='\t', index=False)
    print(f"  -> Exported {len(cleaned_edges_df):,} cleaned edges to {core_export_path.name}")

    plt.figure(figsize=(18, 18))
    
    # PHYSICS: k=0.8 pushes nodes apart, 50 iterations untangles the web
    pos = nx.spring_layout(G, k=0.8, iterations=50, seed=42)
    
    # VISUALS: Micro-nodes and highly transparent edges
    nx.draw_networkx_nodes(G, pos, node_size=5, node_color='crimson', alpha=0.9)
    edge_weights = [G[u][v]['weight'] * 0.1 for u, v in G.edges()]
    nx.draw_networkx_edges(G, pos, width=edge_weights, alpha=0.1, edge_color='gray')
    
    plt.title(f"Hollywood's Tightest Circles ({start_year} - {end_year})\nFiltered to pairs with {core_network_cutoff}+ shared movies (Fringe Pruned)", fontsize=20, pad=20)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(vis_dir / "plot_3_core_network_clean.png", dpi=300, facecolor='white')
    plt.close()

    # ========================================================
    # FINAL SUMMARY
    # ========================================================
    print("\n" + "="*60)
    print(" PIPELINE COMPLETE!")
    print("="*60)
    print(f"Total Movies Processed:    {len(valid_movies):,}")
    print(f"Total Unique Actor Edges:  {len(df):,}")
    print(f"Network Nodes (Actors):    {G.number_of_nodes():,}")
    print(f"Network Core Connections:  {G.number_of_edges():,}")
    print(f"\nAll outputs saved successfully to your project folders.")
    print("="*60 + "\n")

# Run the master pipeline (Notice cutoff is set to 10 here!)
run_master_pipeline(start_year=2000, end_year=2026, core_network_cutoff=10)