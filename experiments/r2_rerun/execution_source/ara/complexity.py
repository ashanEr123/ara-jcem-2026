"""Query Complexity Formula (Section 3.2 / Caliberation.pdf) and routing (tau).

    C(Q) = a1*|T(Q)| + a2*Ops(Q) + a3*Depth(Q) + a4*Amb(Q,D) + a5*Dom(Q)   (Eq. 1)

This is the FIVE-feature aggregated model exactly as the calibration document
defines it: x(Q) = (|T|, Ops, Depth, Amb, Dom), and the weights a1..a5 are fit by
regularised logistic regression (calibrate.py). Ops and Dom are computed with
their internal sub-weights (beta, gamma) fixed to 1.0, as in the paper.

Default weights are the paper's (a1..a5 = 1.0, 2.0, 1.5, 1.0, 2.0; tau = 15.92).
If calibration/learned_weights.json exists, its data-driven alpha and tau override
the defaults (the scorer then prints [learned]).
"""
import json
import math
import os
import re
import config
from .preprocess import tokenize, normalize

FEATURES = ["T", "Ops", "Depth", "Amb", "Dom"]

DEFAULT_ALPHA = {"T": 1.0, "Ops": 2.0, "Depth": 1.5, "Amb": 1.0, "Dom": 2.0}
DEFAULT_TAU = 15.92

# Internal sub-weights of Eq. 2 (Ops) and Eq. 4 (Dom), fixed to 1.0 as in the paper.
BETA = {"AND": 1.0, "OR": 1.0, "NOT": 1.0, "JOIN": 1.0}
GAMMA = {"multi": 1.0, "ndom": 1.0}

# ---- Reasoning-depth feature (Depth, Section 3.2.3) ----
# The original surface-conditional counter carried no signal (calibration AUC 0.50:
# complex queries are narrative, not explicitly nested). Depth is reoperationalised
# as a query-only reasoning-depth proxy = scenario segments + reasoning-intent cues
# + distinct contractual actors. See calibrate.py for the ablation that motivates it.
REASONING_CUES = [
    "explain", "assess", "determine", "walk through", "identify", "analyse",
    "analyze", "evaluate", "implication", "consequence", "remed", "step",
    "procedure", "whether", "entitled", "valid", "liable", "obligation",
    "what happens", "how should", "extent", "rights",
]
ACTOR_TERMS = [
    "client", "consultant", "employer", "contractor", "bank", "expert",
    "sub-consultant", "subconsultant", "arbitrator", "engineer", "parties",
    "party", "ministry",
]
JOIN_MARKERS = ["relating to", "with respect to", "in relation to", "as well as",
                "together with", "in accordance with"]
DOMAIN_LEXICON = {
    "technical": ["work", "overnight", "accelerate", "schedule", "design", "site",
                  "construction", "drawing", "specification", "completion", "programme",
                  "services", "report", "expert", "personnel"],
    "legal":     ["contract", "clause", "legal", "law", "obligation", "liable",
                  "arbitration", "dispute", "agreement", "provision", "breach",
                  "consultant", "terminate", "termination", "notice", "force majeure"],
    "economic":  ["payment", "cost", "price", "interest", "advance", "withhold",
                  "rate", "fee", "financial", "penalty", "compensation", "remuneration",
                  "invoice", "tax"],
    "environmental": ["environment", "environmental", "noise", "pollution", "permit",
                      "emission", "waste", "ecological", "flood"],
}


def _load_alpha():
    path = getattr(config, "LEARNED_WEIGHTS_PATH", "")
    if path and os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        a = dict(DEFAULT_ALPHA)
        a.update(data.get("alpha", {}))
        return a, float(data.get("tau", DEFAULT_TAU)), "learned"
    return dict(DEFAULT_ALPHA), DEFAULT_TAU, "default"


def _load_corpus_logp():
    # Ambiguity is bound to the SOURCE-A calibration KB (frozen), not the serving corpus.
    if os.path.exists(config.CALIB_STATS_PATH):
        with open(config.CALIB_STATS_PATH) as f:
            stats = json.load(f)
        return stats.get("neg_log_p", {}), stats.get("default_neg_log_p", 6.0)
    return {}, 6.0


def operator_counts(norm_query):
    q = " " + norm_query + " "
    return {
        "AND": q.count(" and ") + q.count(" and/or "),
        "OR": q.count(" or ") + q.count(" and/or "),
        "NOT": q.count(" not ") + q.count(" no ") + q.count(" without "),
        "JOIN": sum(norm_query.count(m) for m in JOIN_MARKERS),
    }


def ops_value(norm_query):
    c = operator_counts(norm_query)
    return (BETA["AND"] * c["AND"] + BETA["OR"] * c["OR"]
            + BETA["NOT"] * c["NOT"] + BETA["JOIN"] * c["JOIN"])


def reasoning_depth(query):
    """Reasoning-depth proxy (Depth feature), computed from the RAW query only.

    Depth(Q) = scenario_segments + reasoning_cues + distinct_actors
      - scenario_segments: independent clauses/sentences (multi-step scenarios)
      - reasoning_cues: explain / assess / whether / remedies / procedure ...
      - distinct_actors: Client, Consultant, Employer, ... whose interaction the
        query asks to reconcile
    An optional dependency-parse depth is added when spaCy + a model are present
    (see parse_depth); otherwise it contributes 0 and the lightweight proxy stands.
    """
    raw = (query or "").strip()
    ql = raw.lower()
    segments = [s for s in re.split(r"[.;]+\s+|\?+\s*", raw) if s.strip()]
    n_seg = max(1, len(segments))
    n_reason = sum(ql.count(w) for w in REASONING_CUES)
    n_actors = max(1, len({a for a in ACTOR_TERMS if a in ql}))
    return float(n_seg + n_reason + n_actors + parse_depth(raw))


