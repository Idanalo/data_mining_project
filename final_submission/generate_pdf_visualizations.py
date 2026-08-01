import json
import math
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import requests
import time
from pathlib import Path
from community_clustering import CommunityClusterer

def get_entropy(probabilities):
    entropy = 0
    for p in probabilities:
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy

def generate_entropy_graph():
    print("Generating Entropy Graph...")
    clusterer = CommunityClusterer()
    
    windows = [(2000, 2004), (2005, 2009), (2010, 2014), (2015, 2019), (2020, 2024)]
    window_labels = [f"{w[0]}-{w[1]}" for w in windows]
    avg_geo_entropies = []
    avg_genre_entropies = []
    
    for start_year, end_year in windows:
        print(f"Processing {start_year}-{end_year}...")
        results = clusterer.run_clustering(created_before=end_year, active_after=start_year)
        communities = results.get("communities", [])
        
        # Take top 15 communities by size
        top_communities = sorted(communities, key=lambda x: x["node_count"], reverse=True)[:15]
        
        geo_entropies = []
        genre_entropies = []
        
        for c in top_communities:
            # Geo Entropy
            geo_tag = c.get("geo_tag", {})
            reg_dist = geo_tag.get("regional_distribution", [])
            # reg_dist has items like {'region': 'US/Canada', 'percentage': 85.0}
            probs = [item["percentage"] / 100.0 for item in reg_dist]
            geo_entropies.append(get_entropy(probs))
            
            # Genre Entropy
            genre_stats = c.get("top_genres", [])
            probs = [item["percentage"] / 100.0 for item in genre_stats]
            genre_entropies.append(get_entropy(probs))
                
        avg_geo_entropies.append(sum(geo_entropies) / len(geo_entropies) if geo_entropies else 0)
        avg_genre_entropies.append(sum(genre_entropies) / len(genre_entropies) if genre_entropies else 0)
        
    plt.figure(figsize=(10, 6))
    sns.set_theme(style="whitegrid")
    
    plt.plot(window_labels, avg_geo_entropies, marker='o', linewidth=2.5, label='Geographic Entropy', color='#38bdf8')
    plt.plot(window_labels, avg_genre_entropies, marker='s', linewidth=2.5, label='Genre Entropy', color='#fb923c')
    
    plt.title('Average Entropy of Top 15 Hollywood Communities Over Time', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('Decade', fontsize=12)
    plt.ylabel('Shannon Entropy (Bits)', fontsize=12)
    plt.legend(fontsize=11)
    
    plt.tight_layout()
    plt.savefig('entropy_graph.png', dpi=300)
    plt.close()
    print("Saved entropy_graph.png")

def generate_popular_actors_timeline():
    print("Generating Popular Actors Timeline...")
    with open('web_app/static/popular_actors_timeline.json', 'r', encoding='utf-8') as f:
        timeline = json.load(f)
        
    years = []
    scores = []
    labels = []
    
    # We will sample every 4 years to avoid cluttering the graph text
    for item in timeline:
        year = int(item["year"])
        if year >= 1950 and year <= 2023:
            top_actor = item["top_actors"][0]
            years.append(year)
            scores.append(top_actor["score"])
            if year % 4 == 0:
                labels.append((year, top_actor["score"], top_actor["name"]))
                
    plt.figure(figsize=(12, 6))
    sns.set_theme(style="whitegrid")
    
    plt.plot(years, scores, linewidth=2, color='#a855f7')
    plt.fill_between(years, scores, color='#a855f7', alpha=0.1)
    
    # Annotate top actors
    for (y, s, name) in labels:
        plt.annotate(name, (y, s), textcoords="offset points", xytext=(0,10), ha='center', fontsize=8, rotation=45)
        plt.scatter(y, s, color='#ec4899', zorder=5)
        
    plt.title('Hollywood\'s Leading Actors Over Time (Popularity Score)', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('Year', fontsize=12)
    plt.ylabel('Popularity Score (Window [Y-1, Y+1])', fontsize=12)
    
    plt.tight_layout()
    plt.savefig('popular_actors_timeline.png', dpi=300)
    plt.close()
    print("Saved popular_actors_timeline.png")

def generate_median_comparison():
    print("Generating Median Actor Comparison...")
    # Because computing the shortest paths from scratch takes ~6 minutes,
    # we will query the running backend server to leverage its cache!
    # If the user just calculated medians, the cache will return instantly.
    # Otherwise, it might take a few minutes.
    
    url = "http://127.0.0.1:8000/api/median_actors"
    payload = {
        "start_year": None,
        "end_year": None,
        "top_k": 5
    }
    
    print("Requesting median data from backend (this may take a moment if not cached)...")
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"Failed to get data from API: {e}")
        return
        
    top_median = data["top_medians"][0] if data.get("top_medians") else None
    top_popular = data["top_popular"][0] if data.get("top_popular") else None
    kevin = data.get("kevin_bacon")
    
    if not (top_median and top_popular and kevin):
        print("Missing required actor data from API.")
        return
        
    actors = [
        {"Category": "True Median (Network Center)", "Name": top_median["name"], "Closeness": top_median["closeness"], "Avg Path": top_median["avg_path"], "Co-Stars": top_median["direct_co_stars"]},
        {"Category": "Most Popular", "Name": top_popular["name"], "Closeness": top_popular["closeness"], "Avg Path": top_popular["avg_path"], "Co-Stars": top_popular["direct_co_stars"]},
        {"Category": "The Benchmark", "Name": kevin["name"], "Closeness": kevin["closeness"], "Avg Path": kevin["avg_path"], "Co-Stars": kevin["direct_co_stars"]}
    ]
    
    df = pd.DataFrame(actors)
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 6))
    fig.suptitle('Actor Centrality Comparison (All Time 1920-2026)', fontsize=16, fontweight='bold')
    
    colors = ['#34d399', '#38bdf8', '#fb923c']
    
    sns.barplot(ax=axes[0], data=df, x='Category', y='Closeness', palette=colors)
    axes[0].set_title('Closeness Centrality (Higher is Better)')
    axes[0].set_ylabel('Closeness')
    axes[0].tick_params(axis='x', rotation=15)
    
    sns.barplot(ax=axes[1], data=df, x='Category', y='Avg Path', palette=colors)
    axes[1].set_title('Average Path Length μ (Lower is Better)')
    axes[1].set_ylabel('Degrees of Separation')
    axes[1].tick_params(axis='x', rotation=15)
    
    sns.barplot(ax=axes[2], data=df, x='Category', y='Co-Stars', palette=colors)
    axes[2].set_title('Direct Co-Stars (1-Hop Reach)')
    axes[2].set_ylabel('Count')
    axes[2].tick_params(axis='x', rotation=15)
    
    # Add names to the bars
    for ax in axes:
        for i, row in df.iterrows():
            ax.text(i, ax.patches[i].get_height()/2, row['Name'], color='white', ha='center', va='center', fontweight='bold', fontsize=10, rotation=90)
            
    plt.tight_layout()
    plt.savefig('median_comparison.png', dpi=300)
    plt.close()
    print("Saved median_comparison.png")

if __name__ == "__main__":
    # generate_entropy_graph() # Already saved
    generate_popular_actors_timeline()
    generate_median_comparison()
    print("All visualizations generated successfully.")
