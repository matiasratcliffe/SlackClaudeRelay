# Research Digest: Agent Context Graph

Source: `research_agent-context-graphs-a-dynamically-traversable-kno_1787250205*` (report + transcript). Build input for a Neo4j-backed, multi-agent, agentic-memory knowledge graph with Obsidian export.

## 1. Core data model

**Node**: `{id, embedding, tags[], content, namespace_parent_id, owner, version, created_at, updated_at}`. `namespace_parent_id` is single and always present — the tree is strictly single-parent, no exceptions.

**Secondary edge**: `{id, source_id, target_id, edge_embedding, verb_tags[], weight, version, created_at}`. It's a first-class row, not a bare foreign key — its own embedding enables "find edges similar to *mentors*," and its own version lets confidence/weight update without touching either endpoint.

**Central resolution**: the tree encodes *ownership*, never meaning. Real entities are multi-faceted (a coworker who's also a friend), and forcing single-parent placement to represent "what this relates to" fights the structure constantly. Tree position answers one question — who administratively owns this node, for write authority, lock granularity, and default summarization scope — never "what is this connected to." Every relationship, even hierarchical-feeling ones (task belongs to project), lives on secondary edges only. This mirrors Zettelkasten/Obsidian/Roam: Luhmann's *folgezettel* (sequential hierarchical numbering) was abandoned once backlinks existed, because a good cross-link mechanism makes forced hierarchy stop paying for itself. Keeping the tree pays off operationally: subtree = lock scope, subtree = default rollup boundary.

**Hub nodes are structurally inevitable.** Any organically-grown graph converges on a power-law degree distribution (Barabasi-Albert preferential attachment — citation graphs, social graphs, the web, and personal KGs all show it). Don't store a hub's incoming-edge list inside a versioned record every writer CAS-updates against (hot mutable key); model edges as an independent append-only log keyed by target, so adding an edge is an insert, never a read-modify-write. Node content stays lightly versioned; the edge list is decoupled from it.

## 2. Embeddings & entry-point discovery

Node embeddings are the search key for finding traversal **entry points**: the query embedding runs approximate-nearest-neighbor (ANN) search against node embeddings, not full-text. Baseline index type: HNSW (Hierarchical Navigable Small World) — the ANN structure behind both pgvector's and Neo4j's native vector indexes.

**Seeding policy**: skip fixed top-K; use a *relative* cutoff (everything within a margin of the top match, or above an absolute floor) — fixed-K wastes budget when only one real match exists and drops a genuine second cluster when the answer spans two. When top matches land in unrelated subtrees (query "budget" hitting both a work/finance node and a personal/taxes node), that's often legitimately multi-domain — but to avoid wasteful fan-out on a single-domain query, run a cheap classification pre-step against only the top-level tree roots to decide whether to restrict seeding to one subtree.

**Entry points feed traversal as weighted seeds, not a merge step** — a consequence of using Personalized PageRank (PPR, §3) for propagation: PPR's personalization vector natively supports multiple restart nodes, each given initial mass proportional to cosine similarity (softmax-normalized across candidates). No separate merge logic is needed.

Edge embeddings support entry-adjacent search too: matching a query against edge embeddings surfaces relevant *relationships* directly, and doubles as dedup — a new edge near-identical to an existing edge between the same two nodes should reinforce (bump confidence, refresh timestamp) rather than duplicate.

## 3. Agentic/dynamic traversal strategies

Letting the LLM decide hop-by-hop whether to keep exploring fails both ways: LLMs judge what they don't know poorly, so they under-explore (stopping too early) while over-spending on marginal checks — one full LLM call per hop, no designed stopping condition, unpredictable cost.

**Split traversal into a mechanical layer and an agentic judgment layer.**

- *Spreading activation* (ACT-R/Soar cognitive architectures): seed entry nodes with initial activation = embedding-similarity score, propagate with per-hop decay and edge-weight scaling — `activation(v) += activation(u) * decay^hop * edge_weight(u,v)` — stop a path once activation drops below threshold, hard max-hop cap as backstop. Pure numeric relaxation, no LLM call, sub-second at scale.
- *Personalized PageRank (PPR)* — the formalized random-walk-with-restart version, used by **HippoRAG** (Gutierrez et al.), modeled on hippocampal indexing theory (hippocampus = lightweight associative index over content the neocortex stores). Pipeline: query embedding matches entities (entry points) → PPR propagates from seeds → top-ranked entities map back to source content. It beats plain dense retrieval on multi-hop QA because PPR follows *edges* per hop, not embedding similarity — surfacing facts with zero textual resemblance to the query as long as they're relationship-connected to a match, which dense retrieval structurally cannot do. Since your nodes/edges are already typed (no OpenIE extraction needed, unlike HippoRAG's raw-corpus origin), its PPR-over-graph algorithm can be lifted nearly directly as the mechanical layer.