def parse_depth(raw_query):
    """Optional: max dependency-tree depth via spaCy, if installed with a model.

    Returns 0 when spaCy or the model is unavailable, so the lightweight proxy is
    used unchanged. To enable locally: pip install spacy && python -m spacy
    download en_core_web_sm, then set ARA_USE_PARSE_DEPTH=1.
    """
    if os.getenv("ARA_USE_PARSE_DEPTH", "0") != "1":
        return 0
    try:
        nlp = _get_spacy()
        if nlp is None:
            return 0
        doc = nlp(raw_query)

        def tok_depth(tok):
            d = 0
            while tok.head != tok:
                d += 1
                tok = tok.head
            return d
        return max((tok_depth(t) for t in doc), default=0)
    except Exception:
        return 0


_SPACY = None


def _get_spacy():
    global _SPACY
    if _SPACY is None:
        try:
            import spacy
            _SPACY = spacy.load("en_core_web_sm")
        except Exception:
            _SPACY = False
    return _SPACY or None


# Backwards-compatible alias: feature extraction calls depth(query).
def depth(query):
    return reasoning_depth(query)


def idf_ambiguity(content_terms):
    """IDF query ambiguity (Eq. 3): mean -log p(t|D). Faithful to the paper, but
    on this data it does not separate the classes (Cohen's d ~ 0.16)."""
    if not content_terms:
        return 0.0
    neg_log_p, default = _load_corpus_logp()
    return sum(neg_log_p.get(t, default) for t in content_terms) / len(content_terms)


def clarity_ambiguity(query):
    """Semantic ambiguity via retrieval dispersion (query-clarity style).

    Embed the query, retrieve top-k clauses, and measure the normalized entropy of
    their similarity scores. A simple query is dominated by one clause (peaked ->
    low entropy -> low ambiguity); a complex query spreads relevance across many
    clauses (flat -> high entropy). This matches 'complex = reconcile multiple
    clauses'. Needs the vector DB (ingest.py) + embeddings (API); returns None if
    unavailable so the caller falls back to IDF.
    """
    try:
        from . import retriever
        # Amb dispersion is measured against the SOURCE-A calibration index (frozen),
        # so expanding the serving corpus does not change C(Q) or tau.
        chunks = retriever.retrieve(query, top_k=config.AMB_CLARITY_K,
                                    persist_dir=config.CALIB_DB_DIR)
        if not chunks:
            return None
        sims = [max(0.0, 1.0 - c.get("distance", 1.0)) for c in chunks]
        tot = sum(sims)
        if tot <= 0 or len(sims) < 2:
            return None
        ps = [s / tot for s in sims]
        ent = -sum(p * math.log(p + 1e-12) for p in ps)
        return (ent / math.log(len(ps))) * 10.0   # normalized entropy, scaled ~0-10
    except Exception:
        return None


def ambiguity(query, content_terms):
    """Dispatch on config.AMB_MODE: 'clarity' (semantic, recommended) or 'idf'."""
    if getattr(config, "AMB_MODE", "idf") == "clarity":
        val = clarity_ambiguity(query)
        if val is not None:
            return val
    return idf_ambiguity(content_terms)


def domain_set(content_terms):
    hit = set()
    for dom, lex in DOMAIN_LEXICON.items():
        if any(t in lex for t in content_terms):
            hit.add(dom)
    return hit


def domain_features(content_terms):
    n = max(len(domain_set(content_terms)), 1)
    return {"multi": 1 if n > 1 else 0, "ndom": n}


def dom_value(content_terms):
    df = domain_features(content_terms)
    return GAMMA["multi"] * df["multi"] + GAMMA["ndom"] * df["ndom"]


def feature_vector(query: str) -> dict:
    """The five aggregated features x(Q) = (|T|, Ops, Depth, Amb, Dom)."""
    norm = normalize(query)
    _, content = tokenize(query)
    return {
        "T": float(len(content)),
        "Ops": float(ops_value(norm)),
        "Depth": float(depth(query)),
        "Amb": round(ambiguity(query, content), 4),
        "Dom": float(dom_value(content)),
    }


def score(query: str) -> dict:
    alpha, tau, source = _load_alpha()
    fv = feature_vector(query)
    total = sum(alpha[k] * fv[k] for k in FEATURES)
    return {
        "query": query,
        "features": fv,
        "components": fv,
        "weights_source": source,
        "alpha": alpha,
        "complexity_score": round(total, 2),
        "tau": tau,
        "route": "rag_gym" if total > tau else "rag_flow",
        "type": "complex" if total > tau else "simple",
    }


if __name__ == "__main__":
    for q in ["What is the project commencement date?",
              "If the contractor needs to work overnight to accelerate the "
              "project, what are the legal implications as per the contract?"]:
        s = score(q)
        print(f"{s['type']:8s} C(Q)={s['complexity_score']:6.2f} [{s['weights_source']}]  "
              f"{s['features']}  -> {s['route']}")
