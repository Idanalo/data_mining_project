import pandas as pd
from pathlib import Path
from collections import defaultdict
import itertools

# 1. Setup paths
base_dir = (Path(__file__).parent / "..").resolve()
data_dir = base_dir / "data"
output_dir = base_dir / "processed_data"

output_dir.mkdir(exist_ok=True)

basics_path = data_dir / "title.basics.tsv"
principals_path = data_dir / "title.principals.tsv"
output_path = output_dir / "actor_edges.tsv"

def build_actor_network(principals_row_limit=None, start_year=None, end_year=None):
    # --------------------------------------------------------
    # PHASE 1: Get all tconsts & startYears for movies/tvMovies
    # --------------------------------------------------------
    year_msg = f"{start_year or 'Any'} to {end_year or 'Any'}"
    print(f"Phase 1: Finding movies (Years: {year_msg})...")
    
    valid_movies = {}
    
    if not basics_path.exists():
        print(f"Error: Could not find {basics_path}")
        return
        
    basics_reader = pd.read_csv(
        basics_path, sep='\t', usecols=['tconst', 'titleType', 'startYear'], 
        dtype=str, chunksize=100000
    )
    
    basics_rows_processed = 0
    
    for chunk in basics_reader:
        basics_rows_processed += len(chunk)
        
        # 1. Keep only movies and TV movies
        movies_chunk = chunk[chunk['titleType'].isin(['movie', 'tvMovie'])].copy()
        
        # 2. Convert year to numeric so we can use < and >
        movies_chunk['startYear'] = pd.to_numeric(movies_chunk['startYear'], errors='coerce')
        
        # 3. Apply the year filters if they were provided
        if start_year is not None:
            movies_chunk = movies_chunk[movies_chunk['startYear'] >= start_year]
        if end_year is not None:
            movies_chunk = movies_chunk[movies_chunk['startYear'] <= end_year]
            
        # Add the filtered movies to our dictionary
        chunk_dict = movies_chunk.set_index('tconst')['startYear'].to_dict()
        valid_movies.update(chunk_dict)
        
        # Print progress for basics
        print(f"Processed {basics_rows_processed:,} rows from basics... (Found {len(valid_movies):,} valid movies)")
        
    print(f"\nFinished Phase 1. Total valid movies found: {len(valid_movies):,}")

    # --------------------------------------------------------
    # PHASE 2: Map actors to movies
    # --------------------------------------------------------
    print("\nPhase 2: Reading principals and mapping casts...")
    if not principals_path.exists():
        print(f"Error: Could not find {principals_path}")
        return

    movie_cast = defaultdict(list)
    
    principals_reader = pd.read_csv(
        principals_path, sep='\t', usecols=['tconst', 'nconst', 'category'],
        dtype=str, chunksize=10000
    )
    
    principals_rows_processed = 0
    
    for chunk in principals_reader:
        valid_rows = chunk[
            (chunk['tconst'].isin(valid_movies)) & 
            (chunk['category'].isin(['actor', 'actress']))
        ]
        
        # FIX: Changed .apply(list) to .agg(list) to prevent the FutureWarning
        grouped = valid_rows.groupby('tconst')['nconst'].agg(list)
        
        for tconst, actors in grouped.items():
            movie_cast[tconst].extend(actors)
            
        principals_rows_processed += len(chunk)
        print(f"Processed {principals_rows_processed:,} rows from principals...")
        
        if principals_row_limit and principals_rows_processed >= principals_row_limit:
            print(f"--- Row limit of {principals_row_limit:,} reached. Stopping read. ---")
            break

    # --------------------------------------------------------
    # PHASE 3: Build the edge list (Undirected Graph)
    # --------------------------------------------------------
    print("\nPhase 3: Building the graph edges...")
    edges = defaultdict(list)
    
    for tconst, actors in movie_cast.items():
        if len(actors) < 2:
            continue
            
        for actor1, actor2 in itertools.combinations(actors, 2):
            edge = tuple(sorted([actor1, actor2]))
            edges[edge].append(tconst)

    # --------------------------------------------------------
    # PHASE 4: Calculate Earliest Year and Save
    # --------------------------------------------------------
    print(f"\nPhase 4: Calculating earliest years and saving {len(edges):,} edges to {output_path}...")
    
    output_data = []
    for (actor1, actor2), shared_movies in edges.items():
        movies_str = ",".join(shared_movies)
        
        years = [
            valid_movies[tconst] 
            for tconst in shared_movies 
            if pd.notna(valid_movies.get(tconst))
        ]
        
        earliest_year = int(min(years)) if years else '\\N'
        output_data.append([actor1, actor2, movies_str, earliest_year])
        
    edges_df = pd.DataFrame(output_data, columns=['actor1', 'actor2', 'shared_movies', 'startYear'])
    edges_df.to_csv(output_path, sep='\t', index=False)
    
    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------
    print("\n" + "="*40)
    print(" FINAL SUMMARY")
    print("="*40)
    print(f"Years Filtered:                    {year_msg}")
    print(f"Total Movies/TV Movies identified: {len(valid_movies):,}")
    print(f"Total Basics rows processed:       {basics_rows_processed:,}")
    print(f"Total Principals rows processed:   {principals_rows_processed:,}")
    print(f"Total Unique Actor Edges Created:  {len(edges):,}")
    print("="*40 + "\n")

# --------------------------------------------------------
# RUN THE SCRIPT
# --------------------------------------------------------
# Removed the row_limit so it processes the entire file and finds the 2010-2020 movies.
build_actor_network(principals_row_limit=None, start_year=2000)