**Two-layer architecture**: the mechanical layer produces a bounded candidate subgraph from the seeds in one cheap pass; only then does the LLM read that subgraph, judge relevance, and synthesize — exposed as tools (`search_similar`, `expand_edges`, `read_node`) so the agent judges content, not topology.

**Hub correction** (ACT-R's "fan effect": a node connected to everything dilutes signal to each neighbor): normalize activation by out-degree when propagating — PageRank's core move, dividing a node's vote among its outbound edges. Also don't let traversal stop *on* a hub normally — auto-maintain a rolled-up summary for any node above a degree threshold (GraphRAG's community-summary move, applied locally), and have traversal read the summary first, descending into only 1-2 judged-relevant children.

**Comparable derived-hierarchy alternative**: Microsoft's **GraphRAG** builds an entity graph from LLM-extracted triples, then runs the **Leiden algorithm** (modularity-based community detection) to produce a derived, multi-level summary tree — hierarchy computed from connectivity density, nobody assigns ownership. "Global search" map-reduces top-down over community summaries; "local search" enters via entity-embedding match and expands along edges, bypassing the tree. Derived hierarchy adapts to real structure but is costly to keep current and can reshuffle boundaries silently — wrong as your primary lock-scope tree, but usable as an optional secondary "how does this actually cluster?" suggestion tool, never a live dependency.

## 4. Concurrency & the RW lock-by-agent-id design

Tree and graph layer have different contention profiles and need different mechanisms.

**Tree backbone → pessimistic, multi-granularity hierarchical locking** (Gray et al., 1976 — the intent-lock scheme relational DBs use for table→page→row). Writing `work/project-x/task-7` takes intent-exclusive (IX) locks on `root`, `work`, `work/project-x`, and a full exclusive (X) lock only on `task-7`. Agents in disjoint subtrees never contend — intent locks overlap only at the shared root and are mutually compatible. This works cleanly *because* the tree is strictly single-parent; a DAG-shaped ownership tree would make lock scope ambiguous the moment two "parents" claim write authority over a shared descendant, inviting deadlock unnecessarily.

**Secondary-edge layer → optimistic concurrency, not locks.** Secondary edges cut across subtrees by design, so extending hierarchical locking to them serializes every agent touching anything connected to a popular hub — defeating concurrency. Instead: every edge and node-content field carries a `version`; writes are compare-and-swap (`UPDATE ... WHERE version = $expected`), losers retry against fresh state. Hub nodes additionally use the append-only edge log from §1, so incoming-edge writes never require read-modify-write.

**Lock keying by agent-id**: acquire and track intent/exclusive locks per requesting agent-id (not per session), enabling detection of an agent re-entering its own lock, per-agent contention telemetry, and safe release of all locks held by an agent-id on disconnect/crash without orphaning locks that block others.

**Pitfalls**: blocking a write on an LLM contradiction check breaks the "writes are fast" assumption optimistic CAS depends on — keep such checks async/queued; treating hub connectivity as node-internal locked state recreates the hot-key problem; letting derived/community hierarchy override assigned ownership silently invalidates lock-scope assumptions.

## 5. Neo4j specifics

**Labels**: base label `:CtxNode` plus a domain-subtype label (`:Person`, `:Project`, `:Fact`, `:Root`) for label-scoped lookups. Store `namespace_parent_id`, `owner`, `version`, `tags`, and `embedding` as node properties.

**Relationship types**: one fixed, cheap-to-traverse type for the primary tree edge, e.g. `:CHILD_OF` (child→parent) — pick one direction and stick to it, since Neo4j relationship types are static. For secondary edges, since relationship types aren't dynamic per-instance, the verb-like tags either live as a `verb_tags` list property on a generic `:RELATES_TO` type (`WHERE any(t IN r.verb_tags WHERE t = 'mentors')`), or become distinct typed relationships (`:MENTORS`, `:COLLABORATED_ON`) when the vocabulary is small and stable — a query-flexibility-vs-traversal-efficiency trade-off.

**Vector index support**: Neo4j 5.11+ has a native HNSW-backed vector index, but it indexes **node** properties only — relationships cannot carry one directly. Secondary edges needing embeddings for edge-similarity search must be reified as an intermediate node (`(:CtxNode)-[:FROM]->(:EdgeNode {embedding, verb_tags, weight, version})<-[:TO]-(:CtxNode)`), trading an extra traversal hop for full vector-index support:

```cypher
CREATE VECTOR INDEX node_embedding_idx IF NOT EXISTS
FOR (n:CtxNode) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};
CALL db.index.vector.queryNodes('node_embedding_idx', 10, $queryEmbedding) YIELD node, score
```

**Cypher patterns worth knowing**:
- Bounded candidate-subgraph pull: `MATCH (n:CtxNode)-[:RELATES_TO*1..3]-(m) WHERE n.id = $seedId RETURN DISTINCT m` — cap hops to match the activation max-hop backstop.
- PPR via **Graph Data Science (GDS)**: `CALL gds.pageRank.stream('ctxGraph', {sourceNodes: $seedIds, dampingFactor: 0.85})` — `sourceNodes` is the weighted-multi-seed mechanism from §2/§3; project a bounded subgraph first with `gds.graph.project`.
- Leiden analog to GraphRAG: `CALL gds.leiden.stream('ctxGraph')` — only as an optional re-filing suggestion, never the live ownership tree.
- No Postgres-style advisory-lock primitive exists; implement the §4 intent-lock table as rows keyed by tree path + agent-id, or use `apoc.lock.nodes()` for pessimistic locks on the path nodes touched.
- Append-only hub log: `(:CtxNode)-[:HUB_LOG_ENTRY {ts}]->(:LogEntry)` so writes are pure `CREATE`, never `MERGE`/`SET` against the hub's own properties.

## 6. Obsidian-like representation

Export each node as one Markdown file with YAML front matter for structured properties (`id`, `tags`, `owner`, `version`, `created_at`); omit the raw embedding (too large, not human-meaningful), referencing it by id if needed. File location mirrors the **primary tree** (folder path = `namespace_parent_id` chain) — matching Obsidian's convention that the folder tree is storage location, not semantic weight.

Secondary edges become **wikilinks** (`[[Target Node Name]]`) in the body, optionally annotated with the verb-tag inline (`[[Jane Doe]] (mentors)`), so Obsidian's native backlink panel and graph view surface the relationship graph directly. This reproduces the "tree = cosmetic storage, backlinks = real semantic weight" pattern from prior art — Obsidian/Roam/Zettelkasten never needed a load-bearing folder tree because the backlink graph did the real work; this design is stronger since the tree still carries ownership/lock semantics rather than being purely cosmetic.

Obsidian's built-in graph view renders folders + wikilinks with no extra tooling — sufficient for a human to eyeball what agents have built. Dataview can query front-matter fields (tags, owner, confidence) across the vault for ad hoc reporting; Canvas files can snapshot a specific traversal result (entry point + activated subgraph) as a fixed visual artifact for debugging one retrieval.

## 7. Prior art / comparable systems

- *Semantic networks / frame systems* (Quillian, Minsky, 1960s-70s) — typed nodes/edges, spreading activation from a cue. Died from unmaintainability: hand-authored ontologies don't scale and nothing kept them synced with reality — the single most important cautionary lesson here.
- *ACT-R / Soar* — declarative memory as a graph, activation decaying by distance/time from a cue: a principled stopping rule rather than an ad hoc one.
- *Microsoft GraphRAG* — entity graph + Leiden-derived hierarchical community-summary tree; closest existing tree+graph hybrid, but its tree is a derived compression structure for summarization, not an ownership/lock structure.
- *HippoRAG* (Gutierrez et al.) — hippocampal-indexing-inspired PPR retrieval; validates the "embed to enter, propagate to traverse, map back to content" shape empirically, but has no write path, concurrency control, or agentic judgment layer.
- *Graphiti / Zep* — the real contribution isn't "time-awareness" but **never mutate in place**: conflicting info invalidates the old edge (`valid_to`) and appends a new one, preserving history. Generalizes beyond time to any provenance-tracked append-and-supersede.
- *Obsidian / Roam / Zettelkasten* (Luhmann's folgezettel as origin) — folder tree as cosmetic storage, backlink graph as real structure; direct UX model for §6.

**Trade-offs and pitfalls to avoid**:
- Don't let the tree carry meaning — it collapses under multi-parent reality; keep it ownership-scoped only.
- Avoid a separate graph DB alongside a separate vector DB when possible — dual-system consistency under concurrent writes is the exact problem this design avoids; one engine covering both (or the reified-edge-node work-around in Neo4j, §5) is preferable.
- Don't let an LLM decide traversal stopping hop-by-hop — use mechanical activation/PPR and reserve the LLM for judging content over a pre-bounded subgraph.
- Don't treat hub nodes reactively — the scale-free property is inevitable; design the append-only log, out-degree normalization, and hub-summary-first traversal in from day one.
- Don't skip contradiction detection — the failure mode that ended the semantic-network era. Use a two-stage funnel: a synchronous, free structural heuristic (same subject + same *functional* relation + different object = candidate contradiction; declare functional vs. multi-valued verb-tags as a fixed convention, not inferred) feeding an async LLM check only for ambiguous/same-rank cases, gated by provenance-based authority ranking (user-stated > system-of-record sync > direct agent inference > chained inference).
- Don't block writes on any expensive check — optimistic CAS depends on writes staying fast; queue LLM-based resolution asynchronously.
- Don't recompute summaries synchronously on every write — debounce subtree/hub-summary regeneration on an N-changes-or-T-time trigger, run as a scheduled background job.
