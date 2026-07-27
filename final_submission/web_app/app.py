from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
import uvicorn
import sys
import os

# Add parent directory to sys.path to import community_clustering
web_app_dir = Path(__file__).parent.resolve()
submission_dir = web_app_dir.parent.resolve()
sys.path.append(str(submission_dir))

from community_clustering import CommunityClusterer

app = FastAPI(
    title="Actor Network Community Explorer",
    description="Interactive temporal community clustering engine for Hollywood co-starring graph",
    version="1.0.0"
)

# Global Clusterer instance
clusterer = CommunityClusterer()

# Serve static directory
static_dir = web_app_dir / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class ClusterRequest(BaseModel):
    created_before: int = 2010
    active_after: int = 1800
    min_weight: int = 1
    max_communities: int = 15
    year: int | None = None  # Backwards compatibility alias for created_before

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>Actor Network Community Explorer Backend Running</h1>")

@app.get("/api/years")
async def get_available_years():
    """Returns year boundaries for the UI sliders."""
    return {
        "min_year": 1920,
        "max_year": 2026,
        "default_created_before": 2010,
        "default_active_after": 1800
    }

@app.post("/api/cluster")
async def run_clustering_endpoint(req: ClusterRequest):
    """Executes graph community clustering with dual-way temporal edge filtering (created_before & active_after)."""
    try:
        created_before_year = req.year if req.year is not None else req.created_before
        results = clusterer.run_clustering(
            created_before=created_before_year,
            active_after=req.active_after,
            min_weight=req.min_weight,
            max_communities=req.max_communities
        )
        if "error" in results:
            raise HTTPException(status_code=400, detail=results["error"])
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/community/{created_before}/{community_id}")
async def get_community_details_endpoint(
    created_before: int,
    community_id: int,
    active_after: int = Query(default=1800),
    min_weight: int = Query(default=1, ge=1),
    max_nodes: int = Query(default=150, le=500)
):
    """Fetches sub-graph nodes and edges for D3 visualization of a specific community."""
    try:
        res = clusterer.get_community_graph_details(
            created_before=created_before,
            active_after=active_after,
            community_id=community_id,
            min_weight=min_weight,
            max_nodes=max_nodes
        )
        if "error" in res:
            raise HTTPException(status_code=404, detail=res["error"])
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/actor/{nconst}")
async def get_actor_statistics_endpoint(nconst: str):
    """Fetches comprehensive actor statistics including genre profile, geographical tag, and co-star network."""
    try:
        res = clusterer.get_actor_statistics(nconst=nconst)
        if "error" in res:
            raise HTTPException(status_code=404, detail=res["error"])
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"Starting Web Application server on http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
