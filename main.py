"""
MindVault — Your Living Memory
FastAPI backend: memory ops + entity extraction for live knowledge graph.
"""

import os, json, hashlib
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import memory_engine as mem

load_dotenv()

app = FastAPI(title="MindVault", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory graph store (persists per server run)
_graph: dict = {"nodes": {}, "edges": []}


# ── Models ─────────────────────────────────────────────────────────

class RememberRequest(BaseModel):
    text: str
    dataset: str = "default"

class RecallRequest(BaseModel):
    query: str
    dataset: str = "default"

class ForgetRequest(BaseModel):
    dataset: str = "default"

class ImproveRequest(BaseModel):
    dataset: str = "default"

class ModeRequest(BaseModel):
    mode: str  # "local" or "cloud"


# ── Helpers ────────────────────────────────────────────────────────

def _node_id(label: str) -> str:
    return hashlib.md5(label.lower().strip().encode()).hexdigest()[:8]


async def _extract_and_store_graph(text: str) -> dict:
    """Call LLM to extract entities/relationships, merge into graph store."""
    entities, relationships = await mem.extract_entities(text)
    new_node_ids = []
    for e in entities:
        nid = _node_id(e["label"])
        if nid not in _graph["nodes"]:
            _graph["nodes"][nid] = {"id": nid, "label": e["label"], "type": e["type"], "new": True}
            new_node_ids.append(nid)
        else:
            _graph["nodes"][nid]["new"] = False

    for r in relationships:
        fid = _node_id(r["from"])
        tid = _node_id(r["to"])
        exists = any(e["from"] == fid and e["to"] == tid for e in _graph["edges"])
        if not exists and fid in _graph["nodes"] and tid in _graph["nodes"]:
            _graph["edges"].append({"from": fid, "to": tid, "label": r.get("label", "")})

    return {"nodes": list(_graph["nodes"].values()), "edges": _graph["edges"], "new_ids": new_node_ids}


# ── Routes ─────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/status")
async def status():
    return {
        "app": "MindVault",
        "version": "2.0",
        "mode": mem.COGNEE_MODE,
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "status": "running",
        "graph_nodes": len(_graph["nodes"]),
    }


@app.get("/api/graph")
async def api_graph():
    return {"nodes": list(_graph["nodes"].values()), "edges": _graph["edges"]}


@app.post("/api/mode")
async def api_mode(req: ModeRequest):
    try:
        new_mode = mem.set_mode(req.mode)
        return {"mode": new_mode, "status": "switched"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/remember")
async def api_remember(req: RememberRequest):
    try:
        mem_result = await mem.remember(req.text, req.dataset)
        graph_result = await _extract_and_store_graph(req.text)
        return {**mem_result, "graph": graph_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recall")
async def api_recall(req: RecallRequest):
    try:
        result = await mem.recall(req.query, req.dataset)
        # Mark relevant nodes (simple keyword match for graph highlight)
        keywords = set(req.query.lower().split())
        highlighted = [
            nid for nid, n in _graph["nodes"].items()
            if any(kw in n["label"].lower() for kw in keywords)
        ]
        result["highlighted_nodes"] = highlighted
        result["graph"] = {"nodes": list(_graph["nodes"].values()), "edges": _graph["edges"]}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/improve")
async def api_improve(req: ImproveRequest):
    try:
        result = await mem.improve(req.dataset)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/forget")
async def api_forget(req: ForgetRequest):
    try:
        result = await mem.forget(req.dataset)
        _graph["nodes"].clear()
        _graph["edges"].clear()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
