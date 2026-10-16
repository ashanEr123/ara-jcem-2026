"""Vector database (3C.3), indexer (3C.4) and embedding bridge (3C.5).

Local persistent Chroma store. `persist_dir` selects which index:
  - config.DB_DIR        : serving KB (full corpus) used to ANSWER queries
  - config.CALIB_DB_DIR  : Source-A calibration KB used by the complexity scorer
Embeddings come from the OpenAI embedding model via ara.llm.embed (3C.5).
"""
import chromadb
import config
from . import llm


def get_collection(persist_dir=None):
    client = chromadb.PersistentClient(path=persist_dir or config.DB_DIR)
    return client.get_or_create_collection(
        name=config.COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def index_chunks(chunks, persist_dir=None):
    """Indexer (3C.4): embed chunks and store with metadata in the chosen index."""
    col = get_collection(persist_dir)
    BATCH = 64
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        embeddings = llm.embed([c["text"] for c in batch])
        col.add(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            embeddings=embeddings,
            metadatas=[c.get("metadata", {}) for c in batch],
        )
    return col.count()
