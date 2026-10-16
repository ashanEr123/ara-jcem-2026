"""Query preprocessing (step 1 in Figure 1): normalization + tokenisation.

Section 3.3: 'Text normalisation standardises the input query by resolving
superficial variations such as capitalisation, punctuation, and formatting...
Tokenisation then decomposes the normalised query into semantically meaningful
units.'
"""
import re

# Common English stopwords + contract-query function words. Distinct content
# terms are what feed |T(Q)| (Section 3.2.1).
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "as", "at", "by", "with", "from", "into",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "do", "does", "did", "can", "could", "may", "might", "shall", "should",
    "will", "would", "has", "have", "had", "that", "this", "these", "those",
    "it", "its", "any", "per", "there",
}


def normalize(query: str) -> str:
    """Lowercase, collapse whitespace, strip stray punctuation (keep '/')."""
    q = query.lower().strip()
    q = re.sub(r"[^\w\s/]", " ", q)   # keep '/' for 'and/or'
    q = re.sub(r"\s+", " ", q)
    return q.strip()


def tokenize(query: str):
    """Return (all_tokens, content_terms). content_terms are distinct, non-stopword."""
    norm = normalize(query)
    tokens = norm.split()
    content = []
    seen = set()
    for t in tokens:
        if t in STOPWORDS or len(t) <= 1:
            continue
        if t not in seen:
            seen.add(t)
            content.append(t)
    return tokens, content
