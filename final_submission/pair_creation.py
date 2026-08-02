import pandas as pd
import polars as pl
from pathlib import Path
from collections import defaultdict
import itertools
import argparse
import sys
import time

# Setup paths
base_dir = (Path(__file__).parent / "..").resolve()
data_dir = base_dir / "data"
output_dir = Path(__file__).parent / "processed_data"

basics_path = data_dir / "title.basics.tsv"
principals_path = data_dir / "title.principals.tsv"
edges_output_path = output_dir / "actor_edges.tsv"

def run_pair_creation(start_year=1800, end_year=2026, sample_limit=None):
    """
    Parses IMDb title.basics.tsv and title.principals.tsv to build the actor co-starring network edge list.
    Outputs a TSV file with columns: actor1, actor2, shared_movies, startYear, weight
    """
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print(f" INITIATING ACTOR PAIR CREATION PIPELINE ({start_year} - {end_year})")
    print("=" * 60)
    
    if not basics_path.exists() or not principals_path.exists():
        print(f"Error: Required IMDb dataset files missing from {data_dir}")
        sys.exit(1)
        
    start_time = time.time()
    
    # --------------------------------------------------------
    # PHASE 1: Find Valid Movies & Release Years
    # --------------------------------------------------------
    print("\n[Phase 1] Scanning title.basics for valid movies...")
    
    # Read basics using Polars for high performance
    basics_df = pl.read_csv(
        basics_path,
        separator='\t',
        has_header=True,
        columns=['tconst', 'titleType', 'startYear'],
        quote_char=None,
        schema_overrides={'tconst': pl.Utf8, 'titleType': pl.Utf8, 'startYear': pl.Utf8},
        null_values=['\\N']
    )
    
    # Filter for movies and tvMovies within the target year range
    valid_movies_df = basics_df.filter(
        (pl.col('titleType').is_in(['movie', 'tvMovie'])) &
        (pl.col('startYear').cast(pl.Int32, strict=False) >= start_year) &
        (pl.col('startYear').cast(pl.Int32, strict=False) <= end_year)
    )
    
    # Map tconst -> startYear integer
    valid_movies = dict(zip(valid_movies_df['tconst'], valid_movies_df['startYear'].cast(pl.Int32, strict=False)))
    print(f"  -> Found {len(valid_movies):,} valid movies between {start_year} and {end_year}")

    # --------------------------------------------------------
    # PHASE 2: Group Cast Members by Movie
    # --------------------------------------------------------
    print("\n[Phase 2] Reading title.principals and grouping cast members...")
    movie_cast = defaultdict(list)
    
    # Read principals in chunks using pandas to manage RAM efficiently
    principals_reader = pd.read_csv(
        principals_path,
        sep='\t',
        usecols=['tconst', 'nconst', 'category'],
        dtype=str,
        chunksize=2000000
    )
    
    rows_processed = 0
    for chunk in principals_reader:
        rows_processed += len(chunk)
        # Keep only actors/actresses belonging to valid movies
        mask = (chunk['tconst'].isin(valid_movies)) & (chunk['category'].isin(['actor', 'actress']))
        valid_rows = chunk[mask][['tconst', 'nconst']]
        
        grouped = valid_rows.groupby('tconst')['nconst'].agg(list)
        for tconst, actors in grouped.items():
            movie_cast[tconst].extend(actors)
            
        print(f"  -> Processed {rows_processed:,} rows from principals...")
        if sample_limit and rows_processed >= sample_limit:
            print(f"  -> Reached sample limit of {sample_limit:,} rows.")
            break

    # --------------------------------------------------------
    # PHASE 3: Generate Pair Combinations (Undirected Edges)
    # --------------------------------------------------------
    print("\n[Phase 3] Generating actor pair combinations (Undirected Edges)...")
    edges = defaultdict(list)
    
    for tconst, actors in movie_cast.items():
        unique_actors = list(set(actors))
        if len(unique_actors) < 2:
            continue
            
        for actor1, actor2 in itertools.combinations(unique_actors, 2):
            edge = tuple(sorted([actor1, actor2]))
            edges[edge].append(tconst)
            
    print(f"  -> Generated {len(edges):,} unique co-starring actor pairs.")

    # --------------------------------------------------------
    # PHASE 4: Export to actor_edges.tsv
    # --------------------------------------------------------
    print(f"\n[Phase 4] Exporting to {edges_output_path.name}...")
    output_data = []
    
    for (actor1, actor2), shared_movies in edges.items():
        movies_str = ",".join(shared_movies)
        years = [valid_movies[tconst] for tconst in shared_movies if valid_movies.get(tconst) is not None]
        earliest_year = int(min(years)) if years else '\\N'
        weight = len(shared_movies)
        
        output_data.append([actor1, actor2, movies_str, earliest_year, weight])
        
    df_out = pd.DataFrame(output_data, columns=['actor1', 'actor2', 'shared_movies', 'startYear', 'weight'])
    df_out.to_csv(edges_output_path, sep='\t', index=False)
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f" SUCCESS: Exported {len(df_out):,} edges to {edges_output_path.name}")
    print(f" Total Execution Time: {elapsed:.2f} seconds")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate actor_edges.tsv from IMDb dataset")
    parser.add_argument("--start-year", type=int, default=1800, help="Minimum release year")
    parser.add_argument("--end-year", type=int, default=2026, help="Maximum release year")
    parser.add_argument("--sample", type=int, default=None, help="Optional row limit for quick testing")
    args = parser.parse_args()
    
    run_pair_creation(start_year=args.start_year, end_year=args.end_year, sample_limit=args.sample)
