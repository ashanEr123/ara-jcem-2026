"""LLM (3C.1) and embedding (3C.5) wrappers — API-LLM configuration.

Both the generator and the embeddings are OpenAI API calls here. If you later
switch to a fully-local model, this is the only file you need to change:
point the client at an OpenAI-compatible endpoint (Ollama / vLLM) instead.
"""
import json
from openai import OpenAI
import config

_client = OpenAI(api_key=config.OPENAI_API_KEY, max_retries=0, timeout=config.API_TIMEOUT)


def _token_limit_kwargs(model, max_tokens):
    """Newer OpenAI models use max_completion_tokens instead of max_tokens."""
    if model.startswith("gpt-5") or model.startswith("o"):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


def _chat_kwargs(model, temperature, max_tokens):
    kw = _token_limit_kwargs(model, max_tokens)
    if not (model.startswith("gpt-5") or model.startswith("o")):
        kw["temperature"] = temperature
    return kw


def complete(messages, temperature=0.2, max_tokens=1024):
    """Single chat completion with GPT-5-Mini (3C.1)."""
    resp = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        **_chat_kwargs(config.LLM_MODEL, temperature, max_tokens),
    )
    return resp.choices[0].message.content


def complete_json(messages, temperature=0.2, max_tokens=1024):
    """Chat completion that must return a JSON object. Robust to code fences."""
    resp = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        **_chat_kwargs(config.LLM_MODEL, temperature, max_tokens),
    )
    text = resp.choices[0].message.content.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def embed(texts):
    """Embed a list of strings via the OpenAI embedding model (3C.5)."""
    if isinstance(texts, str):
        texts = [texts]
    resp = _client.embeddings.create(model=config.EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


# ---- General-purpose baselines for evaluation (no retrieval, Section 4.1) ----
_BASELINE_SYS = ("You are answering a construction-contract question. Answer as "
                 "accurately and completely as you can.")


def gpt_baseline(query, temperature=0.2, max_tokens=1024):
    """GPT-5.2 general-purpose baseline (no retrieval, no reasoning gates)."""
    resp = _client.chat.completions.create(
        model=config.BASELINE_GPT_MODEL,
        messages=[{"role": "system", "content": _BASELINE_SYS},
                  {"role": "user", "content": query}],
        **_chat_kwargs(config.BASELINE_GPT_MODEL, temperature, max_tokens))
    return resp.choices[0].message.content


def mistral_baseline(query, temperature=0.2, max_tokens=1024):
    """Mistral general-purpose baseline (no retrieval)."""
    try:
        from mistralai import Mistral
    except ImportError:
        from mistralai.client.sdk import Mistral
    client = Mistral(api_key=config.MISTRAL_API_KEY)
    resp = client.chat.complete(
        model=config.MISTRAL_CHAT_MODEL,
        messages=[{"role": "system", "content": _BASELINE_SYS},
                  {"role": "user", "content": query}],
        temperature=temperature, max_tokens=max_tokens)
    return resp.choices[0].message.content


def note_fallback(kind):
    """Replaced by the run recorder during evaluation."""
    pass
