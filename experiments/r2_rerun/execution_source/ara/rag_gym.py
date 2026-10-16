"""RAG-Gym pipeline (Section 3.3 / blue dashed path in Figure 1).

Agentic, multi-step reasoning for complex queries, built on a nested MDP
(Xiong et al., 2025). One reasoning cycle:

  3B.1 state (question | retrieval history)
  3B.2 GPT-5-Mini proposes candidate actions  (Action 1 | Action 2 | Action 3)
  3B.3 process reward model scores them and selects the best action
  3B.4/3B.5 information retrieval environment executes it:
        - type == "query"  -> retrieve, append to history, loop
        - type == "answer" -> terminate, return final answer

The process reward model here is an LLM-as-judge (the paper notes "advanced LLMs
as process reward judges" are effective). Swap in the trained RAG-Gym PRM from
Xiong et al. (2025) if you want to match that variant exactly.
"""
import json
import config
from . import llm, retriever
from rerun_support import ProviderHalt

ACTOR_SYSTEM = (
    "You are an agentic search policy for construction-contract interpretation. "
    "Given the question and the retrieval history, propose candidate next actions. "
    "Each action is either:\n"
    '  {"type":"query","content":"<a focused search query for missing info>"}\n'
    '  {"type":"answer","content":"<a complete, clause-grounded final answer>"}\n'
    "Propose an 'answer' action only when the history already contains enough "
    "evidence. Return JSON: {\"actions\":[...]}"
)

PRM_SYSTEM = (
    "You are a process reward model. Score each candidate action 0-10 for how much "
    "it advances a correct, complete, clause-grounded answer without redundancy. "
    "Penalise actions that repeat earlier searches or answer prematurely. "
    "Return JSON: {\"scores\":[<float per action in order>]}"
)

FINAL_SYSTEM = (
    "You are a construction-contract interpretation assistant. Using the retrieval "
    "history, write a complete, clause-grounded answer with multi-step reasoning. "
    "Cite clause numbers; flag where the Special Conditions of Contract should be "
    "verified. Use ONLY the retrieved evidence."
)


def _history_text(history):
    if not history:
        return "(empty)"
    out = []
    for i, h in enumerate(history, 1):
        out.append(f"Step {i}: searched \"{h['query']}\"\nRetrieved:\n"
                   + retriever.format_context(h["chunks"]))
    return "\n\n".join(out)


def _prior_searches(history):
    return {h.get("query", "").strip().lower() for h in (history or [])}


def _default_actions(query, history):
    """Deterministic multi-candidate set when the actor LLM fails."""
    actions = [
        {"type": "query", "content": f"Contract clause text and sub-clauses for: {query}"},
        {"type": "query", "content": f"Notice periods, payment, and remedies related to: {query}"},
    ]
    if history:
        actions.append({
            "type": "answer",
            "content": "Provide the final clause-grounded answer from the retrieval history.",
        })
    return actions[: config.GYM_NUM_CANDIDATES]


def _ensure_candidates(query, history, actions):
    """Drop duplicate / already-searched queries; pad to ≥2 candidates for PRM."""
    prior = _prior_searches(history)
    seen = set()
    cleaned = []
    for a in actions:
        text = (a.get("content") or "").strip()
        if not text:
            continue
        key = (a.get("type"), text.lower())
        if key in seen:
            continue
        if a.get("type") == "query" and text.lower() in prior:
            continue
        seen.add(key)
        cleaned.append({"type": a.get("type", "query"), "content": text})

    if history and not any(a.get("type") == "answer" for a in cleaned):
        cleaned.append({
            "type": "answer",
            "content": "Draft the final clause-grounded answer using the retrieval history.",
        })

    for filler in _default_actions(query, history):
        if len(cleaned) >= config.GYM_NUM_CANDIDATES:
            break
        key = (filler.get("type"), filler.get("content", "").lower())
        if key not in seen:
            cleaned.append(filler)
            seen.add(key)

    if len(cleaned) < 2:
        for filler in _default_actions(query, history):
            key = (filler.get("type"), filler.get("content", "").lower())
            if key not in seen:
                cleaned.append(filler)
                seen.add(key)
            if len(cleaned) >= 2:
                break

    return cleaned[: config.GYM_NUM_CANDIDATES]


