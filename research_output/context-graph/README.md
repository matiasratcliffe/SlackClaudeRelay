# context-graph

A **dynamically traversable context knowledge graph** for agent long-term memory.

- A strict single-parent **ownership tree** of life-section nodes (work / personal / ideas / …). The
  tree carries **ownership + lock scope only** — never meaning.
- **Secondary semantic edges** connect *any* two nodes and carry their own embedding, verb-like
  relation tags, weight, and validity window. Meaning lives here.
- **Per-node embeddings** drive **entry-point** discovery; agents then **traverse** the graph
  mechanically (spreading activation / Personalized PageRank), and assemble a budgeted context blob.
- A **read/write lock keyed by agent id** (hierarchical intent locks on the tree; optimistic CAS on
  edges) lets many agents share one graph.
- Backends: **in-memory** (zero-dep reference, runs anywhere) and **Neo4j** (native vector index,
  reified edge nodes). **Obsidian-vault export** for human browsing.

> Scope: this is the **knowledge-graph tool** only. The future "pi" super-agent that would consume
> it (progressive skill disclosure, scratchpad short-term memory, the "ring-a-bell" interrupt,
> model-skill benchmark) is described in [docs/PLANNING.md](docs/PLANNING.md) and **not implemented**.

## Quick start (no setup)
```bash
pip install -e .
context-graph demo                       # seeded sample graph + a search & traverse
context-graph search "aurora mentor"
context-graph traverse "who mentors me on aurora" --budget 6
context-graph export --out vault-export  # open the folder as an Obsidian vault
```

Deploy a persistent graph with the **opinionated macro-node taxonomy** (fixed section ids:
`preferences`, `skills`, `work-facts`, `work-team`, `personal-facts`, `social`, … — see
[docs/INTERFACE.md](docs/INTERFACE.md)):
```bash
context-graph --db mygraph.json init --structure opinionated
context-graph --db mygraph.json add-node "Alex" --type person --parent social
context-graph --db mygraph.json mount work-team <alex-id>   # navigation graft; social keeps ownership
```
**Mounts** solve multi-parent navigation without breaking the single-parent ownership tree (locks):
a node has one owner but can appear in other hierarchy spots. **Secondary edges are wormholes** and
carry extra context — endpoint similarity, tree distance, and a rationale — because their job is to
justify hopping across otherwise-unrelated subtrees.
[docs/INTERFACE.md](docs/INTERFACE.md) is the single human/agent contract (skill-ready).
The default backend is in-memory with an **offline deterministic embedder** — no service or API key
needed. It is process-local (ephemeral); use Neo4j for persistence.

## Library
```python
from context_graph import ContextGraph, NodeType, Authority

g = ContextGraph()                       # in-memory + offline embeddings
g.ensure_root("Context")
work = g.add_node("Work", type=NodeType.SECTION, parent_id="root", tags=["work"])
jane = g.add_node("Jane Doe", type=NodeType.PERSON, parent_id=work.id)
me   = g.add_node("Me", parent_id="root")
g.link(jane.id, me.id, verb_tags=["mentors"], authority=Authority.USER_STATED)

for node, score in g.search("mentor"):
    print(score, node.title)
print(g.traverse("who mentors me", budget_nodes=6).markdown)
```

## Neo4j backend
```bash
pip install -e '.[neo4j]'
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=...
context-graph --backend neo4j init
```
Nodes are `:CtxNode`, primary edges `:CHILD_OF`, secondary edges reified as `:EdgeNode` (so edge
embeddings are index-able), with native vector indexes. See
[docs/RESEARCH-DIGEST.md](docs/RESEARCH-DIGEST.md) §5 for the Cypher.

## Layout
- `src/context_graph/` — the package (`model`, `store/`, `embeddings`, `locking`, `traversal`,
  `assembly`, `graph`, `export_obsidian`, `cli`, `sample`).
- `openspec/` — SDD: current-state capability specs (`specs/`) + Kiro-style per-story changes
  (`changes/archive/`). See [openspec/AGENTS.md](openspec/AGENTS.md).
- `docs/` — [INSTRUCTIONS](docs/INSTRUCTIONS.md), [BACKLOG](docs/BACKLOG.md),
  [PLANNING](docs/PLANNING.md), [RESEARCH-DIGEST](docs/RESEARCH-DIGEST.md).

## Design notes
The tree-is-ownership decision, two-layer traversal, reified edges, and concurrency model are
explained in [docs/PLANNING.md](docs/PLANNING.md) §2, grounded in the research digest.

## Status
First build phase: written but **not executed/tested** (per project instructions). The in-memory
path is designed to run as-is; the Neo4j Cypher is specified but unverified against a live server.
