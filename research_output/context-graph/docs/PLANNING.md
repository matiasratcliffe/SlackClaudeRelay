# Planning — Context Knowledge Graph

Solution planning for the scoped tool, the design decisions behind it, and a **descriptive-only**
section on the future "pi" super-agent. Grounded in [BACKLOG.md](BACKLOG.md) and
[RESEARCH-DIGEST.md](RESEARCH-DIGEST.md); operating rules in [INSTRUCTIONS.md](INSTRUCTIONS.md).

## 1. Objective & north star
Build a **dynamically traversable context knowledge graph** for agent long-term memory: a tree of
life-section nodes with per-node embeddings + tags, any-to-any secondary semantic edges (with their
own embeddings + verb tags), embedding-based **entry-point** search, **agentic traversal + context
assembly**, an **RW lock keyed by agent-id** for safe multi-agent sharing, **Neo4j + in-memory**
backends, and an **Obsidian-style** vault export.

## 2. Key design decisions (with rationale)

**D1 — The tree encodes *ownership*, not *meaning*.** Primary edges answer only "who
administratively owns this node" → write authority, **lock granularity**, and default
summarization/rollup scope. All real relationships (even hierarchical-feeling ones like task→project)
live on **secondary edges**. Rationale: real entities are multi-faceted (a coworker who is also a
friend); forcing single-parent placement to mean "relates to" fights the structure — the same lesson
Zettelkasten/Obsidian learned when backlinks made forced hierarchy stop paying off. This honors the
owner's "tree + secondary edges" vision while making the tree carry operational, not semantic, load.

**D2 — Strict single-parent tree; secondary edges make it a general graph.** Every node has exactly
one `parent_id` (root = `CONTEXT_ROOT`); primary edges are **acyclic** (note 3). Secondary edges are
first-class, any-to-any, directed-or-symmetric, and may form cycles.

**D3 — Secondary edges are reified as first-class records** with `{id, source, target,
edge_embedding, verb_tags[], weight, version, valid_from/valid_to}`. Their own embedding enables
"find relationships like *mentors*" and dedup/reinforce; their own version lets confidence update
without touching endpoints. In Neo4j (whose vector index covers **nodes only**), reify as an
`:EdgeNode` between endpoints so the edge embedding is indexable.

**D4 — Entry points via ANN with a *relative* cutoff.** Query embedding → approximate nearest
neighbors over node embeddings (HNSW). Seed with everything within a margin of the top match (not a
fixed top-K). A cheap top-level-root classification decides whether to restrict seeding to one
subtree or fan across domains.

**D5 — Two-layer traversal: mechanical + agentic.** A cheap mechanical layer produces a bounded
candidate subgraph from weighted seeds — **spreading activation** (`activation(v) += activation(u)·
decay^hop·edge_weight`, threshold + max-hop cap) and/or **Personalized PageRank** (HippoRAG-style,
multi-seed restart weighted by similarity). Only then does the agent judge content over the bounded
subgraph via tools (`search_similar`, `expand_edges`, `read_node`). Never let the LLM decide
stopping hop-by-hop. *(The agentic/LLM judgment layer is described here but its LLM wiring is a
pi-agent concern; the tool surface + mechanical layer are in scope.)*

**D6 — Concurrency split by layer, keyed by agent-id.**
- **Tree → hierarchical intent locks** (Gray et al. IX/X): writing `work/proj-x/task-7` takes IX on
  root/work/proj-x and X on task-7; disjoint subtrees never contend. Clean *because* the tree is
  single-parent.
- **Secondary edges → optimistic concurrency** (version + compare-and-swap; losers retry). Locking
  cross-cutting edges would serialize everything touching a hub.
- Locks tracked **per agent-id** → re-entrancy detection, per-agent telemetry, safe release of all
  of an agent's locks on crash.

