"""
Semantic memory (RAG) for NewsAgent AI.

Every story is embedded into a 768-d vector (Gemini `gemini-embedding-001`) and
stored in Postgres via **pgvector**. That lets the assistant retrieve related
news from the *entire history* — not just today's fetch — and surface
**precedents** ("this echoes N past stories"), which is the retrieval half of
retrieval-augmented generation and the basis for precedent-based outlooks.

    python scripts/embed_stories.py     # backfill embeddings for all stories
"""

from __future__ import annotations

from app import config
from app.analytics import _connect

EMBED_MODEL = "gemini-embedding-001"
DIM = 768


def _embed(texts: list[str], task: str) -> list[list[float]]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=DIM, task_type=task),
    )
    return [list(e.values) for e in resp.embeddings]


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def ensure_schema() -> bool:
    con = _connect()
    if con is None:
        return False
    with con:
        con.execute("CREATE EXTENSION IF NOT EXISTS vector")
        con.execute(f"ALTER TABLE stories ADD COLUMN IF NOT EXISTS embedding vector({DIM})")
    con.close()
    return True


def backfill_embeddings(batch: int = 64) -> dict:
    """Embed every story that doesn't have a vector yet (idempotent)."""
    if not ensure_schema():
        return {"embedded": 0, "store": "none"}
    con = _connect()
    with con:
        rows = con.execute(
            "SELECT fp, headline, summary FROM stories WHERE embedding IS NULL"
        ).fetchall()
    con.close()

    done = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        texts = [f"{h}. {s or ''}"[:2000] for _, h, s in chunk]
        vecs = _embed(texts, "RETRIEVAL_DOCUMENT")  # slow — hold no DB connection here
        con = _connect()  # fresh, short-lived connection just for the write
        with con:
            cur = con.cursor()
            for (fp, _, _), v in zip(chunk, vecs):
                cur.execute("UPDATE stories SET embedding = %s::vector WHERE fp = %s", (_vec(v), fp))
        con.close()
        done += len(chunk)
    return {"embedded": done, "total_pending_was": len(rows)}


def search(query: str, k: int = 6) -> list[dict]:
    """Semantic search over the whole news history (cosine similarity)."""
    if not config.DATABASE_URL:
        return []
    qv = _vec(_embed([query], "RETRIEVAL_QUERY")[0])  # embed first, no DB held
    con = _connect()
    if con is None:
        return []
    with con:
        rows = con.execute(
            "SELECT headline, domain, severity, date, "
            "1 - (embedding <=> %s::vector) AS sim "
            "FROM stories WHERE embedding IS NOT NULL "
            "ORDER BY embedding <=> %s::vector LIMIT %s",
            (qv, qv, k),
        ).fetchall()
    con.close()
    return [
        {"headline": h, "domain": d, "severity": s,
         "date": str(dt) if dt else None, "similarity": round(float(sim), 3)}
        for h, d, s, dt, sim in rows
    ]


def recall(query: str, k: int = 6) -> dict:
    """RAG answer: retrieve related history + an evidence-grounded analyst note
    on the pattern (precedent-based, honest — it only interprets what it found)."""
    hits = search(query, k)
    if not hits:
        return {"query": query, "matches": [], "note": "No related history found yet."}

    from app.gemini import extract_json
    from app.groq_client import run_groq

    evidence = "; ".join(
        f"[{m['date']}] {m['domain']}/{m['severity']}: {m['headline']}" for m in hits
    )
    system = (
        "You are a news research analyst. You are given past stories retrieved as "
        "the closest matches to a query. In 3-4 sentences, summarize the recurring "
        "pattern and — grounded ONLY in these precedents — what has typically "
        "followed. Never invent events or predict specifics; cite the pattern, not "
        'certainty. Respond as JSON: {"note": "..."}.'
    )
    prompt = f"Query: {query}\nRetrieved precedents: {evidence}\nReturn JSON with key 'note'."
    try:
        parsed = extract_json(run_groq(system, prompt))
        note = str(parsed.get("note")) if isinstance(parsed, dict) else ""
    except Exception:  # noqa: BLE001
        note = ""
    return {"query": query, "matches": hits, "note": note or "Related precedents retrieved."}
