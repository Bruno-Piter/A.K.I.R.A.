"""Embedding helpers. Talk to OpenAI or Ollama via settings; lazy on call."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

_OPENAI_SMALL = "text-embedding-3-small"
_NOMIC = "nomic-embed-text"


def embedding_dimensions() -> int:
    """Vector size for the configured embedding model."""
    from app.core.settings import settings

    provider = (settings.embeddings_provider or "openai").strip().lower()
    if provider == "ollama":
        model = (settings.ollama_embedding_model or "").lower()
        if _NOMIC in model or "nomic" in model:
            return 768
        return 768
    model = (settings.embedding_model or "").lower()
    if "3-large" in model:
        return 3072
    if _OPENAI_SMALL in model or "ada-002" in model or "3-small" in model:
        return 1536
    return 1536


def embed_query(text: str) -> list[float]:
    vectors = embed_texts([text])
    if not vectors:
        raise RuntimeError("embed_query produced no vector")
    return vectors[0]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using the configured provider.

    Importing this module does not require credentials. Missing keys only
    raise when an embed is actually requested.
    """
    if not texts:
        return []
    from app.core.settings import settings

    provider = (settings.embeddings_provider or "openai").strip().lower()
    if provider == "ollama":
        return [_embed_ollama(t, settings) for t in texts]
    return _embed_openai(texts, settings)


def _embed_openai(texts: list[str], settings: object) -> list[list[float]]:
    api_key = getattr(settings, "openai_api_key", "") or ""
    if not api_key:
        raise RuntimeError(
            "OpenAI API key is missing; set OPENAI_API_KEY or monkeypatch embed_texts."
        )
    from langchain_openai import OpenAIEmbeddings

    kwargs: dict = {
        "model": getattr(settings, "embedding_model", _OPENAI_SMALL),
        "api_key": api_key,
    }
    base_url = getattr(settings, "openai_base_url", "") or ""
    if base_url:
        kwargs["base_url"] = base_url
    try:
        client = OpenAIEmbeddings(**kwargs)
    except TypeError:
        kwargs.pop("base_url", None)
        if base_url:
            kwargs["openai_api_base"] = base_url
        kwargs.pop("api_key", None)
        kwargs["openai_api_key"] = api_key
        client = OpenAIEmbeddings(**kwargs)
    return [list(map(float, vec)) for vec in client.embed_documents(list(texts))]


def _embed_ollama(text: str, settings: object) -> list[float]:
    base = str(getattr(settings, "ollama_base_url", "http://localhost:11434")).rstrip("/")
    model = getattr(settings, "ollama_embedding_model", _NOMIC)
    url_embeddings = f"{base}/api/embeddings"
    payload = {"model": model, "prompt": text}
    try:
        body = _http_json(url_embeddings, payload)
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
        body = _http_json(
            f"{base}/api/embed",
            {"model": model, "input": text, "prompt": text},
        )
    if "embedding" in body and isinstance(body["embedding"], list):
        return [float(x) for x in body["embedding"]]
    embeddings = body.get("embeddings")
    if isinstance(embeddings, list) and embeddings:
        first = embeddings[0]
        if isinstance(first, list):
            return [float(x) for x in first]
        return [float(x) for x in embeddings]
    raise RuntimeError(f"Unexpected Ollama embeddings payload: {body!r}")


def _http_json(url: str, payload: dict, timeout: float = 60.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to reach {url}: {exc}") from exc
    return json.loads(raw) if raw else {}
