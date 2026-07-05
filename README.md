# 🧠 MindVault — AI That Never Forgets You

> Built for the **WeMakeDevs × Cognee Hackathon** · Jun 29 – Jul 5, 2026

MindVault is your **living memory** — talk to it, and it builds a knowledge graph of your life in real time. Powered by [Cognee](https://github.com/topoteretes/cognee)'s hybrid graph-vector memory layer, it remembers everything you tell it and recalls it across infinite sessions, forever.

Standard AI has goldfish memory — every chat starts from zero. MindVault has elephant memory: it remembers, connects, and gets smarter with every interaction.

---

## ✨ Features

| Operation | What it does |
|-----------|-------------|
| 💾 **Remember** | Ingest text into a permanent hybrid graph-vector memory |
| 🔍 **Recall** | Ask questions — answered by hybrid semantic + graph traversal search |
| ✨ **Improve** | Re-run cognify to enrich and strengthen the knowledge graph |
| 🗑️ **Forget** | Erase memory — GDPR-ready, full data lifecycle |

**Uses all 4 Cognee memory APIs** — the complete memory lifecycle.

Plus:
- 🕸️ **Live knowledge graph** — force-directed Canvas visualization that grows as you type (zero dependencies, pure JS)
- 🎙️ **Voice input** — speak your memories (Web Speech API)
- 🔄 **Live dual-mode toggle** — click LOCAL ↔ CLOUD in the header to switch between open-source Cognee and Cognee Cloud, no restart
- 📁 **Multi-dataset** — organize memory into `default`, `work`, `personal`, `research` namespaces
- 💸 **Runs 100% FREE** — Groq free tier LLM + local fastembed embeddings + open-source Cognee
- 🌑 **Beautiful dark UI** — chat interface, live session stats, node-type legend

---

## 🚀 Quick Start

### 1. Clone & install
```bash
git clone https://github.com/jaybamroliya/mindvault
cd mindvault
pip install -r requirements.txt
```

### 2. Configure (free — no credit card anywhere)
```bash
cp .env.example .env
# 1. Get a free Groq key at https://console.groq.com
# 2. Paste it as LLM_API_KEY and GROQ_API_KEY in .env
```

### 3. Run
```bash
python -m uvicorn main:app --port 8000
# Open http://localhost:8000
```

That's it — local mode needs **zero paid services**: Groq free tier for the LLM, fastembed for local embeddings, open-source Cognee for memory.

---

## 🏗️ Architecture

```
             User (Browser)
     chat · voice · live graph · toggle
                   │
                   ▼
        FastAPI Backend (main.py)
   /remember /recall /improve /forget /mode
                   │
                   ▼
      Memory Engine (memory_engine.py)
       one interface, two backends
              ┌────┴────┐
              │         │
        Local Cognee   Cognee Cloud
        (open source)  (managed API)
        Groq + fastembed  multipart /add
        rate-limited      /cognify /search
```

`memory_engine.py` abstracts both modes behind four async functions:

| Function | Local (OSS) | Cloud |
|----------|------------|-------|
| `remember(text, dataset)` | `cognee.remember()` | `POST /api/v1/add` (multipart) + `/cognify` |
| `recall(query, dataset)` | `cognee.recall()` | `POST /api/v1/search` (GRAPH_COMPLETION) |
| `improve(dataset)` | `cognee.improve()` | `POST /api/v1/cognify` |
| `forget(dataset)` | `cognee.forget(everything=True)` | `DELETE /api/v1/datasets/{id}` |

The live knowledge graph is built by a parallel LLM entity-extraction pass — every memory is mined for entities and relationships, rendered with a custom force-directed physics engine on Canvas.

---

## 💸 The Free-Tier Stack

Making this run at zero cost was the hardest engineering problem:

| Problem | Solution |
|---------|----------|
| LLM costs money | Groq free tier (`llama-3.3-70b-versatile`, 6000 TPM) |
| Embeddings cost money | `fastembed` — runs locally, no API key (BAAI/bge-small-en-v1.5) |
| Groq 6000 TPM limit vs Cognee's concurrent pipeline | Cognee's built-in rate limiter: 1 req/15s via `aiolimiter` |
| Vector dim mismatch (OpenAI 3072 vs fastembed 384) | Clean LanceDB rebuild with matching schema |

---

## 🎯 Why Cognee?

- **Vector search** for semantic similarity
- **Graph traversal** for relational context — *who* relates to *what*
- **Persistent** across sessions and restarts
- **Self-hosted** (open source) or **managed** (Cognee Cloud) — MindVault supports both, switchable live

---

## 📁 Project Structure

```
mindvault/
├── main.py            # FastAPI app + API routes
├── memory_engine.py   # Cognee abstraction (local + cloud)
├── static/
│   └── index.html     # Full web UI: chat, graph, voice, toggle
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🏆 Hackathon Tracks

This project is submitted to:
- **Best Use of Open Source Cognee** — LOCAL mode (default, 100% free stack)
- **Best Use of Cognee Cloud** — CLOUD mode (live toggle in the UI)

---

## 👤 Author

**Jay Bamroliya** · [github.com/jaybamroliya](https://github.com/jaybamroliya)

Built with ❤️ using Cognee, FastAPI, and Python.
