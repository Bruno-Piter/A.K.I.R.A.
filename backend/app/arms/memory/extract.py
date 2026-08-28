"""LLM-backed knowledge-graph extraction. Strict JSON only."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel, Field, ValidationError

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_WS = re.compile(r"\s+")
_WRAP_PUNCT = re.compile(r'^[\s\'"`“”‘’\[\](){}<>,;:!?/\\|~_-]+|[\s\'"`“”‘’\[\](){}<>,;:!?/\\|~_-]+$')

# Articles, prepositions, pronouns, and other non-entity tokens (EN + PT).
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "and",
        "or",
        "but",
        "nor",
        "as",
        "by",
        "from",
        "with",
        "without",
        "into",
        "onto",
        "upon",
        "over",
        "under",
        "about",
        "after",
        "before",
        "between",
        "through",
        "during",
        "including",
        "against",
        "among",
        "via",
        "vs",
        "per",
        "than",
        "then",
        "so",
        "if",
        "not",
        "no",
        "yes",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "them",
        "his",
        "her",
        "their",
        "our",
        "my",
        "your",
        "me",
        "him",
        "us",
        "who",
        "whom",
        "which",
        "what",
        "when",
        "where",
        "why",
        "how",
        "also",
        "just",
        "only",
        "very",
        "more",
        "most",
        "some",
        "any",
        "all",
        "each",
        "every",
        "other",
        "such",
        "same",
        "both",
        "few",
        "many",
        "much",
        "can",
        "could",
        "should",
        "would",
        "will",
        "may",
        "might",
        "must",
        "o",
        "os",
        "as",
        "um",
        "uma",
        "uns",
        "umas",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "por",
        "para",
        "com",
        "sem",
        "que",
        "se",
        "ao",
        "à",
        "aos",
        "às",
        "pelo",
        "pela",
        "pelos",
        "pelas",
        "num",
        "numa",
        "ele",
        "ela",
        "eles",
        "elas",
        "isso",
        "isto",
        "aquele",
        "aquela",
        "este",
        "esta",
        "seu",
        "sua",
        "seus",
        "suas",
        "meu",
        "minha",
        "teu",
        "tua",
        "nosso",
        "nossa",
        "deles",
        "delas",
        "lhe",
        "lhes",
        "não",
        "nao",
        "sim",
        "mais",
        "menos",
        "já",
        "ja",
        "também",
        "tambem",
        "como",
        "quando",
        "onde",
        "qual",
        "quais",
        "porque",
        "porquê",
    }
)


# Discourse adverbs / leftover tokens a tiny LLM often emits as "entities".
_DISCOURSE = frozenset(
    {
        "otherwise",
        "however",
        "therefore",
        "thus",
        "hence",
        "namely",
        "instead",
        "anyway",
        "perhaps",
        "maybe",
        "probably",
        "actually",
        "basically",
        "literally",
        "example",
        "examples",
        "given",
        "using",
        "used",
        "based",
        "related",
        "containing",
        "including",
        "etc",
        "via",
        "versus",
    }
)

# Schema / prompt-leak tokens (llama often copies the extraction schema).
_PROMPT_JUNK = frozenset(
    {
        "schema",
        "vocab",
        "vocabulary",
        "json",
        "prompt",
        "token",
        "tokens",
        "field",
        "fields",
        "format",
        "object",
        "response",
        "request",
        "entity",
        "entities",
        "relation",
        "relations",
        "output",
        "input",
        "string",
        "number",
        "boolean",
        "content",
        "role",
        "system",
        "assistant",
        "temperature",
        "strength",
        "description",
        "source",
        "target",
        "type",
        "types",
        "name",
        "names",
        "text",
        "strict",
        "return",
        "returns",
    }
)

# Leading crumbs from a chopped word: "ed with Python", "ing Neo4j".
_SUFFIX_CRUMBS = frozenset(
    {
        "ed",
        "ing",
        "ted",
        "ion",
        "sion",
        "tion",
        "ness",
        "ful",
        "less",
        "able",
        "ible",
        "ous",
        "ive",
        "ly",
        "er",
        "est",
    }
)

_INTRA_NAME_PREP = frozenset(
    {"of", "the", "and", "de", "da", "do", "dos", "das", "van", "von", "del", "di", "la", "le"}
)


# Graph labels / rel types / retriever modes leaked from our own prompt/schema.
_SCHEMA_LABELS = frozenset(
    {
        "document",
        "chunk",
        "entity",
        "conversationsession",
        "message",
        "haschunk",
        "containsentity",
        "relatedto",
        "hasmessage",
        "person",
        "organization",
        "concept",
        "place",
        "technology",
        "hybridsearch",
        "chunksearch",
        "entitysearch",
        "multihop",
        "neighborhood",
        "vectorsearch",
        "fulltext",
        "graphpayload",
        "graphnode",
        "graphlink",
        "extractedentity",
        "extractedrelation",
        "graphextraction",
        "retriever",
    }
)
_SCHEMA_REL_TYPES = frozenset(
    {
        "haschunk",
        "containsentity",
        "relatedto",
        "hasmessage",
        "hybridsearch",
    }
)

_FRAGMENT_CAMEL = re.compile(r"^[a-z]{4,}[A-Z]")
_HAS_UPPER = re.compile(r"[A-Z]")

_PROMPT = """You extract a knowledge graph from the given text.
Return STRICT JSON only. No markdown, no commentary, no code fences.
Schema:
{{
  "entities": [{{"name": string, "type": string, "description": string}}],
  "relations": [{{"source": string, "target": string, "type": string, "strength": number}}]
}}
Entity types must be one of: Person, Organization, Concept, Place, Technology.
"source" and "target" must match entity names exactly.
"strength" is a float between 0 and 1.
Prefer salient named entities (proper names, technologies, concepts).
NEVER emit stopwords, articles, prepositions, pronouns, discourse words, or names shorter than 3 characters.
NEVER emit word fragments (e.g. rsationSession), broken phrases (e.g. ed with Python),
sentence snippets, or prompt/schema leakage (e.g. schema-vocab, otherwise).
Each entity name must be a complete proper name, technology, or concept in Title Case or canonical form.

