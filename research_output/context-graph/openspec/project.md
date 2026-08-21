# Project — context-graph

## Purpose
A context **knowledge graph** for agent long-term memory: a tree of life-section nodes with
per-node embeddings + tags, any-to-any secondary semantic edges, embedding-based entry-point search,
agentic traversal + context assembly, an RW lock keyed by agent id, Neo4j + in-memory backends, and
an Obsidian-style vault export.

## Tech stack
- **Python 3.11+**
- **Neo4j** (primary backend, native vector index) via the official `neo4j` driver.
- **In-memory backend** (reference implementation, zero-dependency, keeps the tool self-contained).
- Pluggable **embedding provider** with an offline deterministic fallback (no network/keys needed).
- CLI via `argparse` (stdlib) to avoid heavy deps.

## Conventions
- **SDD:** OpenSpec is the source of truth for *current-state* capability specs (`openspec/specs/`).
  Each change under `openspec/changes/` bundles the OpenSpec delta **and** Kiro-style per-story specs
  (`requirements.md` in EARS, `design.md`, `tasks.md`).
- **Clean code:** minimal moving parts, slim contract-only docstrings, one-line justifications for
  non-obvious choices.
- **Storage-agnostic core:** domain logic depends on the `StorageBackend` interface, never on a
  concrete backend.
- **Git:** commit to `main` in the enclosing `slack-agent` repo; conventional commits; no AI
  attribution; no PRs.

## Non-goals
The "pi" super-agent that would consume this graph is **out of scope** (described in
`docs/PLANNING.md`), along with MCP tooling, the "ring-a-bell" interrupt system, and the
model-skill-interpretation benchmark.
