# Requirements (EARS) — add-obsidian-export

## User story
As the owner, I want to browse the graph in Obsidian to see what agents remember.

## Requirements
- R1. WHEN exporting, the system SHALL write one markdown file per node at its primary-tree folder
  path.
- R2. The system SHALL emit YAML frontmatter (`id`, `type`, `tags`, `owner`, `version`, timestamps)
  and the node `body`, omitting the raw embedding.
- R3. WHEN a node has secondary edges, the system SHALL render each as `[[Target]] (verb)` in the
  body so backlinks/graph view surface it.

## Acceptance criteria
- Node under `work/project-x` exports to `work/project-x/<node>.md`.
- A `mentors` edge appears as `[[Target]] (mentors)`.
