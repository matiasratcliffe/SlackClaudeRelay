# Design — add-ingest-provenance

- `ContextGraph` facade composes store + embedder + lock manager.
- `add_node(...)`: acquire_write on parent path → validate → auto-embed → persist.
- `link(...)`: dedup check = existing edge, same endpoints, cosine(edge_emb) ≥ threshold, overlapping
  verb tags → reinforce via CAS; else insert.
- `Authority` enum with ranked values; `supersede()` sets `valid_to=now` on the old, inserts new.
- `functional_verbs` = declared set (e.g. `reports_to`, `born_in`); contradiction check queries
  current edges with same source + functional verb + different target → returns candidate list.
- Contradiction resolution beyond flagging (LLM) is out of scope; flags are surfaced, not resolved.
