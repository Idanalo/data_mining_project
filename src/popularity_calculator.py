import polars as pl
import json
from pathlib import Path
import math
import time
from collections import defaultdict

class PopularityCalculator:
    def __init__(self, data_dir, processed_dir):
        self.data_dir = Path(data_dir)
        self.processed_dir = Path(processed_dir)
        
        self.basics_path = self.data_dir / "title.basics.tsv"
        self.principals_path = self.data_dir / "title.principals.tsv"
        self.names_path = self.data_dir / "name.basics.tsv"
        self.ratings_path = self.data_dir / "title.ratings.tsv"
        self.edges_path = self.processed_dir / "actor_edges.tsv"
        if not self.edges_path.exists():
            self.edges_path = Path(__file__).parent / "processed_data" / "actor_edges.tsv"

        self.movie_years = {}
        self.movie_cast_size = {}
        self.movie_votes = {}
        self.actor_names = {}
        self.actor_professions = {}
        self.initialized = False
        
        self.actor_movie_roles = defaultdict(list) # actor -> [(movie, ordering), ...]
        
    def _initialize_data(self):
        if self.initialized:
            return
            
        print("[Popularity] Initializing data...")
        t0 = time.time()
        
        # 1. Read Valid Movies & Years
        df_basics = pl.read_csv(
            self.basics_path, separator='\t', columns=['tconst', 'titleType', 'startYear'],
            schema_overrides={'tconst': pl.Utf8, 'titleType': pl.Utf8, 'startYear': pl.Utf8},
            null_values=['\\N'], quote_char=None
        )
        valid_movies = df_basics.filter(
            (pl.col('titleType').is_in(['movie', 'tvMovie'])) & 
            (pl.col('startYear').is_not_null())
        )
        
        for row in valid_movies.iter_rows():
            tconst, _, yr = row
            if yr and yr.isdigit():
                self.movie_years[tconst] = int(yr)
                
        # 2. Read Principals for Role Majorness (ordering)
        df_principals = pl.read_csv(
            self.principals_path, separator='\t', columns=['tconst', 'ordering', 'nconst', 'category'],
            schema_overrides={'tconst': pl.Utf8, 'ordering': pl.Utf8, 'nconst': pl.Utf8, 'category': pl.Utf8},
            null_values=['\\N'], quote_char=None
        ).filter(pl.col('category').is_in(['actor', 'actress']))
        
        for row in df_principals.iter_rows():
            tconst, ordering, nconst, _ = row
            if tconst in self.movie_years and nconst:
                ord_val = int(ordering) if ordering and ordering.isdigit() else 10
                self.actor_movie_roles[nconst].append((tconst, ord_val))
                self.movie_cast_size[tconst] = self.movie_cast_size.get(tconst, 0) + 1
                
        print("[Popularity] Parsing ratings...")
        if self.ratings_path.exists():
            df_ratings = pl.read_csv(
                self.ratings_path, separator='\t', ignore_errors=True,
                columns=['tconst', 'numVotes'],
                schema_overrides={'tconst': pl.Utf8, 'numVotes': pl.Int32}
            )
            for row in df_ratings.iter_rows():
                self.movie_votes[row[0]] = row[1] if row[1] else 0

        # 3. Read Names
        df_names = pl.read_csv(
            self.names_path, separator='\t', columns=['nconst', 'primaryName', 'primaryProfession'],
            schema_overrides={'nconst': pl.Utf8, 'primaryName': pl.Utf8, 'primaryProfession': pl.Utf8},
            null_values=['\\N'], quote_char=None
        )
        for row in df_names.iter_rows():
            nconst, name, prof = row
            if nconst:
                self.actor_names[nconst] = name
                if prof:
                    self.actor_professions[nconst] = [p.strip() for p in prof.split(',') if p.strip()]
                
        print(f"[Popularity] Initialized in {time.time() - t0:.2f}s. Indexed {len(self.actor_movie_roles)} actors.")
        self.initialized = True
        
    def calculate_popularity_in_window(self, start_year, end_year, top_k=5):
        self._initialize_data()
        
        actor_scores = []
        for nconst, roles in self.actor_movie_roles.items():
            role_scores = []
            movies_in_window = 0
            for tconst, ordering in roles:
                yr = self.movie_years.get(tconst)
                if yr and start_year <= yr <= end_year:
                    cast_size = self.movie_cast_size.get(tconst, 1)
                    num_votes = self.movie_votes.get(tconst, 0)
                    
                    # Impact = log2(1 + CastSize) * log10(1 + numVotes)
                    impact = math.log2(1 + cast_size) * math.log10(1 + num_votes)
                    
                    # Weight severely dampens minor roles (1/ordering)
                    weight = 1.0 / ordering
                    role_scores.append(weight * impact)
                    movies_in_window += 1
            if movies_in_window > 0:
                # To prevent quantity over quality, we only sum the Top 3 best roles 
                # in the time window for an actor.
                best_roles = sorted(role_scores, reverse=True)[:3]
                balanced_score = sum(best_roles) * 10
                
                # Retrieve actor details
                name = self.actor_names.get(nconst, nconst)
                primary_professions = self.actor_professions.get(nconst, [])
                
                actor_scores.append({
                    "nconst": nconst,
                    "name": name,
                    "professions": primary_professions,
                    "score": round(balanced_score, 2),
                    "movies_in_window": movies_in_window
                })
                
        actor_scores.sort(key=lambda x: x["score"], reverse=True)
        return actor_scores[:top_k]
        
    def precompute_timeline(self, out_path):
        self._initialize_data()
        
        timeline_data = []
        for year in range(1920, 2027):
            start_yr = year - 1
            end_yr = year + 1
            
            top_3 = self.calculate_popularity_in_window(start_yr, end_yr, top_k=3)
            if top_3:
                timeline_data.append({
                    "year": year,
                    "window": f"{start_yr}-{end_yr}",
                    "top_actors": top_3
                })
        
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, indent=2)
        print(f"Exported timeline to {out_file.name}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="../data")
    parser.add_argument("--processed-dir", default="../processed_data")
    parser.add_argument("--out", default="web_app/static/popular_actors_timeline.json")
    args = parser.parse_args()
    
    # Resolve paths relative to this script
    base_dir = Path(__file__).parent.resolve()
    data_dir = (base_dir / args.data_dir).resolve()
    processed_dir = (base_dir / args.processed_dir).resolve()
    out_path = (base_dir / args.out).resolve()
    
    calc = PopularityCalculator(data_dir, processed_dir)
    calc.precompute_timeline(out_path)
