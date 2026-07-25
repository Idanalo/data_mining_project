import pandas as pd
from collections import Counter
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

# ========================================================
# 1. SETUP PATHS
# ========================================================
base_dir = (Path(__file__).parent / "..").resolve()
principals_path = base_dir / "data" / "title.principals.tsv"
basics_path = base_dir / "data" / "title.basics.tsv"
vis_dir = base_dir / "visualizations"

# Make sure the visualizations folder exists
vis_dir.mkdir(exist_ok=True)

def find_top_10_casts():
    print("="*60)
    print(" INITIATING TOP 10 ENSEMBLE CAST SEARCH")
    print("="*60)
    
    if not principals_path.exists() or not basics_path.exists():
        print("Error: Could not find IMDb data files.")
        return

    # ========================================================
    # PHASE 1: COUNT ACTORS PER MOVIE
    # ========================================================
    print("\n[Phase 1] Scanning principals for Actors/Actresses...")
    cast_counts = Counter()
    rows_processed = 0

    principals_reader = pd.read_csv(
        principals_path, 
        sep='\t', 
        usecols=['tconst', 'nconst', 'category'],
        dtype=str, 
        chunksize=2000000 
    )

    for chunk in principals_reader:
        # THE FILTER: Only keep actors and actresses
        actors_chunk = chunk[chunk['category'].isin(['actor', 'actress'])]
        
        # Drop duplicates just in case an actor played 2 roles in the same movie
        unique_actors = actors_chunk.drop_duplicates(subset=['tconst', 'nconst'])
        
        # Count how many unique actors are in each movie
        counts = unique_actors.groupby('tconst').size().to_dict()
        
        # Update our master scoreboard
        cast_counts.update(counts)
        
        rows_processed += len(chunk)
        print(f"  -> Scanned {rows_processed:,} rows...")

    # Grab the top 10 IDs from our scoreboard
    top_10_data = cast_counts.most_common(10)
    top_tconsts = [item[0] for item in top_10_data]

    # ========================================================
    # PHASE 2: TRANSLATE IDs TO REAL MOVIE TITLES
    # ========================================================
    print("\n[Phase 2] Translating IDs into actual movie names...")
    titles = {}
    
    basics_reader = pd.read_csv(
        basics_path, 
        sep='\t', 
        usecols=['tconst', 'primaryTitle', 'startYear'],
        dtype=str, 
        chunksize=1000000
    )

    for chunk in basics_reader:
        # Only look at the rows that match our Top 10 winners
        matches = chunk[chunk['tconst'].isin(top_tconsts)]
        for _, row in matches.iterrows():
            titles[row['tconst']] = f"{row['primaryTitle']} ({row['startYear']})"

    # ========================================================
    # PHASE 3: PRINT THE LEADERBOARD
    # ========================================================
    print("\n" + "="*60)
    print(" 🏆 THE TOP 10 BIGGEST CASTS (IMDb Max Limit)")
    print("="*60)
    
    for rank, (tconst, count) in enumerate(top_10_data, start=1):
        # Get the real name, or fallback to the ID if it wasn't found
        movie_name = titles.get(tconst, f"Unknown Title ({tconst})")
        
        print(f" {rank:2d}. {movie_name}")
        print(f"     Actors Listed: {count} | Link: https://www.imdb.com/title/{tconst}/")
        print("-" * 60)

    # ========================================================
    # PHASE 4: DRAW THE CAST SIZE GRAPH
    # ========================================================
    print("\n[Phase 4] Drawing Plot: Cast Size Distribution...")
    
    # Extract all the cast sizes from our scoreboard into a list
    all_cast_sizes = list(cast_counts.values())
    
    plt.figure(figsize=(10, 6))
    sns.set_theme(style="whitegrid")
    
    # Draw a discrete histogram for the sizes
    ax = sns.histplot(all_cast_sizes, discrete=True, color='mediumseagreen')
    
    # Force X-axis to show every whole number up to the maximum cast size
    max_cast = max(all_cast_sizes) if all_cast_sizes else 10
    plt.xticks(range(1, max_cast + 1))
    
    # Add exact numbers on top of the bars to emphasize the hard limit
    for p in ax.patches:
        height = p.get_height()
        if height > 0:
            ax.annotate(f"{int(height):,}",
                         (p.get_x() + p.get_width() / 2., height),
                         ha='center', va='bottom', fontsize=10, color='black', 
                         xytext=(0, 5), textcoords='offset points')

    plt.title("Distribution of Movie Cast Sizes (IMDb Data Limit)", fontsize=14, pad=15)
    plt.xlabel("Number of Actors/Actresses in a Movie")
    plt.ylabel("Number of Movies")
    
    plt.tight_layout()
    graph_path = vis_dir / "plot_4_cast_sizes.png"
    plt.savefig(graph_path, dpi=300)
    plt.close()
    
    print(f"  -> Successfully saved graph to {graph_path.name}")
    print("="*60 + "\n")

# Run the search!
if __name__ == "__main__":
    find_top_10_casts()