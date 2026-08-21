"""Embeddings and entry-point discovery.

Ships an offline, deterministic `HashingEmbedder` so the tool works with no network or API key; real
providers (sentence-transformers, hosted APIs) implement the same `EmbeddingProvider` interface.
Entry points are chosen by a *relative* cutoff (not a fixed top-K) with hybrid vector+tag ranking,
and returned as similarity-weighted seeds for traversal.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

_TOKEN = re.compile(r"[a-z0-9]+")


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity; 0.0 if either vector is empty/zero."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class EmbeddingProvider(ABC):
    dim: int

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        ...


class HashingEmbedder(EmbeddingProvider):
    """Deterministic hashed bag-of-tokens embedder (stdlib only).

    Not semantically strong, but stable and dependency-free — enough to exercise the whole pipeline
    offline. Each token is hashed into a bucket (with a sign hash) and the vector is L2-normalized.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN.findall((text or "").lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            bucket = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


def find_entry_points(
    store,
    embedder: EmbeddingProvider,
    query: str,
    *,
    query_tags: list[str] | None = None,
    k_max: int = 20,
    margin: float = 0.15,
    floor: float = 0.05,
    alpha: float = 1.0,
    beta: float = 0.25,
) -> list[tuple[str, float]]:
    """Return `[(node_id, weight)]` traversal seeds by hybrid similarity with a relative cutoff.

    Seeds are every candidate scoring within `margin` of the best (and above `floor`); `weight` is
    the normalized hybrid score, suitable as a PPR restart mass. `store` must expose
    `vector_search(embedding, k, kind)` and `get_node(id)`.
    """
    q = embedder.embed(query)
    qtags = set(t.lower() for t in (query_tags or []))
    scored: list[tuple[str, float]] = []
    for node_id, sim in store.vector_search(q, k_max, kind="node"):
        node = store.get_node(node_id)
        tag_overlap = 0.0
        if node and qtags and node.tags:
            tag_overlap = len(qtags & {t.lower() for t in node.tags}) / len(qtags)
        scored.append((node_id, alpha * sim + beta * tag_overlap))
    if not scored:
        return []
    scored.sort(key=lambda p: p[1], reverse=True)
    top = scored[0][1]
    kept = [(i, s) for i, s in scored if s >= max(floor, top - margin)]
    total = sum(s for _, s in kept) or 1.0
    return [(i, s / total) for i, s in kept]
