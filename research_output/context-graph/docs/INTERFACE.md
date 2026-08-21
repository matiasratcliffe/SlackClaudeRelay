# INTERFACE — the common human/agent contract

One tool, one contract, two frontends: **humans use the CLI**, **agents use the `ContextGraph`
facade** (or the CLI with `--json`). Verbs, semantics, and section addresses are identical, so this
document can be lifted verbatim into an agent skill.

## The verbs (same across CLI and facade)
| Verb | CLI | Facade | Notes |
|---|---|---|---|
| Initialize | `init --structure free\|opinionated` | `deploy_structure(g, mode)` | opinionated = fixed macro nodes below |
| Add knowledge | `add-node <title> --type --parent --tag --body` | `g.add_node(...)` | auto-embeds; goes through locks |
| Relate (wormhole) | `link <src> <tgt> --verb v` | `g.link(..., rationale=...)` | stores similarity + tree_distance + rationale |
| Graft (navigation) | `mount <host> <node>` | `g.mount(host, node)` | ownership/locks unchanged |
| Find entry points | `search "<query>"` | `g.search(query)` | relative-cutoff hybrid ranking |
| Assemble context | `traverse "<q>" --budget N --strategy activation\|ppr` | `g.traverse(...)` | bounded, explainable, budgeted |
| Human view | `export --out <dir>` | `export_vault(g, dir)` | open as an Obsidian vault |
| Hub rollups | `summarize --threshold N` | `g.recompute_hub_summaries(N)` | summary-first hub traversal |
| Locks | `lock-status` | `g.locks.*` | per-agent-id; leases expire |

Persistence: `--db <file>` (memory backend) or `--backend neo4j`. Always pass **your own
`--agent <id>`** — locks, provenance, and telemetry key off it.

## Deterministic section addresses (opinionated structure)
Fixed node ids every deployment shares — address them directly, never search for them:
`preferences` · `skills` · `work` · `work-facts` · `work-team` · `work-projects` · `personal` ·
`personal-facts` · `personal-org` · `social` · `ideas`.

## Write etiquette (what goes where)
- **`preferences`** — durable owner preferences. Consult before acting; write new preference
  learnings here, not in chat history.
- **`skills`** — guidance/behaviour (HOW). Never store world-facts here.
- **`work-facts` / `personal-facts`** — durable facts (WHAT). Sub-agents persist learnings here.
- **`social`** — the ONLY owner of person nodes. Elsewhere, reference people by **mount** (e.g.
  under `work-team`) or secondary edge — never duplicate a person.
- **Secondary edges are wormholes**: create one only when hopping between otherwise-unrelated
  nodes would help future traversal, and say why in `rationale`. Hierarchical-feeling relations
  still belong on edges (`works_on`, `part_of`), not on the ownership tree.
- **Ephemeral working state** (today's itinerary, mid-task notes) does NOT belong in the graph —
  keep it in your scratchpad; promote only durable conclusions.
- Conflicting fact? Don't edit in place — `supersede()` the old edge (history is preserved).
