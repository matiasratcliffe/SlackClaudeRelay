# Design — add-cli

- `argparse` subcommands; each maps to a `ContextGraph` call; `--json` toggles `json.dumps` vs a
  compact human formatter.
- Backend/embedder chosen from env/flags (`--backend memory|neo4j`), default `memory` + offline
  embedder → self-contained.
- State: `memory` backend is process-local, so `demo` builds the sample graph in-process and runs a
  query in one invocation (persistence across invocations is a Neo4j-backend concern, documented).
- `sample.py` seeds root → work/personal/ideas subtrees with people/projects/notes and a few
  secondary edges (mentors, blocks, inspired-by) for a meaningful demo.
- `main()` is the `context-graph` entry point declared in pyproject.
