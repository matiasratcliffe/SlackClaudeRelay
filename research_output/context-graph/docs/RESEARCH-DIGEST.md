# Research Digest: Agent Context Graph

Source: `research_agent-context-graphs-a-dynamically-traversable-kno_1787250205*` (report + transcript). Build input for a Neo4j-backed, multi-agent, agentic-memory knowledge graph with Obsidian export.

## 1. Core data model

**Node**: `{id, embedding, tags[], content, namespace_parent_id, owner, version, created_at, updated_at}`. `namespace_parent_id` is single and always present — the tree is strictly single-parent, no exceptions.

**Secondary edge**: `{id, source_id, target_id, edge_embedding, verb_tags[], weight, version, created_at}`. It's a first-class row, not a bare foreign key — its own embedding enables "find edges similar to *mentors*," and its own version lets confidence/weight update without touching either endpoint.

**Central resolution**: the tree encodes *ownership*, never meaning. Real entities are multi-faceted (a coworker who's also a friend), and forcing single-parent placement to represent "what this relates to" fights the structure constantly. Tree position answers one question — who administratively owns this node, for write authority, lock granularity, and default summarization scope — never "what is this connected to." Every relationship, even hierarchical-feeling ones, lives on secondary edges only. This mirrors Zettelkasten/Obsidian/Roam: Luhmann's *folgezettel* (sequential hierarchical numbering) was abandoned once backlinks existed, since a good cross-link mechanism makes forced hierarchy stop paying for itself. Keeping the tree pays off operationally: subtree = lock scope, subtree = default rollup boundary.

**Hub nodes are structurally inevitable.** Any organically-grown graph converges on a power-law degree distribution (Barabasi-Albert preferential attachment: citation graphs, social graphs, personal KGs). Don't store a hub's incoming-edge list inside a versioned record every writer CAS-updates against (hot mutable key); model edges as an independent append-only log keyed by target — adding an edge is an insert, never a read-modify-write.

## 2. Embeddings & entry-point discovery

Node embeddings are the search key for traversal **entry points**: the query embedding runs approximate-nearest-neighbor (ANN) search against node embeddings, not full-text. Baseline index: HNSW (Hierarchical Navigable Small World) — the ANN structure behind both pgvector's and Neo4j's vector indexes.

**Seeding policy**: skip fixed top-K; use a *relative* cutoff (everything within a margin of the top match, or above an absolute floor) — fixed-K wastes budget when only one real match exists and drops a genuine second cluster when the answer spans two. When top matches land in unrelated subtrees (query "budget" hitting a work/finance node and a personal/taxes node), that's often legitimately multi-domain; to avoid wasteful fan-out on a single-domain query, run a cheap classification pre-step against the top-level tree roots first.

**Entry points feed traversal as weighted seeds, not a merge step** — a consequence of using Personalized PageRank (PPR, §3): PPR's personalization vector natively supports multiple restart nodes, each given initial mass proportional to cosine similarity (softmax-normalized across candidates). No separate merge logic is needed.

Edge embeddings support entry-adjacent search too: matching a query against edge embeddings surfaces relevant *relationships* directly, and doubles as dedup — a near-identical edge between the same two nodes should reinforce (bump confidence, refresh timestamp) rather than duplicate.

## 3. Agentic/dynamic traversal strategies

Letting the LLM decide hop-by-hop whether to keep exploring fails both ways: it under-explores, poor at judging what it doesn't know, while over-spending on marginal checks — one full LLM call per hop, no designed stopping condition.

**Split traversal into a mechanical layer and an agentic judgment layer.**

- *Spreading activation* (ACT-R/Soar cognitive architectures): seed entry nodes with initial activation = embedding-similarity score, propagate with per-hop decay and edge-weight scaling — `activation(v) += activation(u) * decay^hop * edge_weight(u,v)` — stop a path once activation drops below threshold, hard max-hop cap as backstop. Pure numeric relaxation, no LLM call, sub-second at scale.
- *Personalized PageRank (PPR)* — the formalized random-walk-with-restart version, used by **HippoRAG** (Gutierrez et al.), modeled on hippocampal indexing theory (hippocampus = lightweight associative index over content the neocortex stores). Pipeline: query embedding matches entities (entry points) → PPR propagates from seeds → top-ranked entities map back to content. It beats dense retrieval on multi-hop QA because PPR follows *edges* per hop, surfacing facts with zero textual resemblance to the query as long as they're relationship-connected to a match. Since your nodes/edges are already typed (no OpenIE extraction needed, unlike HippoRAG's raw-corpus origin), its PPR-over-graph algorithm can be lifted nearly directly as the mechanical layer.

