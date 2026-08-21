# Design — add-obsidian-export

- `export_vault(graph, out_dir)`: walk the tree from root; for each node compute folder path from
  its ancestor chain (slugified titles); write `<slug>.md`.
- Frontmatter via a tiny YAML writer (stdlib only; values are scalars/lists) — avoid a yaml dep.
- Body = node body + a `## Links` section listing outgoing secondary edges as `[[target-title]]
  (verb)`; unresolved/duplicate titles disambiguated by appending a short id.
- Idempotent: re-export overwrites the vault dir (a runtime artifact, gitignored).
- One-way export only; round-trip import is a documented stretch item, not built.
