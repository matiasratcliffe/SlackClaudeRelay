# Change: iteration-2-shared-truth

## Why (owner round-2 directives, reconciled against the initial prompt + 3 notes)
1. The graph must deploy with an **opinionated macro-node structure** (user preferences, skills,
   work facts, personal facts, …) with hardcoded descriptions — so every agent finds the same
   sections at deterministic ids — while free mode (bare root) stays available.
2. The owner's team/social-context case ("work/team primary-links teammates owned by the social
   subtree") needs multi-parent *navigation* without breaking single-parent *ownership* (locks).
   Resolution: **mount links** — a node has one ownership parent but may be mounted into other
   taxonomy spots; traversal and export treat mounts as hierarchy.
3. **Secondary edges are wormholes** for hopping to otherwise-unrelated parts of the graph, so they
   must carry more information than primary edges: endpoint **similarity**, **tree_distance**
   (wormhole value grows with hierarchical distance), and a free-text **rationale**.
4. One **common interface** for humans and agents, documented skill-ready (INTERFACE.md), and the
   pi section must record: the KG is the shared source of truth — PI sub-agents keep only limited
   chat history locally and write durable knowledge into the facts/preferences nodes.

## What changes
- `structure.py`: hardcoded taxonomy (fixed ids + descriptions); `deploy_structure(graph, mode)`.
- `model.MountLink`; store mount CRUD (memory + Neo4j `[:MOUNTS]`); `ContextGraph.mount()`.
- `SecondaryEdge.similarity / tree_distance / rationale`, computed at `link()` time; assembly
  renders the distance so the judgment layer sees wormhole value.
- CLI: `init --structure free|opinionated`, `mount` command.
- Docs: INTERFACE.md; PLANNING pi-section update; specs updated (graph-model, cli,
  new structure-templates capability).

## Impact
- Modified capabilities: `graph-model`, `storage`, `cli`. New capability: `structure-templates`.
- Code: `model.py`, `store/*`, `graph.py`, `traversal.py`, `assembly.py`, `export_obsidian.py`,
  `cli.py`, new `structure.py`; tests extended.