**Two-layer architecture**: the mechanical layer produces a bounded candidate subgraph in one cheap pass; only then does the LLM read it, judge relevance, and synthesize — exposed as tools (`search_similar`, `expand_edges`, `read_node`).

**Hub correction** (ACT-R's "fan effect": a node connected to everything dilutes signal to each neighbor): normalize activation by out-degree when propagating — PageRank's core move. Also don't let traversal stop *on* a hub normally — auto-maintain a rolled-up summary for any node above a degree threshold (GraphRAG's community-summary move, applied locally) and read the summary first, descending into only 1-2 relevant children.

**Derived-hierarchy alternative**: Microsoft's **GraphRAG** builds an entity graph from LLM-extracted triples, then runs the **Leiden algorithm** (modularity-based community detection) to produce a derived, multi-level summary tree — hierarchy computed from connectivity density, nobody assigns ownership. "Global search" map-reduces over community summaries; "local search" enters via entity-embedding match and expands along edges. Derived hierarchy adapts to real structure but is costly to keep current and can silently reshuffle boundaries — wrong as a primary lock-scope tree, but usable as an optional re-filing suggestion.

## 4. Concurrency & the RW lock-by-agent-id design

**Tree backbone → pessimistic, multi-granularity hierarchical locking** (Gray et al., 1976 — the intent-lock scheme relational DBs use for table→page→row). Writing `work/project-x/task-7` takes intent-exclusive (IX) locks on `root`, `work`, `work/project-x`, and a full exclusive (X) lock only on `task-7`. Agents in disjoint subtrees never contend, since intent locks overlap only at the shared root and are mutually compatible. This works cleanly *because* the tree is strictly single-parent; a DAG-shaped ownership tree would make lock scope ambiguous once two "parents" claim write authority over a shared descendant.

**Secondary-edge layer → optimistic concurrency, not locks.** Secondary edges cut across subtrees by design, so extending hierarchical locking to them serializes every agent touching anything connected to a popular hub. Instead every edge and node-content field carries a `version`; writes are compare-and-swap (`UPDATE ... WHERE version = $expected`), losers retry against fresh state. Hub nodes use the append-only edge log from §1, so incoming-edge writes never require read-modify-write.

**Lock keying by agent-id**: track intent/exclusive locks per requesting agent-id, not per session — this enables detecting an agent re-entering its own lock, per-agent contention telemetry, and safe release of all locks an agent-id holds on disconnect or crash.

**Pitfalls**: blocking writes on an LLM contradiction check breaks the "writes are fast" assumption CAS depends on — keep checks async/queued; treating hub connectivity as locked node-internal state recreates the hot-key problem; letting derived hierarchy override assigned ownership invalidates lock-scope assumptions.

## 5. Neo4j specifics

**Labels**: base label `:CtxNode` plus a domain-subtype label (`:Person`, `:Project`, `:Fact`, `:Root`) for label-scoped lookups. Store `namespace_parent_id`, `owner`, `version`, `tags`, `embedding` as properties.

**Relationship types**: one fixed type for the primary tree edge, e.g. `:CHILD_OF` (child→parent) — pick one direction, since types are static. For secondary edges, verb-like tags either live as a `verb_tags` list property on a generic `:RELATES_TO` type, or become distinct typed relationships (`:MENTORS`, `:COLLABORATED_ON`) when the vocabulary is small and stable — a flexibility-vs-efficiency trade-off.

**Vector index support**: Neo4j 5.11+ has a native HNSW-backed vector index, but it indexes **node** properties only — relationships cannot carry one directly. Secondary edges needing embeddings must be reified as an intermediate node (`(:CtxNode)-[:FROM]->(:EdgeNode {embedding, verb_tags, weight, version})<-[:TO]-(:CtxNode)`), trading an extra hop for full vector-index support:

```cypher
CREATE VECTOR INDEX node_embedding_idx IF NOT EXISTS
FOR (n:CtxNode) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};
CALL db.index.vector.queryNodes('node_embedding_idx', 10, $queryEmbedding) YIELD node, score
```