TEXT:
{text}
"""


class ExtractedEntity(BaseModel):
    name: str
    type: str = "Concept"
    description: str = ""


class ExtractedRelation(BaseModel):
    source: str
    target: str
    type: str = "RELATED_TO"
    strength: float = 1.0


class GraphExtraction(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)


def extract_graph(text: str) -> dict[str, Any]:
    """Call the configured LLM and return a validated, sanitized graph dict.

    Raises a clear error if credentials are missing. Tests monkeypatch this
    or the provider call helpers.
    """
    raw = (text or "").strip()
    if not raw:
        return GraphExtraction().model_dump()

    from app.core.settings import settings

    provider = (settings.llm_provider or "openai").strip().lower()
    prompt = _PROMPT.format(text=raw)
    if provider == "ollama":
        payload = _call_ollama(prompt, settings)
    else:
        payload = _call_openai(prompt, settings)
    parsed = _parse_and_validate(payload)
    if parsed is not None:
        return sanitize_extraction(parsed).model_dump()
    repaired = _strip_fences(payload)
    parsed = _parse_and_validate(repaired)
    if parsed is not None:
        return sanitize_extraction(parsed).model_dump()
    raise RuntimeError(f"LLM did not return valid graph JSON: {payload[:500]!r}")


def normalize_entity_name(name: str) -> str:
    """Trim wrapping punctuation/quotes and collapse internal whitespace."""
    text = str(name or "")
    text = _WRAP_PUNCT.sub("", text)
    text = _WS.sub(" ", text).strip()
    text = _WRAP_PUNCT.sub("", text).strip()
    return text




def _label_key(value: str) -> str:
    """Lowercase alnum-only key so HAS_CHUNK == haschunk == HasChunk."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def is_noise_entity(name: str) -> bool:
    """True for stopwords, fragments, sentence snippets, or prompt leakage."""
    normalized = normalize_entity_name(name)
    if not normalized:
        return True
    compact = re.sub(r"[^A-Za-z0-9À-ÿ]+", "", normalized)
    if not compact or len(compact) <= 2:
        return True
    lowered = normalized.lower()
    if lowered in _STOPWORDS or lowered in _DISCOURSE or lowered in _PROMPT_JUNK:
        return True
    if _label_key(normalized) in _SCHEMA_LABELS:
        return True
    tokens = [tok for tok in re.split(r"[^A-Za-z0-9À-ÿ]+", normalized) if tok]
    if not tokens:
        return True
    # Dotted acronyms like A.K.I.R.A. survive when the compacted form is long enough.
    if len(tokens) > 1 and all(len(tok) == 1 for tok in tokens):
        return False
    token_low = [tok.lower() for tok in tokens]
    if all(tok in _STOPWORDS or tok in _DISCOURSE or len(tok) <= 2 for tok in token_low):
        return True
    # camelCase fragment chopped mid-word: "rsationSession"
    if any(_FRAGMENT_CAMEL.match(tok) for tok in tokens):
        return True
    first = token_low[0]
    if first in _SUFFIX_CRUMBS:
        return True
    # Hyphenated prompt leakage: "schema-vocab"
    if "-" in normalized and all(ch.islower() or not ch.isalpha() for ch in normalized):
        if any(tok in _PROMPT_JUNK or tok in _DISCOURSE or tok in _STOPWORDS for tok in token_low):
            return True
    if any(tok in _PROMPT_JUNK for tok in token_low) and not _HAS_UPPER.search(normalized):
        return True
    # Sentence snippet ("ed with Python") vs Title Case names. Hyphenated
    # tech tokens (scikit-learn) are a single word and skip this check.
    words = normalized.split()
    if len(words) >= 2:
        word_tokens = [tok for w in words for tok in re.split(r"[^A-Za-z0-9À-ÿ]+", w) if tok]
        if not _is_title_case_name(word_tokens):
            return True
    return False