**D7 — Append-and-supersede provenance** (Graphiti/Zep's real lesson, generalized beyond time):
never mutate in place for facts; conflicting info sets `valid_to` on the old edge and appends a new
one, with **authority ranking** (user-stated > system-of-record > direct inference > chained).

**D8 — Hubs are inevitable (scale-free), designed for from day one:** append-only incoming-edge log
(insert, never read-modify-write), out-degree-normalized activation, and a rolled-up **hub summary**
read first (descend into only 1–2 relevant children). Summaries regenerate debounced, not per write.

**D9 — Contradiction detection = two-stage funnel.** Synchronous, free **structural heuristic**
(same subject + same *functional* relation + different object → candidate) is in scope; the async
LLM adjudication it feeds is a pi-agent concern (deferred). Functional-vs-multivalued verb tags are a
declared convention, not inferred.

**D10 — Obsidian export mirrors the tree as folders, edges as wikilinks.** One markdown file per
node under its `parent` folder path, YAML frontmatter for properties (embedding omitted, referenced
by id), secondary edges as `[[Target]] (verb)` wikilinks so Obsidian's backlink/graph view surfaces
the semantic graph natively.

## 3. Architecture / module map
```
src/context_graph/
  model.py            # Node, SecondaryEdge, enums, ids, validation (tree invariants)
  store/base.py       # StorageBackend interface (nodes, edges, vector search, versions, locks hook)
  store/memory_store.py  # zero-dep reference backend (executable spec) + brute-force vector search
  store/neo4j_store.py   # Neo4j backend: labels, :CHILD_OF, reified :EdgeNode, vector index, Cypher
  embeddings.py       # EmbeddingProvider interface + offline deterministic HashingEmbedder + hooks
  locking.py          # LockManager: hierarchical intent locks (tree) + version/CAS (edges), agent-id
  traversal.py        # spreading activation + PPR mechanical layer; bounded candidate subgraph
  assembly.py         # rank + budgeted context assembly → subgraph + rendered markdown blob
  export_obsidian.py  # vault exporter (folders mirror tree, wikilinks for edges)
  graph.py            # ContextGraph facade tying store+embeddings+locks+traversal together
  cli.py              # argparse CLI: init/add-node/link/search/traverse/export/lock-status/demo
  sample.py           # seeded sample graph for demo/tests
```

## 4. Storage backends
- **In-memory** (`memory_store`): dicts + brute-force cosine; zero deps; the **reference semantics**
  every other backend must match; keeps the tool runnable with no server (self-containedness goal).
- **Neo4j** (`neo4j_store`): `:CtxNode` + subtype labels, `:CHILD_OF` primary edges, reified
  `:EdgeNode` for secondary edges, native HNSW vector index, `apoc.lock.nodes()`/lock-table for the
  intent locks, GDS `pageRank`/`leiden` for PPR and optional community suggestions.

## 5. Capability → OpenSpec mapping
| Capability (`openspec/specs/`) | Backlog epics |
|---|---|
| `graph-model` | E1, E2 |
| `storage` | E3 |
| `embeddings-entrypoints` | E4 |
| `traversal-assembly` | E5 |
| `concurrency-locking` | E6 |
| `ingest-provenance` | E7, D7, D9(struct) |
| `obsidian-export` | E8 |
| `cli` | E9, E10 |

## 6. Story / change plan (OpenSpec changes)
Ordered; each is one `openspec/changes/<id>/` with proposal + Kiro requirements + design + tasks +
delta. Dependencies flow top-down.
1. `add-graph-model` — nodes, tree invariants, secondary-edge records, validation.
2. `add-storage-backends` — StorageBackend interface + in-memory + Neo4j skeleton.
3. `add-embeddings-entrypoints` — provider abstraction, offline embedder, ANN + relative-cutoff seeds.
4. `add-concurrency-locking` — hierarchical intent locks + optimistic CAS, keyed by agent-id.
5. `add-traversal-assembly` — spreading activation + PPR, budgeted context assembly.
6. `add-ingest-provenance` — write API, auto-embed, dedup/reinforce, append-and-supersede, structural
   contradiction heuristic.
7. `add-obsidian-export` — vault exporter.
8. `add-cli` — CLI + sample graph + self-contained demo.

## 7. Out of scope — the "pi" super-agent (descriptive only, do NOT implement)
The owner eventually wants a full agent (working name **"pi"**) that **consumes** this graph. Written
here to capture intent; **no code now or in the improvement loop.**

- **Purpose:** an agent whose long-term memory *is* this context graph — it enters by embedding
  match, traverses agentically, and assembles just-in-time context per task.
- **Shared source of truth for ALL agents.** The graph is the single common knowledge base across
  the owner's whole agent fleet. PI **sub-agents keep only their limited chat history as local
  context**; anything durable they learn gets written INTO the graph — preference learnings into the
  `preferences` node, factual learnings into `work-facts` / `personal-facts`, people into `social` —
  using the opinionated structure's deterministic section ids (see INTERFACE.md). Chat history is
  ephemeral working memory; the graph is where knowledge survives and is shared.
- **Progressive disclosure of skills.** Skills/guidance live in (or alongside) the graph as
  behaviour nodes, distinct from pure context/knowledge (note 2's split). The agent discloses skills
  **dynamically and progressively** based on the active context subgraph — surfacing only relevant
  skills instead of a flat always-on list. **MCP tools are out of scope for now.**
- **Short-term scratchpad memory.** Separate from the long-term graph, the agent needs a
  **scratchpad** for ephemeral working memory — e.g. organizing the day's itinerary — that is not
  committed to long-term memory unless promoted.
- **"Ring-a-bell" interrupt system (note 1).** A `BELL` faculty: when the current situation is a
  **cosine-distance match** to a past situation stored in the graph, **fire an interrupt** carrying a
  specific prompt/action ("this rings a bell — last time you…"). Associative recall as a proactive
  interrupt, not a passive lookup.
- **Model-skill-interpretation benchmark (note 2).** A metric/benchmark for **how differently
  various models interpret the same skill** — to choose/tune models and to detect skill wording that
  is model-fragile.
- **Standard skills used by context (note 1).** A baseline library of general-purpose skills the
  agent can always draw on, selected/ranked by the active context.

## 8. Risks & pitfalls (carried from research)
- Don't let the tree carry meaning (collapses under multi-parent reality) — ownership-only.
- Don't pair a separate graph DB with a separate vector DB — dual-system write consistency is the
  trap this design avoids; one engine (or the reified-edge-node workaround) instead.
- Don't let an LLM decide traversal stopping hop-by-hop — mechanical activation/PPR bounds it.
- Don't treat hubs reactively — append-only log, out-degree normalization, hub-summary-first.
- Don't skip contradiction detection (what killed the semantic-network era) — structural heuristic
  now, async LLM adjudication later (pi).
- Don't block writes on expensive checks — optimistic CAS needs writes fast; queue LLM checks.
