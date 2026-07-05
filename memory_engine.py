"""
MindVault Memory Engine
Abstracts Cognee local (open-source) vs Cognee Cloud behind one interface.
Uses Cognee 1.2+ native API: remember/recall/forget/improve
Toggle with COGNEE_MODE=local|cloud in your .env
"""

import os, json
from dotenv import load_dotenv

load_dotenv()

COGNEE_MODE      = os.getenv("COGNEE_MODE", "local")
COGNEE_API_KEY   = os.getenv("COGNEE_API_KEY", "")
COGNEE_API_URL   = os.getenv("COGNEE_API_URL", "https://api.cognee.ai")
COGNEE_TENANT_ID = os.getenv("COGNEE_TENANT_ID", "")
LLM_API_KEY  = os.getenv("LLM_API_KEY", "")
LLM_MODEL    = os.getenv("LLM_MODEL", "groq/gemma2-9b-it")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# Derive the bare model name (strip litellm provider prefix e.g. "groq/")
_model_parts  = LLM_MODEL.split("/", 1)
_bare_model   = _model_parts[-1]          # "gemma2-9b-it"
_provider_pfx = _model_parts[0] if len(_model_parts) > 1 else ""  # "groq"

# Map provider prefix → base URL for direct REST calls in extract_entities
_ENDPOINT_MAP = {
    "groq":       "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT") or _ENDPOINT_MAP.get(_provider_pfx, "https://api.groq.com/openai/v1")

# Set provider-specific API key env vars that litellm needs
os.environ["GROQ_API_KEY"]       = LLM_API_KEY
os.environ["OPENROUTER_API_KEY"] = os.getenv("OPENROUTER_API_KEY", LLM_API_KEY)

_cognee_ready = False


def set_mode(mode: str) -> str:
    """Switch between 'local' and 'cloud' at runtime (no restart needed)."""
    global COGNEE_MODE
    if mode not in ("local", "cloud"):
        raise ValueError("mode must be 'local' or 'cloud'")
    COGNEE_MODE = mode
    return COGNEE_MODE


async def _ensure_cognee():
    global _cognee_ready
    if _cognee_ready:
        return
    import cognee
    os.environ["LLM_API_KEY"]  = LLM_API_KEY
    os.environ["LLM_MODEL"]    = LLM_MODEL
    os.environ["LLM_PROVIDER"] = LLM_PROVIDER
    os.environ["GROQ_API_KEY"] = LLM_API_KEY
    os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
    _cognee_ready = True


# ── remember ──────────────────────────────────────────────────────

async def remember(text: str, dataset: str = "default") -> dict:
    if COGNEE_MODE == "local":
        import cognee
        await _ensure_cognee()
        await cognee.remember(text)
        return {"status": "remembered", "mode": "local", "dataset": dataset}
    else:
        import httpx
        headers = {"X-Api-Key": COGNEE_API_KEY, "X-Tenant-Id": COGNEE_TENANT_ID}
        async with httpx.AsyncClient() as client:
            # /add expects multipart file upload (data=files, datasetName=form field)
            r = await client.post(
                f"{COGNEE_API_URL}/api/v1/add",
                headers=headers,
                files={"data": ("memory.txt", text.encode("utf-8"), "text/plain")},
                data={"datasetName": dataset},
                timeout=120,
            )
            r.raise_for_status()
            # Trigger graph build after adding data
            rc = await client.post(f"{COGNEE_API_URL}/api/v1/cognify",
                              headers=headers, json={"datasets": [dataset]}, timeout=120)
            if rc.status_code not in (200, 201, 202, 409):
                rc.raise_for_status()
        return {"status": "remembered", "mode": "cloud", "dataset": dataset}


# ── recall ────────────────────────────────────────────────────────