**Cypher patterns worth knowing**:
- Bounded candidate pull: `MATCH (n:CtxNode)-[:RELATES_TO*1..3]-(m) WHERE n.id = $seedId RETURN DISTINCT m` — cap hops to the activation max-hop backstop.
- PPR via **Graph Data Science (GDS)**: `CALL gds.pageRank.stream('ctxGraph', {sourceNodes: $seedIds, dampingFactor: 0.85})` — `sourceNodes` is the weighted-multi-seed mechanism from §2/§3; project a bounded subgraph first with `gds.graph.project`.
- Leiden analog to GraphRAG: `CALL gds.leiden.stream('ctxGraph')` — only as an optional re-filing suggestion.
- No Postgres-style advisory-lock primitive exists; implement the §4 intent-lock table as rows keyed by tree path + agent-id, or use `apoc.lock.nodes()`.
- Append-only hub log: `(:CtxNode)-[:HUB_LOG_ENTRY {ts}]->(:LogEntry)`, writes are pure `CREATE`, never `MERGE`/`SET`.

## 6. Obsidian-like representation

Export each node as one Markdown file with YAML front matter for structured properties (`id`, `tags`, `owner`, `version`, `created_at`); omit the raw embedding (too large, not human-meaningful). File location mirrors the **primary tree** (folder path = `namespace_parent_id` chain) — matching Obsidian's convention that the folder tree is storage location, not semantic weight.

Secondary edges become **wikilinks** (`[[Target Node Name]]`) in the body, optionally annotated with the verb-tag inline (`[[Jane Doe]] (mentors)`), so Obsidian's native backlink panel and graph view surface the relationship graph directly — reproducing the "tree = cosmetic storage, backlinks = real semantic weight" pattern from prior art. This design is stronger than plain Obsidian since the tree still carries ownership/lock semantics rather than being purely cosmetic.

Obsidian's built-in graph view renders folders + wikilinks with no extra tooling — sufficient to eyeball what agents have built. Dataview can query front-matter fields across the vault for ad hoc reporting; Canvas files can snapshot one traversal result (entry point + activated subgraph) for debugging.

## 7. Prior art / comparable systems

- *Semantic networks / frame systems* (Quillian, Minsky, 1960s-70s) — typed nodes/edges, spreading activation from a cue. Died from unmaintainability: hand-authored ontologies don't scale and nothing kept them synced with reality.
- *ACT-R / Soar* — declarative memory as a graph, activation decaying by distance/time: a principled stopping rule.
- *Microsoft GraphRAG* — entity graph + Leiden-derived community-summary tree; closest tree+graph hybrid, but its tree is a derived compression structure, not ownership/lock.
- *HippoRAG* (Gutierrez et al.) — hippocampal-indexing-inspired PPR retrieval; validates the mechanical shape empirically, but has no write path, concurrency control, or agentic layer.
- *Graphiti / Zep* — the real contribution isn't "time-awareness" but **never mutate in place**: conflicting info invalidates the old edge (`valid_to`) and appends a new one — generalizes to any provenance-tracked append-and-supersede.
- *Obsidian / Roam / Zettelkasten* (Luhmann's folgezettel as origin) — folder tree as cosmetic storage, backlink graph as real structure; the UX model for §6.

**Trade-offs and pitfalls to avoid**:
- Don't let the tree carry meaning — it collapses under multi-parent reality; keep it ownership-scoped only.
- Avoid a separate graph DB alongside a separate vector DB when possible — dual-system consistency under concurrent writes is exactly the problem this design avoids.
- Don't let an LLM decide traversal stopping hop-by-hop — use mechanical activation/PPR, reserve the LLM for judging content.
- Don't treat hub nodes reactively — the scale-free property is inevitable; design the append-only log, out-degree normalization, and hub-summary traversal in from day one.
- Don't skip contradiction detection — the failure mode that ended the semantic-network era. Use a free structural heuristic (same subject + same *functional* relation + different object) feeding an async LLM check only for ambiguous/same-rank cases, gated by authority ranking (user-stated > system sync > agent-inferred > chained inference).
- Don't block writes on any expensive check — optimistic CAS depends on writes staying fast; queue LLM resolution asynchronously.
- Don't recompute summaries on every write — debounce regeneration on an N-changes-or-T-time trigger as a background job.