def _is_title_case_name(tokens: list[str]) -> bool:
    """Proper names: content words capitalized; short prepositions may be lower."""
    if not tokens:
        return False
    for i, tok in enumerate(tokens):
        low = tok.lower()
        if low in _INTRA_NAME_PREP and i > 0:
            continue
        if len(tok) == 1 and tok.isupper():
            continue
        if not tok[0].isupper():
            return False
    return True


def sanitize_extraction(
    graph: GraphExtraction | dict[str, Any] | None,
) -> GraphExtraction:
    """Drop empty/stopword/tiny entities and relations that point at them."""
    if graph is None:
        return GraphExtraction()
    if isinstance(graph, dict):
        try:
            graph = GraphExtraction.model_validate(graph)
        except ValidationError:
            return GraphExtraction()

    kept: list[ExtractedEntity] = []
    names_lower: dict[str, str] = {}
    seen: set[str] = set()
    for ent in graph.entities:
        name = normalize_entity_name(ent.name)
        if is_noise_entity(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names_lower[key] = name
        etype = (ent.type or "Concept").strip() or "Concept"
        kept.append(
            ExtractedEntity(
                name=name,
                type=etype,
                description=(ent.description or "").strip(),
            )
        )

    kept_keys = set(names_lower)
    relations: list[ExtractedRelation] = []
    seen_rels: set[tuple[str, str, str]] = set()
    for rel in graph.relations:
        src = names_lower.get(normalize_entity_name(rel.source).lower())
        tgt = names_lower.get(normalize_entity_name(rel.target).lower())
        if not src or not tgt or src.lower() == tgt.lower():
            continue
        if src.lower() not in kept_keys or tgt.lower() not in kept_keys:
            continue
        rel_type = (rel.type or "RELATED_TO").strip() or "RELATED_TO"
        if _label_key(rel_type) in _SCHEMA_LABELS or _label_key(rel_type) in _SCHEMA_REL_TYPES:
            continue
        try:
            strength = float(rel.strength)
        except (TypeError, ValueError):
            strength = 1.0
        if strength < 0:
            strength = 0.0
        if strength > 1:
            strength = 1.0
        key = (src.lower(), tgt.lower(), rel_type.lower())
        if key in seen_rels:
            continue
        seen_rels.add(key)
        relations.append(
            ExtractedRelation(source=src, target=tgt, type=rel_type, strength=strength)
        )

    return GraphExtraction(entities=kept, relations=relations)


def _call_openai(prompt: str, settings: object) -> str:
    api_key = getattr(settings, "openai_api_key", "") or ""
    if not api_key:
        raise RuntimeError(
            "OpenAI API key is missing; set OPENAI_API_KEY or monkeypatch extract_graph."
        )
    from langchain_openai import ChatOpenAI

    kwargs: dict = {
        "model": getattr(settings, "openai_model", "gpt-4o"),
        "api_key": api_key,
        "temperature": 0,
    }
    base_url = getattr(settings, "openai_base_url", "") or ""
    if base_url:
        kwargs["base_url"] = base_url
    try:
        llm = ChatOpenAI(
            **kwargs,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
    except Exception:
        llm = ChatOpenAI(**kwargs)
    message = [
        {"role": "system", "content": "Return only valid JSON matching the requested schema."},
        {"role": "user", "content": prompt},
    ]
    resp = llm.invoke(message)
    content = getattr(resp, "content", resp)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        content = "".join(parts)
    return str(content or "")


def _call_ollama(prompt: str, settings: object) -> str:
    base = str(getattr(settings, "ollama_base_url", "http://localhost:11434")).rstrip("/")
    model = getattr(settings, "ollama_model", "llama3.1")
    url = f"{base}/api/chat"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only valid JSON matching the requested schema."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to reach Ollama at {url}: {exc}") from exc
    message = payload.get("message") or {}
    content = message.get("content")
    if content is None and "response" in payload:
        content = payload["response"]
    if isinstance(content, dict):
        return json.dumps(content)
    return str(content or "")


def _strip_fences(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_and_validate(raw: str) -> GraphExtraction | None:
    text = _strip_fences(raw)
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    try:
        return GraphExtraction.model_validate(data)
    except ValidationError:
        return None
