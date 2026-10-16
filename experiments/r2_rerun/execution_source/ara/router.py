"""Router (step 2 in Figure 1): score the query, dispatch to the right pipeline.

This is the top-level ARA entry point that the UI and CLI call.
"""
import time
from . import complexity, rag_flow, rag_gym


def ask(query: str, query_id: str = None) -> dict:
    t0 = time.time()
    scored = complexity.score(query)                  # step 2

    if scored["route"] == "rag_gym":
        result = rag_gym.answer(query, query_id=query_id)   # complex path
    else:
        result = rag_flow.answer(query)               # simple path

    elapsed = time.time() - t0
    result.update({
        "complexity_score": scored["complexity_score"],
        "components": scored["components"],
        "tau": scored["tau"],
        "type": scored["type"],
        "response_time_s": round(elapsed, 2),
    })
    return result
