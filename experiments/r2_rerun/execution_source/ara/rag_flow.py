"""RAG-Flow pipeline (Section 3.3 / red dashed path in Figure 1).

Lightweight, single-pass retrieval+generation for simple queries:
    augmenter (3A.1) -> shared retriever (3C.2) -> GPT-5-Mini (3C.1) -> answer.
No reasoning loops. "RAG-Flow provides a straightforward answer within a minimum
time period."
"""
from . import llm, retriever

SYSTEM = (
    "You are a construction-contract interpretation assistant. Answer the user's "
    "question using ONLY the retrieved contract context. Be direct and concise. "
    "Cite clause numbers when present. If the context does not contain the answer, "
    "say so plainly."
)


def answer(query: str):
    chunks = retriever.retrieve(query)
    context = retriever.format_context(chunks)
    # Augmenter (3A.1): fuse query + retrieved context into the prompt.
    user = f"Contract context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    text = llm.complete(
        [{"role": "system", "content": SYSTEM},
         {"role": "user", "content": user}],
        temperature=0.1,
    )
    return {
        "answer": text,
        "route": "simple_ragflow",
        "n_retrievals": 1,
        "sources": [c.get("metadata", {}) for c in chunks],
    }
