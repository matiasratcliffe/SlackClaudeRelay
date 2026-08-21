# Change: add-embeddings-entrypoints

## Why
Traversal needs semantic entry points; the tool must embed text with no network by default.

## What changes
Add `EmbeddingProvider` + offline deterministic `HashingEmbedder`, and entry-point search with a
relative cutoff and hybrid (vector + tag) ranking.

## Impact
- New capability: `embeddings-entrypoints`.
- New code: `embeddings.py`; entry-point search consumed by traversal.
