# Design — iteration-2-shared-truth

- **MountLink** `{id, host_id, node_id, label?, created_at}` — the filesystem-symlink analog.
  Ownership (parent_id) is untouched; locks keep keying off ownership ancestors, so mount hosts
  never gain write authority over the mounted node. Store API: `put_mount`, `delete_mount`,
  `mounts_of(host)`, `mounted_at(node)`. Neo4j: `(host)-[:MOUNTS]->(node)`.
- **Structure templates** (`structure.py`): a literal list of `(id, parent, title, type, tags,
  description)` — descriptions hardcoded in code per the owner's directive. Fixed ids
  (`preferences`, `skills`, `work-facts`, `work-team`, `personal-facts`, `social`, …) so skills and
  agents can address sections deterministically. `deploy_structure(graph, mode)` is idempotent
  (skips nodes that already exist).
- **Wormhole enrichment**: at `link()` time compute `similarity = cosine(src.embedding,
  tgt.embedding)` and `tree_distance` = ownership-path distance (len(pa)+len(pb)−2·common−…, i.e.
  hops via the lowest common ancestor). `rationale` is caller-supplied free text. Traversal
  mechanics stay unchanged (weight still drives propagation); the metadata is for the agentic
  judgment layer, rendered by assembly as `(verb, d<N>)`.
- **Traversal**: `_neighbors` adds mount hops in both directions at `primary_weight` with label
  `mount`.
- **Export**: host files get a `## Mounted here` wikilink section.
- **CLI**: `init --structure`, new `mount <host> <node>`; both persist under `--db`.
- **INTERFACE.md**: single contract for humans (CLI) and agents (facade), including macro ids and
  section write-etiquette; written to be liftable into a skill verbatim.