def _propose_actions(query, history):
    user = (f"Question: {query}\n\nRetrieval history:\n{_history_text(history)}\n\n"
            f"Propose {config.GYM_NUM_CANDIDATES} candidate actions.")
    try:
        data = llm.complete_json(
            [{"role": "system", "content": ACTOR_SYSTEM},
             {"role": "user", "content": user}], temperature=0.5)
        actions = data.get("actions", [])
    except ProviderHalt:
        raise
    except Exception:
        actions = []
    if not actions:
        llm.note_fallback("actor_default_actions")
        actions = _default_actions(query, history)
    return _ensure_candidates(query, history, actions)


def _score_actions(query, history, actions):
    listing = "\n".join(f"{i}. [{a.get('type')}] {a.get('content','')}"
                        for i, a in enumerate(actions))
    user = (f"Question: {query}\n\nHistory:\n{_history_text(history)}\n\n"
            f"Candidate actions:\n{listing}")
    fallback_used = False
    try:
        data = llm.complete_json(
            [{"role": "system", "content": PRM_SYSTEM},
             {"role": "user", "content": user}], temperature=0.0)
        scores = data.get("scores", [])
        scores = [float(s) for s in scores]
    except ProviderHalt:
        raise
    except Exception:
        scores = []
    if len(scores) != len(actions):
        fallback_used = True
        llm.note_fallback("prm_default_scores")
        scores = [(1.0 if a.get("type") == "query" else 0.5) for a in actions]
    prm_pick = scores.index(max(scores)) if scores else 0
    try:
        from experiments.prm_agreement import prm_log
        prm_log.log_decision(
            history=history, actions=actions, scores=scores,
            prm_pick=prm_pick, fallback_used=fallback_used,
            system_prompt=PRM_SYSTEM, user_prompt=user,
        )
    except Exception:
        pass
    return scores


def answer(query: str, query_id: str = None):
    if query_id:
        try:
            from experiments.prm_agreement import prm_log
            prm_log.set_query_context(query_id, query)
        except Exception:
            pass
    history = []
    n_retrievals = 0
    trace = []

    for step in range(config.GYM_MAX_STEPS):
        if query_id:
            try:
                from experiments.prm_agreement import prm_log
                prm_log.next_step()
            except Exception:
                pass
        actions = _propose_actions(query, history)            # 3B.2
        scores = _score_actions(query, history, actions)       # 3B.3 (PRM)
        best = actions[scores.index(max(scores))]              # select excellent action
        trace.append({"step": step, "chosen": best, "scores": scores})

        if best.get("type") == "answer" and history:           # 3B.5 terminate
            break
        # 3B.4 action type == "query": query the environment
        search_q = best.get("content") or query
        chunks = retriever.retrieve(search_q)
        n_retrievals += 1
        history.append({"query": search_q, "chunks": chunks})  # update state -> 3B.1

    # Synthesise the final answer from accumulated state.
    final = llm.complete(
        [{"role": "system", "content": FINAL_SYSTEM},
         {"role": "user", "content": f"Question: {query}\n\n"
                                     f"Retrieval history:\n{_history_text(history)}\n\n"
                                     f"Final answer:"}],
        temperature=0.2, max_tokens=4000)

    sources = [m for h in history for m in
               [c.get("metadata", {}) for c in h["chunks"]]]
    return {
        "answer": final,
        "route": "multi_step_raggym",
        "n_retrievals": n_retrievals,
        "trace": trace,
        "sources": sources,
    }
