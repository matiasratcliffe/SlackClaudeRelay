# Design — add-embeddings-entrypoints

- `HashingEmbedder`: hashed bag-of-tokens → fixed-dim (default 256) L2-normalized vector; pure
  stdlib, deterministic. Real providers (sentence-transformers, API) implement the same interface.
- `cosine(a,b)` helper shared with stores.
- `find_entry_points(query, k_max)`: vector_search top candidates, then relative cutoff
  `score >= max(floor, top_score - margin)`; hybrid score = `alpha*cos + beta*tag_overlap`.
- Optional top-level-root pre-classification (cheap cosine vs root children) to restrict fan-out;
  exposed as a flag, default off for simplicity.
- Seeds returned as `[(node_id, weight)]` where weight = normalized score (feeds PPR restart).
