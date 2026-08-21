# Backlog — Context Knowledge Graph (agent long-term memory)

Internal, tracker-free backlog of **everything wanted**. Scoped to the knowledge-graph tool.
Future/out-of-scope intent (the "pi" super-agent) is described in [PLANNING.md](PLANNING.md#out-of-scope-the-pi-super-agent);
this file only points at it. Items here feed the OpenSpec capabilities and per-story changes.

## Vision (one paragraph)

A single, well-structured **knowledge graph** that serves as an agent's long-term memory and
context. Its **primary edges form a tree**: an overall context root, with sections for the
different aspects of life (work, personal, ideas, …), each branching into finer nodes (coworkers,
projects, …). **Every node** carries a vector **embedding** and a set of **tags/labels**. On top of
the tree, **secondary edges** may connect **any** node to any other node to capture semantic
relationships that the hierarchy can't; a secondary edge itself can carry an **embedding** and a set
of **verb-like relation tags**. Agents find **entry points** by embedding similarity, then
**traverse dynamically and agentically** from there, assembling just the context they need. Multiple
agents share one graph safely via a **read/write lock keyed by agent id**. The graph is backed by
**Neo4j** and can be **exported to an Obsidian-like vault** for human viewing.

## In-scope epics & wants

### E1 — Graph data model
- Node = unit of context/knowledge. Fields: stable `id`, `type`, `title`, `body`/content,
  `embedding`, `tags[]`, timestamps (`created`/`updated`), `source`/provenance, owning `agent_id`.
- **Primary (hierarchical) edges form a proper tree** — exactly one parent per node, single root
  (`CONTEXT_ROOT`). Enforce acyclicity on primary edges (note 3).
- **Sections of life** as first-class subtrees under root: e.g. `work`, `personal`, `ideas`
  (extensible), each with descendant nodes (coworkers, projects, …).
- Distinguish **pure context/knowledge** nodes from **guidance/behaviour (skill)** nodes via node
  type (note 2) — the graph *models* the distinction; skill *execution* is out of scope (pi).

### E2 — Secondary semantic edges (any-to-any)
- A secondary edge may link **any two nodes** regardless of tree position ("main paths acyclic,
  secondary paths interconnect semantically-related but distant nodes" — note 3).
- Edge fields: `type`=secondary, directed or symmetric flag, **relation embedding** (encodes the
  relationship), **verb-like relation tags** (e.g. `mentored`, `blocks`, `inspired-by`), `weight`.
- Tree invariant holds only for primary edges; secondary edges make the whole structure a general
  (possibly cyclic) graph.

### E3 — Storage backends
- **Neo4j** as the primary backend (labels, relationship types, native vector index).
- **In-memory reference backend** so the tool is **self-contained/runnable without a server** and
  serves as the executable spec for the storage contract.
- A single **storage interface** both implement; backend is swappable via config.

### E4 — Embeddings & entry-point discovery
- **Embedding provider abstraction** (pluggable model; offline/deterministic fallback so the tool
  runs with no network/keys).
- **Vector index** over node embeddings (and over secondary-edge embeddings).
- **Entry-point search**: given a query, return the top-k semantically nearest nodes as traversal
  seeds. **Hybrid** ranking = vector similarity + tag/label match.

### E5 — Agentic / dynamic traversal & context assembly
- From entry points, **traverse dynamically**: expand along primary (up/down the tree) and secondary
  (semantic) edges under agent control.
- Strategies: bounded BFS/DFS, best-first by relevance, follow-secondary-by-relation-tag.
- **Ranking** of visited nodes; **budgeted context assembly** (token/'node' budget) that returns a
  coherent subgraph + a rendered context blob (markdown) for an agent to consume.
- Deterministic, explainable traversal (record the path taken).

### E6 — Concurrency: read/write lock by agent id (note 2)
- **Shared read / exclusive write** locks, **keyed by `agent_id`**, so many agents share one graph.
- Lock **scopes**: node, subtree, whole-graph.
- Lock manager with acquire/release, re-entrancy per agent, **stale-lock expiry**, and clear
  conflict errors. Backend-agnostic (works for both stores).

### E7 — Write / ingest API
- Create/update nodes and edges; **upsert** by id; **auto-embed** on write.
- Basic **dedupe** (near-duplicate detection via embedding threshold) and provenance stamping.
- All writes go through the lock manager.

### E8 — Obsidian-like export
- Export the graph to a **vault of markdown files**: one file per node, YAML frontmatter (id, type,
  tags, embedding ref), body content.
- **Wikilinks** for edges: primary edges as parent/child links; secondary edges as `[[target]]`
  with the relation tag annotated. Renders as a navigable Obsidian graph.
- One-way export first; round-trip (import edits back) is a stretch item.

### E9 — CLI & DX
- `init`, `add-node`, `link`, `search`, `traverse`, `export`, `lock-status`, `demo` (load sample
  graph). Human-readable + `--json` output.
- Good README, docstrings, and a seeded **sample graph** for demoing without setup.

### E10 — Config & self-containedness
- Env/file config for backend selection, embedding provider, data paths.
- Works out-of-the-box with in-memory store + offline embeddings; Neo4j opt-in via config.

## Non-goals (this phase)
- Running/testing the code (design for runnability; defer execution).
- The **pi super-agent** and anything it needs (see PLANNING): progressive skill disclosure,
  short-term scratchpad memory, the **"ring-a-bell"** interrupt system, the **model-skill
  interpretation benchmark**. MCP tools explicitly out of scope for now.

## Appendix A — Owner's original framing (paraphrased)
Broad, dynamically traversable knowledge graph as agent context/memory — not merely a temporal graph
like Graphiti (time is just one of infinitely many contextual dimensions). A proper tree on primary
edges (root → life-sections → …), every node with an embedding + tags, node embeddings to find entry
points, agentic dynamic traversal, any-to-any secondary relation edges (with their own embedding +
verb tags), and an RW lock so agents share one graph. Obsidian-like, backed by a vector DB / Neo4j.

## Appendix B — Source self-notes (verbatim)
Routing: knowledge-graph items → this backlog; the rest → PLANNING's pi section.

- **(12/08 4:20 PM)** "Central knowledge graph with sections — work, ideas, personal org — all
  globally available. Standard skills used by context. BELL section: if anything rings a bell
  (cosine-distance match to past situations), fire an interrupt with a specific prompt/action."
  → *KG part* (sections, globally available) is scoped (E1). *BELL* → PLANNING/pi.
- **(14/08 2:53 PM)** "Locking system for writing to the knowledge graph by agent id. Split guidance
  vs behaviour (skills) from pure context/knowledge. A metric/benchmark for how different models
  interpret the same skill." → *Locking* (E6) and *split guidance/context* (E1) scoped. *Benchmark*
  → PLANNING/pi.
- **(14/08 2:56 PM)** "Acyclic graph for main paths, with secondary paths interconnecting
  semantically-related but distant nodes." → scoped (E1 tree acyclicity + E2 secondary edges).