async def recall(query: str, dataset: str = "default") -> dict:
    if COGNEE_MODE == "local":
        import cognee
        await _ensure_cognee()
        results = await cognee.recall(query)
        def _extract_text(r):
            if isinstance(r, str):
                return r
            # Cognee 1.2 SearchResult has .text attribute
            if hasattr(r, "text") and r.text:
                return r.text
            if hasattr(r, "payload"):
                p = r.payload
                return p.get("text", str(p)) if isinstance(p, dict) else str(p)
            if isinstance(r, dict):
                return r.get("text", str(r))
            return str(r)

        if isinstance(results, list):
            answers = [_extract_text(r) for r in results if r is not None]
        else:
            answers = [_extract_text(results)] if results else []
        return {"query": query, "answers": answers, "mode": "local"}
    else:
        import httpx
        headers = {"X-Api-Key": COGNEE_API_KEY, "X-Tenant-Id": COGNEE_TENANT_ID}
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{COGNEE_API_URL}/api/v1/search",
                headers=headers,
                json={"query": query, "search_type": "GRAPH_COMPLETION", "datasets": [dataset]},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        answers = []
        if isinstance(data, list):
            for item in data:
                if not item:
                    continue
                # Cloud returns dicts with search_result list
                if isinstance(item, dict):
                    sr = item.get("search_result") or item.get("text") or item.get("results")
                    if isinstance(sr, list):
                        answers.extend([s for s in sr if s])
                    elif sr:
                        answers.append(str(sr))
                else:
                    answers.append(str(item))
        elif isinstance(data, dict):
            answers = data.get("results", [])
        return {"query": query, "answers": answers, "mode": "cloud"}


# ── improve ───────────────────────────────────────────────────────

async def improve(dataset: str = "default") -> dict:
    if COGNEE_MODE == "local":
        import cognee
        await _ensure_cognee()
        await cognee.improve()
        return {"status": "improved", "mode": "local"}
    else:
        import httpx
        headers = {"X-Api-Key": COGNEE_API_KEY, "X-Tenant-Id": COGNEE_TENANT_ID}
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{COGNEE_API_URL}/api/v1/cognify",
                headers=headers,
                json={"datasets": [dataset]},
                timeout=120,
            )
            r.raise_for_status()
        return {"status": "improved", "mode": "cloud"}


# ── forget ────────────────────────────────────────────────────────

async def forget(dataset: str = "default") -> dict:
    if COGNEE_MODE == "local":
        import cognee
        await _ensure_cognee()
        await cognee.forget(everything=True)
        return {"status": "forgotten", "dataset": dataset, "mode": "local"}
    else:
        import httpx
        headers = {"X-Api-Key": COGNEE_API_KEY, "X-Tenant-Id": COGNEE_TENANT_ID}
        async with httpx.AsyncClient() as client:
            # List all datasets and delete every one (forget = clean slate)
            lr = await client.get(f"{COGNEE_API_URL}/api/v1/datasets", headers=headers, timeout=30)
            if lr.status_code == 200:
                datasets = lr.json() or []
                for ds in datasets:
                    ds_id = ds.get("id")
                    if ds_id:
                        await client.delete(
                            f"{COGNEE_API_URL}/api/v1/datasets/{ds_id}",
                            headers=headers, timeout=30,
                        )
            else:
                # fallback: try deleting by name
                await client.delete(f"{COGNEE_API_URL}/api/v1/datasets/{dataset}",
                                    headers=headers, timeout=30)
        return {"status": "forgotten", "dataset": "all", "mode": "cloud"}


# ── extract_entities ──────────────────────────────────────────────

async def extract_entities(text: str) -> tuple:
    """Use LLM to extract entities and relationships for graph visualization."""
    prompt = f"""Extract entities and relationships from this text for a knowledge graph.

Text: "{text}"

Return ONLY valid JSON, no explanation, no markdown:
{{
  "entities": [
    {{"label": "Short Name", "type": "person|concept|place|event|decision|emotion|goal"}}
  ],
  "relationships": [
    {{"from": "Label1", "to": "Label2", "label": "relation"}}
  ]
}}

Rules:
- entity labels: 1-3 words max, title case
- max 7 entities, max 8 relationships
- from/to must exactly match an entity label above"""

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{LLM_ENDPOINT}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": _bare_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                },
                timeout=20,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            return data.get("entities", []), data.get("relationships", [])
    except Exception:
        return _fallback_extract(text), []


def _fallback_extract(text: str) -> list:
    import re
    words = re.findall(r'\b[A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)?\b', text)
    seen, entities = set(), []
    for w in words[:6]:
        if w not in seen:
            seen.add(w)
            entities.append({"label": w, "type": "concept"})
    return entities
