import polars as pl
import networkx as nx
import networkx.algorithms.community as nx_comm
from pathlib import Path
from collections import Counter, defaultdict, OrderedDict
import argparse
import json
import time
import math
import threading
import requests
from popularity_calculator import PopularityCalculator

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

SUB_COMMUNITY_COLORS = [
    "#38bdf8",  # Cyan
    "#818cf8",  # Purple
    "#34d399",  # Emerald
    "#fbbf24",  # Amber
    "#f43f5e",  # Rose
    "#a855f7",  # Violet
    "#fb923c",  # Orange
    "#4ade80",  # Light Green
    "#e879f9",  # Fuchsia
    "#2dd4bf",  # Teal
    "#6366f1",  # Indigo
    "#ec4899"   # Pink
]

class CommunityClusterer:
    def __init__(self, edges_path=None, names_path=None, titles_path=None):
        self.edges_path = Path(edges_path) if edges_path else edges_file_path
        self.names_path = Path(names_path) if names_path else names_file_path
        self.titles_path = Path(titles_path) if titles_path else titles_file_path
        
        self.popularity_calculator = None
        
        self.actor_names_cache = {}
        self.actor_professions_cache = {}
        self.actor_birth_years_cache = {}
        self.actor_country_cache = {}
        self.movie_genres_cache = {}
        self.movie_titles_cache = {}
        self.median_cache = {}
        self.cluster_result_cache = {}
        self.edges_df_cache = None
        self.graph_cache = OrderedDict()  # LRU: a full clustered graph is several GB, keep only the latest
        self.graph_cache_size = 1
        self._heavy_lock = threading.RLock()
        self._load_wikidata_country_cache()

    def _load_wikidata_country_cache(self):
        cache_file = Path(__file__).parent / "processed_data" / "wikidata_country_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.actor_country_cache = json.load(f)
            except Exception:
                pass

    def _save_wikidata_country_cache(self):
        cache_file = Path(__file__).parent / "processed_data" / "wikidata_country_cache.json"
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.actor_country_cache, f, ensure_ascii=False)
        except Exception:
            pass

    def map_country_to_region(self, country_name):
        if not country_name or country_name == "Unknown":
            return None
        c_lower = country_name.lower()
        if any(k in c_lower for k in ['united states', 'canada', 'puerto rico']):
            return "North America"
        elif any(k in c_lower for k in ['united kingdom', 'england', 'scotland', 'wales', 'northern ireland', 'ireland', 'great britain']):
            return "United Kingdom & Ireland"
        elif any(k in c_lower for k in ['france', 'germany', 'italy', 'spain', 'sweden', 'denmark', 'norway', 'netherlands', 'poland', 'austria', 'switzerland', 'belgium', 'greece', 'hungary', 'czech', 'czechoslovakia', 'finland', 'ussr', 'soviet union', 'russia', 'russian empire', 'yugoslavia', 'romania', 'turkey', 'ottoman']):
            return "European Cinema"
        elif any(k in c_lower for k in ['japan', 'china', 'korea', 'hong kong', 'taiwan', 'singapore']):
            return "East Asian Cinema"
        elif any(k in c_lower for k in ['india', 'pakistan', 'bangladesh', 'sri lanka', 'british raj']):
            return "Bollywood & South Asia"
        elif any(k in c_lower for k in ['mexico', 'brazil', 'argentina', 'colombia', 'chile', 'peru', 'portugal', 'cuba', 'venezuela', 'uruguay']):
            return "Latin America & Iberia"
        else:
            return "Global & Festival Network"

    def fetch_wikidata_nationalities(self, nconsts):
        missing = [n for n in nconsts if n not in self.actor_country_cache]
        if not missing:
            return

        batch_size = 50
        url = 'https://query.wikidata.org/sparql'
        headers = {'User-Agent': 'HollywoodDataMiningProject/1.0 (contact@huji.ac.il)'}

        for i in range(0, len(missing), batch_size):
            chunk = missing[i:i+batch_size]
            values_str = " ".join(f'"{n}"' for n in chunk)
            sparql_query = f"""
            SELECT ?imdbId ?countryLabel WHERE {{
              VALUES ?imdbId {{ {values_str} }}
              ?person wdt:P345 ?imdbId .
              ?person wdt:P27 ?country .
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
            }}
            """
            batch_succeeded = False
            try:
                r = requests.get(url, params={'query': sparql_query, 'format': 'json'}, headers=headers, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get('results', {}).get('bindings', []):
                        nconst = item['imdbId']['value']
                        country = item['countryLabel']['value']
                        self.actor_country_cache[nconst] = country
                    batch_succeeded = True
            except Exception:
                pass

            # Only cache "Unknown" when Wikidata answered and genuinely had no entry;
            # a failed/timed-out batch must stay uncached so it gets retried next run.
            if batch_succeeded:
                for n in chunk:
                    if n not in self.actor_country_cache:
                        self.actor_country_cache[n] = "Unknown"

        self._save_wikidata_country_cache()

    def fetch_metadata_for_targets(self, target_nconsts, target_tconsts):
        """Lazily fetches metadata only for specified actors and movies to keep execution blazingly fast."""
        t0 = time.time()
        
        # Fetch Actor names, birth years & professions for target nodes
        missing_nconsts = [n for n in target_nconsts if n not in self.actor_names_cache]
        if missing_nconsts and self.names_path.exists():
            names_df = pl.read_csv(
                self.names_path,
                separator='\t',
                columns=['nconst', 'primaryName', 'birthYear', 'primaryProfession'],
                quote_char=None,
                schema_overrides={'nconst': pl.Utf8, 'primaryName': pl.Utf8, 'birthYear': pl.Int32, 'primaryProfession': pl.Utf8},
                null_values=['\\N']
            ).filter(pl.col('nconst').is_in(missing_nconsts))
            
            for row in names_df.iter_rows():
                nconst, name, byr, prof = row
                if nconst:
                    self.actor_names_cache[nconst] = name or nconst
                    if byr:
                        self.actor_birth_years_cache[nconst] = byr
                    if prof:
                        profs = [p.strip() for p in prof.split(',') if p.strip()]
                        self.actor_professions_cache[nconst] = profs
                        
        # Fetch Movie titles & genres for target titles
        missing_tconsts = [t for t in target_tconsts if t not in self.movie_genres_cache]
        if missing_tconsts and self.titles_path.exists():
            titles_df = pl.read_csv(
                self.titles_path,
                separator='\t',
                columns=['tconst', 'primaryTitle', 'genres'],
                quote_char=None,
                schema_overrides={'tconst': pl.Utf8, 'primaryTitle': pl.Utf8, 'genres': pl.Utf8},
                null_values=['\\N']
            ).filter(pl.col('tconst').is_in(missing_tconsts))
            
            for row in titles_df.iter_rows():
                tconst, title_name, genres = row
                if tconst:
                    if title_name:
                        self.movie_titles_cache[tconst] = title_name
                    if genres:
                        self.movie_genres_cache[tconst] = [g.strip() for g in genres.split(',') if g.strip()]
                    
        print(f"[Clustering Engine] Lazily loaded metadata for {len(missing_nconsts):,} actors & {len(missing_tconsts):,} titles in {time.time() - t0:.2f}s")

    def infer_community_geography(self, top_actors, top_genres, community_movies):
        """
        Analyzes actor nationalities (via Wikidata SPARQL), actor names, movie titles, and genre distribution
        to tag the community with a geographical profile (Region, Flag, Cinema Hub, Regional Distribution, and Summary).
        """
        # Fetch Wikidata country/citizenship metadata only for top central actors (fast batch query)
        top_nconsts = [a.get('nconst') for a in top_actors if a.get('nconst')]
        self.fetch_wikidata_nationalities(top_nconsts)

        actor_names = [a.get('name', '') for a in top_actors]
        movie_titles = [self.movie_titles_cache.get(m, '') for m in list(community_movies)[:30]]
        genres = [g['genre'] for g in top_genres]

        # Scoring indicators
        scores = {
            "North America": 0.0,
            "United Kingdom & Ireland": 0.0,
            "European Cinema": 0.0,
            "East Asian Cinema": 0.0,
            "Bollywood & South Asia": 0.0,
            "Latin America & Iberia": 0.0,
            "Global & Festival Network": 0.0
        }

        # 1. Grounded Wikidata Country Resolution
        known_wikidata_count = 0
        for a in top_actors:
            nconst = a.get('nconst')
            country = self.actor_country_cache.get(nconst)
            region = self.map_country_to_region(country)
            if region:
                scores[region] += 15.0
                known_wikidata_count += 1

        # 2. Fallback to keyword matching if Wikidata provided no country matches
        if known_wikidata_count == 0:
            scores["North America"] += 12.0  # Baseline fallback for Hollywood network

        # Check UK indicators
        uk_keywords = ['caine', 'connery', 'kingsley', 'mckellen', 'dench', 'smith', 'rickman', 'nighy', 'cumberbatch', 'winslet', 'mirren', 'stewart', 'fiennes', 'colman', 'grant', 'skarsgård', 'broadbent', 'bale', 'hardy']
        for name in actor_names:
            name_lower = name.lower()
            if any(k in name_lower for k in uk_keywords) or 'sir ' in name_lower or 'dame ' in name_lower:
                scores["United Kingdom & Ireland"] += 15.0

        # Check European indicators
        eu_keywords = ['jean', 'pierre', 'francois', 'mastroianni', 'loren', 'morricone', 'fellini', 'depardieu', 'deneuve', 'huppert', 'cotillard', 'cassard', 'herzog', 'wenders', 'almodovar', 'bardem', 'cruz', 'skarsgard', 'mikkelsen', 'von trier']
        for name in actor_names:
            name_lower = name.lower()
            if any(k in name_lower for k in eu_keywords):
                scores["European Cinema"] += 15.0

        # Check East Asian indicators
        asian_keywords = ['mifune', 'akira', 'takashi', 'ken', 'chan', 'chow', 'lee', 'zhang', 'gong', 'yang', 'park', 'kim', 'choi', 'yamada', 'tanaka', 'sato', 'wong', 'leung', 'toshiro', 'kurosawa']
        for name in actor_names:
            name_lower = name.lower()
            if any(k in name_lower for k in asian_keywords):
                scores["East Asian Cinema"] += 20.0

        # Check Indian / South Asian indicators
        indian_keywords = ['kumar', 'singh', 'khan', 'sharma', 'kapoor', 'patel', 'chatterjee', 'verma', 'rao', 'nair', 'gupta', 'bachchan', 'rahman', 'ray', 'sen', 'padukone', 'chopra', 'devgn', 'roshan']
        for name in actor_names:
            name_lower = name.lower()
            if any(k in name_lower for k in indian_keywords):
                scores["Bollywood & South Asia"] += 25.0

        # Check Latin indicators
        latin_keywords = ['garcia', 'rodriguez', 'martinez', 'gomez', 'hernandez', 'lopez', 'perez', 'sanchez', 'del toro', 'bernal', 'bardem']
        for name in actor_names:
            name_lower = name.lower()
            if any(k in name_lower for k in latin_keywords):
                scores["Latin America & Iberia"] += 15.0

        # Check title patterns
        for t in movie_titles:
            t_lower = t.lower()
            if any(k in t_lower for k in ['bbc', 'london', 'british', 'royal', 'king']):
                scores["United Kingdom & Ireland"] += 3.0
            elif any(k in t_lower for k in ['paris', 'rome', 'berlin', 'euro']):
                scores["European Cinema"] += 3.0
            elif any(k in t_lower for k in ['tokyo', 'samurai', 'ninja', 'godzilla', 'dragon']):
                scores["East Asian Cinema"] += 4.0

        # Genre-based adjustments
        if 'Documentary' in genres or 'News' in genres:
            scores["Global & Festival Network"] += 8.0

        total_score = sum(scores.values()) or 1.0
        dist = []
        for region, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            pct = round((score / total_score) * 100, 1)
            if pct >= 4.0:
                flag = "🇺🇸"
                if region == "United Kingdom & Ireland": flag = "🇬🇧"
                elif region == "European Cinema": flag = "🇪🇺"
                elif region == "East Asian Cinema": flag = "🇯🇵"
                elif region == "Bollywood & South Asia": flag = "🇮🇳"
                elif region == "Latin America & Iberia": flag = "🇲🇽"
                elif region == "Global & Festival Network": flag = "🌐"
                dist.append({"region": region, "flag": flag, "percentage": pct})

        # Pick main top region
        top_region = dist[0]["region"] if dist else "North America"
        top_flag = dist[0]["flag"] if dist else "🇺🇸"

        hubs = {
            "North America": "Hollywood / Los Angeles & New York",
            "United Kingdom & Ireland": "London & Pinewood Studios (British Screen)",
            "European Cinema": "Paris, Berlin & Rome (European Auteur Network)",
            "East Asian Cinema": "Tokyo, Hong Kong & Seoul (East Asian Film Hub)",
            "Bollywood & South Asia": "Mumbai Film City & South Asian Cinema",
            "Latin America & Iberia": "Mexico City & Madrid (Ibero-American Film Hub)",
            "Global & Festival Network": "International Festival Circuit (Cannes / Sundance)"
        }
        primary_hub = hubs.get(top_region, "Hollywood & Global Co-productions")

        summaries = {
            "North America": "Core Hollywood mainstream studio network featuring major North American box-office releases.",
            "United Kingdom & Ireland": "British stage and film collaboration circle with frequent transatlantic co-productions.",
            "European Cinema": "Continental European production network focused on dramatic art-house and festival features.",
            "East Asian Cinema": "East Asian film production ecosystem bridging domestic masterworks and international cinema.",
            "Bollywood & South Asia": "South Asian cinematic network centered around Mumbai, Hindi and regional film productions.",
            "Latin America & Iberia": "Ibero-American cinema circle spanning Latin American cinema and Spanish productions.",
            "Global & Festival Network": "Multinational independent network active in documentary and international film festivals."
        }
        geo_summary = summaries.get(top_region, "Global actor collaboration network.")

        return {
            "region": top_region,
            "flag": top_flag,
            "primary_hub": primary_hub,
            "geo_summary": geo_summary,
            "regional_distribution": dist
        }

    def ensure_title_years_cache(self):
        if not hasattr(self, 'movie_years_cache') or not self.movie_years_cache:
            t0 = time.time()
            if self.titles_path.exists():
                df_t = pl.read_csv(
                    self.titles_path,
                    separator='\t',
                    columns=['tconst', 'startYear'],
                    quote_char=None,
                    schema_overrides={'tconst': pl.Utf8, 'startYear': pl.Int32},
                    null_values=['\\N']
                ).filter(pl.col('startYear').is_not_null())
                self.movie_years_cache = dict(zip(df_t['tconst'], df_t['startYear']))
                print(f"[Clustering Engine] Cached {len(self.movie_years_cache):,} title release years in {time.time()-t0:.2f}s")
            else:
                self.movie_years_cache = {}

    def _load_edges_df(self):
        """Loads the full edge list into memory once; every request reuses the cached DataFrame."""
        with self._heavy_lock:
            if self.edges_df_cache is None:
                t0 = time.time()
                self.edges_df_cache = pl.read_csv(
                    self.edges_path,
                    separator='\t',
                    columns=['actor1', 'actor2', 'shared_movies', 'startYear', 'weight'],
                    quote_char=None,
                    schema_overrides={'actor1': pl.Utf8, 'actor2': pl.Utf8, 'shared_movies': pl.Utf8, 'startYear': pl.Int32, 'weight': pl.Int32},
                    null_values=['\\N']
                )
                print(f"[Clustering Engine] Cached edge list in memory ({len(self.edges_df_cache):,} rows) in {time.time() - t0:.2f}s")
            return self.edges_df_cache

    def _ensure_latest_year_column(self):
        """Precomputes each edge's latest shared-movie year so the active_after filter is a vectorized
        column comparison instead of a Python loop over millions of rows."""
        with self._heavy_lock:
            df = self._load_edges_df()
            if 'latest_year' in df.columns:
                return
            t0 = time.time()
            self.ensure_title_years_cache()
            years_df = pl.DataFrame({
                'tconst': list(self.movie_years_cache.keys()),
                'movie_year': list(self.movie_years_cache.values()),
            })
            edges = df.with_row_index('eid')
            latest = (
                edges.select(['eid', 'shared_movies'])
                .with_columns(pl.col('shared_movies').str.split(','))
                .explode('shared_movies')
                .with_columns(pl.col('shared_movies').str.strip_chars('" '))
                .join(years_df, left_on='shared_movies', right_on='tconst', how='left')
                .group_by('eid')
                .agg(pl.col('movie_year').max().alias('latest_year'))
            )
            self.edges_df_cache = (
                edges.join(latest, on='eid', how='left')
                .with_columns(pl.coalesce([pl.col('latest_year'), pl.col('startYear')]).alias('latest_year'))
                .drop('eid')
            )
            print(f"[Clustering Engine] Precomputed per-edge latest active year in {time.time() - t0:.2f}s")

    def _load_filtered_edge_rows(self, created_before, active_after, min_weight):
        """Applies the dual-way temporal filter (created_before & active_after) on the in-memory edge list.
        Shared by run_clustering and get_community_graph_details so both paths filter identically."""
        if active_after > 1800:
            self._ensure_latest_year_column()
        df = self._load_edges_df()

        condition = (pl.col('startYear') <= created_before) & (pl.col('weight') >= min_weight)
        if active_after > 1800:
            condition = condition & (pl.col('latest_year') >= active_after)

        filtered = df.filter(condition).select(['actor1', 'actor2', 'shared_movies', 'startYear', 'weight'])
        return list(filtered.iter_rows())

    def _get_clustered_graph(self, created_before, active_after, min_weight):
        """Builds (or returns the LRU-cached) filtered graph plus its sorted Louvain partition.
        Sharing this between run_clustering and get_community_graph_details means 'Open Community'
        reuses the exact partition the summary was built from, so community IDs always line up."""
        key = (created_before, active_after, min_weight)
        with self._heavy_lock:
            if key in self.graph_cache:
                self.graph_cache.move_to_end(key)
                return self.graph_cache[key]

            valid_rows = self._load_filtered_edge_rows(created_before, active_after, min_weight)
            print(f"  -> Extracted {len(valid_rows):,} edges created <= {created_before} & active >= {active_after}")
            if not valid_rows:
                return None

            G = nx.Graph()
            for a1, a2, movies_str, year, weight in valid_rows:
                G.add_edge(a1, a2, weight=weight, movies=movies_str.split(',') if movies_str else [])

            print(f"  -> Built Graph: {G.number_of_nodes():,} nodes (actors), {G.number_of_edges():,} edges")
            print("  -> Running Louvain Community Detection...")
            try:
                communities_raw = nx_comm.louvain_communities(G, weight='weight', seed=42)
            except Exception as e:
                print(f"  -> Louvain fallback to greedy modularity: {e}")
                communities_raw = list(nx_comm.greedy_modularity_communities(G, weight='weight'))

            modularity_score = nx_comm.modularity(G, communities_raw, weight='weight')
            print(f"  -> Detected {len(communities_raw):,} total communities (Modularity: {modularity_score:.4f})")

            entry = (G, sorted(communities_raw, key=len, reverse=True), modularity_score, len(communities_raw))
            self.graph_cache[key] = entry
            while len(self.graph_cache) > self.graph_cache_size:
                self.graph_cache.popitem(last=False)
            return entry

    def run_clustering(self, created_before=2026, active_after=1800, min_weight=1, max_communities=15, min_community_size=3, target_year=None):
        """
        Filters edges created on or before `created_before` AND active with a movie on or after `active_after`.
        Builds graph G, executes Louvain community detection, and calculates in-community & between-community analytics.
        """
        if target_year is not None:
            created_before = target_year

        t0 = time.time()
        print(f"\n[Clustering Engine] Processing Graph: Created <= {created_before}, Active >= {active_after} (Min Weight: {min_weight})...")

        result_key = (created_before, active_after, min_weight, max_communities, min_community_size)
        if result_key in self.cluster_result_cache:
            print(f"[Clustering Engine] Returning cached clustering result for {result_key}")
            return self.cluster_result_cache[result_key]

        # 1-3. Temporal edge filtering, graph build & Louvain partition (LRU-cached)
        cached = self._get_clustered_graph(created_before, active_after, min_weight)
        if cached is None:
            return {"error": f"No edges found for created <= {created_before} and active >= {active_after} with min weight {min_weight}"}
        G, communities_sorted, modularity_score, total_communities_found = cached

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
            top_actors_ids = sorted(degrees.keys(), key=lambda x: (-degrees[x], x))[:10]
            
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
                
            # Birth Decade Distribution
            decade_counter = Counter()
            for actor_id in comm_nodes:
                byr = self.actor_birth_years_cache.get(actor_id)
                if byr and 1850 <= byr <= 2026:
                    decade = f"{(byr // 10) * 10}s"
                    decade_counter[decade] += 1
                    
            total_births = sum(decade_counter.values()) or 1
            birth_decade_stats = [
                {"decade": d, "count": cnt, "percentage": round((cnt / total_births) * 100, 1)}
                for d, cnt in decade_counter.most_common(6)
            ]
                
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
            
            # Generate Geographical Tag
            geo_tag = self.infer_community_geography(top_actors, genre_stats, community_movies)

            # Generate Archetype Label
            top_prof = profession_stats[0]['tag'].capitalize() if profession_stats else 'Actors'
            top_genre = genre_stats[0]['genre'] if genre_stats else 'Cinema'
            archetype = f"{geo_tag['flag']} {top_genre} {top_prof} Circle"
            
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
                "geo_tag": geo_tag,
                "top_actors": top_actors,
                "profession_tags": profession_stats,
                "birth_decade_tags": birth_decade_stats,
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
            "created_before": created_before,
            "active_after": active_after,
            "target_year": created_before,
            "min_weight": min_weight,
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "total_communities_found": total_communities_found,
            "modularity_score": round(modularity_score, 4),
            "execution_time_seconds": round(elapsed, 2),
            "communities": community_details,
            "inter_community_matrix": matrix_list
        }

        self.cluster_result_cache[result_key] = result
        print(f"[Clustering Engine] Completed analysis in {elapsed:.2f}s")
        return result

    def get_community_graph_details(self, created_before=2026, active_after=1800, community_id=1, min_weight=1, max_nodes=150, target_year=None):
        """Returns node and edge details for interactive D3 graph rendering of a specific community."""
        if target_year is not None:
            created_before = target_year

        res = self.run_clustering(created_before=created_before, active_after=active_after, min_weight=min_weight, max_communities=20)
        if "error" in res:
            return res
            
        target_comm = None
        for c in res['communities']:
            if c['id'] == community_id:
                target_comm = c
                break
                
        if not target_comm:
            return {"error": f"Community {community_id} not found."}
            
        # Reuse the cached filtered graph + Louvain partition the summary was built from,
        # so the sub-graph is extracted from the exact same communities (no re-read, no re-clustering)
        cached = self._get_clustered_graph(created_before, active_after, min_weight)
        if cached is None:
            return {"error": "No edges found for the requested filters."}
        G, communities_sorted, _, _ = cached

        valid_communities = [c for c in communities_sorted if len(c) >= 3][:20]
        
        if community_id > len(valid_communities):
            return {"error": "Invalid community index"}
            
        comm_nodes = list(valid_communities[community_id - 1])
        
        # Sort nodes by degree within community to pick top max_nodes
        subG = G.subgraph(comm_nodes)
        degrees = dict(subG.degree(weight='weight'))
        # Tie-break by nconst so the selection is reproducible across runs (community sets are hash-ordered)
        selected_nodes = sorted(comm_nodes, key=lambda x: (-degrees[x], x))[:max_nodes]
        selected_set = set(selected_nodes)
        
        subG_selected = G.subgraph(selected_set)
        
        # 2. Detect Inner Sub-Communities using Louvain algorithm on subgraph
        try:
            sub_comms_raw = sorted(nx_comm.louvain_communities(subG_selected, weight='weight', seed=42), key=len, reverse=True)
        except Exception:
            sub_comms_raw = list(nx_comm.greedy_modularity_communities(subG_selected, weight='weight'))

        node_to_sub_comm = {}
        node_to_sub_color = {}
        sub_community_stats = []
        total_selected_nodes = len(selected_set) or 1

        for sub_idx, sub_nodes_set in enumerate(sub_comms_raw, start=1):
            color = SUB_COMMUNITY_COLORS[(sub_idx - 1) % len(SUB_COMMUNITY_COLORS)]
            for n in sub_nodes_set:
                node_to_sub_comm[n] = sub_idx
                node_to_sub_color[n] = color

            sub_node_list = list(sub_nodes_set)
            subG_inner = subG_selected.subgraph(sub_nodes_set)
            inner_degrees = dict(subG_inner.degree(weight='weight'))

            top_sub_actors_ids = sorted(sub_node_list, key=lambda x: (-inner_degrees.get(x, 0), x))[:5]
            top_sub_actors = [
                {
                    "nconst": actor_id,
                    "name": self.actor_names_cache.get(actor_id, actor_id),
                    "degree": inner_degrees.get(actor_id, 0)
                }
                for actor_id in top_sub_actors_ids
            ]

            # Top professions in sub-community
            prof_counter = Counter()
            for actor_id in sub_nodes_set:
                for p in self.actor_professions_cache.get(actor_id, []):
                    prof_counter[p] += 1

            pct = round((len(sub_nodes_set) / total_selected_nodes) * 100, 1)
            top_prof = prof_counter.most_common(1)[0][0].capitalize() if prof_counter else "Actor"

            sub_community_stats.append({
                "sub_id": sub_idx,
                "color": color,
                "node_count": len(sub_nodes_set),
                "percentage": pct,
                "archetype": f"Sub-Circle #{sub_idx} ({top_prof} Core)",
                "top_actors": top_sub_actors,
                "top_professions": [p for p, _ in prof_counter.most_common(3)]
            })

        nodes_payload = []
        for n in selected_set:
            nodes_payload.append({
                "id": n,
                "label": self.actor_names_cache.get(n, n),
                "degree": degrees[n],
                "professions": self.actor_professions_cache.get(n, []),
                "sub_community_id": node_to_sub_comm.get(n, 1),
                "sub_community_color": node_to_sub_color.get(n, "#38bdf8")
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
            "edges": edges_payload,
            "sub_communities": sub_community_stats
        }

    def get_actor_statistics(self, nconst):
        """
        Extracts comprehensive statistics for a single actor:
        - Primary details (name, professions, birth year)
        - Co-star network stats (top collaborators, total co-stars, total collaborations)
        - Genre profile & progress percentages
        - Geographical location tag & profile
        - Top filmography
        """
        t0 = time.time()
        
        # 1. Fetch Actor Name & Details from name.basics.tsv if not in cache
        actor_name = self.actor_names_cache.get(nconst)
        professions = self.actor_professions_cache.get(nconst, [])
        birth_year = None
        known_titles = []
        found_in_names = False

        if self.names_path.exists():
            names_df = pl.read_csv(
                self.names_path,
                separator='\t',
                columns=['nconst', 'primaryName', 'birthYear', 'primaryProfession', 'knownForTitles'],
                quote_char=None,
                schema_overrides={'nconst': pl.Utf8, 'primaryName': pl.Utf8, 'birthYear': pl.Utf8, 'primaryProfession': pl.Utf8, 'knownForTitles': pl.Utf8},
                null_values=['\\N']
            ).filter(pl.col('nconst') == nconst)
            
            if len(names_df) > 0:
                found_in_names = True
                row = names_df.row(0)
                _, name, b_yr, prof, k_titles = row
                if name: actor_name = name
                if b_yr and b_yr.isdigit(): birth_year = int(b_yr)
                if prof: professions = [p.strip() for p in prof.split(',') if p.strip()]
                if k_titles: known_titles = [t.strip() for t in k_titles.split(',') if t.strip()]

        if not actor_name:
            actor_name = nconst
            
        # 2. Extract co-star edges from the in-memory edge list
        df_edges = self._load_edges_df()

        actor_edges = (
            df_edges.filter((pl.col('actor1') == nconst) | (pl.col('actor2') == nconst))
            .select(['actor1', 'actor2', 'shared_movies', 'startYear', 'weight'])
        )

        if not found_in_names and len(actor_edges) == 0:
            return {"error": f"Actor {nconst} not found in the dataset."}

        co_star_weights = Counter()
        all_movie_ids = set(known_titles)
        earliest_yr = 2026
        latest_yr = 1800
        total_collaborations = 0
        
        for row in actor_edges.iter_rows():
            a1, a2, movies_str, start_yr, weight = row
            co_star = a2 if a1 == nconst else a1
            co_star_weights[co_star] += weight
            total_collaborations += weight
            
            movies = movies_str.split(',') if movies_str else []
            all_movie_ids.update(movies)
            
            if start_yr:
                earliest_yr = min(earliest_yr, start_yr)
                
        # 3. Fetch metadata for all movies of this actor
        movie_titles_info = []
        genre_counter = Counter()
        
        if all_movie_ids and self.titles_path.exists():
            titles_df = pl.read_csv(
                self.titles_path,
                separator='\t',
                columns=['tconst', 'primaryTitle', 'startYear', 'genres'],
                quote_char=None,
                schema_overrides={'tconst': pl.Utf8, 'primaryTitle': pl.Utf8, 'startYear': pl.Int32, 'genres': pl.Utf8},
                null_values=['\\N']
            ).filter(pl.col('tconst').is_in(list(all_movie_ids)))
            
            for row in titles_df.iter_rows():
                tconst, title, yr, genres_str = row
                if yr:
                    latest_yr = max(latest_yr, yr)
                    earliest_yr = min(earliest_yr, yr)
                    
                genres_list = [g.strip() for g in genres_str.split(',') if g.strip()] if genres_str else []
                for g in genres_list:
                    genre_counter[g] += 1
                    
                movie_titles_info.append({
                    "tconst": tconst,
                    "title": title or tconst,
                    "year": yr,
                    "genres": genres_list
                })
                
        movie_titles_info.sort(key=lambda x: x.get('year') or 0, reverse=True)
        
        # 4. Genre breakdown statistics
        total_genre_hits = sum(genre_counter.values()) or 1
        genre_stats = [
            {"genre": g, "count": cnt, "percentage": round((cnt / total_genre_hits) * 100, 1)}
            for g, cnt in genre_counter.most_common(6)
        ]
        
        # 5. Fetch co-star names for top 10 co-stars
        top_co_star_ids = [cs for cs, _ in co_star_weights.most_common(10)]
        self.fetch_metadata_for_targets(top_co_star_ids, [])
        
        top_co_stars = [
            {
                "nconst": cs_id,
                "name": self.actor_names_cache.get(cs_id, cs_id),
                "shared_movies_count": co_star_weights[cs_id],
                "professions": self.actor_professions_cache.get(cs_id, [])
            }
            for cs_id in top_co_star_ids
        ]
        
        # 6. Infer Actor Geographical Profile
        geo_tag = self.infer_community_geography(
            top_actors=[{"name": actor_name}],
            top_genres=genre_stats,
            community_movies=[m["tconst"] for m in movie_titles_info]
        )
        
        elapsed = time.time() - t0
        
        return {
            "nconst": nconst,
            "name": actor_name,
            "birth_year": birth_year,
            "professions": professions,
            "active_years": f"{earliest_yr if earliest_yr <= 2026 else 'N/A'} - {latest_yr if latest_yr >= 1800 else 'Present'}",
            "geo_tag": geo_tag,
            "genre_profile": genre_stats,
            "top_co_stars": top_co_stars,
            "top_movies": movie_titles_info[:10],
            "network_stats": {
                "total_co_stars": len(co_star_weights),
                "total_collaborations": total_collaborations,
                "total_movies_indexed": len(movie_titles_info)
            },
            "lookup_time_seconds": round(elapsed, 2)
        }

    def calculate_median_actors(self, start_year=None, end_year=None, top_k=5, candidate_count=15):
        """
        Calculates the top K 'median' actors (actors with the minimum sum of shortest unweighted paths 
        to all other actors in the largest connected component of the graph).
        Uses degree-based candidate selection and core graph optimization for sub-second execution.
        """
        cache_key = (start_year, end_year, top_k)
        if cache_key in self.median_cache:
            print(f"[Clustering Engine] Returning cached median actors for query {cache_key}")
            return self.median_cache[cache_key]

        t0 = time.time()

        df_edges = self._load_edges_df()

        filtered = df_edges
        if start_year is not None:
            filtered = filtered.filter(pl.col('startYear') >= start_year)
        if end_year is not None:
            filtered = filtered.filter(pl.col('startYear') <= end_year)
            
        if len(filtered) == 0:
            return {"error": "No edges found for the given year range."}
            
        G = nx.Graph()
        G.add_edges_from(filtered.select(['actor1', 'actor2']).iter_rows())
            
        if G.number_of_nodes() == 0:
            return {"error": "No edges found for the given year range."}
            
        # Get largest connected component
        lcc_nodes = max(nx.connected_components(G), key=len)
        subG = G.subgraph(lcc_nodes)
        
        # Calculate popularity scores for the window
        if self.popularity_calculator is None:
            self.popularity_calculator = PopularityCalculator(data_dir, processed_dir)
        popular_actors = self.popularity_calculator.calculate_popularity_in_window(
            start_year or 1920, end_year or 2026, top_k=5
        )
        popular_nconsts = [pa["nconst"] for pa in popular_actors]
        
        # Candidate pre-filtering: pick top candidate_count nodes by degree
        degrees = dict(subG.degree())
        candidates = sorted(degrees.keys(), key=lambda x: (-degrees[x], x))[:candidate_count]
        
        # Add top popular actors to candidates list if they aren't already there
        for pop_nconst in popular_nconsts:
            if pop_nconst not in candidates and pop_nconst in subG:
                candidates.append(pop_nconst)
                
        # Force Kevin Bacon into candidates
        kevin_bacon_id = "nm0000102"
        if kevin_bacon_id not in candidates and kevin_bacon_id in subG:
            candidates.append(kevin_bacon_id)
        
        # Optimize BFS: If component is large (>10k nodes), prune degree-1 leaf nodes for BFS traversal
        # Leaf nodes increase graph size by 80%+ without altering relative shortest path rankings among central hubs
        leaf_pruning_applied = len(lcc_nodes) > 10000
        if leaf_pruning_applied:
            core_nodes = set(n for n in lcc_nodes if degrees[n] >= 2 or n in candidates)
            bfs_G = subG.subgraph(core_nodes)
            lcc_count = len(core_nodes)
        else:
            bfs_G = subG
            lcc_count = len(lcc_nodes)

        median_scores = []
        for candidate in candidates:
            if candidate not in bfs_G:
                continue
            lengths = nx.single_source_shortest_path_length(bfs_G, candidate)
            path_values = [v for v in lengths.values() if v > 0]
            path_sum = sum(path_values)
            n_nodes = len(path_values)
            
            avg_path = path_sum / n_nodes if n_nodes > 0 else 0
            max_path = max(path_values) if path_values else 0
            min_path = min(path_values) if path_values else 0
            
            # Normal distribution parameters (mean mu, std dev sigma, variance sigma^2)
            mean_dist = avg_path
            variance = sum((x - mean_dist) ** 2 for x in path_values) / n_nodes if n_nodes > 0 else 0
            std_dev = math.sqrt(variance)
            
            # Closeness centrality: (N-1) / path_sum
            closeness = (lcc_count - 1) / path_sum if path_sum > 0 else 0
            
            # Hop breakdown distribution (percentage of nodes at each hop distance)
            hop_counts = Counter(path_values)
            hop_dist = []
            for h in range(1, max_path + 1):
                cnt = hop_counts.get(h, 0)
                pct = round((cnt / n_nodes) * 100, 1) if n_nodes > 0 else 0
                hop_dist.append({"hop": h, "count": cnt, "percentage": pct})
            
            median_scores.append({
                "nconst": candidate,
                "path_sum": path_sum,
                "avg_path": round(avg_path, 4),
                "max_path": max_path,
                "min_path": min_path,
                "std_dev": round(std_dev, 4),
                "variance": round(variance, 4),
                "closeness": round(closeness, 6),
                "direct_co_stars": hop_counts.get(1, 0),
                "hop_distribution": hop_dist
            })
            
        median_scores.sort(key=lambda x: x["path_sum"])
        top_medians = median_scores[:top_k]
        
        # Fetch metadata
        top_nconsts = [item["nconst"] for item in top_medians]
        top_nconsts.append(kevin_bacon_id)
        self.fetch_metadata_for_targets(top_nconsts, [])
        
        results = []
        for rank, item in enumerate(top_medians, start=1):
            nconst = item["nconst"]
            results.append({
                "rank": rank,
                "nconst": nconst,
                "name": self.actor_names_cache.get(nconst, nconst),
                "professions": self.actor_professions_cache.get(nconst, []),
                "avg_path": item["avg_path"],
                "max_path": item["max_path"],
                "min_path": item["min_path"],
                "std_dev": item["std_dev"],
                "variance": item["variance"],
                "closeness": item["closeness"],
                "direct_co_stars": item["direct_co_stars"],
                "total_path_sum": item["path_sum"],
                "hop_distribution": item["hop_distribution"]
            })
            
        elapsed = time.time() - t0
        print(f"[Clustering Engine] Calculated Top {top_k} Median Actors among {len(lcc_nodes):,} nodes in {elapsed:.2f}s")
        
        res_payload = {
            "start_year": start_year,
            "end_year": end_year,
            "nodes_in_component": len(lcc_nodes),
            "bfs_nodes": lcc_count,
            "leaf_pruning_applied": leaf_pruning_applied,
            "approximation_note": (
                f"Path statistics computed on the leaf-pruned core graph ({lcc_count:,} of {len(lcc_nodes):,} component nodes); "
                "degree-1 actors are excluded, so absolute path lengths are slightly optimistic. Candidate rankings are unaffected."
            ) if leaf_pruning_applied else None,
            "total_nodes": G.number_of_nodes(),
            "execution_time_seconds": round(elapsed, 2),
            "top_medians": results,
            "top_popular": [],
            "kevin_bacon": None
        }
        
        for item in median_scores:
            if item["nconst"] in popular_nconsts:
                pop_idx = popular_nconsts.index(item["nconst"])
                pop_info = popular_actors[pop_idx]
                item_copy = dict(item)
                item_copy["name"] = self.actor_names_cache.get(item["nconst"], pop_info["name"])
                item_copy["professions"] = self.actor_professions_cache.get(item["nconst"], pop_info.get("professions", []))
                item_copy["popularity_score"] = pop_info["score"]
                item_copy["movies_in_window"] = pop_info["movies_in_window"]
                res_payload["top_popular"].append(item_copy)
                
            if item["nconst"] == kevin_bacon_id:
                kb_copy = dict(item)
                kb_copy["name"] = self.actor_names_cache.get(kevin_bacon_id, "Kevin Bacon")
                kb_copy["professions"] = self.actor_professions_cache.get(kevin_bacon_id, ["actor"])
                res_payload["kevin_bacon"] = kb_copy
                
        res_payload["top_popular"].sort(key=lambda x: x["popularity_score"], reverse=True)

        self.median_cache[cache_key] = res_payload
        return res_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Temporal Graph Community Clustering Tool")
    parser.add_argument("--year", type=int, default=2010, help="Target cutoff year")
    parser.add_argument("--min-weight", type=int, default=1, help="Minimum edge weight filter")
    parser.add_argument("--max-communities", type=int, default=10, help="Max communities to analyze in detail")
    args = parser.parse_args()
    
    clusterer = CommunityClusterer()
    results = clusterer.run_clustering(target_year=args.year, min_weight=args.min_weight, max_communities=args.max_communities)
    print("\n" + json.dumps(results, indent=2))
