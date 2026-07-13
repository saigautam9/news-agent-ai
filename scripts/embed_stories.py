"""
Embed every story in the warehouse into a pgvector column so the semantic
memory (RAG) can retrieve related history.

    python scripts/embed_stories.py

Idempotent — only embeds stories that don't have a vector yet. Cheap to re-run
after new stories arrive.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.memory import backfill_embeddings  # noqa: E402

if __name__ == "__main__":
    res = backfill_embeddings()
    print(f"[embed] embedded {res['embedded']} stories "
          f"(pending was {res.get('total_pending_was', 0)}).")
