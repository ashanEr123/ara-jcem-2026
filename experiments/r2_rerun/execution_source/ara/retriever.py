"""Shared retriever (3C.2): both pipelines query the same vector DB."""
import config
from . import llm
from .vectorstore import get_collection


def retrieve(query: str, top_k: int = None, persist_dir: str = None):
    """Return the top-k most relevant chunks. persist_dir selects the index
    (serving DB_DIR by default; CALIB_DB_DIR for the complexity scorer's Amb)."""
    top_k = top_k or config.TOP_K
    col = get_collection(persist_dir)
    if col.count() == 0:
        return []
    q_emb = llm.embed(query)[0]
    res = col.query(query_embeddings=[q_emb], n_results=min(top_k, col.count()))
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    out = []
    for d, m, dist in zip(docs, metas, dists):
        out.append({"text": d, "metadata": m, "distance": dist})
    return out


def format_context(chunks):
    """Render retrieved chunks into a context block for the LLM prompt."""
    blocks = []
    for i, c in enumerate(chunks, 1):
        src = c.get("metadata", {}).get("source", "contract")
        blocks.append(f"[{i}] (source: {src})\n{c['text']}")
    return "\n\n".join(blocks)
